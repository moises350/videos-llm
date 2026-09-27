# Scene-Driven Production and Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `videos-llm` with durable per-scene production tracking, deterministic local media import and selection, and FFmpeg-based preview/final MP4 composition, then add the complete declarative pilot project “A casa inteira foi apostada.”

**Architecture:** Keep the existing creative models unchanged and add two focused domains: production state and composition plans. Application services coordinate YAML persistence, media probing/import, selection, timeline resolution, and rendering; infrastructure adapters isolate atomic filesystem writes and the Python-managed FFmpeg executable. The CLI is a thin boundary over those services, so every operation is testable without parsing terminal output.

**Tech Stack:** Python 3.11+, Pydantic 2, PyYAML 6, Pillow 10–12, imageio-ffmpeg 0.6, pytest 8, `argparse`, `hashlib`, `subprocess`, setuptools

**Spec:** `docs/superpowers/specs/2026-09-27-scene-driven-production-and-composition-design.md`

## Global Constraints

- Preserve the existing four-document creative format and all Phase 0 behavior.
- Use schema version `1` for production and composition documents.
- Keep project identifiers kebab-case and scene identifiers in `scene-NNN` form.
- Keep every imported attempt and asset; replacing a selection never deletes history.
- Store media paths as project-relative POSIX paths and reject absolute paths or `..` traversal.
- Store generated/reference media under `projects/<project>/media/` and final files under `projects/<project>/output/`; both remain ignored by Git.
- Obtain FFmpeg from `imageio-ffmpeg`; do not require or invoke a global `ffmpeg` or `ffprobe`.
- Do not add provider APIs, credential storage, publication, analytics, or a graphical editor.
- Default final output is H.264, `yuv420p`, 1080×1920, 30 fps, AAC at 48 kHz.
- Refuse to overwrite an existing output unless `--overwrite` is explicit.
- Write YAML and rendered output atomically; a failed operation must not replace the prior document or leave the final output path behind.
- Keep public-person satire in declarative project content; do not fabricate quotes, convictions, payments, crimes, or private conduct.

## File Structure

```text
src/videos_llm/
|-- application/
|   |-- __init__.py
|   |-- composition_service.py   # resolve selections and orchestrate rendering
|   `-- production_service.py    # import assets and change selections
|-- domain/
|   |-- composition.py           # composition schema and timeline invariants
|   |-- models.py                # existing creative models, unchanged
|   `-- production.py            # assets, attempts, metadata, scene state
|-- infrastructure/
|   |-- ffmpeg.py                # executable lookup, probing, command execution
|   |-- production_store.py      # atomic production YAML persistence
|   `-- yaml_project_loader.py   # existing creative loader
|-- cli.py                       # argparse commands and exit behavior
`-- __main__.py                  # python -m videos_llm entrypoint

tests/
|-- media_factory.py
|-- project_factory.py
|-- test_cli.py
|-- test_composition_models.py
|-- test_composition_service.py
|-- test_ffmpeg.py
|-- test_media_import.py
|-- test_pilot_project.py
|-- test_production_models.py
`-- test_production_store.py

projects/a-casa-inteira-foi-apostada/
|-- project.yaml
|-- brief.yaml
|-- script.yaml
|-- storyboard.yaml
|-- visual-bible.md
|-- composition.yaml
|-- characters/*.md
|-- prompts/{image,video,audio}/*.md
`-- production/scene-*/production.yaml
```

## Review Focus

- A malicious or accidental asset path such as `../outside.mp4`, `C:\outside.mp4`, or `/outside.mp4` must be rejected before any filesystem access; Task 1 pins this with `test_asset_rejects_unsafe_project_relative_path`.
- Re-selecting a different attempt must preserve both attempts and assets while making only attempts that still own selected assets `approved`; Task 2 pins this with `test_select_asset_preserves_history_and_recomputes_approval`.
- Importing a filename containing spaces and non-ASCII characters must produce a stable checksum-derived destination without invoking a global `ffprobe`; Task 3 pins this with `test_import_unicode_filename_uses_managed_ffmpeg_and_stable_path`.
- A selected file whose bytes no longer match its recorded checksum must stop composition and identify the scene, role, and asset; Task 4 pins this with `test_resolver_rejects_changed_selected_asset`.
- An existing output or a failed FFmpeg process must never be overwritten/reported as success and must not leave a partial final file; Task 5 pins this with `test_render_refuses_overwrite_and_cleans_failed_partial`.

---

### Task 1: Production Domain Models

**Files:**
- Create: `src/videos_llm/domain/production.py`
- Modify: `src/videos_llm/domain/__init__.py`
- Create: `tests/test_production_models.py`

**Interfaces:**
- Consumes: `ProjectId`, `SceneId`, `NonEmptyStr`, and `PositiveFiniteFloat` from `videos_llm.domain.models`.
- Produces: `AssetKind`, `AttemptStatus`, `ProductionStatus`, `SelectionRole`, `ImageMetadata`, `VideoMetadata`, `AudioMetadata`, `Asset`, `GenerationAttempt`, and `SceneProduction`.

- [ ] **Step 1: Write failing production-model tests**

Create `tests/test_production_models.py` with helpers that construct one image asset and one attempt, then add these exact behaviors:

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from videos_llm.domain.production import (
    Asset,
    AttemptStatus,
    GenerationAttempt,
    ImageMetadata,
    SceneProduction,
)


def image_asset(asset_id: str = "asset-a1b2c3d4e5f6") -> Asset:
    return Asset(
        id=asset_id,
        kind="image",
        path=f"media/scene-001/image/{asset_id}.png",
        sha256="a" * 64,
        mime_type="image/png",
        created_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        metadata=ImageMetadata(width=1080, height=1920),
    )


def attempt(asset_id: str = "asset-a1b2c3d4e5f6") -> GenerationAttempt:
    return GenerationAttempt(
        id="attempt-001122334455",
        scene_id="scene-001",
        kind="image",
        created_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
        method="manual",
        asset_ids=[asset_id],
        status="candidate",
    )


@pytest.mark.parametrize(
    "path",
    ["../outside.mp4", "/outside.mp4", "C:/outside.mp4", r"C:\outside.mp4"],
)
def test_asset_rejects_unsafe_project_relative_path(path: str) -> None:
    data = image_asset().model_dump()
    data["path"] = path
    with pytest.raises(ValidationError, match="project-relative"):
        Asset.model_validate(data)


def test_asset_kind_must_match_metadata_type() -> None:
    data = image_asset().model_dump()
    data["kind"] = "video"
    with pytest.raises(ValidationError, match="metadata"):
        Asset.model_validate(data)


def test_scene_production_rejects_unknown_attempt_asset() -> None:
    with pytest.raises(ValidationError, match="missing asset"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="in_progress",
            attempts=[attempt("asset-deadbeef0000")],
            assets=[image_asset()],
            selections={},
        )


def test_scene_production_rejects_incompatible_selection_role() -> None:
    with pytest.raises(ValidationError, match="video.*image"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="review",
            attempts=[attempt()],
            assets=[image_asset()],
            selections={"video": "asset-a1b2c3d4e5f6"},
        )


def test_scene_production_rejects_selection_from_candidate_attempt() -> None:
    with pytest.raises(ValidationError, match="approved attempt"):
        SceneProduction(
            schema_version=1,
            project_id="sample-project",
            scene_id="scene-001",
            status="review",
            attempts=[attempt()],
            assets=[image_asset()],
            selections={"key_image": "asset-a1b2c3d4e5f6"},
        )


def test_scene_production_accepts_selected_key_image() -> None:
    state = SceneProduction(
        schema_version=1,
        project_id="sample-project",
        scene_id="scene-001",
        status="review",
        attempts=[attempt().model_copy(update={"status": AttemptStatus.APPROVED})],
        assets=[image_asset()],
        selections={"key_image": "asset-a1b2c3d4e5f6"},
    )
    assert state.selections["key_image"] == "asset-a1b2c3d4e5f6"
```

- [ ] **Step 2: Run the production-model tests and verify RED**

Run: `python -m pytest tests/test_production_models.py -q`

Expected: collection fails because `videos_llm.domain.production` does not exist.

- [ ] **Step 3: Implement the production vocabulary and invariants**

Create `src/videos_llm/domain/production.py` with these public types and validators:

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

from videos_llm.domain.models import NonEmptyStr, PositiveFiniteFloat, ProjectId, SceneId

AssetId = Annotated[str, Field(pattern=r"^asset-[a-f0-9]{12}$")]
AttemptId = Annotated[str, Field(pattern=r"^attempt-[a-f0-9]{12}$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class AssetKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class AttemptStatus(str, Enum):
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    APPROVED = "approved"


class ProductionStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    BLOCKED = "blocked"


class SelectionRole(str, Enum):
    KEY_IMAGE = "key_image"
    VIDEO = "video"
    NARRATION = "narration"
    AMBIENCE = "ambience"
    MUSIC = "music"
    SFX = "sfx"


class ImageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: PositiveInt
    height: PositiveInt


class VideoMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: PositiveInt
    height: PositiveInt
    duration_seconds: PositiveFiniteFloat
    frame_rate: PositiveFiniteFloat
    codec: NonEmptyStr
    has_audio: bool = False


class AudioMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_seconds: PositiveFiniteFloat
    sample_rate: PositiveInt
    channels: PositiveInt
    codec: NonEmptyStr


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: AssetId
    kind: AssetKind
    path: NonEmptyStr
    sha256: Sha256
    mime_type: Annotated[str, Field(pattern=r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")]
    created_at: datetime
    metadata: ImageMetadata | VideoMetadata | AudioMetadata

    @field_validator("path")
    @classmethod
    def require_safe_relative_posix_path(cls, value: str) -> str:
        posix = PurePosixPath(value)
        windows = PureWindowsPath(value)
        if posix.is_absolute() or windows.is_absolute() or ".." in posix.parts or "\\" in value:
            raise ValueError("path must be a safe project-relative POSIX path")
        return value

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include timezone information")
        return value

    @model_validator(mode="after")
    def require_matching_metadata(self) -> "Asset":
        expected = {AssetKind.IMAGE: ImageMetadata, AssetKind.VIDEO: VideoMetadata, AssetKind.AUDIO: AudioMetadata}[self.kind]
        if not isinstance(self.metadata, expected):
            raise ValueError(f"{self.kind.value} asset has incompatible metadata")
        return self


class GenerationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: AttemptId
    scene_id: SceneId
    kind: AssetKind
    created_at: datetime
    method: NonEmptyStr
    provider: NonEmptyStr | None = None
    model: NonEmptyStr | None = None
    prompt_path: NonEmptyStr | None = None
    asset_ids: list[AssetId] = Field(min_length=1)
    status: AttemptStatus = AttemptStatus.CANDIDATE
    notes: NonEmptyStr | None = None

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include timezone information")
        return value

    @field_validator("prompt_path")
    @classmethod
    def require_safe_prompt_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        posix = PurePosixPath(value)
        windows = PureWindowsPath(value)
        if posix.is_absolute() or windows.is_absolute() or ".." in posix.parts or "\\" in value:
            raise ValueError("prompt_path must be a safe project-relative POSIX path")
        return value


class SceneProduction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    project_id: ProjectId
    scene_id: SceneId
    status: ProductionStatus
    attempts: list[GenerationAttempt] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    selections: dict[SelectionRole, AssetId] = Field(default_factory=dict)
    review_notes: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> "SceneProduction":
        assets = {asset.id: asset for asset in self.assets}
        if len(assets) != len(self.assets):
            raise ValueError("duplicate asset id")
        attempts = {item.id: item for item in self.attempts}
        if len(attempts) != len(self.attempts):
            raise ValueError("duplicate attempt id")
        asset_attempts: dict[str, list[GenerationAttempt]] = {}
        for item in self.attempts:
            if item.scene_id != self.scene_id:
                raise ValueError(f"attempt {item.id} belongs to {item.scene_id}, not {self.scene_id}")
            for asset_id in item.asset_ids:
                if asset_id not in assets:
                    raise ValueError(f"attempt {item.id} references missing asset {asset_id}")
                if assets[asset_id].kind != item.kind:
                    raise ValueError(f"attempt {item.id} kind does not match asset {asset_id}")
                asset_attempts.setdefault(asset_id, []).append(item)
        compatibility = {
            SelectionRole.KEY_IMAGE: AssetKind.IMAGE,
            SelectionRole.VIDEO: AssetKind.VIDEO,
            SelectionRole.NARRATION: AssetKind.AUDIO,
            SelectionRole.AMBIENCE: AssetKind.AUDIO,
            SelectionRole.MUSIC: AssetKind.AUDIO,
            SelectionRole.SFX: AssetKind.AUDIO,
        }
        for role, asset_id in self.selections.items():
            if asset_id not in assets:
                raise ValueError(f"selection {role.value} references missing asset {asset_id}")
            if assets[asset_id].kind != compatibility[role]:
                raise ValueError(f"selection {role.value} is incompatible with {assets[asset_id].kind.value} asset {asset_id}")
            if not any(item.status is AttemptStatus.APPROVED for item in asset_attempts.get(asset_id, [])):
                raise ValueError(f"selection {role.value} must belong to an approved attempt")
        return self
```

Export the public names from `src/videos_llm/domain/__init__.py`.

- [ ] **Step 4: Run production-model tests and verify GREEN**

Run: `python -m pytest tests/test_production_models.py -q`

Expected: all production-model tests pass.

- [ ] **Step 5: Run the complete suite**

Run: `python -m pytest -q`

Expected: the existing 34 tests plus the new production tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add src/videos_llm/domain tests/test_production_models.py
git commit -m "feat: add production tracking models"
```

---

### Task 2: Atomic Production Store and Selection Service

**Files:**
- Create: `src/videos_llm/infrastructure/production_store.py`
- Create: `src/videos_llm/application/__init__.py`
- Create: `src/videos_llm/application/production_service.py`
- Modify: `src/videos_llm/infrastructure/__init__.py`
- Create: `tests/project_factory.py`
- Modify: `tests/test_yaml_project_loader.py`
- Create: `tests/test_production_store.py`

**Interfaces:**
- Consumes: `SceneProduction`, `SelectionRole`, and `AttemptStatus` from Task 1; `load_project(project_directory)` from Phase 0.
- Produces: `ProductionStoreError`, `production_path(project_directory: str | Path, scene_id: str) -> Path`, `load_scene_production(project_directory: str | Path, scene_id: str) -> SceneProduction`, `save_scene_production(project_directory: str | Path, state: SceneProduction) -> Path`, `create_scene_production(project_directory: str | Path, scene_id: str) -> SceneProduction`, and `select_asset(project_directory: str | Path, scene_id: str, role: SelectionRole | str, asset_id: str) -> SceneProduction`.

- [ ] **Step 1: Write failing persistence and selection tests**

Create `tests/project_factory.py` with `valid_creative_documents() -> dict[str, dict]` and `write_creative_project(directory: Path) -> Path`, moving the valid four-document sample currently local to `tests/test_yaml_project_loader.py`. Update that existing test module to import the shared helpers without changing its assertions. Import the same factory in `tests/test_production_store.py`, expose it as a `project_dir` fixture, and add:

```python
def test_save_and_load_scene_production_round_trip(project_dir: Path) -> None:
    state = create_scene_production(project_dir, "scene-001")
    saved = save_scene_production(project_dir, state)
    assert saved == project_dir / "production" / "scene-001" / "production.yaml"
    assert load_scene_production(project_dir, "scene-001") == state


def test_create_rejects_scene_absent_from_storyboard(project_dir: Path) -> None:
    with pytest.raises(ProductionStoreError, match="scene-999"):
        create_scene_production(project_dir, "scene-999")


def test_select_asset_preserves_history_and_recomputes_approval(project_dir: Path) -> None:
    first, second = two_image_attempt_state(project_dir)
    selected_first = select_asset(project_dir, "scene-001", "key_image", first)
    selected_second = select_asset(project_dir, "scene-001", "key_image", second)
    assert len(selected_second.assets) == 2
    assert len(selected_second.attempts) == 2
    assert selected_second.selections["key_image"] == second
    statuses = {item.asset_ids[0]: item.status.value for item in selected_second.attempts}
    assert statuses == {first: "candidate", second: "approved"}


def test_failed_atomic_write_preserves_previous_document(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = create_scene_production(project_dir, "scene-001")
    path = save_scene_production(project_dir, state)
    before = path.read_bytes()
    monkeypatch.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(ProductionStoreError, match="disk full"):
        save_scene_production(project_dir, state.model_copy(update={"review_notes": ["changed"]}))
    assert path.read_bytes() == before
```

- [ ] **Step 2: Run store tests and verify RED**

Run: `python -m pytest tests/test_production_store.py -q`

Expected: collection fails because the store and application service do not exist.

- [ ] **Step 3: Implement atomic YAML persistence**

Create `src/videos_llm/infrastructure/production_store.py` around these signatures:

```python
class ProductionStoreError(ValueError):
    pass


def production_path(project_directory: str | Path, scene_id: str) -> Path:
    return Path(project_directory) / "production" / scene_id / "production.yaml"


def load_scene_production(project_directory: str | Path, scene_id: str) -> SceneProduction:
    path = production_path(project_directory, scene_id)
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        state = SceneProduction.model_validate(content)
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError) as error:
        raise ProductionStoreError(f"{path}: {error}") from error
    if state.scene_id != scene_id:
        raise ProductionStoreError(f"{path}: expected scene {scene_id}, found {state.scene_id}")
    return state


def save_scene_production(project_directory: str | Path, state: SceneProduction) -> Path:
    path = production_path(project_directory, state.scene_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".yaml.tmp")
    payload = yaml.safe_dump(state.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ProductionStoreError(f"{path}: {error}") from error
    return path
```

Before returning a loaded or saved document, cross-check `project_id` and `scene_id` against `load_project`; do not accept production state for an absent storyboard scene.

- [ ] **Step 4: Implement selection as an immutable state transition**

Create `src/videos_llm/application/production_service.py` with:

```python
def create_scene_production(
    project_directory: str | Path,
    scene_id: str,
) -> SceneProduction:
    loaded = load_project(project_directory)
    if scene_id not in {scene.id for scene in loaded.storyboard.scenes}:
        raise ProductionStoreError(f"scene {scene_id!r} is not in storyboard.yaml")
    return SceneProduction(
        schema_version=1,
        project_id=loaded.project.id,
        scene_id=scene_id,
        status="in_progress",
        attempts=[],
        assets=[],
        selections={},
    )


def select_asset(
    project_directory: str | Path,
    scene_id: str,
    role: SelectionRole | str,
    asset_id: str,
) -> SceneProduction:
    state = load_scene_production(project_directory, scene_id)
    owning_attempts = [item for item in state.attempts if asset_id in item.asset_ids]
    if not owning_attempts:
        raise ProductionStoreError(f"asset {asset_id!r} does not belong to scene {scene_id}")
    if all(item.status is AttemptStatus.REJECTED for item in owning_attempts):
        raise ProductionStoreError(f"asset {asset_id!r} belongs only to rejected attempts")
    selected = dict(state.selections)
    selected[SelectionRole(role)] = asset_id
    selected_ids = set(selected.values())
    attempts = [
        item.model_copy(update={
            "status": (
                AttemptStatus.REJECTED
                if item.status is AttemptStatus.REJECTED
                else AttemptStatus.APPROVED
                if selected_ids.intersection(item.asset_ids)
                else AttemptStatus.CANDIDATE
                if item.status is AttemptStatus.APPROVED
                else item.status
            )
        })
        for item in state.attempts
    ]
    updated = state.model_copy(update={"selections": selected, "attempts": attempts})
    updated = SceneProduction.model_validate(updated.model_dump())
    save_scene_production(project_directory, updated)
    return updated
```

The conditional above keeps rejected attempts rejected and the pre-check prevents selecting an asset that has no non-rejected producing attempt.

- [ ] **Step 5: Run store tests and verify GREEN**

Run: `python -m pytest tests/test_production_store.py -q`

Expected: all store and selection tests pass.

- [ ] **Step 6: Run the complete suite and commit**

Run: `python -m pytest -q`

Expected: all tests pass.

```powershell
git add src/videos_llm/application src/videos_llm/infrastructure tests/project_factory.py tests/test_yaml_project_loader.py tests/test_production_store.py
git commit -m "feat: persist production state and selections"
```

---

### Task 3: Managed FFmpeg, Media Probing, and Import

**Files:**
- Modify: `pyproject.toml`
- Create: `src/videos_llm/infrastructure/ffmpeg.py`
- Modify: `src/videos_llm/application/production_service.py`
- Create: `tests/media_factory.py`
- Create: `tests/test_ffmpeg.py`
- Create: `tests/test_media_import.py`

**Interfaces:**
- Consumes: Task 1 metadata models and Task 2 store functions.
- Produces: `FfmpegError`, `get_ffmpeg_executable() -> Path`, `probe_media(path: str | Path, ffmpeg_executable: str | Path | None = None) -> ProbedMedia`, `run_ffmpeg(arguments: Sequence[str], ffmpeg_executable: str | Path | None = None) -> CompletedProcess[str]`, `sha256_file(path: str | Path) -> str`, `ImportResult`, and the fully typed `import_media` signature shown in Step 6.

- [ ] **Step 1: Add managed-media dependencies**

Modify `pyproject.toml` runtime dependencies to exactly include:

```toml
dependencies = [
    "pydantic>=2.0,<3.0",
    "PyYAML>=6.0,<7.0",
    "Pillow>=10.0,<13.0",
    "imageio-ffmpeg>=0.6,<0.7",
]
```

Run: `python -m pip install -e ".[dev]"`

Expected: installation succeeds and `python -m pip check` reports no broken requirements.

- [ ] **Step 2: Write synthetic-media helpers and failing probe tests**

Create `tests/media_factory.py` with `make_image(path)`, `make_video(path, ffmpeg)`, and `make_audio(path, ffmpeg)`; use Pillow for a 64×96 PNG and the managed executable for one-second `testsrc2` MP4 and `sine` WAV fixtures.

```python
def make_video(path: Path, ffmpeg: Path) -> Path:
    subprocess.run(
        [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc2=size=64x96:rate=30", "-t", "1", "-pix_fmt", "yuv420p",
         "-c:v", "libx264", str(path)],
        check=True,
    )
    return path


def make_audio(path: Path, ffmpeg: Path) -> Path:
    subprocess.run(
        [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:sample_rate=48000", "-t", "1", str(path)],
        check=True,
    )
    return path
```

Create `tests/test_ffmpeg.py` that asserts image, video, and audio kinds plus required metadata; also patch `imageio_ffmpeg.get_ffmpeg_exe` to return a nonexistent path and assert `FfmpegError("managed FFmpeg")`.

- [ ] **Step 3: Run probe tests and verify RED**

Run: `python -m pytest tests/test_ffmpeg.py -q`

Expected: collection fails because `videos_llm.infrastructure.ffmpeg` does not exist.

- [ ] **Step 4: Implement managed execution and probing**

Create `src/videos_llm/infrastructure/ffmpeg.py` with these public contracts:

```python
@dataclass(frozen=True)
class ProbedMedia:
    kind: AssetKind
    mime_type: str
    metadata: ImageMetadata | VideoMetadata | AudioMetadata


class FfmpegError(RuntimeError):
    pass


def get_ffmpeg_executable() -> Path:
    executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not executable.is_file():
        raise FfmpegError(f"managed FFmpeg executable is unavailable: {executable}")
    return executable


def run_ffmpeg(
    arguments: Sequence[str],
    *,
    ffmpeg_executable: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = Path(ffmpeg_executable) if ffmpeg_executable else get_ffmpeg_executable()
    result = subprocess.run(
        [str(executable), "-hide_banner", "-nostdin", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        message = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown FFmpeg error"
        raise FfmpegError(f"FFmpeg failed ({result.returncode}): {message}")
    return result
```

`probe_media` must try Pillow first. For non-images, invoke only the resolved managed executable with `-i <path> -map 0 -f null -`, parse `Duration`, `Video`, `Audio`, dimensions, FPS, sample rate, channel layout, and codec from combined output, and reject zero/unknown duration. Cover comma decimal-independent numeric parsing and filenames with spaces through argument lists, never shell strings.

- [ ] **Step 5: Write failing import tests**

Create `tests/test_media_import.py` with:

```python
def test_import_unicode_filename_uses_managed_ffmpeg_and_stable_path(
    project_dir: Path, tmp_path: Path
) -> None:
    source = make_video(tmp_path / "vídeo candidato 01.mp4", get_ffmpeg_executable())
    result = import_media(project_dir, "scene-001", source, method="external")
    assert result.asset.path == f"media/scene-001/video/{result.asset.id}.mp4"
    assert (project_dir / result.asset.path).is_file()
    assert result.asset.sha256 == sha256_file(source)
    assert result.state.attempts[-1].asset_ids == [result.asset.id]


def test_reimport_same_bytes_reuses_asset_but_records_attempt(
    project_dir: Path, tmp_path: Path
) -> None:
    source = make_image(tmp_path / "candidate.png")
    first = import_media(project_dir, "scene-001", source)
    second = import_media(project_dir, "scene-001", source)
    assert second.asset.id == first.asset.id
    assert len(second.state.assets) == 1
    assert len(second.state.attempts) == 2


def test_failed_probe_does_not_change_production_yaml(
    project_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = production_path(project_dir, "scene-001").read_bytes()
    source = tmp_path / "broken.mov"
    source.write_bytes(b"not media")
    with pytest.raises(MediaImportError, match="broken.mov"):
        import_media(project_dir, "scene-001", source)
    assert production_path(project_dir, "scene-001").read_bytes() == before
```

- [ ] **Step 6: Implement checksum-derived atomic import**

Extend `production_service.py` with:

```python
@dataclass(frozen=True)
class ImportResult:
    state: SceneProduction
    asset: Asset
    attempt: GenerationAttempt


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_media(
    project_directory: str | Path,
    scene_id: str,
    media_path: str | Path,
    *,
    method: str = "manual",
    provider: str | None = None,
    model: str | None = None,
    prompt_path: str | None = None,
    notes: str | None = None,
    ffmpeg_executable: str | Path | None = None,
) -> ImportResult:
    source = Path(media_path).resolve(strict=True)
    state_path = production_path(project_directory, scene_id)
    state = (
        load_scene_production(project_directory, scene_id)
        if state_path.is_file()
        else create_scene_production(project_directory, scene_id)
    )
    checksum = sha256_file(source)
    probed = probe_media(source, ffmpeg_executable=ffmpeg_executable)
    asset_id = f"asset-{checksum[:12]}"
    suffix = canonical_suffix(probed.mime_type)
    relative = PurePosixPath("media", scene_id, probed.kind.value, f"{asset_id}{suffix}")
    destination = Path(project_directory) / Path(*relative.parts)
```

Complete the function by copying to a sibling `.part`, replacing the destination only after successful copy/checksum verification, reusing an existing matching asset, appending a unique `attempt-<12 hex>` record, validating the entire new `SceneProduction`, and atomically saving it. If persistence fails, remove only a destination created by this call; never remove a pre-existing asset.

Before reusing `asset_id`, verify that any existing asset with that 12-character prefix has the same full SHA-256. Raise `MediaImportError` on a prefix collision. If the reused asset is already selected, create the new attempt with `approved` status so production state remains internally consistent.

- [ ] **Step 7: Run media tests, full suite, and commit**

Run: `python -m pytest tests/test_ffmpeg.py tests/test_media_import.py -q`

Expected: all probe and import tests pass.

Run: `python -m pytest -q`

Expected: all tests pass.

```powershell
git add pyproject.toml src/videos_llm/application/production_service.py src/videos_llm/infrastructure/ffmpeg.py tests/media_factory.py tests/test_ffmpeg.py tests/test_media_import.py
git commit -m "feat: import and inspect local media"
```

---

### Task 4: Composition Models, Loading, and Selection Resolution

**Files:**
- Create: `src/videos_llm/domain/composition.py`
- Create: `src/videos_llm/application/composition_service.py`
- Create: `tests/test_composition_models.py`
- Create: `tests/test_composition_service.py`

**Interfaces:**
- Consumes: creative project loader, `SceneProduction`, and production store from Tasks 1–2.
- Produces: `CompositionPlan`, `VisualItem`, `AudioItem`, `TextOverlay`, `ResolvedComposition`, `CompositionError`, `load_composition_plan(project_directory: str | Path) -> CompositionPlan`, and `resolve_composition(project_directory: str | Path) -> ResolvedComposition`.

- [ ] **Step 1: Write failing composition-model tests**

Create `tests/test_composition_models.py` around a valid two-item plan and assert:

```python
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
    data["visual_items"][1].update({"transition": "dissolve", "transition_seconds": 2.0})
    with pytest.raises(ValidationError, match="transition_seconds"):
        CompositionPlan.model_validate(data)


def test_output_filename_must_be_relative_mp4() -> None:
    data = valid_composition_data()
    data["output_filename"] = "../escape.mov"
    with pytest.raises(ValidationError, match="MP4"):
        CompositionPlan.model_validate(data)
```

- [ ] **Step 2: Run composition-model tests and verify RED**

Run: `python -m pytest tests/test_composition_models.py -q`

Expected: collection fails because `videos_llm.domain.composition` does not exist.

- [ ] **Step 3: Implement the composition schema**

Create `src/videos_llm/domain/composition.py` with these exact fields:

```python
class VisualItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=r"^visual-[a-z0-9-]+$")]
    scene_id: SceneId
    role: Literal[SelectionRole.KEY_IMAGE, SelectionRole.VIDEO]
    start_seconds: NonNegativeFiniteFloat
    duration_seconds: PositiveFiniteFloat
    trim_start_seconds: NonNegativeFiniteFloat = 0
    transition: Literal["hard_cut", "dissolve"] = "hard_cut"
    transition_seconds: NonNegativeFiniteFloat = 0
    motion: Literal["static", "push_in", "pull_out"] = "static"
    analog_preset: Literal["none", "betacam_light", "betacam_heavy"] = "none"


class AudioItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=r"^audio-[a-z0-9-]+$")]
    scene_id: SceneId
    role: Literal[
        SelectionRole.NARRATION,
        SelectionRole.AMBIENCE,
        SelectionRole.MUSIC,
        SelectionRole.SFX,
    ]
    start_seconds: NonNegativeFiniteFloat
    duration_seconds: PositiveFiniteFloat | None = None
    trim_start_seconds: NonNegativeFiniteFloat = 0
    fade_in_seconds: NonNegativeFiniteFloat = 0
    fade_out_seconds: NonNegativeFiniteFloat = 0
    gain_db: FiniteFloat = 0


class TextOverlay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(pattern=r"^overlay-[a-z0-9-]+$")]
    text: NonEmptyStr
    start_seconds: NonNegativeFiniteFloat
    duration_seconds: PositiveFiniteFloat
    position: Literal["top", "center", "bottom"] = "bottom"
    font_size: PositiveInt = 64
    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")] = "#FFFFFF"


class CompositionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    project_id: ProjectId
    visual_items: list[VisualItem]
    audio_items: list[AudioItem] = Field(default_factory=list)
    overlays: list[TextOverlay] = Field(default_factory=list)
    output_filename: NonEmptyStr
```

Define finite numeric aliases with `allow_inf_nan=False`. Validate unique IDs, first visual start at zero, contiguous hard-cut ranges, dissolve overlap exactly equal to `transition_seconds`, transition shorter than both adjacent items, overlay/audio bounds within the visual program, and a safe relative `.mp4` output filename.

- [ ] **Step 4: Write failing resolver tests**

Create `tests/test_composition_service.py` with a project fixture, real imported fixture files, selected roles, and:

```python
def test_resolver_returns_absolute_selected_paths(project_with_selection: Path) -> None:
    resolved = resolve_composition(project_with_selection)
    assert resolved.visual_items[0].path.is_absolute()
    assert resolved.visual_items[0].asset.id.startswith("asset-")


def test_resolver_rejects_changed_selected_asset(project_with_selection: Path) -> None:
    state = load_scene_production(project_with_selection, "scene-001")
    asset_id = state.selections["key_image"]
    asset = next(item for item in state.assets if item.id == asset_id)
    (project_with_selection / asset.path).write_bytes(b"changed")
    with pytest.raises(
        CompositionError,
        match=rf"scene-001.*key_image.*{asset_id}.*checksum",
    ):
        resolve_composition(project_with_selection)


def test_resolver_rejects_missing_selection(project_dir: Path) -> None:
    write_composition(project_dir, valid_single_scene_plan(role="key_image"))
    with pytest.raises(CompositionError, match="scene-001.*key_image.*selected"):
        resolve_composition(project_dir)


def test_old_project_without_composition_still_loads_creative_documents(
    project_dir: Path,
) -> None:
    assert load_project(project_dir).project.id == "sample-project"
```

- [ ] **Step 5: Implement loading and deterministic resolution**

Create `src/videos_llm/application/composition_service.py` with:

```python
@dataclass(frozen=True)
class ResolvedVisualItem:
    item: VisualItem
    asset: Asset
    path: Path


@dataclass(frozen=True)
class ResolvedAudioItem:
    item: AudioItem
    asset: Asset
    path: Path
    effective_duration_seconds: float


@dataclass(frozen=True)
class ResolvedComposition:
    project_directory: Path
    project: Project
    plan: CompositionPlan
    visual_items: list[ResolvedVisualItem]
    audio_items: list[ResolvedAudioItem]


class CompositionError(ValueError):
    pass


def load_composition_plan(project_directory: str | Path) -> CompositionPlan:
    path = Path(project_directory) / "composition.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return CompositionPlan.model_validate(raw)
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError) as error:
        raise CompositionError(f"{path}: {error}") from error


def resolve_composition(project_directory: str | Path) -> ResolvedComposition:
    directory = Path(project_directory).resolve()
    loaded = load_project(directory)
    plan = load_composition_plan(directory)
```

Complete resolution by cross-checking project/scene IDs, loading each needed production document once, finding the selected asset for each role, resolving the path under the project root, rejecting symlink/path escape, missing files, checksum drift, kind mismatch, and source duration shorter than requested trim plus duration. Return visual/audio assets in plan order.

- [ ] **Step 6: Run composition tests, full suite, and commit**

Run: `python -m pytest tests/test_composition_models.py tests/test_composition_service.py -q`

Expected: all model and resolver tests pass.

Run: `python -m pytest -q`

Expected: all tests pass.

```powershell
git add src/videos_llm/domain/composition.py src/videos_llm/application/composition_service.py tests/test_composition_models.py tests/test_composition_service.py
git commit -m "feat: resolve composition timelines"
```

---

### Task 5: Deterministic Preview and Final MP4 Rendering

**Files:**
- Create: `src/videos_llm/infrastructure/compositor.py`
- Modify: `src/videos_llm/application/composition_service.py`
- Create: `tests/test_compositor.py`
- Create: `tests/test_render_integration.py`

**Interfaces:**
- Consumes: `ResolvedComposition`, `run_ffmpeg`, and `probe_media` from Tasks 3–4.
- Produces: `RenderProfile`, `RenderError`, `build_visual_filter(items: Sequence[ResolvedVisualItem], profile: RenderProfile) -> tuple[str, str]`, `build_audio_filter(items: Sequence[ResolvedAudioItem], total_duration: float) -> tuple[str, str]`, and the fully typed `render_composition` signature shown in Step 5.

- [ ] **Step 1: Write failing command-construction tests**

Create `tests/test_compositor.py` and assert exact semantic fragments rather than one platform-specific command string:

```python
def test_visual_filter_normalizes_and_concatenates_hard_cuts() -> None:
    graph, label = build_visual_filter(two_resolved_images(), RenderProfile.preview())
    assert "scale=360:640:force_original_aspect_ratio=increase" in graph
    assert "crop=360:640" in graph
    assert "fps=30" in graph
    assert "concat=n=2:v=1:a=0" in graph
    assert label == "[video_out]"


def test_visual_filter_uses_xfade_for_dissolve() -> None:
    graph, _ = build_visual_filter(two_resolved_videos(transition="dissolve"), RenderProfile.preview())
    assert "xfade=transition=fade:duration=0.25:offset=0.75" in graph


def test_audio_filter_ducks_music_under_narration() -> None:
    graph, label = build_audio_filter(narration_and_music(), total_duration=2.0)
    assert "sidechaincompress" in graph
    assert "aresample=48000" in graph
    assert "amix=" in graph
    assert label == "[audio_out]"


def test_overlay_png_is_created_with_exact_text(tmp_path: Path) -> None:
    path = create_overlay_image(
        TextOverlay(id="overlay-end", text="O sinal acabou. O prejuízo ficou.", start_seconds=1, duration_seconds=1),
        RenderProfile.preview(),
        tmp_path,
    )
    assert path.is_file()
    assert Image.open(path).mode == "RGBA"
```

- [ ] **Step 2: Run compositor unit tests and verify RED**

Run: `python -m pytest tests/test_compositor.py -q`

Expected: collection fails because `videos_llm.infrastructure.compositor` does not exist.

- [ ] **Step 3: Implement render profiles and filter graph builders**

Create `src/videos_llm/infrastructure/compositor.py` with:

```python
@dataclass(frozen=True)
class RenderProfile:
    width: int
    height: int
    fps: float
    video_bitrate: str
    audio_bitrate: str = "192k"

    @classmethod
    def preview(cls) -> "RenderProfile":
        return cls(width=360, height=640, fps=30, video_bitrate="1200k", audio_bitrate="128k")

    @classmethod
    def final(cls, project: Project) -> "RenderProfile":
        return cls(
            width=project.format.width,
            height=project.format.height,
            fps=project.format.fps,
            video_bitrate="8000k",
        )


class RenderError(RuntimeError):
    pass
```

For each visual input, generate `scale,crop,setsar,fps,trim,setpts`; add `zoompan` only for still `push_in`/`pull_out`; add `eq`, `noise`, `chromashift`, and light `tblend` only for named analog presets. Use `concat` for hard cuts and sequential `xfade` for dissolves with offsets derived from cumulative displayed duration. Render text through Pillow RGBA images using `ImageFont.load_default(size=overlay.font_size)` and FFmpeg `overlay=enable='between(t,start,end)'`, avoiding platform-specific font paths and FFmpeg `drawtext` dependencies.

For audio, generate per-input `atrim,asetpts,adelay,aresample,volume,afade`; mix same-role items; sidechain-compress the music bus with narration when both exist; combine buses with `amix=normalize=0`; and end with `alimiter` plus `atrim` to program duration. Generate `anullsrc` when the plan has no audio so the MP4 always contains AAC audio.

- [ ] **Step 4: Write failing render integration tests**

Create `tests/test_render_integration.py` with a two-scene 2-second project using one PNG, one MP4, one WAV narration, a hard cut, and final overlay:

```python
def test_render_preview_produces_valid_vertical_mp4(renderable_project: Path) -> None:
    output = render_composition(renderable_project, preview=True)
    probed = probe_media(output)
    assert output == renderable_project / "output" / "preview.mp4"
    assert probed.kind is AssetKind.VIDEO
    assert probed.metadata.width == 360
    assert probed.metadata.height == 640
    assert probed.metadata.has_audio is True
    assert probed.metadata.duration_seconds == pytest.approx(2.0, abs=0.15)


def test_render_refuses_overwrite_and_cleans_failed_partial(
    renderable_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = renderable_project / "output" / "final.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"existing")
    with pytest.raises(RenderError, match="already exists"):
        render_composition(renderable_project, output_path=destination)
    assert destination.read_bytes() == b"existing"

    destination.unlink()
    monkeypatch.setattr(
        "videos_llm.infrastructure.compositor.run_ffmpeg",
        Mock(side_effect=FfmpegError("encoder failed")),
    )
    with pytest.raises(RenderError, match="encoder failed"):
        render_composition(renderable_project, output_path=destination)
    assert not destination.exists()
    assert not list(destination.parent.glob(".*.part.mp4"))
```

- [ ] **Step 5: Implement atomic rendering and post-render verification**

Add the public application function:

```python
def render_composition(
    project_directory: str | Path,
    *,
    preview: bool = False,
    output_path: str | Path | None = None,
    overwrite: bool = False,
    ffmpeg_executable: str | Path | None = None,
) -> Path:
    resolved = resolve_composition(project_directory)
    profile = RenderProfile.preview() if preview else RenderProfile.final(resolved.project)
    default_name = "preview.mp4" if preview else resolved.plan.output_filename
    destination = Path(output_path) if output_path else resolved.project_directory / "output" / default_name
```

Require explicit `overwrite=True` for an existing destination. Build all input arguments and one `filter_complex` using list elements, encode to a unique sibling `.part.mp4` with `libx264`, `yuv420p`, the profile FPS/bitrate, AAC 48 kHz, and `-movflags +faststart`. Probe the part file, require expected width/height/FPS within 0.01, audio presence, H.264-compatible codec, and duration within two output frames; only then replace the destination. Always remove temporary overlays and part files in `finally`.

- [ ] **Step 6: Run rendering tests, full suite, and commit**

Run: `python -m pytest tests/test_compositor.py tests/test_render_integration.py -q`

Expected: all command and real-render tests pass using the managed binary.

Run: `python -m pytest -q`

Expected: all tests pass.

```powershell
git add src/videos_llm/infrastructure/compositor.py src/videos_llm/application/composition_service.py tests/test_compositor.py tests/test_render_integration.py
git commit -m "feat: render preview and final mp4"
```

---

### Task 6: Command-Line Workflow

**Files:**
- Modify: `pyproject.toml`
- Create: `src/videos_llm/cli.py`
- Create: `src/videos_llm/__main__.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_project`, `resolve_composition`, `import_media`, `select_asset`, and `render_composition`.
- Produces: installed `videos-llm` command and `python -m videos_llm` with `validate`, `production import`, `production select`, and `compose` subcommands.

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py` and call `main(argv)` directly with the explicit argument lists below:

```python
def test_validate_reports_creative_project_success(project_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(project_dir)]) == 0
    assert "valid creative project: sample-project" in capsys.readouterr().out


def test_production_import_and_select_round_trip(
    project_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    image = make_image(tmp_path / "candidate.png")
    assert main(["production", "import", str(project_dir), "scene-001", str(image)]) == 0
    asset_id = load_scene_production(project_dir, "scene-001").assets[0].id
    assert main(["production", "select", str(project_dir), "scene-001", "key_image", asset_id]) == 0
    assert load_scene_production(project_dir, "scene-001").selections["key_image"] == asset_id


def test_cli_returns_two_and_stderr_for_user_error(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["compose", str(project_dir)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "composition.yaml" in captured.err
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `python -m pytest tests/test_cli.py -q`

Expected: collection fails because `videos_llm.cli` does not exist.

- [ ] **Step 3: Add the console entry point and parser**

Add to `pyproject.toml`:

```toml
[project.scripts]
videos-llm = "videos_llm.cli:entrypoint"
```

Create `cli.py` with `build_parser() -> argparse.ArgumentParser`, `main(argv: Sequence[str] | None = None) -> int`, and `entrypoint() -> NoReturn`. Required syntax:

```text
videos-llm validate PROJECT [--production]
videos-llm production import PROJECT SCENE MEDIA [--method VALUE] [--provider VALUE] [--model VALUE] [--prompt PATH] [--notes VALUE]
videos-llm production select PROJECT SCENE ROLE ASSET
videos-llm compose PROJECT [--preview] [--output PATH] [--overwrite]
```

`validate` always loads the creative project; with `--production`, it also calls `resolve_composition`. Print one concise success line to stdout. Catch only expected project/production/composition/render errors, print `error: <message>` to stderr, and return `2`; let programming errors surface in tests.

Create `__main__.py`:

```python
from videos_llm.cli import entrypoint

entrypoint()
```

- [ ] **Step 4: Run CLI tests and an installed-command smoke test**

Run: `python -m pytest tests/test_cli.py -q`

Expected: all CLI tests pass.

Run: `videos-llm --help`

Expected: exit code 0 and help lists `validate`, `production`, and `compose`.

- [ ] **Step 5: Run the complete suite and commit**

Run: `python -m pytest -q`

Expected: all tests pass.

```powershell
git add pyproject.toml src/videos_llm/cli.py src/videos_llm/__main__.py tests/test_cli.py
git commit -m "feat: add production and composition cli"
```

---

### Task 7: Declarative Pilot Project

**Files:**
- Create: `projects/a-casa-inteira-foi-apostada/project.yaml`
- Create: `projects/a-casa-inteira-foi-apostada/brief.yaml`
- Create: `projects/a-casa-inteira-foi-apostada/script.yaml`
- Create: `projects/a-casa-inteira-foi-apostada/storyboard.yaml`
- Create: `projects/a-casa-inteira-foi-apostada/visual-bible.md`
- Create: `projects/a-casa-inteira-foi-apostada/composition.yaml`
- Create: `projects/a-casa-inteira-foi-apostada/characters/virginia-fonseca.md`
- Create: `projects/a-casa-inteira-foi-apostada/characters/maumau-zk.md`
- Create: `projects/a-casa-inteira-foi-apostada/characters/ciro-nogueira.md`
- Create: `projects/a-casa-inteira-foi-apostada/prompts/image/scene-001.md` through `scene-006.md`
- Create: `projects/a-casa-inteira-foi-apostada/prompts/video/scene-001.md` through `scene-006.md`
- Create: `projects/a-casa-inteira-foi-apostada/prompts/audio/narration.md`
- Create: `projects/a-casa-inteira-foi-apostada/prompts/audio/sound-design.md`
- Create: `projects/a-casa-inteira-foi-apostada/production/scene-001/production.yaml` through `scene-006/production.yaml`
- Create: `tests/test_pilot_project.py`

**Interfaces:**
- Consumes: all creative, production, and composition schemas.
- Produces: the validated production skeleton that subsequent conversation turns populate with approved media.

- [ ] **Step 1: Write the failing pilot-project contract test**

Create `tests/test_pilot_project.py`:

```python
from pathlib import Path

import pytest

from videos_llm.application.composition_service import CompositionError, load_composition_plan, resolve_composition
from videos_llm.infrastructure.production_store import load_scene_production
from videos_llm.infrastructure.yaml_project_loader import load_project


PILOT = Path(__file__).parents[1] / "projects" / "a-casa-inteira-foi-apostada"


def test_pilot_creative_documents_and_six_scenes_are_valid() -> None:
    loaded = load_project(PILOT)
    assert loaded.project.id == "a-casa-inteira-foi-apostada"
    assert sum(scene.duration_seconds for scene in loaded.storyboard.scenes) == 30
    assert [scene.id for scene in loaded.storyboard.scenes] == [f"scene-{number:03d}" for number in range(1, 7)]


def test_pilot_production_skeleton_matches_every_scene() -> None:
    states = [load_scene_production(PILOT, f"scene-{number:03d}") for number in range(1, 7)]
    assert all(not state.assets and not state.attempts and not state.selections for state in states)


def test_pilot_composition_is_schema_valid_but_explicitly_not_render_ready() -> None:
    plan = load_composition_plan(PILOT)
    assert plan.output_filename == "a-casa-inteira-foi-apostada-final.mp4"
    assert plan.overlays[-1].text == "O sinal acabou. O prejuízo ficou."
    with pytest.raises(CompositionError, match="scene-001.*selected"):
        resolve_composition(PILOT)


def test_pilot_contains_three_character_guides_and_all_prompt_files() -> None:
    assert {path.name for path in (PILOT / "characters").glob("*.md")} == {
        "virginia-fonseca.md", "maumau-zk.md", "ciro-nogueira.md"
    }
    assert len(list((PILOT / "prompts" / "image").glob("scene-*.md"))) == 6
    assert len(list((PILOT / "prompts" / "video").glob("scene-*.md"))) == 6
```

- [ ] **Step 2: Run the pilot test and verify RED**

Run: `python -m pytest tests/test_pilot_project.py -q`

Expected: tests fail because the pilot directory does not exist.

- [ ] **Step 3: Create the four creative YAML documents**

Use this exact project identity and timing:

```yaml
# project.yaml
schema_version: 1
id: a-casa-inteira-foi-apostada
title: "A casa inteira foi apostada"
language: pt-BR
created_at: "2026-09-27T12:00:00-03:00"
status: in_production
format:
  aspect_ratio: "9:16"
  width: 1080
  height: 1920
  fps: 30
```

`brief.yaml` must encode: harm caused by betting addiction; Brazil 2026 captured as mid-1990s Betacam television; humans remain human while the three benefiting/promoting public figures use realistic character-specific rat heads; no fabricated facts or dialogue; and the final reaction “disturbing recognition.”

`script.yaml` must split the approved narration across six scenes without changing its words:

```yaml
scenes:
  - id: scene-001
    narration: "Em 2026, o Brasil tirou as bets do ar."
  - id: scene-002
    narration: "Mas, antes disso, elas já tinham entrado em casa. Primeiro levaram o troco."
  - id: scene-003
    narration: "Depois, as compras."
  - id: scene-004
    narration: "Depois, o tempo."
  - id: scene-005
    narration: "Enquanto uns perdiam tudo, outros sorriam para a câmera."
  - id: scene-006
    narration: "O sinal acabou. O prejuízo ficou."
    on_screen_text: ["O sinal acabou. O prejuízo ficou."]
```

Include `dialogue: []` and `on_screen_text: []` where omitted above. `storyboard.yaml` must contain six ordered scenes with durations `[4, 6, 4, 4, 5, 7]`, the approved beats, current 2026 props, 1990s broadcast camera language, and sound notes. Scene 3 is Virginia-rat at the CPI microphone; scene 4 is MauMau-rat in a promotional studio; scene 5 is Ciro-rat at an institutional microphone; no character receives dialogue.

- [ ] **Step 4: Create the visual bible, character guides, and prompts**

Write `visual-bible.md` with explicit invariants: native low-definition Betacam look; 4:3 source framed inside 9:16; chroma bleed, interlacing, tracking noise and flat TV light; unmistakably 2026 phones/Pix/apps; humans never morph into rats; rat heads anatomically integrated with human bodies; no gore, mascot look, fangs, sewer imagery, or comic squeaks.

Each character guide must record the already approved visual markers from Spec §4.4, the character's narrative function, `source_reference: user-supplied`, and this factual guardrail:

```text
Editorial satire based on public reporting. Preserve recognizable public markers,
but do not fabricate dialogue, a conviction, a specific payment, a crime, or private conduct.
```

Each image prompt must define one still keyframe with subject, setting, framing, current-2026 props, native Betacam artifacts, palette, and negative constraints. Each video prompt must derive motion from that scene's keyframe and restrict movement to camera correction, breathing, eyes, hands, environment, object-ribbon motion, and analog interference. `audio/narration.md` must contain the exact approved narration and restrained 1990s Brazilian-reportage delivery. `audio/sound-design.md` must specify cheerful jingle, cash-register confirmations, compressed applause/camera shutters, almost imperceptible teeth/whiskers, progressive detuning, TV hum, CRT collapse, and dry power click.

- [ ] **Step 5: Create production skeletons and composition plan**

Create one production document per scene with this shape and matching identifiers:

```yaml
schema_version: 1
project_id: a-casa-inteira-foi-apostada
scene_id: scene-001
status: in_progress
attempts: []
assets: []
selections: {}
review_notes: []
```

Create `composition.yaml` with the six visual items at starts `[0, 4, 10, 14, 18, 23]`, durations `[4, 6, 4, 4, 5, 7]`, `key_image` roles initially, subtle `push_in` or `pull_out` motion, `betacam_light` for domestic scenes and `betacam_heavy` for rat scenes, and hard cuts throughout so the program remains exactly 30 seconds. Add per-scene narration items and the final overlay from 25 to 30 seconds. Set `output_filename: a-casa-inteira-foi-apostada-final.mp4`. Dissolve support remains covered by the synthetic model and rendering tests rather than changing the approved pilot timing.

- [ ] **Step 6: Run pilot tests, full suite, and commit**

Run: `python -m pytest tests/test_pilot_project.py -q`

Expected: all pilot structure tests pass; the intentional not-render-ready assertion reports the absent scene-001 selection.

Run: `python -m pytest -q`

Expected: all tests pass.

```powershell
git add projects/a-casa-inteira-foi-apostada tests/test_pilot_project.py
git commit -m "content: add betting harm pilot project"
```

---

### Task 8: User Documentation and End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` only if the Task 3 canonical media suffix list exposes an uncovered extension

**Interfaces:**
- Consumes: the complete CLI and pilot project.
- Produces: a concise operator workflow for continuing scene-by-scene with Codex and finishing the MP4.

- [ ] **Step 1: Update README with the shipped workflow**

Replace the Phase 0-only statement with the current vertical slice. Document these exact examples:

```powershell
videos-llm validate projects/a-casa-inteira-foi-apostada
videos-llm production import projects/a-casa-inteira-foi-apostada scene-001 C:\media\scene-001.png --method imagegen --prompt prompts/image/scene-001.md
videos-llm production select projects/a-casa-inteira-foi-apostada scene-001 key_image asset-012345abcdef
videos-llm validate projects/a-casa-inteira-foi-apostada --production
videos-llm compose projects/a-casa-inteira-foi-apostada --preview
videos-llm compose projects/a-casa-inteira-foi-apostada
```

Explain that the asset ID printed by `production import` replaces the illustrative ID in the next command; rejected/older attempts remain in YAML; preview defaults to 360×640; final defaults to the project format; publication remains manual and out of scope.

- [ ] **Step 2: Verify Git ignore behavior for all generated artifacts**

Run:

```powershell
git check-ignore -v -- `
  projects/a-casa-inteira-foi-apostada/media/scene-001/image/asset-012345abcdef.png `
  projects/a-casa-inteira-foi-apostada/media/scene-001/video/asset-012345abcdef.mp4 `
  projects/a-casa-inteira-foi-apostada/media/scene-001/audio/asset-012345abcdef.wav `
  projects/a-casa-inteira-foi-apostada/output/final.mp4

git check-ignore -q -- projects/a-casa-inteira-foi-apostada/production/scene-001/production.yaml
if ($LASTEXITCODE -eq 0) { throw "Production YAML must be versioned" }
```

Expected: all media/output probes are ignored and `production.yaml` is not ignored.

- [ ] **Step 3: Run the complete automated verification**

Run:

```powershell
python -m pytest -q
python -m pip check
videos-llm validate projects/a-casa-inteira-foi-apostada
```

Expected: every test passes, package dependencies are consistent, and the pilot creative project validates. Do not run `--production` against the empty pilot skeleton and call that success; it must remain a readable “selection missing” error until real media is approved.

- [ ] **Step 4: Perform an isolated synthetic end-to-end smoke test**

Use pytest's renderable fixture through the integration test rather than adding synthetic media to the real pilot:

```powershell
python -m pytest tests/test_render_integration.py::test_render_preview_produces_valid_vertical_mp4 -vv
```

Expected: the test generates local fixture media, imports/selects it, renders with managed FFmpeg, probes the MP4, and removes the temporary project when pytest exits.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md .gitignore
git commit -m "docs: explain scene production workflow"
```

If `.gitignore` did not need a change, omit it from `git add`.

---

## Final Verification

- [ ] Run `python -m pytest -q` and record the exact pass count.
- [ ] Run `python -m pip check` and require `No broken requirements found.`
- [ ] Run `videos-llm --help` and confirm all four required operations are visible.
- [ ] Run `videos-llm validate projects/a-casa-inteira-foi-apostada` and require success.
- [ ] Run `videos-llm validate projects/a-casa-inteira-foi-apostada --production` and confirm it fails specifically because real assets have not yet been selected, not because of schema or path errors.
- [ ] Run the real synthetic render integration test and inspect its probed dimensions, FPS, duration, codec, and audio presence.
- [ ] Run `git status --short`; preserve the pre-existing untracked `projects/sao-paulo-2099-mas-nada-mudou/` directory and do not include it in any commit.
- [ ] Compare changed files with the File Structure section and confirm no provider, credential, publication, analytics, or UI code was introduced.
- [ ] Report the test evidence, commit list, any deviations, and the next production action: import or generate scene-001 candidates for user review.
