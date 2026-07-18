from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="CreatorOps AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScriptRequest(BaseModel):
    idea: str
    platform: str = "YouTube"
    tone: str = "Professional"
    duration: int = 60


class ScriptResponse(BaseModel):
    title: str
    script: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/generate-script", response_model=ScriptResponse)
def generate_script(request: ScriptRequest) -> ScriptResponse:
    clean_idea = request.idea.strip()

    if not clean_idea:
        return ScriptResponse(
            title="Missing idea",
            script="Please enter a project idea.",
        )

    script = (
        f"Hook: Are you struggling with {clean_idea}?\n\n"
        f"Problem: Many people spend too much time handling this manually.\n\n"
        f"Solution: CreatorOps AI helps turn this idea into useful content.\n\n"
        f"Call to action: Start building your {request.platform} content today."
    )

    return ScriptResponse(
        title=f"{clean_idea.title()} Video",
        script=script,
    )