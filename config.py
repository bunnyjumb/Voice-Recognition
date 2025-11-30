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

# EMBEDDING API
EMBEDDING_BASE_URL = "https://aiportalapi.stu-platform.live/jpe"
EMBEDDING_API_KEY = "sk-c6WKFFVK8oH9hYZmm1eMnA"   # thay key vào đây
EMBEDDING_MODEL = "text-embedding-3-small"

# File Upload Configuration
UPLOAD_FOLDER = 'uploads'
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Text Chunking Configuration for Long Transcripts
# Maximum characters per chunk (approximately 2000 chars = ~500 tokens)
# This ensures we stay well within model context limits
MAX_CHARS_PER_CHUNK = 2000
CHUNK_OVERLAP = 200  # Overlap between chunks to maintain context

# ============================================
# RAG / Azure OpenAI + Pinecone Configuration
# ============================================
AZURE_OPENAI_ENDPOINT = "" 
AZURE_OPENAI_API_KEY = "" 
AZURE_EMBEDDING_DEPLOYMENT = "text-embedding-3-small"
AZURE_CHAT_DEPLOYMENT = "gpt-4o-mini"

PINECONE_API_KEY = "pcsk_4yUBYx_PNUPcpWfYEV8pxWokyMzUKgrFS4w4QuBbXY7NjELz6aGWmYRHAhtYQgd7vjig44"
PINECONE_INDEX_NAME = "meeting-summaries-index"
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"

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

# HuggingFace Configuration for TTS
# Get HF_TOKEN from environment variable first, then fallback to direct setting
# IMPORTANT: For production, always use environment variable for security
# To set environment variable:
#   Windows PowerShell: $env:HF_TOKEN="your_token_here"
#   Windows CMD: set HF_TOKEN=your_token_here
#   Linux/Mac: export HF_TOKEN="your_token_here"
HF_TOKEN = os.environ.get("HF_TOKEN", "") or "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"
# TTS Model: Try Kokoro first, fallback to other models if needed
# Note: Some models may require specific providers or may not be available on free tier
HF_TTS_MODEL = "hexgrad/Kokoro-82M"  # Kokoro TTS model
HF_TTS_FALLBACK_MODEL = "microsoft/speecht5_tts"  # Fallback model (free, multilingual)
# HF_TTS_PROVIDER: Set to None to use HuggingFace Inference API directly (free)
# Provider "fal-ai" requires pre-paid credits, so we use direct API instead
HF_TTS_PROVIDER = None  # Use HuggingFace Inference API directly (no provider)

# Ensure upload directory exists
def ensure_upload_directory():
    """Create upload directory if it doesn't exist."""
    upload_path = Path(UPLOAD_FOLDER)
    upload_path.mkdir(exist_ok=True)
    return str(upload_path)

