"""
Streamlit frontend for the Whisper Transcription API.
"""
import json
import os
from pathlib import Path

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "500"))
REQUEST_TIMEOUT: int = 600  # seconds

LANGUAGE_OPTIONS: dict[str, str] = {
    "Auto-detect": "",
    "English": "en",
    "Gujarati": "gu",
    "Hindi": "hi",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Portuguese": "pt",
    "Italian": "it",
    "Chinese": "zh",
    "Japanese": "ja",
    "Korean": "ko",
    "Arabic": "ar",
    "Russian": "ru",
}

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Whisper Video Transcriber",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚙️ Settings")
    st.markdown("---")

    selected_language = st.selectbox(
        "Transcription language",
        options=list(LANGUAGE_OPTIONS.keys()),
        index=0,
        help="Choose a language or leave on Auto-detect.",
    )
    language_code: str = LANGUAGE_OPTIONS[selected_language]

    st.markdown("---")
    st.markdown("**Supported formats:** `.mp4`, `.mov`, `.mkv`")
    st.markdown(f"**Max upload size:** {MAX_FILE_SIZE_MB} MB")
    st.markdown("---")
    st.caption("Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper)")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🎙️ Whisper Video Transcriber")
st.markdown(
    "Upload a video file to get a full transcript — with timestamps, "
    "downloadable SRT, and JSON output. 90+ languages supported."
)
st.markdown("---")

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

uploaded_file = st.file_uploader(
    "Drop your video here",
    type=["mp4", "mov", "mkv"],
    help=f"Max {MAX_FILE_SIZE_MB} MB. Supported: mp4, mov, mkv.",
)

if uploaded_file is not None:
    file_mb = uploaded_file.size / (1024 * 1024)
    st.info(f"**{uploaded_file.name}** — {file_mb:.1f} MB selected")

    if file_mb > MAX_FILE_SIZE_MB:
        st.error(f"File exceeds the {MAX_FILE_SIZE_MB} MB limit. Please upload a smaller file.")
        st.stop()

    transcribe_btn = st.button(
        "▶ Transcribe",
        type="primary",
        use_container_width=True,
    )

    if transcribe_btn:
        progress = st.progress(0, text="Uploading file…")

        try:
            # ── POST to backend ────────────────────────────────────────────
            progress.progress(10, text="Sending to transcription service…")

            files_payload = {
                "file": (uploaded_file.name, uploaded_file, "video/mp4"),
            }
            data_payload: dict = {}
            if language_code:
                data_payload["language"] = language_code

            with st.spinner("Transcribing — this may take a few minutes for long videos…"):
                response = requests.post(
                    f"{BACKEND_URL}/transcribe",
                    files=files_payload,
                    data=data_payload,
                    timeout=REQUEST_TIMEOUT,
                )

            progress.progress(90, text="Processing results…")

            # ── Handle response ────────────────────────────────────────────
            if response.status_code == 200:
                result: dict = response.json()
                progress.progress(100, text="Done!")

                st.success("Transcription complete!")
                st.markdown("---")

                # ── Summary metrics ────────────────────────────────────────
                col1, col2, col3, col4 = st.columns(4)
                duration = result.get("duration", 0)
                col1.metric("Language", result.get("language", "?").upper())
                col2.metric(
                    "Confidence",
                    f"{result.get('language_probability', 0) * 100:.1f}%",
                )
                col3.metric(
                    "Duration",
                    f"{int(duration // 60)}m {int(duration % 60)}s",
                )
                col4.metric("Segments", len(result.get("segments", [])))

                st.markdown("---")

                # ── Tabs ───────────────────────────────────────────────────
                tab_text, tab_segments, tab_dl = st.tabs(
                    ["📄 Full Transcript", "⏱️ Segments", "⬇️ Downloads"]
                )

                with tab_text:
                    full_text: str = result.get("full_text", "")
                    if full_text:
                        st.text_area(
                            "Transcript",
                            value=full_text,
                            height=420,
                            label_visibility="collapsed",
                        )
                    else:
                        st.info("No speech detected in the video.")

                with tab_segments:
                    segments: list[dict] = result.get("segments", [])
                    if segments:
                        for seg in segments:
                            s, e = seg["start"], seg["end"]

                            def _fmt(t: float) -> str:
                                return f"{int(t // 60):02d}:{t % 60:05.2f}"

                            c_time, c_text = st.columns([1, 4])
                            c_time.caption(f"[{_fmt(s)} → {_fmt(e)}]")
                            c_text.write(seg["text"])
                    else:
                        st.info("No segments available.")

                with tab_dl:
                    st.markdown("### Download output files")
                    stem = Path(uploaded_file.name).stem
                    dl_col1, dl_col2 = st.columns(2)

                    with dl_col1:
                        srt_bytes = result.get("srt", "").encode("utf-8")
                        st.download_button(
                            label="⬇️ Download SRT",
                            data=srt_bytes,
                            file_name=f"{stem}.srt",
                            mime="text/plain",
                            use_container_width=True,
                        )
                        st.caption("Standard subtitle file compatible with most video players.")

                    with dl_col2:
                        json_bytes = json.dumps(
                            result, ensure_ascii=False, indent=2
                        ).encode("utf-8")
                        st.download_button(
                            label="⬇️ Download JSON",
                            data=json_bytes,
                            file_name=f"{stem}.json",
                            mime="application/json",
                            use_container_width=True,
                        )
                        st.caption("Full JSON with segments, timestamps, and metadata.")

            # ── Error responses ────────────────────────────────────────────
            elif response.status_code == 413:
                progress.empty()
                st.error(f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB.")
            elif response.status_code in (400, 422):
                progress.empty()
                detail = response.json().get("detail", "Invalid request.")
                st.error(f"Request error: {detail}")
            else:
                progress.empty()
                try:
                    detail = response.json().get("detail", "Unknown error.")
                except Exception:
                    detail = response.text or "Unknown error."
                st.error(f"Server error ({response.status_code}): {detail}")

        except requests.exceptions.ConnectionError:
            progress.empty()
            st.error(
                "Cannot reach the backend. "
                f"Make sure the API is running at `{BACKEND_URL}`."
            )
        except requests.exceptions.Timeout:
            progress.empty()
            st.error(
                "The request timed out. "
                "The video may be too long — try a shorter clip."
            )
        except Exception as exc:
            progress.empty()
            st.error(f"Unexpected error: {exc}")

else:
    # Placeholder when no file is selected
    st.markdown(
        """
        <div style="
            border: 2px dashed #555;
            border-radius: 12px;
            padding: 48px;
            text-align: center;
            color: #888;
        ">
            <h3>Upload a video to get started</h3>
            <p>Supports mp4 · mov · mkv &nbsp;|&nbsp; Up to {max_mb} MB</p>
        </div>
        """.format(max_mb=MAX_FILE_SIZE_MB),
        unsafe_allow_html=True,
    )
