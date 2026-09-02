"""Pocket Receiver handoff contract."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_RECEIVER = (
    Path.home()
    / "pocketterm"
    / "apps"
    / "pocket-receiver"
    / ".venv"
    / "bin"
    / "pocket-receiver"
)


@dataclass(frozen=True)
class ReceiverTuning:
    frequency_mhz: float
    mode: str
    bandwidth_khz: float


def tuning_for_frequency(frequency_hz: float) -> ReceiverTuning:
    """Choose a conservative listening default that can be edited in Receiver."""
    frequency_mhz = frequency_hz / 1_000_000.0
    if 87.5 <= frequency_mhz <= 108.0:
        return ReceiverTuning(frequency_mhz, "WFM", 200.0)
    if 108.0 < frequency_mhz <= 136.9917:
        return ReceiverTuning(frequency_mhz, "AM", 12.0)
    return ReceiverTuning(frequency_mhz, "NFM", 12.5)


def receiver_command(
    frequency_hz: float,
    executable: str | None = None,
) -> list[str]:
    tuning = tuning_for_frequency(frequency_hz)
    program = executable or os.environ.get(
        "POCKET_RECEIVER_COMMAND",
        str(DEFAULT_RECEIVER),
    )
    return [
        program,
        "--frequency",
        f"{tuning.frequency_mhz:.6f}",
        "--mode",
        tuning.mode,
        "--bandwidth",
        f"{tuning.bandwidth_khz:g}",
        "--play",
    ]

