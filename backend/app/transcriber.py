"""
Transcription pipeline: audio extraction via ffmpeg + transcription via faster-whisper.
"""
import os
import subprocess
import tempfile
import logging
from typing import Any, Optional

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model singleton
# ---------------------------------------------------------------------------

_model: Optional[WhisperModel] = None


def get_model() -> WhisperModel:
    """Return a cached WhisperModel, creating it on first call."""
    global _model
    if _model is None:
        model_size = os.getenv("WHISPER_MODEL", "base")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        logger.info("Loading Whisper model '%s' on %s (%s)…", model_size, device, compute_type)
        _model = WhisperModel(model_size, device=device, compute_type=compute_type)
        logger.info("Whisper model ready.")
    return _model


# ---------------------------------------------------------------------------
# Audio extraction
# ---------------------------------------------------------------------------

def extract_audio(video_path: str, audio_path: str) -> None:
    """
    Extract a 16 kHz mono WAV track from *video_path* and write it to
    *audio_path* using ffmpeg.

    Raises:
        RuntimeError: if ffmpeg exits with a non-zero return code or produces
                      an empty file.
    """
    cmd = [
        "ffmpeg",
        "-y",                   # overwrite without asking
        "-i", video_path,
        "-vn",                  # drop video stream
        "-acodec", "pcm_s16le", # PCM 16-bit little-endian
        "-ar", "16000",         # 16 kHz — optimal for Whisper
        "-ac", "1",             # mono
        audio_path,
    ]

    logger.info("Extracting audio: %s → %s", video_path, audio_path)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10-minute hard cap
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (code {result.returncode}):\n{result.stderr}")

    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        raise RuntimeError("ffmpeg produced an empty audio file — the video may have no audio track.")


# ---------------------------------------------------------------------------
# SRT helpers
# ---------------------------------------------------------------------------

def _fmt_srt_time(seconds: float) -> str:
    """Convert a float number of seconds to ``HH:MM:SS,mmm`` SRT format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(segments: list[dict[str, Any]]) -> str:
    """Build an SRT file string from a list of segment dicts."""
    blocks: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = _fmt_srt_time(seg["start"])
        end = _fmt_srt_time(seg["end"])
        text = seg["text"].strip()
        blocks.append(f"{i}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def transcribe_video(video_path: str, language: Optional[str] = None) -> dict[str, Any]:
    """
    Full pipeline: extract audio from *video_path*, transcribe with Whisper,
    and return a result dict containing:

    - ``language``             – detected (or forced) ISO language code
    - ``language_probability`` – confidence in 0-1
    - ``duration``             – total audio duration in seconds
    - ``full_text``            – all segment text joined with newlines
    - ``segments``             – list of {id, start, end, text}
    - ``srt``                  – complete SRT file content
    """
    model = get_model()

    # Use a named temp file so ffmpeg can open it by path.
    tmp_audio_fd, audio_path = tempfile.mkstemp(suffix=".wav")
    os.close(tmp_audio_fd)  # ffmpeg will (re-)open the path itself

    try:
        extract_audio(video_path, audio_path)

        logger.info("Transcribing %s (language=%s)…", audio_path, language or "auto")
        segments_iter, info = model.transcribe(
            audio_path,
            language=language or None,  # None → auto-detect
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            word_timestamps=False,
        )

        segments: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for seg in segments_iter:
            entry = {
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
            }
            segments.append(entry)
            text_parts.append(seg.text.strip())

        full_text = "\n".join(text_parts)
        srt_content = generate_srt(segments)

        logger.info(
            "Transcription complete: %d segments, lang=%s (%.1f%%)",
            len(segments),
            info.language,
            info.language_probability * 100,
        )

        return {
            "language": info.language,
            "language_probability": round(info.language_probability, 4),
            "duration": round(info.duration, 2),
            "full_text": full_text,
            "segments": segments,
            "srt": srt_content,
        }

    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
            logger.debug("Deleted temp audio: %s", audio_path)
