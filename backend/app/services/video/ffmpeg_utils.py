import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path


class FFmpegExecutionError(RuntimeError):
    """Raised when FFmpeg or FFprobe cannot process local media."""


def run_ffmpeg(command: list[str], timeout: int = 600) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise FFmpegExecutionError("FFmpeg is not installed on the backend.") from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegExecutionError("FFmpeg timed out while processing media.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        message = detail[-1] if detail else "FFmpeg could not process the media."
        raise FFmpegExecutionError(message) from exc


def probe_media(path: Path) -> tuple[set[str], float | None]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise FFmpegExecutionError("FFprobe is not installed on the backend.") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise FFmpegExecutionError("The uploaded file is not readable media.") from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FFmpegExecutionError("FFprobe returned invalid media information.") from exc

    streams = payload.get("streams", [])
    stream_types = {
        stream.get("codec_type")
        for stream in streams
        if stream.get("codec_type") in {"audio", "video"}
    }

    duration_values = [payload.get("format", {}).get("duration")]
    duration_values.extend(stream.get("duration") for stream in streams)
    duration = next(
        (
            parsed
            for value in duration_values
            if value not in {None, "N/A"}
            and (parsed := _positive_float(value)) is not None
        ),
        None,
    )
    return stream_types, duration


def probe_duration(path: Path) -> float:
    _, duration = probe_media(path)
    if duration is None:
        raise FFmpegExecutionError("The media duration could not be determined.")
    return duration


@lru_cache(maxsize=None)
def ffmpeg_has_filter(filter_name: str) -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False

    return re.search(rf"\b{re.escape(filter_name)}\b", result.stdout) is not None


def escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _positive_float(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
