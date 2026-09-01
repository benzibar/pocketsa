from dataclasses import dataclass


@dataclass(frozen=True)
class ScanPreset:
    id: str
    name: str
    start_hz: int
    stop_hz: int
    step_hz: int
    description: str


@dataclass(frozen=True)
class SpectrumBin:
    frequency_hz: float
    power_db: float


@dataclass(frozen=True)
class SignalHit:
    frequency_hz: float
    power_db: float
    noise_floor_db: float

    @property
    def snr_db(self) -> float:
        return self.power_db - self.noise_floor_db
