"""
Audio Compressor Module
Handles compressing large audio files to fit within API limits.
"""
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Tuple

from utils.ffmpeg_checker import get_ffmpeg_checker

logger = logging.getLogger(__name__)


class AudioCompressor:
    """Service for compressing large audio files."""
    
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB (Whisper API limit)
    
    # Compression presets
    COMPRESSION_PRESETS = {
        'high': {'bitrate': '64k', 'sample_rate': '22050'},      # Smaller file, lower quality
        'medium': {'bitrate': '128k', 'sample_rate': '44100'},   # Balanced
        'low': {'bitrate': '192k', 'sample_rate': '44100'},      # Larger file, higher quality
    }
    
    def __init__(self):
        """Initialize AudioCompressor."""
        self._ffmpeg_checker = get_ffmpeg_checker()
        self._ffmpeg_available = self._ffmpeg_checker.is_available()
    
    def compress_audio(
        self,
        audio_file_path: str,
        target_size: int = None,
        output_path: Optional[str] = None
    ) -> Tuple[str, bool, Optional[str]]:
        """
        Compress audio file to fit within size limit.
        
        Args:
            audio_file_path: Path to the audio file
            target_size: Target file size in bytes (default: MAX_FILE_SIZE)
            output_path: Path for output file (optional, uses temp file if not provided)
            
        Returns:
            Tuple of (output_file_path, was_compressed, error_message)
            - If file already small enough: (original_path, False, None)
            - If compressed successfully: (compressed_path, True, None)
            - If FFmpeg not available: (original_path, False, error_message)
            - If compression failed: (original_path, False, error_message)
        """
        if target_size is None:
            target_size = self.MAX_FILE_SIZE
        
        file_size = os.path.getsize(audio_file_path)
        
        # If file is already small enough, return original
        if file_size <= target_size:
            return audio_file_path, False, None
        
        # Check if FFmpeg is available
        if not self._ffmpeg_available:
            # Return original file and indicate compression is not available
            # Don't raise error here, let caller handle it
            error_msg = (
                "FFmpeg is required to compress large audio files.\n\n"
                + self._ffmpeg_checker.get_installation_instructions() +
                "\n\nAlternatively, compress your audio file manually before uploading."
            )
            logger.warning("FFmpeg not available, compression skipped")
            return audio_file_path, False, error_msg
        
        # Create output path if not provided
        if output_path is None:
            original_ext = Path(audio_file_path).suffix
            # Use temp file with same extension
            temp_dir = tempfile.gettempdir()
            temp_name = f"compressed_{os.path.basename(audio_file_path)}"
            output_path = os.path.join(temp_dir, temp_name)
        
        logger.info(f"Compressing audio file from {file_size / (1024*1024):.2f}MB...")
        
        # Try compression presets from high to low (more aggressive to less aggressive)
        compressed = False
        for preset_name in ['high', 'medium', 'low']:
            preset = self.COMPRESSION_PRESETS[preset_name]
            logger.info(f"Trying compression preset: {preset_name} (bitrate: {preset['bitrate']})...")
            
            try:
                # Use ffmpeg to compress
                cmd = [
                    'ffmpeg', '-i', audio_file_path,
                    '-acodec', 'libmp3lame',  # MP3 codec
                    '-ab', preset['bitrate'],  # Bitrate
                    '-ar', preset['sample_rate'],  # Sample rate
                    '-ac', '2',  # Stereo
                    '-y',  # Overwrite output
                    output_path
                ]
                
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=600,  # 10 minute timeout
                    check=True
                )
                
                # Check if compression was successful and file size is acceptable
                if os.path.exists(output_path):
                    compressed_size = os.path.getsize(output_path)
                    logger.info(f"Compressed to {compressed_size / (1024*1024):.2f}MB using preset '{preset_name}'")
                    
                    if compressed_size <= target_size:
                        compressed = True
                        break
                    elif compressed_size < file_size:
                        # Smaller than original but still too large
                        # Try next preset
                        logger.info(f"Still too large ({compressed_size / (1024*1024):.2f}MB), trying more aggressive compression...")
                        continue
                    else:
                        # Compression made it larger, use original
                        os.remove(output_path)
                        break
                        
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                logger.warning(f"Compression with preset '{preset_name}' failed: {error_msg}")
                # Try next preset
                continue
            except Exception as e:
                logger.warning(f"Error during compression: {str(e)}")
                continue
        
        if not compressed:
            # If all presets failed or didn't reduce size enough, try adaptive bitrate
            logger.info("Trying adaptive bitrate compression...")
            try:
                # Calculate target bitrate based on file size
                # Rough estimate: bitrate (kbps) ≈ file_size (MB) * 8 / duration (seconds) * 1000
                # For safety, use lower bitrate
                estimated_bitrate = max(32, int((target_size / (1024 * 1024)) * 8 * 0.8))
                estimated_bitrate = min(estimated_bitrate, 192)  # Cap at 192k
                
                cmd = [
                    'ffmpeg', '-i', audio_file_path,
                    '-acodec', 'libmp3lame',
                    '-ab', f'{estimated_bitrate}k',
                    '-ar', '44100',
                    '-ac', '2',
                    '-y',
                    output_path
                ]
                
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=600,
                    check=True
                )
                
                if os.path.exists(output_path):
                    compressed_size = os.path.getsize(output_path)
                    if compressed_size <= target_size * 1.1:  # Allow 10% tolerance
                        compressed = True
                        logger.info(f"Compressed to {compressed_size / (1024*1024):.2f}MB using adaptive bitrate")
            
            except Exception as e:
                logger.warning(f"Adaptive compression failed: {str(e)}")
        
        if not compressed:
            error_msg = (
                f"Could not compress file to target size.\n"
                f"Original size: {file_size / (1024*1024):.2f}MB\n"
                f"Target size: {target_size / (1024*1024):.2f}MB\n\n"
                "Please manually compress your audio file before uploading, or split it into smaller segments."
            )
            return audio_file_path, False, error_msg
        
        return output_path, True, None
    
    def cleanup_temp_file(self, file_path: str):
        """Clean up temporary compressed file."""
        try:
            if os.path.exists(file_path) and 'compressed_' in file_path:
                os.remove(file_path)
                logger.debug(f"Cleaned up temp compressed file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

