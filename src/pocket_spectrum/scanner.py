from __future__ import annotations

from statistics import median

from pocket_spectrum.models import SignalHit, SpectrumBin


def detect_signals(
    bins: list[SpectrumBin],
    threshold_db: float = 8.0,
    min_spacing_hz: float = 25_000.0,
) -> tuple[float, list[SignalHit]]:
    if not bins:
        return -120.0, []

    powers = [item.power_db for item in bins]
    noise_floor = float(median(powers))
    cutoff = noise_floor + threshold_db

    hot = [
        item
        for item in sorted(bins, key=lambda item: item.frequency_hz)
        if item.power_db >= cutoff
    ]

    if not hot:
        return noise_floor, []

    groups: list[list[SpectrumBin]] = []
    current: list[SpectrumBin] = [hot[0]]

    for item in hot[1:]:
        if item.frequency_hz - current[-1].frequency_hz <= min_spacing_hz:
            current.append(item)
        else:
            groups.append(current)
            current = [item]

    groups.append(current)

    hits: list[SignalHit] = []

    for group in groups:
        peak = max(group, key=lambda item: item.power_db)
        start = group[0].frequency_hz
        stop = group[-1].frequency_hz
        bandwidth = max(0.0, stop - start + min_spacing_hz)

        hits.append(
            SignalHit(
                frequency_hz=peak.frequency_hz,
                power_db=peak.power_db,
                noise_floor_db=noise_floor,
                bandwidth_hz=bandwidth,
            )
        )

    return noise_floor, hits
