import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def get_data_dir() -> Path:
    configured = os.getenv("DATA_DIR", "").strip()
    if not configured:
        return BACKEND_DIR
    data_dir = Path(configured).expanduser()
    if not data_dir.is_absolute():
        data_dir = BACKEND_DIR / data_dir
    return data_dir.resolve()


def get_uploads_dir() -> Path:
    return get_data_dir() / "uploads"


def get_audio_dir() -> Path:
    return get_data_dir() / "outputs" / "audio"


def get_video_dir() -> Path:
    return get_data_dir() / "outputs" / "video"


def get_jobs_dir() -> Path:
    return get_data_dir() / "jobs"


def get_model_cache_dir() -> Path:
    return get_data_dir() / "models"


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "").strip()
    if not configured:
        return list(DEFAULT_CORS_ORIGINS)

    origins = []
    for value in configured.split(","):
        origin = value.strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)
    return origins or list(DEFAULT_CORS_ORIGINS)


def resolve_voice_reference_path() -> Path:
    configured = os.getenv("VOICE_REFERENCE_PATH", "private/my_voice.wav").strip()
    reference_path = Path(configured or "private/my_voice.wav").expanduser()
    if not reference_path.is_absolute():
        reference_path = get_data_dir() / reference_path
    return reference_path.resolve()
