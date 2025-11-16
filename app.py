"""
Flask Application for Meeting Summary
Main application file with routes and request handling.
"""
import traceback
import logging
import sys
import signal
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

from config import ensure_upload_directory
from services.audio_service import AudioService
from services.ai_service import AIService
from services.validation_service import ValidationService
from services.file_cleanup_service import FileCleanupService
from utils.ffmpeg_checker import get_ffmpeg_checker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Suppress noisy warnings
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="whisper")

# Initialize Flask application
app = Flask(__name__)

# Configure upload folder
logger.info("Initializing Flask application...")
UPLOAD_FOLDER = ensure_upload_directory()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
logger.info(f"Upload folder configured: {UPLOAD_FOLDER}")

# Initialize services
logger.info("Initializing services...")
audio_service = AudioService(upload_folder=UPLOAD_FOLDER)
logger.info("AudioService initialized")

# Initialize validation service
validation_service = ValidationService()
logger.info("ValidationService initialized")

# Initialize file cleanup service
cleanup_service = FileCleanupService(upload_folder=UPLOAD_FOLDER)
logger.info("FileCleanupService initialized")

# Run initial cleanup of old files
try:
    deleted_count = cleanup_service.cleanup_old_files()
    if deleted_count > 0:
        logger.info(f"Initial cleanup: {deleted_count} old files removed")
except Exception as e:
    logger.warning(f"Initial cleanup failed: {e}")

# Initialize AI service (this will preload Whisper models in background)
logger.info("Initializing AIService (preloading Whisper models in background)...")
ai_service = AIService()
logger.info("AIService initialized - Whisper models are preloading in background")
logger.info("Note: First request may wait for model loading, subsequent requests will be faster")


@app.route('/')
def index():
    """Render the main page."""
    logger.info("GET / - Rendering index page")
    return render_template('index.html')


@app.route('/process-audio', methods=['POST'])
def process_audio():
    """
    Process uploaded audio file: transcribe and summarize.
    
    Returns:
        JSON response with summary and download URL
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("POST /process-audio - Starting audio processing")
    logger.info("=" * 60)
    
    try:
        # Step 1: Validate AI service
        logger.info("[STEP 1/5] Checking AI service availability...")
        if not ai_service.is_available():
            logger.error("AI service is not available")
            return jsonify({
                "error": "AI service is not available. Please check configuration."
            }), 500
        logger.info("✓ AI service is available")
        
        # Step 2 & 3: Validate request (audio file + form data)
        logger.info("[STEP 2/5] Validating request...")
        is_valid, error_msg, validated_data = validation_service.validate_audio_request(
            form_data=request.form,
            files=request.files
        )
        
        if not is_valid:
            logger.error(f"Validation failed: {error_msg}")
            return jsonify({"error": error_msg}), 400
        
        file = request.files['audio_data']
        topic = validated_data['topic']
        language = validated_data['language']
        custom_language = validated_data['custom_language']
        
        logger.info(f"✓ Request validated - File: {file.filename}, Topic: {topic}, Language: {language}")
        if custom_language:
            logger.info(f"  Custom language: {custom_language}")
        
        # Step 4: Save audio file
        logger.info("[STEP 4/5] Saving audio file...")
        filepath, filename = audio_service.save_audio_file(file)
        logger.info(f"✓ File saved successfully")
        logger.info(f"  Filepath: {filepath}")
        logger.info(f"  Filename: {filename}")
        
        # Check file size
        import os
        file_size = os.path.getsize(filepath)
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"  File size: {file_size_mb:.2f}MB")
        
        # Step 5: Transcribe audio to text
        logger.info("[STEP 5/5] Starting transcription...")
        logger.info(f"  Language: {language if language != 'other' else custom_language}")
        
        if file_size_mb > 25:
            logger.warning(f"  File is large ({file_size_mb:.2f}MB), may need compression/splitting")
        
        transcript_start = datetime.now()
        try:
            transcript = ai_service.transcribe_audio(
                audio_file_path=filepath,
                language=language if language != 'other' else None
            )
            transcript_duration = (datetime.now() - transcript_start).total_seconds()
            logger.info(f"✓ Transcription completed in {transcript_duration:.2f} seconds")
            logger.info(f"  Transcript length: {len(transcript)} characters")
            logger.info(f"  Transcript preview: {transcript[:100]}...")
        except Exception as e:
            transcript_duration = (datetime.now() - transcript_start).total_seconds()
            logger.error(f"✗ Transcription failed after {transcript_duration:.2f} seconds: {str(e)}")
            error_msg = str(e)
            if 'Connection' in error_msg or 'timeout' in error_msg.lower():
                raise RuntimeError(
                    "Transcription failed: Connection error. This may be due to:\n"
                    "- Network connectivity issues\n"
                    "- Audio file format not supported (Whisper supports: mp3, mp4, mpeg, mpga, m4a, wav, webm)\n"
                    "- File too large or corrupted\n"
                    "Please check your network connection and try again with a supported audio format."
                )
            elif 'file' in error_msg.lower() or 'format' in error_msg.lower():
                raise RuntimeError(
                    f"Transcription failed: {error_msg}\n"
                    "Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm"
                )
            else:
                raise RuntimeError(f"Transcription failed: {error_msg}")
        
        # Step 6: Summarize transcript
        logger.info("[STEP 6/6] Starting summarization...")
        summary_start = datetime.now()
        try:
            summary = ai_service.summarize_transcript(
                transcript=transcript,
                topic=topic,
                language=language,
                custom_language=custom_language
            )
            summary_duration = (datetime.now() - summary_start).total_seconds()
            logger.info(f"✓ Summarization completed in {summary_duration:.2f} seconds")
            logger.info(f"  Summary length: {len(summary)} characters")
        except Exception as e:
            summary_duration = (datetime.now() - summary_start).total_seconds()
            logger.error(f"✗ Summarization failed after {summary_duration:.2f} seconds: {str(e)}")
            raise
        
        # Step 7: Cleanup old files (async, don't block response)
        try:
            # Cleanup old files in background (non-blocking)
            cleanup_service.cleanup_old_files()
        except Exception as e:
            logger.warning(f"Cleanup failed (non-critical): {e}")
        
        # Step 8: Return results
        total_duration = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"✓ Processing completed successfully in {total_duration:.2f} seconds")
        logger.info(f"  Transcription: {transcript_duration:.2f}s")
        logger.info(f"  Summarization: {summary_duration:.2f}s")
        logger.info("=" * 60)
        
        return jsonify({
            "summary": summary,
            "download_url": f"/uploads/{filename}"
        })
    
    except ValueError as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"✗ Validation error after {duration:.2f} seconds: {e}")
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"✗ Processing error after {duration:.2f} seconds: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"✗ Unexpected error after {duration:.2f} seconds: {e}")
        logger.exception("Full traceback:")
        traceback.print_exc()
        return jsonify({
            "error": f"An unexpected error occurred: {str(e)}"
        }), 500


@app.route('/check-ffmpeg', methods=['GET'])
def check_ffmpeg():
    """
    Check if FFmpeg is available on the server.
    
    Returns:
        JSON response with FFmpeg availability status
    """
    logger.info("GET /check-ffmpeg - Checking FFmpeg availability")
    try:
        ffmpeg_checker = get_ffmpeg_checker()
        ffmpeg_available = ffmpeg_checker.is_available()
        logger.info(f"FFmpeg available: {ffmpeg_available}")
        return jsonify({
            "ffmpeg_available": ffmpeg_available,
            "message": "FFmpeg is installed and ready" if ffmpeg_available else "FFmpeg is not installed"
        })
    except Exception as e:
        logger.error(f"Error checking FFmpeg: {e}")
        return jsonify({
            "ffmpeg_available": False,
            "message": f"Error checking FFmpeg: {str(e)}"
        })


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    Serve uploaded files.
    
    Args:
        filename: Name of the file to serve
        
    Returns:
        File response
    """
    logger.info(f"GET /uploads/{filename} - Serving file")
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("\nShutting down gracefully...")
    sys.exit(0)


if __name__ == '__main__':
    # Register signal handlers for graceful shutdown (if supported)
    try:
        signal.signal(signal.SIGINT, signal_handler)
    except (ValueError, OSError):
        # SIGINT may not be available on all platforms
        pass
    
    try:
        signal.signal(signal.SIGTERM, signal_handler)
    except (ValueError, OSError):
        # SIGTERM may not be available on Windows
        pass
    
    try:
        # Disable reloader to prevent issues during long-running transcription tasks
        # Set use_reloader=False to avoid socket errors when files change during processing
        # This is important because transcription can take several minutes
        # Threaded=True allows handling multiple requests concurrently
        logger.info("Starting Flask development server...")
        logger.info("Note: Auto-reloader is disabled to prevent issues during long operations")
        logger.info("Server will run on http://127.0.0.1:5000")
        app.run(debug=True, use_reloader=False, threaded=True, host='127.0.0.1', port=5000)
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        traceback.print_exc()
        sys.exit(1)
