# Videos LLM — Scene-Driven Production and Composition Design

**Date:** 2026-09-27  
**Status:** Approved
**Pilot project:** `a-casa-inteira-foi-apostada`

## 1. Purpose

Extend `videos-llm` from a validated set of creative documents into a local,
versionable production workflow that supports a human-led, scene-by-scene
collaboration and ends with a finished MP4.

The human and Codex continue making creative decisions together. The software
owns production state, asset selection, validation, timeline assembly, and
rendering. Automatic social-media publication is outside this design.

The first complete use case is a roughly 30-second vertical satirical film
about the damage caused by online betting in Brazil. Its working title is
**“A casa inteira foi apostada.”**

## 2. Agreed Outcome

Starting from a project brief, the workflow must support:

1. creating a script, storyboard, visual bible, and prompts;
2. generating or importing image, video, and audio alternatives per scene;
3. preserving every attempt with provenance and notes;
4. explicitly selecting the approved asset for each role in each scene;
5. generating repeatable preview renders during production;
6. assembling selected assets, narration, music, sound effects, and overlays;
7. exporting a final vertical MP4 ready for manual publication.

Success means the user can conduct production through the conversation without
manually organizing filenames or reconstructing which attempt was approved.

## 3. Scope

### Included

- `GenerationAttempt`, `Asset`, and per-scene production state.
- Media import and metadata extraction.
- SHA-256 checksums for asset identity.
- Explicit asset selection without deleting rejected alternatives.
- A versioned `composition.yaml` timeline.
- Preview and final MP4 rendering.
- Local FFmpeg execution through a Python-managed binary.
- Image segments with controlled motion when no video asset is selected.
- Video segments when an approved video asset exists.
- Narration, music, sound effects, and final text overlays.
- Validation and readable failures before rendering.
- A command-line interface operated by Codex during the conversation.
- The complete declarative project for `a-casa-inteira-foi-apostada`.

### Excluded

- Automatic publication to social networks.
- Analytics or performance tracking.
- A web dashboard or desktop UI.
- Automatic integration with every image, video, voice, or music provider.
- Credential storage.
- Autonomous creative approval.
- Deleting rejected assets.
- A general-purpose nonlinear video editor.

Generation remains conversational in this iteration. Codex may use available
generation tools or import assets produced by another service, while the
repository records the resulting files consistently.

## 4. Creative Design of the Pilot Film

### 4.1 Intent

The film is not primarily a celebration of a political decision. It shows the
human and domestic damage left by widespread betting addiction, contrasted
with the people and institutions that commercially benefited from promoting
the sector.

The desired reaction is disturbing recognition: the viewer should understand
the subject immediately, then become uncomfortable as ordinary domestic life
is consumed by the betting interface.

### 4.2 Visual language

The setting, devices, clothing, and social context are unmistakably Brazil in
2026. The material is captured as though a Brazilian television crew from the
mid-1990s recorded it:

- 4:3 standard-definition broadcast composition adapted into a 9:16 output;
- Betacam SP softness;
- analog composite chroma bleed;
- interlacing, mild dropout, ghosting, and tracking noise;
- harsh video-camera highlights and flat domestic or institutional lighting;
- contemporary smartphones, flat-screen televisions, instant-payment visual
  language, and betting interfaces;
- no nostalgic claim that the story occurs in the 1990s.

Low definition is intrinsic to the fictional capture process. It must not look
like clean 4K footage with a filter placed on top.

### 4.3 Surreal rule

People harmed by betting remain human. Public figures used in the satire who
commercially promoted or were publicly linked to the betting ecosystem have
realistic rat heads on otherwise human bodies.

Each rat character must:

- preserve recognizable public markers such as hair, glasses, clothing,
  jewelry, gestures, posture, and setting;
- use an anatomically integrated rat head rather than a mask or mascot;
- retain human hands and body language;
- avoid gore, sewer imagery, monster fangs, or cartoon exaggeration;
- be treated as physically normal by the camera;
- have a character-specific design rather than reuse one generic rat.

The rat head is an editorial metaphor. It is not presented as a factual claim
about criminal conduct.

### 4.4 Approved cast

#### Rato 01 — Virginia Fonseca

- Long straight blonde hair.
- Thin angular glasses.
- Oversized black sweatshirt from her CPI appearance.
- Rings, microphone, and confident positive gesture.
- Pale beige-blonde rat fur and a large, unsettling smile.
- Function: influencer marketing and commercial benefit.

#### Rato 02 — MauMau ZK (Mauricio Martins Junior)

- Stocky silhouette and black clothing.
- Black cap, narrow reflective gold glasses, layered gold chains, wristwatch,
  forearm tattoos, and characteristic hand gesture.
- Broad gray-brown rat head with a self-satisfied promotional smile.
- Function: the fusion of betting promotion, entertainment, and ostentation.

#### Rato 03 — Ciro Nogueira

- Short salt-and-pepper hair integrated with dark rat fur.
- Navy suit, white shirt, lavender tie, metal watch, and committee microphone.
- Composed, institutionally practiced expression.
- Function: political and institutional proximity to the betting ecosystem.

Three rats are sufficient for the initial cut. A fourth character is added only
if the completed storyboard reveals a missing narrative function.

### 4.5 Factual guardrails

The film may use verified public associations and documented allegations as
the basis for satire. It must not invent quotes, convictions, payments, crimes,
or private conduct.

- Virginia Fonseca publicly confirmed advertising contracts with Esportes da
  Sorte and Blaze. She stated that a bonus depended on company profit and
  denied direct remuneration from follower losses. The CPI rapporteur proposed
  findings against her, but the final report was rejected 4–3 and did not
  become an official CPI conclusion.
- MauMau ZK has public promotional associations with betting projects and was
  reported as a target of Operação Desfortuna. Investigation is not presented
  as conviction.
- Public reporting and a Transparency International retrospective describe
  allegations of personal and financial links between Ciro Nogueira and a
  betting entrepreneur. These remain allegations and are not presented as a
  judicial finding.
- None of the three characters receives fabricated dialogue.

Research references:

- <https://www.gov.br/mj/pt-br/assuntos/noticias-1/governo-federal-proibe-bets-em-todo-o-pais-e-lanca-pacote-de-protecao-as-familias-endividadas-1>
- <https://www12.senado.leg.br/noticias/materias/2025/05/13/influenciadora-virginia-diz-que-nao-lucra-com-perdas-de-seguidores-em-jogos>
- <https://www12.senado.leg.br/noticias/materias/2025/06/12/cpi-das-bets-rejeita-relatorio-final>
- <https://osinfiltradosnacopa.com/>
- <https://vejasp.abril.com.br/cidades/influenciadores-sao-alvos-de-operacao-contra-jogo-do-tigrinho/>
- <https://transparenciainternacional.org.br/posts/as-revelacoes-e-fracassos-da-cpi-das-bets/>
- <https://www.intercept.com.br/2026/03/28/bet-ciro-nogueira-perfis-de-fofoca-extrema-direita/>

### 4.6 Narrative structure

| Time | Beat | Content |
| --- | --- | --- |
| 0–4 s | The signal ended | A news voice announces the ban. A man continues tapping his betting app. |
| 4–10 s | The house disappears | Groceries, a bank card, a work helmet, and family portraits turn into luminous ribbons and enter the phone. The family loses color. |
| 10–14 s | Influence | Virginia-rat smiles and gives a positive gesture at the CPI microphone. |
| 14–18 s | Promotion | MauMau-rat poses before promotional panels. The ribbons become gold chains. |
| 18–23 s | Power | Ciro-rat speaks into a committee microphone while ribbons pass under the institutional table and into the corridors. |
| 23–30 s | What remained | Return to the nearly empty room. The screen collapses to a white dot; the family remains isolated in the reflection. |

The political image is satirical and symbolic. The edit does not present the
ribbons as documentary footage of a specific payment.

### 4.7 Approved narration

> Em 2026, o Brasil tirou as bets do ar.  
> Mas, antes disso, elas já tinham entrado em casa.  
> Primeiro levaram o troco.  
> Depois, as compras.  
> Depois, o tempo.  
> Enquanto uns perdiam tudo,  
> outros sorriam para a câmera.  
> O sinal acabou.  
> O prejuízo ficou.

The delivery is restrained Brazilian television reportage from the 1990s,
without performed outrage.

### 4.8 Sound design

- Begin with an excessively cheerful broadcast jingle.
- Use electronic confirmations resembling a cash register when objects vanish.
- Add camera shutters and compressed applause around the public figures.
- Use nearly imperceptible teeth and whisker sounds, never comic rat squeaks.
- Gradually detune and slow the music.
- End with television hum, CRT collapse, and a dry power-off click.
- The only required editorial overlay is the final line:
  **“O sinal acabou. O prejuízo ficou.”**

### 4.9 Production approach

Use a hybrid strategy:

- the family and disappearing-house sequences may use generated video;
- rat characters begin from approved identity-preserving keyframes;
- rat motion remains controlled: breathing, eye movement, restrained mouth and
  hand movement, broadcast-camera correction, and analog interference;
- image segments remain a supported fallback using subtle push, crop,
  parallax, and degradation effects;
- all generated motion is approved scene by scene before composition.

## 5. Repository Structure

The existing four-document project format remains intact. Production tracking
and composition are additions, not replacements.

```text
projects/
`-- a-casa-inteira-foi-apostada/
    |-- project.yaml
    |-- brief.yaml
    |-- script.yaml
    |-- storyboard.yaml
    |-- visual-bible.md
    |-- composition.yaml
    |-- characters/
    |   |-- virginia-fonseca.md
    |   |-- maumau-zk.md
    |   `-- ciro-nogueira.md
    |-- prompts/
    |   |-- image/
    |   |-- video/
    |   `-- audio/
    |-- production/
    |   |-- scene-001/
    |   |   `-- production.yaml
    |   `-- ...
    |-- media/       # ignored by Git
    `-- output/      # ignored by Git
```

Character documents contain approved visual invariants and public-source notes.
They do not contain source images. Reference images and generated media live
under ignored media directories.

## 6. Production Domain

### 6.1 Asset

An `Asset` represents one local media file.

Required fields:

- `id`
- `kind`: `image`, `video`, or `audio`
- `path`: project-relative local path
- `sha256`
- `mime_type`
- `created_at`

Kind-specific metadata is validated when available:

- images: width and height;
- videos: width, height, duration, frame rate, video codec, and optional audio;
- audio: duration, sample rate, and channel count.

Asset identifiers are stable. Renaming a file does not silently create a new
asset when the checksum is unchanged.

### 6.2 GenerationAttempt

A `GenerationAttempt` records how one or more assets were created or imported.

Fields:

- `id`
- `scene_id`
- `kind`
- `created_at`
- `method`: for example `imagegen`, `external`, `manual`, or `derived`
- optional `provider` and `model`
- optional project-relative `prompt_path`
- `asset_ids`
- `status`: `candidate`, `rejected`, or `approved`
- optional notes

The workflow does not require credentials or remote generation APIs to load a
project. Provider and model are provenance strings only in this iteration.

### 6.3 SceneProduction

Each scene owns one `production.yaml` containing:

- schema version;
- project and scene identifiers;
- production status;
- attempts;
- assets;
- selections by role;
- optional review notes.

Supported selection roles are initially:

- `key_image`
- `video`
- `narration`
- `ambience`
- `music`
- `sfx`

Selecting an asset marks the corresponding attempt approved. For an attempt
with multiple outputs, that status means the attempt produced at least one
currently selected asset; it does not implicitly approve every output. The
selection map remains the source of truth for the exact approved asset.
Replacing a selection does not delete or rewrite the previous attempt.

## 7. Composition Domain

`composition.yaml` is a versioned `CompositionPlan`.

It contains:

- schema version and project identifier;
- output format or an explicit reference to the project format;
- ordered visual timeline items;
- audio timeline items;
- overlays;
- transition and motion presets;
- output filename.

Each visual item references a scene and a selected asset role rather than a raw
path. This keeps the timeline stable when a different attempt becomes selected.

Initial visual operations are deliberately small:

- hard cut;
- short dissolve;
- scale and crop to project aspect ratio;
- freeze or trim video;
- subtle still-image push or pull;
- optional analog degradation preset;
- static text overlay.

Initial audio operations are:

- place, trim, and fade;
- mix narration, music, ambience, and effects;
- lower music under narration;
- normalize the final program to a social-video-safe target;
- encode AAC audio in the MP4.

The default final output is H.264, `yuv420p`, 1080×1920, 30 fps, AAC audio at
48 kHz, matching the pilot project's format.

## 8. Application Workflow

The package exposes a small CLI through a `videos-llm` console script. Codex
operates it during the conversation.

Required operations:

```text
videos-llm validate <project-directory>
videos-llm production import <project-directory> <scene-id> <media-path> ...
videos-llm production select <project-directory> <scene-id> <role> <asset-id>
videos-llm compose <project-directory> [--preview] [--output <path>]
```

`import` copies media into the project's ignored media area using a stable,
collision-safe filename, extracts metadata, calculates the checksum, and adds
an attempt to the correct scene document.

`select` validates that the asset belongs to the scene and is compatible with
the requested role.

`compose` loads and validates the project, every referenced production document,
and the composition plan before launching FFmpeg.

## 9. Data Flow

1. Load and cross-validate the four creative YAML documents.
2. Generate or receive a scene candidate.
3. Import the candidate and record provenance plus metadata.
4. Present alternatives to the user.
5. Record the selected role without removing previous candidates.
6. Resolve composition timeline roles into selected asset paths.
7. Validate formats, durations, and required audio.
8. Build a deterministic FFmpeg command.
9. Render to a new output path.
10. Validate that the output exists, is non-empty, and matches required media
    metadata before reporting success.

## 10. Error Handling and Safety

The system fails before rendering when:

- a required creative or production document is missing;
- a scene or asset identifier is invalid;
- a selected asset is missing or its checksum changed;
- a composition role has no selected asset;
- media metadata cannot be read;
- a video or audio duration is invalid;
- the timeline contains overlaps not supported by the schema;
- FFmpeg is unavailable;
- the destination exists and overwrite was not explicitly requested.

Failures identify the project, scene, role, asset, or timeline item involved.
No failed import rewrites an existing `production.yaml`. Rendering uses a
temporary sibling file and moves it to the destination only after successful
completion.

## 11. FFmpeg Runtime

Use `imageio-ffmpeg` to obtain a project-managed FFmpeg executable rather than
requiring a global installation. The application invokes the executable
directly and keeps command construction in a dedicated adapter.

Media probing uses the same runtime. Implementation must not depend on a
separate globally installed `ffprobe` executable.

## 12. Testing Strategy

### Unit tests

- production model validation;
- duplicate attempt and asset identifiers;
- checksum and path validation;
- selection compatibility;
- composition model validation;
- timeline resolution;
- command construction and escaping;
- refusal to overwrite an output by default.

### Integration tests

- import a synthetic image, video, and audio asset;
- select assets for a small two-scene fixture;
- render a short MP4 with generated fixture media;
- verify dimensions, frame rate, duration tolerance, video codec, audio presence,
  and non-empty output;
- confirm a failed render does not leave a file at the final destination.

### Regression tests

- the existing Phase 0 templates continue to load unchanged;
- the current manual projects continue to validate without production files;
- projects need production and composition documents only when invoking their
  corresponding workflows.

## 13. Acceptance Criteria

The implementation is complete when:

- the existing 34-test baseline remains green;
- production documents load with readable validation errors;
- real local assets can be imported and selected per scene;
- replacing a selection preserves prior attempts;
- `composition.yaml` resolves scene roles into selected assets;
- a preview and a final MP4 can be rendered without a global FFmpeg install;
- the final output is not reported successful until its media metadata is
  validated;
- the pilot project's creative documents and character guides are present;
- the first pilot preview can be assembled from approved scene assets;
- no publication, analytics, credential management, or provider automation is
  introduced.

## 14. Roadmap Effect

This design intentionally implements a narrow vertical slice across the old
Phase 2 production-tracking milestone and the minimum useful portion of the old
Phase 4 composition milestone. That change reflects the agreed product goal:
scene-by-scene creative collaboration that ends in a finished MP4.

Prompt templating and provider automation remain later work. They are not
prerequisites for learning from the pilot production.
