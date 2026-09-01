# Pocket Spectrum

Receive-only spectrum scanner for PocketTerm.

## v0.2

Pocket Spectrum uses `rtl_power` as its first SDR backend and keeps the UI
separate from the radio backend so HackRF support can be added later.

### Current features

- RTL-SDR device detection.
- Preset band scans.
- Custom start/stop frequency and bin width.
- Adjustable detection threshold.
- Adjustable RTL gain.
- Median-based noise-floor estimation.
- Groups adjacent hot bins into a single detected signal.
- Shows frequency, power, level above noise floor and estimated bandwidth.
- Compact spectrum graph for the scanned range.
- Signal detail screen.
- `Q` as Back/Exit.

### Controls

Home:
- Enter: scan selected preset
- C: custom scan
- T: cycle detection threshold
- G: cycle RTL gain
- R: refresh device
- Q: quit

Results:
- Enter: signal detail
- G: spectrum graph
- Q: back

### Included presets

- Civil Airband
- UK 2 metre amateur
- Marine VHF
- UK 70 centimetre amateur
- PMR446
- 1090 MHz ADS-B neighbourhood

This application is receive-only.

## PocketTerm prerequisites

```bash
which rtl_power
which rtl_test
```

If missing:

```bash
sudo apt update
sudo apt install rtl-sdr
```

If `readsb` is using the RTL-SDR:

```bash
sudo systemctl stop readsb
```

Restart it afterwards:

```bash
sudo systemctl start readsb
```

## Install / update

```bash
cd ~/pocketterm/apps/pocketsa
git pull
source .venv/bin/activate
python -m pip install -e .
pocket-spectrum
```

## Launcher entry

```toml
[[apps]]
id = "spectrum"
name = "Spectrum Scanner"
description = "Find and inspect interesting RF activity"
status = "READY"
command = "/home/bdm198/pocketterm/apps/pocketsa/.venv/bin/pocket-spectrum"
args = []
cwd = "/home/bdm198/pocketterm/apps/pocketsa"
```

## Roadmap

- Better spectrum scaling and frequency markers.
- Live/tune inspect mode.
- Saved findings and frequency notes.
- Waterfall/history view.
- HackRF backend.


## v0.3

Interactive spectrum inspection:

- The spectrum graph now has a movable cursor.
- Left/Right scans across the displayed spectrum.
- The exact representative frequency and power for the selected graph column
  are shown above the graph.
- P/N jumps directly between detected peaks.
- The graph opens initially on the strongest visible point.
- A vertical cursor line and marker show exactly which part of the graph is
  being inspected.

The graph keeps the strongest raw FFT bin represented by each screen column,
so narrow peaks remain visible on the PocketTerm display.


## v0.3.1

- Threshold control now works directly on the scan-results screen.
- Press T to cycle the threshold and immediately re-detect signals from the existing scan data without re-running the SDR capture.
- The chosen threshold is kept for the next scan.


## v0.3.2

- `R` on the scan-results screen now performs a fresh SDR capture of the same range.
- Refresh preserves the current range, bin width, gain and detection threshold.
- `T` continues to re-detect from the existing captured data without touching the SDR.


## v0.3.3

- Fixed refresh worker UI updates by using `self.app.call_from_thread()`.
