# Meeting Summary Assistant - Tài liệu đầy đủ

## Tổng quan

Meeting Summary Assistant là một ứng dụng web Flask cho phép người dùng upload hoặc ghi âm audio, tự động chuyển đổi thành văn bản (transcription) và tạo tóm tắt cuộc họp bằng AI.

## Kiến trúc ứng dụng

### Cấu trúc thư mục

```
Python/
├── app.py                          # Flask application chính
├── config.py                       # Cấu hình và constants
├── requirements.txt                # Dependencies
├── templates/
│   └── index.html                 # Frontend UI
├── services/
│   ├── audio_service.py           # Xử lý file audio
│   ├── audio_compressor.py        # Nén audio files
│   ├── audio_splitter.py          # Chia nhỏ audio files
│   ├── ai_service.py              # AI transcription & summarization
│   ├── whisper_model_cache.py     # Cache Whisper models để tối ưu performance
│   ├── chromadb_service.py        # Lưu trữ transcripts vào ChromaDB
│   └── tts_service.py             # Text-to-Speech sử dụng HuggingFace
├── utils/
│   ├── prompt_builder.py          # Tạo prompts cho AI
│   ├── text_chunker.py            # Chia nhỏ text dài
│   ├── vietnamese_postprocessor.py # Post-processing cho tiếng Việt
│   ├── message_manager.py         # Quản lý conversation history
│   ├── function_calling.py        # Function calling cho OpenAI
│   └── batch_processor.py         # Batch processing
├── uploads/                       # Thư mục lưu files
└── chroma_db/                     # ChromaDB database (tự động tạo)
```

## Luồng xử lý từ đầu đến cuối

### 1. Frontend (index.html)

**Chức năng:**
- Form nhập liệu: Meeting Topic, Language
- Upload file audio hoặc ghi âm trực tiếp
- Hiển thị progress bar và kết quả
- Validation phía client

**Workflow:**
1. User nhập topic và chọn language
2. User upload file hoặc ghi âm
3. JavaScript validate form
4. Gửi POST request đến `/process-audio` với FormData
5. Hiển thị progress bar (simulated)
6. Nhận kết quả và hiển thị summary

### 2. Backend API Routes

#### Route: `/` (GET)
- Render trang chủ (index.html)
- Không xử lý logic

#### Route: `/process-audio` (POST)
**Input:**
- `audio_data`: File audio (multipart/form-data)
- `topic`: Meeting topic (required)
- `language`: Language code (required)
- `custom_language`: Custom language nếu chọn "other"

**Workflow:**
1. **Validation**: Kiểm tra AI service available, file tồn tại, form data hợp lệ
2. **Save File**: Lưu file audio vào thư mục uploads
3. **Transcription**: Chuyển audio thành text
4. **Summarization**: Tạo summary từ transcript
5. **Store in ChromaDB**: Lưu transcript và summary vào ChromaDB với metadata
6. **Response**: Trả về JSON với summary, download URL, và transcript_id

**Output:**
```json
{
  "summary": "Meeting summary text...",
  "download_url": "/uploads/recording_xxx.mp3",
  "transcript_id": "uuid-string",
  "language": "vi",
  "custom_language": ""
}
```

#### Route: `/check-ffmpeg` (GET)
- Kiểm tra FFmpeg có sẵn không
- Trả về JSON với status

#### Route: `/uploads/<filename>` (GET)
- Serve static files từ thư mục uploads

#### Route: `/generate-tts` (POST)
**Input:**
- `text`: Text cần chuyển thành giọng nói (JSON)
- `language`: Language code (JSON)
- `custom_language`: Custom language nếu có (JSON)

**Workflow:**
1. Validate TTS service available
2. Gọi HuggingFace Inference API với model Kokoro-82M
3. Nhận audio bytes từ API
4. Lưu audio vào file WAV
5. Trả về audio URL

**Output:**
```json
{
  "audio_url": "/uploads/tts_20240115_103045.wav",
  "filename": "tts_20240115_103045.wav"
}
```

### 3. Audio Service (audio_service.py)

**Class: AudioService**

**Chức năng:**
- Lưu file audio với tên unique (timestamp-based)
- Quản lý thư mục uploads
- Validate file existence

**Methods:**
- `save_audio_file(file)`: Lưu file và trả về (filepath, filename)
- `get_file_path(filename)`: Lấy full path của file
- `file_exists(filename)`: Kiểm tra file có tồn tại không

### 4. AI Service (ai_service.py)

**Class: AIService**

**Chức năng chính:**
- Transcription: Chuyển audio thành text
- Summarization: Tạo summary từ text

#### 4.1 Transcription Workflow

**Method: `transcribe_audio(audio_file_path, language)`**

**Quy trình xử lý:**

1. **Kiểm tra file size**
   - Nếu ≤ 25MB: Transcribe trực tiếp
   - Nếu > 25MB: Cần compression/splitting

2. **Compression (nếu file lớn)**
   - Sử dụng AudioCompressor
   - Cần FFmpeg
   - Nén xuống < 25MB nếu có thể

3. **Splitting (nếu vẫn lớn)**
   - Sử dụng AudioSplitter
   - Chia thành nhiều chunks ≤ 25MB
   - Mỗi chunk được transcribe riêng
   - Kết hợp các transcripts lại

4. **Transcription Method Selection**
   - **API First**: Thử OpenAI Whisper API trước
   - **Fallback**: Nếu API fail (404), dùng local Whisper

5. **Local Whisper Transcription**
   - Load Whisper model từ cache (WhisperModelCache)
   - Models được preload khi server start (background thread)
   - Model selection:
     - Vietnamese: "medium" (better accuracy)
     - Other languages: "base" (balance speed/accuracy)
   - Models chỉ load 1 lần, reuse cho các requests sau
   - Transcribe với language hint
   - Post-processing cho tiếng Việt (nếu cần)

6. **Post-processing (Vietnamese only)**
   - Sửa lỗi chính tả phổ biến
   - Chuẩn hóa định dạng
   - Cải thiện chất lượng text

**Method: `_transcribe_single_file(audio_file_path, language)`**

- Transcribe một file đơn lẻ (≤ 25MB)
- Thử API trước, fallback local Whisper
- Return transcript text

**Method: `_transcribe_with_local_whisper(audio_file_path, language)`**

- Kiểm tra FFmpeg available
- Load Whisper model từ cache (nếu chưa có thì load và cache)
- Transcribe audio (CPU-intensive, có thể mất vài phút)
- Log estimated và actual processing time
- Post-process nếu là tiếng Việt
- Return transcript

#### 4.2 Summarization Workflow

**Method: `summarize_transcript(transcript, topic, language, custom_language)`**

**Quy trình:**

1. **Kiểm tra độ dài transcript**
   - Nếu ≤ 2000 chars: Summarize trực tiếp
   - Nếu > 2000 chars: Chunked summarization

2. **Single Chunk Summarization**
   - Tạo prompt từ PromptBuilder
   - Gọi OpenAI API với GPT model
   - Return summary

3. **Chunked Summarization**
   - Chia transcript thành chunks (2000 chars/chunk, overlap 200)
   - Summarize từng chunk
   - Combine chunk summaries
   - Tạo final summary từ combined summaries

**Method: `_summarize_single_chunk(...)`**
- Summarize một chunk text
- Sử dụng PromptBuilder để tạo prompts
- Gọi OpenAI API

**Method: `_summarize_chunked(...)`**
- Chia text thành chunks
- Summarize từng chunk
- Combine và tạo final summary

### 5. Audio Processing Services

#### AudioCompressor (audio_compressor.py)
- Nén audio files để giảm kích thước
- Sử dụng FFmpeg
- Presets: high/medium/low compression

#### AudioSplitter (audio_splitter.py)
- Chia audio files thành chunks
- Sử dụng FFmpeg
- Mỗi chunk ≤ 25MB
- Preserve audio quality

### 6. ChromaDB Service (chromadb_service.py)

**Class: ChromaDBService**

**Chức năng:**
- Lưu trữ transcripts và summaries vào ChromaDB (vector database)
- Tự động tạo embeddings cho semantic search
- Lưu metadata (topic, language, timestamp, file info)
- Truy xuất transcripts theo ID hoặc query

**Methods:**
- `store_transcript(...)`: Lưu transcript và summary với metadata
- `get_transcript(doc_id)`: Lấy transcript theo ID
- `query_transcripts(...)`: Tìm kiếm transcripts (semantic search hoặc filter)

**Cấu trúc dữ liệu:**
- Mỗi document có: ID (UUID), document text (transcript + summary), metadata
- ChromaDB tự động tạo embeddings để hỗ trợ semantic search
- Dữ liệu được lưu vĩnh viễn trong thư mục `chroma_db/`

### 7. TTS Service (tts_service.py)

**Class: TTSService**

**Chức năng:**
- Chuyển đổi text thành giọng nói sử dụng HuggingFace Inference API
- Model: Kokoro-82M từ HuggingFace
- Provider: fal-ai
- Hỗ trợ đa ngôn ngữ

**Methods:**
- `text_to_speech(text, language, output_file)`: Chuyển text thành audio file
- `is_available()`: Kiểm tra service có sẵn không

**Cách hoạt động:**
1. Khởi tạo InferenceClient với HF_TOKEN
2. Gọi HuggingFace API với text và model name
3. Nhận audio bytes từ API
4. Ghi bytes vào file WAV
5. Trả về file path

### 8. Utility Modules

#### PromptBuilder (prompt_builder.py)
- Tạo prompts cho AI summarization
- Support multiple languages
- Structured và standard prompts
- Preserve technical terms

#### TextChunker (text_chunker.py)
- Chia text dài thành chunks
- Intelligent splitting (sentence boundaries)
- Overlap để preserve context

#### VietnamesePostProcessor (vietnamese_postprocessor.py)
- Sửa lỗi chính tả tiếng Việt
- Chuẩn hóa định dạng
- Cải thiện transcription quality

#### MessageManager (message_manager.py)
- Quản lý conversation history
- Multi-turn dialogue support
- Context preservation

#### FunctionRegistry (function_calling.py)
- Function calling cho OpenAI
- Mock data schema
- Function definitions

#### BatchProcessor (batch_processor.py)
- Batch processing nhiều requests
- Thread pool execution
- Timeout handling

#### WhisperModelCache (whisper_model_cache.py)
- Singleton cache cho Whisper models
- Preload models khi server start
- Thread-safe với locks
- Reuse models across requests (không cần load lại)
- Background preloading để tối ưu performance

## Cấu hình (config.py)

### API Configuration
- `OPENAI_BASE_URL`: Base URL cho OpenAI API
- `OPENAI_API_KEY`: API key
- `OPENAI_MODEL_TRANSCRIPTION`: Model cho transcription (whisper-1)
- `OPENAI_MODEL_SUMMARY`: Model cho summarization (GPT-5-mini)

### File Configuration
- `UPLOAD_FOLDER`: Thư mục lưu files
- `MAX_FILE_SIZE`: Kích thước file tối đa (100MB)

### Text Chunking
- `MAX_CHARS_PER_CHUNK`: 2000 chars
- `CHUNK_OVERLAP`: 200 chars

### Language Support
- Hỗ trợ: vi, en, zh, ja, ko, fr, de, es, other
- Language mapping cho Whisper API

### HuggingFace TTS Configuration
- `HF_TOKEN`: HuggingFace API token (từ environment variable hoặc config)
- `HF_TTS_MODEL`: Model cho TTS ("hexgrad/Kokoro-82M")
- `HF_TTS_PROVIDER`: Provider cho Inference API ("fal-ai")

### ChromaDB Configuration
- Tự động tạo database trong thư mục `chroma_db/`
- Không cần config thêm, tự động khởi tạo khi app start

## Xử lý lỗi và Fallback

### Transcription Fallback Chain
1. Thử OpenAI Whisper API
2. Nếu 404: Thử alternative URL (/v1)
3. Nếu vẫn fail: Fallback local Whisper
4. Local Whisper: Load model và transcribe

### File Size Handling
1. File ≤ 25MB: Process trực tiếp
2. File > 25MB: Compress trước
3. Nếu vẫn > 25MB: Split thành chunks
4. Process từng chunk và combine

### Error Handling
- Validation errors: 400 Bad Request
- Processing errors: 500 Internal Server Error
- Detailed error messages cho user
- Logging đầy đủ cho debugging

## Tối ưu hóa

### Vietnamese Optimization
- Model: "medium" thay vì "base"
- Post-processing để sửa lỗi
- Better accuracy

### Performance
- **Model Caching**: Whisper models chỉ load 1 lần, reuse cho tất cả requests
- **Preloading**: Models được preload khi server start (background thread)
- **Fast Model Access**: Model load từ cache < 0.1s (thay vì 5+ giây)
- Chunking để xử lý files lớn
- Batch processing support
- Efficient memory usage

### User Experience
- Progress bar (simulated)
- Clear error messages
- Validation feedback
- Download link cho audio file

## Dependencies

### Required
- Flask: Web framework
- openai: OpenAI SDK
- openai-whisper: Local Whisper transcription
- chromadb: Vector database cho lưu trữ transcripts
- huggingface_hub: HuggingFace Inference API client cho TTS

### Optional
- FFmpeg: Cho compression và splitting (required cho files lớn)

## API Endpoints Summary

| Method | Endpoint | Description | Input | Output |
|--------|----------|-------------|-------|--------|
| GET | `/` | Home page | - | HTML |
| POST | `/process-audio` | Process audio | FormData | JSON |
| GET | `/check-ffmpeg` | Check FFmpeg | - | JSON |
| GET | `/uploads/<filename>` | Serve file | filename | File |
| POST | `/generate-tts` | Generate TTS audio | JSON | JSON |

## Data Flow

```
User Input (Audio + Topic + Language)
    ↓
[Frontend Validation]
    ↓
POST /process-audio
    ↓
[Backend Validation]
    ↓
[Save Audio File] → AudioService
    ↓
[Transcribe Audio] → AIService
    ├─→ [API Transcription] (if available)
    └─→ [Local Whisper] (fallback)
        ├─→ [Get Model from Cache] (WhisperModelCache)
        │   └─→ [Load Model] (if not cached, then cache it)
        ├─→ [Transcribe] (CPU-intensive)
        └─→ [Post-process] (Vietnamese)
    ↓
[Transcript Text]
    ↓
[Summarize] → AIService
    ├─→ [Single Chunk] (if short)
    └─→ [Chunked] (if long)
        ├─→ [Split Text]
        ├─→ [Summarize Chunks]
        └─→ [Combine Summaries]
    ↓
[Summary Text]
    ↓
[Store in ChromaDB] → ChromaDBService
    ├─→ [Generate UUID]
    ├─→ [Combine transcript + summary]
    ├─→ [Create metadata]
    └─→ [Save to ChromaDB]
    ↓
[Return JSON Response] (với transcript_id)
    ↓
[Frontend Display]
    ↓
[User clicks TTS button]
    ↓
[POST /generate-tts] → TTSService
    ├─→ [Call HuggingFace API]
    ├─→ [Receive audio bytes]
    ├─→ [Save to WAV file]
    └─→ [Return audio URL]
    ↓
[Frontend Play Audio]
```

## Logging và Debugging

App sử dụng Python `logging` module và `print()` statements. Các log points:
- **Initialization**: Server start, service initialization, model preloading
- **File Operations**: File save, file size, file path
- **Transcription**: 
  - API attempts và fallback
  - Model loading (from cache hoặc fresh load)
  - Estimated và actual processing time
  - Progress updates
- **Summarization**: Chunk splitting, API calls, completion time
- **Error Handling**: Detailed error messages với context

Log format: `[MODULE] Message` để dễ theo dõi

## Performance Considerations

### Transcription
- Local Whisper: CPU-intensive, có thể chậm
- Model size: medium/large chậm hơn base
- File size: Files lớn cần nhiều thời gian

### Summarization
- API calls: Network latency
- Chunked processing: Multiple API calls
- Token limits: Model context limits

### Memory
- Whisper models: ~1.5GB (medium)
- Large files: Memory usage khi processing
- Chunking: Giảm memory usage

## Troubleshooting

### App treo ở 72%
- Có thể đang load Whisper model (lần đầu)
- Hoặc đang transcribe (CPU-intensive)
- Check logs để xem đang ở bước nào

### FP16 Warning
- Bình thường khi chạy Whisper trên CPU
- Whisper tự động dùng FP32 thay vì FP16

### Memory Issues
- Giảm model size (base thay vì medium)
- Giảm file size trước khi upload
- Close other applications

### Model Loading
- Models được preload khi server start (background thread)
- Lần đầu có thể mất vài giây để download model
- Các lần sau: instant từ cache (< 0.1s)
- Check logs để xem model loading status

### Server Configuration
- **Auto-reloader disabled**: Tắt để tránh lỗi socket khi đang xử lý transcription dài
- **Threaded mode**: Cho phép xử lý nhiều requests đồng thời
- **Warning suppression**: Tắt các warnings không cần thiết (FP16, etc.)
- **Graceful shutdown**: Xử lý tín hiệu shutdown đúng cách

---

# Hướng dẫn Cài đặt và Sử dụng

## Yêu cầu Hệ thống

### Hệ điều hành
- **Windows**: Windows 10/11 hoặc mới hơn
- **Linux**: Ubuntu 18.04+ hoặc các distro tương tự
- **macOS**: macOS 10.14+ hoặc mới hơn

### Phần mềm cần thiết

#### 1. Python
- **Version**: Python 3.8 hoặc mới hơn (khuyến nghị Python 3.10+)
- **Cách kiểm tra**: Mở terminal/cmd và chạy `python --version`
- **Cách cài đặt**:
  - Windows: Download từ [python.org](https://www.python.org/downloads/)
  - Linux: `sudo apt-get install python3 python3-pip` (Ubuntu/Debian)
  - macOS: `brew install python3` hoặc download từ python.org

#### 2. FFmpeg (Bắt buộc)
FFmpeg cần thiết cho Whisper để xử lý audio files.

**Windows:**
1. Download từ: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
2. Giải nén vào thư mục (ví dụ: `C:\ffmpeg`)
3. Thêm vào PATH:
   - Nhấn `Win + X` → chọn "System"
   - Click "Advanced system settings"
   - Click "Environment Variables"
   - Trong "System variables", tìm "Path" → click "Edit"
   - Click "New" → thêm: `C:\ffmpeg\bin`
   - Click "OK" trên tất cả các hộp thoại
4. Khởi động lại terminal/IDE
5. Kiểm tra: `ffmpeg -version`

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Hoặc dùng Chocolatey (Windows):**
```powershell
choco install ffmpeg
```

## Cài đặt Dependencies

### Bước 1: Clone hoặc tải project
```bash
cd C:\Users\PhamDucDuy        \Desktop\Python
```

### Bước 2: Tạo virtual environment (khuyến nghị)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Bước 3: Cài đặt packages
```bash
pip install -r requirements.txt
```

**Dependencies sẽ được cài:**
- `flask>=2.0.0` - Web framework
- `openai>=1.0.0` - OpenAI SDK
- `openai-whisper>=20231117` - Local Whisper transcription
- `chromadb>=0.4.0` - Vector database cho lưu trữ transcripts
- `huggingface_hub>=0.20.0` - HuggingFace Inference API client

**Lưu ý:**
- Whisper sẽ tự động download models khi cần (lần đầu sử dụng)
- Model "medium" (~1.5GB) sẽ được download cho tiếng Việt
- Model "base" (~150MB) sẽ được download cho các ngôn ngữ khác
- Models được lưu trong cache của Whisper (thường ở `~/.cache/whisper/`)

## Cấu hình

### Chỉnh sửa config.py (nếu cần)

Mở file `config.py` và kiểm tra các cấu hình:

```python
# OpenAI API Configuration
OPENAI_BASE_URL = "https://aiportalapi.stu-platform.live/use"
OPENAI_API_KEY = "sk-6gH161QwRXLB0FmOCwxglA"
OPENAI_MODEL_TRANSCRIPTION = "whisper-1"
OPENAI_MODEL_SUMMARY = "GPT-5-mini"
```

**Lưu ý**: 
- Nếu API không hỗ trợ transcription, app sẽ tự động fallback sang local Whisper.
- Để sử dụng TTS, cần set `HF_TOKEN` environment variable hoặc cấu hình trong `config.py`.

## Chạy Ứng dụng

### Bước 1: Khởi động server
```bash
python app.py
```

Hoặc:
```bash
python -m flask run
```

### Bước 2: Mở trình duyệt
Truy cập: `http://127.0.0.1:5000` hoặc `http://localhost:5000`

### Bước 3: Sử dụng ứng dụng

1. **Nhập thông tin:**
   - Meeting Topic: Nhập chủ đề cuộc họp (bắt buộc)
   - Conversation Language: Chọn ngôn ngữ (bắt buộc)

2. **Upload audio:**
   - Click "📁 Or Upload Audio File" để chọn file
   - Hoặc click "🎤 Start Recording" để ghi âm trực tiếp

3. **Xử lý:**
   - Click "📤 Process Audio File" (nếu upload file)
   - Hoặc click "⏹️ Stop Recording" (nếu ghi âm)
   - Đợi quá trình xử lý hoàn tất

4. **Xem kết quả:**
   - Summary sẽ hiển thị sau khi xử lý xong
   - Có thể download audio file đã upload
   - Transcript được tự động lưu vào ChromaDB

5. **Nghe Summary (TTS):**
   - Click nút "🔊 Play Summary (Text-to-Speech)" sau khi processing xong
   - App sẽ generate audio từ summary
   - Click lại để dừng playback

## Lần đầu chạy

Khi chạy lần đầu, bạn sẽ thấy:

1. **Server khởi động:**
   ```
   [AISERVICE] Started preloading common Whisper models in background...
   [WHISPER CACHE] Preloading model 'base' in background...
   [WHISPER CACHE] Preloading model 'medium' in background...
   ```

2. **Models được download:**
   - Lần đầu: Models sẽ được download (~1.5GB cho medium, ~150MB cho base)
   - Có thể mất vài phút tùy vào tốc độ internet
   - Models được cache, không cần download lại

3. **Request đầu tiên:**
   - Nếu model chưa preload xong, sẽ đợi model load
   - Các request sau sẽ nhanh hơn (model đã có trong cache)

## Kiểm tra Logs

Khi chạy app, logs sẽ hiển thị trong terminal:

```
2025-11-16 14:49:34 - __main__ - INFO - Initializing Flask application...
[AISERVICE] Started preloading common Whisper models in background...
[WHISPER CACHE] Preloading model 'base' in background...
[WHISPER CACHE] ✓ Model 'base' loaded and cached in 2.30 seconds
```

**Các log quan trọng:**
- `[AISERVICE]` - AI service operations
- `[WHISPER CACHE]` - Model loading và caching
- `[LOCAL WHISPER]` - Transcription process
- `[SUMMARIZATION]` - Summarization process
- `[AUDIO SERVICE]` - File operations

## Xử lý Lỗi Thường gặp

### Lỗi: "FFmpeg is not installed"
**Giải pháp**: Cài đặt FFmpeg theo hướng dẫn ở trên và khởi động lại terminal.

### Lỗi: "ModuleNotFoundError: No module named 'whisper'"
**Giải pháp**: 
```bash
pip install openai-whisper
```

### Lỗi: "API endpoint not found (404)"
**Giải pháp**: Đây là bình thường. App sẽ tự động fallback sang local Whisper.

### App treo ở 72%
**Giải pháp**: 
- Đây không phải lỗi, app đang transcribe audio (CPU-intensive)
- Với file 6MB, có thể mất 8-10 phút
- Check logs để xem progress: `[LOCAL WHISPER] Transcription started - processing audio...`
- UI progress bar là simulated, không phản ánh thực tế
- Đợi cho đến khi thấy log: `[LOCAL WHISPER] ✓ Transcription completed`

### Lỗi: "OSError: [WinError 10038] An operation was attempted on something that is not a socket"
**Giải pháp**: 
- Đã được fix bằng cách tắt auto-reloader (`use_reloader=False`)
- Lỗi này xảy ra khi Flask cố reload code trong khi đang xử lý request
- Không chỉnh sửa code trong khi đang xử lý transcription

### Memory Issues
**Giải pháp**:
- Đóng các ứng dụng khác
- Giảm model size (sửa code để dùng "base" thay vì "medium")
- Giảm file size trước khi upload

## Tối ưu Performance

### Cho tốc độ nhanh nhất:
1. **Sử dụng model "base"** thay vì "medium" (sửa trong code)
2. **Giảm file size** trước khi upload (< 5MB)
3. **Đảm bảo FFmpeg đã cài** để tránh lỗi
4. **Để models preload** khi server start (đã tự động)

### Cho độ chính xác cao nhất (tiếng Việt):
1. **Giữ model "medium"** (mặc định cho tiếng Việt)
2. **File audio chất lượng tốt** (rõ ràng, ít noise)
3. **Chọn đúng ngôn ngữ** trong form

## Cấu trúc Thư mục sau khi chạy

```
Python/
├── uploads/                    # Files audio đã upload
│   ├── recording_*.mp3
│   └── tts_*.wav              # TTS audio files
├── chroma_db/                  # ChromaDB database (tự động tạo)
│   └── chroma.sqlite3         # Database file
├── __pycache__/               # Python cache files
└── .cache/                    # Whisper model cache (tự động tạo)
    └── whisper/
        ├── base.pt            # Model base (~150MB)
        └── medium.pt          # Model medium (~1.5GB)
```

## Hỗ trợ

Nếu gặp vấn đề:
1. Check logs trong terminal
2. Kiểm tra FFmpeg đã cài đúng chưa: `ffmpeg -version`
3. Kiểm tra Python version: `python --version`
4. Kiểm tra dependencies: `pip list`
5. Xem phần Troubleshooting ở trên
