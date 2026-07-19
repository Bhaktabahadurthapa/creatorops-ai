import re
import subprocess
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any


XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
SPEAKER_NAME = "my_voice"
SPEECH_SPEED = 1.04
SHORT_PAUSE_MS = 180
PARAGRAPH_PAUSE_MS = 350

_TTS: Any | None = None


class VoiceGenerationError(RuntimeError):
    """Raised when the local voice model cannot produce a usable WAV file."""


def load_tts_model() -> Any:
    """Load XTTS on first use and reuse it for later requests."""
    global _TTS

    if _TTS is None:
        try:
            from TTS.api import TTS
        except ImportError as exc:
            raise VoiceGenerationError(
                "Voice model dependencies are not installed."
            ) from exc

        try:
            _TTS = TTS(model_name=XTTS_MODEL, progress_bar=False).to("cpu")
        except Exception as exc:
            raise VoiceGenerationError("The voice model could not be loaded.") from exc

    return _TTS


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
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]

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

    if chunks:
        chunks[-1] = (chunks[-1][0], 0)

    return chunks


def generate_audio(
    text: str,
    output_path: Path,
    reference_path: Path,
    model_loader: Callable[[], Any] = load_tts_model,
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
                    tts.tts_to_file(
                        text=chunk,
                        speaker=SPEAKER_NAME,
                        speaker_wav=str(normalized_voice) if index == 1 else None,
                        language="en",
                        file_path=str(chunk_path),
                        split_sentences=False,
                        temperature=0.75,
                        repetition_penalty=5.0,
                        top_k=50,
                        top_p=0.85,
                        speed=SPEECH_SPEED,
                        sound_norm_refs=True,
                        gpt_cond_len=13,
                        gpt_cond_chunk_len=6,
                        max_ref_len=20,
                    )

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
