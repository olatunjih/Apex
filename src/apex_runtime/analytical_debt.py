"""
APEX Analytical Debt Dashboard & Thesis Lifecycle Management
Implements: Section 29 - Analytical Debt Dashboard, Section 78 - Component Health Scoring
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

try:
    from .core_models import ConfidenceLevel, TickerIntelligenceFile, EpistemicState
except ImportError:
    from core_models import ConfidenceLevel, TickerIntelligenceFile, EpistemicState


class DebtCategory(Enum):
    """Categories of analytical debt"""
    DATA_QUALITY = "data_quality"
    MODEL_UNCERTAINTY = "model_uncertainty"
    EPISTEMIC_GAP = "epistemic_gap"
    NARRATIVE_INCONSISTENCY = "narrative_inconsistency"
    GUARDRAIL_VIOLATION = "guardrail_violation"
    COMPONENT_DEGRADATION = "component_degradation"
    STALE_ANALYSIS = "stale_analysis"


@dataclass
class AnalyticalDebtItem:
    """A single item of analytical debt"""
    debt_id: str
    category: DebtCategory
    description: str
    severity: Decimal  # 0.0 to 1.0
    identified_at: datetime
    ticker: Optional[str]
    component: Optional[str]
    resolution_required_by: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    def age_days(self) -> int:
        return (datetime.now() - self.identified_at).days
    
    def is_overdue(self) -> bool:
        return datetime.now() > self.resolution_required_by and not self.resolved


@dataclass
class ComponentHealthScore:
    """Health score for a thesis component"""
    component_name: str
    current_score: Decimal  # 0.0 to 1.0
    trend: str  # improving, stable, declining
    last_updated: datetime
    degradation_rate: Decimal  # Rate of decline if negative
    factors: List[str] = field(default_factory=list)
    
    def is_healthy(self) -> bool:
        return self.current_score >= Decimal("0.7")
    
    def is_critical(self) -> bool:
        return self.current_score < Decimal("0.4")


@dataclass
class ThesisLifecycleEvent:
    """Event in the lifecycle of a thesis"""
    event_id: str
    timestamp: datetime
    event_type: str  # created, updated, strengthened, weakened, invalidated
    ticker: str
    previous_state: Optional[str]
    new_state: str
    trigger_reason: str
    component_health_snapshot: Dict[str, Decimal] = field(default_factory=dict)


class AnalyticalDebtDashboard:
    """
    Section 29 & 78: Analytical Debt Dashboard
    Tracks and manages technical and epistemic debt in analysis
    """
    
    def __init__(self):
        self.debt_items: Dict[str, AnalyticalDebtItem] = {}
        self.debt_counter = 0
        self.resolution_history: List[Dict[str, Any]] = []
        
    def add_debt_item(self, category: DebtCategory, description: str,
                     severity: Decimal, ticker: str = None,
                     component: str = None, 
                     resolution_days: int = 7) -> str:
        """Add a new analytical debt item"""
        self.debt_counter += 1
        debt_id = f"DEBT-{self.debt_counter:06d}"
        
        debt = AnalyticalDebtItem(
            debt_id=debt_id,
            category=category,
            description=description,
            severity=severity,
            identified_at=datetime.now(),
            ticker=ticker,
            component=component,
            resolution_required_by=datetime.now() + timedelta(days=resolution_days)
        )
        
        self.debt_items[debt_id] = debt
        return debt_id
    
    def resolve_debt(self, debt_id: str, notes: str = None):
        """Mark a debt item as resolved"""
        if debt_id in self.debt_items:
            debt = self.debt_items[debt_id]
            debt.resolved = True
            debt.resolved_at = datetime.now()
            debt.resolution_notes = notes
            
            self.resolution_history.append({
                "debt_id": debt_id,
                "resolved_at": debt.resolved_at.isoformat(),
                "age_days": debt.age_days(),
                "notes": notes
            })
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get comprehensive dashboard summary"""
        active_debts = [d for d in self.debt_items.values() if not d.resolved]
        overdue = [d for d in active_debts if d.is_overdue()]
        
        by_category = {}
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        
        for debt in active_debts:
            # By category
            cat = debt.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            
            # By severity
            if debt.severity >= Decimal("0.8"):
                by_severity["critical"] += 1
            elif debt.severity >= Decimal("0.6"):
                by_severity["high"] += 1
            elif debt.severity >= Decimal("0.4"):
                by_severity["medium"] += 1
            else:
                by_severity["low"] += 1
        
        total_severity = sum(d.severity for d in active_debts)
        avg_severity = total_severity / len(active_debts) if active_debts else Decimal("0")
        
        return {
            "total_active_debts": len(active_debts),
            "overdue_count": len(overdue),
            "by_category": by_category,
            "by_severity": by_severity,
            "average_severity": float(avg_severity),
            "oldest_debt_age_days": max((d.age_days() for d in active_debts), default=0),
            "total_debt_score": float(total_severity)
        }
    
    def get_high_priority_items(self, limit: int = 10) -> List[AnalyticalDebtItem]:
        """Get highest priority unresolved debt items"""
        active = [d for d in self.debt_items.values() if not d.resolved]
        # Sort by severity and overdue status
        active.sort(key=lambda d: (d.is_overdue(), float(d.severity), d.age_days()), reverse=True)
        return active[:limit]
    
    def get_ticker_specific_debts(self, ticker: str) -> List[AnalyticalDebtItem]:
        """Get all debt items for a specific ticker"""
        return [
            d for d in self.debt_items.values()
            if d.ticker == ticker and not d.resolved
        ]


class ThesisLifecycleManager:
    """
    Manages thesis lifecycle with component health monitoring
    Triggers invalidation when component health deteriorates
    """
    
    def __init__(self):
        self.lifecycle_events: List[ThesisLifecycleEvent] = []
        self.component_health: Dict[str, Dict[str, ComponentHealthScore]] = {}
        self.event_counter = 0
        self.invalidation_threshold = Decimal("0.4")  # Below this triggers invalidation
        
    def record_thesis_event(self, event_type: str, ticker: str,
                           previous_state: str, new_state: str,
                           trigger_reason: str,
                           component_health: Dict[str, Decimal] = None):
        """Record a thesis lifecycle event"""
        self.event_counter += 1
        
        event = ThesisLifecycleEvent(
            event_id=f"EVENT-{self.event_counter:06d}",
            timestamp=datetime.now(),
            event_type=event_type,
            ticker=ticker,
            previous_state=previous_state,
            new_state=new_state,
            trigger_reason=trigger_reason,
            component_health_snapshot=component_health or {}
        )
        
        self.lifecycle_events.append(event)
        
    def update_component_health(self, ticker: str, component_name: str,
                               score: Decimal, factors: List[str] = None):
        """Update health score for a thesis component"""
        if ticker not in self.component_health:
            self.component_health[ticker] = {}
            
        if component_name in self.component_health[ticker]:
            # Update existing
            existing = self.component_health[ticker][component_name]
            old_score = existing.current_score
            
            # Determine trend
            if score > old_score + Decimal("0.05"):
                trend = "improving"
            elif score < old_score - Decimal("0.05"):
                trend = "declining"
            else:
                trend = "stable"
                
            # Calculate degradation rate
            time_delta = (datetime.now() - existing.last_updated).total_seconds() / 3600  # hours
            if time_delta > 0 and score < old_score:
                degradation_rate = (old_score - score) / Decimal(str(time_delta))
            else:
                degradation_rate = Decimal("0")
                
            self.component_health[ticker][component_name] = ComponentHealthScore(
                component_name=component_name,
                current_score=score,
                trend=trend,
                last_updated=datetime.now(),
                degradation_rate=degradation_rate,
                factors=factors or []
            )
        else:
            # New component
            self.component_health[ticker][component_name] = ComponentHealthScore(
                component_name=component_name,
                current_score=score,
                trend="stable",
                last_updated=datetime.now(),
                degradation_rate=Decimal("0"),
                factors=factors or []
            )
    
    def check_invalidation_triggers(self, ticker: str, 
                                   tif: TickerIntelligenceFile) -> Optional[Dict[str, Any]]:
        """
        Check if any component health thresholds trigger thesis invalidation
        Returns invalidation recommendation if triggered
        """
        if ticker not in self.component_health:
            return None
            
        critical_components = []
        for comp_name, health in self.component_health[ticker].items():
            if health.is_critical():
                critical_components.append({
                    "name": comp_name,
                    "score": float(health.current_score),
                    "trend": health.trend
                })
        
        if critical_components:
            avg_health = tif.get_average_component_health()
            
            if avg_health < self.invalidation_threshold:
                return {
                    "invalidate": True,
                    "reason": f"Component health below threshold: {len(critical_components)} critical",
                    "critical_components": critical_components,
                    "average_health": float(avg_health),
                    "recommended_action": "Initiate thesis review and potential invalidation"
                }
                
        return None
    
    def get_component_health_dashboard(self, ticker: str) -> Dict[str, Any]:
        """Get health dashboard for a ticker's components"""
        if ticker not in self.component_health:
            return {"error": "No component health data for ticker"}
            
        components = self.component_health[ticker]
        
        healthy = [c for c in components.values() if c.is_healthy()]
        critical = [c for c in components.values() if c.is_critical()]
        declining = [c for c in components.values() if c.trend == "declining"]
        
        return {
            "ticker": ticker,
            "total_components": len(components),
            "healthy_count": len(healthy),
            "critical_count": len(critical),
            "declining_count": len(declining),
            "components": {
                name: {
                    "score": float(comp.current_score),
                    "trend": comp.trend,
                    "is_healthy": comp.is_healthy(),
                    "is_critical": comp.is_critical()
                }
                for name, comp in components.items()
            },
            "overall_health": float(sum(c.current_score for c in components.values()) / len(components)) if components else 0
        }
    
    def get_lifecycle_history(self, ticker: str) -> List[ThesisLifecycleEvent]:
        """Get full lifecycle history for a ticker"""
        return [e for e in self.lifecycle_events if e.ticker == ticker]
