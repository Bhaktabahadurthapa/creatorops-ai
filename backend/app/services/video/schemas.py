from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MediaType = Literal["image", "video", "audio"]
MediaRole = Literal["scene", "logo", "background_music"]
FitMode = Literal["cover", "contain"]
MotionType = Literal[
    "automatic",
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "none",
]
MotionStrength = Literal["subtle", "medium", "strong"]
VideoResolution = Literal["720p", "1080p"]


class MediaUploadResponse(BaseModel):
    project_id: UUID
    media_id: UUID
    filename: str
    media_type: MediaType
    media_role: MediaRole
    media_path: str


class VideoSceneInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scene_number: int = Field(ge=1)
    duration_seconds: int = Field(ge=1, le=600)
    media_path: str | None = Field(default=None, max_length=500)
    media_type: Literal["image", "video", "generated"] = "generated"
    subtitle: str = Field(min_length=1, max_length=500)
    visual_description: str = Field(default="", max_length=1000)
    fit_mode: FitMode = "cover"
    motion_type: MotionType = "automatic"
    motion_strength: MotionStrength = "subtle"

    @field_validator("fit_mode", mode="before")
    @classmethod
    def normalize_legacy_fit_mode(cls, value: object) -> object:
        return {"fit": "contain", "crop": "cover"}.get(value, value)

    @model_validator(mode="after")
    def validate_media_source(self) -> "VideoSceneInput":
        if self.media_type == "generated" and self.media_path:
            raise ValueError("Generated scenes must not include an uploaded media path")
        if self.media_type != "generated" and not self.media_path:
            raise ValueError("Uploaded image and video scenes require a media path")
        return self


class VideoRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    audio_id: UUID
    resolution: VideoResolution = "1080p"
    scenes: list[VideoSceneInput] = Field(min_length=1, max_length=100)
    logo_path: str | None = Field(default=None, max_length=500)
    background_music_path: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_scene_numbers(self) -> "VideoRenderRequest":
        numbers = [scene.scene_number for scene in self.scenes]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Video scenes must be sequential and start at 1")
        return self


class VideoRenderResponse(BaseModel):
    video_id: UUID
    status: Literal["completed"]
    video_url: str
    subtitle_url: str
    subtitles_burned: bool
    resolution: VideoResolution


@dataclass(frozen=True)
class RenderScene:
    scene_number: int
    duration_seconds: int
    media_path: Path | None
    media_type: Literal["image", "video", "generated"]
    subtitle: str
    fit_mode: FitMode
    motion_type: MotionType = "automatic"
    motion_strength: MotionStrength = "subtle"
    visual_description: str = ""


@dataclass(frozen=True)
class VideoRenderResult:
    video_path: Path
    subtitle_path: Path
    subtitles_burned: bool
