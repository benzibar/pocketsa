import unittest

from pocket_spectrum.receiver_integration import (
    receiver_command,
    tuning_for_frequency,
)


class ReceiverIntegrationTests(unittest.TestCase):
    def test_fm_broadcast_defaults_to_wfm(self):
        tuning = tuning_for_frequency(104_000_000)
        self.assertEqual((tuning.mode, tuning.bandwidth_khz), ("WFM", 200.0))

    def test_airband_defaults_to_am(self):
        tuning = tuning_for_frequency(121_500_000)
        self.assertEqual((tuning.mode, tuning.bandwidth_khz), ("AM", 12.0))

    def test_other_frequencies_default_to_nfm(self):
        tuning = tuning_for_frequency(145_500_000)
        self.assertEqual((tuning.mode, tuning.bandwidth_khz), ("NFM", 12.5))

    def test_command_is_an_argument_list_and_autoplays(self):
        command = receiver_command(446_006_250, executable="receiver-test")
        self.assertEqual(command[0], "receiver-test")
        self.assertIn("446.006250", command)
        self.assertIn("NFM", command)
        self.assertEqual(command[-1], "--play")


if __name__ == "__main__":
    unittest.main()

