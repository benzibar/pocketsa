import unittest

from pocket_spectrum.presets import PRESETS


class PresetTests(unittest.TestCase):
    def test_uk_fm_broadcast_preset(self):
        preset = next(item for item in PRESETS if item.id == "fm-radio")
        self.assertEqual(preset.name, "FM Radio")
        self.assertEqual(preset.start_hz, 87_500_000)
        self.assertEqual(preset.stop_hz, 108_000_000)
        self.assertEqual(preset.step_hz, 100_000)


if __name__ == "__main__":
    unittest.main()
