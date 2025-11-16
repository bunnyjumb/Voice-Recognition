"""
Configuration module for the Meeting Summary Application.
Contains all configuration settings and constants.
"""
import os
from pathlib import Path

# OpenAI API Configuration
OPENAI_BASE_URL = "https://aiportalapi.stu-platform.live/use"
# Try alternative base URLs if the default doesn't work
# Some APIs require /v1 suffix: "https://aiportalapi.stu-platform.live/use/v1"
OPENAI_API_KEY = "sk-6gH161QwRXLB0FmOCwxglA"
OPENAI_MODEL_TRANSCRIPTION = "whisper-1"
OPENAI_MODEL_SUMMARY = "GPT-5-mini"

# File Upload Configuration
UPLOAD_FOLDER = 'uploads'
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Text Chunking Configuration for Long Transcripts
# Maximum characters per chunk (approximately 2000 chars = ~500 tokens)
# This ensures we stay well within model context limits
MAX_CHARS_PER_CHUNK = 2000
CHUNK_OVERLAP = 200  # Overlap between chunks to maintain context

# Language Mapping for Whisper API
LANGUAGE_MAP = {
    'vi': 'vi',  # Vietnamese
    'en': 'en',  # English
    'zh': 'zh',  # Chinese
    'ja': 'ja',  # Japanese
    'ko': 'ko',  # Korean
    'fr': 'fr',  # French
    'de': 'de',  # German
    'es': 'es',  # Spanish
}

# Language Display Names
LANGUAGE_NAMES = {
    'vi': 'Vietnamese',
    'en': 'English',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish',
    'other': 'the language used'
}

# Ensure upload directory exists
def ensure_upload_directory():
    """Create upload directory if it doesn't exist."""
    upload_path = Path(UPLOAD_FOLDER)
    upload_path.mkdir(exist_ok=True)
    return str(upload_path)

