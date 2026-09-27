from pathlib import Path

import pytest

from videos_llm.application.composition_service import (
    CompositionError,
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


def test_pilot_uses_only_approved_narration_and_no_dialogue() -> None:
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


def test_pilot_production_skeleton_matches_every_scene() -> None:
    states = [
        load_scene_production(PILOT, f"scene-{number:03d}")
        for number in range(1, 7)
    ]
    assert all(
        not state.assets and not state.attempts and not state.selections
        for state in states
    )


def test_pilot_composition_is_schema_valid_but_explicitly_not_render_ready() -> None:
    plan = load_composition_plan(PILOT)
    assert plan.duration_seconds == 30
    assert plan.output_filename == "a-casa-inteira-foi-apostada-final.mp4"
    assert plan.overlays[-1].text == "O sinal acabou. O prejuízo ficou."
    with pytest.raises(CompositionError, match="scene-001.*selected"):
        resolve_composition(PILOT)


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
