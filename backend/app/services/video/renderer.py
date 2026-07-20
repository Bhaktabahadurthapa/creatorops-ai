import tempfile
from dataclasses import replace
from pathlib import Path

from app.services.video.ffmpeg_utils import (
    FFmpegExecutionError,
    escape_filter_path,
    ffmpeg_has_filter,
    probe_duration,
    run_ffmpeg,
)
from app.services.video.cards import generate_text_card
from app.services.video.hyperframes import render_hyperframes_text_scene
from app.services.video.schemas import (
    MotionStrength,
    MotionType,
    RenderScene,
    VideoResolution,
    VideoRenderResult,
)
from app.services.video.subtitles import write_srt


WIDTH = 1920
HEIGHT = 1080
FPS = 30
TRANSITION_SECONDS = 0.4
IMAGE_FADE_SECONDS = 0.4
AUTOMATIC_MOTIONS: tuple[MotionType, ...] = (
    "zoom_in",
    "pan_right",
    "zoom_out",
    "pan_left",
    "pan_up",
    "pan_down",
)
MOTION_STRENGTHS: dict[MotionStrength, float] = {
    "subtle": 0.12,
    "medium": 0.18,
    "strong": 0.25,
}
OUTPUT_DIMENSIONS: dict[VideoResolution, tuple[int, int]] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}


class VideoRenderError(RuntimeError):
    """Raised when the local FFmpeg renderer cannot create an MP4."""


def allocate_scene_frames(
    scenes: list[RenderScene],
    audio_duration: float,
    fps: int = FPS,
) -> list[int]:
    total_frames = max(len(scenes), round(audio_duration * fps))
    remaining_frames = total_frames
    remaining_weight = sum(scene.duration_seconds for scene in scenes)
    allocations: list[int] = []

    for index, scene in enumerate(scenes):
        remaining_scenes = len(scenes) - index
        if remaining_scenes == 1:
            frame_count = remaining_frames
        else:
            proportional = round(
                remaining_frames * scene.duration_seconds / remaining_weight
            )
            frame_count = min(
                max(1, proportional),
                remaining_frames - (remaining_scenes - 1),
            )
        allocations.append(frame_count)
        remaining_frames -= frame_count
        remaining_weight -= scene.duration_seconds

    return allocations


def calculate_transition_frames(
    scene_frames: list[int],
    fps: int = FPS,
) -> list[int]:
    maximum = round(TRANSITION_SECONDS * fps)
    minimum = max(2, round(0.1 * fps))
    transitions: list[int] = []
    for left_frames, right_frames in zip(scene_frames, scene_frames[1:]):
        safe_frames = min(maximum, min(left_frames, right_frames) // 3)
        transitions.append(safe_frames if safe_frames >= minimum else 0)
    return transitions


def calculate_render_frames(
    scene_frames: list[int],
    transition_frames: list[int],
) -> list[int]:
    if len(transition_frames) != max(0, len(scene_frames) - 1):
        raise ValueError("Transition count must match the scene boundaries.")
    return [
        frame_count
        + (transition_frames[index] if index < len(transition_frames) else 0)
        for index, frame_count in enumerate(scene_frames)
    ]


def resolve_motion_type(motion_type: MotionType, scene_number: int) -> MotionType:
    if motion_type != "automatic":
        return motion_type
    return AUTOMATIC_MOTIONS[(scene_number - 1) % len(AUTOMATIC_MOTIONS)]


def render_video(
    *,
    audio_path: Path,
    scenes: list[RenderScene],
    output_path: Path,
    subtitle_path: Path,
    logo_path: Path | None = None,
    background_music_path: Path | None = None,
    resolution: VideoResolution = "1080p",
) -> VideoRenderResult:
    if not audio_path.is_file():
        raise FileNotFoundError("Narration audio was not found.")
    if not scenes:
        raise ValueError("At least one video scene is required.")
    if any(
        scene.media_type != "generated"
        and (scene.media_path is None or not scene.media_path.is_file())
        for scene in scenes
    ):
        raise FileNotFoundError("One or more scene media files are missing.")

    try:
        audio_duration = probe_duration(audio_path)
        frame_allocations = allocate_scene_frames(scenes, audio_duration)
        transition_frames = calculate_transition_frames(frame_allocations)
        use_crossfades = (
            bool(transition_frames)
            and all(frame_count > 0 for frame_count in transition_frames)
            and ffmpeg_has_filter("xfade")
        )
        if not use_crossfades:
            transition_frames = [0] * max(0, len(scenes) - 1)
        render_frame_counts = calculate_render_frames(
            frame_allocations,
            transition_frames,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        subtitle_entries: list[tuple[float, float, str]] = []
        elapsed_frames = 0
        for scene, frame_count in zip(scenes, frame_allocations, strict=True):
            start = elapsed_frames / FPS
            elapsed_frames += frame_count
            subtitle_entries.append((start, elapsed_frames / FPS, scene.subtitle))
        write_srt(subtitle_entries, subtitle_path)

        with tempfile.TemporaryDirectory(
            dir=output_path.parent,
            prefix="video-render-",
        ) as temporary_directory:
            work_dir = Path(temporary_directory)
            scene_paths: list[Path] = []
            for scene, frame_count in zip(
                scenes,
                render_frame_counts,
                strict=True,
            ):
                scene_output = work_dir / f"scene-{scene.scene_number:04d}.mp4"
                render_scene = scene
                if scene.media_type == "generated":
                    hyperframes_path = work_dir / f"hyperframes-{scene.scene_number:04d}.mp4"
                    rendered_with_hyperframes = render_hyperframes_text_scene(
                        scene_number=scene.scene_number,
                        visual_description=scene.visual_description,
                        subtitle=scene.subtitle,
                        duration_seconds=frame_count / FPS,
                        project_dir=work_dir / f"hyperframes-{scene.scene_number:04d}",
                        output_path=hyperframes_path,
                    )
                    if rendered_with_hyperframes:
                        render_scene = replace(
                            scene,
                            media_path=hyperframes_path,
                            media_type="video",
                        )
                    else:
                        card_path = work_dir / f"card-{scene.scene_number:04d}.png"
                        generate_text_card(
                            scene_number=scene.scene_number,
                            visual_description=scene.visual_description,
                            subtitle=scene.subtitle,
                            output_path=card_path,
                        )
                        render_scene = replace(
                            scene,
                            media_path=card_path,
                            media_type="image",
                        )
                _render_scene(render_scene, frame_count, scene_output)
                scene_paths.append(scene_output)

            joined_video = work_dir / "joined.mp4"
            _join_scenes(
                scene_paths=scene_paths,
                scene_frames=frame_allocations,
                transition_frames=transition_frames,
                output_path=joined_video,
                work_dir=work_dir,
            )
            subtitles_burned = ffmpeg_has_filter("subtitles")
            _export_video(
                joined_video=joined_video,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=output_path,
                duration=audio_duration,
                logo_path=logo_path,
                background_music_path=background_music_path,
                burn_subtitles=subtitles_burned,
                resolution=resolution,
            )
    except (FFmpegExecutionError, OSError, ValueError) as exc:
        output_path.unlink(missing_ok=True)
        raise VideoRenderError(str(exc)) from exc

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise VideoRenderError("Video rendering did not produce an MP4 file.")
    return VideoRenderResult(
        video_path=output_path,
        subtitle_path=subtitle_path,
        subtitles_burned=subtitles_burned,
    )


def _render_scene(scene: RenderScene, frame_count: int, output_path: Path) -> None:
    if scene.media_path is None:
        raise ValueError("A rendered scene requires image or video media.")
    if scene.fit_mode == "cover":
        visual_filter = (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}"
        )
    else:
        visual_filter = (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black"
        )
    visual_filter += ",setsar=1"
    if scene.media_type == "image":
        motion_type = resolve_motion_type(scene.motion_type, scene.scene_number)
        motion_filter = build_image_motion_filter(
            motion_type,
            scene.motion_strength,
            frame_count,
        )
        if motion_filter:
            visual_filter += f",{motion_filter}"
        else:
            visual_filter += f",fps={FPS}"
        visual_filter += f",{_image_fade_filter(frame_count)}"
    else:
        visual_filter += f",fps={FPS}"
    visual_filter += ",format=yuv420p"

    input_options = ["-stream_loop", "-1"] if scene.media_type == "video" else ["-loop", "1"]
    run_ffmpeg(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *input_options,
            "-i",
            str(scene.media_path),
            "-frames:v",
            str(frame_count),
            "-an",
            "-vf",
            visual_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            str(output_path),
        ]
    )


def build_image_motion_filter(
    motion_type: MotionType,
    motion_strength: MotionStrength,
    frame_count: int,
) -> str:
    if motion_type == "none":
        return ""
    if motion_type == "automatic":
        raise ValueError("Automatic motion must be resolved before rendering.")

    last_frame = max(1, frame_count - 1)
    strength = MOTION_STRENGTHS[motion_strength]
    zoom_limit = f"{1 + strength:.2f}"
    zoom_step = f"{strength / last_frame:.6f}"
    progress = f"on/{last_frame}"
    horizontal_center = "(iw-iw/zoom)/2"
    vertical_center = "(ih-ih/zoom)/2"

    if motion_type == "zoom_in":
        zoom = f"min(zoom+{zoom_step},{zoom_limit})"
        x_position = horizontal_center
        y_position = vertical_center
    elif motion_type == "zoom_out":
        zoom = f"max({zoom_limit}-{zoom_step}*on,1.00)"
        x_position = horizontal_center
        y_position = vertical_center
    elif motion_type == "pan_left":
        zoom = zoom_limit
        x_position = f"(iw-iw/zoom)*(1-{progress})"
        y_position = vertical_center
    elif motion_type == "pan_right":
        zoom = zoom_limit
        x_position = f"(iw-iw/zoom)*{progress}"
        y_position = vertical_center
    elif motion_type == "pan_up":
        zoom = zoom_limit
        x_position = horizontal_center
        y_position = f"(ih-ih/zoom)*(1-{progress})"
    else:
        zoom = zoom_limit
        x_position = horizontal_center
        y_position = f"(ih-ih/zoom)*{progress}"

    return (
        f"zoompan=z='{zoom}':x='{x_position}':y='{y_position}':"
        f"d={frame_count}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    )


def _image_fade_filter(frame_count: int) -> str:
    duration = frame_count / FPS
    fade_duration = min(IMAGE_FADE_SECONDS, duration / 2)
    fade_out_start = max(0.0, duration - fade_duration)
    return (
        f"fade=t=in:st=0:d={fade_duration:.6f},"
        f"fade=t=out:st={fade_out_start:.6f}:d={fade_duration:.6f}"
    )


def _join_scenes(
    *,
    scene_paths: list[Path],
    scene_frames: list[int],
    transition_frames: list[int],
    output_path: Path,
    work_dir: Path,
) -> None:
    if len(scene_paths) > 1 and all(transition_frames):
        command = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
        for scene_path in scene_paths:
            command.extend(["-i", str(scene_path)])

        filters = [
            f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS[v{index}]"
            for index in range(len(scene_paths))
        ]
        current_label = "[v0]"
        elapsed_frames = 0
        for index in range(1, len(scene_paths)):
            elapsed_frames += scene_frames[index - 1]
            output_label = f"[crossfade{index}]"
            filters.append(
                f"{current_label}[v{index}]xfade=transition=fade:"
                f"duration={transition_frames[index - 1] / FPS:.6f}:"
                f"offset={elapsed_frames / FPS:.6f}{output_label}"
            )
            current_label = output_label

        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                current_label,
                "-an",
                "-r",
                str(FPS),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )
        run_ffmpeg(command)
        return

    concat_file = work_dir / "scenes.txt"
    concat_file.write_text(
        "".join(f"file '{path.name}'\n" for path in scene_paths),
        encoding="utf-8",
    )
    run_ffmpeg(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_path),
        ]
    )


def _export_video(
    *,
    joined_video: Path,
    audio_path: Path,
    subtitle_path: Path,
    output_path: Path,
    duration: float,
    logo_path: Path | None,
    background_music_path: Path | None,
    burn_subtitles: bool,
    resolution: VideoResolution,
) -> None:
    output_width, output_height = OUTPUT_DIMENSIONS[resolution]
    command = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(joined_video),
        "-i",
        str(audio_path),
    ]
    background_index: int | None = None
    logo_index: int | None = None
    next_input_index = 2

    if background_music_path:
        command.extend(["-stream_loop", "-1", "-i", str(background_music_path)])
        background_index = next_input_index
        next_input_index += 1
    if logo_path:
        command.extend(["-loop", "1", "-i", str(logo_path)])
        logo_index = next_input_index

    filters = [
        f"[0:v]scale={output_width}:{output_height}:flags=lanczos[scaled]"
    ]
    video_source = "[scaled]"
    video_map = "[scaled]"
    if burn_subtitles:
        filters.append(
            f"{video_source}subtitles=filename='{escape_filter_path(subtitle_path)}':"
            "force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,Outline=2,Shadow=0,Alignment=2,MarginV=48'"
            "[subtitled]"
        )
        video_source = "[subtitled]"
        video_map = "[subtitled]"
    if logo_index is not None:
        logo_width = round(output_width * 0.125)
        logo_margin = round(output_width * 0.025)
        filters.extend(
            [
                f"[{logo_index}:v]scale={logo_width}:-1[logo]",
                f"{video_source}[logo]overlay=W-w-{logo_margin}:"
                f"{logo_margin}:format=auto[videoout]",
            ]
        )
        video_map = "[videoout]"

    if background_index is not None:
        filters.extend(
            [
                "[1:a]aresample=48000,volume=1.0[narration]",
                f"[{background_index}:a]aresample=48000,volume=0.12[music]",
                "[narration][music]amix=inputs=2:duration=first:"
                "dropout_transition=2[audioout]",
            ]
        )
        audio_map = "[audioout]"
    else:
        audio_map = "1:a:0"

    if filters:
        command.extend(["-filter_complex", ";".join(filters)])
    command.extend(
        [
            "-map",
            video_map,
            "-map",
            audio_map,
            "-t",
            f"{duration:.6f}",
            "-r",
            str(FPS),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    run_ffmpeg(command)
