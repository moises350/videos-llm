from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from media_factory import make_audio, make_image, make_video
from project_factory import valid_creative_documents, write_creative_project
from videos_llm.application.composition_service import render_composition
from videos_llm.application.production_service import import_media, select_asset
from videos_llm.domain.production import AssetKind, VideoMetadata
from videos_llm.infrastructure.compositor import RenderError
from videos_llm.infrastructure.ffmpeg import (
    FfmpegError,
    get_ffmpeg_executable,
    probe_media,
)


def two_scene_documents() -> dict[str, dict]:
    documents = valid_creative_documents()
    documents["script.yaml"]["scenes"].append(
        {
            "id": "scene-002",
            "narration": "The second scene.",
            "dialogue": [],
            "on_screen_text": [],
        }
    )
    first_scene = documents["storyboard.yaml"]["scenes"][0]
    first_scene["duration_seconds"] = 1
    second_scene = {
        **first_scene,
        "id": "scene-002",
        "order": 2,
        "script_scene_id": "scene-002",
        "purpose": "ending",
    }
    documents["storyboard.yaml"]["scenes"].append(second_scene)
    return documents


@pytest.fixture
def renderable_project(tmp_path: Path) -> Path:
    project = write_creative_project(
        tmp_path / "project",
        two_scene_documents(),
    )
    ffmpeg = get_ffmpeg_executable()
    image = import_media(
        project,
        "scene-001",
        make_image(tmp_path / "opening.png"),
    )
    voice = import_media(
        project,
        "scene-001",
        make_audio(tmp_path / "voice.wav", ffmpeg),
    )
    video = import_media(
        project,
        "scene-002",
        make_video(tmp_path / "ending.mp4", ffmpeg),
    )
    select_asset(project, "scene-001", "key_image", image.asset.id)
    select_asset(project, "scene-001", "narration", voice.asset.id)
    select_asset(project, "scene-002", "video", video.asset.id)

    composition = {
        "schema_version": 1,
        "project_id": "sample-project",
        "visual_items": [
            {
                "id": "visual-opening",
                "scene_id": "scene-001",
                "role": "key_image",
                "start_seconds": 0,
                "duration_seconds": 1,
                "motion": "push_in",
            },
            {
                "id": "visual-ending",
                "scene_id": "scene-002",
                "role": "video",
                "start_seconds": 1,
                "duration_seconds": 1,
            },
        ],
        "audio_items": [
            {
                "id": "audio-voice",
                "scene_id": "scene-001",
                "role": "narration",
                "start_seconds": 0,
                "duration_seconds": 1,
                "fade_out_seconds": 0.1,
            }
        ],
        "overlays": [
            {
                "id": "overlay-end",
                "text": "O sinal acabou. O prejuízo ficou.",
                "start_seconds": 1,
                "duration_seconds": 1,
                "position": "bottom",
            }
        ],
        "output_filename": "final.mp4",
    }
    (project / "composition.yaml").write_text(
        yaml.safe_dump(composition, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return project


def test_render_preview_produces_valid_vertical_mp4(
    renderable_project: Path,
) -> None:
    output = render_composition(renderable_project, preview=True)
    probed = probe_media(output)
    assert output == renderable_project / "output" / "preview.mp4"
    assert probed.kind is AssetKind.VIDEO
    assert isinstance(probed.metadata, VideoMetadata)
    assert probed.metadata.width == 360
    assert probed.metadata.height == 640
    assert probed.metadata.has_audio is True
    assert probed.metadata.duration_seconds == pytest.approx(2.0, abs=0.15)


def test_render_refuses_overwrite_and_cleans_failed_partial(
    renderable_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = renderable_project / "output" / "final.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"existing")
    with pytest.raises(RenderError, match="already exists"):
        render_composition(renderable_project, output_path=destination)
    assert destination.read_bytes() == b"existing"

    destination.unlink()
    monkeypatch.setattr(
        "videos_llm.infrastructure.compositor.run_ffmpeg",
        Mock(side_effect=FfmpegError("encoder failed")),
    )
    with pytest.raises(RenderError, match="encoder failed"):
        render_composition(renderable_project, output_path=destination)
    assert not destination.exists()
    assert not list(destination.parent.glob(".*.part.mp4"))
