"""
Audio Service Module
Handles audio file operations and management.
"""
import os
import time
from pathlib import Path
from typing import Tuple, Optional
from werkzeug.datastructures import FileStorage

from config import UPLOAD_FOLDER


class AudioService:
    """Service for handling audio file operations."""
    
    def __init__(self, upload_folder: str = UPLOAD_FOLDER):
        """
        Initialize AudioService.
        
        Args:
            upload_folder: Path to the upload directory
        """
        self.upload_folder = upload_folder
        self._ensure_upload_directory()
    
    def _ensure_upload_directory(self):
        """Ensure upload directory exists."""
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
    
    def save_audio_file(self, file: FileStorage) -> Tuple[str, str]:
        """
        Save uploaded audio file with unique filename.
        
        Args:
            file: The uploaded file from Flask request
            
        Returns:
            Tuple of (filepath, filename)
            
        Raises:
            ValueError: If file is empty or invalid
        """
        if not file or file.filename == '':
            raise ValueError("No file provided or filename is empty")
        
        # Generate unique filename with timestamp
        timestamp = int(time.time())
        original_filename = file.filename
        file_extension = os.path.splitext(original_filename)[1] or '.webm'
        filename = f"recording_{timestamp}{file_extension}"
        filepath = os.path.join(self.upload_folder, filename)
        
        # Save file
        file.save(filepath)
        
        if not os.path.exists(filepath):
            raise IOError(f"Failed to save file to {filepath}")
        
        return filepath, filename
    
    def get_file_path(self, filename: str) -> str:
        """
        Get full path to a file in upload directory.
        
        Args:
            filename: Name of the file
            
        Returns:
            Full path to the file
        """
        return os.path.join(self.upload_folder, filename)
    
    def file_exists(self, filename: str) -> bool:
        """
        Check if file exists in upload directory.
        
        Args:
            filename: Name of the file to check
            
        Returns:
            True if file exists, False otherwise
        """
        filepath = self.get_file_path(filename)
        return os.path.exists(filepath) and os.path.isfile(filepath)

