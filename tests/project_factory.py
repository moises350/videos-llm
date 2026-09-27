from pathlib import Path

import yaml


def valid_creative_documents() -> dict[str, dict]:
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
        "audience": {
            "primary": "General audience",
            "desired_reaction": ["curiosity"],
        },
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


def write_creative_project(
    directory: Path,
    documents: dict[str, dict] | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for filename, content in (documents or valid_creative_documents()).items():
        (directory / filename).write_text(
            yaml.safe_dump(content, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    return directory
