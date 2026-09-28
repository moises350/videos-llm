from pathlib import Path

import pytest
import yaml

from media_factory import make_audio, make_image, make_video
from project_factory import write_creative_project
from videos_llm.application.composition_service import (
    CompositionError,
    load_composition_plan,
    resolve_composition,
)
from videos_llm.application.production_service import (
    create_scene_production,
    import_media,
    select_asset,
)
from videos_llm.infrastructure.ffmpeg import get_ffmpeg_executable
from videos_llm.infrastructure.production_store import (
    load_scene_production,
    save_scene_production,
)
from videos_llm.infrastructure.yaml_project_loader import load_project


def valid_single_scene_plan(role: str = "key_image") -> dict:
    return {
        "schema_version": 1,
        "project_id": "sample-project",
        "visual_items": [
            {
                "id": "visual-main",
                "scene_id": "scene-001",
                "role": role,
                "start_seconds": 0,
                "duration_seconds": 3,
            }
        ],
        "audio_items": [],
        "overlays": [],
        "output_filename": "final.mp4",
    }


def write_composition(project_dir: Path, content: dict) -> Path:
    path = project_dir / "composition.yaml"
    path.write_text(
        yaml.safe_dump(content, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return write_creative_project(tmp_path / "project")


@pytest.fixture
def project_with_selection(project_dir: Path, tmp_path: Path) -> Path:
    imported = import_media(
        project_dir,
        "scene-001",
        make_image(tmp_path / "selected.png"),
    )
    select_asset(project_dir, "scene-001", "key_image", imported.asset.id)
    write_composition(project_dir, valid_single_scene_plan())
    return project_dir


def test_load_composition_plan_returns_validated_model(project_dir: Path) -> None:
    write_composition(project_dir, valid_single_scene_plan())
    assert load_composition_plan(project_dir).project_id == "sample-project"


def test_resolver_returns_absolute_selected_paths(
    project_with_selection: Path,
) -> None:
    resolved = resolve_composition(project_with_selection)
    assert resolved.visual_items[0].path.is_absolute()
    assert resolved.visual_items[0].asset.id.startswith("asset-")


def test_resolver_rejects_changed_selected_asset(
    project_with_selection: Path,
) -> None:
    state = load_scene_production(project_with_selection, "scene-001")
    asset_id = state.selections["key_image"]
    asset = next(item for item in state.assets if item.id == asset_id)
    (project_with_selection / asset.path).write_bytes(b"changed")
    with pytest.raises(
        CompositionError,
        match=rf"scene-001.*key_image.*{asset_id}.*checksum",
    ):
        resolve_composition(project_with_selection)


def test_resolver_rejects_missing_selection(project_dir: Path) -> None:
    save_scene_production(
        project_dir,
        create_scene_production(project_dir, "scene-001"),
    )
    write_composition(project_dir, valid_single_scene_plan(role="key_image"))
    with pytest.raises(
        CompositionError,
        match="scene-001.*key_image.*selected",
    ):
        resolve_composition(project_dir)


def test_resolver_rejects_video_shorter_than_timeline(
    project_dir: Path,
    tmp_path: Path,
) -> None:
    imported = import_media(
        project_dir,
        "scene-001",
        make_video(tmp_path / "short.mp4", get_ffmpeg_executable()),
    )
    select_asset(project_dir, "scene-001", "video", imported.asset.id)
    write_composition(project_dir, valid_single_scene_plan(role="video"))
    with pytest.raises(CompositionError, match="scene-001.*video.*duration"):
        resolve_composition(project_dir)


def test_resolver_allows_sub_frame_video_duration_rounding(
    project_dir: Path,
    tmp_path: Path,
) -> None:
    imported = import_media(
        project_dir,
        "scene-001",
        make_video(tmp_path / "rounded.mp4", get_ffmpeg_executable()),
    )
    select_asset(project_dir, "scene-001", "video", imported.asset.id)
    metadata = imported.asset.metadata
    plan = valid_single_scene_plan(role="video")
    plan["visual_items"][0]["duration_seconds"] = (
        metadata.duration_seconds + 0.5 / metadata.frame_rate
    )
    write_composition(project_dir, plan)

    resolved = resolve_composition(project_dir)

    assert resolved.visual_items[0].asset.id == imported.asset.id


def test_resolver_derives_audio_duration_from_source(
    project_with_selection: Path,
    tmp_path: Path,
) -> None:
    imported = import_media(
        project_with_selection,
        "scene-001",
        make_audio(tmp_path / "voice.wav", get_ffmpeg_executable()),
    )
    select_asset(
        project_with_selection,
        "scene-001",
        "narration",
        imported.asset.id,
    )
    plan = valid_single_scene_plan()
    plan["audio_items"] = [
        {
            "id": "audio-voice",
            "scene_id": "scene-001",
            "role": "narration",
            "start_seconds": 0,
        }
    ]
    write_composition(project_with_selection, plan)
    resolved = resolve_composition(project_with_selection)
    assert resolved.audio_items[0].effective_duration_seconds == pytest.approx(
        1.0,
        abs=0.1,
    )


def test_resolver_rejects_fades_longer_than_derived_audio_duration(
    project_with_selection: Path,
    tmp_path: Path,
) -> None:
    imported = import_media(
        project_with_selection,
        "scene-001",
        make_audio(tmp_path / "voice.wav", get_ffmpeg_executable()),
    )
    select_asset(
        project_with_selection,
        "scene-001",
        "narration",
        imported.asset.id,
    )
    plan = valid_single_scene_plan()
    plan["audio_items"] = [
        {
            "id": "audio-voice",
            "scene_id": "scene-001",
            "role": "narration",
            "start_seconds": 0,
            "fade_in_seconds": 0.75,
            "fade_out_seconds": 0.75,
        }
    ]
    write_composition(project_with_selection, plan)

    with pytest.raises(CompositionError, match="fades.*duration"):
        resolve_composition(project_with_selection)


def test_resolver_rejects_composition_for_another_project(
    project_dir: Path,
) -> None:
    plan = valid_single_scene_plan()
    plan["project_id"] = "another-project"
    write_composition(project_dir, plan)
    with pytest.raises(CompositionError, match="another-project.*sample-project"):
        resolve_composition(project_dir)


def test_old_project_without_composition_still_loads_creative_documents(
    project_dir: Path,
) -> None:
    assert load_project(project_dir).project.id == "sample-project"
