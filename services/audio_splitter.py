"""
Audio Splitter Module
Handles splitting large audio files into smaller chunks for processing.
"""
import os
import subprocess
import tempfile
import logging
from typing import List, Tuple
from pathlib import Path

from utils.ffmpeg_checker import get_ffmpeg_checker

logger = logging.getLogger(__name__)


class AudioSplitter:
    """Service for splitting large audio files into smaller chunks."""
    
    # Whisper API limit is 25MB per file
    MAX_CHUNK_SIZE = 25 * 1024 * 1024  # 25MB
    CHUNK_DURATION_ESTIMATE = 600  # Estimate 10 minutes per 25MB (rough estimate)
    
    def __init__(self, max_chunk_size: int = None):
        """
        Initialize AudioSplitter.
        
        Args:
            max_chunk_size: Maximum size per chunk in bytes
        """
        self.max_chunk_size = max_chunk_size or self.MAX_CHUNK_SIZE
        self._ffmpeg_checker = get_ffmpeg_checker()
        self._ffmpeg_available = self._ffmpeg_checker.is_available()
    
    def split_audio_file(self, audio_file_path: str, output_dir: str = None) -> List[str]:
        """
        Split large audio file into smaller chunks.
        
        Args:
            audio_file_path: Path to the audio file
            output_dir: Directory to save chunks (optional, uses temp dir if not provided)
            
        Returns:
            List of paths to chunk files
            
        Raises:
            RuntimeError: If splitting fails
        """
        file_size = os.path.getsize(audio_file_path)
        
        # If file is small enough, return original file path
        if file_size <= self.max_chunk_size:
            return [audio_file_path]
        
        # Create output directory
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='audio_chunks_')
        else:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            if self._ffmpeg_available:
                return self._split_with_ffmpeg(audio_file_path, output_dir)
            else:
                # FFmpeg is required for proper audio splitting
                # Binary splitting creates invalid audio files
                raise RuntimeError(
                    "FFmpeg is required to split large audio files.\n\n"
                    + self._ffmpeg_checker.get_installation_instructions() +
                    "\n\nAlternatively, compress or split your audio file manually before uploading."
                )
        except Exception as e:
            raise RuntimeError(f"Failed to split audio file: {str(e)}")
    
    def _split_with_ffmpeg(self, audio_file_path: str, output_dir: str) -> List[str]:
        """
        Split audio file using ffmpeg (best quality).
        
        Args:
            audio_file_path: Path to the audio file
            output_dir: Directory to save chunks
            
        Returns:
            List of chunk file paths
        """
        base_name = Path(audio_file_path).stem
        # Always use .mp3 for chunks to ensure compatibility with Whisper API
        extension = '.mp3'
        
        # Get audio duration using ffprobe
        try:
            probe_cmd = [
                'ffprobe', '-v', 'error', '-show_entries',
                'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_file_path
            ]
            result = subprocess.run(
                probe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            duration = float(result.stdout.strip())
        except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
            # If we can't get duration, estimate from file size
            file_size = os.path.getsize(audio_file_path)
            # Rough estimate: 1MB ≈ 1 minute (depends on bitrate)
            duration = file_size / (1024 * 1024) * 60
        
        # Calculate chunk duration based on file size
        file_size = os.path.getsize(audio_file_path)
        chunks_needed = (file_size // self.max_chunk_size) + 1
        chunk_duration = duration / chunks_needed
        
        chunk_files = []
        start_time = 0
        chunk_index = 0
        
        while start_time < duration:
            chunk_file = os.path.join(
                output_dir,
                f"{base_name}_chunk_{chunk_index:03d}{extension}"
            )
            
            # Calculate end time (ensure we don't exceed duration)
            end_time = min(start_time + chunk_duration, duration)
            
            # Use ffmpeg to extract chunk
            # Re-encode to ensure valid output format that Whisper can handle
            cmd = [
                'ffmpeg', '-i', audio_file_path,
                '-ss', str(start_time),
                '-t', str(end_time - start_time),
                '-acodec', 'libmp3lame',  # Use MP3 codec for compatibility
                '-ab', '128k',  # Set bitrate to keep file size reasonable
                '-ar', '44100',  # Set sample rate
                '-ac', '2',  # Stereo
                '-y',  # Overwrite output file
                chunk_file
            ]
            
            # If original file is already MP3 or MP4, try to use copy first
            original_ext = Path(audio_file_path).suffix.lower()
            if original_ext in ['.mp3', '.mp4', '.m4a']:
                # Try copy codec first (faster and preserves quality)
                cmd_copy = [
                    'ffmpeg', '-i', audio_file_path,
                    '-ss', str(start_time),
                    '-t', str(end_time - start_time),
                    '-acodec', 'copy',
                    '-y',
                    chunk_file
                ]
                try:
                    result = subprocess.run(
                        cmd_copy,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=300,
                        check=True
                    )
                    # If copy worked, check size and continue
                    if os.path.exists(chunk_file):
                        chunk_size = os.path.getsize(chunk_file)
                        if chunk_size > 0 and chunk_size <= self.max_chunk_size * 1.1:
                            chunk_files.append(chunk_file)
                            start_time = end_time
                            chunk_index += 1
                            if chunk_index > 100:
                                break
                            continue
                except subprocess.CalledProcessError:
                    # If copy failed, fall back to re-encoding
                    pass
            
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,  # 5 minute timeout
                    check=True
                )
                
                # Check if chunk file was created and is small enough
                if os.path.exists(chunk_file):
                    chunk_size = os.path.getsize(chunk_file)
                    if chunk_size > 0:
                        # If chunk is still too large, recursively split it
                        if chunk_size > self.max_chunk_size:
                            sub_chunks = self._split_with_ffmpeg(chunk_file, output_dir)
                            chunk_files.extend(sub_chunks)
                            os.remove(chunk_file)  # Remove temporary chunk
                        else:
                            chunk_files.append(chunk_file)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
            
            start_time = end_time
            chunk_index += 1
            
            # Safety check to avoid infinite loop
            if chunk_index > 100:
                break
        
        return chunk_files if chunk_files else [audio_file_path]
    
    def cleanup_chunks(self, chunk_files: List[str]):
        """
        Clean up temporary chunk files.
        
        Args:
            chunk_files: List of chunk file paths to delete
        """
        for chunk_file in chunk_files:
            try:
                if os.path.exists(chunk_file) and '_chunk_' in chunk_file:
                    os.remove(chunk_file)
                    logger.debug(f"Cleaned up chunk file: {chunk_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup chunk file {chunk_file}: {e}")

