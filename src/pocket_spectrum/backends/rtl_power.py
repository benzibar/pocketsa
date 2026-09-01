from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path

from pocket_spectrum.models import SpectrumBin


class RtlPowerError(RuntimeError):
    pass


class RtlPowerBackend:
    """Receive-only RTL-SDR spectrum capture using rtl_power."""

    def __init__(
        self,
        device_index: int = 0,
        gain: str = "auto",
    ) -> None:
        self.device_index = device_index
        self.gain = gain

    def set_gain(self, gain: str) -> None:
        self.gain = gain

    @staticmethod
    def available() -> bool:
        return shutil.which("rtl_power") is not None

    @staticmethod
    def rtl_test_available() -> bool:
        return shutil.which("rtl_test") is not None

    def device_summary(self) -> str:
        if not self.rtl_test_available():
            return "rtl_test not installed"

        result = subprocess.run(
            ["rtl_test", "-t", "-d", str(self.device_index)],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )

        output = (result.stderr or result.stdout).strip()

        for line in output.splitlines():
            if "Using device" in line:
                return line.strip()

        if result.returncode == 0:
            return "RTL-SDR detected"

        return "RTL-SDR unavailable"

    def scan(
        self,
        start_hz: int,
        stop_hz: int,
        bin_hz: int,
        integration_seconds: int = 2,
    ) -> list[SpectrumBin]:
        if not self.available():
            raise RtlPowerError(
                "rtl_power is not installed. Install the rtl-sdr package."
            )

        if start_hz >= stop_hz:
            raise RtlPowerError("Start frequency must be below stop frequency.")

        if bin_hz <= 0:
            raise RtlPowerError("Bin width must be greater than zero.")

        with tempfile.TemporaryDirectory(prefix="pocket-spectrum-") as temp_dir:
            output_path = Path(temp_dir) / "scan.csv"

            command = [
                "rtl_power",
                "-d",
                str(self.device_index),
                "-f",
                f"{start_hz}:{stop_hz}:{bin_hz}",
                "-i",
                "1",
                "-e",
                f"{max(1, integration_seconds)}s",
            ]

            if self.gain != "auto":
                command += ["-g", self.gain]

            command.append(str(output_path))

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                message = (result.stderr or result.stdout).strip()
                raise RtlPowerError(message or "rtl_power scan failed.")

            if not output_path.exists():
                raise RtlPowerError("rtl_power did not produce scan output.")

            return self._parse_csv(output_path)

    @staticmethod
    def _parse_csv(path: Path) -> list[SpectrumBin]:
        bins: list[SpectrumBin] = []

        with path.open("r", encoding="utf-8", errors="replace") as handle:
            reader = csv.reader(handle)

            for row in reader:
                if len(row) < 7:
                    continue

                try:
                    start_hz = float(row[2])
                    step_hz = float(row[4])
                except ValueError:
                    continue

                powers = row[6:]

                for index, value in enumerate(powers):
                    try:
                        power_db = float(value)
                    except ValueError:
                        continue

                    bins.append(
                        SpectrumBin(
                            frequency_hz=start_hz + (index * step_hz),
                            power_db=power_db,
                        )
                    )

        return bins
