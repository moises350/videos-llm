from datetime import datetime, timezone
from pathlib import Path

import pytest

from project_factory import write_creative_project
from videos_llm.application.production_service import (
    create_scene_production,
    select_asset,
)
from videos_llm.domain.production import (
    Asset,
    AttemptStatus,
    GenerationAttempt,
    ImageMetadata,
)
from videos_llm.infrastructure.production_store import (
    ProductionStoreError,
    load_scene_production,
    production_path,
    save_scene_production,
)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return write_creative_project(tmp_path)


def image_asset(asset_id: str, checksum_character: str) -> Asset:
    return Asset(
        id=asset_id,
        kind="image",
        path=f"media/scene-001/image/{asset_id}.png",
        sha256=checksum_character * 64,
        mime_type="image/png",
        created_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        metadata=ImageMetadata(width=1080, height=1920),
    )


def image_attempt(attempt_id: str, asset_id: str) -> GenerationAttempt:
    return GenerationAttempt(
        id=attempt_id,
        scene_id="scene-001",
        kind="image",
        created_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        method="manual",
        asset_ids=[asset_id],
        status="candidate",
    )


def two_image_attempt_state(project_dir: Path) -> tuple[str, str]:
    first = "asset-a1b2c3d4e5f6"
    second = "asset-001122334455"
    state = create_scene_production(project_dir, "scene-001").model_copy(
        update={
            "assets": [image_asset(first, "a"), image_asset(second, "b")],
            "attempts": [
                image_attempt("attempt-a1b2c3d4e5f6", first),
                image_attempt("attempt-001122334455", second),
            ],
        }
    )
    save_scene_production(project_dir, state)
    return first, second


def test_save_and_load_scene_production_round_trip(project_dir: Path) -> None:
    state = create_scene_production(project_dir, "scene-001")
    saved = save_scene_production(project_dir, state)
    assert saved == project_dir / "production" / "scene-001" / "production.yaml"
    assert load_scene_production(project_dir, "scene-001") == state


def test_create_rejects_scene_absent_from_storyboard(project_dir: Path) -> None:
    with pytest.raises(ProductionStoreError, match="scene-999"):
        create_scene_production(project_dir, "scene-999")


def test_production_path_rejects_path_traversal(project_dir: Path) -> None:
    with pytest.raises(ProductionStoreError, match="scene id"):
        production_path(project_dir, "../outside")


def test_store_rejects_mismatched_project(project_dir: Path) -> None:
    state = create_scene_production(project_dir, "scene-001").model_copy(
        update={"project_id": "another-project"}
    )
    with pytest.raises(ProductionStoreError, match="another-project.*sample-project"):
        save_scene_production(project_dir, state)


def test_select_asset_preserves_history_and_recomputes_approval(
    project_dir: Path,
) -> None:
    first, second = two_image_attempt_state(project_dir)
    selected_first = select_asset(project_dir, "scene-001", "key_image", first)
    assert selected_first.selections["key_image"] == first

    selected_second = select_asset(project_dir, "scene-001", "key_image", second)
    assert len(selected_second.assets) == 2
    assert len(selected_second.attempts) == 2
    assert selected_second.selections["key_image"] == second
    statuses = {
        item.asset_ids[0]: item.status.value for item in selected_second.attempts
    }
    assert statuses == {first: "candidate", second: "approved"}


def test_select_rejects_asset_owned_only_by_rejected_attempt(
    project_dir: Path,
) -> None:
    first, _ = two_image_attempt_state(project_dir)
    state = load_scene_production(project_dir, "scene-001")
    state = state.model_copy(
        update={
            "attempts": [
                item.model_copy(update={"status": AttemptStatus.REJECTED})
                if first in item.asset_ids
                else item
                for item in state.attempts
            ]
        }
    )
    save_scene_production(project_dir, state)
    with pytest.raises(ProductionStoreError, match="rejected"):
        select_asset(project_dir, "scene-001", "key_image", first)


def test_failed_atomic_write_preserves_previous_document(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = create_scene_production(project_dir, "scene-001")
    path = save_scene_production(project_dir, state)
    before = path.read_bytes()

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(ProductionStoreError, match="disk full"):
        save_scene_production(
            project_dir,
            state.model_copy(update={"review_notes": ["changed"]}),
        )
    assert path.read_bytes() == before
