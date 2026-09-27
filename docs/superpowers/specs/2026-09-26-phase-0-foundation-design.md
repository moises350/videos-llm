# Videos LLM — Phase 0 Foundation Design

Date: 2026-09-26
Status: proposed for final review

## 1. Purpose

`videos-llm` is a local, Git-versioned laboratory for producing short AI-assisted videos. It is not a SaaS, web application, API, or cloud platform.

Phase 0 establishes only the minimum reliable foundation needed to describe and validate a video project with human-readable YAML. A project must remain usable without external APIs and without generated media being committed to Git.

## 2. Approved Architectural Direction

The project uses the approved "central creative documents plus per-scene production state" architecture.

The long-term dependency direction is:

```text
CLI -> application use cases -> domain models
                           \-> application ports <- infrastructure adapters
```

Phase 0 implements only domain models, YAML loading, validation, templates, and tests. Application ports, providers, media assets, production state, and composition are deferred.

## 3. Phase 0 Scope

Phase 0 includes:

- Git repository initialization.
- `pyproject.toml` using a `src` package layout.
- The `videos_llm` Python package.
- Pydantic models for:
  - `Project`
  - `ContentBrief`
  - `Script`
  - `Storyboard`
  - `Scene`
- The minimum enums and supporting value objects required by those models.
- YAML templates for:
  - `project.yaml`
  - `brief.yaml`
  - `script.yaml`
  - `storyboard.yaml`
- A YAML project loader.
- Cross-document validation.
- Unit tests for the principal invariants.
- A minimal README.
- A `.gitignore` that excludes generated media and temporary files.

Phase 0 explicitly excludes:

- `Generation` and `GenerationAttempt`.
- `Asset` and asset selection.
- `production.yaml` implementation.
- Image, video, or voice providers.
- External APIs and SDKs.
- FFmpeg and composition.
- Publication metadata and analytics.
- A full CLI.
- Creation of the first real video project.

## 4. Project Documents and Responsibilities

Each project uses conventional file locations. Paths are not repeated in every document unless future requirements demonstrate a need for configurable locations.

### `project.yaml`

The main manifest and entrypoint. It owns project identity and global technical media configuration.

Initial fields:

- `schema_version`
- `id`
- `title`
- `language`
- `created_at`
- `status`
- `format`
- Optional references to non-conventional primary document locations

The initial implementation uses conventional document names and therefore does not require document path fields.

`format` owns:

- `aspect_ratio`
- `width`
- `height`
- `fps`

This technical configuration is not duplicated in the brief or storyboard.

### `brief.yaml`

Owns creative intent:

- Objective
- Audience
- Premise
- Hook
- Key message
- Tone
- Narrative direction
- Visual direction
- Audio direction
- Creative constraints
- Success criteria

It does not contain provider settings, resolution, frame rate, or generation parameters.

### `script.yaml`

Owns spoken and written content by scene:

- Narration
- Dialogue
- On-screen text

Each script scene has a stable scene ID.

### `storyboard.yaml`

Owns visual realization and timing by scene:

- Stable scene ID
- Order
- Duration
- Purpose
- Scene status
- `script_scene_id`
- Visual description
- Composition
- Camera direction
- Lighting
- Mood
- Audio direction such as ambience, SFX, and music notes

It does not use fragment-style references such as `script.yaml#scenes.scene-001`.

It does not contain a `production_ref`. When production tracking is added, the conventional location will be `scenes/{scene-id}/production.yaml`.

### `production.yaml`

Deferred to Phase 2. It will own generation attempts, assets, and selections for one scene.

When introduced, IDs inside a scene are local, for example:

- `video-attempt-001`
- `image-attempt-002`
- `image-001`
- `video-002`

A globally unique identifier may be composed at runtime from the project ID, scene ID, and local ID.

### `publication.yaml`

Deferred to Phase 7. It will own publication metadata.

## 5. Proposed Directory Structure After Phase 0

```text
videos-llm/
|-- .gitignore
|-- README.md
|-- pyproject.toml
|-- docs/
|   `-- superpowers/
|       `-- specs/
|           `-- 2026-09-26-phase-0-foundation-design.md
|-- templates/
|   |-- project.yaml
|   |-- brief.yaml
|   |-- script.yaml
|   `-- storyboard.yaml
|-- src/
|   `-- videos_llm/
|       |-- __init__.py
|       |-- domain/
|       |   |-- __init__.py
|       |   `-- models.py
|       `-- infrastructure/
|           |-- __init__.py
|           `-- yaml_project_loader.py
`-- tests/
    |-- test_domain_models.py
    `-- test_yaml_project_loader.py
```

Files may be split further only when doing so materially improves clarity. Empty provider, FFmpeg, application-port, CLI, or production packages will not be created in Phase 0.

## 6. Domain Model

Pydantic models are used directly as the initial domain models. This provides validation and YAML mapping without duplicating domain objects and persistence DTOs.

### Project

```text
Project
  schema_version: int
  id: ProjectId
  title: non-empty string
  language: language tag string
  created_at: timezone-aware datetime
  status: ProjectStatus
  format: MediaFormat
```

### MediaFormat

```text
MediaFormat
  aspect_ratio: string
  width: positive integer
  height: positive integer
  fps: positive number
```

The initial validator ensures positive dimensions and frame rate. It also verifies that the declared aspect ratio is compatible with width and height within a small tolerance.

### ContentBrief

```text
ContentBrief
  schema_version: int
  project_id: ProjectId
  objective: non-empty string
  audience: Audience
  creative: CreativeDirection
  visual_direction: VisualDirection
  audio_direction: AudioDirection
  constraints: CreativeConstraints
  success_criteria: list[non-empty string]
```

Supporting value objects remain small and correspond to coherent YAML sections. They are not modeled as separate aggregates.

### Script

```text
Script
  schema_version: int
  project_id: ProjectId
  scenes: list[ScriptScene]

ScriptScene
  id: SceneId
  narration: optional string
  dialogue: list[DialogueLine]
  on_screen_text: list[string]
```

A script scene must contain at least one of narration, dialogue, or on-screen text.

### Storyboard and Scene

```text
Storyboard
  schema_version: int
  project_id: ProjectId
  version: positive integer
  status: DocumentStatus
  scenes: list[Scene]

Scene
  id: SceneId
  order: positive integer
  duration_seconds: positive number
  purpose: non-empty string
  status: SceneStatus
  script_scene_id: SceneId
  visual: SceneVisual
  audio: SceneAudio
```

The storyboard does not duplicate global media format or script content.

## 7. Minimum Enums

```text
ProjectStatus
  draft
  in_production
  ready
  published
  archived

DocumentStatus
  draft
  ready
  approved

SceneStatus
  draft
  ready
  in_progress
  review
  approved
  blocked
```

No workflow engine or transition graph is implemented. Enums validate vocabulary only.

## 8. Identifiers

Project and scene IDs use lowercase kebab-case:

```text
brasil-1995-imagina-2026
scene-001
```

IDs are stable. Scene order is mutable and does not form part of scene identity.

Technical field names and enum values are in English. Creative content may use any UTF-8 language, with Portuguese as the first project language.

## 9. YAML Loading and Validation

The loader accepts a project directory and treats `project.yaml` as the entrypoint.

It loads the conventional files:

```text
project.yaml
brief.yaml
script.yaml
storyboard.yaml
```

The loader returns a validated aggregate view containing all four documents. It performs both Pydantic field validation and cross-document validation.

Cross-document invariants:

- All `project_id` fields equal `project.yaml:id`.
- Script scene IDs are unique.
- Storyboard scene IDs are unique.
- Storyboard scene orders are unique.
- Every `script_scene_id` references an existing script scene.
- Each scene duration is greater than zero.
- Required project files exist.
- Only the supported `schema_version` is accepted.

Errors include the source file and field path where practical. The loader does not silently add defaults to authored content and does not rewrite YAML.

Missing optional creative values may use explicit empty lists or `null` where the schema allows it.

## 10. Templates

Templates are valid, loadable examples rather than commented pseudo-schemas. They use a small fictional placeholder project and demonstrate the minimum supported structure.

Templates must stay synchronized with the Pydantic models through an automated test that loads all four templates together.

## 11. Git Policy

Phase 0 initializes Git but does not configure Git LFS.

The repository versions:

- YAML documents
- Prompt Markdown files
- Documentation
- Metadata
- Manifests
- Source code and tests

The `.gitignore` excludes generated or imported media under project scene directories and final outputs, including common image, video, and audio formats. It also excludes temporary files, Python caches, virtual environments, test caches, coverage output, and build artifacts.

Reference media and generated media are both ignored initially. Storage and LFS policy will be reconsidered after real production experience.

## 12. Dependencies

Runtime dependencies:

- Python 3.11 or newer
- Pydantic 2
- PyYAML

Development dependency:

- pytest

No application framework, CLI framework, provider SDK, FFmpeg wrapper, database library, or cloud dependency is added.

An optional validation command is not required for Phase 0. Tests and direct use of the loader are sufficient. If a command is added, its only supported operation is equivalent to:

```text
videos-llm validate <project-directory>
```

## 13. Test Strategy

Unit tests cover:

- Valid model construction.
- Invalid project and scene IDs.
- Non-positive width, height, FPS, scene order, and duration.
- Incompatible aspect ratio and dimensions.
- Empty script scenes.
- Duplicate script scene IDs.
- Duplicate storyboard scene IDs.
- Duplicate scene order.
- Missing script references.
- Mismatched project IDs across documents.
- Missing required YAML files.
- Invalid or unsupported schema versions.
- Successful loading of the complete template project.

Tests use temporary directories and do not depend on external programs, network access, media files, or environment secrets.

## 14. Error Handling

YAML syntax errors, schema validation errors, missing files, and cross-document consistency failures are exposed as project validation errors with readable context.

Phase 0 does not attempt recovery, migration, automatic rewriting, locking, or concurrent editing support.

## 15. Roadmap

### Phase 0 — Foundation

- Git
- `pyproject.toml`
- Minimum domain models
- YAML schemas
- Loader
- Validation
- Tests

### Phase 1 — First Real Manual Production

- Create `brasil-1995-imagina-2026`
- Fill in brief, script, and storyboard
- Author prompts manually
- Produce the first video using external tools manually

### Phase 2 — Production Tracking

- `GenerationAttempt`
- `Asset`
- Asset import
- Asset selection
- Per-scene `production.yaml`

`Generation` is not introduced unless real usage demonstrates a need to group attempts by a shared specification.

### Phase 3 — Prompt Tooling

- Prompt templates
- Prompt rendering
- Prompt versioning

### Phase 4 — Automated Composition

- `CompositionPlan`
- `MediaComposer`
- FFmpeg
- Automatic final-video composition

### Phase 5 — External Providers

- First real image or video integration
- Providers added one at a time

### Phase 6 — Automation

- Automate proven repetitive workflow steps only

### Phase 7 — Publication and Analytics

- Publication metadata
- Publication records
- Performance metrics

## 16. Acceptance Criteria

Phase 0 is complete when:

- The repository has the agreed minimal structure.
- All four templates parse into their corresponding Pydantic models.
- A project directory can be loaded from `project.yaml` and its conventional companion documents.
- Cross-document invariants produce readable validation failures.
- Generated images, videos, audio, outputs, and temporary files are ignored by Git.
- The complete unit test suite passes without network access or external binaries.
- No excluded Phase 1 or later concept has been implemented.
