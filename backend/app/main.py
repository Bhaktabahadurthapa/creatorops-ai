import logging
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

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
