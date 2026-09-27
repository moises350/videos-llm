from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence
from uuid import uuid4

from PIL import Image, ImageColor, ImageDraw, ImageFont

from videos_llm.application.composition_service import (
    ResolvedComposition,
    ResolvedAudioItem,
    ResolvedVisualItem,
)
from videos_llm.domain.composition import TextOverlay
from videos_llm.domain.models import Project
from videos_llm.domain.production import AssetKind, SelectionRole
from videos_llm.domain.production import VideoMetadata
from videos_llm.infrastructure.ffmpeg import (
    FfmpegError,
    probe_media,
    run_ffmpeg,
)


@dataclass(frozen=True)
class RenderProfile:
    width: int
    height: int
    fps: float
    video_bitrate: str
    audio_bitrate: str = "192k"

    @classmethod
    def preview(cls) -> RenderProfile:
        return cls(
            width=360,
            height=640,
            fps=30,
            video_bitrate="1200k",
            audio_bitrate="128k",
        )

    @classmethod
    def final(cls, project: Project) -> RenderProfile:
        return cls(
            width=project.format.width,
            height=project.format.height,
            fps=project.format.fps,
            video_bitrate="8000k",
        )


class RenderError(RuntimeError):
    """Raised when a composition cannot be rendered and verified."""


def _number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _analog_filters(preset: str) -> list[str]:
    if preset == "none":
        return []
    strength = "3" if preset == "betacam_light" else "7"
    opacity = "0.06" if preset == "betacam_light" else "0.12"
    return [
        "eq=saturation=0.88:contrast=1.04",
        f"noise=alls={strength}:allf=t+u",
        "chromashift=cbh=1:crh=-1",
        f"tblend=all_mode=average:all_opacity={opacity}",
    ]


def build_visual_filter(
    items: Sequence[ResolvedVisualItem],
    profile: RenderProfile,
    *,
    input_offset: int = 0,
) -> tuple[str, str]:
    if not items:
        raise RenderError("composition has no visual items")

    filters: list[str] = []
    fps = _number(profile.fps)
    for index, resolved in enumerate(items):
        item = resolved.item
        chain = [
            (
                f"scale={profile.width}:{profile.height}:"
                "force_original_aspect_ratio=increase"
            ),
            f"crop={profile.width}:{profile.height}",
            "setsar=1",
            f"fps={fps}",
            (
                f"trim=start={_number(item.trim_start_seconds)}:"
                f"duration={_number(item.duration_seconds)}"
            ),
            "setpts=PTS-STARTPTS",
        ]
        if resolved.asset.kind is AssetKind.IMAGE and item.motion != "static":
            zoom = (
                "min(zoom+0.001,1.05)"
                if item.motion == "push_in"
                else "if(lte(zoom,1.0),1.05,max(1.0,zoom-0.001))"
            )
            chain.append(
                f"zoompan=z='{zoom}':d=1:s={profile.width}x{profile.height}:fps={fps}"
            )
        chain.extend(_analog_filters(item.analog_preset))
        filters.append(
            f"[{input_offset + index}:v]{','.join(chain)}[v{index}]"
        )

    if len(items) == 1:
        filters.append("[v0]null[video_out]")
        return ";".join(filters), "[video_out]"

    current = "[v0]"
    for index, resolved in enumerate(items[1:], start=1):
        output = "[video_out]" if index == len(items) - 1 else f"[vjoin{index}]"
        item = resolved.item
        if item.transition == "dissolve":
            filters.append(
                f"{current}[v{index}]xfade=transition=fade:"
                f"duration={_number(item.transition_seconds)}:"
                f"offset={_number(item.start_seconds)}{output}"
            )
        else:
            filters.append(
                f"{current}[v{index}]concat=n=2:v=1:a=0{output}"
            )
        current = output
    return ";".join(filters), "[video_out]"


def build_audio_filter(
    items: Sequence[ResolvedAudioItem],
    total_duration: float,
    *,
    input_offset: int = 0,
) -> tuple[str, str]:
    total = _number(total_duration)
    if not items:
        return (
            f"anullsrc=r=48000:cl=stereo,atrim=duration={total}[audio_out]",
            "[audio_out]",
        )

    filters: list[str] = []
    roles: dict[SelectionRole, list[str]] = defaultdict(list)
    for index, resolved in enumerate(items):
        item = resolved.item
        duration = resolved.effective_duration_seconds
        chain = [
            (
                f"atrim=start={_number(item.trim_start_seconds)}:"
                f"duration={_number(duration)}"
            ),
            "asetpts=PTS-STARTPTS",
            "aresample=48000",
            f"volume={_number(item.gain_db)}dB",
        ]
        if item.fade_in_seconds > 0:
            chain.append(
                f"afade=t=in:st=0:d={_number(item.fade_in_seconds)}"
            )
        if item.fade_out_seconds > 0:
            fade_start = max(0.0, duration - item.fade_out_seconds)
            chain.append(
                f"afade=t=out:st={_number(fade_start)}:"
                f"d={_number(item.fade_out_seconds)}"
            )
        delay = round(item.start_seconds * 1000)
        chain.append(f"adelay={delay}|{delay}")
        label = f"[audio_item_{index}]"
        filters.append(
            f"[{input_offset + index}:a]{','.join(chain)}{label}"
        )
        roles[SelectionRole(item.role)].append(label)

    buses: dict[SelectionRole, str] = {}
    for role, labels in roles.items():
        bus = f"[{role.value}_bus]"
        if len(labels) == 1:
            filters.append(f"{labels[0]}anull{bus}")
        else:
            filters.append(
                f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0{bus}"
            )
        buses[role] = bus

    mix_labels: list[str] = []
    narration = buses.get(SelectionRole.NARRATION)
    music = buses.get(SelectionRole.MUSIC)
    if narration and music:
        filters.append(
            f"{narration}asplit=2[narration_mix][narration_side]"
        )
        filters.append(
            f"{music}[narration_side]sidechaincompress="
            "threshold=0.05:ratio=8[ducked_music]"
        )
        mix_labels.extend(["[narration_mix]", "[ducked_music]"])
    else:
        if narration:
            mix_labels.append(narration)
        if music:
            mix_labels.append(music)

    for role in (SelectionRole.AMBIENCE, SelectionRole.SFX):
        if role in buses:
            mix_labels.append(buses[role])

    if len(mix_labels) == 1:
        mixed = mix_labels[0]
    else:
        filters.append(
            f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:"
            "normalize=0[audio_mix]"
        )
        mixed = "[audio_mix]"
    filters.append(
        f"{mixed}alimiter=limit=0.95,atrim=duration={total}[audio_out]"
    )
    return ";".join(filters), "[audio_out]"


def _wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        box = draw.textbbox((0, 0), candidate, font=font)
        if current and box[2] - box[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def create_overlay_image(
    overlay: TextOverlay,
    profile: RenderProfile,
    directory: str | Path,
) -> Path:
    output_directory = Path(directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / f"{overlay.id}.png"
    canvas = Image.new("RGBA", (profile.width, profile.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    scaled_size = max(8, round(overlay.font_size * profile.width / 1080))
    font = ImageFont.load_default(size=scaled_size)
    text = _wrapped_text(draw, overlay.text, font, round(profile.width * 0.84))
    box = draw.multiline_textbbox(
        (0, 0),
        text,
        font=font,
        align="center",
        spacing=round(scaled_size * 0.25),
    )
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    positions = {
        "top": round(profile.height * 0.14),
        "center": round((profile.height - text_height) / 2),
        "bottom": round(profile.height * 0.82 - text_height),
    }
    x = round((profile.width - text_width) / 2)
    y = positions[overlay.position]
    padding = max(5, round(scaled_size * 0.5))
    draw.rounded_rectangle(
        (x - padding, y - padding, x + text_width + padding, y + text_height + padding),
        radius=max(3, round(padding * 0.5)),
        fill=(0, 0, 0, 150),
    )
    color = (*ImageColor.getrgb(overlay.color), 255)
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=color,
        align="center",
        spacing=round(scaled_size * 0.25),
    )
    canvas.save(path)
    return path


def render_resolved_composition(
    resolved: ResolvedComposition,
    destination: str | Path,
    profile: RenderProfile,
    *,
    overwrite: bool = False,
    ffmpeg_executable: str | Path | None = None,
) -> Path:
    output = Path(destination)
    if output.exists() and not overwrite:
        raise RenderError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_name(
        f".{output.stem}.{uuid4().hex}.part.mp4"
    )

    total_duration = resolved.plan.duration_seconds
    input_arguments: list[str] = []
    for item in resolved.visual_items:
        if item.asset.kind is AssetKind.IMAGE:
            input_arguments.extend(
                [
                    "-loop",
                    "1",
                    "-framerate",
                    _number(profile.fps),
                    "-t",
                    _number(item.item.duration_seconds),
                ]
            )
        input_arguments.extend(["-i", str(item.path)])

    for item in resolved.audio_items:
        input_arguments.extend(["-i", str(item.path)])

    try:
        with TemporaryDirectory(
            prefix="videos-llm-overlays-",
            dir=output.parent,
        ) as overlay_directory:
            overlay_paths = [
                create_overlay_image(overlay, profile, overlay_directory)
                for overlay in resolved.plan.overlays
            ]
            for overlay_path in overlay_paths:
                input_arguments.extend(
                    [
                        "-loop",
                        "1",
                        "-framerate",
                        _number(profile.fps),
                        "-t",
                        _number(total_duration),
                        "-i",
                        str(overlay_path),
                    ]
                )

            visual_graph, video_label = build_visual_filter(
                resolved.visual_items,
                profile,
            )
            audio_graph, audio_label = build_audio_filter(
                resolved.audio_items,
                total_duration,
                input_offset=len(resolved.visual_items),
            )
            graph_parts = [visual_graph, audio_graph]
            current_video = video_label
            overlay_offset = len(resolved.visual_items) + len(
                resolved.audio_items
            )
            for index, overlay in enumerate(resolved.plan.overlays):
                output_label = (
                    "[video_final]"
                    if index == len(resolved.plan.overlays) - 1
                    else f"[video_overlay_{index}]"
                )
                start = _number(overlay.start_seconds)
                end = _number(
                    overlay.start_seconds + overlay.duration_seconds
                )
                graph_parts.append(
                    f"{current_video}[{overlay_offset + index}:v]"
                    f"overlay=enable='between(t,{start},{end})'"
                    f"{output_label}"
                )
                current_video = output_label

            arguments = [
                "-y",
                *input_arguments,
                "-filter_complex",
                ";".join(graph_parts),
                "-map",
                current_video,
                "-map",
                audio_label,
                "-t",
                _number(total_duration),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                _number(profile.fps),
                "-b:v",
                profile.video_bitrate,
                "-c:a",
                "aac",
                "-b:a",
                profile.audio_bitrate,
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(part),
            ]
            run_ffmpeg(arguments, ffmpeg_executable=ffmpeg_executable)

            probed = probe_media(part, ffmpeg_executable=ffmpeg_executable)
            if not isinstance(probed.metadata, VideoMetadata):
                raise RenderError("rendered output has no video metadata")
            metadata = probed.metadata
            if (metadata.width, metadata.height) != (
                profile.width,
                profile.height,
            ):
                raise RenderError(
                    "rendered output dimensions do not match the profile"
                )
            if abs(metadata.frame_rate - profile.fps) > 0.01:
                raise RenderError("rendered output frame rate does not match")
            if metadata.codec not in {"h264", "avc1"}:
                raise RenderError(
                    f"rendered output codec is not H.264: {metadata.codec}"
                )
            if not metadata.has_audio:
                raise RenderError("rendered output has no audio stream")
            frame_tolerance = 2 / profile.fps
            if abs(metadata.duration_seconds - total_duration) > frame_tolerance:
                raise RenderError(
                    "rendered output duration does not match the composition"
                )
            part.replace(output)
    except (FfmpegError, OSError) as error:
        raise RenderError(str(error)) from error
    finally:
        part.unlink(missing_ok=True)

    return output
