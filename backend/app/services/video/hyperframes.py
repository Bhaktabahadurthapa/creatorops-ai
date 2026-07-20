import html
import logging
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)

WIDTH = 1920
HEIGHT = 1080
FPS = 30
REPOSITORY_DIR = Path(__file__).resolve().parents[4]
HYPERFRAMES_CLI = REPOSITORY_DIR / "node_modules" / ".bin" / "hyperframes"
HYPERFRAMES_TIMEOUT_SECONDS = 15 * 60
PALETTES = (
    ("#22d3ee", "#8b5cf6", "#07111f"),
    ("#a78bfa", "#f59e0b", "#100b21"),
    ("#34d399", "#22d3ee", "#061b1b"),
    ("#fb7185", "#a78bfa", "#190b19"),
)


def render_hyperframes_text_scene(
    *,
    scene_number: int,
    visual_description: str,
    subtitle: str,
    duration_seconds: float,
    project_dir: Path,
    output_path: Path,
) -> bool:
    """Render a motion-designed text scene, returning False for safe fallback."""
    if duration_seconds <= 0:
        raise ValueError("A HyperFrames scene must have a positive duration.")
    if not HYPERFRAMES_CLI.is_file():
        return False

    project_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    (project_dir / "index.html").write_text(
        build_hyperframes_composition(
            scene_number=scene_number,
            visual_description=visual_description,
            subtitle=subtitle,
            duration_seconds=duration_seconds,
        ),
        encoding="utf-8",
    )

    try:
        subprocess.run(
            [
                str(HYPERFRAMES_CLI),
                "render",
                str(project_dir),
                "--output",
                str(output_path),
                "--fps",
                str(FPS),
                "--quality",
                "standard",
                "--workers",
                "2",
                "--no-browser-gpu",
                "--quiet",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=HYPERFRAMES_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        output_path.unlink(missing_ok=True)
        detail = getattr(exc, "stderr", "") or str(exc)
        logger.warning(
            "HyperFrames scene %s failed; using the FFmpeg fallback: %s",
            scene_number,
            str(detail).strip()[-500:],
        )
        return False

    if not output_path.is_file() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        logger.warning(
            "HyperFrames scene %s produced no MP4; using the FFmpeg fallback.",
            scene_number,
        )
        return False
    return True


def build_hyperframes_composition(
    *,
    scene_number: int,
    visual_description: str,
    subtitle: str,
    duration_seconds: float,
) -> str:
    """Create a deterministic, network-free HyperFrames HTML composition."""
    accent, secondary, background = PALETTES[(scene_number - 1) % len(PALETTES)]
    duration = f"{duration_seconds:.6f}"
    headline = html.escape(" ".join(subtitle.split()) or "CreatorOps AI")
    direction = html.escape(
        " ".join(visual_description.split()) or "A polished creator workflow in motion"
    )
    words = "".join(
        f'<span class="word" style="--word-index:{index}">{word}</span>'
        for index, word in enumerate(headline.split())
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={WIDTH}, height={HEIGHT}" />
    <title>CreatorOps AI scene {scene_number:02d}</title>
    <style>
      * {{ box-sizing: border-box; }}
      html, body {{ margin: 0; width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden; }}
      body {{ background: #020617; color: #f8fafc; font-family: sans-serif; }}
      #root {{ position: relative; width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden; }}
      .clip {{ position: absolute; inset: 0; overflow: hidden; }}
      .stage {{ position: absolute; inset: 0; background: {background}; }}
      .wash {{
        position: absolute; inset: -160px;
        background:
          radial-gradient(circle at 78% 18%, {secondary}55 0, transparent 34%),
          radial-gradient(circle at 10% 88%, {accent}44 0, transparent 38%),
          linear-gradient(135deg, {background} 0%, #050b1d 55%, #020617 100%);
        animation: wash-shift {duration}s ease-in-out both;
      }}
      .grid {{
        position: absolute; inset: 0; opacity: .15;
        background-image: linear-gradient({accent}35 1px, transparent 1px), linear-gradient(90deg, {accent}35 1px, transparent 1px);
        background-size: 80px 80px;
        mask-image: linear-gradient(to bottom, transparent, black 24%, black 78%, transparent);
        animation: grid-drift {duration}s linear both;
      }}
      .orb {{ position: absolute; border-radius: 999px; filter: blur(2px); opacity: .65; }}
      .orb-a {{ width: 360px; height: 360px; right: 120px; top: 80px; background: {secondary}55; animation: orb-a {duration}s ease-in-out both; }}
      .orb-b {{ width: 220px; height: 220px; left: 80px; bottom: 40px; background: {accent}44; animation: orb-b {duration}s ease-in-out both; }}
      .rail {{ position: absolute; left: 126px; top: 130px; bottom: 130px; width: 8px; border-radius: 8px; background: linear-gradient({accent}, {secondary}); transform-origin: top; animation: rail-in .7s cubic-bezier(.2,.8,.2,1) both; }}
      .content {{ position: absolute; left: 184px; top: 154px; width: 1300px; }}
      .eyebrow {{ color: {accent}; font-size: 28px; font-weight: 800; letter-spacing: .24em; text-transform: uppercase; animation: rise .65s .08s cubic-bezier(.2,.8,.2,1) both; }}
      h1 {{ margin: 44px 0 0; max-width: 1320px; font-size: 94px; line-height: 1.02; letter-spacing: -.045em; }}
      .word {{ display: inline-block; margin-right: .24em; animation: word-in .72s cubic-bezier(.16,1,.3,1) both; animation-delay: calc(.20s + var(--word-index) * .075s); }}
      .direction {{ margin: 50px 0 0; max-width: 1100px; color: #b7c3de; font-size: 38px; line-height: 1.42; animation: rise .8s .72s cubic-bezier(.2,.8,.2,1) both; }}
      .meter {{ position: absolute; left: 184px; right: 184px; bottom: 112px; height: 3px; overflow: hidden; background: #ffffff1f; }}
      .meter::after {{ content: ""; display: block; width: 100%; height: 100%; background: linear-gradient(90deg, {accent}, {secondary}); transform-origin: left; animation: progress {duration}s linear both; }}
      .number {{ position: absolute; right: 130px; bottom: 92px; color: #62677a; font-size: 240px; line-height: 1; font-weight: 900; letter-spacing: -.08em; animation: number-in 1s .2s cubic-bezier(.2,.8,.2,1) both; }}
      @keyframes wash-shift {{ from {{ transform: scale(1.02) translate3d(-18px, 12px, 0); }} to {{ transform: scale(1.12) translate3d(28px, -18px, 0); }} }}
      @keyframes grid-drift {{ from {{ transform: translate3d(0, 0, 0); }} to {{ transform: translate3d(80px, 40px, 0); }} }}
      @keyframes orb-a {{ from {{ transform: translate3d(40px, -30px, 0) scale(.85); }} to {{ transform: translate3d(-140px, 80px, 0) scale(1.18); }} }}
      @keyframes orb-b {{ from {{ transform: translate3d(-50px, 50px, 0) scale(.8); }} to {{ transform: translate3d(160px, -90px, 0) scale(1.12); }} }}
      @keyframes rail-in {{ from {{ opacity: 0; transform: scaleY(0); }} to {{ opacity: 1; transform: scaleY(1); }} }}
      @keyframes rise {{ from {{ opacity: 0; transform: translate3d(0, 42px, 0); }} to {{ opacity: 1; transform: translate3d(0, 0, 0); }} }}
      @keyframes word-in {{ from {{ opacity: 0; transform: translate3d(0, 70px, 0) rotate(2deg); }} to {{ opacity: 1; transform: translate3d(0, 0, 0) rotate(0); }} }}
      @keyframes number-in {{ from {{ opacity: 0; transform: translate3d(80px, 30px, 0) scale(.9); }} to {{ opacity: 1; transform: translate3d(0, 0, 0) scale(1); }} }}
      @keyframes progress {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-no-timeline data-start="0" data-width="{WIDTH}" data-height="{HEIGHT}" data-duration="{duration}" data-fps="{FPS}">
      <section id="scene-{scene_number:02d}" class="clip" data-start="0" data-duration="{duration}" data-track-index="1">
        <div class="stage">
          <div class="wash"></div><div class="grid"></div>
          <div class="orb orb-a" data-layout-allow-overflow></div><div class="orb orb-b" data-layout-allow-overflow></div>
          <div class="rail"></div>
          <div class="content"><div class="eyebrow">CreatorOps AI · Scene {scene_number:02d}</div><h1>{words}</h1><p class="direction">{direction}</p></div>
          <div class="number">{scene_number:02d}</div><div class="meter"></div>
        </div>
      </section>
    </div>
  </body>
</html>
"""
