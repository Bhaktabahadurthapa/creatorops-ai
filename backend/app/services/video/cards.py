from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1920
HEIGHT = 1080
ACCENTS = (
    (34, 211, 238),
    (167, 139, 250),
    (251, 191, 36),
    (52, 211, 153),
)


def generate_text_card(
    *,
    scene_number: int,
    visual_description: str,
    subtitle: str,
    output_path: Path,
) -> Path:
    accent = ACCENTS[(scene_number - 1) % len(ACCENTS)]
    image = Image.new("RGB", (WIDTH, HEIGHT), (5, 10, 28))
    draw = ImageDraw.Draw(image)

    for y_position in range(HEIGHT):
        progress = y_position / max(1, HEIGHT - 1)
        color = (
            round(5 + progress * 8),
            round(10 + progress * 10),
            round(28 + progress * 20),
        )
        draw.line((0, y_position, WIDTH, y_position), fill=color)

    draw.ellipse((1350, -260, 2130, 520), fill=tuple(channel // 5 for channel in accent))
    draw.rectangle((120, 146, 138, 934), fill=accent)
    draw.rectangle((138, 146, 510, 154), fill=accent)
    draw.rectangle((138, 926, 760, 934), fill=accent)

    label_font = _load_font(32, bold=True)
    title_font = _load_font(84, bold=True)
    number_font = _load_font(180, bold=True)

    draw.text((184, 166), f"SCENE {scene_number:02d}", font=label_font, fill=accent)
    draw.text(
        (1510, 765),
        f"{scene_number:02d}",
        font=number_font,
        fill=tuple(min(255, channel + 45) for channel in accent),
    )

    headline = _clean_text(subtitle) or "CreatorOps AI"
    headline_lines = _wrap_text(draw, headline, title_font, 1180, max_lines=3)
    headline_y = 290
    for line in headline_lines:
        draw.text((184, headline_y), line, font=title_font, fill=(245, 247, 255))
        headline_y += 104

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return output_path


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"),
        ("Arial Bold.ttf", "Arial.ttf"),
    )
    for bold_name, regular_name in candidates:
        try:
            return ImageFont.truetype(bold_name if bold else regular_name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    *,
    max_lines: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)

    consumed = " ".join(lines)
    if len(consumed) < len(text) and lines:
        last_line = lines[-1]
        while last_line and draw.textbbox(
            (0, 0), f"{last_line}…", font=font
        )[2] > max_width:
            last_line = last_line.rsplit(" ", 1)[0]
        lines[-1] = f"{last_line}…"
    return lines


def _clean_text(value: str) -> str:
    return " ".join(value.split())
