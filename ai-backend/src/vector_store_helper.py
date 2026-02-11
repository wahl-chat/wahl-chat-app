# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import os
from pathlib import Path
from typing import Union
import logging

from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from src.models.context import ContextParty

from src.utils import load_env, safe_load_api_key

from src.chatbot_async import rerank_documents
from functools import lru_cache

load_env()

logger = logging.getLogger(__name__)

BASE_PATH = Path(__file__).parent
EMBEDDING_SIZE = 3072  # Embedding sizes for the OpenAI models: https://platform.openai.com/docs/guides/embeddings#how-to-get-embeddings

# Get environment suffix
env = os.getenv("ENV", "dev")
env_suffix = f"_{env}" if env in ["prod", "dev"] else "_dev"

# Default context for backwards compatibility
DEFAULT_CONTEXT_ID = "bundestagswahl-2025"

# Legacy collection names (kept for backwards compatibility)
PARTY_INDEX_NAME = f"all_parties{env_suffix}"
VOTING_BEHAVIOR_INDEX_NAME = f"justified_voting_behavior{env_suffix}"
PARLIAMENTARY_QUESTIONS_INDEX_NAME = f"parliamentary_questions{env_suffix}"


def get_context_collection_name(context_id: str) -> str:
    """Get the Qdrant collection name for party documents in a given context.

    Args:
        context_id: The context identifier (e.g., 'bundestagswahl-2025')

    Returns:
        The collection name in format: context_{context_id}_party_docs_{env}
    """
    return f"context_{context_id}_party_docs{env_suffix}"


embed = OpenAIEmbeddings(
    model="text-embedding-3-large", openai_api_key=safe_load_api_key("OPENAI_API_KEY")
)

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

# Initialize Qdrant vector stores
voting_behavior_vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=VOTING_BEHAVIOR_INDEX_NAME,
    embedding=embed,
    vector_name="dense",
    content_payload_key="text",
)
parliamentary_questions_vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=PARLIAMENTARY_QUESTIONS_INDEX_NAME,
    embedding=embed,
    vector_name="dense",
    content_payload_key="text",
)


def _search_results_to_documents(search_result: list) -> list[Document]:
    """Convert Qdrant search results to LangChain Documents."""
    documents = []
    for point in search_result:
        if point.payload is None:
            continue
        content = point.payload.get("text", "")
        metadata = {k: v for k, v in point.payload.items() if k != "text"}
        documents.append(Document(page_content=content, metadata=metadata))
    return documents


@lru_cache(maxsize=16)
def _get_vector_store_for_context(context_id: str) -> QdrantVectorStore:
    """Get or create a QdrantVectorStore for a given context.

    For the default context (bundestagswahl-2025), uses the legacy collection
    name for backwards compatibility. For other contexts, uses the new
    context-scoped naming convention.

    Args:
        context_id: The context identifier

    Returns:
        QdrantVectorStore instance for the context
    """
    # Use legacy collection for default context (backwards compatibility)
    if context_id == DEFAULT_CONTEXT_ID:
        collection_name = PARTY_INDEX_NAME
    else:
        collection_name = get_context_collection_name(context_id)

    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=embed,
        vector_name="dense",
        content_payload_key="text",
    )


async def _identify_relevant_documents(
    namespace: str,
    rag_query: str,
    n_docs: int = 5,
    score_threshold: float = 0.5,
    context_id: str = DEFAULT_CONTEXT_ID,
) -> list[Document]:
    """
    Identify relevant documents based on the provided query and namespace.
    Uses direct Qdrant client to ensure all metadata is preserved.

    Args:
        namespace: The namespace to filter documents by (e.g., party_id)
        rag_query: The query to search for relevant documents
        n_docs: The number of documents to return
        score_threshold: The score threshold for the similarity search
        context_id: The context identifier (defaults to 'bundestagswahl-2025')

    Returns:
        A list of relevant documents
    """
    # Determine collection name
    if context_id == DEFAULT_CONTEXT_ID:
        collection_name = PARTY_INDEX_NAME
    else:
        collection_name = get_context_collection_name(context_id)

    # Check if collection exists before trying to search
    existing_collections = [
        col.name for col in qdrant_client.get_collections().collections
    ]
    if collection_name not in existing_collections:
        logger.warning(
            f"Collection '{collection_name}' does not exist. "
            f"No documents have been uploaded for context '{context_id}' yet."
        )
        return []

    # Get the vector store for this context
    vector_store = _get_vector_store_for_context(context_id)

    # Get query vector
    query_vector = await embed.aembed_query(rag_query)

    # Create filter for the namespace
    filter_condition = Filter(
        must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
    )

    # Search directly using Qdrant client to preserve all metadata
    # Note: Using sync client in async context - this might need optimization later
    search_result = qdrant_client.search(
        collection_name=vector_store.collection_name,
        query_vector=("dense", query_vector),
        limit=n_docs,
        with_payload=True,
        query_filter=filter_condition,
        score_threshold=score_threshold,
    )

    return _search_results_to_documents(search_result)


async def identify_relevant_docs(
    party: ContextParty,
    rag_query: str,
    n_docs: int = 5,
    score_threshold: float = 0.5,
    context_id: str = DEFAULT_CONTEXT_ID,
) -> list[Document]:
    """Identify relevant documents for a party within a context.

    Args:
        party: The party to search documents for
        rag_query: The query to search for relevant documents
        n_docs: The number of documents to return
        score_threshold: The score threshold for the similarity search
        context_id: The context identifier (defaults to 'bundestagswahl-2025')

    Returns:
        A list of relevant documents
    """
    return await _identify_relevant_documents(
        namespace=party.party_id,
        rag_query=rag_query,
        n_docs=n_docs,
        score_threshold=score_threshold,
        context_id=context_id,
    )


async def identify_relevant_docs_with_reranking(
    party: ContextParty,
    rag_query: str,
    n_docs: int = 20,
    score_threshold: float = 0.5,
    context_id: str = DEFAULT_CONTEXT_ID,
) -> list[Document]:
    """Identify relevant documents with reranking for a party within a context.

    Args:
        party: The party to search documents for
        rag_query: The query to search for relevant documents
        n_docs: The number of documents to return
        score_threshold: The score threshold for the similarity search
        context_id: The context identifier (defaults to 'bundestagswahl-2025')

    Returns:
        A list of relevant documents (top 5)
    """
    relevant_docs = await _identify_relevant_documents(
        namespace=party.party_id,
        rag_query=rag_query,
        n_docs=n_docs,
        score_threshold=score_threshold,
        context_id=context_id,
    )

    # For now, return without external reranking since we're moving away from Pinecone
    # TODO: Implement alternative reranking if needed
    return relevant_docs[:5]  # Return top 5 documents


async def identify_relevant_docs_with_llm_based_reranking(
    party: ContextParty,
    rag_query: str,
    chat_history: str,
    user_message: str,
    n_docs: int = 20,
    score_threshold: float = 0.5,
    context_id: str = DEFAULT_CONTEXT_ID,
) -> list[Document]:
    """Identify relevant documents with LLM-based reranking for a party within a context.

    Args:
        party: The party to search documents for
        rag_query: The query to search for relevant documents
        chat_history: The chat history for reranking context
        user_message: The user message for reranking context
        n_docs: The number of documents to return
        score_threshold: The score threshold for the similarity search
        context_id: The context identifier (defaults to 'bundestagswahl-2025')

    Returns:
        A list of relevant documents (reranked if >= 5 docs)
    """
    relevant_docs = await _identify_relevant_documents(
        namespace=party.party_id,
        rag_query=rag_query,
        n_docs=n_docs,
        score_threshold=score_threshold,
        context_id=context_id,
    )

    # Note: We lose the score information when using direct Qdrant search
    # If score sorting is critical, we could modify _identify_relevant_documents
    # to return scores as well

    if len(relevant_docs) >= 5:
        # get indices of relevant docs
        relevant_docs = await rerank_documents(
            relevant_docs=relevant_docs,
            user_message=user_message,
            chat_history=chat_history,
        )
        return relevant_docs
    else:
        return relevant_docs


async def identify_relevant_votes(
    rag_query: str, n_docs: int = 5, score_threshold: float = 0.5
) -> list[Document]:
    """
    Identify relevant votes based on the provided query.

    Note: Votes are stored in a separate collection and are not context-scoped.

    :param rag_query: The query to search for relevant documents.
    :param n_docs: The number of documents to return.
    :param score_threshold: The score threshold for the similarity search.
    :return: A list of relevant documents.
    """
    # Votes use a separate collection, not context-scoped
    # Get query vector
    query_vector = await embed.aembed_query(rag_query)

    filter_condition = Filter(
        must=[FieldCondition(key="namespace", match=MatchValue(value="vote_summary"))]
    )

    search_result = qdrant_client.search(
        collection_name=voting_behavior_vector_store.collection_name,
        query_vector=("dense", query_vector),
        limit=n_docs,
        with_payload=True,
        query_filter=filter_condition,
        score_threshold=score_threshold,
    )

    return _search_results_to_documents(search_result)


async def identify_relevant_parliamentary_questions(
    party: Union[ContextParty, str],
    rag_query: str,
    n_docs: int = 5,
    score_threshold: float = 0.7,
) -> list[Document]:
    """
    Identify relevant parliamentary questions based on the provided query and party.

    Note: Parliamentary questions are stored in a separate collection and are not context-scoped.
    """
    namespace = f"{party.party_id if isinstance(party, ContextParty) else party}-parliamentary-questions"

    # Parliamentary questions use a separate collection, not context-scoped
    query_vector = await embed.aembed_query(rag_query)

    filter_condition = Filter(
        must=[FieldCondition(key="namespace", match=MatchValue(value=namespace))]
    )

    search_result = qdrant_client.search(
        collection_name=parliamentary_questions_vector_store.collection_name,
        query_vector=("dense", query_vector),
        limit=n_docs,
        with_payload=True,
        query_filter=filter_condition,
        score_threshold=score_threshold,
    )

    return _search_results_to_documents(search_result)
