def format_frequency(frequency_hz: float) -> str:
    if frequency_hz >= 1_000_000_000:
        return f"{frequency_hz / 1_000_000_000:.6f} GHz"

    return f"{frequency_hz / 1_000_000:.4f} MHz"


def format_frequency_compact(frequency_hz: float) -> str:
    return f"{frequency_hz / 1_000_000:.4f}"
