import logging
from typing import Optional

from pinecone import Pinecone, ServerlessSpec
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,

    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_CLOUD,
    PINECONE_REGION,
)

logger = logging.getLogger(__name__)


class PineconeService:
    def __init__(self):
        self.available = False
        self.vector_store = None

        try:
            # 1. Init Pinecone
            pc = Pinecone(api_key=PINECONE_API_KEY)

            # Create index if not exists
            existing = [i["name"] for i in pc.list_indexes()]
            if PINECONE_INDEX_NAME not in existing:
                logger.info(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")
                pc.create_index(
                    name=PINECONE_INDEX_NAME,
                    dimension=1536,         # dims for text-embedding-3-small
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud=PINECONE_CLOUD,
                        region=PINECONE_REGION,
                    )
                )

            # Connect to the index
            self.index = pc.Index(PINECONE_INDEX_NAME)

            # 2. Embeddings (using EMBEDDING KEY)
            embeddings = OpenAIEmbeddings(
                model=EMBEDDING_MODEL,
                openai_api_key=EMBEDDING_API_KEY,
                openai_api_base=EMBEDDING_BASE_URL,
            )

            # 3. Vector Store
            self.vector_store = PineconeVectorStore(
                index_name=PINECONE_INDEX_NAME,
                embedding=embeddings,
                pinecone_api_key=PINECONE_API_KEY,   # REQUIRED
            )

            self.available = True
            logger.info("PineconeService READY (with dedicated embedding key)")

        except Exception as e:
            logger.error(f"PineconeService init failed: {e}")
            self.available = False

    def is_available(self) -> bool:
        return self.available

    def upsert(self, doc_id, transcript, summary, metadata=None):
        if not self.available:
            return False

        text = f"Transcript:\n{transcript}\n\nSummary:\n{summary}"

        meta = metadata or {}
        meta.setdefault("type", "meeting_summary")

        try:
            self.vector_store.add_texts(
                texts=[text],
                metadatas=[meta],
                ids=[doc_id],
            )
            return True

        except Exception as e:
            logger.error(f"Pinecone upsert failed: {e}")
            return False

    def search(self, query, top_k=3):
        if not self.available:
            return []

        try:
            retriever = self.vector_store.as_retriever(search_kwargs={"k": top_k})
            results = retriever.invoke(query)
            return results

        except Exception as e:
            logger.error(f"Pinecone search failed: {e}")
            return []

    def delete(self, doc_id: str):
        if not self.available:
            return False

        try:
            self.vector_store.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error(f"Pinecone delete failed: {e}")
            return False

