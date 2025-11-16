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
│   └── ai_service.py              # AI transcription & summarization
├── utils/
│   ├── prompt_builder.py          # Tạo prompts cho AI
│   ├── text_chunker.py            # Chia nhỏ text dài
│   ├── vietnamese_postprocessor.py # Post-processing cho tiếng Việt
│   ├── message_manager.py         # Quản lý conversation history
│   ├── function_calling.py        # Function calling cho OpenAI
│   └── batch_processor.py         # Batch processing
└── uploads/                       # Thư mục lưu files
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
5. **Response**: Trả về JSON với summary và download URL

**Output:**
```json
{
  "summary": "Meeting summary text...",
  "download_url": "/uploads/recording_xxx.mp3"
}
```

#### Route: `/check-ffmpeg` (GET)
- Kiểm tra FFmpeg có sẵn không
- Trả về JSON với status

#### Route: `/uploads/<filename>` (GET)
- Serve static files từ thư mục uploads

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
   - Load Whisper model (base/medium/large)
   - Model selection:
     - Vietnamese: "medium" (better accuracy)
     - Other languages: "base" (balance speed/accuracy)
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
- Load Whisper model
- Transcribe audio
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

### 6. Utility Modules

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

### Optional
- FFmpeg: Cho compression và splitting (required cho files lớn)

## API Endpoints Summary

| Method | Endpoint | Description | Input | Output |
|--------|----------|-------------|-------|--------|
| GET | `/` | Home page | - | HTML |
| POST | `/process-audio` | Process audio | FormData | JSON |
| GET | `/check-ffmpeg` | Check FFmpeg | - | JSON |
| GET | `/uploads/<filename>` | Serve file | filename | File |

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
        ├─→ [Load Model]
        ├─→ [Transcribe]
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
[Return JSON Response]
    ↓
[Frontend Display]
```

## Logging và Debugging

App sử dụng `print()` statements để logging. Các log points:
- File save operations
- Transcription start/completion
- Model loading
- Chunk processing
- Summarization steps
- Error messages

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
