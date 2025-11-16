"""
File Cleanup Service
Handles automatic cleanup of old files and temporary files.
Prevents accumulation of unused files in the upload directory.
"""
import os
import time
import logging
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FileCleanupService:
    """
    Service for cleaning up old and temporary files.
    
    Features:
    - Automatic cleanup of old uploaded files
    - Cleanup of temporary files (compressed, chunks)
    - Configurable retention period
    - Safe cleanup with error handling
    """
    
    # Default retention period: 1 day (files older than 1 day will be cleaned up)
    DEFAULT_RETENTION_DAYS = 1
    
    # File patterns to identify temporary files
    TEMP_FILE_PATTERNS = [
        'compressed_',
        '_chunk_',
        'audio_chunks_',
    ]
    
    def __init__(self, upload_folder: str, retention_days: int = None):
        """
        Initialize FileCleanupService.
        
        Args:
            upload_folder: Path to the upload directory
            retention_days: Number of days to keep files (default: 7)
        """
        self.upload_folder = Path(upload_folder)
        self.retention_days = retention_days or self.DEFAULT_RETENTION_DAYS
        logger.info(f"FileCleanupService initialized with retention: {self.retention_days} days")
    
    def cleanup_old_files(self, dry_run: bool = False) -> int:
        """
        Clean up old files in the upload directory.
        
        Args:
            dry_run: If True, only report what would be deleted without actually deleting
            
        Returns:
            Number of files deleted (or would be deleted in dry_run mode)
        """
        if not self.upload_folder.exists():
            logger.warning(f"Upload folder does not exist: {self.upload_folder}")
            return 0
        
        cutoff_time = time.time() - (self.retention_days * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            for file_path in self.upload_folder.iterdir():
                if not file_path.is_file():
                    continue
                
                # Check file age
                file_mtime = file_path.stat().st_mtime
                if file_mtime < cutoff_time:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would delete old file: {file_path.name}")
                    else:
                        try:
                            file_path.unlink()
                            logger.info(f"Deleted old file: {file_path.name}")
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete file {file_path.name}: {e}")
        
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        if not dry_run:
            logger.info(f"Cleanup completed: {deleted_count} files deleted")
        
        return deleted_count
    
    def cleanup_temp_files(self, file_paths: List[str]) -> int:
        """
        Clean up temporary files (compressed, chunks, etc.).
        
        Args:
            file_paths: List of file paths to check and potentially delete
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        
        for file_path in file_paths:
            if not file_path:
                continue
            
            try:
                path = Path(file_path)
                
                # Check if it's a temporary file
                is_temp = any(pattern in path.name for pattern in self.TEMP_FILE_PATTERNS)
                
                if is_temp and path.exists() and path.is_file():
                    path.unlink()
                    logger.debug(f"Deleted temp file: {path.name}")
                    deleted_count += 1
                    
            except Exception as e:
                logger.warning(f"Failed to delete temp file {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} temporary files")
        
        return deleted_count
    
    def cleanup_temp_directories(self, directory_paths: List[str]) -> int:
        """
        Clean up temporary directories (e.g., audio_chunks_*).
        
        Args:
            directory_paths: List of directory paths to check and potentially delete
            
        Returns:
            Number of directories deleted
        """
        deleted_count = 0
        
        for dir_path in directory_paths:
            if not dir_path:
                continue
            
            try:
                path = Path(dir_path)
                
                # Check if it's a temporary directory
                is_temp = any(pattern in path.name for pattern in self.TEMP_FILE_PATTERNS)
                
                if is_temp and path.exists() and path.is_dir():
                    shutil.rmtree(path)
                    logger.debug(f"Deleted temp directory: {path.name}")
                    deleted_count += 1
                    
            except Exception as e:
                logger.warning(f"Failed to delete temp directory {dir_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} temporary directories")
        
        return deleted_count
    
    def cleanup_after_processing(self, processed_file_path: str, temp_files: List[str] = None, temp_dirs: List[str] = None):
        """
        Clean up files after processing is complete.
        
        Args:
            processed_file_path: Path to the processed file (keep this)
            temp_files: List of temporary file paths to delete
            temp_dirs: List of temporary directory paths to delete
        """
        temp_files = temp_files or []
        temp_dirs = temp_dirs or []
        
        # Clean up temp files
        if temp_files:
            self.cleanup_temp_files(temp_files)
        
        # Clean up temp directories
        if temp_dirs:
            self.cleanup_temp_directories(temp_dirs)
        
        logger.debug(f"Cleanup after processing completed for: {processed_file_path}")
    
    def get_old_files(self) -> List[Path]:
        """
        Get list of old files that would be cleaned up.
        
        Returns:
            List of file paths that are older than retention period
        """
        if not self.upload_folder.exists():
            return []
        
        cutoff_time = time.time() - (self.retention_days * 24 * 60 * 60)
        old_files = []
        
        try:
            for file_path in self.upload_folder.iterdir():
                if file_path.is_file():
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < cutoff_time:
                        old_files.append(file_path)
        except Exception as e:
            logger.error(f"Error getting old files: {e}")
        
        return old_files
    
    def get_storage_stats(self) -> dict:
        """
        Get statistics about storage usage.
        
        Returns:
            Dictionary with storage statistics
        """
        if not self.upload_folder.exists():
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'old_files_count': 0,
                'old_files_size_mb': 0
            }
        
        total_files = 0
        total_size = 0
        old_files_count = 0
        old_files_size = 0
        
        cutoff_time = time.time() - (self.retention_days * 24 * 60 * 60)
        
        try:
            for file_path in self.upload_folder.iterdir():
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    file_mtime = file_path.stat().st_mtime
                    
                    total_files += 1
                    total_size += file_size
                    
                    if file_mtime < cutoff_time:
                        old_files_count += 1
                        old_files_size += file_size
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
        
        return {
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'old_files_count': old_files_count,
            'old_files_size_mb': round(old_files_size / (1024 * 1024), 2)
        }

