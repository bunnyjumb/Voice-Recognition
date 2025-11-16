"""
FFmpeg Checker Utility
Centralized utility for checking FFmpeg availability.
Follows DRY principle - single source of truth for FFmpeg checks.
"""
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FFmpegChecker:
    """
    Singleton utility for checking FFmpeg availability.
    Caches the result to avoid repeated subprocess calls.
    """
    
    _instance = None
    _ffmpeg_available: Optional[bool] = None
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(FFmpegChecker, cls).__new__(cls)
        return cls._instance
    
    def is_available(self) -> bool:
        """
        Check if FFmpeg is available in the system.
        Caches the result after first check.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        if self._ffmpeg_available is None:
            self._ffmpeg_available = self._check_ffmpeg()
        
        return self._ffmpeg_available
    
    def _check_ffmpeg(self) -> bool:
        """
        Actually check FFmpeg availability by running a command.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            logger.info("FFmpeg is available")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"FFmpeg is not available: {type(e).__name__}")
            return False
    
    def get_installation_instructions(self) -> str:
        """
        Get installation instructions for FFmpeg.
        
        Returns:
            Formatted string with installation instructions
        """
        return (
            "FFmpeg is required for audio processing.\n\n"
            "Please install FFmpeg:\n"
            "- Windows: Download from https://www.gyan.dev/ffmpeg/builds/ or use 'choco install ffmpeg'\n"
            "- Linux: 'sudo apt-get install ffmpeg' (Ubuntu/Debian) or 'sudo yum install ffmpeg' (RHEL/CentOS)\n"
            "- Mac: 'brew install ffmpeg'\n\n"
            "Quick Windows Install:\n"
            "1. Download from: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip\n"
            "2. Extract to a folder (e.g., C:\\ffmpeg)\n"
            "3. Add C:\\ffmpeg\\bin to your PATH environment variable\n"
            "4. Restart your terminal/IDE\n"
            "5. Verify by running: ffmpeg -version\n\n"
            "After installing FFmpeg, restart the application and try again."
        )
    
    def reset_cache(self):
        """Reset the cached FFmpeg availability (useful for testing)."""
        self._ffmpeg_available = None
        logger.info("FFmpeg cache reset")


# Global singleton instance
_ffmpeg_checker = None

def get_ffmpeg_checker() -> FFmpegChecker:
    """Get the global FFmpegChecker instance."""
    global _ffmpeg_checker
    if _ffmpeg_checker is None:
        _ffmpeg_checker = FFmpegChecker()
    return _ffmpeg_checker

