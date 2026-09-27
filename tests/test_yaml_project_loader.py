from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from videos_llm.infrastructure.yaml_project_loader import (
    ProjectValidationError,
    load_project,
)


def valid_documents() -> dict[str, dict]:
    project = {
        "schema_version": 1,
        "id": "sample-project",
        "title": "Sample Project",
        "language": "pt-BR",
        "created_at": "2026-09-26T18:00:00-03:00",
        "status": "draft",
        "format": {
            "aspect_ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "fps": 30,
        },
    }
    brief = {
        "schema_version": 1,
        "project_id": "sample-project",
        "objective": "Create a short video.",
        "audience": {"primary": "General audience", "desired_reaction": ["curiosity"]},
        "creative": {
            "premise": "A presenter imagines the future.",
            "hook": "What will happen?",
            "key_message": "Predictions are imperfect.",
            "tone": ["nostalgic"],
            "narrative_arc": ["setup", "punchline"],
        },
        "visual_direction": {
            "era": "1995",
            "style": ["crt"],
            "color_notes": ["saturated"],
            "texture": ["scanlines"],
            "references": [],
        },
        "audio_direction": {
            "narration_style": "Television announcer",
            "music_style": "Synth",
            "sound_notes": ["VHS noise"],
        },
        "constraints": {"must_include": ["CRT"], "avoid": []},
        "success_criteria": ["The hook is clear."],
    }
    script = {
        "schema_version": 1,
        "project_id": "sample-project",
        "scenes": [
            {
                "id": "scene-001",
                "narration": "The future is coming.",
                "dialogue": [],
                "on_screen_text": [],
            }
        ],
    }
    storyboard = {
        "schema_version": 1,
        "project_id": "sample-project",
        "version": 1,
        "status": "draft",
        "scenes": [
            {
                "id": "scene-001",
                "order": 1,
                "duration_seconds": 3,
                "purpose": "hook",
                "status": "draft",
                "script_scene_id": "scene-001",
                "visual": {
                    "description": "A presenter in a studio.",
                    "composition": "Presenter centered.",
                    "camera": {
                        "framing": "medium_shot",
                        "angle": "eye_level",
                        "movement": "static",
                    },
                    "lighting": {"style": "television_studio"},
                    "mood": ["optimistic"],
                },
                "audio": {"sfx": []},
            }
        ],
    }
    return {
        "project.yaml": project,
        "brief.yaml": brief,
        "script.yaml": script,
        "storyboard.yaml": storyboard,
    }


def write_project(directory: Path, documents: dict[str, dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for filename, content in documents.items():
        (directory / filename).write_text(
            yaml.safe_dump(content, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
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
