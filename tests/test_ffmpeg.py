from pathlib import Path

import pytest

from media_factory import make_audio, make_image, make_video
from videos_llm.domain.production import (
    AssetKind,
    AudioMetadata,
    ImageMetadata,
    VideoMetadata,
)
from videos_llm.infrastructure.ffmpeg import (
    FfmpegError,
    get_ffmpeg_executable,
    probe_media,
    run_ffmpeg,
)


def test_probe_image_reads_dimensions_without_ffmpeg(tmp_path: Path) -> None:
    probed = probe_media(make_image(tmp_path / "still.png"))
    assert probed.kind is AssetKind.IMAGE
    assert probed.mime_type == "image/png"
    assert probed.metadata == ImageMetadata(width=64, height=96)


def test_probe_video_reads_required_metadata(tmp_path: Path) -> None:
    ffmpeg = get_ffmpeg_executable()
    probed = probe_media(make_video(tmp_path / "clip.mp4", ffmpeg), ffmpeg)
    assert probed.kind is AssetKind.VIDEO
    assert probed.mime_type == "video/mp4"
    assert isinstance(probed.metadata, VideoMetadata)
    assert probed.metadata.width == 64
    assert probed.metadata.height == 96
    assert probed.metadata.duration_seconds == pytest.approx(1.0, abs=0.1)
    assert probed.metadata.frame_rate == pytest.approx(30.0)
    assert probed.metadata.codec == "h264"
    assert probed.metadata.has_audio is False


def test_probe_audio_reads_required_metadata(tmp_path: Path) -> None:
    ffmpeg = get_ffmpeg_executable()
    probed = probe_media(make_audio(tmp_path / "tone.wav", ffmpeg), ffmpeg)
    assert probed.kind is AssetKind.AUDIO
    assert probed.mime_type == "audio/wav"
    assert isinstance(probed.metadata, AudioMetadata)
    assert probed.metadata.duration_seconds == pytest.approx(1.0, abs=0.1)
    assert probed.metadata.sample_rate == 48000
    assert probed.metadata.channels == 1
    assert probed.metadata.codec == "pcm_s16le"


def test_get_ffmpeg_reports_missing_managed_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "imageio_ffmpeg.get_ffmpeg_exe",
        lambda: "C:/definitely-missing/ffmpeg.exe",
    )
    with pytest.raises(FfmpegError, match="managed FFmpeg"):
        get_ffmpeg_executable()


def test_run_ffmpeg_reports_process_failure() -> None:
    with pytest.raises(FfmpegError, match="FFmpeg failed"):
        run_ffmpeg(["-definitely-not-a-real-option"])
