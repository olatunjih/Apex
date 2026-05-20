from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from apex_runtime import ApexRuntime, RuntimeConfig, enforce_decimal
from apex_runtime.cognitive import CognitiveLayer
from apex_runtime.errors import APEXError


class TestRuntime(unittest.TestCase):
    def test_startup_degraded_mode(self):
        rt = ApexRuntime(RuntimeConfig())
        stale = datetime.now(timezone.utc) - timedelta(hours=2)
        state = rt.startup(vendor_ok=False, llm_ok=False, snapshot_timestamp=stale)
        self.assertTrue(state.ready)
        self.assertIn("analysis_mode_data_warning", state.degraded_modes)
        self.assertIn("deterministic_only", state.degraded_modes)
        self.assertIn("pil_cold_start", state.degraded_modes)

    def test_idempotency_and_outbox(self):
        rt = ApexRuntime(RuntimeConfig(max_idempotency_cache_size=2))
        first = rt.process_idempotent("k1", {"x": 1})
        second = rt.process_idempotent("k1", {"x": 9})
        self.assertEqual(first, second)
        self.assertEqual(rt.outbox_size, 1)

        rt.process_idempotent("k2", {"x": 2})
        rt.process_idempotent("k3", {"x": 3})
        self.assertEqual(len(rt._idempotency_cache), 2)

    def test_decimal_gate(self):
        self.assertEqual(enforce_decimal(Decimal("1.23")), Decimal("1.23"))
        with self.assertRaises(APEXError):
            enforce_decimal(1.23, "price")

    def test_drain_outbox_dlq(self):
        rt = ApexRuntime(RuntimeConfig())
        rt.process_idempotent("k1", {"x": 1})
        rt.process_idempotent("k2", {"x": 2})
        delivered = rt.drain_outbox(fail_keys=["k2"])
        self.assertEqual(delivered, 1)
        self.assertEqual(rt.dead_letter_size, 1)


class TestCognitiveLayer(unittest.TestCase):
    def test_memory_and_failure_feedback(self):
        cog = CognitiveLayer(memory_ttl_days=10)
        rec = cog.upsert_thesis("AAPL", "Earnings revision momentum", 0.8, 0.9)
        self.assertAlmostEqual(rec.confidence, 0.72)

        cog.record_failure("AAPL", "Thesis invalidated", "momentum")
        adjusted = cog.get_bias_adjusted_confidence("AAPL", 0.8)
        self.assertLess(adjusted, 0.8)

    def test_stale_eviction(self):
        cog = CognitiveLayer(memory_ttl_days=1)
        rec = cog.upsert_thesis("MSFT", "Cloud margin expansion", 0.7, 1.0)
        rec.created_at = datetime.now(timezone.utc) - timedelta(days=3)
        evicted = cog.evict_stale_memory()
        self.assertEqual(evicted, 1)


if __name__ == "__main__":
    unittest.main()
