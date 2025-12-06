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
from services.chromadb_service import ChromaDBService
from services.tts_service import TTSService
from utils.ffmpeg_checker import get_ffmpeg_checker

from services.pinecone_service import PineconeService
from services.rag_service import RAGService

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

# Initialize ChromaDB service
logger.info("Initializing ChromaDB service...")
chromadb_service = ChromaDBService()
if chromadb_service.is_available():
    logger.info("ChromaDB service initialized successfully")
else:
    logger.warning("ChromaDB service not available - transcripts will not be stored")

# Initialize TTS service
logger.info("Initializing TTS service...")
tts_service = TTSService()
if tts_service.is_available():
    logger.info("TTS service initialized successfully")
else:
    logger.warning("TTS service not available - text-to-speech will not work")
    # Check why it's not available
    try:
        from config import HF_TOKEN
        if not HF_TOKEN:
            logger.warning("  Reason: HF_TOKEN is not set. Please set it as environment variable.")
        else:
            logger.warning(f"  Reason: TTS service initialization failed. HF_TOKEN is set: {bool(HF_TOKEN)}")
    except Exception as e:
        logger.warning(f"  Reason: Could not check HF_TOKEN: {e}")


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
            print("-------------TEST------------------------------------------------------------")
            print(transcript)
            print("-------------TEST---END------------------------------------------------------")
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
        
        # Step 7: Store transcript in ChromaDB
        transcript_id = ""
        try:
            logger.info("[STEP 7/8] Storing transcript in ChromaDB...")
            transcript_id = chromadb_service.store_transcript(
                transcript=transcript,
                summary=summary,
                topic=topic,
                language=language,
                custom_language=custom_language,
                metadata={
                    "filename": filename,
                    "file_size_mb": round(file_size_mb, 2)
                }
            )
            if transcript_id:
                logger.info(f"✓ Transcript stored in ChromaDB with ID: {transcript_id}")
                if pinecone_service.is_available():
                    try:
                        pinecone_service.upsert(
                            doc_id=transcript_id,
                            transcript=transcript,
                            summary=summary,
                            metadata={
                                "topic": topic,
                                "language": language,
                                "filename": filename,
                            },
                        )
                        logger.info("✓ Transcript also indexed in Pinecone")
                    except Exception as e:
                        logger.warning(
                            f"Failed to upsert transcript into Pinecone (non-critical): {e}"
                        )
                else:
                    logger.warning(
                        "PineconeService not available, skipping Pinecone upsert"
                    )
            else:
                logger.warning("ChromaDB storage failed or not available")
        except Exception as e:
            logger.warning(f"Failed to store transcript in ChromaDB (non-critical): {e}")
        
        # Step 8: Cleanup old files (async, don't block response)
        try:
            # Cleanup old files in background (non-blocking)
            cleanup_service.cleanup_old_files()
        except Exception as e:
            logger.warning(f"Cleanup failed (non-critical): {e}")
        
        # Step 9: Return results
        total_duration = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"✓ Processing completed successfully in {total_duration:.2f} seconds")
        logger.info(f"  Transcription: {transcript_duration:.2f}s")
        logger.info(f"  Summarization: {summary_duration:.2f}s")
        logger.info("=" * 60)
        
        return jsonify({
            "summary": summary,
            "download_url": f"/uploads/{filename}",
            "transcript_id": transcript_id,
            "language": language,
            "custom_language": custom_language
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


@app.route('/generate-tts', methods=['POST'])
def generate_tts():
    """
    Generate text-to-speech audio from summary text.
    
    Request body (JSON):
        - text: Text to convert to speech
        - language: Language code for TTS
        
    Returns:
        JSON response with audio file URL
    """
    logger.info("POST /generate-tts - Generating TTS audio")
    
    try:
        if not tts_service.is_available():
            # Provide detailed error message
            error_msg = "TTS service is not available. "
            try:
                from config import HF_TOKEN
                if not HF_TOKEN:
                    error_msg += "Please set HF_TOKEN environment variable. "
                else:
                    error_msg += "TTS service initialization failed. "
            except:
                pass
            error_msg += "Please check: 1) Install huggingface_hub: pip install huggingface_hub, 2) Set HF_TOKEN environment variable"
            return jsonify({"error": error_msg}), 503
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        text = data.get('text', '').strip()
        language = data.get('language', 'en')
        custom_language = data.get('custom_language', None)
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        logger.info(f"Generating TTS for text (length: {len(text)} chars, language: {language})")
        
        # Generate TTS audio
        import os
        audio_file = tts_service.text_to_speech(
            text=text,
            language=language if language != 'other' else None
        )
        
        if not audio_file or not os.path.exists(audio_file):
            return jsonify({"error": "Failed to generate TTS audio"}), 500
        
        # Move audio file to uploads folder for serving
        import shutil
        # Get file extension from generated file (gTTS creates .mp3, HuggingFace creates .wav)
        file_ext = os.path.splitext(audio_file)[1] or '.mp3'
        audio_filename = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
        audio_dest = os.path.join(UPLOAD_FOLDER, audio_filename)
        shutil.move(audio_file, audio_dest)
        
        logger.info(f"TTS audio generated: {audio_filename}")
        
        return jsonify({
            "audio_url": f"/uploads/{audio_filename}",
            "filename": audio_filename
        })
        
    except ValueError as e:
        logger.error(f"TTS validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        logger.error(f"TTS generation error: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"TTS unexpected error: {e}")
        logger.exception("Full traceback:")
        traceback.print_exc()
        return jsonify({
            "error": f"An unexpected error occurred: {str(e)}"
        }), 500


@app.route('/api/transcripts', methods=['GET'])
def list_transcripts():
    """
    Return stored transcripts summaries for reuse/playback.
    Query params:
        query: semantic search text
        topic: exact topic filter
        language: language code filter
        limit: number of entries (default 10, max 50)
    """
    if not chromadb_service.is_available():
        return jsonify({"items": [], "error": "ChromaDB service unavailable"}), 503

    query = request.args.get('query', '').strip() or None
    topic = request.args.get('topic', '').strip() or None
    language = request.args.get('language', '').strip() or None
    try:
        limit = int(request.args.get('limit', 10))
    except ValueError:
        limit = 10
    limit = max(1, min(limit, 50))

    results = chromadb_service.query_transcripts(
        query_text=query,
        topic=topic,
        language=language,
        limit=limit
    )

    for item in results:
        metadata = item.get("metadata") or {}
        # Nếu metadata là list, lấy phần tử đầu tiên
        if isinstance(metadata, list) and metadata:
            metadata = metadata[0]
        filename = metadata.get("filename") if isinstance(metadata, dict) else None
        if filename:
            item["audio_url"] = f"/uploads/{filename}"

    return jsonify({"items": results})


@app.route('/api/transcripts/<doc_id>', methods=['GET'])
def get_transcript(doc_id: str):
    """Return a single transcript entry."""
    if not chromadb_service.is_available():
        return jsonify({"error": "ChromaDB service unavailable"}), 503

    if not doc_id:
        return jsonify({"error": "Transcript ID is required"}), 400

    result = chromadb_service.get_transcript(doc_id)
    if not result:
        return jsonify({"error": "Transcript not found"}), 404

    metadata = result.get("metadata") or {}
    filename = metadata.get("filename")
    if filename:
        result["audio_url"] = f"/uploads/{filename}"

    return jsonify(result)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("\nShutting down gracefully...")
    sys.exit(0)

pinecone_service = PineconeService()
rag_service = RAGService()

if pinecone_service.is_available():
    logger.info("PineconeService initialized (Pinecone vector store)")
else:
    logger.warning("PineconeService not available")

if rag_service.is_available():
    logger.info("RAGService initialized (LangChain + Pinecone)")
else:
    logger.warning("RAGService not available")


@app.route("/api/chat", methods=["POST"])
def chat_global():
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    doc_id = (data.get("doc_id") or "").strip()

    if not question:
        return jsonify({"error": "question required"}), 400

    if not rag_service.is_available():
        return jsonify({"error": "RAG not initialized"}), 503

    result = rag_service.ask_with_priority(question, doc_id)

    if not result or not result.get("result"):
        return jsonify({"error": "No answer found"}), 200

    sources = []
    for doc in result.get("source_documents", []):
        metadata = getattr(doc, "metadata", {}) or {}
        sources.append(
            {
                "filename": metadata.get("filename"),
                "topic": metadata.get("topic"),
            }
        )

    return jsonify(
        {
            "answer": result["result"],
            "sources": sources,
        }
    )

@app.route("/api/transcript/<doc_id>", methods=["DELETE"])
def delete_transcript(doc_id):
    try:
        record = chromadb_service.get_transcript(doc_id)
        if not record:
            return jsonify({"success": False, "error": "Record not found"}), 404

        metadata = record.get("metadata", {})
        filename = metadata.get("filename")
        if filename:
            import os
            audio_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(audio_path):
                os.remove(audio_path)

        try:
            chromadb_service.collection.delete(ids=[doc_id])
        except Exception as e:
            print("Error deleting from ChromaDB:", e)

        try:
            pinecone_service.index.delete(ids=[doc_id])
        except:
            pass 

        return jsonify({"success": True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

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
