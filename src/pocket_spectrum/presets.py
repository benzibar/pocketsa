from pocket_spectrum.models import ScanPreset


PRESETS: list[ScanPreset] = [
    ScanPreset(
        id="fm-radio",
        name="FM Radio",
        start_hz=87_500_000,
        stop_hz=108_000_000,
        step_hz=100_000,
        description="UK VHF FM broadcast band",
    ),
    ScanPreset(
        id="airband",
        name="Airband",
        start_hz=118_000_000,
        stop_hz=137_000_000,
        step_hz=25_000,
        description="Civil aviation VHF voice/navigation band",
    ),
    ScanPreset(
        id="2m",
        name="2m Amateur",
        start_hz=144_000_000,
        stop_hz=146_000_000,
        step_hz=12_500,
        description="UK 2 metre amateur band",
    ),
    ScanPreset(
        id="marine",
        name="Marine VHF",
        start_hz=156_000_000,
        stop_hz=163_000_000,
        step_hz=25_000,
        description="Marine VHF voice/AIS neighbourhood",
    ),
    ScanPreset(
        id="70cm",
        name="70cm Amateur",
        start_hz=430_000_000,
        stop_hz=440_000_000,
        step_hz=12_500,
        description="UK 70 centimetre amateur band",
    ),
    ScanPreset(
        id="pmr446",
        name="PMR446",
        start_hz=446_000_000,
        stop_hz=446_200_000,
        step_hz=6_250,
        description="PMR446 handheld radio channels",
    ),
    ScanPreset(
        id="adsb",
        name="ADS-B Area",
        start_hz=1_085_000_000,
        stop_hz=1_095_000_000,
        step_hz=100_000,
        description="10 MHz view centred on 1090 MHz",
    ),
]
