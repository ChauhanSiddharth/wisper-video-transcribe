#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start.sh — launch FastAPI backend + Streamlit frontend in one container
# ---------------------------------------------------------------------------
set -euo pipefail

BACKEND_PORT=8000
FRONTEND_PORT="${PORT:-8501}"

echo "=== Whisper Transcription Service ==="
echo "Backend  → http://0.0.0.0:${BACKEND_PORT}"
echo "Frontend → http://0.0.0.0:${FRONTEND_PORT}"
echo "======================================"

# ── Start FastAPI backend ────────────────────────────────────────────────────
uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "${BACKEND_PORT}" \
    --workers 1 \
    --log-level info &

BACKEND_PID=$!

# Ensure backend is cleaned up when this script exits
cleanup() {
    echo "Shutting down backend (PID ${BACKEND_PID})…"
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
    echo "Shutdown complete."
}
trap cleanup EXIT INT TERM

# ── Wait for backend to accept connections ───────────────────────────────────
echo "Waiting for backend to become ready…"
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${BACKEND_PORT}/health" > /dev/null 2>&1; then
        echo "Backend is ready (after ${i}s)."
        break
    fi
    if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
        echo "ERROR: Backend process exited unexpectedly." >&2
        exit 1
    fi
    sleep 1
done

# ── Start Streamlit frontend (foreground — container lifetime tied to this) ───
exec streamlit run frontend/streamlit_app.py \
    --server.port "${FRONTEND_PORT}" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.maxUploadSize "${MAX_FILE_SIZE_MB:-500}" \
    --server.enableCORS false \
    --server.enableXsrfProtection false
