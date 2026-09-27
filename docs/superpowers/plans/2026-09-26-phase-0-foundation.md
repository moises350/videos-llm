# Phase 0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal Python foundation that loads and validates the four human-authored YAML documents of a local video project.

**Architecture:** Pydantic models define the domain vocabulary and local invariants. A single infrastructure loader reads conventional YAML paths, delegates structural validation to Pydantic, and enforces consistency across documents without rewriting them.

**Tech Stack:** Python 3.11+, Pydantic 2, PyYAML 6, pytest 8, setuptools build backend

**Spec:** `docs/superpowers/specs/2026-09-26-phase-0-foundation-design.md`

## Global Constraints

- Implement only Phase 0.
- Do not implement `Generation`, `GenerationAttempt`, `Asset`, providers, FFmpeg, publication, analytics, production tracking, or Phase 1 project content.
- Runtime dependencies are limited to Pydantic 2 and PyYAML 6.
- The only development dependency is pytest 8.
- Do not implement a CLI unless validation cannot be demonstrated through the loader and tests.
- Do not rewrite YAML or attempt to preserve its comments.
- Keep technical keys in English and allow UTF-8 creative content.
- Use conventional document names: `project.yaml`, `brief.yaml`, `script.yaml`, and `storyboard.yaml`.
- Use a relative aspect-ratio tolerance of 1%: `abs(actual - declared) / declared <= 0.01`.
- Generated and reference media, final outputs, and temporary files remain unversioned; do not configure Git LFS.

## Review Focus

- A syntactically valid YAML document whose top-level value is not a mapping must produce a readable project validation error.
- A naive `created_at` datetime must be rejected because project timestamps require timezone information.
- Whitespace-only creative text must be rejected wherever a non-empty string is required.
- A storyboard reference to an absent script scene must identify the offending storyboard scene and missing script ID.
- Media dimensions just inside the 1% aspect-ratio tolerance must pass, while dimensions outside it must fail.

---

### Task 1: Package Configuration and Domain Models

**Files:**
- Create: `pyproject.toml`
- Create: `src/videos_llm/__init__.py`
- Create: `src/videos_llm/domain/__init__.py`
- Create: `src/videos_llm/domain/models.py`
- Create: `tests/test_domain_models.py`

**Interfaces:**
- Consumes: the field definitions and invariants in the Phase 0 design.
- Produces: `Project`, `ContentBrief`, `Script`, `Storyboard`, `Scene`, supporting value objects, and the three approved status enums from `videos_llm.domain.models`.

- [ ] **Step 1: Add package metadata and empty package markers**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "videos-llm"
version = "0.1.0"
description = "Local, versioned workflow for AI-assisted short video production"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0,<3.0",
    "PyYAML>=6.0,<7.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0,<9.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra"
```

Create `src/videos_llm/__init__.py`:

```python
"""Local workflow tools for AI-assisted short video production."""
```

Create empty `src/videos_llm/domain/__init__.py`.

- [ ] **Step 2: Install only the approved project dependencies**

Run: `python -m pip install -e ".[dev]"`

Expected: installation succeeds with Pydantic, PyYAML, and pytest as the only direct project dependencies.

- [ ] **Step 3: Write failing domain model tests**

Create `tests/test_domain_models.py` with tests that:

```python
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
```

- [ ] **Step 4: Run domain tests and verify RED**

Run: `python -m pytest tests/test_domain_models.py -q`

Expected: collection fails because `videos_llm.domain.models` does not exist.

- [ ] **Step 5: Implement the minimal domain models**

Create `src/videos_llm/domain/models.py`:

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ProjectId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
SceneId = Annotated[str, StringConstraints(pattern=r"^scene-[0-9]{3,}$")]
LanguageTag = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"),
]


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    IN_PRODUCTION = "in_production"
    READY = "ready"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"


class SceneStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    BLOCKED = "blocked"


class MediaFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aspect_ratio: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*:[1-9][0-9]*$")]
    width: PositiveInt
    height: PositiveInt
    fps: PositiveFloat

    @model_validator(mode="after")
    def validate_aspect_ratio(self) -> MediaFormat:
        ratio_width, ratio_height = (int(part) for part in self.aspect_ratio.split(":"))
        declared = ratio_width / ratio_height
        actual = self.width / self.height
        relative_difference = abs(actual - declared) / declared
        if relative_difference > 0.01:
            raise ValueError(
                "aspect_ratio is incompatible with width and height "
                "using the 1% tolerance"
            )
        return self


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    id: ProjectId
    title: NonEmptyStr
    language: LanguageTag
    created_at: datetime
    status: ProjectStatus
    format: MediaFormat

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include timezone information")
        return value


class Audience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: NonEmptyStr
    desired_reaction: list[NonEmptyStr] = Field(default_factory=list)


class CreativeDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premise: NonEmptyStr
    hook: NonEmptyStr
    key_message: NonEmptyStr
    tone: list[NonEmptyStr] = Field(default_factory=list)
    narrative_arc: list[NonEmptyStr] = Field(default_factory=list)


class VisualDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    era: NonEmptyStr
    style: list[NonEmptyStr] = Field(default_factory=list)
    color_notes: list[NonEmptyStr] = Field(default_factory=list)
    texture: list[NonEmptyStr] = Field(default_factory=list)
    references: list[NonEmptyStr] = Field(default_factory=list)


class AudioDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narration_style: NonEmptyStr
    music_style: NonEmptyStr
    sound_notes: list[NonEmptyStr] = Field(default_factory=list)


class CreativeConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_include: list[NonEmptyStr] = Field(default_factory=list)
    avoid: list[NonEmptyStr] = Field(default_factory=list)


class ContentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    objective: NonEmptyStr
    audience: Audience
    creative: CreativeDirection
    visual_direction: VisualDirection
    audio_direction: AudioDirection
    constraints: CreativeConstraints
    success_criteria: list[NonEmptyStr] = Field(default_factory=list)


class DialogueLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: NonEmptyStr
    text: NonEmptyStr


class ScriptScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SceneId
    narration: NonEmptyStr | None = None
    dialogue: list[DialogueLine] = Field(default_factory=list)
    on_screen_text: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_content(self) -> ScriptScene:
        if self.narration is None and not self.dialogue and not self.on_screen_text:
            raise ValueError(
                "script scene must contain at least one narration, dialogue, "
                "or on-screen text entry"
            )
        return self


class Script(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    scenes: list[ScriptScene]

    @field_validator("scenes")
    @classmethod
    def require_unique_scene_ids(cls, scenes: list[ScriptScene]) -> list[ScriptScene]:
        seen: set[str] = set()
        for scene in scenes:
            if scene.id in seen:
                raise ValueError(f"duplicate script scene id: {scene.id}")
            seen.add(scene.id)
        return scenes


class CameraDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    framing: NonEmptyStr
    angle: NonEmptyStr
    movement: NonEmptyStr
    lens: NonEmptyStr | None = None


class LightingDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: NonEmptyStr
    notes: NonEmptyStr | None = None


class SceneVisual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: NonEmptyStr
    composition: NonEmptyStr
    camera: CameraDirection
    lighting: LightingDirection
    mood: list[NonEmptyStr] = Field(default_factory=list)


class SceneAudio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ambience: NonEmptyStr | None = None
    sfx: list[NonEmptyStr] = Field(default_factory=list)
    music_note: NonEmptyStr | None = None


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SceneId
    order: PositiveInt
    duration_seconds: PositiveFloat
    purpose: NonEmptyStr
    status: SceneStatus
    script_scene_id: SceneId
    visual: SceneVisual
    audio: SceneAudio


class Storyboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: ProjectId
    version: PositiveInt
    status: DocumentStatus
    scenes: list[Scene]

    @field_validator("scenes")
    @classmethod
    def require_unique_scenes(cls, scenes: list[Scene]) -> list[Scene]:
        seen_ids: set[str] = set()
        seen_orders: set[int] = set()
        for scene in scenes:
            if scene.id in seen_ids:
                raise ValueError(f"duplicate storyboard scene id: {scene.id}")
            if scene.order in seen_orders:
                raise ValueError(f"duplicate storyboard scene order: {scene.order}")
            seen_ids.add(scene.id)
            seen_orders.add(scene.order)
        return scenes
```

Create `src/videos_llm/domain/__init__.py`:

```python
from videos_llm.domain.models import (
    ContentBrief,
    DocumentStatus,
    Project,
    ProjectStatus,
    Scene,
    SceneStatus,
    Script,
    Storyboard,
)

__all__ = [
    "ContentBrief",
    "DocumentStatus",
    "Project",
    "ProjectStatus",
    "Scene",
    "SceneStatus",
    "Script",
    "Storyboard",
]
```

- [ ] **Step 6: Run domain tests and verify GREEN**

Run: `python -m pytest tests/test_domain_models.py -q`

Expected: all domain tests pass with no warnings.

- [ ] **Step 7: Run the complete suite**

Run: `python -m pytest -q`

Expected: all collected tests pass.

- [ ] **Step 8: Commit Task 1**

```text
git add pyproject.toml src/videos_llm tests/test_domain_models.py
git commit -m "feat: add phase 0 domain models"
```

---

### Task 2: YAML Project Loader and Cross-Document Validation

**Files:**
- Create: `src/videos_llm/infrastructure/__init__.py`
- Create: `src/videos_llm/infrastructure/yaml_project_loader.py`
- Create: `tests/test_yaml_project_loader.py`

**Interfaces:**
- Consumes: `Project`, `ContentBrief`, `Script`, and `Storyboard` from Task 1.
- Produces: `LoadedProject`, `ProjectValidationError`, and `load_project(project_directory: str | Path) -> LoadedProject`.

- [ ] **Step 1: Write failing loader tests**

Create `tests/test_yaml_project_loader.py` with a local helper that writes YAML through `yaml.safe_dump` and valid document dictionaries. Add these tests:

```python
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
```

- [ ] **Step 2: Run loader tests and verify RED**

Run: `python -m pytest tests/test_yaml_project_loader.py -q`

Expected: collection fails because `videos_llm.infrastructure.yaml_project_loader` does not exist.

- [ ] **Step 3: Implement the minimal loader**

Create `src/videos_llm/infrastructure/__init__.py`:

```python
from videos_llm.infrastructure.yaml_project_loader import (
    LoadedProject,
    ProjectValidationError,
    load_project,
)

__all__ = ["LoadedProject", "ProjectValidationError", "load_project"]
```

Create `src/videos_llm/infrastructure/yaml_project_loader.py` with:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from videos_llm.domain.models import ContentBrief, Project, Script, Storyboard


class ProjectValidationError(ValueError):
    """Raised when a project directory cannot be loaded as a valid project."""


@dataclass(frozen=True)
class LoadedProject:
    project: Project
    brief: ContentBrief
    script: Script
    storyboard: Storyboard


ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ProjectValidationError(f"{path.name}: {error}") from error

    if not isinstance(content, dict):
        raise ProjectValidationError(f"{path.name}: top-level YAML value must be a mapping")

    try:
        return model_type.model_validate(content)
    except ValidationError as error:
        raise ProjectValidationError(f"{path.name}: {error}") from error


def load_project(project_directory: str | Path) -> LoadedProject:
    directory = Path(project_directory)
    required = ("project.yaml", "brief.yaml", "script.yaml", "storyboard.yaml")
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise ProjectValidationError(
            f"missing required project files: {', '.join(missing)}"
        )

    project = _load_model(directory / "project.yaml", Project)
    brief = _load_model(directory / "brief.yaml", ContentBrief)
    script = _load_model(directory / "script.yaml", Script)
    storyboard = _load_model(directory / "storyboard.yaml", Storyboard)

    for filename, project_id in (
        ("brief.yaml", brief.project_id),
        ("script.yaml", script.project_id),
        ("storyboard.yaml", storyboard.project_id),
    ):
        if project_id != project.id:
            raise ProjectValidationError(
                f"{filename}: project_id {project_id!r} does not match "
                f"project.yaml id {project.id!r}"
            )

    script_scene_ids = {scene.id for scene in script.scenes}
    for scene in storyboard.scenes:
        if scene.script_scene_id not in script_scene_ids:
            raise ProjectValidationError(
                f"storyboard.yaml: scene {scene.id!r} references missing "
                f"script scene {scene.script_scene_id!r}"
            )

    return LoadedProject(
        project=project,
        brief=brief,
        script=script,
        storyboard=storyboard,
    )
```

- [ ] **Step 4: Run loader tests and verify GREEN**

Run: `python -m pytest tests/test_yaml_project_loader.py -q`

Expected: all loader tests pass with no warnings.

- [ ] **Step 5: Run the complete suite**

Run: `python -m pytest -q`

Expected: all collected tests pass.

- [ ] **Step 6: Commit Task 2**

```text
git add src/videos_llm/infrastructure tests/test_yaml_project_loader.py
git commit -m "feat: load and validate yaml projects"
```

---

### Task 3: Valid Templates, Git Policy, and Minimal Documentation

**Files:**
- Create: `templates/project.yaml`
- Create: `templates/brief.yaml`
- Create: `templates/script.yaml`
- Create: `templates/storyboard.yaml`
- Create: `tests/test_templates.py`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Consumes: `load_project` from Task 2 and the conventional document schemas from Task 1.
- Produces: a complete loadable template project and the repository's documented Phase 0 usage and ignore policy.

- [ ] **Step 1: Write the failing template integration test**

Create `tests/test_templates.py`:

```python
from pathlib import Path

from videos_llm.infrastructure.yaml_project_loader import load_project


def test_templates_form_a_complete_valid_project() -> None:
    template_directory = Path(__file__).parents[1] / "templates"
    loaded = load_project(template_directory)
    assert loaded.project.id == "sample-project"
    assert [scene.id for scene in loaded.script.scenes] == ["scene-001"]
    assert [scene.id for scene in loaded.storyboard.scenes] == ["scene-001"]
```

- [ ] **Step 2: Run the template test and verify RED**

Run: `python -m pytest tests/test_templates.py -q`

Expected: FAIL with a `ProjectValidationError` listing the missing template YAML files.

- [ ] **Step 3: Create the four valid YAML templates**

Create `templates/project.yaml`:

```yaml
schema_version: 1
id: sample-project
title: "Projeto de exemplo"
language: pt-BR
created_at: "2026-09-26T18:00:00-03:00"
status: draft

format:
  aspect_ratio: "9:16"
  width: 1080
  height: 1920
  fps: 30
```

Create `templates/brief.yaml`:

```yaml
schema_version: 1
project_id: sample-project

objective: "Criar um vídeo curto de exemplo."

audience:
  primary: "Público interessado no tema do vídeo."
  desired_reaction:
    - curiosity

creative:
  premise: "Uma apresentação curta introduz uma ideia."
  hook: "E se olhássemos para essa ideia de outro jeito?"
  key_message: "Uma ideia clara pode ser contada em poucos segundos."
  tone:
    - engaging
  narrative_arc:
    - setup
    - conclusion

visual_direction:
  era: "contemporary"
  style:
    - editorial
  color_notes:
    - balanced
  texture:
    - clean
  references: []

audio_direction:
  narration_style: "Clear and conversational"
  music_style: "Subtle background music"
  sound_notes: []

constraints:
  must_include:
    - "A clear opening image"
  avoid: []

success_criteria:
  - "The main idea is understandable without additional context."
```

Create `templates/script.yaml`:

```yaml
schema_version: 1
project_id: sample-project

scenes:
  - id: scene-001
    narration: "Toda grande história começa com uma ideia clara."
    dialogue: []
    on_screen_text:
      - "Uma ideia. Poucos segundos."
```

Create `templates/storyboard.yaml`:

```yaml
schema_version: 1
project_id: sample-project
version: 1
status: draft

scenes:
  - id: scene-001
    order: 1
    duration_seconds: 3
    purpose: hook
    status: draft
    script_scene_id: scene-001

    visual:
      description: "Uma pessoa apresenta uma ideia diretamente para a câmera."
      composition: "Apresentador centralizado com espaço para texto."
      camera:
        framing: medium_shot
        angle: eye_level
        movement: static
        lens: null
      lighting:
        style: soft_key_light
        notes: "Iluminação uniforme e natural."
      mood:
        - curious

    audio:
      ambience: null
      sfx: []
      music_note: "Trilha discreta sob a narração."
```

- [ ] **Step 4: Run the template test and verify GREEN**

Run: `python -m pytest tests/test_templates.py -q`

Expected: 1 passed.

- [ ] **Step 5: Add the explicit Git ignore policy**

Create `.gitignore` containing Python environment/build/test artifacts, `.superpowers/`, temporary files, final output directories, and common media extensions under `projects/`:

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
build/
dist/
.venv/
venv/

.superpowers/
*.tmp
*.temp
*.part

projects/**/output/
projects/**/*.png
projects/**/*.jpg
projects/**/*.jpeg
projects/**/*.webp
projects/**/*.gif
projects/**/*.mp4
projects/**/*.mov
projects/**/*.mkv
projects/**/*.webm
projects/**/*.wav
projects/**/*.mp3
projects/**/*.m4a
projects/**/*.aac
projects/**/*.flac
```

- [ ] **Step 6: Verify the Git ignore policy**

Run:

```powershell
git check-ignore -v -- `
  projects/ignore-probe/scenes/scene-001/images/image.png `
  projects/ignore-probe/scenes/scene-001/videos/video.mp4 `
  projects/ignore-probe/scenes/scene-001/audio/voice.wav `
  projects/ignore-probe/output/final.txt

git check-ignore -q -- projects/ignore-probe/prompts/image-v001.md
if ($LASTEXITCODE -eq 0) { throw "Prompt Markdown must not be ignored" }
```

Expected: every media/output probe is reported by `git check-ignore`; the prompt probe is not reported.

- [ ] **Step 7: Create the minimal README**

Create `README.md`:

````markdown
# videos-llm

Laboratório local e versionável para produção manual de vídeos curtos com auxílio de IA.

O projeto está na Phase 0. Neste estágio ele oferece apenas modelos de domínio, templates YAML e carregamento com validação. Não existem providers, APIs externas, FFmpeg, tracking de produção, publicação ou analytics.

## Requisitos

- Python 3.11 ou superior

## Instalação para desenvolvimento

```powershell
python -m pip install -e ".[dev]"
```

## Documentos de um projeto

- `project.yaml`: identidade e configuração técnica global.
- `brief.yaml`: intenção criativa.
- `script.yaml`: narração, diálogos e textos de tela.
- `storyboard.yaml`: duração e realização visual de cada cena.

`project.yaml` é o entrypoint. Os demais documentos são encontrados pelos nomes convencionais no mesmo diretório.

## Validação

```python
from pathlib import Path

from videos_llm.infrastructure import load_project

project = load_project(Path("path/to/project"))
print(project.project.title)
```

## Testes

```powershell
python -m pytest
```

Imagens, vídeos, áudio e outputs finais não são versionados inicialmente. Git LFS não está configurado.
````

- [ ] **Step 8: Run the complete suite**

Run: `python -m pytest -q`

Expected: all tests pass with no warnings.

- [ ] **Step 9: Verify installed package metadata**

Run: `python -m pip check`

Expected: `No broken requirements found.`

- [ ] **Step 10: Commit Task 3**

```text
git add .gitignore README.md templates tests/test_templates.py
git commit -m "docs: add phase 0 templates and usage"
```

---

## Final Verification

- [ ] Run `python -m pytest -q` and read the complete result.
- [ ] Run `python -m pip check` and confirm dependency consistency.
- [ ] Run `git status --short` and confirm the working tree is clean except for the implementation plan if it has not yet been committed.
- [ ] Compare the created file tree against Section 5 of the spec.
- [ ] Search source and templates for excluded concepts: `Generation`, `GenerationAttempt`, `Asset`, `Provider`, `FFmpeg`, `publication`, `analytics`, and `production.yaml`.
- [ ] Report the file tree, decisions, complete test result, and any deviation from the design.
- [ ] Stop without starting Phase 1.
