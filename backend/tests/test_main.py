import io
import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from openai import APITimeoutError

from app.main import (
    ScriptResponse,
    app,
    get_audio_output_dir,
    get_media_probe,
    get_media_uploads_dir,
    get_openai_client,
    get_openai_model,
    get_video_output_dir,
    get_video_renderer,
    get_voice_generator,
    get_voice_reference_normalizer,
    get_voice_reference_path,
    get_voice_upload_path,
    normalize_voice_reference,
)
from app.services.voice import VoiceGenerationError, generate_audio
from app.services.video.renderer import (
    AUTOMATIC_MOTIONS,
    allocate_scene_frames,
    build_image_motion_filter,
    calculate_render_frames,
    calculate_transition_frames,
    render_video,
    resolve_motion_type,
)
from app.services.video.hyperframes import (
    build_hyperframes_composition,
    render_hyperframes_text_scene,
)
from app.services.video.schemas import RenderScene, VideoRenderResult
from app.services.video.subtitles import write_srt


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


class FakeVoiceReferenceNormalizer:
    def __init__(self):
        self.calls: list[tuple[Path, Path]] = []

    def __call__(self, source_path: Path, output_path: Path) -> None:
        self.calls.append((source_path, output_path))
        if source_path.read_bytes() == b"not audio":
            raise ValueError(
                "The uploaded file is damaged or is not a supported audio format."
            )

        output_path.write_bytes(make_wav_bytes())


class FakeMediaProbe:
    def __init__(self):
        self.calls: list[Path] = []

    def __call__(self, media_path: Path) -> tuple[set[str], float | None]:
        self.calls.append(media_path)
        if media_path.suffix.lower() in {".mp3", ".wav", ".m4a"}:
            return {"audio"}, 10.0
        return {"video"}, 10.0


class FakeVideoRenderer:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> VideoRenderResult:
        self.calls.append(kwargs)
        output_path = Path(str(kwargs["output_path"]))
        subtitle_path = Path(str(kwargs["subtitle_path"]))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"mock mp4")
        subtitle_path.write_text("mock subtitles\n", encoding="utf-8")
        return VideoRenderResult(
            video_path=output_path,
            subtitle_path=subtitle_path,
            subtitles_burned=False,
        )


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
    def test_voice_reference_normalization_uses_ffmpeg(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "voice.m4a"
            output_path = temp_path / "voice.wav"
            source_path.write_bytes(b"mock compressed audio")
            commands: list[list[str]] = []

            def fake_ffmpeg(command: list[str], **kwargs: object) -> None:
                commands.append(command)
                Path(command[-1]).write_bytes(make_wav_bytes())

            with patch("app.main.subprocess.run", side_effect=fake_ffmpeg):
                normalize_voice_reference(source_path, output_path)

            self.assertTrue(output_path.read_bytes().startswith(b"RIFF"))
            self.assertEqual(len(commands), 1)
            self.assertIn("0:a:0", commands[0])
            self.assertIn("pcm_s16le", commands[0])
            self.assertIn("24000", commands[0])

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


class VideoServiceUnitTests(unittest.TestCase):
    def test_hyperframes_composition_is_deterministic_and_escapes_text(self) -> None:
        composition = build_hyperframes_composition(
            scene_number=2,
            visual_description="Dashboard <script>alert('x')</script>",
            subtitle="Create & publish",
            duration_seconds=4.25,
        )

        self.assertIn('data-composition-id="main"', composition)
        self.assertIn('data-duration="4.250000"', composition)
        self.assertIn('data-fps="30"', composition)
        self.assertIn("@keyframes word-in", composition)
        self.assertIn("Create", composition)
        self.assertIn("&amp;", composition)
        self.assertIn("&lt;script&gt;", composition)
        self.assertNotIn("<script>alert", composition)
        self.assertNotIn("https://", composition)

    def test_hyperframes_renderer_mocks_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)
            cli_path = working_dir / "hyperframes"
            project_dir = working_dir / "composition"
            output_path = working_dir / "scene.mp4"
            cli_path.touch()
            commands: list[list[str]] = []

            def fake_hyperframes(command: list[str], **kwargs: object) -> None:
                commands.append(command)
                output_path.write_bytes(b"mock hyperframes mp4")

            with (
                patch(
                    "app.services.video.hyperframes.HYPERFRAMES_CLI",
                    cli_path,
                ),
                patch(
                    "app.services.video.hyperframes.subprocess.run",
                    side_effect=fake_hyperframes,
                ),
            ):
                rendered = render_hyperframes_text_scene(
                    scene_number=1,
                    visual_description="Creator workflow",
                    subtitle="Build content faster",
                    duration_seconds=3.0,
                    project_dir=project_dir,
                    output_path=output_path,
                )

            self.assertTrue(rendered)
            self.assertTrue((project_dir / "index.html").is_file())
            self.assertEqual(commands[0][0], str(cli_path))
            self.assertIn("render", commands[0])
            self.assertIn("--no-browser-gpu", commands[0])
            self.assertTrue(output_path.is_file())

    def test_scene_frames_match_narration_duration(self) -> None:
        scenes = [
            RenderScene(1, 8, Path("one.png"), "image", "First", "contain"),
            RenderScene(2, 12, Path("two.mp4"), "video", "Second", "cover"),
        ]

        allocations = allocate_scene_frames(scenes, audio_duration=10.0)

        self.assertEqual(sum(allocations), 300)
        self.assertEqual(allocations, [120, 180])

    def test_scene_and_transition_frames_preserve_exact_duration(self) -> None:
        scenes = [
            RenderScene(1, 3, Path("one.png"), "image", "First", "cover"),
            RenderScene(2, 7, Path("two.png"), "image", "Second", "contain"),
        ]

        scene_frames = allocate_scene_frames(scenes, audio_duration=10.0)
        transition_frames = calculate_transition_frames(scene_frames)
        render_frames = calculate_render_frames(scene_frames, transition_frames)

        self.assertEqual(scene_frames, [90, 210])
        self.assertEqual(transition_frames, [12])
        self.assertEqual(render_frames, [102, 210])
        self.assertEqual(sum(render_frames) - sum(transition_frames), 300)

    def test_all_image_motion_types_build_zoompan_filters(self) -> None:
        for motion_type in AUTOMATIC_MOTIONS:
            with self.subTest(motion_type=motion_type):
                motion_filter = build_image_motion_filter(
                    motion_type,
                    "subtle",
                    90,
                )
                self.assertIn("zoompan=", motion_filter)
                self.assertIn("fps=30", motion_filter)

        self.assertEqual(build_image_motion_filter("none", "subtle", 90), "")

    def test_automatic_motion_rotates_without_repeating(self) -> None:
        resolved = [
            resolve_motion_type("automatic", scene_number)
            for scene_number in range(1, len(AUTOMATIC_MOTIONS) + 2)
        ]

        self.assertEqual(tuple(resolved[:-1]), AUTOMATIC_MOTIONS)
        self.assertEqual(resolved[-1], AUTOMATIC_MOTIONS[0])
        self.assertTrue(all(left != right for left, right in zip(resolved, resolved[1:])))

    def test_srt_uses_cumulative_scene_timing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "video.srt"

            write_srt(
                [
                    (0.0, 8.0, "From text to video in minutes"),
                    (8.0, 18.0, "An AI voice and video generation system"),
                ],
                subtitle_path,
            )

            self.assertEqual(
                subtitle_path.read_text(encoding="utf-8"),
                "1\n00:00:00,000 --> 00:00:08,000\n"
                "From text to video in minutes\n\n"
                "2\n00:00:08,000 --> 00:00:18,000\n"
                "An AI voice and video generation system\n",
            )

    def test_renderer_mocks_ffmpeg_for_images_clips_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)
            audio_path = working_dir / "narration.wav"
            image_path = working_dir / "opening.png"
            video_path = working_dir / "demo.mp4"
            output_path = working_dir / "final.mp4"
            subtitle_path = working_dir / "final.srt"
            audio_path.write_bytes(b"mock audio")
            image_path.write_bytes(b"mock image")
            video_path.write_bytes(b"mock video")
            ffmpeg_calls: list[list[str]] = []

            def fake_ffmpeg(command: list[str]) -> None:
                ffmpeg_calls.append(command)
                generated_path = Path(command[-1])
                generated_path.parent.mkdir(parents=True, exist_ok=True)
                generated_path.write_bytes(b"mock ffmpeg output")

            scenes = [
                RenderScene(
                    1,
                    1,
                    image_path,
                    "image",
                    "Opening",
                    "contain",
                    "pan_right",
                    "subtle",
                ),
                RenderScene(2, 1, video_path, "video", "Demo", "cover"),
            ]
            with (
                patch(
                    "app.services.video.renderer.probe_duration",
                    return_value=2.0,
                ),
                patch(
                    "app.services.video.renderer.ffmpeg_has_filter",
                    side_effect=lambda filter_name: filter_name == "xfade",
                ),
                patch(
                    "app.services.video.renderer.run_ffmpeg",
                    side_effect=fake_ffmpeg,
                ),
            ):
                result = render_video(
                    audio_path=audio_path,
                    scenes=scenes,
                    output_path=output_path,
                    subtitle_path=subtitle_path,
                    resolution="720p",
                )

            self.assertEqual(len(ffmpeg_calls), 4)
            self.assertIn("-loop", ffmpeg_calls[0])
            self.assertIn("-stream_loop", ffmpeg_calls[1])
            image_filter = ffmpeg_calls[0][ffmpeg_calls[0].index("-vf") + 1]
            video_filter = ffmpeg_calls[1][ffmpeg_calls[1].index("-vf") + 1]
            self.assertIn("zoompan=", image_filter)
            self.assertIn("z='1.12'", image_filter)
            self.assertIn("d=40:s=1920x1080:fps=30", image_filter)
            self.assertIn("fade=t=in:st=0:d=0.400000", image_filter)
            self.assertIn(
                "fade=t=out:st=0.933333:d=0.400000",
                image_filter,
            )
            self.assertNotIn("zoompan=", video_filter)
            crossfade_filter = ffmpeg_calls[2][
                ffmpeg_calls[2].index("-filter_complex") + 1
            ]
            self.assertIn("xfade=transition=fade", crossfade_filter)
            self.assertIn("duration=0.333333", crossfade_filter)
            self.assertIn("offset=1.000000", crossfade_filter)
            export_filter = ffmpeg_calls[3][
                ffmpeg_calls[3].index("-filter_complex") + 1
            ]
            self.assertIn(
                "[0:v]scale=1280:720:flags=lanczos[scaled]",
                export_filter,
            )
            self.assertIn("+faststart", ffmpeg_calls[3])
            self.assertEqual(result.video_path, output_path)
            self.assertTrue(result.video_path.is_file())
            self.assertTrue(result.subtitle_path.is_file())
            self.assertFalse(result.subtitles_burned)

    def test_renderer_generates_text_card_when_scene_has_no_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)
            audio_path = working_dir / "narration.wav"
            output_path = working_dir / "final.mp4"
            subtitle_path = working_dir / "final.srt"
            audio_path.write_bytes(b"mock audio")
            ffmpeg_calls: list[list[str]] = []
            card_calls: list[dict[str, object]] = []

            def fake_ffmpeg(command: list[str]) -> None:
                ffmpeg_calls.append(command)
                generated_path = Path(command[-1])
                generated_path.parent.mkdir(parents=True, exist_ok=True)
                generated_path.write_bytes(b"mock ffmpeg output")

            def fake_card(**kwargs: object) -> Path:
                card_calls.append(kwargs)
                card_path = Path(str(kwargs["output_path"]))
                card_path.write_bytes(b"mock png")
                return card_path

            with (
                patch(
                    "app.services.video.renderer.probe_duration",
                    return_value=2.0,
                ),
                patch(
                    "app.services.video.renderer.ffmpeg_has_filter",
                    return_value=False,
                ),
                patch(
                    "app.services.video.renderer.run_ffmpeg",
                    side_effect=fake_ffmpeg,
                ),
                patch(
                    "app.services.video.renderer.generate_text_card",
                    side_effect=fake_card,
                ),
                patch(
                    "app.services.video.renderer.render_hyperframes_text_scene",
                    return_value=False,
                ),
            ):
                result = render_video(
                    audio_path=audio_path,
                    scenes=[
                        RenderScene(
                            1,
                            2,
                            None,
                            "generated",
                            "Build content faster",
                            "cover",
                            visual_description="Creator dashboard in motion",
                        )
                    ],
                    output_path=output_path,
                    subtitle_path=subtitle_path,
                )

            self.assertEqual(len(card_calls), 1)
            self.assertEqual(card_calls[0]["subtitle"], "Build content faster")
            self.assertEqual(
                card_calls[0]["visual_description"],
                "Creator dashboard in motion",
            )
            self.assertEqual(len(ffmpeg_calls), 3)
            scene_filter = ffmpeg_calls[0][ffmpeg_calls[0].index("-vf") + 1]
            self.assertIn("zoompan=", scene_filter)
            self.assertTrue(result.video_path.is_file())

    def test_renderer_prefers_hyperframes_for_generated_text_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)
            audio_path = working_dir / "narration.wav"
            output_path = working_dir / "final.mp4"
            subtitle_path = working_dir / "final.srt"
            audio_path.write_bytes(b"mock audio")
            ffmpeg_calls: list[list[str]] = []
            hyperframes_calls: list[dict[str, object]] = []

            def fake_ffmpeg(command: list[str]) -> None:
                ffmpeg_calls.append(command)
                Path(command[-1]).write_bytes(b"mock ffmpeg output")

            def fake_hyperframes(**kwargs: object) -> bool:
                hyperframes_calls.append(kwargs)
                Path(str(kwargs["output_path"])).write_bytes(b"mock hyperframes mp4")
                return True

            with (
                patch(
                    "app.services.video.renderer.probe_duration",
                    return_value=2.0,
                ),
                patch(
                    "app.services.video.renderer.ffmpeg_has_filter",
                    return_value=False,
                ),
                patch(
                    "app.services.video.renderer.run_ffmpeg",
                    side_effect=fake_ffmpeg,
                ),
                patch(
                    "app.services.video.renderer.render_hyperframes_text_scene",
                    side_effect=fake_hyperframes,
                ),
                patch(
                    "app.services.video.renderer.generate_text_card",
                ) as card_mock,
            ):
                result = render_video(
                    audio_path=audio_path,
                    scenes=[
                        RenderScene(
                            1,
                            2,
                            None,
                            "generated",
                            "Build content faster",
                            "cover",
                            visual_description="Creator dashboard in motion",
                        )
                    ],
                    output_path=output_path,
                    subtitle_path=subtitle_path,
                )

            self.assertEqual(len(hyperframes_calls), 1)
            self.assertEqual(hyperframes_calls[0]["duration_seconds"], 2.0)
            card_mock.assert_not_called()
            self.assertIn("-stream_loop", ffmpeg_calls[0])
            self.assertTrue(result.video_path.is_file())


class CreatorOpsAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audio_output_dir = Path(self.temp_dir.name) / "audio"
        self.video_output_dir = Path(self.temp_dir.name) / "video"
        self.media_uploads_dir = Path(self.temp_dir.name) / "uploads"
        self.voice_reference = Path(self.temp_dir.name) / "voice-reference.wav"
        self.voice_reference.touch()
        self.fake_voice_generator = FakeVoiceGenerator()
        self.fake_voice_normalizer = FakeVoiceReferenceNormalizer()
        self.fake_media_probe = FakeMediaProbe()
        self.fake_video_renderer = FakeVideoRenderer()
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
        app.dependency_overrides[get_voice_reference_normalizer] = (
            lambda: self.fake_voice_normalizer
        )
        app.dependency_overrides[get_media_uploads_dir] = lambda: self.media_uploads_dir
        app.dependency_overrides[get_media_probe] = lambda: self.fake_media_probe
        app.dependency_overrides[get_video_output_dir] = lambda: self.video_output_dir
        app.dependency_overrides[get_video_renderer] = lambda: self.fake_video_renderer

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
            files={"file": ("authorized-voice.m4a", b"mock m4a audio", "audio/mp4")},
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
        self.assertEqual(len(self.fake_voice_normalizer.calls), 1)
        source_path, normalized_path = self.fake_voice_normalizer.calls[0]
        self.assertEqual(source_path.suffix, ".m4a")
        self.assertEqual(normalized_path.suffix, ".wav")
        self.assertEqual(
            after_upload.json(),
            {"ready": True, "filename": "voice-reference.wav"},
        )

    async def test_upload_voice_reference_accepts_common_audio_formats(self) -> None:
        formats = [
            ("voice.wav", "audio/wav"),
            ("voice.mp3", "audio/mpeg"),
            ("voice.m4a", "audio/mp4"),
            ("voice.flac", "audio/flac"),
            ("voice.ogg", "audio/ogg"),
            ("voice.webm", "audio/webm"),
        ]

        for filename, media_type in formats:
            with self.subTest(filename=filename):
                response = await self.client.post(
                    "/api/voice/reference",
                    files={"file": (filename, b"mock audio", media_type)},
                )
                self.assertEqual(response.status_code, 201)
                self.assertTrue(response.json()["ready"])

    async def test_upload_voice_reference_rejects_invalid_audio(self) -> None:
        original_contents = self.voice_reference.read_bytes()

        invalid_audio = await self.client.post(
            "/api/voice/reference",
            files={"file": ("voice.mp3", b"not audio", "audio/mpeg")},
        )

        self.assertEqual(invalid_audio.status_code, 422)
        self.assertIn("not a supported audio", invalid_audio.json()["detail"])
        self.assertEqual(self.voice_reference.read_bytes(), original_contents)

    async def test_media_upload_and_video_render_workflow(self) -> None:
        project_id = uuid4()

        async def upload(filename: str, role: str, content_type: str) -> dict[str, object]:
            response = await self.client.post(
                "/api/media/upload",
                data={"project_id": str(project_id), "media_role": role},
                files={"file": (filename, b"mock media", content_type)},
            )
            self.assertEqual(response.status_code, 201)
            return response.json()

        first_scene = await upload("opening.png", "scene", "image/png")
        second_scene = await upload("demo.mp4", "scene", "video/mp4")
        logo = await upload("logo.png", "logo", "image/png")
        background_music = await upload("music.mp3", "background_music", "audio/mpeg")

        self.assertEqual(first_scene["media_type"], "image")
        self.assertEqual(second_scene["media_type"], "video")
        self.assertEqual(logo["media_role"], "logo")
        self.assertEqual(background_music["media_type"], "audio")
        for upload_result in (first_scene, second_scene, logo, background_music):
            self.assertTrue(str(upload_result["media_path"]).startswith("uploads/"))

        audio_id = uuid4()
        narration_path = self.audio_output_dir / f"{audio_id}.wav"
        narration_path.parent.mkdir(parents=True, exist_ok=True)
        narration_path.write_bytes(make_wav_bytes())

        render_response = await self.client.post(
            "/api/video/render",
            json={
                "audio_id": str(audio_id),
                "resolution": "720p",
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration_seconds": 8,
                        "media_path": first_scene["media_path"],
                        "media_type": "image",
                        "subtitle": "From text to video in minutes",
                        "fit_mode": "fit",
                        "motion_type": "pan_left",
                        "motion_strength": "medium",
                    },
                    {
                        "scene_number": 2,
                        "duration_seconds": 10,
                        "media_path": second_scene["media_path"],
                        "media_type": "video",
                        "subtitle": "An AI voice and video generation system",
                        "fit_mode": "crop",
                    },
                ],
                "logo_path": logo["media_path"],
                "background_music_path": background_music["media_path"],
            },
        )

        self.assertEqual(render_response.status_code, 201)
        render_result = render_response.json()
        self.assertEqual(render_result["status"], "completed")
        self.assertEqual(render_result["resolution"], "720p")
        self.assertEqual(
            render_result["video_url"],
            f"/api/video/{render_result['video_id']}",
        )
        self.assertEqual(
            render_result["subtitle_url"],
            f"/api/video/{render_result['video_id']}/subtitles",
        )
        self.assertFalse(render_result["subtitles_burned"])
        self.assertEqual(len(self.fake_video_renderer.calls), 1)
        renderer_call = self.fake_video_renderer.calls[0]
        render_scenes = renderer_call["scenes"]
        self.assertEqual(
            [scene.fit_mode for scene in render_scenes],
            ["contain", "cover"],
        )
        self.assertEqual(
            [scene.motion_type for scene in render_scenes],
            ["pan_left", "automatic"],
        )
        self.assertEqual(
            [scene.motion_strength for scene in render_scenes],
            ["medium", "subtle"],
        )
        self.assertIsNotNone(renderer_call["logo_path"])
        self.assertIsNotNone(renderer_call["background_music_path"])
        self.assertEqual(renderer_call["resolution"], "720p")

        preview_response = await self.client.get(render_result["video_url"])
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.headers["content-type"], "video/mp4")
        self.assertEqual(preview_response.content, b"mock mp4")

        subtitle_response = await self.client.get(render_result["subtitle_url"])
        self.assertEqual(subtitle_response.status_code, 200)
        self.assertEqual(subtitle_response.content, b"mock subtitles\n")

        download_response = await self.client.get(
            f"{render_result['video_url']}?download=true"
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertTrue(
            download_response.headers["content-disposition"].startswith("attachment;")
        )

    async def test_video_render_rejects_media_path_traversal(self) -> None:
        audio_id = uuid4()
        narration_path = self.audio_output_dir / f"{audio_id}.wav"
        narration_path.parent.mkdir(parents=True, exist_ok=True)
        narration_path.write_bytes(make_wav_bytes())

        response = await self.client.post(
            "/api/video/render",
            json={
                "audio_id": str(audio_id),
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration_seconds": 8,
                        "media_path": "uploads/../../private/my_voice.wav",
                        "media_type": "image",
                        "subtitle": "Unsafe path",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("outside the uploads directory", response.json()["detail"])
        self.assertEqual(self.fake_video_renderer.calls, [])

    async def test_video_render_allows_generated_scene_without_upload(self) -> None:
        audio_id = uuid4()
        narration_path = self.audio_output_dir / f"{audio_id}.wav"
        narration_path.parent.mkdir(parents=True, exist_ok=True)
        narration_path.write_bytes(make_wav_bytes())

        response = await self.client.post(
            "/api/video/render",
            json={
                "audio_id": str(audio_id),
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration_seconds": 8,
                        "media_path": None,
                        "media_type": "generated",
                        "subtitle": "Create faster with CreatorOps AI",
                        "visual_description": "A modern creator workflow",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.fake_video_renderer.calls), 1)
        scene = self.fake_video_renderer.calls[0]["scenes"][0]
        self.assertIsNone(scene.media_path)
        self.assertEqual(scene.media_type, "generated")
        self.assertEqual(scene.visual_description, "A modern creator workflow")

    async def test_video_render_accepts_mixed_text_and_uploaded_scenes(self) -> None:
        project_id = uuid4()
        upload_response = await self.client.post(
            "/api/media/upload",
            data={"project_id": str(project_id), "media_role": "scene"},
            files={"file": ("product.png", b"mock image", "image/png")},
        )
        self.assertEqual(upload_response.status_code, 201)

        audio_id = uuid4()
        narration_path = self.audio_output_dir / f"{audio_id}.wav"
        narration_path.parent.mkdir(parents=True, exist_ok=True)
        narration_path.write_bytes(make_wav_bytes())

        response = await self.client.post(
            "/api/video/render",
            json={
                "audio_id": str(audio_id),
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration_seconds": 4,
                        "media_type": "generated",
                        "subtitle": "Start with an idea",
                        "visual_description": "Words assemble into a creator plan",
                    },
                    {
                        "scene_number": 2,
                        "duration_seconds": 4,
                        "media_type": "image",
                        "media_path": upload_response.json()["media_path"],
                        "subtitle": "Finish with a polished video",
                        "motion_type": "zoom_in",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        scenes = self.fake_video_renderer.calls[0]["scenes"]
        self.assertEqual([scene.media_type for scene in scenes], ["generated", "image"])
        self.assertIsNone(scenes[0].media_path)
        self.assertTrue(scenes[1].media_path.is_file())

    async def test_video_render_rejects_unknown_resolution(self) -> None:
        response = await self.client.post(
            "/api/video/render",
            json={
                "audio_id": str(uuid4()),
                "resolution": "4k",
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration_seconds": 4,
                        "media_type": "generated",
                        "subtitle": "Unsupported export size",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.fake_video_renderer.calls, [])

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
