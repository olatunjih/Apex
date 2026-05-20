"""APEX v3 Financial Risk Architecture - §30, §31.

Provides VaR/CVaR calculations, position heat monitoring, drawdown tracking,
and cost budget management.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Tuple


@dataclass
class RiskConfig:
    """Configuration for risk enforcement."""
    
    max_position_heat_pct: Decimal = Decimal("2")  # 2% of equity per position
    max_portfolio_heat_pct: Decimal = Decimal("6")  # 6% total portfolio heat
    var_confidence: Decimal = Decimal("0.95")  # 95% confidence for VaR
    daily_loss_limit_pct: Decimal = Decimal("3")  # 3% daily loss limit
    drawdown_halt_pct: Decimal = Decimal("10")  # 10% drawdown triggers halt


class FinancialRiskEngine:
    """§30 — Financial Risk Architecture.
    
    Provides core financial risk calculations:
    - Historical Value at Risk (VaR)
    - Conditional VaR (Expected Shortfall / CVaR)
    - Position heat as fraction of account equity
    - Drawdown monitoring and halt checks
    """

    def compute_var(
        self,
        returns: List[Decimal],
        confidence: Decimal = Decimal("0.95"),
    ) -> Decimal:
        """Compute Historical VaR at given confidence level.
        
        Args:
            returns: List of historical returns (as Decimals)
            confidence: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            VaR as a positive Decimal representing potential loss
            
        Raises:
            ValueError: If returns list is empty
        """
        if not returns:
            raise ValueError("Returns list is empty")
        
        sorted_returns = sorted(returns)
        cutoff_idx = int(len(sorted_returns) * (1 - confidence))
        # Ensure we have at least one element
        cutoff_idx = max(0, min(cutoff_idx, len(sorted_returns) - 1))
        
        return abs(sorted_returns[cutoff_idx])

    def compute_cvar(
        self,
        returns: List[Decimal],
        confidence: Decimal = Decimal("0.95"),
    ) -> Decimal:
        """Compute Conditional VaR (Expected Shortfall).
        
        CVaR is the average loss in the tail beyond the VaR threshold.
        
        Args:
            returns: List of historical returns (as Decimals)
            confidence: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            CVaR as a positive Decimal representing expected tail loss
            
        Raises:
            ValueError: If returns list is empty
        """
        if not returns:
            raise ValueError("Returns list is empty")
        
        sorted_returns = sorted(returns)
        cutoff_idx = int(len(sorted_returns) * (1 - confidence))
        cutoff_idx = max(1, min(cutoff_idx, len(sorted_returns)))
        
        tail = sorted_returns[:cutoff_idx]
        return abs(sum(tail) / len(tail))

    def position_heat(
        self,
        position_notional: Decimal,
        account_equity: Decimal,
    ) -> Decimal:
        """Calculate position heat as fraction of account equity.
        
        Args:
            position_notional: Notional value of the position
            account_equity: Total account equity
            
        Returns:
            Heat ratio (position_notional / account_equity)
            
        Raises:
            ValueError: If account_equity is not positive
        """
        if account_equity <= 0:
            raise ValueError("Account equity must be positive")
        return position_notional / account_equity

    def check_drawdown_halt(
        self,
        current_equity: Decimal,
        peak_equity: Decimal,
        halt_pct: Decimal,
    ) -> bool:
        """Check if drawdown breach requires trading halt.
        
        Args:
            current_equity: Current account equity
            peak_equity: Peak (high water mark) equity
            halt_pct: Drawdown percentage that triggers halt
            
        Returns:
            True if drawdown >= halt_pct, False otherwise
        """
        if peak_equity <= 0:
            return False
        
        drawdown = (peak_equity - current_equity) / peak_equity * Decimal("100")
        return drawdown >= halt_pct

    def compute_portfolio_heat(
        self,
        positions: Dict[str, Decimal],
        account_equity: Decimal,
    ) -> Decimal:
        """Compute total portfolio heat from all positions.
        
        Args:
            positions: Dict mapping ticker to notional value
            account_equity: Total account equity
            
        Returns:
            Total heat ratio (sum of all position notionals / equity)
        """
        if account_equity <= 0:
            return Decimal("0")
        
        total_notional = sum(positions.values())
        return total_notional / account_equity


class PositionLimitEnforcer:
    """§30 — Enforces per-instrument and portfolio-level limits.
    
    Tracks open positions and enforces:
    - Per-position heat limits
    - Portfolio-level heat limits
    """

    def __init__(self, config: RiskConfig) -> None:
        """Initialize the enforcer with configuration.
        
        Args:
            config: RiskConfig with heat limits
        """
        self._config = config
        self._open_positions: Dict[str, Decimal] = {}
        self._lock = threading.RLock()

    def can_open(
        self,
        ticker: str,
        notional: Decimal,
        account_equity: Decimal,
    ) -> Tuple[bool, str]:
        """Check if a new position can be opened.
        
        Args:
            ticker: Ticker symbol
            notional: Proposed position notional
            account_equity: Current account equity
            
        Returns:
            Tuple of (approved, reason)
        """
        with self._lock:
            # Check individual position heat
            proposed_heat = notional / account_equity if account_equity > 0 else Decimal("1")
            max_position_heat = self._config.max_position_heat_pct / Decimal("100")
            
            if proposed_heat > max_position_heat:
                return (
                    False,
                    f"Position heat {proposed_heat:.2%} exceeds limit {max_position_heat:.2%}"
                )
            
            # Check portfolio heat
            current_total = sum(self._open_positions.values())
            new_total = current_total + notional
            portfolio_heat = new_total / account_equity if account_equity > 0 else Decimal("1")
            max_portfolio_heat = self._config.max_portfolio_heat_pct / Decimal("100")
            
            if portfolio_heat > max_portfolio_heat:
                return (
                    False,
                    f"Portfolio heat {portfolio_heat:.2%} exceeds limit {max_portfolio_heat:.2%}"
                )
            
            return True, "approved"

    def register_open(self, ticker: str, notional: Decimal) -> None:
        """Register a newly opened position.
        
        Args:
            ticker: Ticker symbol
            notional: Position notional value
        """
        with self._lock:
            current = self._open_positions.get(ticker, Decimal("0"))
            self._open_positions[ticker] = current + notional

    def register_close(self, ticker: str, notional: Decimal) -> None:
        """Register a position close/reduction.
        
        Args:
            ticker: Ticker symbol
            notional: Amount being closed
        """
        with self._lock:
            current = self._open_positions.get(ticker, Decimal("0"))
            remaining = current - notional
            self._open_positions[ticker] = max(Decimal("0"), remaining)
            
            # Clean up zero positions
            if self._open_positions[ticker] == Decimal("0"):
                del self._open_positions[ticker]

    def get_position(self, ticker: str) -> Decimal:
        """Get current notional for a ticker.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Current notional value
        """
        with self._lock:
            return self._open_positions.get(ticker, Decimal("0"))

    def get_all_positions(self) -> Dict[str, Decimal]:
        """Get all open positions.
        
        Returns:
            Copy of positions dict
        """
        with self._lock:
            return dict(self._open_positions)

    def clear(self) -> None:
        """Clear all tracked positions."""
        with self._lock:
            self._open_positions.clear()


class CostBudgetTracker:
    """§31 — Tracks LLM and API call costs against configured budgets.
    
    Thread-safe budget tracking with:
    - Daily budget enforcement
    - Spend recording
    - Remaining budget queries
    """

    def __init__(self, daily_budget_usd: Decimal) -> None:
        """Initialize the budget tracker.
        
        Args:
            daily_budget_usd: Daily budget limit in USD
        """
        self._daily_budget = daily_budget_usd
        self._spent_today: Decimal = Decimal("0")
        self._lock = threading.RLock()

    def record_spend(self, amount: Decimal) -> None:
        """Record a spend against the budget.
        
        Args:
            amount: Amount spent in USD
        """
        with self._lock:
            self._spent_today += amount

    def remaining(self) -> Decimal:
        """Get remaining budget for today.
        
        Returns:
            Remaining budget (never negative)
        """
        with self._lock:
            return max(Decimal("0"), self._daily_budget - self._spent_today)

    def is_over_budget(self) -> bool:
        """Check if budget has been exceeded.
        
        Returns:
            True if spent >= daily_budget
        """
        with self._lock:
            return self._spent_today >= self._daily_budget

    def get_spent(self) -> Decimal:
        """Get total spent today.
        
        Returns:
            Total amount spent
        """
        with self._lock:
            return self._spent_today

    def reset(self) -> None:
        """Reset the tracker (for new day)."""
        with self._lock:
            self._spent_today = Decimal("0")

    def set_budget(self, new_budget: Decimal) -> None:
        """Update the daily budget.
        
        Args:
            new_budget: New daily budget limit
        """
        with self._lock:
            self._daily_budget = new_budget
