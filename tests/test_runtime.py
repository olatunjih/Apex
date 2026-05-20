from decimal import Decimal
import unittest

from apex_runtime import ApexRuntime, RuntimeConfig, enforce_decimal
from apex_runtime.errors import APEXError


class TestRuntime(unittest.TestCase):
    def test_startup_degraded_mode(self):
        rt = ApexRuntime(RuntimeConfig())
        state = rt.startup(vendor_ok=False, llm_ok=False)
        self.assertTrue(state.ready)
        self.assertIn("analysis_mode_data_warning", state.degraded_modes)
        self.assertIn("deterministic_only", state.degraded_modes)

    def test_idempotency(self):
        rt = ApexRuntime(RuntimeConfig())
        first = rt.process_idempotent("k1", {"x": 1})
        second = rt.process_idempotent("k1", {"x": 9})
        self.assertEqual(first, second)

    def test_decimal_gate(self):
        self.assertEqual(enforce_decimal(Decimal("1.23")), Decimal("1.23"))
        with self.assertRaises(APEXError):
            enforce_decimal(1.23, "price")


if __name__ == "__main__":
    unittest.main()
