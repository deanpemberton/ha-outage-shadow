"""Pure restoration evidence regression tests; no Home Assistant required."""
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

spec = spec_from_file_location('restoration_under_test', Path(__file__).resolve().parents[1] / 'custom_components' / 'we_outage_shadow' / 'restoration.py')
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
MELLING_2025, NETWORK_2025, compare = module.MELLING_2025, module.NETWORK_2025, module.compare

class TestEvidence(unittest.TestCase):
    def test_melling_counts(self):
        self.assertEqual(MELLING_2025.observations, 10)
        self.assertEqual(MELLING_2025.count_within(6), 9)
        self.assertEqual(MELLING_2025.count_within(12), 10)

    def test_network_counts(self):
        self.assertEqual(NETWORK_2025.observations, 208)
        self.assertEqual(NETWORK_2025.count_within(48), 205)

    def test_no_probability_claim(self):
        result = compare({"24h_p10": {"status": "survives"}})
        self.assertIsNone(result["restoration_probability"])
        self.assertFalse(result["evidence"]["calibrated"])
        self.assertEqual(result["windows"]["24h"]["battery_status"], "survives")
        self.assertEqual(result["windows"]["6h"]["battery_status"], "unknown")

if __name__ == "__main__":
    unittest.main()
