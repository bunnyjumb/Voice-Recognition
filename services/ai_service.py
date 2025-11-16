"""
AI Service Module
Handles AI operations including transcription and summarization.

This module provides:
- Audio transcription using OpenAI Whisper API or local Whisper model
- Text summarization using OpenAI GPT models
- Support for multiple languages with optimized settings
- Automatic fallback mechanisms for reliability
- Integration with OpenAI SDK features (function calling, batching, message management)

Features:
- Automatic API fallback to local Whisper when API is unavailable
- Vietnamese-specific optimizations (larger model, post-processing)
- Large file handling (compression and chunking)
- Multi-turn dialogue support with context management
"""
import os
import openai
from typing import Optional, Dict, Any, List
from config import (
    OPENAI_BASE_URL,
    OPENAI_API_KEY,
    OPENAI_MODEL_TRANSCRIPTION,
    OPENAI_MODEL_SUMMARY,
    LANGUAGE_MAP,
    MAX_CHARS_PER_CHUNK
)


class AIService:
    """
    Service for handling AI operations.
    
    This class manages:
    - OpenAI API client initialization and management
    - Audio transcription (API and local Whisper fallback)
    - Text summarization with chunking support
    - Language-specific optimizations
    - Error handling and fallback mechanisms
    
    Attributes:
        client: OpenAI client instance (initialized on __init__)
        max_chunk_size: Maximum file size for transcription chunks (25MB)
    """
    
    # Maximum chunk size for transcription (25MB - API limit, but local Whisper can handle larger)
    # This is used when splitting large audio files for processing
    max_chunk_size = 25 * 1024 * 1024  # 25MB
    
    def __init__(self):
        """
        Initialize AI service with OpenAI client.
        
        The client is initialized with configuration from config.py.
        If initialization fails, the service will still be available but
        will use local Whisper for transcription instead of API.
        
        Also preloads common Whisper models in background for better performance.
        """
        self.client = self._initialize_client()
        
        # Preload common Whisper models in background
        # This improves user experience by having models ready when needed
        try:
            from services.whisper_model_cache import get_model_cache
            cache = get_model_cache()
            cache.preload_common_models()
            print("[AISERVICE] Started preloading common Whisper models in background...")
        except Exception as e:
            print(f"[AISERVICE] Warning: Could not preload models: {e}")
            # Continue without preloading - models will be loaded on demand
    
    def _initialize_client(self) -> Optional[openai.OpenAI]:
        """
        Initialize OpenAI client with configured base URL and API key.
        
        This method creates an OpenAI client instance using the base URL
        and API key from configuration. The client is used for both
        transcription (Whisper API) and summarization (GPT models).
        
        Returns:
            OpenAI client instance if successful, None if initialization fails
            
        Note:
            If initialization fails, the service will fall back to local
            Whisper for transcription, but summarization will not be available.
        """
        try:
            # Create OpenAI client with custom base URL and API key
            # This allows using alternative API providers that are compatible
            # with OpenAI's API format
            client = openai.OpenAI(
                base_url=OPENAI_BASE_URL,
                api_key=OPENAI_API_KEY
            )
            print(f"OpenAI client initialized successfully with base URL: {OPENAI_BASE_URL}")
            return client
        except Exception as e:
            # Log error but don't raise - allow fallback to local Whisper
            print(f"Error initializing OpenAI client: {e}")
            return None
    
    def is_available(self) -> bool:
        """
        Check if AI service is available.
        
        Returns:
            True if client is initialized, False otherwise
        """
        return self.client is not None
    
    def transcribe_audio(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> str:
        """
        Transcribe audio file to text using Whisper.
        Automatically splits large files into chunks if needed.
        
        Args:
            audio_file_path: Path to the audio file
            language: Language code for transcription (optional)
            
        Returns:
            Transcribed text
            
        Raises:
            RuntimeError: If client is not available or transcription fails
        """
        if not self.is_available():
            raise RuntimeError("OpenAI client is not initialized")
        
        import os
        file_size = os.path.getsize(audio_file_path)
        max_size = 25 * 1024 * 1024  # 25MB
        
        # If file is small enough, transcribe directly
        if file_size <= max_size:
            return self._transcribe_single_file(audio_file_path, language)
        
        # File is too large, try to compress first
        print(f"File is large ({file_size / (1024*1024):.2f}MB). Attempting compression...")
        
        compressed_file = None
        compression_error = None
        
        try:
            from services.audio_compressor import AudioCompressor
            compressor = AudioCompressor()
            compressed_file, was_compressed, error_msg = compressor.compress_audio(audio_file_path)
            
            if error_msg:
                compression_error = error_msg
                print("Compression not available:", error_msg.split('\n')[0])
            
            if was_compressed:
                compressed_size = os.path.getsize(compressed_file)
                print(f"Successfully compressed to {compressed_size / (1024*1024):.2f}MB")
                
                # If compressed file is still too large, split it
                if compressed_size > max_size:
                    print("Compressed file still too large, splitting into chunks...")
                    audio_file_path = compressed_file  # Use compressed file for splitting
                else:
                    # Compressed file is small enough, use it directly
                    try:
                        result = self._transcribe_single_file(compressed_file, language)
                        # Clean up compressed file
                        compressor.cleanup_temp_file(compressed_file)
                        return result
                    except Exception as e:
                        # If transcription fails, try splitting
                        print(f"Transcription of compressed file failed: {str(e)}")
                        print("Falling back to splitting...")
            else:
                # Compression not needed or failed
                if compressed_file != audio_file_path:
                    # Clean up if it's a temp file
                    compressor.cleanup_temp_file(compressed_file)
                compressed_file = None
        except Exception as e:
            print(f"Compression error: {str(e)}")
            compression_error = str(e)
            compressed_file = None
        
        # Check if FFmpeg is available before attempting to split
        if not self._check_ffmpeg_available():
            # Build comprehensive error message
            error_details = [
                "Audio file is too large and FFmpeg is not installed.\n",
                f"File size: {file_size / (1024*1024):.2f}MB",
                f"Maximum size: 25MB\n",
                "To process large files, FFmpeg is required for both compression and splitting.\n",
                "Please install FFmpeg:",
                "- Windows: Download from https://ffmpeg.org/download.html or use 'choco install ffmpeg'",
                "- Linux: 'sudo apt-get install ffmpeg' (Ubuntu/Debian)",
                "- Mac: 'brew install ffmpeg'\n",
                "Quick Windows Install:",
                "1. Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/",
                "2. Extract to a folder (e.g., C:\\ffmpeg)",
                "3. Add C:\\ffmpeg\\bin to your PATH environment variable",
                "4. Restart your terminal/IDE\n",
                "After installing FFmpeg, restart the application and try again.\n",
                "Alternatively, compress your audio file manually before uploading:",
                "- Use online tools: CloudConvert, FreeConvert, etc.",
                "- Use audio editors: Audacity (free), VLC Media Player, etc.",
                "- Target: < 25MB file size"
            ]
            
            raise RuntimeError("\n".join(error_details))
        
        # File is too large, split it
        print(f"Splitting file into chunks...")
        from services.audio_splitter import AudioSplitter
        
        splitter = AudioSplitter()
        chunk_files = splitter.split_audio_file(audio_file_path if compressed_file is None else compressed_file)
        
        print(f"Split into {len(chunk_files)} chunks")
        
        # Transcribe each chunk with better error handling
        transcripts = []
        successful_chunks = 0
        failed_chunks = 0
        
        for i, chunk_file in enumerate(chunk_files, 1):
            print(f"Transcribing chunk {i}/{len(chunk_files)}...")
            
            # Validate chunk file before transcribing
            if not os.path.exists(chunk_file):
                print(f"Warning: Chunk {i} file does not exist, skipping...")
                failed_chunks += 1
                continue
            
            chunk_size = os.path.getsize(chunk_file)
            if chunk_size == 0:
                print(f"Warning: Chunk {i} is empty, skipping...")
                failed_chunks += 1
                continue
            
            if chunk_size > self.max_chunk_size * 1.1:  # Allow 10% tolerance
                print(f"Warning: Chunk {i} is too large ({chunk_size / (1024*1024):.2f}MB), skipping...")
                failed_chunks += 1
                continue
            
            try:
                chunk_transcript = self._transcribe_single_file(chunk_file, language)
                if chunk_transcript and chunk_transcript.strip():
                    transcripts.append(chunk_transcript)
                    successful_chunks += 1
                    print(f"✓ Successfully transcribed chunk {i}")
                else:
                    print(f"Warning: Chunk {i} returned empty transcript")
                    failed_chunks += 1
            except Exception as e:
                error_msg = str(e)
                # Check for specific error types
                if '404' in error_msg or 'Not Found' in error_msg:
                    print(f"Warning: Chunk {i} may be invalid or corrupt (404 error). This can happen if FFmpeg is not available. Skipping...")
                elif 'format' in error_msg.lower():
                    print(f"Warning: Chunk {i} format issue: {error_msg}")
                else:
                    print(f"Warning: Failed to transcribe chunk {i}: {error_msg}")
                failed_chunks += 1
            finally:
                # Clean up chunk file if it's a temporary split
                if chunk_file != audio_file_path and '_chunk_' in chunk_file:
                    try:
                        os.remove(chunk_file)
                    except Exception:
                        pass
        
        # Check if we got any successful transcriptions
        if not transcripts:
            error_details = []
            if failed_chunks == len(chunk_files):
                error_details.append("All chunks failed to transcribe.")
            if not self._check_ffmpeg_available():
                error_details.append("FFmpeg may not be installed. Audio splitting requires FFmpeg to create valid chunks.")
            error_details.append("Please ensure:")
            error_details.append("1. Your audio file is not corrupted")
            error_details.append("2. Audio format is supported (mp3, mp4, mpeg, mpga, m4a, wav, webm)")
            error_details.append("3. FFmpeg is installed if file needs splitting")
            
            raise RuntimeError(
                f"Failed to transcribe any chunks of the audio file.\n\n"
                f"Chunks processed: {len(chunk_files)}\n"
                f"Successful: {successful_chunks}\n"
                f"Failed: {failed_chunks}\n\n"
                + "\n".join(error_details)
            )
        
        # Combine all transcripts
        combined_transcript = " ".join(transcripts)
        print(f"Successfully transcribed {successful_chunks}/{len(chunk_files)} chunks")
        
        if failed_chunks > 0:
            print(f"Warning: {failed_chunks} chunks failed, but continuing with {successful_chunks} successful transcriptions")
        
        # Clean up compressed file if used
        if compressed_file and compressed_file != audio_file_path:
            try:
                from services.audio_compressor import AudioCompressor
                compressor = AudioCompressor()
                compressor.cleanup_temp_file(compressed_file)
            except Exception:
                pass
        
        return combined_transcript
    
    def _check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            from services.audio_splitter import AudioSplitter
            splitter = AudioSplitter()
            return splitter._ffmpeg_available
        except Exception:
            return False
    
    def _transcribe_single_file(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> str:
        """
        Transcribe a single audio file (must be <= 25MB).
        Tries API first, falls back to local Whisper if API fails.
        
        Args:
            audio_file_path: Path to the audio file
            language: Language code for transcription (optional)
            
        Returns:
            Transcribed text
        """
        # Validate file exists and has content
        if not os.path.exists(audio_file_path):
            raise RuntimeError(f"Audio file does not exist: {audio_file_path}")
        
        file_size = os.path.getsize(audio_file_path)
        if file_size == 0:
            raise RuntimeError("Audio file is empty or corrupted")
        
        # Check file format
        file_ext = os.path.splitext(audio_file_path)[1].lower()
        supported_formats = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
        if file_ext not in supported_formats:
            raise RuntimeError(
                f"Unsupported audio format: {file_ext}. "
                f"Supported formats: {', '.join(supported_formats)}"
            )
        
        print(f"Transcribing file: {audio_file_path} ({file_size / (1024*1024):.2f}MB, format: {file_ext})")
        
        # Try API first
        api_failed = False
        api_error = None
        
        if self.is_available():
            try:
                # Read file and prepare for upload
                with open(audio_file_path, "rb") as audio_file:
                    # Ensure file pointer is at beginning
                    audio_file.seek(0)
                    
                    # Build transcription parameters - use file object directly
                    transcription_params = {
                        "model": OPENAI_MODEL_TRANSCRIPTION,
                        "file": audio_file
                    }
                    
                    # Add language if specified and supported
                    if language and language in LANGUAGE_MAP:
                        transcription_params["language"] = LANGUAGE_MAP[language]
                    
                    print(f"Attempting API transcription with model: {OPENAI_MODEL_TRANSCRIPTION}")
                    if language and language in LANGUAGE_MAP:
                        print(f"Language specified: {LANGUAGE_MAP[language]}")
                    print(f"Base URL: {OPENAI_BASE_URL}")
                    
                    try:
                        # Standard OpenAI API call
                        print("[API] Calling OpenAI Whisper API...")
                        import time
                        api_start = time.time()
                        transcript_response = self.client.audio.transcriptions.create(
                            **transcription_params
                        )
                        api_duration = time.time() - api_start
                        
                        if hasattr(transcript_response, 'text') and transcript_response.text:
                            print(f"[API] ✓ API transcription successful in {api_duration:.2f} seconds")
                            return transcript_response.text
                        else:
                            raise RuntimeError("API returned empty transcript")
                            
                    except (openai.NotFoundError, openai.APIError) as e:
                        error_code = getattr(e, 'status_code', None)
                        if error_code == 404:
                            api_failed = True
                            api_error = "API endpoint not found (404)"
                            print(f"⚠ API transcription failed: {api_error}")
                            print("Falling back to local Whisper transcription...")
                        else:
                            # For other API errors, try alternative URL first
                            try:
                                if not OPENAI_BASE_URL.endswith('/v1'):
                                    alt_base_url = f"{OPENAI_BASE_URL.rstrip('/')}/v1"
                                    print(f"Trying alternative base URL: {alt_base_url}")
                                    alt_client = openai.OpenAI(
                                        base_url=alt_base_url,
                                        api_key=OPENAI_API_KEY
                                    )
                                    audio_file.seek(0)
                                    alt_params = {
                                        "model": OPENAI_MODEL_TRANSCRIPTION,
                                        "file": audio_file
                                    }
                                    if language and language in LANGUAGE_MAP:
                                        alt_params["language"] = LANGUAGE_MAP[language]
                                    transcript_response = alt_client.audio.transcriptions.create(**alt_params)
                                    if hasattr(transcript_response, 'text') and transcript_response.text:
                                        print("✓ Alternative API URL successful")
                                        return transcript_response.text
                            except Exception:
                                pass
                            
                            # If alternative URL also failed, fall back to local
                            api_failed = True
                            api_error = f"API error (Status: {error_code}): {str(e)}"
                            print(f"⚠ API transcription failed: {api_error}")
                            print("Falling back to local Whisper transcription...")
                            
                    except Exception as e:
                        error_msg = str(e)
                        if '404' in error_msg or 'not found' in error_msg.lower():
                            api_failed = True
                            api_error = "API endpoint not found"
                            print(f"⚠ API transcription failed: {api_error}")
                            print("Falling back to local Whisper transcription...")
                        else:
                            # For other errors, still try local as fallback
                            api_failed = True
                            api_error = f"API error: {error_msg}"
                            print(f"⚠ API transcription failed: {api_error}")
                            print("Falling back to local Whisper transcription...")
            except Exception as e:
                api_failed = True
                api_error = str(e)
                print(f"⚠ API transcription failed: {api_error}")
                print("Falling back to local Whisper transcription...")
        
        # If API failed or not available, use local Whisper
        if api_failed or not self.is_available():
            return self._transcribe_with_local_whisper(audio_file_path, language)
        
        # Should not reach here, but just in case
        raise RuntimeError("Transcription failed: Unknown error")
    
    def _transcribe_with_local_whisper(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> str:
        """
        Transcribe audio using local Whisper model.
        
        Args:
            audio_file_path: Path to the audio file
            language: Language code for transcription (optional)
            
        Returns:
            Transcribed text
            
        Raises:
            RuntimeError: If Whisper is not installed or transcription fails
        """
        try:
            import whisper
        except ImportError:
            raise RuntimeError(
                "Local Whisper transcription requires the 'whisper' package.\n\n"
                "Please install it by running:\n"
                "  pip install openai-whisper\n\n"
                "Note: This will download the Whisper model on first use (~1.5GB).\n"
                "The transcription will run locally on your machine."
            )
        
        # Normalize file path for Windows compatibility
        audio_file_path = os.path.abspath(os.path.normpath(audio_file_path))
        
        # Verify file exists before proceeding
        if not os.path.exists(audio_file_path):
            raise RuntimeError(
                f"Audio file not found: {audio_file_path}\n\n"
                "Please ensure the file was saved correctly."
            )
        
        if not os.path.isfile(audio_file_path):
            raise RuntimeError(
                f"Path is not a file: {audio_file_path}"
            )
        
        file_size = os.path.getsize(audio_file_path)
        if file_size == 0:
            raise RuntimeError(
                f"Audio file is empty: {audio_file_path}"
            )
        
        # Check if FFmpeg is available (Whisper requires it)
        ffmpeg_available = self._check_ffmpeg_available()
        if not ffmpeg_available:
            raise RuntimeError(
                "FFmpeg is not installed. Whisper requires FFmpeg to process audio files.\n\n"
                "Please install FFmpeg:\n"
                "1. Download from: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip\n"
                "2. Extract to a folder (e.g., C:\\ffmpeg)\n"
                "3. Add C:\\ffmpeg\\bin to your PATH environment variable:\n"
                "   - Press Win + X, select 'System'\n"
                "   - Click 'Advanced system settings'\n"
                "   - Click 'Environment Variables'\n"
                "   - Under 'System variables', find 'Path' and click 'Edit'\n"
                "   - Click 'New' and add: C:\\ffmpeg\\bin\n"
                "   - Click 'OK' on all dialogs\n"
                "4. Restart your terminal/IDE\n"
                "5. Verify by running: ffmpeg -version\n\n"
                "After installing FFmpeg, restart the application and try again."
            )
        
        print("=" * 60)
        print("[LOCAL WHISPER] Starting local Whisper transcription...")
        print(f"[LOCAL WHISPER] Audio file: {audio_file_path}")
        print(f"[LOCAL WHISPER] File size: {file_size / (1024*1024):.2f}MB")
        print("[LOCAL WHISPER] Note: First-time use will download the model (~1.5GB)")
        print("=" * 60)
        
        try:
            # Load Whisper model - use larger model for Vietnamese for better accuracy
            # Options: tiny, base, small, medium, large
            # For Vietnamese, use 'medium' or 'large' for better accuracy
            # 'medium' is a good balance between accuracy and speed
            if language == 'vi':
                model_name = "medium"  # Better accuracy for Vietnamese
                print("[LOCAL WHISPER] Using 'medium' model for Vietnamese (better accuracy)")
            else:
                model_name = "base"  # Good balance for other languages
            print(f"[LOCAL WHISPER] Loading Whisper model: {model_name}...")
            print("[LOCAL WHISPER] This may take a while on first use (downloading model)...")
            
            # Use cached model instead of loading every time
            from services.whisper_model_cache import get_model_cache
            cache = get_model_cache()
            
            import time
            model_load_start = time.time()
            try:
                # Get model from cache (will load if not cached)
                model = cache.get_model(model_name)
                model_load_duration = time.time() - model_load_start
                
                if model_load_duration < 0.1:
                    print(f"[LOCAL WHISPER] ✓ Model '{model_name}' loaded from cache (instant)")
                else:
                    print(f"[LOCAL WHISPER] ✓ Model '{model_name}' loaded in {model_load_duration:.2f} seconds")
            except Exception as model_error:
                error_msg = str(model_error)
                if "WinError 2" in error_msg or "cannot find the file" in error_msg.lower():
                    # This might be FFmpeg issue - Whisper needs FFmpeg for some formats
                    raise RuntimeError(
                        f"Whisper model loading failed: {error_msg}\n\n"
                        "This error often occurs when FFmpeg is not installed.\n"
                        "Whisper requires FFmpeg to process audio files.\n\n"
                        "Please install FFmpeg:\n"
                        "- Windows: Download from https://ffmpeg.org/download.html\n"
                        "- Or use: choco install ffmpeg (if you have Chocolatey)\n"
                        "- Or download from: https://www.gyan.dev/ffmpeg/builds/\n"
                        "- Extract and add to PATH environment variable\n\n"
                        "After installing FFmpeg, restart the application."
                    )
                else:
                    raise
            
            # Prepare language parameter
            whisper_language = None
            if language and language in LANGUAGE_MAP:
                whisper_language = LANGUAGE_MAP[language]
            
            print(f"[LOCAL WHISPER] Starting transcription...")
            if whisper_language:
                print(f"[LOCAL WHISPER] Language: {whisper_language}")
            
            # Estimate processing time (rough estimate: ~1-2 minutes per MB for medium model on CPU)
            estimated_time_min = (file_size / (1024 * 1024)) * 1.5  # ~1.5 min per MB
            print(f"[LOCAL WHISPER] Estimated processing time: ~{estimated_time_min:.1f} minutes")
            print("[LOCAL WHISPER] This is CPU-intensive and may take a while...")
            print("[LOCAL WHISPER] Please be patient - transcription is in progress...")
            
            # Transcribe - use absolute path to avoid path issues
            import time
            transcribe_start = time.time()
            last_log_time = transcribe_start
            
            # Start transcription in a way that allows periodic logging
            try:
                # Note: Whisper transcribe is blocking, so we can't get real-time progress
                # But we can log periodically using a separate thread or just log start/end
                print("[LOCAL WHISPER] Transcription started - processing audio...")
                
                result = model.transcribe(
                    audio_file_path,
                    language=whisper_language,
                    task="transcribe",
                    verbose=False  # Reduce noise
                )
                
                transcribe_duration = time.time() - transcribe_start
                minutes = int(transcribe_duration // 60)
                seconds = int(transcribe_duration % 60)
                print(f"[LOCAL WHISPER] ✓ Transcription completed in {minutes}m {seconds}s ({transcribe_duration:.2f} seconds)")
            except FileNotFoundError as fnf_error:
                error_msg = str(fnf_error)
                if "ffmpeg" in error_msg.lower() or "ffprobe" in error_msg.lower():
                    raise RuntimeError(
                        f"FFmpeg not found: {error_msg}\n\n"
                        "Whisper requires FFmpeg to process audio files.\n\n"
                        "Please install FFmpeg:\n"
                        "- Windows: Download from https://www.gyan.dev/ffmpeg/builds/\n"
                        "- Extract to a folder (e.g., C:\\ffmpeg)\n"
                        "- Add C:\\ffmpeg\\bin to your PATH environment variable\n"
                        "- Restart your terminal/IDE and try again\n\n"
                        "Quick install guide:\n"
                        "1. Download: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip\n"
                        "2. Extract to C:\\ffmpeg\n"
                        "3. Add C:\\ffmpeg\\bin to PATH\n"
                        "4. Restart application"
                    )
                else:
                    raise RuntimeError(
                        f"File not found error: {error_msg}\n\n"
                        f"Audio file path: {audio_file_path}\n"
                        "Please verify the file exists and is accessible."
                    )
            
            transcript = result.get("text", "").strip()
            
            if not transcript:
                raise RuntimeError(
                    "Local Whisper transcription returned empty result. "
                    "Please ensure your audio file contains clear speech."
                )
            
            # Post-process transcript for Vietnamese to improve accuracy
            if language == 'vi':
                print("[LOCAL WHISPER] Applying Vietnamese post-processing...")
                try:
                    from utils.vietnamese_postprocessor import VietnamesePostProcessor
                    post_processor = VietnamesePostProcessor()
                    transcript = post_processor.post_process(transcript)
                    print("[LOCAL WHISPER] ✓ Applied Vietnamese post-processing")
                except Exception as e:
                    print(f"[LOCAL WHISPER] Warning: Vietnamese post-processing failed: {e}")
                    # Continue with original transcript if post-processing fails
            
            print("=" * 60)
            print("[LOCAL WHISPER] ✓ Transcription successful")
            print(f"[LOCAL WHISPER] Transcript length: {len(transcript)} characters")
            print("=" * 60)
            return transcript
            
        except RuntimeError:
            # Re-raise RuntimeError as-is (already has good error message)
            raise
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            if "WinError 2" in error_msg or "cannot find the file" in error_msg.lower():
                # Check if it's FFmpeg related
                if "ffmpeg" in error_msg.lower() or "ffprobe" in error_msg.lower():
                    raise RuntimeError(
                        f"FFmpeg not found: {error_msg}\n\n"
                        "Whisper requires FFmpeg to process audio files.\n\n"
                        "Please install FFmpeg:\n"
                        "- Windows: Download from https://www.gyan.dev/ffmpeg/builds/\n"
                        "- Extract to a folder (e.g., C:\\ffmpeg)\n"
                        "- Add C:\\ffmpeg\\bin to your PATH environment variable\n"
                        "- Restart your terminal/IDE and try again"
                    )
                else:
                    raise RuntimeError(
                        f"File not found error: {error_msg}\n\n"
                        f"Audio file path: {audio_file_path}\n"
                        f"File exists: {os.path.exists(audio_file_path)}\n"
                        "Please verify the file path is correct."
                    )
            elif "CUDA" in error_msg or "cuda" in error_msg:
                raise RuntimeError(
                    f"Local Whisper error: {error_msg}\n\n"
                    "If you have a GPU, make sure CUDA is properly installed.\n"
                    "Otherwise, Whisper will use CPU (slower but works)."
                )
            else:
                raise RuntimeError(
                    f"Local Whisper transcription failed ({error_type}): {error_msg}\n\n"
                    f"Audio file: {audio_file_path}\n"
                    f"File exists: {os.path.exists(audio_file_path)}\n"
                    f"File size: {file_size / (1024*1024):.2f}MB\n\n"
                    "Please ensure:\n"
                    "1. The audio file is not corrupted\n"
                    "2. The file format is supported\n"
                    "3. You have sufficient disk space for the model (~1.5GB)\n"
                    "4. FFmpeg is installed (required by Whisper)"
                )
    
    def summarize_transcript(
        self,
        transcript: str,
        topic: Optional[str] = None,
        language: str = 'en',
        custom_language: Optional[str] = None
    ) -> str:
        """
        Summarize transcript using GPT model.
        Handles long transcripts by chunking and summarizing in stages.
        
        Args:
            transcript: The transcribed text
            topic: Optional topic/context for the conversation
            language: Language code for summary output
            custom_language: Custom language name if language is "other"
            
        Returns:
            Summarized text
            
        Raises:
            RuntimeError: If client is not available or summarization fails
        """
        if not self.is_available():
            raise RuntimeError("OpenAI client is not initialized")
        
        print("[SUMMARIZATION] Starting summarization process...")
        print(f"[SUMMARIZATION] Transcript length: {len(transcript)} characters")
        print(f"[SUMMARIZATION] Topic: {topic}")
        print(f"[SUMMARIZATION] Language: {language}")
        
        # Check if transcript is too long and needs chunking
        if len(transcript) <= MAX_CHARS_PER_CHUNK:
            # Short transcript - summarize directly
            print("[SUMMARIZATION] Transcript is short, summarizing directly...")
            return self._summarize_single_chunk(
                transcript=transcript,
                topic=topic,
                language=language,
                custom_language=custom_language
            )
        else:
            # Long transcript - use chunked summarization
            print(f"[SUMMARIZATION] Transcript is long ({len(transcript)} chars). Using chunked summarization...")
            return self._summarize_chunked(
                transcript=transcript,
                topic=topic,
                language=language,
                custom_language=custom_language
            )
    
    def _summarize_single_chunk(
        self,
        transcript: str,
        topic: Optional[str] = None,
        language: str = 'en',
        custom_language: Optional[str] = None
    ) -> str:
        """
        Summarize a single chunk of transcript.
        
        Args:
            transcript: The transcript chunk to summarize
            topic: Optional topic/context
            language: Language code
            custom_language: Custom language name
            
        Returns:
            Summary text
        """
        print("[SUMMARIZATION] Building prompts...")
        from utils.prompt_builder import PromptBuilder
        
        prompt_builder = PromptBuilder()
        system_message, user_prompt = prompt_builder.build_summary_prompt(
            transcript=transcript,
            topic=topic,
            language=language,
            custom_language=custom_language
        )
        print("[SUMMARIZATION] ✓ Prompts built")
        
        try:
            print(f"[SUMMARIZATION] Calling OpenAI API with model: {OPENAI_MODEL_SUMMARY}...")
            import time
            api_start = time.time()
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL_SUMMARY,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ]
            )
            api_duration = time.time() - api_start
            print(f"[SUMMARIZATION] ✓ API call completed in {api_duration:.2f} seconds")
            return response.choices[0].message.content
        except Exception as e:
            print(f"[SUMMARIZATION] ✗ API call failed: {str(e)}")
            raise RuntimeError(f"Summarization failed: {str(e)}")
    
    def _summarize_chunked(
        self,
        transcript: str,
        topic: Optional[str] = None,
        language: str = 'en',
        custom_language: Optional[str] = None
    ) -> str:
        """
        Summarize long transcript by chunking.
        
        Process:
        1. Split transcript into chunks
        2. Summarize each chunk
        3. Combine chunk summaries into final summary
        
        Args:
            transcript: The full transcript
            topic: Optional topic/context
            language: Language code
            custom_language: Custom language name
            
        Returns:
            Final summary text
        """
        from utils.text_chunker import TextChunker
        from utils.prompt_builder import PromptBuilder
        
        # Split transcript into chunks
        print("[SUMMARIZATION] Splitting transcript into chunks...")
        chunker = TextChunker()
        chunks = chunker.chunk_text(transcript)
        print(f"[SUMMARIZATION] ✓ Split transcript into {len(chunks)} chunks")
        
        # Summarize each chunk
        chunk_summaries: List[str] = []
        import time
        for i, chunk in enumerate(chunks, 1):
            print(f"[SUMMARIZATION] Processing chunk {i}/{len(chunks)}...")
            chunk_start = time.time()
            chunk_summary = self._summarize_single_chunk(
                transcript=chunk,
                topic=topic,  # Include topic for context
                language=language,
                custom_language=custom_language
            )
            chunk_duration = time.time() - chunk_start
            print(f"[SUMMARIZATION] ✓ Chunk {i}/{len(chunks)} completed in {chunk_duration:.2f} seconds")
            chunk_summaries.append(chunk_summary)
        
        # If we only have one chunk summary, return it
        if len(chunk_summaries) == 1:
            return chunk_summaries[0]
        
        # Combine chunk summaries into final summary
        print(f"[SUMMARIZATION] Combining {len(chunk_summaries)} chunk summaries into final summary...")
        combined_summaries = "\n\n---\n\n".join([
            f"Section {i+1} Summary:\n{summary}"
            for i, summary in enumerate(chunk_summaries)
        ])
        print(f"[SUMMARIZATION] ✓ Combined summaries length: {len(combined_summaries)} characters")
        
        # Create prompt for final summary
        print("[SUMMARIZATION] Building final summary prompt...")
        prompt_builder = PromptBuilder()
        # Get language name (using the same logic as PromptBuilder)
        if language == 'other' and custom_language:
            language_name = custom_language
        else:
            from config import LANGUAGE_NAMES
            language_name = LANGUAGE_NAMES.get(language, 'the language used')
        
        system_message = (
            f"You are a professional meeting assistant. Combine multiple section summaries "
            f"into one cohesive, comprehensive summary. Your final summary must:\n"
            f"- Be written in {language_name}\n"
            f"- Preserve all technical terms, proper nouns, and domain-specific terminology\n"
            f"- Integrate information from all sections smoothly\n"
            f"- Focus on key decisions, action items, and important points across all sections\n"
            f"- Maintain clear structure and avoid redundancy"
        )
        
        user_prompt = f"""Please combine the following section summaries into one comprehensive meeting summary.

MEETING TOPIC/CONTEXT: {topic if topic else "General Meeting"}

CRITICAL INSTRUCTIONS:
- Write the final summary in {language_name}
- Preserve ALL technical terms, proper nouns, company names, and product names exactly as they appear
- Do NOT translate technical terms or proper nouns
- Integrate information from all sections into a cohesive narrative
- Focus on key decisions, action items, important discussions, and outcomes across all sections
- Structure the summary clearly with main points and sub-points
- Include any deadlines, responsibilities, or next steps mentioned
- Remove any redundancy between sections

Section Summaries:
---
{combined_summaries}
---

Please provide the final comprehensive summary:"""
        
        try:
            print(f"[SUMMARIZATION] Calling OpenAI API for final summary with model: {OPENAI_MODEL_SUMMARY}...")
            final_start = time.time()
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL_SUMMARY,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ]
            )
            final_duration = time.time() - final_start
            print(f"[SUMMARIZATION] ✓ Final summary completed in {final_duration:.2f} seconds")
            return response.choices[0].message.content
        except Exception as e:
            print(f"[SUMMARIZATION] ✗ Final summarization failed: {str(e)}")
            raise RuntimeError(f"Final summarization failed: {str(e)}")

