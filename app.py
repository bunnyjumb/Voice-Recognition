"""
Flask Application for Meeting Summary
Main application file with routes and request handling.
"""
import traceback
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

from config import ensure_upload_directory
from services.audio_service import AudioService
from services.ai_service import AIService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
ai_service = AIService()
logger.info("Services initialized successfully")


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
        
        # Step 2: Validate audio file
        logger.info("[STEP 2/5] Validating audio file...")
        if 'audio_data' not in request.files:
            logger.error("No audio file found in request")
            return jsonify({"error": "No audio file found in request"}), 400
        
        file = request.files['audio_data']
        if file.filename == '':
            logger.error("No file selected")
            return jsonify({"error": "No file selected"}), 400
        logger.info(f"✓ Audio file received: {file.filename}")
        
        # Step 3: Validate form data
        logger.info("[STEP 3/5] Validating form data...")
        topic = request.form.get('topic', '').strip()
        language = request.form.get('language', '').strip()
        custom_language = request.form.get('custom_language', '').strip() or None
        
        if not topic:
            logger.error("Meeting Topic is required")
            return jsonify({"error": "Meeting Topic is required"}), 400
        
        if not language:
            logger.error("Conversation Language is required")
            return jsonify({"error": "Conversation Language is required"}), 400
        
        if language == 'other' and not custom_language:
            logger.error("Custom language is required when 'Other' is selected")
            return jsonify({"error": "Custom language is required when 'Other' is selected"}), 400
        
        logger.info(f"✓ Form data validated - Topic: {topic}, Language: {language}")
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
        
        # Step 7: Return results
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
        from services.audio_compressor import AudioCompressor
        compressor = AudioCompressor()
        ffmpeg_available = compressor._ffmpeg_available
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


if __name__ == '__main__':
    app.run(debug=True)
