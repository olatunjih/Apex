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

    def test_idempotency_and_outbox_retries(self):
        rt = ApexRuntime(RuntimeConfig(max_idempotency_cache_size=2, outbox_retry_limit=2))
        self.assertEqual(rt.process_idempotent("k1", {"x": 1}), rt.process_idempotent("k1", {"x": 9}))
        self.assertEqual(rt.outbox_size, 1)
        rt.drain_outbox(fail_keys=["k1"])
        rt.drain_outbox(fail_keys=["k1"])
        self.assertEqual(rt.dead_letter_size, 1)

    def test_decimal_gate(self):
        self.assertEqual(enforce_decimal(Decimal("1.23")), Decimal("1.23"))
        with self.assertRaises(APEXError):
            enforce_decimal(1.23, "price")


class TestReactiveLayer(unittest.TestCase):
    def test_reactive_analysis_uses_why_engine_and_reflection(self):
        cog = CognitiveLayer(memory_ttl_days=30)
        cog.upsert_thesis("NVDA", "AI capex cycle", 0.9, 0.8, source_count=5, horizon_days=30, regime_tag="risk_on")
        cog.record_failure("NVDA", "late-cycle valuation compression", "trend", realized_return_bps=-220)
        layer = ReactiveLayer(cog, RuntimeConfig())

        decision = layer.analyze(AnalysisRequest("NVDA", "analyze ticker", 0.03, 0.85, 45))
        self.assertIn("horizon_days", decision.why.market_structure)
        self.assertIn("failure_rate", decision.why.evidence_quality)
        self.assertIn("loss_adjustment", decision.why.confidence_calibration)

        rec = layer.reflection.recent()[0]
        self.assertGreaterEqual(rec.failure_rate, 0.0)
        self.assertGreaterEqual(layer.reflection.analytical_debt_score(), 0.0)


if __name__ == "__main__":
    unittest.main()
