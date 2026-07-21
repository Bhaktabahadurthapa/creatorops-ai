import base64
import binascii
import os
from pathlib import Path

from openai import OpenAI


DEFAULT_IMAGE_MODEL = "gpt-image-2"


class SceneVisualGenerationError(RuntimeError):
    """Raised when a scene prompt cannot be converted into an image."""


def get_image_model() -> str:
    configured = os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip()
    return configured or DEFAULT_IMAGE_MODEL


def generate_scene_image(
    prompt: str,
    output_path: Path,
    *,
    client: OpenAI,
    model: str,
) -> Path:
    """Generate one text-free landscape scene image with the OpenAI Image API."""
    clean_prompt = " ".join(prompt.split())
    if not clean_prompt:
        raise SceneVisualGenerationError("The scene visual prompt is empty.")

    image_prompt = (
        "Create a cinematic, photorealistic 16:9 production still for a video scene. "
        "Follow this visual direction: "
        f"{clean_prompt}\n\n"
        "Show the subject, setting, lighting, action, and camera composition visually. "
        "Do not include captions, titles, logos, watermarks, UI, written words, letters, "
        "or readable text anywhere in the image."
    )

    try:
        response = client.images.generate(
            model=model,
            prompt=image_prompt,
            size="1536x1024",
            quality="low",
            output_format="jpeg",
            n=1,
            timeout=180,
        )
        encoded_image = response.data[0].b64_json if response.data else None
        if not encoded_image:
            raise SceneVisualGenerationError(
                "OpenAI returned no image for the scene prompt."
            )
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except SceneVisualGenerationError:
        raise
    except (binascii.Error, IndexError, AttributeError, ValueError) as exc:
        raise SceneVisualGenerationError(
            "OpenAI returned an invalid scene image."
        ) from exc
    except Exception as exc:
        raise SceneVisualGenerationError(
            "OpenAI could not generate the scene image."
        ) from exc

    if not image_bytes:
        raise SceneVisualGenerationError("OpenAI returned an empty scene image.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".tmp")
    try:
        temporary_path.write_bytes(image_bytes)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return output_path
