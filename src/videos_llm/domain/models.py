from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ProjectId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
SceneId = Annotated[str, StringConstraints(pattern=r"^scene-[0-9]{3,}$")]
LanguageTag = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"),
]


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    IN_PRODUCTION = "in_production"
    READY = "ready"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"


class SceneStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    BLOCKED = "blocked"


class MediaFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aspect_ratio: Annotated[
        str,
        StringConstraints(pattern=r"^[1-9][0-9]*:[1-9][0-9]*$"),
    ]
    width: PositiveInt
    height: PositiveInt
    fps: PositiveFloat

    @model_validator(mode="after")
    def validate_aspect_ratio(self) -> MediaFormat:
        ratio_width, ratio_height = (int(part) for part in self.aspect_ratio.split(":"))
        declared = ratio_width / ratio_height
        actual = self.width / self.height
        relative_difference = abs(actual - declared) / declared
        if relative_difference > 0.01:
            raise ValueError(
                "aspect_ratio is incompatible with width and height "
                "using the 1% tolerance"
            )
        return self


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    id: ProjectId
    title: NonEmptyStr
    language: LanguageTag
    created_at: datetime
    status: ProjectStatus
    format: MediaFormat

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include timezone information")
        return value


class Audience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: NonEmptyStr
    desired_reaction: list[NonEmptyStr] = Field(default_factory=list)


class CreativeDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premise: NonEmptyStr
    hook: NonEmptyStr
    key_message: NonEmptyStr
    tone: list[NonEmptyStr] = Field(default_factory=list)
    narrative_arc: list[NonEmptyStr] = Field(default_factory=list)


class VisualDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    era: NonEmptyStr
    style: list[NonEmptyStr] = Field(default_factory=list)
    color_notes: list[NonEmptyStr] = Field(default_factory=list)
    texture: list[NonEmptyStr] = Field(default_factory=list)
    references: list[NonEmptyStr] = Field(default_factory=list)


class AudioDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narration_style: NonEmptyStr
    music_style: NonEmptyStr
    sound_notes: list[NonEmptyStr] = Field(default_factory=list)


class CreativeConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_include: list[NonEmptyStr] = Field(default_factory=list)
    avoid: list[NonEmptyStr] = Field(default_factory=list)


class ContentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    objective: NonEmptyStr
    audience: Audience
    creative: CreativeDirection
    visual_direction: VisualDirection
    audio_direction: AudioDirection
    constraints: CreativeConstraints
    success_criteria: list[NonEmptyStr] = Field(default_factory=list)


class DialogueLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: NonEmptyStr
    text: NonEmptyStr


class ScriptScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SceneId
    narration: NonEmptyStr | None = None
    dialogue: list[DialogueLine] = Field(default_factory=list)
    on_screen_text: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_content(self) -> ScriptScene:
        if self.narration is None and not self.dialogue and not self.on_screen_text:
            raise ValueError(
                "script scene must contain at least one narration, dialogue, "
                "or on-screen text entry"
            )
        return self


class Script(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    scenes: list[ScriptScene]

    @field_validator("scenes")
    @classmethod
    def require_unique_scene_ids(cls, scenes: list[ScriptScene]) -> list[ScriptScene]:
        seen: set[str] = set()
        for scene in scenes:
            if scene.id in seen:
                raise ValueError(f"duplicate script scene id: {scene.id}")
            seen.add(scene.id)
        return scenes


class CameraDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    framing: NonEmptyStr
    angle: NonEmptyStr
    movement: NonEmptyStr
    lens: NonEmptyStr | None = None


class LightingDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: NonEmptyStr
    notes: NonEmptyStr | None = None


class SceneVisual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: NonEmptyStr
    composition: NonEmptyStr
    camera: CameraDirection
    lighting: LightingDirection
    mood: list[NonEmptyStr] = Field(default_factory=list)


class SceneAudio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ambience: NonEmptyStr | None = None
    sfx: list[NonEmptyStr] = Field(default_factory=list)
    music_note: NonEmptyStr | None = None


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SceneId
    order: PositiveInt
    duration_seconds: PositiveFloat
    purpose: NonEmptyStr
    status: SceneStatus
    script_scene_id: SceneId
    visual: SceneVisual
    audio: SceneAudio


class Storyboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    version: PositiveInt
    status: DocumentStatus
    scenes: list[Scene]

    @field_validator("scenes")
    @classmethod
    def require_unique_scenes(cls, scenes: list[Scene]) -> list[Scene]:
        seen_ids: set[str] = set()
        seen_orders: set[int] = set()
        for scene in scenes:
            if scene.id in seen_ids:
                raise ValueError(f"duplicate storyboard scene id: {scene.id}")
            if scene.order in seen_orders:
                raise ValueError(f"duplicate storyboard scene order: {scene.order}")
            seen_ids.add(scene.id)
            seen_orders.add(scene.order)
        return scenes
