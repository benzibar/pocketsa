from __future__ import annotations

import subprocess

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
)

from pocket_spectrum.backends.rtl_power import (
    RtlPowerBackend,
    RtlPowerError,
)
from pocket_spectrum.formatting import (
    format_frequency,
    format_frequency_compact,
)
from pocket_spectrum.graph import (
    render_spectrum,
    spectrum_columns,
)
from pocket_spectrum.models import (
    ScanPreset,
    SignalHit,
    SpectrumBin,
)
from pocket_spectrum.presets import PRESETS
from pocket_spectrum.receiver_integration import receiver_command
from pocket_spectrum.scanner import detect_signals
from pocket_spectrum.sdr_lease import ReadsbLease, SdrLeaseError


def field_text(rows: list[tuple[str, str]]) -> Text:
    text = Text()

    for index, (label, value) in enumerate(rows):
        text.append(
            f"{label:<10}",
            style="bright_green bold",
        )
        text.append(value)

        if index != len(rows) - 1:
            text.append("\n")

    return text


class CustomScanScreen(ModalScreen[ScanPreset | None]):
    CSS = """
    CustomScanScreen {
        align: center middle;
    }

    #custom-box {
        width: 92%;
        height: auto;
        border: round cyan;
        padding: 1 2;
    }

    #custom-title {
        color: cyan;
        text-style: bold;
        margin-bottom: 1;
    }

    #custom-buttons {
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("q", "cancel", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="custom-box"):
            yield Static(
                "CUSTOM SCAN (MHz)",
                id="custom-title",
            )
            yield Input(
                placeholder="Start MHz e.g. 118.0",
                id="start",
            )
            yield Input(
                placeholder="Stop MHz e.g. 137.0",
                id="stop",
            )
            yield Input(
                value="25",
                placeholder="Bin width kHz",
                id="step",
            )

            with Horizontal(id="custom-buttons"):
                yield Button(
                    "Scan",
                    id="scan",
                    variant="primary",
                )
                yield Button(
                    "Cancel",
                    id="cancel",
                )

    def on_mount(self) -> None:
        self.query_one("#start", Input).focus()

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return

        try:
            start_mhz = float(
                self.query_one("#start", Input).value
            )
            stop_mhz = float(
                self.query_one("#stop", Input).value
            )
            step_khz = float(
                self.query_one("#step", Input).value
            )
        except ValueError:
            return

        if (
            start_mhz <= 0
            or stop_mhz <= start_mhz
            or step_khz <= 0
        ):
            return

        self.dismiss(
            ScanPreset(
                id="custom",
                name="Custom",
                start_hz=int(start_mhz * 1_000_000),
                stop_hz=int(stop_mhz * 1_000_000),
                step_hz=int(step_khz * 1_000),
                description="User-defined frequency range",
            )
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


class SignalDetailScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
        ("l", "listen", "Listen"),
    ]

    CSS = """
    #detail {
        padding: 1 2;
    }

    #detail-title {
        color: cyan;
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, hit: SignalHit) -> None:
        super().__init__()
        self.hit = hit

    def compose(self) -> ComposeResult:
        bandwidth = (
            f"{self.hit.bandwidth_hz / 1000:.1f} kHz"
            if self.hit.bandwidth_hz > 0
            else "---"
        )

        with Vertical(id="detail"):
            yield Static(
                "SIGNAL DETAIL",
                id="detail-title",
            )
            yield Static(
                field_text(
                    [
                        (
                            "Frequency",
                            format_frequency(
                                self.hit.frequency_hz
                            ),
                        ),
                        (
                            "Power",
                            f"{self.hit.power_db:.1f} dB",
                        ),
                        (
                            "Noise",
                            f"{self.hit.noise_floor_db:.1f} dB",
                        ),
                        (
                            "Above NF",
                            f"{self.hit.snr_db:.1f} dB",
                        ),
                        (
                            "Bandwidth",
                            bandwidth,
                        ),
                    ]
                )
            )
            yield Static(
                "\nDetected RF energy peak. "
                "Signal identification/decoding will come later.\n\n"
                "L Listen   Q Back"
            )

    def action_listen(self) -> None:
        self.app.open_receiver(self.hit.frequency_hz)


class SpectrumScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
        ("left", "cursor_left", "Left"),
        ("right", "cursor_right", "Right"),
        ("p", "previous_peak", "Prev peak"),
        ("n", "next_peak", "Next peak"),
        ("l", "listen", "Listen"),
    ]

    GRAPH_WIDTH = 58
    GRAPH_HEIGHT = 8

    CSS = """
    #graph-root {
        padding: 0 1;
        height: 1fr;
    }

    #graph-title {
        color: cyan;
        text-style: bold;
        height: 1;
    }

    #graph-readout {
        height: 2;
        margin-top: 1;
    }

    #graph {
        height: auto;
    }

    #graph-help {
        height: 2;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        preset: ScanPreset,
        bins: list[SpectrumBin],
        hits: list[SignalHit],
    ) -> None:
        super().__init__()
        self.preset = preset
        self.bins = bins
        self.hits = hits

        self.columns = spectrum_columns(
            bins,
            width=self.GRAPH_WIDTH,
        )

        self.cursor_column = (
            self._initial_cursor_column()
        )

    def _initial_cursor_column(self) -> int:
        if not self.columns:
            return 0

        # Start on the strongest visible point.
        strongest = max(
            range(len(self.columns)),
            key=lambda index: (
                self.columns[index].power_db
            ),
        )
        return strongest

    def compose(self) -> ComposeResult:
        with Vertical(id="graph-root"):
            yield Static(
                f"SPECTRUM: "
                f"{self.preset.name.upper()}",
                id="graph-title",
            )

            yield Static(
                "",
                id="graph-readout",
            )

            yield Static(
                "",
                id="graph",
            )

            yield Static(
                "←/→ Scan  P/N Peaks  L Listen  Q Back",
                id="graph-help",
            )

    def on_mount(self) -> None:
        self._update_graph()

    def _selected_bin(
        self,
    ) -> SpectrumBin | None:
        if not self.columns:
            return None

        self.cursor_column = max(
            0,
            min(
                self.cursor_column,
                len(self.columns) - 1,
            ),
        )

        return self.columns[
            self.cursor_column
        ]

    def _update_graph(self) -> None:
        selected = self._selected_bin()

        self.query_one(
            "#graph",
            Static,
        ).update(
            render_spectrum(
                self.bins,
                width=self.GRAPH_WIDTH,
                height=self.GRAPH_HEIGHT,
                cursor_column=(
                    self.cursor_column
                    if self.columns
                    else None
                ),
            )
        )

        if selected is None:
            readout = "No spectrum data"
        else:
            readout = (
                f"{format_frequency(selected.frequency_hz)}  "
                f"{selected.power_db:.1f} dB\n"
                f"Column {self.cursor_column + 1}/"
                f"{len(self.columns)}"
            )

        self.query_one(
            "#graph-readout",
            Static,
        ).update(
            readout
        )

    def action_cursor_left(self) -> None:
        if not self.columns:
            return

        self.cursor_column = max(
            0,
            self.cursor_column - 1,
        )
        self._update_graph()

    def action_cursor_right(self) -> None:
        if not self.columns:
            return

        self.cursor_column = min(
            len(self.columns) - 1,
            self.cursor_column + 1,
        )
        self._update_graph()

    def _column_for_frequency(
        self,
        frequency_hz: float,
    ) -> int:
        if not self.columns:
            return 0

        return min(
            range(len(self.columns)),
            key=lambda index: abs(
                self.columns[index].frequency_hz
                - frequency_hz
            ),
        )

    def _peak_columns(self) -> list[int]:
        columns = sorted(
            {
                self._column_for_frequency(
                    hit.frequency_hz
                )
                for hit in self.hits
            }
        )

        return columns

    def action_next_peak(self) -> None:
        peak_columns = (
            self._peak_columns()
        )

        if not peak_columns:
            return

        for column in peak_columns:
            if column > self.cursor_column:
                self.cursor_column = column
                self._update_graph()
                return

        self.cursor_column = (
            peak_columns[0]
        )
        self._update_graph()

    def action_previous_peak(self) -> None:
        peak_columns = (
            self._peak_columns()
        )

        if not peak_columns:
            return

        for column in reversed(
            peak_columns
        ):
            if column < self.cursor_column:
                self.cursor_column = column
                self._update_graph()
                return

        self.cursor_column = (
            peak_columns[-1]
        )
        self._update_graph()

    def action_listen(self) -> None:
        selected = self._selected_bin()
        if selected is not None:
            self.app.open_receiver(selected.frequency_hz)

class ScanResultsScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
        ("enter", "details", "Details"),
        ("g", "graph", "Graph"),
        ("t", "cycle_threshold", "Thresh"),
        ("r", "refresh_scan", "Refresh"),
        ("l", "listen", "Listen"),
    ]

    CSS = """
    #results-root {
        padding: 0 1;
        height: 1fr;
    }

    #results-title {
        color: cyan;
        text-style: bold;
        height: 1;
    }

    #results-summary {
        height: 2;
    }

    #results-table {
        height: 1fr;
    }
    """

    def __init__(
        self,
        preset: ScanPreset,
        hits: list[SignalHit],
        noise_floor: float,
        bins: list[SpectrumBin],
        threshold_db: float,
        gain: str,
    ) -> None:
        super().__init__()
        self.preset = preset
        self.hits = hits
        self.noise_floor = noise_floor
        self.bins = bins
        self.threshold_db = threshold_db
        self.gain = gain
        self.refreshing = False

    def compose(self) -> ComposeResult:
        with Vertical(id="results-root"):
            yield Static(
                f"SCAN: {self.preset.name.upper()}",
                id="results-title",
            )

            yield Static(
                "",
                id="results-summary",
            )

            table = DataTable(
                id="results-table",
                cursor_type="row",
            )
            table.add_columns(
                "FREQ",
                "PWR",
                "+NF",
                "BW kHz",
            )
            yield table

        yield Footer()

    def on_mount(self) -> None:
        self._populate_table()

    def _update_summary(self, message: str | None = None) -> None:
        summary = self.query_one(
            "#results-summary",
            Static,
        )

        if message is not None:
            summary.update(message)
            return

        summary.update(
            f"NF {self.noise_floor:.1f} dB | "
            f"Thr +{self.threshold_db:.0f} | "
            f"{len(self.hits)} sig | "
            f"G Graph  L Listen  R Refresh"
        )

    def _populate_table(self) -> None:
        table = self.query_one(
            "#results-table",
            DataTable,
        )

        table.clear()

        for index, hit in enumerate(self.hits):
            table.add_row(
                format_frequency_compact(
                    hit.frequency_hz
                ),
                f"{hit.power_db:.1f}",
                f"{hit.snr_db:.1f}",
                f"{hit.bandwidth_hz / 1000:.1f}",
                key=str(index),
            )

        self._update_summary()

    def action_cycle_threshold(self) -> None:
        thresholds = getattr(
            self.app,
            "THRESHOLDS",
            [6.0, 8.0, 10.0, 12.0, 15.0],
        )

        try:
            current_index = thresholds.index(
                self.threshold_db
            )
        except ValueError:
            current_index = 0

        self.threshold_db = thresholds[
            (current_index + 1)
            % len(thresholds)
        ]

        self.noise_floor, self.hits = detect_signals(
            self.bins,
            threshold_db=self.threshold_db,
            min_spacing_hz=max(
                self.preset.step_hz,
                25_000,
            ),
        )

        if hasattr(
            self.app,
            "threshold_index",
        ):
            try:
                self.app.threshold_index = (
                    thresholds.index(
                        self.threshold_db
                    )
                )
            except ValueError:
                pass

        self._populate_table()

    @work(thread=True)
    def action_refresh_scan(self) -> None:
        if self.refreshing:
            return

        self.refreshing = True
        self.app.scanning = True

        self.app.call_from_thread(
            self._update_summary,
            f"Refreshing {self.preset.name}..."
        )

        backend = RtlPowerBackend(
            gain=self.gain,
        )

        try:
            bins = backend.scan(
                start_hz=self.preset.start_hz,
                stop_hz=self.preset.stop_hz,
                bin_hz=self.preset.step_hz,
                integration_seconds=2,
            )

            noise_floor, hits = detect_signals(
                bins,
                threshold_db=self.threshold_db,
                min_spacing_hz=max(
                    self.preset.step_hz,
                    25_000,
                ),
            )

        except Exception as exc:
            self.refreshing = False
            self.app.scanning = False
            self.app.call_from_thread(
                self._update_summary,
                f"Refresh failed: {exc}",
            )
            return

        self.bins = bins
        self.noise_floor = noise_floor
        self.hits = hits
        self.refreshing = False
        self.app.scanning = False

        self.app.call_from_thread(
            self._populate_table
        )

    def action_details(self) -> None:
        table = self.query_one(
            "#results-table",
            DataTable,
        )

        if (
            table.cursor_row < 0
            or table.cursor_row >= len(self.hits)
        ):
            return

        self.app.push_screen(
            SignalDetailScreen(
                self.hits[table.cursor_row]
            )
        )

    def action_listen(self) -> None:
        if self.refreshing:
            return

        table = self.query_one(
            "#results-table",
            DataTable,
        )
        if 0 <= table.cursor_row < len(self.hits):
            self.app.open_receiver(
                self.hits[table.cursor_row].frequency_hz
            )

    def action_graph(self) -> None:
        self.app.push_screen(
            SpectrumScreen(
                self.preset,
                self.bins,
                self.hits,
            )
        )

class PocketSpectrum(App):
    TITLE = "Pocket Spectrum"

    CSS = """
    Screen {
        layout: vertical;
    }

    #home-root {
        padding: 1 2;
        height: 1fr;
    }

    #title {
        color: cyan;
        text-style: bold;
        content-align: center middle;
        margin-bottom: 1;
    }

    #device-status {
        height: auto;
        margin-bottom: 1;
    }

    #preset-list {
        height: 1fr;
        border: round $surface;
    }

    #scan-status {
        height: 2;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_device", "Device"),
        ("c", "custom_scan", "Custom"),
        ("t", "cycle_threshold", "Thresh"),
        ("g", "cycle_gain", "Gain"),
    ]

    THRESHOLDS = [6.0, 8.0, 10.0, 12.0, 15.0]
    GAINS = ["auto", "10", "20", "30", "40"]

    def __init__(self) -> None:
        super().__init__()
        self.backend = RtlPowerBackend()
        self.scanning = False
        self.threshold_index = 1
        self.gain_index = 0
        self.lease = ReadsbLease()
        self.lease_acquired = False

    @property
    def threshold_db(self) -> float:
        return self.THRESHOLDS[
            self.threshold_index
        ]

    @property
    def gain(self) -> str:
        return self.GAINS[
            self.gain_index
        ]

    def compose(self) -> ComposeResult:
        with Vertical(id="home-root"):
            yield Static(
                "POCKET SPECTRUM",
                id="title",
            )

            yield Static(
                "",
                id="device-status",
            )

            yield ListView(
                *[
                    ListItem(
                        Label(
                            f"{preset.name:<18} "
                            f"{preset.start_hz / 1_000_000:.1f}-"
                            f"{preset.stop_hz / 1_000_000:.1f}"
                        )
                    )
                    for preset in PRESETS
                ],
                id="preset-list",
            )

            yield Static(
                "",
                id="scan-status",
            )

        yield Footer()

    def on_mount(self) -> None:
        try:
            self.lease.acquire()
            self.lease_acquired = True
        except SdrLeaseError as exc:
            self.lease_acquired = False
            self.query_one(
                "#scan-status",
                Static,
            ).update(
                f"SDR unavailable: {exc}"
            )

        self.action_refresh_device()

        if self.lease_acquired:
            self._update_controls()

    def on_unmount(self) -> None:
        if not self.lease_acquired:
            return

        try:
            self.lease.release()
        except SdrLeaseError:
            pass
        finally:
            self.lease_acquired = False

    def _update_controls(self) -> None:
        gain_text = (
            "AUTO"
            if self.gain == "auto"
            else f"{self.gain} dB"
        )

        self.query_one(
            "#scan-status",
            Static,
        ).update(
            f"Thr +{self.threshold_db:.0f}dB | "
            f"Gain {gain_text} | "
            "C Custom"
        )

    def action_refresh_device(self) -> None:
        if not self.backend.available():
            summary = "rtl_power not installed"
        else:
            try:
                summary = (
                    self.backend.device_summary()
                )
            except Exception:
                summary = "Unable to query RTL-SDR"

        self.query_one(
            "#device-status",
            Static,
        ).update(
            field_text(
                [
                    (
                        "Backend",
                        "RTL-SDR / rtl_power",
                    ),
                    (
                        "Device",
                        summary,
                    ),
                    (
                        "readsb",
                        "Paused" if self.lease_acquired else "Not leased",
                    ),
                ]
            )
        )

    def action_cycle_threshold(self) -> None:
        if self.scanning:
            return

        self.threshold_index = (
            self.threshold_index + 1
        ) % len(self.THRESHOLDS)
        self._update_controls()

    def action_cycle_gain(self) -> None:
        if self.scanning:
            return

        self.gain_index = (
            self.gain_index + 1
        ) % len(self.GAINS)

        self.backend.set_gain(
            self.gain
        )

        self._update_controls()

    def action_custom_scan(self) -> None:
        if self.scanning or not self.lease_acquired:
            return

        self.push_screen(
            CustomScanScreen(),
            self._custom_scan_ready,
        )

    def open_receiver(self, frequency_hz: float) -> None:
        """Give the terminal to Receiver while retaining the readsb lease."""
        if self.scanning or not self.lease_acquired:
            self.notify(
                "Receiver is unavailable while the SDR is busy.",
                severity="warning",
            )
            return

        command = receiver_command(frequency_hz)
        try:
            with self.suspend():
                result = subprocess.run(
                    command,
                    check=False,
                )
        except FileNotFoundError:
            self.notify(
                "Pocket Receiver is not installed at the expected path.",
                severity="error",
            )
            return
        except OSError as exc:
            self.notify(
                f"Could not open Pocket Receiver: {exc}",
                severity="error",
            )
            return

        if result.returncode != 0:
            self.notify(
                f"Pocket Receiver exited with status {result.returncode}.",
                severity="error",
            )

    def _custom_scan_ready(
        self,
        preset: ScanPreset | None,
    ) -> None:
        if preset is not None:
            self.start_scan(preset)

    def on_list_view_selected(
        self,
        event: ListView.Selected,
    ) -> None:
        if self.scanning or not self.lease_acquired:
            return

        index = event.list_view.index

        if (
            index is None
            or not (
                0 <= index < len(PRESETS)
            )
        ):
            return

        self.start_scan(
            PRESETS[index]
        )

    @work(thread=True)
    def start_scan(
        self,
        preset: ScanPreset,
    ) -> None:
        self.scanning = True

        self.app.call_from_thread(
            self.query_one(
                "#scan-status",
                Static,
            ).update,
            f"Scanning {preset.name}...",
        )

        try:
            bins = self.backend.scan(
                start_hz=preset.start_hz,
                stop_hz=preset.stop_hz,
                bin_hz=preset.step_hz,
                integration_seconds=2,
            )

            noise_floor, hits = (
                detect_signals(
                    bins,
                    threshold_db=self.threshold_db,
                    min_spacing_hz=max(
                        preset.step_hz,
                        25_000,
                    ),
                )
            )

        except RtlPowerError as exc:
            self.app.call_from_thread(
                self.query_one(
                    "#scan-status",
                    Static,
                ).update,
                f"Scan failed: {exc}",
            )
            self.scanning = False
            return

        except Exception as exc:
            self.app.call_from_thread(
                self.query_one(
                    "#scan-status",
                    Static,
                ).update,
                f"Error: {exc}",
            )
            self.scanning = False
            return

        self.scanning = False

        self.app.call_from_thread(
            self.push_screen,
            ScanResultsScreen(
                preset=preset,
                hits=hits,
                noise_floor=noise_floor,
                bins=bins,
                threshold_db=self.threshold_db,
                gain=self.gain,
            ),
        )

        self.app.call_from_thread(
            self._update_controls
        )


def main() -> None:
    PocketSpectrum().run()


if __name__ == "__main__":
    main()
