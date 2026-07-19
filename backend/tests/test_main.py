import os
import unittest
from types import SimpleNamespace

import httpx
from openai import APITimeoutError

from app.main import (
    ScriptResponse,
    app,
    get_openai_client,
    get_openai_model,
)


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


class CreatorOpsAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )
        self.fake_responses = FakeResponses(make_script())
        self.fake_openai = FakeOpenAI(self.fake_responses)
        app.dependency_overrides[get_openai_client] = lambda: self.fake_openai
        app.dependency_overrides[get_openai_model] = lambda: "gpt-5.6"

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

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


if __name__ == "__main__":
    unittest.main()
