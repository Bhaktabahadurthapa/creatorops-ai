import io
import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import APITimeoutError

from app.main import (
    ScriptResponse,
    app,
    get_audio_output_dir,
    get_openai_client,
    get_openai_model,
    get_voice_generator,
    get_voice_reference_path,
    get_voice_upload_path,
)
from app.services.voice import VoiceGenerationError, generate_audio


class FakeResponses:
    def __init__(
        self,
        result: ScriptResponse | None = None,
        error: Exception | None = None,
    ):
        self.result = result
        self.error = error
        self.request = None
        self.output: list[SimpleNamespace] = []

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.request = kwargs

        if self.error:
            raise self.error

        return SimpleNamespace(output_parsed=self.result, output=self.output)


class FakeOpenAI:
    def __init__(self, responses: FakeResponses):
        self.responses = responses


class FakeVoiceGenerator:
    def __init__(self):
        self.calls: list[tuple[str, Path, Path]] = []

    def __call__(self, narration: str, output_path: Path, reference_path: Path) -> Path:
        self.calls.append((narration, output_path, reference_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(output_path), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(24_000)
            audio_file.writeframes(b"\0\0" * 240)

        return output_path


class FailingVoiceGenerator:
    def __call__(self, narration: str, output_path: Path, reference_path: Path) -> Path:
        raise VoiceGenerationError("Mock voice model failure")


class FakeTTSModel:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def tts_to_file(self, **kwargs: object) -> None:
        self.calls.append(kwargs)
        output_path = Path(str(kwargs["file_path"]))

        with wave.open(str(output_path), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(24_000)
            audio_file.writeframes(b"\0\0" * 240)


def make_script(duration: int = 60) -> ScriptResponse:
    return ScriptResponse(
        title="CreatorOps AI in One Minute",
        hook="What if one idea could become a complete video plan?",
        narration="CreatorOps AI turns a raw idea into a structured production plan.",
        call_to_action="Turn your next idea into a CreatorOps AI project.",
        scenes=[
            {
                "scene_number": 1,
                "visual_description": "A creator faces a blank planning board.",
                "narration": "Every video starts as a rough idea.",
                "subtitle": "Start with one idea",
                "duration_seconds": duration // 2,
            },
            {
                "scene_number": 2,
                "visual_description": "The idea expands into an organized storyboard.",
                "narration": "CreatorOps AI shapes it into a production-ready plan.",
                "subtitle": "Build the plan",
                "duration_seconds": duration - (duration // 2),
            },
        ],
    )


def make_wav_bytes(duration_seconds: int = 2) -> bytes:
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(24_000)
        audio_file.writeframes(b"\0\0" * 24_000 * duration_seconds)

    return wav_buffer.getvalue()


class VoiceGeneratorUnitTests(unittest.TestCase):
    def test_generate_audio_uses_mocked_model_and_writes_wav(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            reference_path = temp_path / "voice-reference.wav"
            output_path = temp_path / "output.wav"
            fake_model = FakeTTSModel()

            with wave.open(str(reference_path), "wb") as reference_file:
                reference_file.setnchannels(1)
                reference_file.setsampwidth(2)
                reference_file.setframerate(24_000)
                reference_file.writeframes(b"\0\0" * 240)

            def fake_ffmpeg(command: list[str], **kwargs: object) -> None:
                source_path = Path(command[command.index("-i") + 1])
                destination_path = Path(command[-1])
                shutil.copyfile(source_path, destination_path)

            with patch(
                "app.services.voice.generator.subprocess.run",
                side_effect=fake_ffmpeg,
            ):
                result = generate_audio(
                    "# CreatorOps\n\nFirst scene. Second scene.",
                    output_path,
                    reference_path,
                    model_loader=lambda: fake_model,
                )

            self.assertEqual(result, output_path)
            self.assertTrue(output_path.read_bytes().startswith(b"RIFF"))
            self.assertEqual(len(fake_model.calls), 2)
            self.assertEqual(fake_model.calls[0]["text"], "CreatorOps")
            self.assertIsNotNone(fake_model.calls[0]["speaker_wav"])
            self.assertIsNone(fake_model.calls[1]["speaker_wav"])


class CreatorOpsAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audio_output_dir = Path(self.temp_dir.name) / "audio"
        self.voice_reference = Path(self.temp_dir.name) / "voice-reference.wav"
        self.voice_reference.touch()
        self.fake_voice_generator = FakeVoiceGenerator()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )
        self.fake_responses = FakeResponses(make_script())
        self.fake_openai = FakeOpenAI(self.fake_responses)
        app.dependency_overrides[get_openai_client] = lambda: self.fake_openai
        app.dependency_overrides[get_openai_model] = lambda: "gpt-5.6"
        app.dependency_overrides[get_voice_reference_path] = lambda: self.voice_reference
        app.dependency_overrides[get_voice_generator] = lambda: self.fake_voice_generator
        app.dependency_overrides[get_audio_output_dir] = lambda: self.audio_output_dir
        app.dependency_overrides[get_voice_upload_path] = lambda: self.voice_reference

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    async def test_health_check_is_preserved(self) -> None:
        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    async def test_generate_script_returns_structured_response(self) -> None:
        response = await self.client.post(
            "/api/generate-script",
            json={
                "idea": "Explain how CreatorOps AI helps creators",
                "platform": "YouTube",
                "tone": "Educational",
                "duration": 60,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), make_script().model_dump())
        self.assertEqual(self.fake_responses.request["model"], "gpt-5.6")
        self.assertIs(self.fake_responses.request["text_format"], ScriptResponse)
        self.assertFalse(self.fake_responses.request["store"])
        prompt = str(self.fake_responses.request["input"])
        self.assertIn("Platform: YouTube", prompt)
        self.assertIn("Tone: Educational", prompt)
        self.assertIn("exactly 60 seconds", prompt)

    async def test_request_validation_rejects_invalid_inputs(self) -> None:
        invalid_payloads = [
            {"idea": "  ", "platform": "YouTube", "tone": "Friendly", "duration": 60},
            {"idea": "A valid idea", "platform": "Podcast", "tone": "Friendly", "duration": 60},
            {"idea": "A valid idea", "platform": "TikTok", "tone": "Sarcastic", "duration": 60},
            {"idea": "A valid idea", "platform": "TikTok", "tone": "Energetic", "duration": 45},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = await self.client.post(
                    "/api/generate-script",
                    json=payload,
                )
                self.assertEqual(response.status_code, 422)

    async def test_missing_api_key_returns_configuration_error(self) -> None:
        original_api_key = os.environ.pop("OPENAI_API_KEY", None)
        app.dependency_overrides.pop(get_openai_client)

        try:
            response = await self.client.post(
                "/api/generate-script",
                json={"idea": "A valid idea"},
            )
        finally:
            if original_api_key is not None:
                os.environ["OPENAI_API_KEY"] = original_api_key

        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["detail"])

    async def test_missing_model_returns_configuration_error(self) -> None:
        original_model = os.environ.pop("OPENAI_MODEL", None)
        app.dependency_overrides.pop(get_openai_model)

        try:
            response = await self.client.post(
                "/api/generate-script",
                json={"idea": "A valid idea"},
            )
        finally:
            if original_model is not None:
                os.environ["OPENAI_MODEL"] = original_model

        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_MODEL", response.json()["detail"])

    async def test_openai_timeout_returns_service_unavailable(self) -> None:
        timeout = APITimeoutError(
            request=httpx.Request("POST", "https://api.openai.com/v1/responses")
        )
        self.fake_responses.error = timeout

        response = await self.client.post(
            "/api/generate-script",
            json={"idea": "A valid idea"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.json()["detail"])

    async def test_missing_parsed_output_returns_bad_gateway(self) -> None:
        self.fake_responses.result = None

        response = await self.client.post(
            "/api/generate-script",
            json={"idea": "A valid idea"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("no usable result", response.json()["detail"])

    async def test_model_refusal_returns_validation_error(self) -> None:
        self.fake_responses.result = None
        self.fake_responses.output = [
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="refusal")],
            )
        ]

        response = await self.client.post(
            "/api/generate-script",
            json={"idea": "A valid idea"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("revise it", response.json()["detail"])

    async def test_scene_duration_must_match_requested_duration(self) -> None:
        self.fake_responses.result = make_script(duration=30)

        response = await self.client.post(
            "/api/generate-script",
            json={"idea": "A valid idea", "duration": 60},
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("scene timing", response.json()["detail"])

    async def test_generate_voice_returns_playable_audio_url(self) -> None:
        response = await self.client.post(
            "/api/voice/generate",
            json={"text": "CreatorOps AI turns narration into audio."},
        )

        self.assertEqual(response.status_code, 201)
        response_body = response.json()
        self.assertEqual(len(self.fake_voice_generator.calls), 1)
        narration, output_path, reference_path = self.fake_voice_generator.calls[0]
        self.assertEqual(narration, "CreatorOps AI turns narration into audio.")
        self.assertEqual(reference_path, self.voice_reference)
        self.assertEqual(output_path.parent, self.audio_output_dir)
        self.assertEqual(response_body["audio_id"], output_path.stem)
        self.assertEqual(
            response_body["audio_url"],
            f"/api/voice/audio/{response_body['audio_id']}",
        )

        audio_response = await self.client.get(response_body["audio_url"])
        self.assertEqual(audio_response.status_code, 200)
        self.assertEqual(audio_response.headers["content-type"], "audio/wav")
        self.assertTrue(audio_response.content.startswith(b"RIFF"))

        download_response = await self.client.get(
            f"{response_body['audio_url']}?download=true"
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertTrue(
            download_response.headers["content-disposition"].startswith("attachment;")
        )

    async def test_upload_voice_reference_is_available_later(self) -> None:
        self.voice_reference.unlink()

        before_upload = await self.client.get("/api/voice/reference/status")
        upload_response = await self.client.post(
            "/api/voice/reference",
            files={"file": ("authorized-voice.wav", make_wav_bytes(), "audio/wav")},
        )
        after_upload = await self.client.get("/api/voice/reference/status")

        self.assertEqual(before_upload.status_code, 200)
        self.assertEqual(before_upload.json(), {"ready": False, "filename": None})
        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(
            upload_response.json(),
            {"ready": True, "filename": "voice-reference.wav"},
        )
        self.assertTrue(self.voice_reference.read_bytes().startswith(b"RIFF"))
        self.assertEqual(
            after_upload.json(),
            {"ready": True, "filename": "voice-reference.wav"},
        )

    async def test_upload_voice_reference_rejects_invalid_files(self) -> None:
        original_contents = self.voice_reference.read_bytes()

        wrong_extension = await self.client.post(
            "/api/voice/reference",
            files={"file": ("voice.txt", make_wav_bytes(), "text/plain")},
        )
        invalid_wav = await self.client.post(
            "/api/voice/reference",
            files={"file": ("voice.wav", b"not audio", "audio/wav")},
        )

        self.assertEqual(wrong_extension.status_code, 422)
        self.assertIn(".wav extension", wrong_extension.json()["detail"])
        self.assertEqual(invalid_wav.status_code, 422)
        self.assertIn("not a readable", invalid_wav.json()["detail"])
        self.assertEqual(self.voice_reference.read_bytes(), original_contents)

    async def test_voice_generation_rejects_empty_narration(self) -> None:
        response = await self.client.post(
            "/api/voice/generate",
            json={"text": "   "},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.fake_voice_generator.calls, [])

    async def test_missing_voice_reference_configuration_returns_error(self) -> None:
        original_reference = os.environ.pop("VOICE_REFERENCE_PATH", None)
        app.dependency_overrides.pop(get_voice_reference_path)

        try:
            response = await self.client.post(
                "/api/voice/generate",
                json={"text": "A valid narration."},
            )
        finally:
            if original_reference is not None:
                os.environ["VOICE_REFERENCE_PATH"] = original_reference

        self.assertEqual(response.status_code, 503)
        self.assertIn("VOICE_REFERENCE_PATH", response.json()["detail"])
        self.assertEqual(self.fake_voice_generator.calls, [])

    async def test_voice_model_failure_returns_service_unavailable(self) -> None:
        app.dependency_overrides[get_voice_generator] = lambda: FailingVoiceGenerator()

        response = await self.client.post(
            "/api/voice/generate",
            json={"text": "A valid narration."},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.json()["detail"])

    async def test_missing_audio_identifier_returns_not_found(self) -> None:
        response = await self.client.get(
            "/api/voice/audio/00000000-0000-0000-0000-000000000000"
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
