from __future__ import annotations

import mimetypes
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import imageio_ffmpeg
from PIL import Image, UnidentifiedImageError

from videos_llm.domain.production import (
    AssetKind,
    AudioMetadata,
    ImageMetadata,
    VideoMetadata,
)


@dataclass(frozen=True)
class ProbedMedia:
    kind: AssetKind
    mime_type: str
    metadata: ImageMetadata | VideoMetadata | AudioMetadata


class FfmpegError(RuntimeError):
    """Raised when managed FFmpeg is unavailable or media cannot be read."""


def get_ffmpeg_executable() -> Path:
    executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if not executable.is_file():
        raise FfmpegError(
            f"managed FFmpeg executable is unavailable: {executable}"
        )
    return executable


def run_ffmpeg(
    arguments: Sequence[str],
    *,
    ffmpeg_executable: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = (
        Path(ffmpeg_executable)
        if ffmpeg_executable is not None
        else get_ffmpeg_executable()
    )
    if not executable.is_file():
        raise FfmpegError(f"FFmpeg executable is unavailable: {executable}")
    try:
        result = subprocess.run(
            [str(executable), "-hide_banner", "-nostdin", *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise FfmpegError(f"could not launch FFmpeg {executable}: {error}") from error
    if result.returncode != 0:
        message = (
            result.stderr.strip().splitlines()[-1]
            if result.stderr.strip()
            else "unknown FFmpeg error"
        )
        raise FfmpegError(f"FFmpeg failed ({result.returncode}): {message}")
    return result


def _seconds_from_duration(output: str) -> float:
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:[.,]\d+)?)",
        output,
    )
    if match is None:
        raise FfmpegError("media duration is missing or unknown")
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(
        seconds.replace(",", ".")
    )
    if duration <= 0:
        raise FfmpegError("media duration must be positive")
    return duration


def _stream_line(output: str, marker: str) -> str | None:
    return next((line.strip() for line in output.splitlines() if marker in line), None)


def _codec(stream_line: str, marker: str) -> str:
    value = stream_line.split(marker, 1)[1].lstrip()
    codec = value.split(",", 1)[0].split(None, 1)[0]
    if not codec:
        raise FfmpegError(f"could not read {marker.rstrip(':').lower()} codec")
    return codec


def _mime_type(path: Path, kind: AssetKind) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    normalizations = {
        "audio/x-wav": "audio/wav",
        "audio/vnd.wave": "audio/wav",
        "video/quicktime": "video/quicktime",
    }
    if guessed:
        guessed = normalizations.get(guessed, guessed)
        if guessed.startswith(f"{kind.value}/"):
            return guessed
    defaults = {
        AssetKind.IMAGE: "image/png",
        AssetKind.VIDEO: "video/mp4",
        AssetKind.AUDIO: "audio/wav",
    }
    return defaults[kind]


def _channel_count(audio_line: str) -> int:
    lowered = audio_line.lower()
    if re.search(r"\bmono\b", lowered):
        return 1
    if re.search(r"\bstereo\b", lowered):
        return 2
    surround = re.search(r"\b(5\.1|7\.1)\b", lowered)
    if surround:
        return 6 if surround.group(1) == "5.1" else 8
    explicit = re.search(r"\b(\d+)\s+channels?\b", lowered)
    if explicit:
        return int(explicit.group(1))
    raise FfmpegError("could not read audio channel count")


def probe_media(
    path: str | Path,
    ffmpeg_executable: str | Path | None = None,
) -> ProbedMedia:
    media_path = Path(path)
    if not media_path.is_file():
        raise FfmpegError(f"media file does not exist: {media_path}")

    try:
        with Image.open(media_path) as image:
            image.verify()
            width, height = image.size
            mime_type = Image.MIME.get(image.format or "")
            if mime_type is None:
                mime_type = _mime_type(media_path, AssetKind.IMAGE)
            return ProbedMedia(
                kind=AssetKind.IMAGE,
                mime_type=mime_type,
                metadata=ImageMetadata(width=width, height=height),
            )
    except (OSError, UnidentifiedImageError):
        pass

    try:
        result = run_ffmpeg(
            ["-i", str(media_path), "-map", "0", "-f", "null", "-"],
            ffmpeg_executable=ffmpeg_executable,
        )
    except FfmpegError as error:
        raise FfmpegError(f"could not probe {media_path}: {error}") from error

    output = f"{result.stdout}\n{result.stderr}"
    duration = _seconds_from_duration(output)
    video_line = _stream_line(output, "Video:")
    audio_line = _stream_line(output, "Audio:")

    if video_line is not None:
        dimensions = re.search(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", video_line)
        fps = re.search(r"(\d+(?:[.,]\d+)?)\s+fps\b", video_line)
        if dimensions is None or fps is None:
            raise FfmpegError(f"could not read video dimensions or FPS: {media_path}")
        return ProbedMedia(
            kind=AssetKind.VIDEO,
            mime_type=_mime_type(media_path, AssetKind.VIDEO),
            metadata=VideoMetadata(
                width=int(dimensions.group(1)),
                height=int(dimensions.group(2)),
                duration_seconds=duration,
                frame_rate=float(fps.group(1).replace(",", ".")),
                codec=_codec(video_line, "Video:"),
                has_audio=audio_line is not None,
            ),
        )

    if audio_line is not None:
        sample_rate = re.search(r"(\d+)\s+Hz\b", audio_line)
        if sample_rate is None:
            raise FfmpegError(f"could not read audio sample rate: {media_path}")
        return ProbedMedia(
            kind=AssetKind.AUDIO,
            mime_type=_mime_type(media_path, AssetKind.AUDIO),
            metadata=AudioMetadata(
                duration_seconds=duration,
                sample_rate=int(sample_rate.group(1)),
                channels=_channel_count(audio_line),
                codec=_codec(audio_line, "Audio:"),
            ),
        )

    raise FfmpegError(f"no supported media stream found: {media_path}")
