# 🎙️ Whisper Video Transcriber

A production-ready video transcription web app powered by OpenAI's Whisper model. Upload any video file and get a full transcript with timestamps, downloadable SRT subtitles, and JSON output — all in your browser.

Supports **90+ languages** with automatic language detection.

---

## ✨ Features

- 🎬 **Video upload** — supports `.mp4`, `.mov`, `.mkv` (up to 500 MB)
- 🔊 **Audio extraction** — powered by ffmpeg
- 🤖 **AI transcription** — powered by faster-whisper (base model)
- 🌍 **90+ languages** — auto-detects language or let you pick manually
- ⏱️ **Timestamped segments** — view exactly when each word was spoken
- 📄 **Download SRT** — standard subtitle file for any video player
- 📦 **Download JSON** — full structured output with metadata
- 🧹 **Zero persistence** — temp files deleted immediately after processing
- ⚡ **Async processing** — non-blocking transcription pipeline
- 🐳 **Docker ready** — single container runs both frontend and backend
- 🚀 **Railway ready** — deploy in minutes

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Backend | FastAPI |
| Frontend | Streamlit |
| Transcription | faster-whisper (Whisper base model) |
| Audio extraction | ffmpeg |
| Async server | Uvicorn |
| Containerisation | Docker (multi-stage build) |
| Deployment | Railway |

---

## 📁 Project Structure

```
whisper-transcript/
├── backend/
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py             # FastAPI app — /health & /transcribe endpoints
│       └── transcriber.py      # ffmpeg audio extraction + Whisper pipeline
├── frontend/
│   └── streamlit_app.py        # Streamlit UI — upload, results, downloads
├── Dockerfile                  # Multi-stage build, pre-bakes Whisper model
├── docker-compose.yml          # Local development
├── railway.toml                # Railway deployment config
├── start.sh                    # Starts backend + frontend in one container
├── requirements.txt
├── .env.example                # Environment variable reference
├── .gitattributes
└── .dockerignore
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `base` | Model size: `tiny` / `base` / `small` / `medium` / `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` (GPU) |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8` (fast) / `float16` (GPU) / `float32` (accurate) |
| `MAX_FILE_SIZE_MB` | `500` | Maximum upload size in MB |
| `BACKEND_URL` | `http://localhost:8000` | URL Streamlit uses to reach FastAPI |
| `PORT` | `8501` | Streamlit listen port (set automatically by Railway) |

---

## 🚀 Running the App

### Option 1 — Docker Compose (Recommended)

```bash
# Clone the repo
git clone https://github.com/ChauhanSiddharth/wisper-video-transcribe.git
cd wisper-video-transcribe

# Build and start
docker compose up --build
```

| Service | URL |
|---|---|
| Streamlit UI | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |

> First build takes a few minutes — it downloads the Whisper model and bakes it into the image.

---

### Option 2 — Run Locally (without Docker)

**Prerequisites:** Python 3.12+, ffmpeg installed on your system

```bash
# Clone the repo
git clone https://github.com/ChauhanSiddharth/wisper-video-transcribe.git
cd wisper-video-transcribe

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI backend (terminal 1)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Streamlit frontend (terminal 2)
streamlit run frontend/streamlit_app.py --server.port 8501
```

Open http://localhost:8501 in your browser.

---

## ☁️ Deploy to Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
3. Select your repository — Railway auto-detects the `Dockerfile`
4. Under **Settings → Networking**, click **Generate Domain** and set port to **`8501`**
5. Under the **Variables** tab, add:

```
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_FILE_SIZE_MB=500
BACKEND_URL=http://localhost:8000
```

Every `git push` to `main` triggers an automatic redeploy.

---

## 🔄 How It Works

```
User uploads video
       │
       ▼
FastAPI receives file (streamed in 1 MB chunks)
       │
       ▼
ffmpeg extracts 16 kHz mono WAV audio
       │
       ▼
faster-whisper transcribes audio (async, thread pool)
       │
       ▼
Segments collected → full text + SRT generated
       │
       ▼
Temp files deleted → JSON response returned
       │
       ▼
Streamlit displays transcript, segments, download buttons
```

---

## 📤 API Reference

### `GET /health`
Returns service status.

```json
{ "status": "healthy" }
```

### `POST /transcribe`
**Form fields:**
- `file` — video file (mp4 / mov / mkv)
- `language` *(optional)* — ISO 639-1 code e.g. `en`, `hi`, `fr`. Leave blank for auto-detect.

**Response:**
```json
{
  "language": "en",
  "language_probability": 0.9987,
  "duration": 142.5,
  "full_text": "Hello, this is the transcript...",
  "segments": [
    { "id": 1, "start": 0.0, "end": 3.2, "text": "Hello, this is the transcript." }
  ],
  "srt": "1\n00:00:00,000 --> 00:00:03,200\nHello, this is the transcript.\n",
  "filename": "my-video.mp4",
  "file_size_mb": 24.3
}
```

---

## 🌍 Supported Languages

Whisper supports **90+ languages** including English, Hindi, Spanish, French, German, Arabic, Chinese, Japanese, Korean, Russian, Portuguese, Italian, Gujarati, Bengali, Punjabi, Urdu, and many more.

Full list: [openai/whisper — supported languages](https://github.com/openai/whisper#available-models-and-languages)

---

## 📋 Requirements

- Docker (for containerised run)
- **or** Python 3.12+ and ffmpeg (for local run)
- 2 GB RAM minimum (base model)
- Internet connection on first run (to download Whisper model, unless using Docker image)

---

## 📄 License

MIT
