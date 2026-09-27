from datetime import datetime

import pytest
from pydantic import ValidationError

from videos_llm.domain.models import (
    AudioDirection,
    Audience,
    CameraDirection,
    ContentBrief,
    CreativeConstraints,
    CreativeDirection,
    DialogueLine,
    DocumentStatus,
    LightingDirection,
    MediaFormat,
    Project,
    ProjectStatus,
    Scene,
    SceneAudio,
    SceneStatus,
    SceneVisual,
    Script,
    ScriptScene,
    Storyboard,
    VisualDirection,
)


def valid_project_data() -> dict:
    return {
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


def valid_scene(*, scene_id: str = "scene-001", order: int = 1) -> Scene:
    return Scene(
        id=scene_id,
        order=order,
        duration_seconds=3,
        purpose="hook",
        status=SceneStatus.DRAFT,
        script_scene_id=scene_id,
        visual=SceneVisual(
            description="A presenter in a television studio.",
            composition="Presenter centered in frame.",
            camera=CameraDirection(
                framing="medium_shot",
                angle="eye_level",
                movement="static",
            ),
            lighting=LightingDirection(style="television_studio"),
            mood=["optimistic"],
        ),
        audio=SceneAudio(),
    )


def test_project_accepts_valid_vertical_format() -> None:
    project = Project.model_validate(valid_project_data())
    assert project.status is ProjectStatus.DRAFT
    assert project.format.width == 1080


@pytest.mark.parametrize("project_id", ["Sample Project", "sample_project", "-sample"])
def test_project_rejects_invalid_id(project_id: str) -> None:
    data = valid_project_data()
    data["id"] = project_id
    with pytest.raises(ValidationError):
        Project.model_validate(data)


def test_project_rejects_naive_created_at() -> None:
    data = valid_project_data()
    data["created_at"] = datetime(2026, 9, 26, 18, 0)
    with pytest.raises(ValidationError, match="timezone"):
        Project.model_validate(data)


@pytest.mark.parametrize(
    ("width", "height", "is_valid"),
    [(1080, 1920, True), (1085, 1920, True), (1100, 1920, False)],
)
def test_media_format_uses_one_percent_ratio_tolerance(
    width: int, height: int, is_valid: bool
) -> None:
    data = {"aspect_ratio": "9:16", "width": width, "height": height, "fps": 30}
    if is_valid:
        assert MediaFormat.model_validate(data).width == width
    else:
        with pytest.raises(ValidationError, match="aspect_ratio"):
            MediaFormat.model_validate(data)


@pytest.mark.parametrize("field", ["width", "height", "fps"])
def test_media_format_rejects_non_positive_values(field: str) -> None:
    data = {"aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 30}
    data[field] = 0
    with pytest.raises(ValidationError):
        MediaFormat.model_validate(data)


def test_content_brief_accepts_utf8_creative_content() -> None:
    brief = ContentBrief(
        schema_version=1,
        project_id="sample-project",
        objective="Criar um vídeo nostálgico.",
        audience=Audience(
            primary="Pessoas que assistiam televisão nos anos 90.",
            desired_reaction=["nostalgia"],
        ),
        creative=CreativeDirection(
            premise="Um programa antigo imagina o futuro.",
            hook="Como será o mundo?",
            key_message="O futuro tomou outro rumo.",
            tone=["nostalgic"],
            narrative_arc=["setup", "punchline"],
        ),
        visual_direction=VisualDirection(
            era="1995",
            style=["crt"],
            color_notes=["saturated"],
            texture=["scanlines"],
            references=[],
        ),
        audio_direction=AudioDirection(
            narration_style="Brazilian television announcer",
            music_style="Corporate synth",
            sound_notes=["vhs noise"],
        ),
        constraints=CreativeConstraints(must_include=["CRT"], avoid=[]),
        success_criteria=["A época é reconhecível."],
    )
    assert brief.project_id == "sample-project"


def test_non_empty_creative_text_rejects_whitespace() -> None:
    with pytest.raises(ValidationError):
        Audience(primary="   ", desired_reaction=[])


def test_script_scene_requires_some_content() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        ScriptScene(id="scene-001")


def test_script_rejects_duplicate_scene_ids() -> None:
    scene = ScriptScene(id="scene-001", narration="Hello")
    with pytest.raises(ValidationError, match="duplicate script scene id"):
        Script(
            schema_version=1,
            project_id="sample-project",
            scenes=[scene, scene.model_copy()],
        )


def test_dialogue_line_requires_speaker_and_text() -> None:
    with pytest.raises(ValidationError):
        DialogueLine(speaker="Presenter", text=" ")


@pytest.mark.parametrize(
    ("field", "value"),
    [("id", "Scene One"), ("order", 0), ("duration_seconds", 0)],
)
def test_scene_rejects_invalid_identity_order_or_duration(field: str, value: object) -> None:
    data = valid_scene().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        Scene.model_validate(data)


def test_storyboard_rejects_duplicate_scene_ids() -> None:
    scene = valid_scene()
    with pytest.raises(ValidationError, match="duplicate storyboard scene id"):
        Storyboard(
            schema_version=1,
            project_id="sample-project",
            version=1,
            status=DocumentStatus.DRAFT,
            scenes=[scene, scene.model_copy(update={"order": 2})],
        )


def test_storyboard_rejects_duplicate_scene_order() -> None:
    with pytest.raises(ValidationError, match="duplicate storyboard scene order"):
        Storyboard(
            schema_version=1,
            project_id="sample-project",
            version=1,
            status=DocumentStatus.DRAFT,
            scenes=[valid_scene(), valid_scene(scene_id="scene-002")],
        )
