from pathlib import Path

from videos_llm.application.composition_service import (
    load_composition_plan,
    resolve_composition,
)
from videos_llm.infrastructure.production_store import load_scene_production
from videos_llm.infrastructure.yaml_project_loader import load_project


PILOT = (
    Path(__file__).parents[1]
    / "projects"
    / "a-casa-inteira-foi-apostada"
)


def test_pilot_creative_documents_and_six_scenes_are_valid() -> None:
    loaded = load_project(PILOT)
    assert loaded.project.id == "a-casa-inteira-foi-apostada"
    assert sum(scene.duration_seconds for scene in loaded.storyboard.scenes) == 30
    assert [scene.id for scene in loaded.storyboard.scenes] == [
        f"scene-{number:03d}" for number in range(1, 7)
    ]


def test_pilot_preserves_archived_editorial_narration_and_no_dialogue() -> None:
    loaded = load_project(PILOT)
    narration = " ".join(
        scene.narration for scene in loaded.script.scenes if scene.narration
    )
    assert narration == (
        "Em 2026, o Brasil tirou as bets do ar. "
        "Mas, antes disso, elas já tinham entrado em casa. "
        "Primeiro levaram o troco. Depois, as compras. Depois, o tempo. "
        "Enquanto uns perdiam tudo, outros sorriam para a câmera. "
        "O sinal acabou. O prejuízo ficou."
    )
    assert all(not scene.dialogue for scene in loaded.script.scenes)


def test_pilot_production_tracks_the_approved_scene_one_key_image() -> None:
    states = [
        load_scene_production(PILOT, f"scene-{number:03d}")
        for number in range(1, 7)
    ]
    assert [state.scene_id for state in states] == [
        f"scene-{number:03d}" for number in range(1, 7)
    ]

    scene_one = states[0]
    selected_id = scene_one.selections["key_image"]
    assert selected_id in {asset.id for asset in scene_one.assets}
    assert any(
        selected_id in attempt.asset_ids and attempt.status.value == "approved"
        for attempt in scene_one.attempts
    )
    image_attempt = next(
        attempt
        for attempt in scene_one.attempts
        if selected_id in attempt.asset_ids
    )
    assert image_attempt.method == "imagegen"
    assert image_attempt.prompt_path == "prompts/image/scene-001.md"


def test_pilot_composition_is_render_ready_with_approved_music_and_sfx() -> None:
    plan = load_composition_plan(PILOT)
    assert plan.duration_seconds == 30
    assert plan.output_filename == "a-casa-inteira-foi-apostada-final.mp4"
    assert plan.overlays[-1].text == "O sinal acabou. O prejuízo ficou."

    resolved = resolve_composition(PILOT)
    assert len(resolved.visual_items) == 6
    assert [item.item.role for item in resolved.audio_items] == ["music", "sfx"]
    assert all(item.path.is_file() for item in resolved.audio_items)


def test_pilot_composition_uses_approved_scene_two_video() -> None:
    resolved = resolve_composition(PILOT)
    scene_two = next(
        item for item in resolved.visual_items if item.item.scene_id == "scene-002"
    )

    assert scene_two.item.role == "video"
    assert scene_two.asset.kind.value == "video"
    assert scene_two.path.suffix == ".mp4"


def test_pilot_composition_uses_approved_scene_three_video() -> None:
    resolved = resolve_composition(PILOT)
    scene_three = next(
        item for item in resolved.visual_items if item.item.scene_id == "scene-003"
    )

    assert scene_three.item.role == "video"
    assert scene_three.asset.kind.value == "video"
    assert scene_three.path.suffix == ".mp4"


def test_pilot_contains_three_character_guides_and_all_prompt_files() -> None:
    assert {path.name for path in (PILOT / "characters").glob("*.md")} == {
        "virginia-fonseca.md",
        "maumau-zk.md",
        "ciro-nogueira.md",
    }
    assert len(list((PILOT / "prompts" / "image").glob("scene-*.md"))) == 6
    assert len(list((PILOT / "prompts" / "video").glob("scene-*.md"))) == 6
    assert {path.name for path in (PILOT / "prompts" / "audio").glob("*.md")} == {
        "narration.md",
        "sound-design.md",
    }
