from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from videos_llm.domain.models import ContentBrief, Project, Script, Storyboard


class ProjectValidationError(ValueError):
    """Raised when a project directory cannot be loaded as a valid project."""


@dataclass(frozen=True)
class LoadedProject:
    project: Project
    brief: ContentBrief
    script: Script
    storyboard: Storyboard


ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as error:
        raise ProjectValidationError(f"{path.name}: {error}") from error

    if not isinstance(content, dict):
        raise ProjectValidationError(
            f"{path.name}: top-level YAML value must be a mapping"
        )

    try:
        return model_type.model_validate(content)
    except ValidationError as error:
        raise ProjectValidationError(f"{path.name}: {error}") from error


def load_project(project_directory: str | Path) -> LoadedProject:
    directory = Path(project_directory)
    required = ("project.yaml", "brief.yaml", "script.yaml", "storyboard.yaml")
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise ProjectValidationError(
            f"missing required project files: {', '.join(missing)}"
        )

    project = _load_model(directory / "project.yaml", Project)
    brief = _load_model(directory / "brief.yaml", ContentBrief)
    script = _load_model(directory / "script.yaml", Script)
    storyboard = _load_model(directory / "storyboard.yaml", Storyboard)

    for filename, project_id in (
        ("brief.yaml", brief.project_id),
        ("script.yaml", script.project_id),
        ("storyboard.yaml", storyboard.project_id),
    ):
        if project_id != project.id:
            raise ProjectValidationError(
                f"{filename}: project_id {project_id!r} does not match "
                f"project.yaml id {project.id!r}"
            )

    script_scene_ids = {scene.id for scene in script.scenes}
    for scene in storyboard.scenes:
        if scene.script_scene_id not in script_scene_ids:
            raise ProjectValidationError(
                f"storyboard.yaml: scene {scene.id!r} references missing "
                f"script scene {scene.script_scene_id!r}"
            )

    return LoadedProject(
        project=project,
        brief=brief,
        script=script,
        storyboard=storyboard,
    )
