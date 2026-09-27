from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from videos_llm.domain.production import (
    Asset,
    AttemptStatus,
    GenerationAttempt,
    ImageMetadata,
    SceneProduction,
)


def image_asset(asset_id: str = "asset-a1b2c3d4e5f6") -> Asset:
    return Asset(
        id=asset_id,
        kind="image",
        path=f"media/scene-001/image/{asset_id}.png",
        sha256="a" * 64,
        mime_type="image/png",
        created_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        metadata=ImageMetadata(width=1080, height=1920),
    )


def attempt(asset_id: str = "asset-a1b2c3d4e5f6") -> GenerationAttempt:
    return GenerationAttempt(
        id="attempt-001122334455",
        scene_id="scene-001",
        kind="image",
        created_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        method="manual",
        asset_ids=[asset_id],
        status="candidate",
    )


@pytest.mark.parametrize(
    "path",
    ["../outside.mp4", "/outside.mp4", "C:/outside.mp4", r"C:\outside.mp4"],
)
def test_asset_rejects_unsafe_project_relative_path(path: str) -> None:
    data = image_asset().model_dump()
    data["path"] = path
    with pytest.raises(ValidationError, match="project-relative"):
        Asset.model_validate(data)


def test_asset_kind_must_match_metadata_type() -> None:
    data = image_asset().model_dump()
    data["kind"] = "video"
    with pytest.raises(ValidationError, match="metadata"):
        Asset.model_validate(data)


def test_asset_requires_timezone_aware_creation_time() -> None:
    data = image_asset().model_dump()
    data["created_at"] = datetime(2026, 9, 27, 12)
    with pytest.raises(ValidationError, match="timezone"):
        Asset.model_validate(data)


@pytest.mark.parametrize("prompt_path", ["../prompt.md", "/prompt.md", r"C:\prompt.md"])
def test_attempt_rejects_unsafe_prompt_path(prompt_path: str) -> None:
    data = attempt().model_dump()
    data["prompt_path"] = prompt_path
    with pytest.raises(ValidationError, match="project-relative"):
        GenerationAttempt.model_validate(data)


def test_attempt_requires_an_asset() -> None:
    data = attempt().model_dump()
    data["asset_ids"] = []
    with pytest.raises(ValidationError):
        GenerationAttempt.model_validate(data)


def test_scene_production_rejects_unknown_attempt_asset() -> None:
    with pytest.raises(ValidationError, match="missing asset"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="in_progress",
            attempts=[attempt("asset-deadbeef0000")],
            assets=[image_asset()],
            selections={},
        )


def test_scene_production_rejects_duplicate_asset_ids() -> None:
    asset = image_asset()
    with pytest.raises(ValidationError, match="duplicate asset id"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="in_progress",
            attempts=[],
            assets=[asset, asset.model_copy()],
            selections={},
        )


def test_scene_production_rejects_attempt_from_another_scene() -> None:
    other_attempt = attempt().model_copy(update={"scene_id": "scene-002"})
    with pytest.raises(ValidationError, match="scene-002.*scene-001"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="in_progress",
            attempts=[other_attempt],
            assets=[image_asset()],
            selections={},
        )


def test_scene_production_rejects_incompatible_selection_role() -> None:
    with pytest.raises(ValidationError, match="video.*image"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="review",
            attempts=[attempt()],
            assets=[image_asset()],
            selections={"video": "asset-a1b2c3d4e5f6"},
        )


def test_scene_production_rejects_selection_from_candidate_attempt() -> None:
    with pytest.raises(ValidationError, match="approved attempt"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="review",
            attempts=[attempt()],
            assets=[image_asset()],
            selections={"key_image": "asset-a1b2c3d4e5f6"},
        )


def test_scene_production_accepts_selected_key_image() -> None:
    state = SceneProduction(
        schema_version=1,
        project_id="sample-project",
        scene_id="scene-001",
        status="review",
        attempts=[attempt().model_copy(update={"status": AttemptStatus.APPROVED})],
        assets=[image_asset()],
        selections={"key_image": "asset-a1b2c3d4e5f6"},
    )
    assert state.selections["key_image"] == "asset-a1b2c3d4e5f6"
