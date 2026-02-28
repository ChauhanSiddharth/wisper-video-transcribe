# ─────────────────────────────────────────────
# Stage 1 – dependency install (cached layer)
# ─────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /build

# System packages: ffmpeg + build tools for some Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the Whisper base model so it is baked into the image
# and users don't experience a delay on first request.
RUN python - <<'EOF'
from faster_whisper import WhisperModel
import os
model_name = os.getenv("WHISPER_MODEL", "base")
print(f"Pre-downloading Whisper model: {model_name}")
WhisperModel(model_name, device="cpu", compute_type="int8")
print("Model downloaded and cached.")
EOF

# ─────────────────────────────────────────────
# Stage 2 – runtime image
# ─────────────────────────────────────────────
FROM python:3.12-slim

# Re-install only the runtime system dependency (ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from build stage
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy cached Whisper model (stored in ~/.cache/huggingface inside build stage)
COPY --from=deps /root/.cache /root/.cache

# Copy application source
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY start.sh ./start.sh

RUN chmod +x start.sh

# ── Environment defaults (override via Railway env vars) ─────────────────────
ENV WHISPER_MODEL=base \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8 \
    MAX_FILE_SIZE_MB=500 \
    BACKEND_URL=http://localhost:8000 \
    # PORT is set by Railway automatically; default to 8501 for local Docker
    PORT=8501

# Expose both internal ports so docker-compose or local testing can reach them
EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["./start.sh"]
