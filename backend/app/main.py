import io
import logging
import os
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
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


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
AUDIO_OUTPUT_DIR = BACKEND_DIR / "outputs" / "audio"
VOICE_UPLOAD_PATH = BACKEND_DIR / "private" / "my_voice.wav"
MAX_VOICE_UPLOAD_BYTES = 25 * 1024 * 1024
MIN_VOICE_REFERENCE_SECONDS = 1.0
load_dotenv(BACKEND_DIR / ".env")

VoiceGenerator = Callable[[str, Path, Path], Path]

app = FastAPI(title="CreatorOps AI API")

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


def validate_voice_reference(filename: str | None, contents: bytes) -> None:
    if not filename or Path(filename).suffix.lower() != ".wav":
        raise ValueError("Choose a WAV file with a .wav extension.")

    if not contents:
        raise ValueError("The uploaded WAV file is empty.")

    if len(contents) > MAX_VOICE_UPLOAD_BYTES:
        raise ValueError("The uploaded WAV file must be 25 MB or smaller.")

    try:
        with wave.open(io.BytesIO(contents), "rb") as audio_file:
            channels = audio_file.getnchannels()
            sample_width = audio_file.getsampwidth()
            sample_rate = audio_file.getframerate()
            frame_count = audio_file.getnframes()
    except (EOFError, wave.Error) as exc:
        raise ValueError("The uploaded file is not a readable PCM WAV file.") from exc

    if channels not in {1, 2}:
        raise ValueError("The voice reference must contain mono or stereo audio.")
    if sample_width not in {1, 2, 3, 4} or sample_rate < 8_000:
        raise ValueError("The voice reference uses an unsupported WAV format.")
    if frame_count / sample_rate < MIN_VOICE_REFERENCE_SECONDS:
        raise ValueError("The voice reference must be at least 1 second long.")


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

    try:
        validate_voice_reference(file.filename, contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    temporary_path = upload_path.with_name(f".{upload_path.name}.{uuid4()}.uploading")
    try:
        upload_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_bytes(contents)
        temporary_path.chmod(0o600)
        temporary_path.replace(upload_path)
    except OSError as exc:
        logger.error("Could not store uploaded voice reference: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The voice reference could not be saved.",
        ) from exc
    finally:
        temporary_path.unlink(missing_ok=True)

    return VoiceReferenceStatus(ready=True, filename=upload_path.name)


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
