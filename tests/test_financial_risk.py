"""Tests for FinancialRiskEngine and related classes - FIX-03.

Tests cover:
- VaR on known return series
- CVaR tail calculation
- Position heat ratio
- Drawdown halt trigger
- Position limit enforcement
- Cost budget tracking
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apex_runtime.financial_risk import (
    CostBudgetTracker,
    FinancialRiskEngine,
    PositionLimitEnforcer,
    RiskConfig,
)


class TestFinancialRiskEngineVar:
    """Test Value at Risk (VaR) calculations."""

    def test_var_on_known_series_95_confidence(self) -> None:
        """Test VaR with known return series at 95% confidence."""
        engine = FinancialRiskEngine()
        
        # 20 returns: sorted would be [-0.10, -0.08, ..., 0.09]
        returns = [Decimal(str(x / 100)) for x in range(-10, 10)]
        
        var = engine.compute_var(returns, Decimal("0.95"))
        
        # At 95% confidence with 20 samples, cutoff is at index int(20 * 0.05) = 1
        # So we expect the value at index 1 of sorted list, which is -0.09
        assert var == Decimal("0.09")

    def test_var_on_known_series_99_confidence(self) -> None:
        """Test VaR at 99% confidence."""
        engine = FinancialRiskEngine()
        
        # 100 returns from -0.50 to 0.49
        returns = [Decimal(str(x / 100)) for x in range(-50, 50)]
        
        var = engine.compute_var(returns, Decimal("0.99"))
        
        # At 99% confidence with 100 samples, cutoff is at index 1
        assert var == Decimal("0.49")

    def test_var_empty_returns_raises(self) -> None:
        """Test that empty returns list raises ValueError."""
        engine = FinancialRiskEngine()
        
        with pytest.raises(ValueError, match="Returns list is empty"):
            engine.compute_var([], Decimal("0.95"))

    def test_var_all_negative_returns(self) -> None:
        """Test VaR when all returns are negative."""
        engine = FinancialRiskEngine()
        
        returns = [Decimal("-0.05"), Decimal("-0.03"), Decimal("-0.08"), Decimal("-0.02")]
        
        var = engine.compute_var(returns, Decimal("0.95"))
        
        # Sorted: [-0.08, -0.05, -0.03, -0.02]
        # At 95% with 4 samples: cutoff = int(4 * 0.05) = 0
        assert var == Decimal("0.08")

    def test_var_single_value(self) -> None:
        """Test VaR with single return value."""
        engine = FinancialRiskEngine()
        
        returns = [Decimal("-0.05")]
        
        var = engine.compute_var(returns, Decimal("0.95"))
        
        assert var == Decimal("0.05")


class TestFinancialRiskEngineCvar:
    """Test Conditional VaR (Expected Shortfall) calculations."""

    def test_cvar_on_known_series_95_confidence(self) -> None:
        """Test CVaR with known return series at 95% confidence."""
        engine = FinancialRiskEngine()
        
        # 20 returns
        returns = [Decimal(str(x / 100)) for x in range(-10, 10)]
        
        cvar = engine.compute_cvar(returns, Decimal("0.95"))
        
        # At 95% with 20 samples, tail has 1 element (index 0)
        # Tail is just [-0.10], so average is -0.10
        assert cvar == Decimal("0.10")

    def test_cvar_tail_average(self) -> None:
        """Test CVaR computes average of tail losses."""
        engine = FinancialRiskEngine()
        
        # Returns where tail has multiple elements
        returns = [
            Decimal("-0.10"),
            Decimal("-0.08"),
            Decimal("-0.06"),
            Decimal("-0.04"),
            Decimal("-0.02"),
            Decimal("0.01"),
            Decimal("0.02"),
            Decimal("0.03"),
            Decimal("0.04"),
            Decimal("0.05"),
        ]
        
        # At 90% confidence with 10 samples, tail has 1 element (10%)
        cvar = engine.compute_cvar(returns, Decimal("0.90"))
        
        # Tail is just [-0.10]
        assert cvar == Decimal("0.10")

    def test_cvar_empty_returns_raises(self) -> None:
        """Test that empty returns list raises ValueError."""
        engine = FinancialRiskEngine()
        
        with pytest.raises(ValueError, match="Returns list is empty"):
            engine.compute_cvar([], Decimal("0.95"))

    def test_cvar_larger_tail(self) -> None:
        """Test CVaR with larger tail (lower confidence)."""
        engine = FinancialRiskEngine()
        
        returns = [
            Decimal("-0.10"),
            Decimal("-0.08"),
            Decimal("-0.06"),
            Decimal("-0.04"),
            Decimal("-0.02"),
            Decimal("0.00"),
            Decimal("0.02"),
            Decimal("0.04"),
            Decimal("0.06"),
            Decimal("0.08"),
        ]
        
        # At 50% confidence, tail is bottom 50% (5 elements)
        cvar = engine.compute_cvar(returns, Decimal("0.50"))
        
        # Tail average: (-0.10 + -0.08 + -0.06 + -0.04 + -0.02) / 5 = -0.06
        assert cvar == Decimal("0.06")


class TestPositionHeat:
    """Test position heat calculations."""

    def test_heat_ratio_calculation(self) -> None:
        """Test basic heat ratio calculation."""
        engine = FinancialRiskEngine()
        
        heat = engine.position_heat(
            position_notional=Decimal("10000"),
            account_equity=Decimal("100000"),
        )
        
        assert heat == Decimal("0.1")  # 10%

    def test_heat_with_small_position(self) -> None:
        """Test heat with small position relative to equity."""
        engine = FinancialRiskEngine()
        
        heat = engine.position_heat(
            position_notional=Decimal("1000"),
            account_equity=Decimal("100000"),
        )
        
        assert heat == Decimal("0.01")  # 1%

    def test_heat_zero_equity_raises(self) -> None:
        """Test that zero equity raises ValueError."""
        engine = FinancialRiskEngine()
        
        with pytest.raises(ValueError, match="Account equity must be positive"):
            engine.position_heat(
                position_notional=Decimal("1000"),
                account_equity=Decimal("0"),
            )

    def test_heat_negative_equity_raises(self) -> None:
        """Test that negative equity raises ValueError."""
        engine = FinancialRiskEngine()
        
        with pytest.raises(ValueError, match="Account equity must be positive"):
            engine.position_heat(
                position_notional=Decimal("1000"),
                account_equity=Decimal("-1000"),
            )


class TestDrawdownHalt:
    """Test drawdown halt checks."""

    def test_drawdown_triggers_halt(self) -> None:
        """Test that drawdown >= halt_pct triggers halt."""
        engine = FinancialRiskEngine()
        
        should_halt = engine.check_drawdown_halt(
            current_equity=Decimal("90000"),
            peak_equity=Decimal("100000"),
            halt_pct=Decimal("10"),
        )
        
        # Drawdown is exactly 10%, should halt
        assert should_halt is True

    def test_drawdown_below_threshold_no_halt(self) -> None:
        """Test that drawdown < halt_pct does not trigger halt."""
        engine = FinancialRiskEngine()
        
        should_halt = engine.check_drawdown_halt(
            current_equity=Decimal("95000"),
            peak_equity=Decimal("100000"),
            halt_pct=Decimal("10"),
        )
        
        # Drawdown is 5%, below 10% threshold
        assert should_halt is False

    def test_drawdown_exceeds_threshold_halt(self) -> None:
        """Test that drawdown > halt_pct triggers halt."""
        engine = FinancialRiskEngine()
        
        should_halt = engine.check_drawdown_halt(
            current_equity=Decimal("85000"),
            peak_equity=Decimal("100000"),
            halt_pct=Decimal("10"),
        )
        
        # Drawdown is 15%, exceeds 10% threshold
        assert should_halt is True

    def test_zero_peak_equity_no_halt(self) -> None:
        """Test that zero peak equity returns False (no halt)."""
        engine = FinancialRiskEngine()
        
        should_halt = engine.check_drawdown_halt(
            current_equity=Decimal("50000"),
            peak_equity=Decimal("0"),
            halt_pct=Decimal("10"),
        )
        
        assert should_halt is False

    def test_drawdown_calculation_precision(self) -> None:
        """Test precise drawdown calculation."""
        engine = FinancialRiskEngine()
        
        # Peak: 100000, Current: 92500 => Drawdown = 7.5%
        should_halt = engine.check_drawdown_halt(
            current_equity=Decimal("92500"),
            peak_equity=Decimal("100000"),
            halt_pct=Decimal("7.5"),
        )
        
        assert should_halt is True


class TestPortfolioHeat:
    """Test portfolio heat calculation."""

    def test_portfolio_heat_single_position(self) -> None:
        """Test portfolio heat with single position."""
        engine = FinancialRiskEngine()
        
        positions = {"AAPL": Decimal("10000")}
        heat = engine.compute_portfolio_heat(positions, Decimal("100000"))
        
        assert heat == Decimal("0.1")

    def test_portfolio_heat_multiple_positions(self) -> None:
        """Test portfolio heat with multiple positions."""
        engine = FinancialRiskEngine()
        
        positions = {
            "AAPL": Decimal("10000"),
            "GOOGL": Decimal("15000"),
            "MSFT": Decimal("5000"),
        }
        heat = engine.compute_portfolio_heat(positions, Decimal("100000"))
        
        # Total: 30000 / 100000 = 0.3
        assert heat == Decimal("0.3")

    def test_portfolio_heat_zero_equity(self) -> None:
        """Test portfolio heat with zero equity returns 0."""
        engine = FinancialRiskEngine()
        
        positions = {"AAPL": Decimal("10000")}
        heat = engine.compute_portfolio_heat(positions, Decimal("0"))
        
        assert heat == Decimal("0")

    def test_portfolio_heat_empty_positions(self) -> None:
        """Test portfolio heat with no positions."""
        engine = FinancialRiskEngine()
        
        positions: dict = {}
        heat = engine.compute_portfolio_heat(positions, Decimal("100000"))
        
        assert heat == Decimal("0")


class TestPositionLimitEnforcer:
    """Test position limit enforcement."""

    def test_can_open_within_limits(self) -> None:
        """Test that position within limits is approved."""
        config = RiskConfig(
            max_position_heat_pct=Decimal("2"),
            max_portfolio_heat_pct=Decimal("6"),
        )
        enforcer = PositionLimitEnforcer(config)
        
        approved, reason = enforcer.can_open(
            ticker="AAPL",
            notional=Decimal("1000"),
            account_equity=Decimal("100000"),
        )
        
        assert approved is True
        assert reason == "approved"

    def test_cannot_open_exceeds_position_heat(self) -> None:
        """Test that position exceeding heat limit is rejected."""
        config = RiskConfig(
            max_position_heat_pct=Decimal("2"),
            max_portfolio_heat_pct=Decimal("6"),
        )
        enforcer = PositionLimitEnforcer(config)
        
        approved, reason = enforcer.can_open(
            ticker="AAPL",
            notional=Decimal("5000"),  # 5% of 100k, exceeds 2% limit
            account_equity=Decimal("100000"),
        )
        
        assert approved is False
        assert "Position heat" in reason

    def test_cannot_open_exceeds_portfolio_heat(self) -> None:
        """Test that position causing portfolio heat breach is rejected."""
        config = RiskConfig(
            max_position_heat_pct=Decimal("5"),
            max_portfolio_heat_pct=Decimal("6"),
        )
        enforcer = PositionLimitEnforcer(config)
        
        # First position uses 4%
        enforcer.register_open("AAPL", Decimal("4000"))
        
        # Second position would bring total to 7%, exceeding 6%
        approved, reason = enforcer.can_open(
            ticker="GOOGL",
            notional=Decimal("3000"),
            account_equity=Decimal("100000"),
        )
        
        assert approved is False
        assert "Portfolio heat" in reason

    def test_register_open_tracks_position(self) -> None:
        """Test that register_open correctly tracks position."""
        config = RiskConfig()
        enforcer = PositionLimitEnforcer(config)
        
        enforcer.register_open("AAPL", Decimal("5000"))
        
        assert enforcer.get_position("AAPL") == Decimal("5000")

    def test_register_close_reduces_position(self) -> None:
        """Test that register_close reduces position."""
        config = RiskConfig()
        enforcer = PositionLimitEnforcer(config)
        
        enforcer.register_open("AAPL", Decimal("5000"))
        enforcer.register_close("AAPL", Decimal("2000"))
        
        assert enforcer.get_position("AAPL") == Decimal("3000")

    def test_register_close_removes_zero_position(self) -> None:
        """Test that closing full position removes it."""
        config = RiskConfig()
        enforcer = PositionLimitEnforcer(config)
        
        enforcer.register_open("AAPL", Decimal("5000"))
        enforcer.register_close("AAPL", Decimal("5000"))
        
        assert enforcer.get_position("AAPL") == Decimal("0")
        assert "AAPL" not in enforcer.get_all_positions()

    def test_get_all_positions_returns_copy(self) -> None:
        """Test that get_all_positions returns a copy."""
        config = RiskConfig()
        enforcer = PositionLimitEnforcer(config)
        
        enforcer.register_open("AAPL", Decimal("5000"))
        
        positions = enforcer.get_all_positions()
        positions["AAPL"] = Decimal("9999")  # Modify returned dict
        
        # Original should be unchanged
        assert enforcer.get_position("AAPL") == Decimal("5000")


class TestCostBudgetTracker:
    """Test cost budget tracking."""

    def test_record_spend_increases_total(self) -> None:
        """Test that recording spend increases total."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("25"))
        
        assert tracker.get_spent() == Decimal("25")

    def test_remaining_decreases_with_spend(self) -> None:
        """Test that remaining budget decreases with spends."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("25"))
        
        assert tracker.remaining() == Decimal("75")

    def test_is_over_budget_false_when_under(self) -> None:
        """Test is_over_budget returns False when under budget."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("50"))
        
        assert tracker.is_over_budget() is False

    def test_is_over_budget_true_when_equal(self) -> None:
        """Test is_over_budget returns True when at budget."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("100"))
        
        assert tracker.is_over_budget() is True

    def test_is_over_budget_true_when_exceeded(self) -> None:
        """Test is_over_budget returns True when over budget."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("150"))
        
        assert tracker.is_over_budget() is True

    def test_remaining_never_negative(self) -> None:
        """Test that remaining never returns negative value."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("150"))
        
        assert tracker.remaining() == Decimal("0")

    def test_reset_clears_spent(self) -> None:
        """Test that reset clears spent amount."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("75"))
        tracker.reset()
        
        assert tracker.get_spent() == Decimal("0")
        assert tracker.remaining() == Decimal("100")

    def test_set_budget_updates_limit(self) -> None:
        """Test that set_budget updates the daily limit."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.set_budget(Decimal("200"))
        
        assert tracker.remaining() == Decimal("200")
        
        tracker.record_spend(Decimal("150"))
        assert tracker.remaining() == Decimal("50")

    def test_multiple_spends_accumulate(self) -> None:
        """Test that multiple spends accumulate correctly."""
        tracker = CostBudgetTracker(daily_budget_usd=Decimal("100"))
        
        tracker.record_spend(Decimal("25"))
        tracker.record_spend(Decimal("30"))
        tracker.record_spend(Decimal("15"))
        
        assert tracker.get_spent() == Decimal("70")
        assert tracker.remaining() == Decimal("30")
