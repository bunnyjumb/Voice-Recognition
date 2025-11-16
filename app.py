"""
Flask Application for Meeting Summary
Main application file with routes and request handling.
"""
import traceback
from flask import Flask, render_template, request, jsonify, send_from_directory

from config import ensure_upload_directory
from services.audio_service import AudioService
from services.ai_service import AIService


# Initialize Flask application
app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = ensure_upload_directory()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize services
audio_service = AudioService(upload_folder=UPLOAD_FOLDER)
ai_service = AIService()


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/process-audio', methods=['POST'])
def process_audio():
    """
    Process uploaded audio file: transcribe and summarize.
    
    Returns:
        JSON response with summary, transcript, and download URL
    """
    # Check if AI service is available
    if not ai_service.is_available():
        return jsonify({
            "error": "AI service is not available. Please check configuration."
        }), 500
    
    # Validate audio file
    if 'audio_data' not in request.files:
        return jsonify({"error": "No audio file found in request"}), 400
    
    file = request.files['audio_data']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Get form data - validate required fields
    topic = request.form.get('topic', '').strip()
    language = request.form.get('language', '').strip()
    custom_language = request.form.get('custom_language', '').strip() or None
    
    # Validate required fields
    if not topic:
        return jsonify({"error": "Meeting Topic is required"}), 400
    
    if not language:
        return jsonify({"error": "Conversation Language is required"}), 400
    
    if language == 'other' and not custom_language:
        return jsonify({"error": "Custom language is required when 'Other' is selected"}), 400
    
    try:
        # Save audio file
        filepath, filename = audio_service.save_audio_file(file)
        print(f"File saved at: {filepath}")
        print(f"Topic: {topic}")
        print(f"Language: {language}")
        if custom_language:
            print(f"Custom language: {custom_language}")
        
        # Step 1: Transcribe audio to text (with auto-compression if needed)
        print("Starting transcription...")
        try:
            # Check file size and inform user
            import os
            file_size = os.path.getsize(filepath)
            file_size_mb = file_size / (1024 * 1024)
            max_size_mb = 25
            
            if file_size_mb > max_size_mb:
                print(f"File is large ({file_size_mb:.2f}MB), will attempt compression before transcription...")
            
            transcript = ai_service.transcribe_audio(
                audio_file_path=filepath,
                language=language if language != 'other' else None
            )
        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages
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
        print(f"Transcript: {transcript[:100]}...")  # Print first 100 chars
        
        # Step 2: Summarize transcript
        print("Starting summarization...")
        summary = ai_service.summarize_transcript(
            transcript=transcript,
            topic=topic,
            language=language,
            custom_language=custom_language
        )
        print(f"Summary generated successfully")
        
        # Return results
        return jsonify({
            "summary": summary,
            "transcript": transcript,
            "download_url": f"/uploads/{filename}"
        })
    
    except ValueError as e:
        print(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        print(f"Processing error: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
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
    try:
        from services.audio_compressor import AudioCompressor
        compressor = AudioCompressor()
        ffmpeg_available = compressor._ffmpeg_available
        
        return jsonify({
            "ffmpeg_available": ffmpeg_available,
            "message": "FFmpeg is installed and ready" if ffmpeg_available else "FFmpeg is not installed"
        })
    except Exception as e:
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
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True)
