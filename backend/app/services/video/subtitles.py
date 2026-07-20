from collections.abc import Sequence
from pathlib import Path


def format_srt_timestamp(seconds: float) -> str:
    total_milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def write_srt(
    entries: Sequence[tuple[float, float, str]],
    output_path: Path,
) -> Path:
    blocks: list[str] = []
    for index, (start, end, subtitle) in enumerate(entries, start=1):
        clean_subtitle = " ".join(subtitle.split())
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}",
                    clean_subtitle,
                ]
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output_path
