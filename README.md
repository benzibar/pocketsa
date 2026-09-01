# Pocket Spectrum

Receive-only spectrum scanner for PocketTerm.

## v0.1

Pocket Spectrum uses the Linux `rtl_power` utility as its first SDR backend.
The UI is intentionally independent of the backend so HackRF support can be
added later without rewriting the application.

### Current features

- Detects the RTL-SDR through `rtl_test`.
- Scans a selected preset band with `rtl_power`.
- Estimates the local noise floor using the median power level.
- Detects peaks above the noise floor.
- Displays frequency, power and level above the estimated noise floor.
- Signal detail screen.
- `Q` is the normal Back/Exit key.

### Included presets

- Civil Airband
- UK 2 metre amateur
- Marine VHF
- UK 70 centimetre amateur
- PMR446
- 1090 MHz ADS-B neighbourhood

This version is receive-only. It does not transmit or interact with signals.

## PocketTerm prerequisites

Check that the RTL-SDR utilities are installed:

```bash
which rtl_power
which rtl_test
```

If they are missing:

```bash
sudo apt update
sudo apt install rtl-sdr
```

Before running Pocket Spectrum, stop any service currently holding the RTL-SDR,
such as `readsb`:

```bash
sudo systemctl stop readsb
```

After testing Pocket Spectrum, restart ADS-B reception with:

```bash
sudo systemctl start readsb
```

## Install

```bash
cd ~/pocketterm/apps
git clone https://github.com/benzibar/pocket-spectrum.git
cd pocket-spectrum

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
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
command = "/home/bdm198/pocketterm/apps/pocket-spectrum/.venv/bin/pocket-spectrum"
args = []
cwd = "/home/bdm198/pocketterm/apps/pocket-spectrum"
```

## Roadmap

- Custom frequency-range entry.
- Threshold/gain controls.
- Spectrum graph.
- Waterfall/history view.
- Tune/inspect mode.
- Saved findings.
- HackRF backend.


## v0.1.1

- Fixed Rich field-label colour styling on startup.
