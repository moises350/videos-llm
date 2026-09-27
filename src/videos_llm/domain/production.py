from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

from videos_llm.domain.models import (
    NonEmptyStr,
    PositiveFiniteFloat,
    ProjectId,
    SceneId,
)

AssetId = Annotated[str, Field(pattern=r"^asset-[a-f0-9]{12}$")]
AttemptId = Annotated[str, Field(pattern=r"^attempt-[a-f0-9]{12}$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class AssetKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class AttemptStatus(str, Enum):
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    APPROVED = "approved"


class ProductionStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    BLOCKED = "blocked"


class SelectionRole(str, Enum):
    KEY_IMAGE = "key_image"
    VIDEO = "video"
    NARRATION = "narration"
    AMBIENCE = "ambience"
    MUSIC = "music"
    SFX = "sfx"


class ImageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: PositiveInt
    height: PositiveInt


class VideoMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: PositiveInt
    height: PositiveInt
    duration_seconds: PositiveFiniteFloat
    frame_rate: PositiveFiniteFloat
    codec: NonEmptyStr
    has_audio: bool = False


class AudioMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: PositiveFiniteFloat
    sample_rate: PositiveInt
    channels: PositiveInt
    codec: NonEmptyStr


def _is_unsafe_project_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return (
        posix.is_absolute()
        or windows.is_absolute()
        or ".." in posix.parts
        or "\\" in value
    )


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must include timezone information")
    return value


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: AssetId
    kind: AssetKind
    path: NonEmptyStr
    sha256: Sha256
    mime_type: Annotated[str, Field(pattern=r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")]
    created_at: datetime
    metadata: ImageMetadata | VideoMetadata | AudioMetadata

    @field_validator("path")
    @classmethod
    def require_safe_relative_posix_path(cls, value: str) -> str:
        if _is_unsafe_project_path(value):
            raise ValueError("path must be a safe project-relative POSIX path")
        return value

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @model_validator(mode="after")
    def require_matching_metadata(self) -> Asset:
        expected = {
            AssetKind.IMAGE: ImageMetadata,
            AssetKind.VIDEO: VideoMetadata,
            AssetKind.AUDIO: AudioMetadata,
        }[self.kind]
        if not isinstance(self.metadata, expected):
            raise ValueError(f"{self.kind.value} asset has incompatible metadata")
        return self


class GenerationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: AttemptId
    scene_id: SceneId
    kind: AssetKind
    created_at: datetime
    method: NonEmptyStr
    provider: NonEmptyStr | None = None
    model: NonEmptyStr | None = None
    prompt_path: NonEmptyStr | None = None
    asset_ids: list[AssetId] = Field(min_length=1)
    status: AttemptStatus = AttemptStatus.CANDIDATE
    notes: NonEmptyStr | None = None

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @field_validator("prompt_path")
    @classmethod
    def require_safe_prompt_path(cls, value: str | None) -> str | None:
        if value is not None and _is_unsafe_project_path(value):
            raise ValueError(
                "prompt_path must be a safe project-relative POSIX path"
            )
        return value


class SceneProduction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    scene_id: SceneId
    status: ProductionStatus
    attempts: list[GenerationAttempt] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    selections: dict[SelectionRole, AssetId] = Field(default_factory=dict)
    review_notes: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> SceneProduction:
        assets = {asset.id: asset for asset in self.assets}
        if len(assets) != len(self.assets):
            raise ValueError("duplicate asset id")

        attempts = {item.id: item for item in self.attempts}
        if len(attempts) != len(self.attempts):
            raise ValueError("duplicate attempt id")

        asset_attempts: dict[str, list[GenerationAttempt]] = {}
        for item in self.attempts:
            if item.scene_id != self.scene_id:
                raise ValueError(
                    f"attempt {item.id} belongs to {item.scene_id}, "
                    f"not {self.scene_id}"
                )
            for asset_id in item.asset_ids:
                if asset_id not in assets:
                    raise ValueError(
                        f"attempt {item.id} references missing asset {asset_id}"
                    )
                if assets[asset_id].kind != item.kind:
                    raise ValueError(
                        f"attempt {item.id} kind does not match asset {asset_id}"
                    )
                asset_attempts.setdefault(asset_id, []).append(item)

        compatibility = {
            SelectionRole.KEY_IMAGE: AssetKind.IMAGE,
            SelectionRole.VIDEO: AssetKind.VIDEO,
            SelectionRole.NARRATION: AssetKind.AUDIO,
            SelectionRole.AMBIENCE: AssetKind.AUDIO,
            SelectionRole.MUSIC: AssetKind.AUDIO,
            SelectionRole.SFX: AssetKind.AUDIO,
        }
        for role, asset_id in self.selections.items():
            if asset_id not in assets:
                raise ValueError(
                    f"selection {role.value} references missing asset {asset_id}"
                )
            if assets[asset_id].kind != compatibility[role]:
                raise ValueError(
                    f"selection {role.value} is incompatible with "
                    f"{assets[asset_id].kind.value} asset {asset_id}"
                )
            if not any(
                item.status is AttemptStatus.APPROVED
                for item in asset_attempts.get(asset_id, [])
            ):
                raise ValueError(
                    f"selection {role.value} must belong to an approved attempt"
                )
        return self
