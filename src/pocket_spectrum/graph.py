from __future__ import annotations

from pocket_spectrum.models import SpectrumBin


def spectrum_columns(
    bins: list[SpectrumBin],
    width: int = 58,
) -> list[SpectrumBin]:
    """Reduce raw bins to one representative bin per display column."""
    if not bins or width <= 0:
        return []

    ordered = sorted(
        bins,
        key=lambda item: item.frequency_hz,
    )

    if len(ordered) <= width:
        return ordered

    sampled: list[SpectrumBin] = []

    for x in range(width):
        start = int(
            x * len(ordered) / width
        )
        stop = int(
            (x + 1) * len(ordered) / width
        )

        chunk = ordered[
            start:max(start + 1, stop)
        ]

        # Keep the strongest bin in each display column so narrow peaks
        # remain visible rather than being averaged away.
        sampled.append(
            max(
                chunk,
                key=lambda item: item.power_db,
            )
        )

    return sampled


def render_spectrum(
    bins: list[SpectrumBin],
    width: int = 58,
    height: int = 8,
    cursor_column: int | None = None,
) -> str:
    columns = spectrum_columns(
        bins,
        width=width,
    )

    if not columns or height <= 0:
        return "(no spectrum data)"

    powers = [
        item.power_db
        for item in columns
    ]

    low = min(powers)
    high = max(powers)
    span = max(
        1.0,
        high - low,
    )

    levels = [
        int(
            round(
                (power - low)
                / span
                * height
            )
        )
        for power in powers
    ]

    rows: list[str] = []

    for row in range(
        height,
        0,
        -1,
    ):
        chars = [
            "█" if level >= row else " "
            for level in levels
        ]

        if (
            cursor_column is not None
            and 0 <= cursor_column < len(chars)
        ):
            chars[cursor_column] = "│"

        rows.append(
            "".join(chars)
        )

    if (
        cursor_column is not None
        and 0 <= cursor_column < len(columns)
    ):
        marker = [
            " "
            for _ in columns
        ]
        marker[cursor_column] = "▲"
        rows.append(
            "".join(marker)
        )

    return "\n".join(rows)
