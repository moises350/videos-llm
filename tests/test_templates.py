from pathlib import Path

from videos_llm.infrastructure.yaml_project_loader import load_project


def test_templates_form_a_complete_valid_project() -> None:
    template_directory = Path(__file__).parents[1] / "templates"
    loaded = load_project(template_directory)
    assert loaded.project.id == "sample-project"
    assert [scene.id for scene in loaded.script.scenes] == ["scene-001"]
    assert [scene.id for scene in loaded.storyboard.scenes] == ["scene-001"]
