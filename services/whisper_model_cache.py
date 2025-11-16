"""
Whisper Model Cache Module
Caches Whisper models to avoid reloading on every request.
Preloads models when server starts for better user experience.
"""
import threading
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class WhisperModelCache:
    """
    Singleton cache for Whisper models.
    Loads models once and reuses them across requests.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WhisperModelCache, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the cache (only once)."""
        if self._initialized:
            return
        
        self.models: Dict[str, any] = {}  # Store loaded models
        self.loading: Dict[str, threading.Lock] = {}  # Locks for loading models
        self._initialized = True
        logger.info("[WHISPER CACHE] Model cache initialized")
    
    def get_model(self, model_name: str, preload: bool = False):
        """
        Get a Whisper model, loading it if not already cached.
        
        Args:
            model_name: Name of the Whisper model (tiny, base, small, medium, large)
            preload: If True, load model in background thread
            
        Returns:
            Whisper model instance
        """
        # Check if model is already loaded
        if model_name in self.models:
            logger.info(f"[WHISPER CACHE] Model '{model_name}' found in cache")
            return self.models[model_name]
        
        # Check if model is currently being loaded
        if model_name not in self.loading:
            self.loading[model_name] = threading.Lock()
        
        with self.loading[model_name]:
            # Double-check after acquiring lock
            if model_name in self.models:
                logger.info(f"[WHISPER CACHE] Model '{model_name}' loaded by another thread")
                return self.models[model_name]
            
            # Load the model
            logger.info(f"[WHISPER CACHE] Loading model '{model_name}'...")
            try:
                import whisper
                import time
                load_start = time.time()
                
                model = whisper.load_model(model_name)
                load_duration = time.time() - load_start
                
                # Cache the model
                self.models[model_name] = model
                logger.info(f"[WHISPER CACHE] ✓ Model '{model_name}' loaded and cached in {load_duration:.2f} seconds")
                
                return model
            except Exception as e:
                logger.error(f"[WHISPER CACHE] ✗ Failed to load model '{model_name}': {e}")
                raise
    
    def preload_model(self, model_name: str):
        """
        Preload a model in a background thread.
        
        Args:
            model_name: Name of the Whisper model to preload
        """
        def load_in_background():
            try:
                logger.info(f"[WHISPER CACHE] Preloading model '{model_name}' in background...")
                self.get_model(model_name)
                logger.info(f"[WHISPER CACHE] ✓ Model '{model_name}' preloaded successfully")
            except Exception as e:
                logger.error(f"[WHISPER CACHE] ✗ Failed to preload model '{model_name}': {e}")
        
        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()
        logger.info(f"[WHISPER CACHE] Started background thread to preload '{model_name}'")
    
    def preload_common_models(self):
        """
        Preload common models (base and medium) in background.
        These are the most commonly used models.
        """
        logger.info("[WHISPER CACHE] Preloading common models (base, medium)...")
        self.preload_model("base")
        self.preload_model("medium")
    
    def clear_cache(self):
        """Clear all cached models (useful for testing or memory management)."""
        logger.info("[WHISPER CACHE] Clearing model cache...")
        self.models.clear()
        logger.info("[WHISPER CACHE] ✓ Cache cleared")
    
    def get_cached_models(self):
        """Get list of currently cached model names."""
        return list(self.models.keys())


# Global singleton instance
_model_cache = None

def get_model_cache() -> WhisperModelCache:
    """Get the global WhisperModelCache instance."""
    global _model_cache
    if _model_cache is None:
        _model_cache = WhisperModelCache()
    return _model_cache

