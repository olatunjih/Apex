from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from apex_runtime import ApexRuntime, RuntimeConfig, enforce_decimal
from apex_runtime.cognitive import CognitiveLayer
from apex_runtime.errors import APEXError
from apex_runtime.reactive import AnalysisRequest, ReactiveLayer


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


class TestCognitiveLayer(unittest.TestCase):
    def test_memory_and_failure_feedback(self):
        cog = CognitiveLayer(memory_ttl_days=10)
        rec = cog.upsert_thesis("AAPL", "Earnings revision momentum", 0.8, 0.9, source_count=4, horizon_days=15, regime_tag="risk_on")
        self.assertGreater(rec.confidence, 0.0)

        cog.record_failure("AAPL", "Thesis invalidated", "momentum", realized_return_bps=-140)
        adjusted = cog.get_bias_adjusted_confidence("AAPL", 0.8)
        self.assertLess(adjusted, 0.8)

    def test_stale_eviction(self):
        cog = CognitiveLayer(memory_ttl_days=1)
        cog.upsert_thesis("MSFT", "Cloud margin expansion", 0.7, 1.0, source_count=3, horizon_days=20)
        cog.set_memory_timestamp("MSFT", datetime.now(timezone.utc) - timedelta(days=3))
        evicted = cog.evict_stale_memory()
        self.assertEqual(evicted, 1)


class TestReactiveLayer(unittest.TestCase):
    def test_reactive_analysis_uses_cognitive_calibration(self):
        cog = CognitiveLayer(memory_ttl_days=30)
        cog.upsert_thesis("NVDA", "AI capex cycle", 0.9, 0.8, source_count=5, horizon_days=30, regime_tag="risk_on")
        cog.record_failure("NVDA", "late-cycle valuation compression", "trend", realized_return_bps=-220)
        layer = ReactiveLayer(cog, RuntimeConfig())

        decision = layer.analyze(AnalysisRequest("NVDA", "analyze ticker", 0.03, 0.85, 45))
        self.assertEqual(decision.tier, "ticker")
        self.assertLess(decision.confidence, 0.85)
        self.assertIn("final", decision.why.confidence_calibration)

    def test_position_confirmation(self):
        layer = ReactiveLayer(CognitiveLayer(), RuntimeConfig())
        approved = layer.position_confirmation("AAPL", proposed_heat=0.12, max_heat=0.20)
        rejected = layer.position_confirmation("AAPL", proposed_heat=0.22, max_heat=0.20)
        self.assertTrue(approved["approved"])
        self.assertFalse(rejected["approved"])


if __name__ == "__main__":
    unittest.main()
