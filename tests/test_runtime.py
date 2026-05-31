from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import signal
import unittest

from apex_runtime import (
    ApexRuntime,
    RuntimeConfig,
    RuntimePhase,
    HealthChecker,
    HealthCheckSystem,
    SignalHandler,
    SignalStrength,
    StrategyAggregator,
    StrategySignal,
    EpistemicState,
    create_standard_tool_registry,
    enforce_decimal,
)
from apex_runtime.errors import APEXError
from apex_runtime.reactive import AnalysisRequest, ReactiveLayer
from apex_runtime.cognitive import CognitiveLayer
from apex_runtime.policy import NumericalPolicy


class TestRuntime(unittest.TestCase):
    def test_startup_degraded_mode(self):
        rt = ApexRuntime(RuntimeConfig())
        stale = datetime.now(timezone.utc) - timedelta(hours=2)
        state = rt.startup(vendor_ok=False, llm_ok=False, snapshot_timestamp=stale)
        self.assertTrue(state.ready)
        self.assertEqual(state.phase, RuntimePhase.SERVICES)

    def test_startup_rejects_invalid_numerical_policy(self):
        cfg = RuntimeConfig()
        object.__setattr__(cfg, "numerical_policy", NumericalPolicy(
            monetary_precision=10,
            monetary_type_name="Decimal",
            rounding_mode=ROUND_HALF_UP,
            price_display_precision=2,
            percentage_precision=6,
        ))
        rt = ApexRuntime(cfg)
        with self.assertRaises(ValueError):
            rt.startup()

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
        self.assertGreaterEqual(layer.reflection.analytical_debt_score(), 0.0)


class TestPhase0Stabilization(unittest.TestCase):
    def _signal(self, sid, direction, confidence, strength=SignalStrength.STRONG):
        return StrategySignal(
            signal_id=sid,
            strategy_id=f"strategy_{sid}",
            ticker="AAPL",
            timestamp=datetime.now(timezone.utc),
            direction=direction,
            strength=strength,
            confidence=Decimal(confidence),
            target_price=None,
            stop_loss=None,
            time_horizon_days=5,
            rationale="test",
            epistemic_state=EpistemicState.PROBABLE,
        )

    def test_strategy_aggregation_penalizes_dissenting_confidence(self):
        aggregator = StrategyAggregator()
        signal = aggregator.aggregate_signals(
            "AAPL",
            [
                self._signal("long", "long", "0.90", SignalStrength.STRONG),
                self._signal("short", "short", "0.60", SignalStrength.MODERATE),
            ],
        )

        self.assertEqual(signal.aggregated_direction, "long")
        self.assertEqual(signal.consensus_score, Decimal("0.6"))
        self.assertEqual(signal.aggregated_confidence, Decimal("0.540"))

    def test_tool_metadata_is_initialized_without_forward_declaration(self):
        registry = create_standard_tool_registry()
        tool = registry.get("fetch_market_data")

        self.assertIsNotNone(tool)
        metadata = tool.get_metadata()
        self.assertEqual(metadata.tool_id, "fetch_market_data")
        self.assertTrue(metadata.stateless)
        self.assertTrue(metadata.llm_free)

    def test_health_checker_uses_canonical_health_system(self):
        self.assertIs(HealthChecker, HealthCheckSystem)
        checker = HealthChecker()
        checker.register_check("ready_test", lambda: (True, "ok", None))
        ready = checker.get_ready_status()
        self.assertEqual(ready.status, "healthy")
        self.assertIn("ready_test", ready.checks)

    def test_signal_debug_dump_does_not_fail_on_asdict(self):
        handler = SignalHandler()
        handler.toggle_verbose_logging(signal.SIGUSR2, None)
        handler.dump_debug_state(signal.SIGUSR1, None)
        self.assertEqual(handler.get_signal_history()[-1].result, "success")


if __name__ == "__main__":
    unittest.main()
