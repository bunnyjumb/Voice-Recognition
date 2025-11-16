"""
Text Chunker Module
Handles intelligent splitting of long transcripts into manageable chunks.
"""
from typing import List
from config import MAX_CHARS_PER_CHUNK, CHUNK_OVERLAP


class TextChunker:
    """Utility for splitting long text into chunks while preserving context."""
    
    def __init__(
        self,
        max_chars: int = MAX_CHARS_PER_CHUNK,
        overlap: int = CHUNK_OVERLAP
    ):
        """
        Initialize TextChunker.
        
        Args:
            max_chars: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks
        """
        self.max_chars = max_chars
        self.overlap = overlap
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks intelligently.
        
        Tries to split at sentence boundaries first, then paragraph boundaries,
        and finally at word boundaries to avoid cutting mid-sentence.
        
        Args:
            text: The text to chunk
            
        Returns:
            List of text chunks
        """
        if len(text) <= self.max_chars:
            return [text]
        
        chunks = []
        current_pos = 0
        text_length = len(text)
        
        while current_pos < text_length:
            # Calculate end position for this chunk
            end_pos = min(current_pos + self.max_chars, text_length)
            
            # If this is not the last chunk, try to find a good break point
            if end_pos < text_length:
                # Try to find sentence boundary (., !, ?)
                chunk_text = text[current_pos:end_pos]
                
                # Look for sentence endings in the last 20% of chunk
                search_start = int(len(chunk_text) * 0.8)
                sentence_endings = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
                
                best_break = -1
                for ending in sentence_endings:
                    # Search backwards from end of chunk
                    pos = chunk_text.rfind(ending, search_start)
                    if pos != -1:
                        best_break = pos + len(ending)
                        break
                
                # If no sentence boundary found, try paragraph boundary
                if best_break == -1:
                    para_break = chunk_text.rfind('\n\n', search_start)
                    if para_break != -1:
                        best_break = para_break + 2
                
                # If still no good break, try word boundary (space)
                if best_break == -1:
                    word_break = chunk_text.rfind(' ', search_start)
                    if word_break != -1:
                        best_break = word_break + 1
                
                # Use best break if found, otherwise use max_chars
                if best_break != -1:
                    end_pos = current_pos + best_break
                else:
                    # Force break at max_chars if no good break point
                    end_pos = current_pos + self.max_chars
            
            # Extract chunk
            chunk = text[current_pos:end_pos].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move to next chunk with overlap
            if end_pos >= text_length:
                break
            
            # Start next chunk with overlap
            current_pos = max(current_pos + 1, end_pos - self.overlap)
        
        return chunks
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count (rough approximation: 1 token ≈ 4 characters).
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        return len(text) // 4

