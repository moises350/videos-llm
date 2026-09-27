from pathlib import Path

import yaml
from pydantic import TypeAdapter, ValidationError

from videos_llm.domain.models import SceneId
from videos_llm.domain.production import SceneProduction
from videos_llm.infrastructure.yaml_project_loader import (
    ProjectValidationError,
    load_project,
)


class ProductionStoreError(ValueError):
    """Raised when per-scene production state cannot be safely persisted."""


def _validated_scene_id(scene_id: str) -> str:
    try:
        return TypeAdapter(SceneId).validate_python(scene_id)
    except ValidationError as error:
        raise ProductionStoreError(f"invalid scene id {scene_id!r}: {error}") from error


def production_path(project_directory: str | Path, scene_id: str) -> Path:
    valid_scene_id = _validated_scene_id(scene_id)
    return (
        Path(project_directory)
        / "production"
        / valid_scene_id
        / "production.yaml"
    )


def _validate_project_context(
    project_directory: str | Path,
    state: SceneProduction,
) -> None:
    try:
        loaded = load_project(project_directory)
    except ProjectValidationError as error:
        raise ProductionStoreError(str(error)) from error

    if state.project_id != loaded.project.id:
        raise ProductionStoreError(
            f"production project_id {state.project_id!r} does not match "
            f"project.yaml id {loaded.project.id!r}"
        )
    scene_ids = {scene.id for scene in loaded.storyboard.scenes}
    if state.scene_id not in scene_ids:
        raise ProductionStoreError(
            f"production scene {state.scene_id!r} is not in storyboard.yaml"
        )


def load_scene_production(
    project_directory: str | Path,
    scene_id: str,
) -> SceneProduction:
    path = production_path(project_directory, scene_id)
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        state = SceneProduction.model_validate(content)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        raise ProductionStoreError(f"{path}: {error}") from error
    if state.scene_id != scene_id:
        raise ProductionStoreError(
            f"{path}: expected scene {scene_id}, found {state.scene_id}"
        )
    _validate_project_context(project_directory, state)
    return state


def save_scene_production(
    project_directory: str | Path,
    state: SceneProduction,
) -> Path:
    _validate_project_context(project_directory, state)
    path = production_path(project_directory, state.scene_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".yaml.tmp")
    payload = yaml.safe_dump(
        state.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
    )
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ProductionStoreError(f"{path}: {error}") from error
    return path
