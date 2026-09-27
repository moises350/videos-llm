from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from videos_llm.application.production_service import sha256_file
from videos_llm.domain.composition import (
    AudioItem,
    CompositionPlan,
    VisualItem,
)
from videos_llm.domain.models import Project
from videos_llm.domain.production import (
    Asset,
    AudioMetadata,
    SelectionRole,
    VideoMetadata,
)
from videos_llm.infrastructure.production_store import (
    ProductionStoreError,
    load_scene_production,
)
from videos_llm.infrastructure.yaml_project_loader import (
    ProjectValidationError,
    load_project,
)


@dataclass(frozen=True)
class ResolvedVisualItem:
    item: VisualItem
    asset: Asset
    path: Path


@dataclass(frozen=True)
class ResolvedAudioItem:
    item: AudioItem
    asset: Asset
    path: Path
    effective_duration_seconds: float


@dataclass(frozen=True)
class ResolvedComposition:
    project_directory: Path
    project: Project
    plan: CompositionPlan
    visual_items: list[ResolvedVisualItem]
    audio_items: list[ResolvedAudioItem]


class CompositionError(ValueError):
    """Raised when a composition plan cannot be resolved into safe assets."""


def load_composition_plan(
    project_directory: str | Path,
) -> CompositionPlan:
    path = Path(project_directory) / "composition.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return CompositionPlan.model_validate(raw)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        raise CompositionError(f"{path}: {error}") from error


def _asset_path(
    directory: Path,
    scene_id: str,
    role: SelectionRole,
    asset: Asset,
) -> Path:
    candidate = (
        directory / Path(*PurePosixPath(asset.path).parts)
    ).resolve()
    try:
        candidate.relative_to(directory)
    except ValueError as error:
        raise CompositionError(
            f"scene {scene_id} role {role.value} asset {asset.id} "
            "escapes the project directory"
        ) from error
    if not candidate.is_file():
        raise CompositionError(
            f"scene {scene_id} role {role.value} asset {asset.id} "
            f"is missing at {candidate}"
        )
    try:
        actual_checksum = sha256_file(candidate)
    except OSError as error:
        raise CompositionError(
            f"scene {scene_id} role {role.value} asset {asset.id} "
            f"could not be read: {error}"
        ) from error
    if actual_checksum != asset.sha256:
        raise CompositionError(
            f"scene {scene_id} role {role.value} asset {asset.id} "
            "has a checksum mismatch"
        )
    return candidate


def resolve_composition(
    project_directory: str | Path,
) -> ResolvedComposition:
    directory = Path(project_directory).resolve()
    try:
        loaded = load_project(directory)
    except ProjectValidationError as error:
        raise CompositionError(str(error)) from error
    plan = load_composition_plan(directory)
    if plan.project_id != loaded.project.id:
        raise CompositionError(
            f"composition project_id {plan.project_id!r} does not match "
            f"project.yaml id {loaded.project.id!r}"
        )

    known_scenes = {scene.id for scene in loaded.storyboard.scenes}
    required_scenes = {
        item.scene_id for item in [*plan.visual_items, *plan.audio_items]
    }
    unknown_scenes = sorted(required_scenes - known_scenes)
    if unknown_scenes:
        raise CompositionError(
            "composition references storyboard scenes that do not exist: "
            + ", ".join(unknown_scenes)
        )

    states = {}
    for scene_id in sorted(required_scenes):
        try:
            states[scene_id] = load_scene_production(directory, scene_id)
        except ProductionStoreError as error:
            raise CompositionError(f"scene {scene_id}: {error}") from error

    def selected_asset(scene_id: str, role: SelectionRole) -> tuple[Asset, Path]:
        state = states[scene_id]
        asset_id = state.selections.get(role)
        if asset_id is None:
            raise CompositionError(
                f"scene {scene_id} role {role.value} has no selected asset"
            )
        asset = next(
            (candidate for candidate in state.assets if candidate.id == asset_id),
            None,
        )
        if asset is None:
            raise CompositionError(
                f"scene {scene_id} role {role.value} selected missing "
                f"asset {asset_id}"
            )
        return asset, _asset_path(directory, scene_id, role, asset)

    resolved_visuals: list[ResolvedVisualItem] = []
    for item in plan.visual_items:
        role = SelectionRole(item.role)
        asset, path = selected_asset(item.scene_id, role)
        if isinstance(asset.metadata, VideoMetadata):
            required_duration = item.trim_start_seconds + item.duration_seconds
            if required_duration > asset.metadata.duration_seconds + 1e-6:
                raise CompositionError(
                    f"scene {item.scene_id} role {role.value} asset {asset.id} "
                    "duration is shorter than the requested trim and timeline"
                )
        resolved_visuals.append(
            ResolvedVisualItem(item=item, asset=asset, path=path)
        )

    resolved_audio: list[ResolvedAudioItem] = []
    for item in plan.audio_items:
        role = SelectionRole(item.role)
        asset, path = selected_asset(item.scene_id, role)
        if not isinstance(asset.metadata, AudioMetadata):
            raise CompositionError(
                f"scene {item.scene_id} role {role.value} asset {asset.id} "
                "does not contain audio metadata"
            )
        available = asset.metadata.duration_seconds - item.trim_start_seconds
        program_remaining = plan.duration_seconds - item.start_seconds
        requested = item.duration_seconds
        effective = min(available, program_remaining) if requested is None else requested
        if available <= 0 or effective <= 0 or effective > available + 1e-6:
            raise CompositionError(
                f"scene {item.scene_id} role {role.value} asset {asset.id} "
                "duration is shorter than the requested trim and timeline"
            )
        resolved_audio.append(
            ResolvedAudioItem(
                item=item,
                asset=asset,
                path=path,
                effective_duration_seconds=effective,
            )
        )

    return ResolvedComposition(
        project_directory=directory,
        project=loaded.project,
        plan=plan,
        visual_items=resolved_visuals,
        audio_items=resolved_audio,
    )


def render_composition(
    project_directory: str | Path,
    *,
    preview: bool = False,
    output_path: str | Path | None = None,
    overwrite: bool = False,
    ffmpeg_executable: str | Path | None = None,
) -> Path:
    from videos_llm.infrastructure.compositor import (
        RenderProfile,
        render_resolved_composition,
    )

    resolved = resolve_composition(project_directory)
    profile = (
        RenderProfile.preview()
        if preview
        else RenderProfile.final(resolved.project)
    )
    default_name = (
        "preview.mp4" if preview else resolved.plan.output_filename
    )
    destination = (
        Path(output_path)
        if output_path is not None
        else resolved.project_directory / "output" / default_name
    )
    return render_resolved_composition(
        resolved,
        destination,
        profile,
        overwrite=overwrite,
        ffmpeg_executable=ffmpeg_executable,
    )
