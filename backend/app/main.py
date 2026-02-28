"""
FastAPI backend for video transcription.

Endpoints:
    GET  /health      – liveness probe
    POST /transcribe  – upload a video file, receive transcript data
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .transcriber import transcribe_video

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App & config
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Whisper Transcription API",
    description="Upload a video and receive a full transcript powered by faster-whisper.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_FILE_SIZE_MB", "500")) * 1024 * 1024
ALLOWED_SUFFIXES: frozenset[str] = frozenset({".mp4", ".mov", ".mkv"})
CHUNK_SIZE: int = 1024 * 1024  # 1 MB read chunks


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"])
async def health() -> dict:
    """Return a simple liveness response."""
    return {"status": "healthy"}


@app.post("/transcribe", tags=["transcription"])
async def transcribe(
    file: UploadFile = File(..., description="Video file (mp4 / mov / mkv)"),
    language: Optional[str] = Form(
        None,
        description="ISO-639-1 language code (e.g. 'en', 'gu', 'hi'). "
                    "Leave blank to auto-detect.",
    ),
) -> JSONResponse:
    """
    Transcribe a video file.

    - Validates extension and size (≤ 500 MB by default).
    - Extracts audio with ffmpeg.
    - Transcribes with faster-whisper.
    - Returns full text, timestamped segments, and SRT content.
    - All temporary files are deleted after processing.
    """
    # ── Validate extension ──────────────────────────────────────────────────
    original_name: str = file.filename or "upload"
    suffix: str = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}"
            ),
        )

    # ── Normalise language ──────────────────────────────────────────────────
    lang: Optional[str] = (language or "").strip() or None

    # ── Stream upload to temp file ──────────────────────────────────────────
    tmp_video_fd, tmp_video_path = tempfile.mkstemp(suffix=suffix)
    os.close(tmp_video_fd)

    try:
        total_bytes = 0
        async with aiofiles.open(tmp_video_path, "wb") as out:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
                        ),
                    )
                await out.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        logger.info(
            "Received '%s' — %.1f MB", original_name, total_bytes / (1024 * 1024)
        )

        # ── Transcribe (runs in thread pool to avoid blocking the event loop) ──
        result: dict = await asyncio.to_thread(transcribe_video, tmp_video_path, lang)

        result["filename"] = original_name
        result["file_size_mb"] = round(total_bytes / (1024 * 1024), 2)

        return JSONResponse(content=result)

    except HTTPException:
        raise  # re-raise FastAPI errors as-is

    except RuntimeError as exc:
        logger.error("Transcription runtime error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))

    except Exception as exc:
        logger.exception("Unexpected error during transcription")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please check server logs.",
        ) from exc

    finally:
        # Always remove the uploaded video temp file
        if os.path.exists(tmp_video_path):
            os.unlink(tmp_video_path)
            logger.debug("Deleted temp video: %s", tmp_video_path)
