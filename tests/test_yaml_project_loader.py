from copy import deepcopy
from pathlib import Path

import pytest

from project_factory import (
    valid_creative_documents as valid_documents,
    write_creative_project as write_project,
)

from videos_llm.infrastructure.yaml_project_loader import (
    ProjectValidationError,
    load_project,
)


def test_load_project_returns_all_validated_documents(tmp_path: Path) -> None:
    write_project(tmp_path, valid_documents())
    loaded = load_project(tmp_path)
    assert loaded.project.id == "sample-project"
    assert loaded.brief.project_id == loaded.project.id
    assert loaded.script.scenes[0].id == "scene-001"
    assert loaded.storyboard.scenes[0].script_scene_id == "scene-001"


def test_load_project_reports_missing_required_file(tmp_path: Path) -> None:
    documents = valid_documents()
    del documents["script.yaml"]
    write_project(tmp_path, documents)
    with pytest.raises(ProjectValidationError, match="script.yaml"):
        load_project(tmp_path)


@pytest.mark.parametrize("filename", ["brief.yaml", "script.yaml", "storyboard.yaml"])
def test_load_project_rejects_mismatched_project_id(
    tmp_path: Path, filename: str
) -> None:
    documents = valid_documents()
    documents[filename]["project_id"] = "another-project"
    write_project(tmp_path, documents)
    with pytest.raises(ProjectValidationError, match=filename):
        load_project(tmp_path)


def test_load_project_rejects_missing_script_scene_reference(tmp_path: Path) -> None:
    documents = valid_documents()
    scene = documents["storyboard.yaml"]["scenes"][0]
    scene["script_scene_id"] = "scene-999"
    write_project(tmp_path, documents)
    with pytest.raises(
        ProjectValidationError,
        match=r"scene-001.*scene-999",
    ):
        load_project(tmp_path)


def test_load_project_wraps_yaml_syntax_error_with_filename(tmp_path: Path) -> None:
    write_project(tmp_path, valid_documents())
    (tmp_path / "brief.yaml").write_text("audience: [", encoding="utf-8")
    with pytest.raises(ProjectValidationError, match="brief.yaml"):
        load_project(tmp_path)


def test_load_project_wraps_invalid_yaml_timestamp_with_filename(tmp_path: Path) -> None:
    write_project(tmp_path, valid_documents())
    project_path = tmp_path / "project.yaml"
    project_path.write_text(
        project_path.read_text(encoding="utf-8").replace(
            "'2026-09-26T18:00:00-03:00'",
            "2026-13-26T18:00:00-03:00",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectValidationError, match="project.yaml"):
        load_project(tmp_path)


def test_load_project_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    write_project(tmp_path, valid_documents())
    (tmp_path / "brief.yaml").write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    with pytest.raises(ProjectValidationError, match=r"brief.yaml.*mapping"):
        load_project(tmp_path)


def test_load_project_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    documents = deepcopy(valid_documents())
    documents["project.yaml"]["schema_version"] = 2
    write_project(tmp_path, documents)
    with pytest.raises(ProjectValidationError, match="project.yaml"):
        load_project(tmp_path)
