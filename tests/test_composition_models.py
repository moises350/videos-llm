from copy import deepcopy

import pytest
from pydantic import ValidationError

from videos_llm.domain.composition import CompositionPlan


def valid_composition_data() -> dict:
    return {
        "schema_version": 1,
        "project_id": "sample-project",
        "visual_items": [
            {
                "id": "visual-opening",
                "scene_id": "scene-001",
                "role": "key_image",
                "start_seconds": 0,
                "duration_seconds": 2,
            },
            {
                "id": "visual-ending",
                "scene_id": "scene-002",
                "role": "video",
                "start_seconds": 2,
                "duration_seconds": 2,
            },
        ],
        "audio_items": [],
        "overlays": [],
        "output_filename": "final.mp4",
    }


def test_valid_hard_cut_timeline_is_accepted() -> None:
    plan = CompositionPlan.model_validate(valid_composition_data())
    assert plan.duration_seconds == 4


def test_visual_timeline_rejects_overlap() -> None:
    data = valid_composition_data()
    data["visual_items"][1]["start_seconds"] = 1.5
    with pytest.raises(ValidationError, match="overlap"):
        CompositionPlan.model_validate(data)


def test_visual_timeline_rejects_gap() -> None:
    data = valid_composition_data()
    data["visual_items"][1]["start_seconds"] = 2.5
    with pytest.raises(ValidationError, match="gap"):
        CompositionPlan.model_validate(data)


def test_dissolve_requires_shorter_positive_transition() -> None:
    data = valid_composition_data()
    data["visual_items"][1].update(
        {"transition": "dissolve", "transition_seconds": 2.0}
    )
    with pytest.raises(ValidationError, match="transition_seconds"):
        CompositionPlan.model_validate(data)


def test_valid_dissolve_uses_exact_overlap() -> None:
    data = valid_composition_data()
    data["visual_items"][1].update(
        {
            "start_seconds": 1.75,
            "transition": "dissolve",
            "transition_seconds": 0.25,
        }
    )
    assert CompositionPlan.model_validate(data).duration_seconds == 3.75


def test_output_filename_must_be_relative_mp4() -> None:
    data = valid_composition_data()
    data["output_filename"] = "../escape.mov"
    with pytest.raises(ValidationError, match="MP4"):
        CompositionPlan.model_validate(data)


def test_overlay_must_end_within_program() -> None:
    data = valid_composition_data()
    data["overlays"] = [
        {
            "id": "overlay-end",
            "text": "The end",
            "start_seconds": 3,
            "duration_seconds": 2,
        }
    ]
    with pytest.raises(ValidationError, match="overlay-end.*program"):
        CompositionPlan.model_validate(data)


def test_audio_with_explicit_duration_must_end_within_program() -> None:
    data = deepcopy(valid_composition_data())
    data["audio_items"] = [
        {
            "id": "audio-narration",
            "scene_id": "scene-001",
            "role": "narration",
            "start_seconds": 3,
            "duration_seconds": 2,
        }
    ]
    with pytest.raises(ValidationError, match="audio-narration.*program"):
        CompositionPlan.model_validate(data)


def test_duplicate_timeline_id_is_rejected() -> None:
    data = valid_composition_data()
    data["visual_items"][1]["id"] = "visual-opening"
    with pytest.raises(ValidationError, match="duplicate visual item id"):
        CompositionPlan.model_validate(data)
