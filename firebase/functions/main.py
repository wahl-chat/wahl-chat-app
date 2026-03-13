# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import datetime
import os
import tempfile
import time
import uuid

from firebase_functions.params import StringParam
from firebase_functions.options import SupportedRegion, MemoryOption
from firebase_functions import storage_fn, logger
from firebase_admin import initialize_app, storage, firestore
import google.cloud.firestore

from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointIdsList,
    PayloadSchemaType,
    PointStruct,
)

from models import PartySource  # type: ignore


ENV = StringParam("ENV")  # "dev" or "prod"
OPENAI_API_KEY = StringParam("OPENAI_API_KEY")
QDRANT_URL = StringParam("QDRANT_URL")
QDRANT_API_KEY = StringParam("QDRANT_API_KEY")

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_SIZE = 3072  # Embedding sizes for the OpenAI models: https://platform.openai.com/docs/guides/embeddings#how-to-get-embeddings

# Get environment from OS environment variable or Firebase project ID for region selection
# This is evaluated at module load time, before StringParam values are available
_env_from_os = os.getenv("ENV", "dev")
_project_id = os.getenv("GCLOUD_PROJECT", os.getenv("GCP_PROJECT", ""))

# Get environment suffix for collection naming
env_suffix = f"_{ENV.value}" if ENV.value in ["prod", "dev"] else "_dev"

# Legacy collection name for backwards compatibility
ALL_PARTIES_COLLECTION = f"all_parties{env_suffix}"

# Default context for backwards compatibility
DEFAULT_CONTEXT_ID = "bundestagswahl-2025"


def get_context_collection_name(context_id: str) -> str:
    """Get the Qdrant collection name for a given context.

    For the default context (bundestagswahl-2025), uses the legacy collection
    name for backwards compatibility. For other contexts, uses the new
    context-scoped naming convention.

    Args:
        context_id: The context identifier (e.g., 'bundestagswahl-2025')

    Returns:
        The collection name
    """
    if context_id == DEFAULT_CONTEXT_ID:
        return ALL_PARTIES_COLLECTION
    return f"context_{context_id}_party_docs{env_suffix}"


# Set region based on environment at module load time
# For prod (project: wahl-chat), use US_EAST1; for dev (project: wahl-chat-dev), use EUROPE_WEST1
# Check both ENV variable and project ID to determine region
_is_prod = _env_from_os == "prod" or _project_id == "wahl-chat"
STORAGE_TRIGGER_FN_REGION = (
    SupportedRegion.US_EAST1 if _is_prod else SupportedRegion.EUROPE_WEST1
)

initialize_app()


def is_party_pdf_for_vector_store(
    event: storage_fn.CloudEvent[storage_fn.StorageObjectData], name: str
):
    """Check if the file is a party PDF that should be added to the vector store.

    Expected path format: public/{context_id}/{party_id}/{filename}
    Example: public/bundestagswahl-2025/spd/wahlprogramm_2025-01-01.pdf
    """
    # Make sure the file is in the public subdirectory
    if not name.startswith("public/"):
        logger.info(f"Skipping file as it is not in the public directory: {name}")
        return False

    # Check if the file is in the expected directory structure
    # Expected: public/{context_id}/{party_id}/{filename} = exactly 4 parts
    path_parts = name.split("/")
    if len(path_parts) != 4:
        logger.info(
            f"Skipping file as it does not match expected path format "
            f"'public/{{context_id}}/{{party_id}}/{{filename}}': {name}"
        )
        return False

    # Validate that path components are non-empty
    context_id, party_id, filename = path_parts[1], path_parts[2], path_parts[3]
    if not context_id or not party_id or not filename:
        logger.info(f"Skipping file as path contains empty components: {name}")
        return False

    # Check if the file is a PDF
    if not event.data.content_type == "application/pdf":
        # TODO: consider adding support for other document types
        logger.info(f"Skipping file as it is not a PDF: {name}")
        return False
    return True


def download_pdf(bucket_name: str, name: str):
    bucket = storage.bucket(bucket_name)
    pdf_blob = bucket.blob(name)

    # Create a named temporary file for the PDF, ensuring delete=False
    # so we can manage cleanup manually.
    tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_file_name = tmp_file.name
    tmp_file.close()  # Close the file so we can write to it

    pdf_blob.download_to_filename(tmp_file_name)
    logger.info(f"Downloaded file to temporary path: {tmp_file_name}")

    return tmp_file_name, pdf_blob


def split_pdf(file_path: str):
    # Load the document as a PDF and split it into chunks
    # TODO: consider switching to PDFMiner (https://www.reddit.com/r/LangChain/comments/13jd9wo/comment/jkh2f9j/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button)
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    chunk_size = 1000
    chunk_overlap = 100
    length_function = len
    is_separator_regex = False
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=length_function,
        is_separator_regex=is_separator_regex,
    )
    logger.info(
        f"Splitting the document with chunk size={chunk_size} and overlap={chunk_overlap}"
    )

    splits = text_splitter.split_documents(pages)
    # Free up memory
    del pages
    del loader
    logger.info(f"Split the document into {len(splits)} chunks")
    return splits


def create_collection_if_not_exists(
    qdrant_client: QdrantClient, collection_name: str, embedding_size: int
):
    existing_collections = [
        col.name for col in qdrant_client.get_collections().collections
    ]
    if collection_name not in existing_collections:
        logger.info(f"Creating Qdrant collection {collection_name}")
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(size=embedding_size, distance=Distance.COSINE)
            },
        )
        while not qdrant_client.collection_exists(collection_name=f"{collection_name}"):
            time.sleep(1)
        logger.info(f"Collection {collection_name} created")

    # Always ensure payload indexes exist (even for existing collections)
    # Create payload index for 'namespace' to improve query performance (following migration pattern)
    try:
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="namespace",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info(f"Created namespace index for collection {collection_name}")
    except Exception as e:
        # Index might already exist, which is fine
        logger.debug(
            f"Namespace index for {collection_name} already exists or could not be created: {str(e)}"
        )

    # Create payload index for 'source_document' to improve deletion performance
    try:
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="source_document",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info(f"Created source_document index for collection {collection_name}")
    except Exception as e:
        # Index might already exist, which is fine
        logger.debug(
            f"Source_document index for {collection_name} already exists or could not be created: {str(e)}"
        )


def add_to_collection(splits: list[Document], collection_name: str, namespace: str):
    logger.info(
        f"Adding {len(splits)} splits to collection {collection_name} with namespace {namespace}"
    )

    # TODO: consider switching to NV-Embed-v2 or a similar high-performing embedding model (https://huggingface.co/spaces/mteb/leaderboard) potentially by leveraging (https://github.com/michaelfeil/infinity)
    embed = OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=OPENAI_API_KEY.value)

    qdrant_client = QdrantClient(
        url=QDRANT_URL.value,
        api_key=QDRANT_API_KEY.value if QDRANT_API_KEY.value else None,
        timeout=120,  # Increase timeout to 120 seconds
    )

    create_collection_if_not_exists(qdrant_client, collection_name, EMBEDDING_SIZE)

    # Verify all documents have IDs and namespace - these should be set before calling this function
    for split in splits:
        if not hasattr(split, "id") or not split.id:
            raise ValueError(f"Document missing ID: {split.page_content[:50]}...")
        if "namespace" not in split.metadata:
            raise ValueError(f"Document missing namespace in metadata: {split.id}")

    # Process documents in batches to avoid timeout
    batch_size = 50  # Adjust based on your needs
    total_batches = (len(splits) + batch_size - 1) // batch_size

    logger.info(
        f"Starting batch upload: {len(splits)} documents in {total_batches} batches of {batch_size}"
    )

    for i in range(0, len(splits), batch_size):
        batch = splits[i : i + batch_size]
        batch_num = (i // batch_size) + 1

        logger.info(
            f"Processing batch {batch_num}/{total_batches} with {len(batch)} documents"
        )

        # Log first document metadata for debugging
        if batch:
            sample_doc = batch[0]
            logger.info(
                f"Sample document ID: {sample_doc.id if hasattr(sample_doc, 'id') else 'NO_ID'}"
            )
            logger.info(f"Sample metadata keys: {list(sample_doc.metadata.keys())}")
            logger.info(
                f"Sample namespace: {sample_doc.metadata.get('namespace', 'MISSING')}"
            )
            logger.info(f"Sample content length: {len(sample_doc.page_content)}")

        try:
            # Use direct Qdrant client with explicit IDs instead of LangChain wrapper
            # This ensures our custom UUIDs are preserved

            # Generate embeddings for the batch
            texts = [doc.page_content for doc in batch]
            embeddings = embed.embed_documents(texts)

            # Create points with explicit IDs and metadata
            points = []
            for doc, embedding in zip(batch, embeddings):
                # Prepare payload with content and all metadata
                payload = {
                    "text": doc.page_content,  # Content stored in 'text' field
                    **doc.metadata,  # All metadata fields
                }

                # Ensure ID is a string (should always be set by caller)
                point_id = (
                    str(doc.id)
                    if doc.id
                    else str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.page_content))
                )

                point = PointStruct(
                    id=point_id,  # Use our custom UUID
                    vector={"dense": embedding},  # Named vector
                    payload=payload,
                )
                points.append(point)

            # Upload points to Qdrant
            qdrant_client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True,  # Wait for operation to complete
            )

            logger.info(f"Successfully added batch {batch_num}/{total_batches}")
            logger.info(
                f"Uploaded {len(points)} points with IDs: {[p.id[:8] + '...' for p in points[:3]]}"
            )
        except Exception as e:
            logger.error(f"Error adding batch {batch_num}/{total_batches}: {str(e)}")
            # Retry with smaller batch size
            if len(batch) > 1:
                logger.info(f"Retrying batch {batch_num} with individual documents")
                for j, doc in enumerate(batch):
                    try:
                        # Retry individual document with direct client
                        text = doc.page_content
                        embedding = embed.embed_documents([text])[0]

                        payload = {"text": text, **doc.metadata}

                        # Ensure ID is a string
                        point_id = (
                            str(doc.id)
                            if doc.id
                            else str(uuid.uuid5(uuid.NAMESPACE_DNS, text))
                        )

                        point = PointStruct(
                            id=point_id, vector={"dense": embedding}, payload=payload
                        )

                        qdrant_client.upsert(
                            collection_name=collection_name, points=[point], wait=True
                        )

                        logger.info(
                            f"Successfully added document {j + 1}/{len(batch)} from batch {batch_num}"
                        )
                    except Exception as doc_e:
                        logger.error(
                            f"Failed to add document {j + 1} from batch {batch_num}: {str(doc_e)}"
                        )
                        # Continue with next document instead of failing completely
                        continue
            else:
                logger.error(
                    f"Failed to add single document in batch {batch_num}: {str(e)}"
                )
                # Continue with next batch instead of failing completely
                continue

    # Verify the upload by checking collection count for this namespace
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        count_result = qdrant_client.count(
            collection_name=collection_name,
            exact=True,
            count_filter=Filter(
                must=[
                    FieldCondition(key="namespace", match=MatchValue(value=namespace))
                ]
            ),
        )
        logger.info(
            f"Completed adding splits to collection {collection_name} with namespace {namespace}"
        )
        logger.info(
            f"Total documents in collection with namespace '{namespace}': {count_result.count}"
        )
    except Exception as e:
        logger.warning(f"Could not verify document count: {str(e)}")
        logger.info(
            f"Completed adding splits to collection {collection_name} with namespace {namespace}"
        )


def add_source_document_to_firebase(
    document_id: str, context_id: str, party_id: str, source: PartySource
):
    """Add a source document reference to Firestore.

    Args:
        document_id: The document identifier (filename without extension)
        context_id: The context identifier (e.g., 'bundestagswahl-2025')
        party_id: The party identifier (e.g., 'spd')
        source: The PartySource object with document metadata

    Firestore path: sources/{context_id}/parties/{party_id}/source_documents/{document_id}
    """
    firestore_client: google.cloud.firestore.Client = firestore.client()
    source_info_ref = (
        firestore_client.collection("sources")
        .document(context_id)
        .collection("parties")
        .document(party_id)
        .collection("source_documents")
        .document(document_id)
    )

    source_info_ref.set(source.model_dump())


def delete_source_document_from_firebase(
    document_id: str, context_id: str, party_id: str
):
    """Delete a source document reference from Firestore.

    Args:
        document_id: The document identifier (filename without extension)
        context_id: The context identifier (e.g., 'bundestagswahl-2025')
        party_id: The party identifier (e.g., 'spd')

    Firestore path: sources/{context_id}/parties/{party_id}/source_documents/{document_id}
    """
    firestore_client: google.cloud.firestore.Client = firestore.client()
    source_info_ref = (
        firestore_client.collection("sources")
        .document(context_id)
        .collection("parties")
        .document(party_id)
        .collection("source_documents")
        .document(document_id)
    )
    source_info_ref.delete()


def build_vector_prefix(name: str):
    prefix = name.lower()
    prefix = prefix.replace("/", "#").replace(".", "_")
    # replace umlauts with their ASCII representation
    prefix = prefix.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return prefix


# Implement a function that adds a pdf document to a vector store when a new document is uploaded to the storage bucket
@storage_fn.on_object_finalized(
    region=STORAGE_TRIGGER_FN_REGION, timeout_sec=540, memory=MemoryOption.GB_1
)
def on_party_document_upload(
    event: storage_fn.CloudEvent[storage_fn.StorageObjectData],
):
    bucket_name = event.data.bucket
    name = event.data.name
    logger.info(f"Processing file: gs://{bucket_name}/{name}")

    # Print event info
    logger.info(f"Event id: {event.id}")
    logger.info(f"Event type: {event.type}")
    logger.info(f"Event source: {event.source}")
    logger.info(f"Event time: {event.time}")
    logger.info(f"Event data: {event.data}")
    logger.info(f"Event data content type: {event.data.content_type}")
    logger.info(f"Event data size: {event.data.size}")

    if not is_party_pdf_for_vector_store(event, name):
        return

    # Extract path components: public/{context_id}/{party_id}/{filename}
    path_parts = name.split("/")
    context_id = path_parts[1]
    party_id = path_parts[2]
    file_name = path_parts[3].removesuffix(".pdf")

    logger.info(f"Extracted context_id: {context_id}, party_id: {party_id}")

    # Download the document from the storage bucket
    file_path, pdf_blob = download_pdf(bucket_name, name)

    # Split the document into chunks
    splits = split_pdf(file_path)

    # Delete the local file
    os.remove(file_path)

    # Parse the file name for metadata
    file_name_parts = file_name.split("_")
    # Make sure the file name is in the expected format
    if len(file_name_parts) != 2:
        raise ValueError(
            f"File name {file_name} does not match the expected format: [document_name]_[document_date]"
        )
    document_name = file_name_parts[0]
    document_date_str = file_name_parts[1]
    # Make sure the date is in the expected format
    try:
        document_date = datetime.strptime(document_date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Document date {document_date_str} does not match the expected format: YYYY-MM-DD"
        )

    # Enable and create a public URL for the PDF
    pdf_blob.make_public()
    download_url = pdf_blob.public_url

    # Get the context-scoped collection name
    collection_name = get_context_collection_name(context_id)
    logger.info(f"Using collection: {collection_name}")

    prefix = build_vector_prefix(name)
    for split in splits:
        # Generate deterministic UUID based on page content for Qdrant compatibility
        qdrant_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, split.page_content))
        split.id = qdrant_uuid

        # Add comprehensive metadata following the migration pattern
        # Core document metadata
        split.metadata["source_document"] = str(name)  # Full path as string
        split.metadata["url"] = str(download_url)  # URL as string
        split.metadata["file_name"] = str(file_name)  # File name without extension
        split.metadata["document_name"] = str(document_name)  # Document display name
        split.metadata["document_publish_date"] = str(
            document_date_str
        )  # Date as string (YYYY-MM-DD)

        # Numeric metadata for potential filtering/sorting
        # Handle page number safely - it might already exist from PDF parsing
        existing_page = split.metadata.get("page", 0)
        if existing_page is None:
            existing_page = 0
        try:
            split.metadata["page"] = float(existing_page)  # Page number as float
        except (ValueError, TypeError):
            split.metadata["page"] = 0.0  # Default to 0 if conversion fails

        split.metadata["size"] = int(len(split.page_content))  # Content size as integer

        # Timestamps for tracking
        split.metadata["created_at"] = str(
            datetime.now().isoformat()
        )  # ISO format timestamp
        split.metadata["updated_at"] = str(
            datetime.now().isoformat()
        )  # ISO format timestamp

        # Document type classification (required for payload indexing)
        split.metadata["document_type"] = "pdf"  # Document format
        split.metadata["source_type"] = "party_document"  # Source category

        # Add namespace for filtering/querying
        split.metadata["namespace"] = party_id  # Party ID as namespace

        # Add context_id to metadata for cross-context queries
        split.metadata["context_id"] = context_id

        # Content enhancement for speeches
        if "rede" in prefix:
            split.page_content = f"Ausschnitt aus {prefix}\n\n{split.page_content}"
            split.metadata["content_type"] = "speech_excerpt"
        else:
            split.metadata["content_type"] = "document_excerpt"

    # Add the document to the context-scoped collection with the namespace of the party
    add_to_collection(splits, collection_name, namespace=party_id)

    # Add the source information to Firestore
    logger.info(
        f"Adding source document {document_name} for context {context_id}, party {party_id} to Firestore"
    )
    # create datetime object from string
    source = PartySource(
        name=document_name, publish_date=document_date, storage_url=download_url
    )

    add_source_document_to_firebase(
        document_id=file_name, context_id=context_id, party_id=party_id, source=source
    )
    logger.info("Added source information to Firestore")


@storage_fn.on_object_deleted(
    region=STORAGE_TRIGGER_FN_REGION, timeout_sec=540, memory=MemoryOption.MB_512
)
def on_party_document_deleted(
    event: storage_fn.CloudEvent[storage_fn.StorageObjectData],
):
    bucket_name = event.data.bucket
    name = event.data.name
    logger.info(f"Deleting splits associated with file: gs://{bucket_name}/{name}")

    # Print event info
    logger.info(f"Event id: {event.id}")
    logger.info(f"Event type: {event.type}")
    logger.info(f"Event source: {event.source}")
    logger.info(f"Event time: {event.time}")
    logger.info(f"Event data: {event.data}")

    if not is_party_pdf_for_vector_store(event, name):
        return

    # Extract path components: public/{context_id}/{party_id}/{filename}
    path_parts = name.split("/")
    context_id = path_parts[1]
    party_id = path_parts[2]
    file_name = path_parts[3].removesuffix(".pdf")

    logger.info(f"Extracted context_id: {context_id}, party_id: {party_id}")

    # Delete source document from Firestore
    logger.info(f"Deleting source document {file_name} from Firestore")
    delete_source_document_from_firebase(
        document_id=file_name, context_id=context_id, party_id=party_id
    )
    logger.info(f"Deleted source document {file_name} from Firestore")

    # Initialize Qdrant client
    qdrant_client = QdrantClient(
        url=QDRANT_URL.value,
        api_key=QDRANT_API_KEY.value if QDRANT_API_KEY.value else None,
        timeout=120,  # Increase timeout to 120 seconds
    )

    # Get the context-scoped collection name
    collection_name = get_context_collection_name(context_id)
    logger.info(f"Using collection: {collection_name}")

    existing_collections = [
        col.name for col in qdrant_client.get_collections().collections
    ]
    if collection_name not in existing_collections:
        logger.info(
            f"Collection {collection_name} does not exist. No deletion of document splits required."
        )
        return

    # Ensure payload indexes exist for filtering (same as in upload)
    try:
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="namespace",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info(f"Ensured namespace index exists for collection {collection_name}")
    except Exception as e:
        logger.debug(f"Namespace index already exists: {str(e)}")

    try:
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="source_document",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info(
            f"Ensured source_document index exists for collection {collection_name}"
        )
    except Exception as e:
        logger.debug(f"Source_document index already exists: {str(e)}")

    prefix = f"{build_vector_prefix(name)}#"

    logger.info(
        f"Deleting splits from collection {collection_name} with namespace {party_id} and prefix {prefix}"
    )

    # In Qdrant, we need to use filters to find and delete documents
    # Filter based on namespace and source_document (following migration pattern)
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    filter_condition = Filter(
        must=[
            FieldCondition(key="namespace", match=MatchValue(value=party_id)),
            FieldCondition(key="source_document", match=MatchValue(value=name)),
        ]
    )

    logger.info(
        f"Searching for documents to delete with filter: namespace={party_id}, source_document={name}"
    )

    # Search for documents to delete using scroll to get all matching points
    try:
        # Get count of points to delete (for logging only)
        count_result = qdrant_client.count(
            collection_name=collection_name,
            exact=True,  # Use exact count to know how many to expect
            count_filter=filter_condition,  # Note: parameter is 'count_filter' not 'filter'
        )
        expected_count = count_result.count

        logger.info(f"Found {expected_count} documents to delete")

        if expected_count == 0:
            logger.info("No documents found to delete")
            return

        # Scroll through ALL matching documents with pagination
        # Qdrant's scroll API returns results in pages, we need to iterate through all pages
        point_ids = []
        next_page_offset = None
        scroll_limit = 100  # Process 100 points per scroll request

        logger.info("Starting scroll through documents with filter")

        while True:
            scroll_result = qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter=filter_condition,
                limit=scroll_limit,
                offset=next_page_offset,  # Continue from where we left off
                with_payload=False,  # Don't need payload for deletion
                with_vectors=False,  # Don't need vectors for deletion
            )

            # scroll returns (points, next_page_offset)
            points, next_page_offset = scroll_result

            # Extract IDs from this page
            page_ids = [point.id for point in points]
            point_ids.extend(page_ids)

            logger.info(
                f"Scrolled {len(page_ids)} points (total so far: {len(point_ids)})"
            )

            # If no next_page_offset, we've reached the end
            if next_page_offset is None or len(points) == 0:
                break

        logger.info(
            f"Finished scrolling. Collected {len(point_ids)} point IDs to delete (expected {expected_count})"
        )

        if point_ids:
            logger.info(
                f"Deleting {len(point_ids)} document splits from collection {collection_name}"
            )

            # Delete in batches to avoid potential issues with large deletions
            batch_size = 100
            for i in range(0, len(point_ids), batch_size):
                batch_ids = point_ids[i : i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(point_ids) + batch_size - 1) // batch_size

                logger.info(
                    f"Deleting batch {batch_num}/{total_batches} with {len(batch_ids)} points"
                )

                qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=PointIdsList(points=batch_ids),
                    wait=True,  # Wait for operation to complete
                )

                logger.info(f"Successfully deleted batch {batch_num}/{total_batches}")

            logger.info(f"Successfully deleted all {len(point_ids)} document splits")
        else:
            logger.info("No document splits found to delete")

    except Exception as e:
        logger.error(
            f"Error deleting splits from collection {collection_name}: {str(e)}"
        )
        # Re-raise the exception to ensure the function fails if deletion fails
        raise e

    logger.info(
        f"Deleted splits from collection {collection_name} with namespace {party_id}"
    )
