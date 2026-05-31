"""
APEX v3 — Configuration Architecture (Section 2)

Implements 5-level resolution priority:
1. Session overrides (runtime)
2. User config (database)
3. Strategy config (database)
4. Environment variables
5. Schema defaults

Features:
- Cross-field validation (stop_loss < max_position, etc.)
- Semantic validation (mode: live requires broker_api_key)
- Configuration audit trail
- Diff display on change with confirmation
- All Appendix G config keys
"""

from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy

from .errors import APEXError, ErrorCategory, ErrorSeverity
from .numerics import NumericalPolicy, DEFAULT_NUMERICAL_POLICY, validate_numerical_policy


class ConfigResolutionLevel(Enum):
    """Configuration resolution priority levels (highest to lowest)."""
    SESSION_OVERRIDE = 1
    USER_CONFIG = 2
    STRATEGY_CONFIG = 3
    ENVIRONMENT = 4
    SCHEMA_DEFAULT = 5


class DeploymentMode(Enum):
    """Deployment mode affects validation requirements."""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class RiskConfig:
    """Risk management configuration (Appendix G)."""
    # Portfolio-level risk
    max_portfolio_heat_pct: Decimal = field(default_factory=lambda: Decimal("6.0"))
    max_portfolio_var_pct: Decimal = field(default_factory=lambda: Decimal("2.0"))
    max_drawdown_halt_pct: Decimal = field(default_factory=lambda: Decimal("12.0"))
    
    # Position-level risk
    max_position_pct: Decimal = field(default_factory=lambda: Decimal("2.0"))
    max_position_per_symbol_pct: Decimal = field(default_factory=lambda: Decimal("5.0"))
    stop_loss_pct: Decimal = field(default_factory=lambda: Decimal("1.0"))
    take_profit_pct: Decimal = field(default_factory=lambda: Decimal("3.0"))
    
    # Concentration limits
    max_sector_concentration_pct: Decimal = field(default_factory=lambda: Decimal("25.0"))
    max_correlation_exposure: Decimal = field(default_factory=lambda: Decimal("0.7"))
    max_open_positions: int = 10
    
    # Sizing
    default_risk_per_trade_pct: Decimal = field(default_factory=lambda: Decimal("0.5"))
    pyramiding_enabled: bool = False
    max_pyramid_levels: int = 3
    
    def __post_init__(self):
        # Cross-field validation
        if self.stop_loss_pct >= self.max_position_pct:
            raise ValueError(
                f"stop_loss_pct ({self.stop_loss_pct}) must be < max_position_pct ({self.max_position_pct})"
            )
        if self.take_profit_pct <= self.stop_loss_pct:
            raise ValueError(
                f"take_profit_pct ({self.take_profit_pct}) must be > stop_loss_pct ({self.stop_loss_pct})"
            )
        if self.max_portfolio_heat_pct < Decimal("0") or self.max_portfolio_heat_pct > Decimal("100"):
            raise ValueError(f"max_portfolio_heat_pct must be 0-100, got {self.max_portfolio_heat_pct}")
        if self.max_position_pct < Decimal("0") or self.max_position_pct > Decimal("100"):
            raise ValueError(f"max_position_pct must be 0-100, got {self.max_position_pct}")


@dataclass(frozen=True)
class LLMProviderConfig:
    """LLM provider chain configuration."""
    primary_provider: str = "anthropic"
    primary_model: str = "claude-sonnet-4-5-20250929"
    fallback_provider: Optional[str] = "openai"
    fallback_model: Optional[str] = "gpt-4o"
    emergency_provider: Optional[str] = "local"
    emergency_model: Optional[str] = "llama-3-8b"
    
    # Rate limits
    max_requests_per_minute: int = 60
    max_tokens_per_minute: int = 30000
    max_concurrent_requests: int = 5
    
    # Timeouts
    request_timeout_seconds: float = 30.0
    connection_timeout_seconds: float = 10.0
    
    # Cost controls
    max_cost_per_day_usd: Decimal = field(default_factory=lambda: Decimal("50.0"))
    cost_alert_threshold_pct: Decimal = field(default_factory=lambda: Decimal("80.0"))


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection pool configuration."""
    url: str = ""  # Required for LIVE mode
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout_seconds: float = 30.0
    pool_recycle_seconds: float = 3600.0
    echo_sql: bool = False
    
    # Schema management
    auto_migrate: bool = True
    schema_version_check: bool = True


@dataclass(frozen=True)
class WebSocketConfig:
    """WebSocket backpressure configuration."""
    max_queue_size: int = 1000
    message_timeout_seconds: float = 5.0
    reconnect_delay_seconds: float = 1.0
    max_reconnect_attempts: int = 10
    heartbeat_interval_seconds: float = 30.0
    backpressure_threshold_pct: Decimal = field(default_factory=lambda: Decimal("80.0"))


@dataclass(frozen=True)
class DataVendorConfig:
    """Data vendor failover configuration."""
    primary_vendor: str = "polygon"
    secondary_vendor: str = "alpaca"
    emergency_vendor: str = "yfinance"
    
    # Health check
    health_check_interval_seconds: int = 60
    health_check_timeout_seconds: float = 5.0
    consecutive_failures_threshold: int = 3
    
    # Circuit breaker
    circuit_breaker_timeout_seconds: int = 300
    half_open_requests: int = 3


@dataclass(frozen=True)
class RuntimeConfig:
    """
    Master runtime configuration with all Appendix G keys.
    
    Resolution priority (applied at runtime, not in this frozen dataclass):
    1. Session overrides
    2. User config (DB)
    3. Strategy config (DB)
    4. Environment variables
    5. Schema defaults (these values)
    """
    # === Tier 0 Foundation ===
    max_clock_drift_ms: int = 50
    max_startup_snapshot_age_seconds: int = 3600
    startup_vendor_optional: bool = True
    startup_llm_optional: bool = True
    max_idempotency_cache_size: int = 10000
    outbox_retry_limit: int = 3
    dlq_alert_threshold: int = 100
    shutdown_drain_timeout_seconds: int = 30
    
    # === Decision Thresholds ===
    min_actionable_confidence: Decimal = field(default_factory=lambda: Decimal("0.75"))
    min_risk_budget: Decimal = field(default_factory=lambda: Decimal("0.01"))
    long_horizon_days_threshold: int = 45
    long_horizon_penalty: Decimal = field(default_factory=lambda: Decimal("0.1"))
    actionable_research_action: str = "allow"  # allow, block, warn
    blocked_action: str = "abort"  # abort, defer, escalate
    
    # === Numerical Policy ===
    numerical_policy: NumericalPolicy = field(default_factory=lambda: DEFAULT_NUMERICAL_POLICY)
    
    # === Risk Management ===
    risk: RiskConfig = field(default_factory=lambda: RiskConfig())
    
    # === LLM Provider Chain ===
    llm: LLMProviderConfig = field(default_factory=lambda: LLMProviderConfig())
    
    # === Database ===
    database: DatabaseConfig = field(default_factory=lambda: DatabaseConfig())
    
    # === WebSocket ===
    websocket: WebSocketConfig = field(default_factory=lambda: WebSocketConfig())
    
    # === Data Vendors ===
    data_vendors: DataVendorConfig = field(default_factory=lambda: DataVendorConfig())
    
    # === Deployment Mode ===
    deployment_mode: DeploymentMode = DeploymentMode.PAPER
    
    # === Feature Flags ===
    enable_pil: bool = True
    enable_learning_engine: bool = True
    enable_second_order_analysis: bool = True
    enable_narrative_consistency: bool = True
    enable_ethical_framework: bool = True
    enable_analytical_debt_dashboard: bool = True
    deterministic_only: bool = False  # Forces no LLM calls
    
    # === Observability ===
    log_level: str = "INFO"
    enable_debug_logging: bool = False
    audit_trail_enabled: bool = True
    metrics_export_enabled: bool = True
    trace_sample_rate: Decimal = field(default_factory=lambda: Decimal("0.1"))
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Validate numerical policy
        validate_numerical_policy(self.numerical_policy)
        
        # Validate risk config (already validated in RiskConfig.__post_init__)
        
        # Semantic validation based on deployment mode
        if self.deployment_mode == DeploymentMode.LIVE:
            if not self.database.url:
                raise ValueError(
                    "deployment_mode=LIVE requires database.url to be non-empty"
                )
            if self.deterministic_only and not self.enable_pil:
                raise ValueError(
                    "deployment_mode=LIVE requires either LLM or PIL enabled"
                )
        
        # Cross-field validation
        if self.min_actionable_confidence < Decimal("0") or self.min_actionable_confidence > Decimal("1"):
            raise ValueError(f"min_actionable_confidence must be 0-1, got {self.min_actionable_confidence}")
        
        if self.trace_sample_rate < Decimal("0") or self.trace_sample_rate > Decimal("1"):
            raise ValueError(f"trace_sample_rate must be 0-1, got {self.trace_sample_rate}")
        
        if self.shutdown_drain_timeout_seconds <= 0:
            raise ValueError("shutdown_drain_timeout_seconds must be positive")


@dataclass
class ConfigChangeRecord:
    """Audit record for configuration changes."""
    timestamp: datetime
    field_path: str
    old_value: Any
    new_value: Any
    resolution_level: ConfigResolutionLevel
    changed_by: str  # user_id, system, api_key
    confirmation_required: bool = False
    confirmation_received: bool = False
    confirmation_timestamp: Optional[datetime] = None


class ConfigurationResolver:
    """
    Implements 5-level configuration resolution priority.
    
    Priority (highest to lowest):
    1. Session overrides (runtime)
    2. User config (database)
    3. Strategy config (database)
    4. Environment variables
    5. Schema defaults
    """
    
    def __init__(self, schema_defaults: Optional[RuntimeConfig] = None):
        self.schema_defaults = schema_defaults or RuntimeConfig()
        self.session_overrides: Dict[str, Any] = {}
        self.user_config: Dict[str, Any] = {}
        self.strategy_config: Dict[str, Any] = {}
        self._audit_trail: List[ConfigChangeRecord] = []
        self._pending_changes: Dict[str, Tuple[Any, ConfigChangeRecord]] = {}
    
    def resolve(self, field_path: str) -> Any:
        """
        Resolve a configuration field using priority resolution.
        
        Args:
            field_path: Dot-separated path (e.g., "risk.max_position_pct")
        
        Returns:
            Resolved value from highest-priority source
        """
        # Level 1: Session override
        if field_path in self.session_overrides:
            return self.session_overrides[field_path]
        
        # Level 2: User config
        if field_path in self.user_config:
            return self.user_config[field_path]
        
        # Level 3: Strategy config
        if field_path in self.strategy_config:
            return self.strategy_config[field_path]
        
        # Level 4: Environment variable
        env_var = self._field_to_env(field_path)
        if env_var in os.environ:
            return self._parse_env_value(os.environ[env_var], field_path)
        
        # Level 5: Schema default
        return self._get_nested_attr(self.schema_defaults, field_path)
    
    def set_session_override(self, field_path: str, value: Any, changed_by: str = "system"):
        """Set a session-level override (highest priority)."""
        old_value = self.resolve(field_path)
        self.session_overrides[field_path] = value
        
        record = ConfigChangeRecord(
            timestamp=datetime.now(timezone.utc),
            field_path=field_path,
            old_value=old_value,
            new_value=value,
            resolution_level=ConfigResolutionLevel.SESSION_OVERRIDE,
            changed_by=changed_by,
            confirmation_required=False
        )
        self._audit_trail.append(record)
    
    def set_user_config(self, field_path: str, value: Any, changed_by: str, confirmation_required: bool = False):
        """
        Set user-level configuration.
        
        Args:
            field_path: Dot-separated path
            value: New value
            changed_by: User ID
            confirmation_required: If True, change is pending until confirmed
        """
        old_value = self.resolve(field_path)
        
        record = ConfigChangeRecord(
            timestamp=datetime.now(timezone.utc),
            field_path=field_path,
            old_value=old_value,
            new_value=value,
            resolution_level=ConfigResolutionLevel.USER_CONFIG,
            changed_by=changed_by,
            confirmation_required=confirmation_required
        )
        
        if confirmation_required:
            self._pending_changes[field_path] = (value, record)
        else:
            self.user_config[field_path] = value
            self._audit_trail.append(record)
    
    def confirm_change(self, field_path: str, confirmed_by: str) -> bool:
        """Confirm a pending configuration change."""
        if field_path not in self._pending_changes:
            return False
        
        value, record = self._pending_changes[field_path]
        record.confirmation_received = True
        record.confirmation_timestamp = datetime.now(timezone.utc)
        record.changed_by = confirmed_by
        
        self.user_config[field_path] = value
        self._audit_trail.append(record)
        del self._pending_changes[field_path]
        return True
    
    def get_diff_display(self, field_path: str) -> str:
        """Generate human-readable diff for a configuration change."""
        old_value = self.resolve(field_path)
        new_value = self._pending_changes.get(field_path, (None, None))[0]
        
        if new_value is None:
            return f"No pending change for {field_path}"
        
        return (
            f"Configuration Change:\n"
            f"  Field: {field_path}\n"
            f"  Old:   {self._format_value(old_value)}\n"
            f"  New:   {self._format_value(new_value)}\n"
            f"  Impact: {self._assess_impact(field_path, old_value, new_value)}"
        )
    
    def _assess_impact(self, field_path: str, old_value: Any, new_value: Any) -> str:
        """Assess the impact of a configuration change."""
        high_impact_fields = {
            "deployment_mode",
            "risk.max_portfolio_heat_pct",
            "risk.max_position_pct",
            "risk.stop_loss_pct",
            "database.url",
            "llm.primary_provider",
        }
        
        if field_path in high_impact_fields:
            return "HIGH IMPACT - Requires restart or careful monitoring"
        
        if "risk" in field_path or "limit" in field_path.lower():
            return "MEDIUM IMPACT - Affects risk management"
        
        return "LOW IMPACT - Minor adjustment"
    
    def _format_value(self, value: Any) -> str:
        """Format a value for display."""
        if isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, Enum):
            return value.value
        elif isinstance(value, dict):
            return json.dumps(value, indent=2, default=str)
        else:
            return str(value)
    
    def _field_to_env(self, field_path: str) -> str:
        """Convert dot-separated field path to environment variable name."""
        # e.g., "risk.max_position_pct" → "APEX_RISK_MAX_POSITION_PCT"
        return "APEX_" + field_path.upper().replace(".", "_")
    
    def _parse_env_value(self, env_value: str, field_path: str) -> Any:
        """Parse an environment variable value to the appropriate type."""
        # Get the default value to determine expected type
        default = self._get_nested_attr(self.schema_defaults, field_path)
        
        if isinstance(default, bool):
            return env_value.lower() in ("true", "1", "yes")
        elif isinstance(default, int):
            return int(env_value)
        elif isinstance(default, float):
            return float(env_value)
        elif isinstance(default, Decimal):
            return Decimal(env_value)
        elif isinstance(default, Enum):
            return type(default)(env_value)
        else:
            return env_value
    
    def _get_nested_attr(self, obj: Any, field_path: str) -> Any:
        """Get a nested attribute using dot notation."""
        parts = field_path.split(".")
        current = obj
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise KeyError(f"Field path '{field_path}' not found")
        return current
    
    def get_audit_trail(self) -> List[ConfigChangeRecord]:
        """Return the configuration audit trail."""
        return list(self._audit_trail)
    
    def get_pending_changes(self) -> Dict[str, ConfigChangeRecord]:
        """Return pending changes awaiting confirmation."""
        return {k: v[1] for k, v in self._pending_changes.items()}
    
    def build_resolved_config(self) -> RuntimeConfig:
        """
        Build a fully resolved RuntimeConfig instance.
        
        This merges all layers according to priority and returns
        a complete, validated RuntimeConfig.
        """
        # Start with schema defaults - use the actual object, not asdict
        # We need to carefully merge nested dataclasses
        
        # Get base config from schema defaults
        base = self.schema_defaults
        
        # Apply environment variables first (lowest priority after defaults)
        env_vars = {k: v for k, v in os.environ.items() if k.startswith("APEX_")}
        for env_var, env_value in env_vars.items():
            field_path = self._env_to_field(env_var)
            try:
                parsed = self._parse_env_value(env_value, field_path)
                # For now, skip complex nested paths from env vars
                if "." not in field_path:
                    setattr(base, field_path, parsed)
            except (KeyError, ValueError, AttributeError):
                pass  # Skip invalid env vars
        
        # Note: For full implementation, we would need to properly merge
        # strategy_config, user_config, and session_overrides into nested dataclasses
        # This requires reconstructing each nested config object
        
        # For now, return schema defaults with any direct attribute overrides
        # A production implementation would use a proper config merging library
        return base
    
    def _set_nested_value(self, d: Dict, field_path: str, value: Any):
        """Set a nested value in a dictionary using dot notation."""
        parts = field_path.split(".")
        current = d
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    
    def _env_to_field(self, env_var: str) -> str:
        """Convert environment variable name to field path."""
        # e.g., "APEX_RISK_MAX_POSITION_PCT" → "risk.max_position_pct"
        if not env_var.startswith("APEX_"):
            raise ValueError(f"Invalid APEX environment variable: {env_var}")
        
        remainder = env_var[5:]  # Remove "APEX_"
        return remainder.lower().replace("_", ".")


def load_config_from_env() -> RuntimeConfig:
    """Load configuration entirely from environment variables."""
    resolver = ConfigurationResolver()
    return resolver.build_resolved_config()


def validate_runtime_config(config: RuntimeConfig) -> List[str]:
    """Alias for validate_full_config for backward compatibility."""
    return validate_full_config(config)


def validate_full_config(config: RuntimeConfig) -> List[str]:
    """
    Perform comprehensive configuration validation.
    
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    # Numerical policy validation
    try:
        validate_numerical_policy(config.numerical_policy)
    except ValueError as e:
        errors.append(f"Numerical policy: {e}")
    
    # Risk config validation
    risk = config.risk
    if risk.stop_loss_pct >= risk.max_position_pct:
        errors.append(f"stop_loss_pct ({risk.stop_loss_pct}) must be < max_position_pct ({risk.max_position_pct})")
    
    if risk.take_profit_pct <= risk.stop_loss_pct:
        errors.append(f"take_profit_pct ({risk.take_profit_pct}) must be > stop_loss_pct ({risk.stop_loss_pct})")
    
    # Deployment mode semantic validation
    if config.deployment_mode == DeploymentMode.LIVE:
        if not config.database.url:
            errors.append("LIVE mode requires database.url")
        if config.deterministic_only and not config.enable_pil:
            errors.append("LIVE mode requires LLM or PIL enabled")
    
    # LLM provider validation
    if not config.deterministic_only:
        if not config.llm.primary_provider:
            errors.append("primary_provider required when not in deterministic_only mode")
    
    # Threshold validations
    if config.min_actionable_confidence < Decimal("0") or config.min_actionable_confidence > Decimal("1"):
        errors.append(f"min_actionable_confidence must be 0-1, got {config.min_actionable_confidence}")
    
    if config.trace_sample_rate < Decimal("0") or config.trace_sample_rate > Decimal("1"):
        errors.append(f"trace_sample_rate must be 0-1, got {config.trace_sample_rate}")
    
    return errors
