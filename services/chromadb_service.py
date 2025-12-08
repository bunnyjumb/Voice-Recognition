"""
ChromaDB Service Module
Handles storing and retrieving transcripts using ChromaDB.
"""
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB not installed. Transcripts will not be stored.")


class ChromaDBService:
    """
    Service for managing transcripts in ChromaDB.
    
    This class handles:
    - Storing transcripts with metadata (topic, language, timestamp)
    - Retrieving transcripts by ID
    - Querying transcripts by topic or language
    """
    
    def __init__(self, persist_directory: str = "chroma_db"):
        """
        Initialize ChromaDB service.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB is not available. Install with: pip install chromadb")
            self.client = None
            self.collection = None
            return
        
        try:
            # Create persist directory if it doesn't exist
            os.makedirs(persist_directory, exist_ok=True)
            
            # Initialize ChromaDB client with persistence
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection for transcripts
            self.collection = self.client.get_or_create_collection(
                name="transcripts",
                metadata={"description": "Stored audio transcripts and summaries"}
            )
            
            logger.info(f"ChromaDB initialized successfully. Persist directory: {persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None
    
    def is_available(self) -> bool:
        """
        Check if ChromaDB service is available.
        
        Returns:
            True if ChromaDB is available, False otherwise
        """
        return CHROMADB_AVAILABLE and self.client is not None and self.collection is not None
    
    def store_transcript(
        self,
        transcript: str,
        summary: str,
        topic: Optional[str] = None,
        language: Optional[str] = None,
        custom_language: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store transcript and summary in ChromaDB.
        
        Args:
            transcript: The transcribed text
            summary: The summarized text
            topic: Meeting topic
            language: Language code
            custom_language: Custom language name if language is "other"
            metadata: Additional metadata to store
            
        Returns:
            Document ID (UUID string)
        """
        if not self.is_available():
            logger.warning("ChromaDB not available, skipping transcript storage")
            return ""
        
        try:
            # Generate unique ID
            doc_id = str(uuid.uuid4())
            
            # Prepare document text (combine transcript and summary)
            document_text = f"Transcript:\n{transcript}\n\nSummary:\n{summary}"
            
            # Prepare metadata
            doc_metadata = {
                "topic": topic or "Unknown",
                "language": language or "unknown",
                "custom_language": custom_language or "",
                "timestamp": datetime.now().isoformat(),
                "transcript_length": len(transcript),
                "summary_length": len(summary)
            }
            
            # Add any additional metadata
            if metadata:
                doc_metadata.update(metadata)
            
            # Store in ChromaDB
            self.collection.add(
                ids=[doc_id],
                documents=[document_text],
                metadatas=[doc_metadata]
            )
            
            logger.info(f"Transcript stored in ChromaDB with ID: {doc_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to store transcript in ChromaDB: {e}")
            return ""
    
    def get_transcript(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve transcript by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Dictionary with transcript data or None if not found
        """
        if not self.is_available():
            return None
        
        try:
            results = self.collection.get(ids=[doc_id])
            
            if not results['ids']:
                return None
            
            # Parse document text to extract transcript and summary
            document_text = results['documents'][0]
            metadata = results['metadatas'][0]
            
            # Split transcript and summary
            parts = document_text.split("\n\nSummary:\n")
            transcript = parts[0].replace("Transcript:\n", "").strip()
            summary = parts[1].strip() if len(parts) > 1 else ""
            
            return {
                "id": doc_id,
                "transcript": transcript,
                "summary": summary,
                "metadata": metadata
            }
        except Exception as e:
            logger.error(f"Failed to retrieve transcript from ChromaDB: {e}")
            return None
    
    def query_transcripts(
        self,
        query_text: Optional[str] = None,
        topic: Optional[str] = None,
        language: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query transcripts by text, topic, or language.

        Args:
            query_text: Text to search for
            topic: Filter by topic
            language: Filter by language
            limit: Maximum number of results (None để lấy tất cả)

        Returns:
            List of matching transcripts sorted by relevance (if available)
        """
        if not self.is_available():
            return []

        try:
            results = {}
            if query_text:
                # Nếu limit là None thì lấy tất cả, còn không thì lấy theo limit
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=limit
                )
            else:
                # Build filters
                where = {}
                if topic:
                    where["topic"] = topic
                if language:
                    where["language"] = language

                if where:
                    results = self.collection.get(
                        where=where,
                        limit=limit
                    )
                else:
                    results = self.collection.get(limit=limit)

            formatted_results = []
            # Sắp xếp kết quả nếu có trường 'distances' hoặc 'scores'
            indices = list(range(len(results.get('ids', []))))
            if results.get('distances'):
                indices.sort(key=lambda i: results['distances'][i])
            elif results.get('scores'):
                indices.sort(key=lambda i: -results['scores'][i])

            for i in indices:
                doc_id = results['ids'][i]
                document_text = results['documents'][i]
                metadata = results['metadatas'][i]

                # Normalize shapes
                if isinstance(document_text, list):
                    document_text = document_text[0]
                if isinstance(metadata, list):
                    metadata = metadata[0] if metadata else {}
                if not isinstance(metadata, dict):
                    metadata = {}

                parts = document_text.split("\n\nSummary:\n", 1)
                transcript = parts[0].replace("Transcript:\n", "").strip()
                summary = parts[1].strip() if len(parts) > 1 else ""

                formatted_results.append({
                    "id": doc_id,
                    "transcript": transcript,
                    "summary": summary,
                    "metadata": metadata
                })

            print("-------------TEST------------------------------------------------------------")
            print("formatted_results", len(formatted_results))
            print("-------------TEST---END------------------------------------------------------")

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to query transcripts from ChromaDB: {e}")
            return []

