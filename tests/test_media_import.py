from pathlib import Path

import pytest

from media_factory import make_image, make_video
from project_factory import write_creative_project
from videos_llm.application.production_service import (
    MediaImportError,
    create_scene_production,
    import_media,
    sha256_file,
)
from videos_llm.infrastructure.ffmpeg import get_ffmpeg_executable
from videos_llm.infrastructure.production_store import (
    production_path,
    save_scene_production,
)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return write_creative_project(tmp_path / "project")


def test_import_unicode_filename_uses_managed_ffmpeg_and_stable_path(
    project_dir: Path,
    tmp_path: Path,
) -> None:
    source = make_video(
        tmp_path / "vídeo candidato 01.mp4",
        get_ffmpeg_executable(),
    )
    result = import_media(project_dir, "scene-001", source, method="external")
    assert result.asset.path == (
        f"media/scene-001/video/{result.asset.id}.mp4"
    )
    assert (project_dir / result.asset.path).is_file()
    assert result.asset.sha256 == sha256_file(source)
    assert result.state.attempts[-1].asset_ids == [result.asset.id]
    assert result.attempt.method == "external"


def test_reimport_same_bytes_reuses_asset_but_records_attempt(
    project_dir: Path,
    tmp_path: Path,
) -> None:
    source = make_image(tmp_path / "candidate.png")
    first = import_media(project_dir, "scene-001", source)
    second = import_media(project_dir, "scene-001", source)
    assert second.asset.id == first.asset.id
    assert len(second.state.assets) == 1
    assert len(second.state.attempts) == 2


def test_failed_probe_does_not_change_production_yaml(
    project_dir: Path,
    tmp_path: Path,
) -> None:
    initial = create_scene_production(project_dir, "scene-001")
    path = save_scene_production(project_dir, initial)
    before = path.read_bytes()
    source = tmp_path / "broken.mov"
    source.write_bytes(b"not media")
    with pytest.raises(MediaImportError, match="broken.mov"):
        import_media(project_dir, "scene-001", source)
    assert production_path(project_dir, "scene-001").read_bytes() == before


def test_invalid_attempt_metadata_removes_new_managed_asset(
    project_dir: Path,
    tmp_path: Path,
) -> None:
    source = make_image(tmp_path / "candidate.png")

    with pytest.raises(MediaImportError, match="project-relative"):
        import_media(
            project_dir,
            "scene-001",
            source,
            prompt_path="../outside.md",
        )

    assert not production_path(project_dir, "scene-001").exists()
    assert not list((project_dir / "media").rglob("*.*"))


def test_import_rejects_checksum_prefix_collision(
    project_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = import_media(
        project_dir,
        "scene-001",
        make_image(tmp_path / "first.png"),
    )
    collision = first.asset.sha256[:12] + "b" * 52
    second_source = make_image(tmp_path / "second.png")
    monkeypatch.setattr(
        "videos_llm.application.production_service.sha256_file",
        lambda path: collision,
    )
    with pytest.raises(MediaImportError, match="prefix collision"):
        import_media(project_dir, "scene-001", second_source)


def test_import_reports_missing_source(project_dir: Path, tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    with pytest.raises(MediaImportError, match="missing.mp4"):
        import_media(project_dir, "scene-001", missing)
