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

    candidates = [
        item
        for item in bins
        if item.power_db >= noise_floor + threshold_db
    ]

    candidates.sort(
        key=lambda item: item.power_db,
        reverse=True,
    )

    accepted: list[SignalHit] = []

    for candidate in candidates:
        if any(
            abs(candidate.frequency_hz - existing.frequency_hz)
            < min_spacing_hz
            for existing in accepted
        ):
            continue

        accepted.append(
            SignalHit(
                frequency_hz=candidate.frequency_hz,
                power_db=candidate.power_db,
                noise_floor_db=noise_floor,
            )
        )

    accepted.sort(key=lambda item: item.frequency_hz)
    return noise_floor, accepted
