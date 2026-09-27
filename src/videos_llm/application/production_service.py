from pathlib import Path

from videos_llm.domain.production import (
    AttemptStatus,
    SceneProduction,
    SelectionRole,
)
from videos_llm.infrastructure.production_store import (
    ProductionStoreError,
    load_scene_production,
    save_scene_production,
)
from videos_llm.infrastructure.yaml_project_loader import (
    ProjectValidationError,
    load_project,
)


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
