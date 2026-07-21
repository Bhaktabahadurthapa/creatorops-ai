import os
import re
import subprocess
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import get_model_cache_dir


SHORT_PAUSE_MS = 180
PARAGRAPH_PAUSE_MS = 350
PAUSE_MARKER_PATTERN = re.compile(
    r"\[pause\s+([0-9]+(?:\.[0-9]+)?)s\]",
    re.IGNORECASE,
)

_MODEL: Any | None = None


class VoiceGenerationError(RuntimeError):
    """Raised when the local voice model cannot produce a usable WAV file."""


def load_voice_model() -> Any:
    """Load Chatterbox Turbo on first use and reuse it for later requests."""
    global _MODEL

    if _MODEL is None:
        model_cache_dir = get_model_cache_dir()
        model_cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(model_cache_dir))
        os.environ.setdefault(
            "HUGGINGFACE_HUB_CACHE",
            str(model_cache_dir / "hub"),
        )

        try:
            import torch
            from chatterbox.tts_turbo import ChatterboxTurboTTS
        except ImportError as exc:
            raise VoiceGenerationError(
                "Voice model dependencies are not installed."
            ) from exc

        try:
            configured_device = os.getenv(
                "CHATTERBOX_DEVICE", "auto"
            ).strip().lower()
            if configured_device not in {"auto", "cpu", "mps", "cuda"}:
                raise VoiceGenerationError(
                    "CHATTERBOX_DEVICE must be one of: auto, cpu, mps, or cuda."
                )

            mps_available = bool(
                getattr(torch.backends, "mps", None)
                and torch.backends.mps.is_available()
            )
            if configured_device == "auto":
                if torch.cuda.is_available():
                    device = "cuda"
                elif mps_available:
                    device = "mps"
                else:
                    device = "cpu"
            else:
                device = configured_device

            if device == "cuda" and not torch.cuda.is_available():
                raise VoiceGenerationError(
                    "CHATTERBOX_DEVICE is cuda but no CUDA GPU is available."
                )
            if device == "mps" and not mps_available:
                raise VoiceGenerationError(
                    "CHATTERBOX_DEVICE is mps but Apple MPS is unavailable."
                )

            _MODEL = ChatterboxTurboTTS.from_pretrained(device=device)
        except VoiceGenerationError:
            raise
        except Exception as exc:
            raise VoiceGenerationError("The voice model could not be loaded.") from exc

    return _MODEL


def save_waveform(path: Path, waveform: Any, sample_rate: int) -> None:
    """Write a generated Chatterbox tensor as a WAV file."""
    try:
        import torchaudio
    except ImportError as exc:
        raise VoiceGenerationError(
            "Voice audio dependencies are not installed."
        ) from exc

    torchaudio.save(
        str(path),
        waveform,
        sample_rate,
        encoding="PCM_S",
        bits_per_sample=16,
    )


def clean_script(text: str) -> str:
    """Remove Markdown formatting that should not be spoken aloud."""
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"```(?:\w+)?", "", text)

    cleaned_lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*(?:[-+*]|\d+[.)])\s+", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = re.sub(r"[*_`~]", "", line)
        cleaned_lines.append(line.strip())

    text = "\n".join(cleaned_lines)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_for_speech(text: str, max_chars: int = 240) -> list[tuple[str, int]]:
    """Split narration into natural chunks paired with pause lengths."""
    chunks: list[tuple[str, int]] = []
    pause_segments = PAUSE_MARKER_PATTERN.split(text)

    for segment_index in range(0, len(pause_segments), 2):
        segment = pause_segments[segment_index]
        paragraphs = [
            part.strip()
            for part in re.split(r"\n\s*\n", segment)
            if part.strip()
        ]

        for paragraph in paragraphs:
            paragraph = " ".join(paragraph.splitlines())
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", paragraph)
                if sentence.strip()
            ]
            current = ""

            for sentence in sentences:
                candidate = f"{current} {sentence}".strip()
                if current and len(candidate) > max_chars:
                    chunks.append((current, SHORT_PAUSE_MS))
                    current = sentence
                else:
                    current = candidate

            if current:
                chunks.append((current, PARAGRAPH_PAUSE_MS))

        pause_value_index = segment_index + 1
        if pause_value_index < len(pause_segments) and chunks:
            pause_ms = round(float(pause_segments[pause_value_index]) * 1000)
            pause_ms = max(0, min(pause_ms, 5000))
            chunks[-1] = (chunks[-1][0], pause_ms)

    if chunks:
        chunks[-1] = (chunks[-1][0], 0)

    return chunks


def generate_audio(
    text: str,
    output_path: Path,
    reference_path: Path,
    model_loader: Callable[[], Any] = load_voice_model,
) -> Path:
    """Generate a WAV file with the configured reference voice."""
    cleaned_text = clean_script(text)
    if not cleaned_text:
        raise ValueError("Narration must contain speakable text.")

    if not reference_path.is_file():
        raise FileNotFoundError("The configured voice reference file was not found.")

    if output_path.suffix.lower() != ".wav":
        raise ValueError("Voice output must use the .wav extension.")

    chunks = split_for_speech(cleaned_text)
    if not chunks:
        raise ValueError("Narration must contain speakable text.")
    partial_path = output_path.with_suffix(".partial.wav")
    normalized_path = output_path.with_suffix(".normalized.wav")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            normalized_voice = temp_path / "voice_reference.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(reference_path),
                    "-af",
                    "highpass=f=70,loudnorm=I=-20:TP=-3:LRA=11",
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    "-c:a",
                    "pcm_s16le",
                    str(normalized_voice),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            tts = model_loader()

            with wave.open(str(partial_path), "wb") as output_wav:
                output_format: tuple[int, int, int] | None = None

                for index, (chunk, pause_ms) in enumerate(chunks, start=1):
                    chunk_path = temp_path / f"chunk_{index:04d}.wav"
                    waveform = tts.generate(
                        chunk,
                        audio_prompt_path=(
                            str(normalized_voice) if index == 1 else None
                        ),
                    )
                    save_waveform(chunk_path, waveform, int(tts.sr))

                    with wave.open(str(chunk_path), "rb") as chunk_wav:
                        chunk_format = (
                            chunk_wav.getnchannels(),
                            chunk_wav.getsampwidth(),
                            chunk_wav.getframerate(),
                        )
                        if output_format is None:
                            output_format = chunk_format
                            output_wav.setnchannels(chunk_format[0])
                            output_wav.setsampwidth(chunk_format[1])
                            output_wav.setframerate(chunk_format[2])
                        elif chunk_format != output_format:
                            raise ValueError(
                                "Generated audio sections use incompatible formats."
                            )

                        output_wav.writeframes(
                            chunk_wav.readframes(chunk_wav.getnframes())
                        )
                        silence_frames = int(chunk_format[2] * pause_ms / 1000)
                        output_wav.writeframes(
                            b"\0"
                            * silence_frames
                            * chunk_format[0]
                            * chunk_format[1]
                        )

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(partial_path),
                    "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    "-c:a",
                    "pcm_s16le",
                    str(normalized_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            normalized_path.replace(output_path)
    except Exception as exc:
        raise VoiceGenerationError("Voice audio generation failed.") from exc
    finally:
        partial_path.unlink(missing_ok=True)
        normalized_path.unlink(missing_ok=True)

    return output_path
