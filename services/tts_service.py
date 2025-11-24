"""
Text To Speech Service Module
Handles text-to-speech conversion using gTTS (Google TTS - preferred) or transformers pipeline (fallback).
"""
import os
import logging
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)

# Initialize TTS library availability flags
USE_GTTS = False
USE_TRANSFORMERS = False
TTS_AVAILABLE = False

# Try gTTS first (Google TTS - free, online, no API key needed, preferred)
try:
    from gtts import gTTS
    TTS_AVAILABLE = True
    USE_GTTS = True
    logger.info("gTTS is available - will use Google Text-to-Speech (free, online, no API key needed)")
except ImportError:
    USE_GTTS = False
    # Fallback to transformers pipeline (local, no API key needed)
    try:
        from transformers import pipeline
        import torch
        TTS_AVAILABLE = True
        USE_TRANSFORMERS = True
        logger.info("transformers is available - will use local TTS pipeline (no API key needed)")
    except ImportError:
        TTS_AVAILABLE = False
        USE_TRANSFORMERS = False
        logger.warning("Neither gTTS nor transformers installed. Install one: pip install gtts (recommended) or pip install transformers torch")


class TTSService:
    """
    Service for text-to-speech conversion.
    
    This class handles:
    - Using gTTS (Google Text-to-Speech) - free, online, no API key (preferred)
    - Using transformers pipeline - local, no API key, requires model download (fallback)
    - Converting text to speech audio
    """
    LANGUAGE_MAP = {
        'vi': 'vi',
        'en': 'en',
        'zh': 'zh-cn',
        'ja': 'ja',
        'ko': 'ko',
        'fr': 'fr',
        'de': 'de',
        'es': 'es',
    }

    def __init__(self):
        """
        Initialize TTS service - prefers gTTS (Google TTS), falls back to transformers pipeline.
        """
        self.pipeline = None
        self._service_available = False
        self.use_gtts = False
        self.use_transformers = False

        local_available = False
        
        if USE_GTTS:
            self.use_gtts = True
            local_available = True
        else:
            try:
                from gtts import gTTS  # noqa: F401
                self.use_gtts = True
                local_available = True
            except ImportError:
                self.use_gtts = False
        
        if not self.use_gtts:
            if USE_TRANSFORMERS:
                self.use_transformers = True
                local_available = True
            else:
                try:
                    from transformers import pipeline  # noqa: F401
                    import torch  # noqa: F401
                    self.use_transformers = True
                    local_available = True
                except ImportError:
                    self.use_transformers = False
        
        if not local_available and not TTS_AVAILABLE:
            logger.warning("TTS service not available. Install with: pip install gtts (recommended) or pip install transformers torch")
            return
        
        if self.use_gtts:
            # gTTS doesn't need initialization
            self._service_available = True
            logger.info("TTS service initialized with gTTS (Google Text-to-Speech - free, online, no API key needed)")
            return
        
        if self.use_transformers:
            # Initialize transformers pipeline (will load model on first use)
            self._service_available = True
            logger.info("TTS service initialized with transformers pipeline (local, no API key needed)")
            logger.info("Model will be downloaded on first use (~500MB)")
            return

    def _normalize_language(self, language: Optional[str]) -> str:
        """Resolve requested language to supported code."""
        if not language:
            return 'en'
        return self.LANGUAGE_MAP.get(language.lower(), 'en')

    def _prepare_output_file(self, output_file: Optional[str], suffix: str) -> str:
        """Create or reuse an output filepath for the generated audio."""
        if output_file:
            output_dir = os.path.dirname(output_file) or tempfile.gettempdir()
            os.makedirs(output_dir, exist_ok=True)
            return output_file
        temp_fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=tempfile.gettempdir())
        os.close(temp_fd)
        return temp_path

    def is_available(self) -> bool:
        """
        Check if TTS service is available.
        
        Returns:
            True if TTS is available, False otherwise
        """
        return self._service_available
    
    def _get_transformers_pipeline(self):
        """
        Get or create transformers TTS pipeline.
        Model is loaded lazily on first use.
        
        Returns:
            TTS pipeline
        """
        if self.pipeline is None:
            try:
                from transformers import pipeline
                import torch
                
                logger.info("Loading TTS model: microsoft/speecht5_tts (this may take a while on first use)...")
                self.pipeline = pipeline(
                    "text-to-speech",
                    model="microsoft/speecht5_tts",
                    device=0 if torch.cuda.is_available() else -1  # Use GPU if available
                )
                logger.info("TTS model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load TTS model: {e}")
                raise RuntimeError(f"Failed to load TTS model: {str(e)}")
        
        return self.pipeline
    
    def _get_speaker_embedding(self):
        """
        Get speaker embedding for speecht5_tts model.
        Uses a default embedding from the cmu-arctic-xvectors dataset.
        
        Returns:
            Speaker embedding tensor
        """
        try:
            from datasets import load_dataset
            import torch
            
            # Load speaker embeddings dataset
            embeddings_dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
            # Use a default speaker (index 7306 is a good default)
            speaker_embedding = torch.tensor(embeddings_dataset[7306]["xvector"]).unsqueeze(0)
            return speaker_embedding
        except Exception as e:
            logger.warning(f"Failed to load speaker embedding, using None: {e}")
            # Some models might work without explicit embedding
            return None
    
    def text_to_speech(
        self,
        text: str,
        language: Optional[str] = None,
        output_file: Optional[str] = None
    ) -> Optional[str]:
        """
        Convert text to speech audio file.
        
        Args:
            text: Text to convert to speech
            language: Language code (vi, en, zh, ja, ko, fr, de, es)
            output_file: Optional output file path. If None, creates temp file.
            
        Returns:
            Path to generated audio file, or None if failed
        """
        if not self.is_available():
            raise RuntimeError(
                "TTS service is not available. "
                "Please install gTTS (recommended, free): pip install gtts "
                "or install transformers and torch: pip install transformers torch"
            )
        
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        resolved_language = self._normalize_language(language)
        
        try:
            if self.use_gtts:
                from gtts import gTTS
                
                logger.info("Converting text to speech using gTTS (Google Text-to-Speech)")
                logger.info(f"Text length: {len(text)} characters, Language: {resolved_language}")
                
                output_path = self._prepare_output_file(output_file, '.mp3')
                tts = gTTS(text=text, lang=resolved_language, slow=False)
                tts.save(output_path)
                
                if not os.path.exists(output_path):
                    raise RuntimeError("Failed to create audio file")
                
                file_size = os.path.getsize(output_path)
                if file_size == 0:
                    raise RuntimeError("Generated audio file is empty")
                
                logger.info(f"TTS audio saved to: {output_path} (size: {file_size} bytes)")
                return output_path
            
            # Fallback to transformers pipeline if available (local, no API key needed)
            if self.use_transformers:
                import numpy as np
                
                logger.info(f"Converting text to speech using transformers pipeline (local)")
                logger.info(f"Text length: {len(text)} characters")
                
                # Get pipeline (loads model on first use)
                pipe = self._get_transformers_pipeline()
                
                # Get speaker embedding for speecht5_tts
                speaker_embedding = self._get_speaker_embedding()
                
                # Generate speech
                logger.info("Generating speech...")
                if speaker_embedding is not None:
                    output = pipe(text, forward_params={"speaker_embeddings": speaker_embedding})
                else:
                    output = pipe(text)
                
                # Extract audio array and sample rate
                if isinstance(output, dict):
                    audio_array = output.get("audio", output.get("raw", None))
                    sample_rate = output.get("sampling_rate", 22050)
                elif isinstance(output, tuple):
                    audio_array, sample_rate = output
                else:
                    audio_array = output
                    sample_rate = 22050
                
                # Ensure numpy array
                if isinstance(audio_array, list):
                    audio_array = np.array(audio_array)
                elif not isinstance(audio_array, np.ndarray):
                    audio_array = np.array(audio_array)
                
                output_path = self._prepare_output_file(output_file, '.wav')
                
                try:
                    import soundfile as sf
                    sf.write(output_path, audio_array, sample_rate)
                except ImportError:
                    try:
                        from scipy.io import wavfile
                        # Normalize to int16 range
                        if audio_array.dtype != np.int16:
                            # Normalize to [-1, 1] range first
                            if audio_array.max() > 1.0 or audio_array.min() < -1.0:
                                audio_array = audio_array / np.max(np.abs(audio_array))
                            audio_array = (audio_array * 32767).astype(np.int16)
                        wavfile.write(output_path, sample_rate, audio_array)
                    except ImportError:
                        raise RuntimeError(
                            "Need soundfile or scipy to save audio. "
                            "Install with: pip install soundfile or pip install scipy"
                        )
                
                # Verify file
                if not os.path.exists(output_path):
                    raise RuntimeError("Failed to create audio file")
                
                file_size = os.path.getsize(output_path)
                if file_size == 0:
                    raise RuntimeError("Generated audio file is empty")
                
                logger.info(f"TTS audio saved to: {output_path} (size: {file_size} bytes)")
                return output_path
            
            # Should not reach here
            raise RuntimeError("No TTS method available")
            
        except Exception as e:
            logger.error(f"TTS conversion failed: {e}")
            raise RuntimeError(f"Text-to-speech conversion failed: {str(e)}")
