from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from videos_llm.application.composition_service import (
    ResolvedAudioItem,
    ResolvedVisualItem,
)
from videos_llm.domain.composition import AudioItem, TextOverlay, VisualItem
from videos_llm.domain.production import (
    Asset,
    AudioMetadata,
    ImageMetadata,
    VideoMetadata,
)
from videos_llm.infrastructure.compositor import (
    RenderProfile,
    build_audio_filter,
    build_visual_filter,
    create_overlay_image,
)


def asset(asset_id: str, kind: str) -> Asset:
    metadata = (
        ImageMetadata(width=64, height=96)
        if kind == "image"
        else VideoMetadata(
            width=64,
            height=96,
            duration_seconds=1,
            frame_rate=30,
            codec="h264",
            has_audio=False,
        )
        if kind == "video"
        else AudioMetadata(
            duration_seconds=2,
            sample_rate=48000,
            channels=1,
            codec="pcm_s16le",
        )
    )
    suffix = {"image": "png", "video": "mp4", "audio": "wav"}[kind]
    mime = {"image": "image/png", "video": "video/mp4", "audio": "audio/wav"}[
        kind
    ]
    return Asset(
        id=asset_id,
        kind=kind,
        path=f"media/scene-001/{kind}/{asset_id}.{suffix}",
        sha256="a" * 64,
        mime_type=mime,
        created_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        metadata=metadata,
    )


def two_resolved_images() -> list[ResolvedVisualItem]:
    return [
        ResolvedVisualItem(
            item=VisualItem(
                id="visual-one",
                scene_id="scene-001",
                role="key_image",
                start_seconds=0,
                duration_seconds=1,
            ),
            asset=asset("asset-a1b2c3d4e5f6", "image"),
            path=Path("one.png"),
        ),
        ResolvedVisualItem(
            item=VisualItem(
                id="visual-two",
                scene_id="scene-002",
                role="key_image",
                start_seconds=1,
                duration_seconds=1,
            ),
            asset=asset("asset-001122334455", "image"),
            path=Path("two.png"),
        ),
    ]


def two_resolved_videos(transition: str) -> list[ResolvedVisualItem]:
    transition_seconds = 0.25 if transition == "dissolve" else 0
    start = 0.75 if transition == "dissolve" else 1
    return [
        ResolvedVisualItem(
            item=VisualItem(
                id="visual-one",
                scene_id="scene-001",
                role="video",
                start_seconds=0,
                duration_seconds=1,
            ),
            asset=asset("asset-a1b2c3d4e5f6", "video"),
            path=Path("one.mp4"),
        ),
        ResolvedVisualItem(
            item=VisualItem(
                id="visual-two",
                scene_id="scene-002",
                role="video",
                start_seconds=start,
                duration_seconds=1,
                transition=transition,
                transition_seconds=transition_seconds,
            ),
            asset=asset("asset-001122334455", "video"),
            path=Path("two.mp4"),
        ),
    ]


def narration_and_music() -> list[ResolvedAudioItem]:
    return [
        ResolvedAudioItem(
            item=AudioItem(
                id="audio-voice",
                scene_id="scene-001",
                role="narration",
                start_seconds=0,
                duration_seconds=2,
            ),
            asset=asset("asset-a1b2c3d4e5f6", "audio"),
            path=Path("voice.wav"),
            effective_duration_seconds=2,
        ),
        ResolvedAudioItem(
            item=AudioItem(
                id="audio-music",
                scene_id="scene-001",
                role="music",
                start_seconds=0,
                duration_seconds=2,
                gain_db=-6,
            ),
            asset=asset("asset-001122334455", "audio"),
            path=Path("music.wav"),
            effective_duration_seconds=2,
        ),
    ]


def test_visual_filter_normalizes_and_concatenates_hard_cuts() -> None:
    graph, label = build_visual_filter(
        two_resolved_images(),
        RenderProfile.preview(),
    )
    assert "scale=360:640:force_original_aspect_ratio=increase" in graph
    assert "crop=360:640" in graph
    assert "fps=30" in graph
    assert "concat=n=2:v=1:a=0" in graph
    assert label == "[video_out]"


def test_visual_filter_uses_xfade_for_dissolve() -> None:
    graph, _ = build_visual_filter(
        two_resolved_videos(transition="dissolve"),
        RenderProfile.preview(),
    )
    assert "xfade=transition=fade:duration=0.25:offset=0.75" in graph


def test_visual_filter_adds_still_motion_and_analog_degradation() -> None:
    items = two_resolved_images()
    items[0] = ResolvedVisualItem(
        item=items[0].item.model_copy(
            update={"motion": "push_in", "analog_preset": "betacam_light"}
        ),
        asset=items[0].asset,
        path=items[0].path,
    )
    graph, _ = build_visual_filter(items, RenderProfile.preview())
    assert "zoompan=" in graph
    assert "chromashift=" in graph
    assert "noise=" in graph


def test_audio_filter_ducks_music_under_narration() -> None:
    graph, label = build_audio_filter(
        narration_and_music(),
        total_duration=2.0,
    )
    assert "sidechaincompress" in graph
    assert "aresample=48000" in graph
    assert "amix=" in graph
    assert label == "[audio_out]"


def test_audio_filter_generates_silence_when_no_audio_is_selected() -> None:
    graph, label = build_audio_filter([], total_duration=2.0)
    assert "anullsrc=r=48000:cl=stereo" in graph
    assert "atrim=duration=2" in graph
    assert label == "[audio_out]"


def test_overlay_png_is_created_with_exact_text(tmp_path: Path) -> None:
    path = create_overlay_image(
        TextOverlay(
            id="overlay-end",
            text="O sinal acabou. O prejuízo ficou.",
            start_seconds=1,
            duration_seconds=1,
        ),
        RenderProfile.preview(),
        tmp_path,
    )
    assert path.is_file()
    with Image.open(path) as image:
        assert image.mode == "RGBA"
        assert image.size == (360, 640)
