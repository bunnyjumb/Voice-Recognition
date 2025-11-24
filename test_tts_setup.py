"""
Script to test TTS service setup and diagnose issues.
Run this to check if TTS service is properly configured.
"""
import os
import sys

print("=" * 60)
print("TTS Service Setup Diagnostic")
print("=" * 60)

# Check 1: huggingface_hub library
print("\n[1] Checking huggingface_hub library...")
try:
    import huggingface_hub
    print(f"✓ huggingface_hub is installed (version: {huggingface_hub.__version__})")
except ImportError:
    print("✗ huggingface_hub is NOT installed")
    print("  Solution: pip install huggingface_hub")
    sys.exit(1)

# Check 2: InferenceClient
print("\n[2] Checking InferenceClient...")
try:
    from huggingface_hub import InferenceClient
    print("✓ InferenceClient can be imported")
except ImportError as e:
    print(f"✗ Cannot import InferenceClient: {e}")
    sys.exit(1)

# Check 3: HF_TOKEN
print("\n[3] Checking HF_TOKEN...")
hf_token = os.environ.get("HF_TOKEN", "")
if hf_token:
    print(f"✓ HF_TOKEN is set (length: {len(hf_token)} characters)")
    print(f"  Token starts with: {hf_token[:10]}...")
else:
    print("✗ HF_TOKEN is NOT set")
    print("  Solution: Set environment variable HF_TOKEN")
    print("  Windows PowerShell: $env:HF_TOKEN='your_token_here'")
    print("  Windows CMD: set HF_TOKEN=your_token_here")
    print("  Linux/Mac: export HF_TOKEN='your_token_here'")
    sys.exit(1)

# Check 4: Config values
print("\n[4] Checking config values...")
try:
    from config import HF_TOKEN, HF_TTS_MODEL, HF_TTS_PROVIDER
    print(f"✓ Config loaded successfully")
    print(f"  HF_TTS_MODEL: {HF_TTS_MODEL}")
    print(f"  HF_TTS_PROVIDER: {HF_TTS_PROVIDER}")
    if HF_TOKEN:
        print(f"  HF_TOKEN from config: Set (length: {len(HF_TOKEN)})")
    else:
        print(f"  HF_TOKEN from config: Not set")
except Exception as e:
    print(f"✗ Error loading config: {e}")
    sys.exit(1)

# Check 5: Initialize TTS Service
print("\n[5] Testing TTS Service initialization...")
try:
    from services.tts_service import TTSService
    tts_service = TTSService()
    
    if tts_service.is_available():
        print("✓ TTS Service is available and ready")
    else:
        print("✗ TTS Service is NOT available")
        print("  Checking details...")
        print(f"  - client is None: {tts_service.client is None}")
        print(f"  - api_key is None: {tts_service.api_key is None}")
        print(f"  - _service_available: {tts_service._service_available}")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error initializing TTS Service: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Check 6: Test API connection (optional, might take time)
print("\n[6] Testing API connection (this may take a moment)...")
try:
    from config import HF_TTS_MODEL
    test_text = "Hello, this is a test."
    
    print(f"  Testing with model: {HF_TTS_MODEL}")
    print(f"  Test text: '{test_text}'")
    
    audio_file = tts_service.text_to_speech(
        text=test_text,
        language="en"
    )
    
    if audio_file and os.path.exists(audio_file):
        file_size = os.path.getsize(audio_file)
        print(f"✓ API connection successful!")
        print(f"  Generated audio file: {audio_file}")
        print(f"  File size: {file_size} bytes")
        
        # Clean up test file
        try:
            os.remove(audio_file)
            print("  Test file cleaned up")
        except:
            pass
    else:
        print("✗ API connection failed - no audio file generated")
        sys.exit(1)
        
except Exception as e:
    print(f"✗ API connection test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All checks passed! TTS service is ready to use.")
print("=" * 60)

