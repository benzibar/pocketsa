from __future__ import annotations

from pocket_spectrum.models import SpectrumBin


BLOCKS = " ▁▂▃▄▅▆▇█"


def render_spectrum(
    bins: list[SpectrumBin],
    width: int = 58,
    height: int = 8,
) -> str:
    if not bins or width <= 0 or height <= 0:
        return "(no spectrum data)"

    bins = sorted(bins, key=lambda item: item.frequency_hz)

    if len(bins) <= width:
        sampled = bins
    else:
        sampled = []
        for x in range(width):
            start = int(x * len(bins) / width)
            stop = int((x + 1) * len(bins) / width)
            chunk = bins[start:max(start + 1, stop)]
            sampled.append(max(chunk, key=lambda item: item.power_db))

    powers = [item.power_db for item in sampled]
    low = min(powers)
    high = max(powers)
    span = max(1.0, high - low)

    levels = [
        int(round((power - low) / span * height))
        for power in powers
    ]

    rows: list[str] = []
    for row in range(height, 0, -1):
        rows.append(
            "".join(
                "█" if level >= row else " "
                for level in levels
            )
        )

    return "\n".join(rows)
