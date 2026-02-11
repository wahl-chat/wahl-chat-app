# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import os
import logging

from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

DELETE_FROM_PROD = False

if not DELETE_FROM_PROD:
    load_dotenv(override=True)
else:
    load_dotenv("../../.env.prod", override=True)
print(f"ENV={os.getenv('ENV')}")

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_SIZE = 3072  # Embedding sizes for the OpenAI models: https://platform.openai.com/docs/guides/embeddings#how-to-get-embeddings

INDEX_NAME = "all-parties-index"

embed = OpenAIEmbeddings(
    model=EMBEDDING_MODEL, openai_api_key=os.getenv("OPENAI_API_KEY")
)
pc = Pinecone(pinecone_api_key=os.getenv("PINECONE_API_KEY"), embedding=embed)

index = pc.Index(INDEX_NAME)

PARTY_ID = "volt"
ORIGINAL_STORAGE_DOCUMENT_NAME = "Programm BTW25_2025-01-06.pdf"
OLD_FORMATTING = True


def build_vector_prefix(name: str, old_formatting=False) -> str:
    if old_formatting:
        prefix = name
    else:
        prefix = name.lower()
        prefix = prefix.replace(".", "_")
    prefix = prefix.replace("/", "#")
    # replace umlauts with their ASCII representation
    prefix = prefix.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return prefix


prefix = f"public#{PARTY_ID}#{build_vector_prefix(ORIGINAL_STORAGE_DOCUMENT_NAME, old_formatting=OLD_FORMATTING)}#"

print(
    f"Deleting splits from index {INDEX_NAME} in namespace {PARTY_ID} with prefix {prefix}"
)

# Perform the deletion
deleted_ids = []
for ids in index.list(prefix=prefix, namespace=PARTY_ID):
    try:
        print(f"Deleting {len(ids)} splits with ids: {ids}")
        index.delete(ids, namespace=PARTY_ID)
    except Exception as e:
        logger.error(f"Error deleting splits: {e}")
    deleted_ids.extend(ids)

print(
    f"Deleted {len(deleted_ids)} splits from index {INDEX_NAME} in namespace {PARTY_ID} with prefix {prefix}"
)
