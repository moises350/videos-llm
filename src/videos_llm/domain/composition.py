from __future__ import annotations

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
from videos_llm.domain.production import SelectionRole

NonNegativeFiniteFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class VisualItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(pattern=r"^visual-[a-z0-9-]+$")]
    scene_id: SceneId
    role: Literal[SelectionRole.KEY_IMAGE, SelectionRole.VIDEO]
    start_seconds: NonNegativeFiniteFloat
    duration_seconds: PositiveFiniteFloat
    trim_start_seconds: NonNegativeFiniteFloat = 0
    transition: Literal["hard_cut", "dissolve"] = "hard_cut"
    transition_seconds: NonNegativeFiniteFloat = 0
    motion: Literal["static", "push_in", "pull_out"] = "static"
    analog_preset: Literal[
        "none", "betacam_light", "betacam_heavy"
    ] = "none"

    @model_validator(mode="after")
    def validate_transition_fields(self) -> VisualItem:
        if self.transition == "hard_cut" and self.transition_seconds != 0:
            raise ValueError(
                "hard_cut transition_seconds must be zero"
            )
        if self.transition == "dissolve" and self.transition_seconds <= 0:
            raise ValueError(
                "dissolve transition_seconds must be positive"
            )
        return self


class AudioItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(pattern=r"^audio-[a-z0-9-]+$")]
    scene_id: SceneId
    role: Literal[
        SelectionRole.NARRATION,
        SelectionRole.AMBIENCE,
        SelectionRole.MUSIC,
        SelectionRole.SFX,
    ]
    start_seconds: NonNegativeFiniteFloat
    duration_seconds: PositiveFiniteFloat | None = None
    trim_start_seconds: NonNegativeFiniteFloat = 0
    fade_in_seconds: NonNegativeFiniteFloat = 0
    fade_out_seconds: NonNegativeFiniteFloat = 0
    gain_db: FiniteFloat = 0

    @model_validator(mode="after")
    def validate_fades(self) -> AudioItem:
        if (
            self.duration_seconds is not None
            and self.fade_in_seconds + self.fade_out_seconds
            > self.duration_seconds
        ):
            raise ValueError("audio fades cannot exceed item duration")
        return self


class TextOverlay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(pattern=r"^overlay-[a-z0-9-]+$")]
    text: NonEmptyStr
    start_seconds: NonNegativeFiniteFloat
    duration_seconds: PositiveFiniteFloat
    position: Literal["top", "center", "bottom"] = "bottom"
    font_size: PositiveInt = 64
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")] = "#FFFFFF"


class CompositionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    visual_items: list[VisualItem] = Field(min_length=1)
    audio_items: list[AudioItem] = Field(default_factory=list)
    overlays: list[TextOverlay] = Field(default_factory=list)
    output_filename: NonEmptyStr

    @field_validator("output_filename")
    @classmethod
    def require_safe_mp4_path(cls, value: str) -> str:
        posix = PurePosixPath(value)
        windows = PureWindowsPath(value)
        if (
            posix.suffix.lower() != ".mp4"
            or posix.is_absolute()
            or windows.is_absolute()
            or ".." in posix.parts
            or "\\" in value
        ):
            raise ValueError(
                "output filename must be a safe project-relative MP4 path"
            )
        return value

    @property
    def duration_seconds(self) -> float:
        last = self.visual_items[-1]
        return last.start_seconds + last.duration_seconds

    @model_validator(mode="after")
    def validate_timeline(self) -> CompositionPlan:
        self._require_unique_ids("visual", self.visual_items)
        self._require_unique_ids("audio", self.audio_items)
        self._require_unique_ids("overlay", self.overlays)

        tolerance = 1e-6
        first = self.visual_items[0]
        if abs(first.start_seconds) > tolerance:
            raise ValueError("visual timeline must start at zero")
        if first.transition != "hard_cut" or first.transition_seconds != 0:
            raise ValueError("first visual item must use a hard cut")

        for previous, current in zip(
            self.visual_items,
            self.visual_items[1:],
            strict=False,
        ):
            previous_end = previous.start_seconds + previous.duration_seconds
            if current.transition == "dissolve":
                if current.transition_seconds >= min(
                    previous.duration_seconds,
                    current.duration_seconds,
                ):
                    raise ValueError(
                        f"visual item {current.id} transition_seconds must be "
                        "shorter than both adjacent items"
                    )
                expected_start = previous_end - current.transition_seconds
            else:
                expected_start = previous_end

            difference = current.start_seconds - expected_start
            if difference < -tolerance:
                raise ValueError(
                    f"visual timeline overlap before {current.id}"
                )
            if difference > tolerance:
                raise ValueError(f"visual timeline gap before {current.id}")

        program_duration = self.duration_seconds
        for item in self.audio_items:
            if item.start_seconds >= program_duration:
                raise ValueError(
                    f"audio item {item.id} starts outside the program"
                )
            if (
                item.duration_seconds is not None
                and item.start_seconds + item.duration_seconds
                > program_duration + tolerance
            ):
                raise ValueError(f"audio item {item.id} ends outside the program")

        for overlay in self.overlays:
            if (
                overlay.start_seconds + overlay.duration_seconds
                > program_duration + tolerance
            ):
                raise ValueError(
                    f"overlay {overlay.id} ends outside the program"
                )
        return self

    @staticmethod
    def _require_unique_ids(kind: str, items: list[object]) -> None:
        identifiers = [getattr(item, "id") for item in items]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"duplicate {kind} item id")
