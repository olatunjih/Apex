from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from apex_runtime import ApexRuntime, RuntimeConfig, RuntimePhase, enforce_decimal
from apex_runtime.cognitive import CognitiveLayer
from apex_runtime.errors import APEXError
from apex_runtime.reactive import AnalysisRequest, ReactiveLayer


class TestRuntime(unittest.TestCase):
    def test_startup_degraded_mode(self):
        rt = ApexRuntime(RuntimeConfig())
        stale = datetime.now(timezone.utc) - timedelta(hours=2)
        state = rt.startup(vendor_ok=False, llm_ok=False, snapshot_timestamp=stale)
        self.assertTrue(state.ready)
        self.assertEqual(state.phase, RuntimePhase.SERVICES)
        self.assertIn("analysis_mode_data_warning", state.degraded_modes)
        self.assertIn("deterministic_only", state.degraded_modes)
        self.assertIn("pil_cold_start", state.degraded_modes)
        self.assertTrue(any("PIL_STARTING" in e for e in state.audit_trail))

    def test_idempotency_and_outbox_retries(self):
        rt = ApexRuntime(RuntimeConfig(max_idempotency_cache_size=2, outbox_retry_limit=2))
        first = rt.process_idempotent("k1", {"x": 1})
        second = rt.process_idempotent("k1", {"x": 9})
        self.assertEqual(first, second)
        self.assertEqual(rt.outbox_size, 1)

        delivered = rt.drain_outbox(fail_keys=["k1"])
        self.assertEqual(delivered, 0)
        self.assertEqual(rt.outbox_size, 1)

        delivered = rt.drain_outbox(fail_keys=["k1"])
        self.assertEqual(delivered, 0)
        self.assertEqual(rt.dead_letter_size, 1)

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


class TestReactiveLayer(unittest.TestCase):
    def test_reactive_analysis_uses_cognitive_calibration(self):
        cog = CognitiveLayer(memory_ttl_days=30)
        cog.upsert_thesis("NVDA", "AI capex cycle", 0.9, 0.8, source_count=5, horizon_days=30, regime_tag="risk_on")
        cog.record_failure("NVDA", "late-cycle valuation compression", "trend", realized_return_bps=-220)
        layer = ReactiveLayer(cog, RuntimeConfig())

        decision = layer.analyze(AnalysisRequest("NVDA", "analyze ticker", 0.03, 0.85, 45))
        self.assertEqual(decision.tier, "ticker")
        self.assertLess(decision.confidence, 0.85)
        self.assertIn("threshold", decision.why.confidence_calibration)


if __name__ == "__main__":
    unittest.main()
