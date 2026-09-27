from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import uuid4

from pydantic import ValidationError

from videos_llm.domain.production import (
    Asset,
    AttemptStatus,
    GenerationAttempt,
    SceneProduction,
    SelectionRole,
)
from videos_llm.infrastructure.ffmpeg import FfmpegError, probe_media
from videos_llm.infrastructure.production_store import (
    ProductionStoreError,
    load_scene_production,
    production_path,
    save_scene_production,
)
from videos_llm.infrastructure.yaml_project_loader import (
    ProjectValidationError,
    load_project,
)


class MediaImportError(ValueError):
    """Raised when a local media file cannot be safely imported."""


@dataclass(frozen=True)
class ImportResult:
    state: SceneProduction
    asset: Asset
    attempt: GenerationAttempt


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_suffix(mime_type: str) -> str:
    suffixes = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/flac": ".flac",
    }
    try:
        return suffixes[mime_type]
    except KeyError as error:
        raise MediaImportError(f"unsupported media type: {mime_type}") from error


def _new_attempt_id(state: SceneProduction) -> str:
    existing = {item.id for item in state.attempts}
    while True:
        candidate = f"attempt-{uuid4().hex[:12]}"
        if candidate not in existing:
            return candidate


def create_scene_production(
    project_directory: str | Path,
    scene_id: str,
) -> SceneProduction:
    try:
        loaded = load_project(project_directory)
    except ProjectValidationError as error:
        raise ProductionStoreError(str(error)) from error
    if scene_id not in {scene.id for scene in loaded.storyboard.scenes}:
        raise ProductionStoreError(f"scene {scene_id!r} is not in storyboard.yaml")
    return SceneProduction(
        schema_version=1,
        project_id=loaded.project.id,
        scene_id=scene_id,
        status="in_progress",
        attempts=[],
        assets=[],
        selections={},
    )


def select_asset(
    project_directory: str | Path,
    scene_id: str,
    role: SelectionRole | str,
    asset_id: str,
) -> SceneProduction:
    state = load_scene_production(project_directory, scene_id)
    owning_attempts = [
        item for item in state.attempts if asset_id in item.asset_ids
    ]
    if not owning_attempts:
        raise ProductionStoreError(
            f"asset {asset_id!r} does not belong to scene {scene_id}"
        )
    if all(item.status is AttemptStatus.REJECTED for item in owning_attempts):
        raise ProductionStoreError(
            f"asset {asset_id!r} belongs only to rejected attempts"
        )

    selected = dict(state.selections)
    selected[SelectionRole(role)] = asset_id
    selected_ids = set(selected.values())
    attempts = [
        item.model_copy(
            update={
                "status": (
                    AttemptStatus.REJECTED
                    if item.status is AttemptStatus.REJECTED
                    else AttemptStatus.APPROVED
                    if selected_ids.intersection(item.asset_ids)
                    else AttemptStatus.CANDIDATE
                    if item.status is AttemptStatus.APPROVED
                    else item.status
                )
            }
        )
        for item in state.attempts
    ]
    updated = state.model_copy(
        update={"selections": selected, "attempts": attempts}
    )
    updated = SceneProduction.model_validate(updated.model_dump())
    save_scene_production(project_directory, updated)
    return updated


def import_media(
    project_directory: str | Path,
    scene_id: str,
    media_path: str | Path,
    *,
    method: str = "manual",
    provider: str | None = None,
    model: str | None = None,
    prompt_path: str | None = None,
    notes: str | None = None,
    ffmpeg_executable: str | Path | None = None,
) -> ImportResult:
    source_input = Path(media_path)
    try:
        source = source_input.resolve(strict=True)
    except OSError as error:
        raise MediaImportError(
            f"could not import {source_input}: {error}"
        ) from error
    if not source.is_file():
        raise MediaImportError(f"could not import {source}: not a file")

    state_path = production_path(project_directory, scene_id)
    state = (
        load_scene_production(project_directory, scene_id)
        if state_path.is_file()
        else create_scene_production(project_directory, scene_id)
    )

    try:
        checksum = sha256_file(source)
        probed = probe_media(source, ffmpeg_executable=ffmpeg_executable)
    except (OSError, FfmpegError) as error:
        raise MediaImportError(f"could not import {source}: {error}") from error

    asset_id = f"asset-{checksum[:12]}"
    existing_asset = next(
        (asset for asset in state.assets if asset.id == asset_id),
        None,
    )
    if existing_asset is not None and existing_asset.sha256 != checksum:
        raise MediaImportError(
            f"asset id prefix collision for {asset_id}: full checksums differ"
        )

    created_destination = False
    destination: Path | None = None
    if existing_asset is None:
        suffix = canonical_suffix(probed.mime_type)
        relative = PurePosixPath(
            "media",
            scene_id,
            probed.kind.value,
            f"{asset_id}{suffix}",
        )
        destination = Path(project_directory) / Path(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            try:
                destination_checksum = sha256_file(destination)
            except OSError as error:
                raise MediaImportError(
                    f"could not inspect existing destination {destination}: {error}"
                ) from error
            if destination_checksum != checksum:
                raise MediaImportError(
                    f"destination collision for {destination}: checksums differ"
                )
        else:
            temporary = destination.with_name(
                f".{destination.name}.{uuid4().hex}.part"
            )
            try:
                shutil.copyfile(source, temporary)
                if sha256_file(temporary) != checksum:
                    raise MediaImportError(
                        f"checksum changed while copying {source}"
                    )
                temporary.replace(destination)
                created_destination = True
            except (OSError, MediaImportError) as error:
                temporary.unlink(missing_ok=True)
                if isinstance(error, MediaImportError):
                    raise
                raise MediaImportError(
                    f"could not copy {source} to {destination}: {error}"
                ) from error

        asset = Asset(
            id=asset_id,
            kind=probed.kind,
            path=relative.as_posix(),
            sha256=checksum,
            mime_type=probed.mime_type,
            created_at=datetime.now(timezone.utc),
            metadata=probed.metadata,
        )
        assets = [*state.assets, asset]
    else:
        asset = existing_asset
        assets = list(state.assets)

    try:
        is_selected = asset_id in state.selections.values()
        attempt = GenerationAttempt(
            id=_new_attempt_id(state),
            scene_id=scene_id,
            kind=asset.kind,
            created_at=datetime.now(timezone.utc),
            method=method,
            provider=provider,
            model=model,
            prompt_path=prompt_path,
            asset_ids=[asset_id],
            status=(
                AttemptStatus.APPROVED
                if is_selected
                else AttemptStatus.CANDIDATE
            ),
            notes=notes,
        )
        updated = SceneProduction.model_validate(
            state.model_copy(
                update={
                    "assets": assets,
                    "attempts": [*state.attempts, attempt],
                }
            ).model_dump()
        )
        save_scene_production(project_directory, updated)
    except (ProductionStoreError, ValidationError, ValueError) as error:
        if created_destination and destination is not None:
            destination.unlink(missing_ok=True)
        raise MediaImportError(f"could not import {source}: {error}") from error

    return ImportResult(state=updated, asset=asset, attempt=attempt)
