from pathlib import Path

import pytest

from media_factory import make_image
from project_factory import write_creative_project
from videos_llm.cli import main
from videos_llm.infrastructure.production_store import load_scene_production


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return write_creative_project(tmp_path / "project")


def test_validate_reports_creative_project_success(
    project_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate", str(project_dir)]) == 0
    captured = capsys.readouterr()
    assert "valid creative project: sample-project" in captured.out
    assert captured.err == ""


def test_production_import_and_select_round_trip(
    project_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image = make_image(tmp_path / "candidate.png")
    assert (
        main(
            [
                "production",
                "import",
                str(project_dir),
                "scene-001",
                str(image),
            ]
        )
        == 0
    )
    asset_id = load_scene_production(project_dir, "scene-001").assets[0].id
    assert asset_id in capsys.readouterr().out

    assert (
        main(
            [
                "production",
                "select",
                str(project_dir),
                "scene-001",
                "key_image",
                asset_id,
            ]
        )
        == 0
    )
    assert (
        load_scene_production(project_dir, "scene-001").selections["key_image"]
        == asset_id
    )
    assert "selected key_image" in capsys.readouterr().out


def test_cli_returns_two_and_stderr_for_user_error(
    project_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["compose", str(project_dir)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "composition.yaml" in captured.err


def test_validate_production_resolves_composition(
    project_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate", str(project_dir), "--production"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "composition.yaml" in captured.err
