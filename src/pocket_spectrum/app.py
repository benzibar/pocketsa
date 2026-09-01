from __future__ import annotations

from concurrent.futures import Future
from typing import Any

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, ListItem, ListView, Static

from pocket_spectrum.backends.rtl_power import RtlPowerBackend, RtlPowerError
from pocket_spectrum.formatting import (
    format_frequency,
    format_frequency_compact,
)
from pocket_spectrum.models import ScanPreset, SignalHit
from pocket_spectrum.presets import PRESETS
from pocket_spectrum.scanner import detect_signals


def field_text(rows: list[tuple[str, str]]) -> Text:
    text = Text()

    for index, (label, value) in enumerate(rows):
        text.append(f"{label:<10}", style="bright_green bold")
        text.append(value)

        if index != len(rows) - 1:
            text.append("\n")

    return text


class SignalDetailScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
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
        with Vertical(id="detail"):
            yield Static(
                "SIGNAL DETAIL",
                id="detail-title",
            )
            yield Static(
                field_text(
                    [
                        ("Frequency", format_frequency(self.hit.frequency_hz)),
                        ("Power", f"{self.hit.power_db:.1f} dB"),
                        ("Noise", f"{self.hit.noise_floor_db:.1f} dB"),
                        ("Above NF", f"{self.hit.snr_db:.1f} dB"),
                    ]
                )
            )
            yield Static(
                "\nThis is a detected RF energy peak. "
                "Modulation/decoder identification will be added later.\n\n"
                "Q Back"
            )


class ScanResultsScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
        ("enter", "details", "Details"),
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
    ) -> None:
        super().__init__()
        self.preset = preset
        self.hits = hits

    def compose(self) -> ComposeResult:
        with Vertical(id="results-root"):
            yield Static(
                f"SCAN: {self.preset.name.upper()}",
                id="results-title",
            )
            yield Static(
                f"{format_frequency(self.preset.start_hz)} - "
                f"{format_frequency(self.preset.stop_hz)}\n"
                f"{len(self.hits)} signal(s) detected",
                id="results-summary",
            )

            table = DataTable(
                id="results-table",
                cursor_type="row",
            )
            table.add_columns(
                "FREQ MHz",
                "POWER",
                "+NF",
            )
            yield table

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)

        for index, hit in enumerate(self.hits):
            table.add_row(
                format_frequency_compact(hit.frequency_hz),
                f"{hit.power_db:.1f}",
                f"{hit.snr_db:.1f}",
                key=str(index),
            )

    def action_details(self) -> None:
        table = self.query_one("#results-table", DataTable)

        if table.cursor_row < 0 or table.cursor_row >= len(self.hits):
            return

        self.app.push_screen(
            SignalDetailScreen(
                self.hits[table.cursor_row]
            )
        )

    def on_data_table_row_selected(
        self,
        event: DataTable.RowSelected,
    ) -> None:
        try:
            index = int(str(event.row_key.value))
        except (TypeError, ValueError):
            return

        if 0 <= index < len(self.hits):
            self.app.push_screen(
                SignalDetailScreen(
                    self.hits[index]
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
    ]

    def __init__(self) -> None:
        super().__init__()
        self.backend = RtlPowerBackend()
        self.scanning = False

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
                "Enter Scan   R Device   Q Quit",
                id="scan-status",
            )

        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh_device()

    def action_refresh_device(self) -> None:
        if not self.backend.available():
            summary = "rtl_power not installed"
        else:
            try:
                summary = self.backend.device_summary()
            except Exception:
                summary = "Unable to query RTL-SDR"

        self.query_one(
            "#device-status",
            Static,
        ).update(
            field_text(
                [
                    ("Backend", "RTL-SDR / rtl_power"),
                    ("Device", summary),
                ]
            )
        )

    def on_list_view_selected(
        self,
        event: ListView.Selected,
    ) -> None:
        if self.scanning:
            return

        index = event.list_view.index

        if index is None or not (0 <= index < len(PRESETS)):
            return

        self.start_scan(PRESETS[index])

    @work(thread=True)
    def start_scan(self, preset: ScanPreset) -> None:
        self.scanning = True

        self.call_from_thread(
            self.query_one("#scan-status", Static).update,
            f"Scanning {preset.name}...",
        )

        try:
            bins = self.backend.scan(
                start_hz=preset.start_hz,
                stop_hz=preset.stop_hz,
                bin_hz=preset.step_hz,
                integration_seconds=2,
            )

            noise_floor, hits = detect_signals(
                bins,
                threshold_db=8.0,
                min_spacing_hz=max(preset.step_hz, 25_000),
            )

        except RtlPowerError as exc:
            self.call_from_thread(
                self.query_one("#scan-status", Static).update,
                f"Scan failed: {exc}",
            )
            self.scanning = False
            return

        except Exception as exc:
            self.call_from_thread(
                self.query_one("#scan-status", Static).update,
                f"Error: {exc}",
            )
            self.scanning = False
            return

        self.scanning = False

        self.call_from_thread(
            self.query_one("#scan-status", Static).update,
            f"{len(hits)} signal(s) found",
        )

        self.call_from_thread(
            self.push_screen,
            ScanResultsScreen(
                preset=preset,
                hits=hits,
                noise_floor=noise_floor,
            ),
        )


def main() -> None:
    PocketSpectrum().run()


if __name__ == "__main__":
    main()
