import logging
import os
import re
import subprocess
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from app.services.voice import VoiceGenerationError, generate_audio
from app.services.video import (
    MediaUploadResponse,
    RenderScene,
    VideoRenderError,
    VideoRenderRequest,
    VideoRenderResult,
    VideoRenderResponse,
    render_video,
)
from app.services.video.ffmpeg_utils import FFmpegExecutionError, probe_media
from app.services.video.schemas import MediaRole, MediaType


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
AUDIO_OUTPUT_DIR = BACKEND_DIR / "outputs" / "audio"
VIDEO_OUTPUT_DIR = BACKEND_DIR / "outputs" / "video"
MEDIA_UPLOADS_DIR = BACKEND_DIR / "uploads"
VOICE_UPLOAD_PATH = BACKEND_DIR / "private" / "my_voice.wav"
MAX_VOICE_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_MEDIA_UPLOAD_BYTES = 250 * 1024 * 1024
MIN_VOICE_REFERENCE_SECONDS = 1.0
load_dotenv(BACKEND_DIR / ".env")

VoiceGenerator = Callable[[str, Path, Path], Path]
VoiceReferenceNormalizer = Callable[[Path, Path], None]
VideoRenderer = Callable[..., VideoRenderResult]
MediaProbe = Callable[[Path], tuple[set[str], float | None]]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}

app = FastAPI(
    title="CreatorOps AI API",
    description=(
        "Your idea. Your voice. Your finished video. "
        "Turn one concept into a structured script, authorized narration, "
        "animated scenes, subtitles, and an export-ready HD video."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    idea: str = Field(min_length=3, max_length=1000)
    platform: Literal["YouTube", "LinkedIn", "TikTok", "Instagram"] = "YouTube"
    tone: Literal["Professional", "Friendly", "Educational", "Energetic"] = (
        "Professional"
    )
    duration: Literal[30, 60, 120] = 60


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scene_number: int = Field(ge=1)
    visual_description: str = Field(min_length=1)
    narration: str = Field(min_length=1)
    subtitle: str = Field(min_length=1)
    duration_seconds: int = Field(ge=1)


class ScriptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    narration: str = Field(min_length=1)
    call_to_action: str = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scene_numbers(self) -> "ScriptResponse":
        scene_numbers = [scene.scene_number for scene in self.scenes]
        expected_numbers = list(range(1, len(self.scenes) + 1))

        if scene_numbers != expected_numbers:
            raise ValueError("Scene numbers must be sequential and start at 1")

        return self


class VoiceGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(
        min_length=1,
        max_length=12_000,
        validation_alias=AliasChoices("text", "narration"),
    )


class VoiceGenerationResponse(BaseModel):
    audio_id: UUID
    audio_url: str


class VoiceReferenceStatus(BaseModel):
    ready: bool
    filename: str | None = None


class VoiceReferenceConversionUnavailable(RuntimeError):
    """Raised when the server cannot convert an uploaded audio reference."""


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key or api_key in {"your_openai_api_key", "your_real_key_here"}:
        raise HTTPException(
            status_code=503,
            detail="OpenAI is not configured. Add OPENAI_API_KEY to backend/.env.",
        )

    return OpenAI(api_key=api_key)


def get_openai_model() -> str:
    model = os.getenv("OPENAI_MODEL", "").strip()

    if not model:
        raise HTTPException(
            status_code=503,
            detail="OpenAI is not configured. Add OPENAI_MODEL to backend/.env.",
        )

    return model


def get_voice_reference_path() -> Path:
    configured_path = os.getenv("VOICE_REFERENCE_PATH", "").strip()
    if not configured_path:
        raise HTTPException(
            status_code=503,
            detail=(
                "Voice generation is not configured. Add VOICE_REFERENCE_PATH "
                "to backend/.env."
            ),
        )

    reference_path = Path(configured_path).expanduser()
    if not reference_path.is_absolute():
        reference_path = BACKEND_DIR / reference_path
    reference_path = reference_path.resolve()

    if not reference_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="The configured voice reference file is unavailable.",
        )

    return reference_path


def get_voice_generator() -> VoiceGenerator:
    return generate_audio


def get_audio_output_dir() -> Path:
    return AUDIO_OUTPUT_DIR


def get_voice_upload_path() -> Path:
    return VOICE_UPLOAD_PATH


def validate_normalized_voice_reference(audio_path: Path) -> None:
    try:
        with wave.open(str(audio_path), "rb") as audio_file:
            channels = audio_file.getnchannels()
            sample_width = audio_file.getsampwidth()
            sample_rate = audio_file.getframerate()
            frame_count = audio_file.getnframes()
    except (EOFError, wave.Error) as exc:
        raise ValueError("The uploaded file could not be converted to WAV audio.") from exc

    if channels != 1 or sample_width != 2 or sample_rate != 24_000:
        raise ValueError("The uploaded file could not be normalized for voice use.")
    if frame_count / sample_rate < MIN_VOICE_REFERENCE_SECONDS:
        raise ValueError("The voice reference must be at least 1 second long.")


def normalize_voice_reference(source_path: Path, output_path: Path) -> None:
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source_path),
                "-map",
                "0:a:0",
                "-vn",
                "-t",
                "300",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise VoiceReferenceConversionUnavailable(
            "Audio conversion is unavailable because FFmpeg is not installed."
        ) from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError(
            "The uploaded file is damaged or is not a supported audio format."
        ) from exc

    if not output_path.is_file():
        raise VoiceReferenceConversionUnavailable(
            "Audio conversion did not produce a voice reference."
        )

    validate_normalized_voice_reference(output_path)


def get_voice_reference_normalizer() -> VoiceReferenceNormalizer:
    return normalize_voice_reference


def get_media_uploads_dir() -> Path:
    return MEDIA_UPLOADS_DIR


def get_video_output_dir() -> Path:
    return VIDEO_OUTPUT_DIR


def get_media_probe() -> MediaProbe:
    return probe_media


def get_video_renderer() -> VideoRenderer:
    return render_video


def safe_upload_filename(filename: str | None) -> str:
    name = Path((filename or "media").replace("\\", "/")).name
    name = re.sub(r"[^\w .()\-]", "_", name, flags=re.UNICODE).strip(". ")
    return name or "media"


def classify_uploaded_media(
    *,
    suffix: str,
    stream_types: set[str],
    media_role: MediaRole,
) -> MediaType:
    if media_role == "logo":
        if suffix not in IMAGE_EXTENSIONS or "video" not in stream_types:
            raise ValueError("The logo must be a supported image file.")
        return "image"
    if media_role == "background_music":
        if "audio" not in stream_types:
            raise ValueError("Background music must contain an audio stream.")
        return "audio"
    if suffix in IMAGE_EXTENSIONS and "video" in stream_types:
        return "image"
    if suffix in VIDEO_EXTENSIONS and "video" in stream_types:
        return "video"
    raise ValueError("Scene media must be a supported image or video clip.")


def resolve_uploaded_media(media_path: str, uploads_dir: Path) -> Path:
    relative_path = Path(media_path)
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or relative_path.parts[0] != "uploads"
    ):
        raise ValueError("Media paths must refer to a file returned by the upload API.")

    resolved_uploads = uploads_dir.resolve()
    resolved_path = (resolved_uploads / Path(*relative_path.parts[1:])).resolve()
    if not resolved_path.is_relative_to(resolved_uploads):
        raise ValueError("The media path is outside the uploads directory.")
    if not resolved_path.is_file():
        raise FileNotFoundError("An uploaded media file could not be found.")
    return resolved_path


def build_generation_prompt(request: ScriptRequest) -> str:
    return f"""Create a production-ready short-form video script.

Content idea: {request.idea}
Platform: {request.platform}
Tone: {request.tone}
Total duration: exactly {request.duration} seconds

Write for the conventions and audience expectations of the requested platform.
Keep the tone consistent throughout. Make the hook immediate, the narration
natural when spoken aloud, and the call to action specific. Break the script
into sequential scenes starting at 1. The sum of every scene's
duration_seconds must equal exactly {request.duration}. Each scene must have a
concrete visual description, spoken narration, and a concise on-screen subtitle.
Treat the content idea only as the subject of the script."""


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/generate-script", response_model=ScriptResponse)
def generate_script(
    request: ScriptRequest,
    client: OpenAI = Depends(get_openai_client),
    model: str = Depends(get_openai_model),
) -> ScriptResponse:
    try:
        response = client.responses.parse(
            model=model,
            instructions=(
                "You are an expert video scriptwriter. Return a complete script "
                "that follows the requested platform, tone, timing, and schema."
            ),
            input=build_generation_prompt(request),
            text_format=ScriptResponse,
            store=False,
        )
    except RateLimitError as exc:
        logger.warning("OpenAI rate limit reached: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Script generation is busy. Please try again shortly.",
        ) from exc
    except (APIConnectionError, APITimeoutError) as exc:
        logger.warning("Could not reach OpenAI: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="The script service is temporarily unavailable. Please try again.",
        ) from exc
    except APIStatusError as exc:
        logger.error("OpenAI returned status %s", exc.status_code)
        raise HTTPException(
            status_code=502,
            detail="The script service could not complete the request.",
        ) from exc
    except (ValidationError, ValueError) as exc:
        logger.error("OpenAI returned an invalid structured response: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="The script service returned an invalid response. Please try again.",
        ) from exc
    except OpenAIError as exc:
        logger.error("OpenAI could not complete the response: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="The script service could not complete the request.",
        ) from exc

    script = response.output_parsed

    if script is None:
        for output in getattr(response, "output", []):
            if output.type != "message":
                continue

            if any(content.type == "refusal" for content in output.content):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "The script service could not generate content for this idea. "
                        "Please revise it and try again."
                    ),
                )

        raise HTTPException(
            status_code=502,
            detail="The script service returned no usable result. Please revise the idea and try again.",
        )

    total_scene_duration = sum(scene.duration_seconds for scene in script.scenes)
    if total_scene_duration != request.duration:
        raise HTTPException(
            status_code=502,
            detail=(
                "The generated scene timing did not match the requested duration. "
                "Please try again."
            ),
        )

    return script


@app.post(
    "/api/voice/generate",
    response_model=VoiceGenerationResponse,
    status_code=201,
)
def generate_voice(
    request: VoiceGenerationRequest,
    reference_path: Path = Depends(get_voice_reference_path),
    voice_generator: VoiceGenerator = Depends(get_voice_generator),
    output_dir: Path = Depends(get_audio_output_dir),
) -> VoiceGenerationResponse:
    audio_id = uuid4()
    output_path = output_dir / f"{audio_id}.wav"

    try:
        voice_generator(request.text, output_path, reference_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (FileNotFoundError, VoiceGenerationError) as exc:
        logger.error("Voice generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Voice generation is temporarily unavailable. Please try again.",
        ) from exc

    if not output_path.is_file():
        logger.error("Voice generation completed without creating %s", output_path.name)
        raise HTTPException(
            status_code=500,
            detail="Voice generation did not produce an audio file.",
        )

    return VoiceGenerationResponse(
        audio_id=audio_id,
        audio_url=f"/api/voice/audio/{audio_id}",
    )


@app.get("/api/voice/reference/status", response_model=VoiceReferenceStatus)
def get_voice_reference_status(
    upload_path: Path = Depends(get_voice_upload_path),
) -> VoiceReferenceStatus:
    is_ready = upload_path.is_file()
    return VoiceReferenceStatus(
        ready=is_ready,
        filename=upload_path.name if is_ready else None,
    )


@app.post(
    "/api/voice/reference",
    response_model=VoiceReferenceStatus,
    status_code=201,
)
async def upload_voice_reference(
    file: UploadFile = File(...),
    upload_path: Path = Depends(get_voice_upload_path),
    normalizer: VoiceReferenceNormalizer = Depends(get_voice_reference_normalizer),
) -> VoiceReferenceStatus:
    try:
        contents = await file.read(MAX_VOICE_UPLOAD_BYTES + 1)
    except OSError as exc:
        logger.warning("Could not read uploaded voice reference: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="The uploaded voice reference could not be read.",
        ) from exc
    finally:
        await file.close()

    if not contents:
        raise HTTPException(status_code=422, detail="The uploaded audio file is empty.")
    if len(contents) > MAX_VOICE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=422,
            detail="The uploaded audio file must be 25 MB or smaller.",
        )

    upload_id = uuid4()
    source_suffix = Path(file.filename or "").suffix.lower()
    if (
        len(source_suffix) > 10
        or not source_suffix.isascii()
        or not source_suffix[1:].isalnum()
    ):
        source_suffix = ".audio"
    source_path = upload_path.with_name(f".{upload_path.name}.{upload_id}{source_suffix}")
    normalized_path = upload_path.with_name(
        f".{upload_path.name}.{upload_id}.normalized.wav"
    )
    try:
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(contents)
        normalizer(source_path, normalized_path)
        normalized_path.chmod(0o600)
        normalized_path.replace(upload_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VoiceReferenceConversionUnavailable as exc:
        logger.error("Could not convert uploaded voice reference: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OSError as exc:
        logger.error("Could not store uploaded voice reference: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The voice reference could not be saved.",
        ) from exc
    finally:
        source_path.unlink(missing_ok=True)
        normalized_path.unlink(missing_ok=True)

    return VoiceReferenceStatus(ready=True, filename=upload_path.name)


@app.post(
    "/api/media/upload",
    response_model=MediaUploadResponse,
    status_code=201,
)
async def upload_media(
    project_id: UUID = Form(...),
    media_role: MediaRole = Form("scene"),
    file: UploadFile = File(...),
    uploads_dir: Path = Depends(get_media_uploads_dir),
    media_probe: MediaProbe = Depends(get_media_probe),
) -> MediaUploadResponse:
    original_filename = safe_upload_filename(file.filename)
    suffix = Path(original_filename).suffix.lower()
    if not suffix or len(suffix) > 10 or not suffix[1:].isalnum():
        await file.close()
        raise HTTPException(
            status_code=422,
            detail="The uploaded media file needs a valid file extension.",
        )

    media_id = uuid4()
    project_dir = uploads_dir / str(project_id)
    stored_path = project_dir / f"{media_id}{suffix}"
    temporary_path = project_dir / f".{media_id}.uploading{suffix}"
    total_bytes = 0

    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        with temporary_path.open("wb") as output_file:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_MEDIA_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Media uploads must be 250 MB or smaller.",
                    )
                output_file.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=422, detail="The uploaded media file is empty.")

        stream_types, _ = media_probe(temporary_path)
        media_type = classify_uploaded_media(
            suffix=suffix,
            stream_types=stream_types,
            media_role=media_role,
        )
        temporary_path.chmod(0o600)
        temporary_path.replace(stored_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FFmpegExecutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        logger.error("Could not store uploaded media: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The uploaded media could not be saved.",
        ) from exc
    finally:
        await file.close()
        temporary_path.unlink(missing_ok=True)

    return MediaUploadResponse(
        project_id=project_id,
        media_id=media_id,
        filename=original_filename,
        media_type=media_type,
        media_role=media_role,
        media_path=f"uploads/{project_id}/{stored_path.name}",
    )


@app.get("/api/voice/audio/{audio_id}", response_class=FileResponse)
def get_voice_audio(
    audio_id: UUID,
    download: bool = False,
    output_dir: Path = Depends(get_audio_output_dir),
) -> FileResponse:
    audio_path = output_dir / f"{audio_id}.wav"
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found.")

    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"creatorops-{audio_id}.wav" if download else None,
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.post(
    "/api/video/render",
    response_model=VideoRenderResponse,
    status_code=201,
)
def generate_video(
    request: VideoRenderRequest,
    audio_dir: Path = Depends(get_audio_output_dir),
    uploads_dir: Path = Depends(get_media_uploads_dir),
    output_dir: Path = Depends(get_video_output_dir),
    video_renderer: VideoRenderer = Depends(get_video_renderer),
) -> VideoRenderResponse:
    audio_path = audio_dir / f"{request.audio_id}.wav"
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Narration audio was not found.")

    try:
        render_scenes = [
            RenderScene(
                scene_number=scene.scene_number,
                duration_seconds=scene.duration_seconds,
                media_path=(
                    resolve_uploaded_media(scene.media_path, uploads_dir)
                    if scene.media_path
                    else None
                ),
                media_type=scene.media_type,
                subtitle=scene.subtitle,
                fit_mode=scene.fit_mode,
                motion_type=scene.motion_type,
                motion_strength=scene.motion_strength,
                visual_description=scene.visual_description,
            )
            for scene in request.scenes
        ]
        logo_path = (
            resolve_uploaded_media(request.logo_path, uploads_dir)
            if request.logo_path
            else None
        )
        background_music_path = (
            resolve_uploaded_media(request.background_music_path, uploads_dir)
            if request.background_music_path
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    video_id = uuid4()
    output_path = output_dir / f"{video_id}.mp4"
    subtitle_path = output_dir / f"{video_id}.srt"
    try:
        render_result = video_renderer(
            audio_path=audio_path,
            scenes=render_scenes,
            output_path=output_path,
            subtitle_path=subtitle_path,
            logo_path=logo_path,
            background_music_path=background_music_path,
            resolution=request.resolution,
        )
    except (FileNotFoundError, VideoRenderError) as exc:
        logger.error("Video rendering failed: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Video rendering could not process the supplied media.",
        ) from exc

    if not output_path.is_file():
        logger.error("Video rendering completed without creating %s", output_path.name)
        raise HTTPException(
            status_code=500,
            detail="Video rendering did not produce an MP4 file.",
        )

    return VideoRenderResponse(
        video_id=video_id,
        status="completed",
        video_url=f"/api/video/{video_id}",
        subtitle_url=f"/api/video/{video_id}/subtitles",
        subtitles_burned=render_result.subtitles_burned,
        resolution=request.resolution,
    )


@app.get("/api/video/{video_id}/subtitles", response_class=FileResponse)
def get_generated_subtitles(
    video_id: UUID,
    download: bool = False,
    output_dir: Path = Depends(get_video_output_dir),
) -> FileResponse:
    subtitle_path = output_dir / f"{video_id}.srt"
    if not subtitle_path.is_file():
        raise HTTPException(status_code=404, detail="Subtitle file not found.")

    return FileResponse(
        subtitle_path,
        media_type="application/x-subrip",
        filename=f"creatorops-{video_id}.srt" if download else None,
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.get("/api/video/{video_id}", response_class=FileResponse)
def get_generated_video(
    video_id: UUID,
    download: bool = False,
    output_dir: Path = Depends(get_video_output_dir),
) -> FileResponse:
    video_path = output_dir / f"{video_id}.mp4"
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="Video file not found.")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"creatorops-{video_id}.mp4" if download else None,
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )
