"""
APEX Ethical Framework & Human Feedback Integration
Implements: Section 21 - Human Feedback, Section 35 - 8 Ethical Axioms
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class AxiomViolationSeverity(Enum):
    """Severity levels for axiom violations"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKING = "blocking"


@dataclass
class EthicalAxiom:
    """One of the 8 core ethical axioms"""
    axiom_id: int
    name: str
    description: str
    evaluation_function: Optional[str] = None  # Name of eval function
    

@dataclass
class AxiomEvaluationResult:
    """Result of evaluating an axiom"""
    axiom_id: int
    passed: bool
    severity: AxiomViolationSeverity
    details: str
    timestamp: datetime
    context_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HumanFeedback:
    """Human feedback on APEX decisions/analysis"""
    feedback_id: str
    timestamp: datetime
    feedback_type: str  # correction, endorsement, warning, suggestion
    target_decision_id: Optional[str]
    target_analysis_id: Optional[str]
    content: str
    source: str  # user_id or expert_id
    expertise_level: str  # novice, intermediate, expert, domain_expert
    incorporated: bool = False
    incorporation_notes: Optional[str] = None


@dataclass
class ExpertIntelligence:
    """Domain expert knowledge injection"""
    expert_id: str
    domain: str
    credentials: str
    knowledge_injection: Dict[str, Any]
    confidence_weight: Decimal  # How much to weight this expert's input
    validated: bool = False
    validation_date: Optional[datetime] = None


class EthicalFramework:
    """
    Section 35: 8 Ethical Axioms
    Core ethical constraints that govern all APEX operations
    """
    
    def __init__(self):
        self.axioms = self._initialize_axioms()
        self.evaluation_history: List[AxiomEvaluationResult] = []
        self.violation_count = 0
        
    def _initialize_axioms(self) -> List[EthicalAxiom]:
        """Initialize the 8 core ethical axioms"""
        return [
            EthicalAxiom(1, "Beneficence", 
                "APEX must act in the best interest of users and stakeholders"),
            EthicalAxiom(2, "Non-Maleficence",
                "APEX must not cause harm through actions or recommendations"),
            EthicalAxiom(3, "Autonomy",
                "APEX must respect human autonomy and decision-making authority"),
            EthicalAxiom(4, "Justice",
                "APEX must treat all users fairly without discrimination"),
            EthicalAxiom(5, "Transparency",
                "APEX must be transparent about its reasoning and limitations"),
            EthicalAxiom(6, "Privacy",
                "APEX must protect user privacy and confidential information"),
            EthicalAxiom(7, "Accountability",
                "APEX must maintain audit trails and accept responsibility"),
            EthicalAxiom(8, "Fidelity",
                "APEX must remain faithful to its stated purpose and commitments")
        ]
    
    def evaluate_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> List[AxiomEvaluationResult]:
        """Evaluate a proposed action against all 8 axioms"""
        results = []
        
        for axiom in self.axioms:
            result = self._evaluate_axiom(axiom, action, context)
            results.append(result)
            self.evaluation_history.append(result)
            
            if not result.passed:
                self.violation_count += 1
                
        return results
    
    def _evaluate_axiom(self, axiom: EthicalAxiom, action: Dict, 
                       context: Dict) -> AxiomEvaluationResult:
        """Evaluate a single axiom"""
        passed = True
        severity = AxiomViolationSeverity.INFO
        details = f"{axiom.name}: No violation detected"
        
        # Axiom-specific evaluations
        if axiom.axiom_id == 1:  # Beneficence
            if action.get("intent") == "harmful":
                passed = False
                severity = AxiomViolationSeverity.BLOCKING
                details = "Action violates beneficence - harmful intent detected"
                
        elif axiom.axiom_id == 2:  # Non-Maleficence
            if action.get("potential_harm", Decimal("0")) > Decimal("0.5"):
                passed = False
                severity = AxiomViolationSeverity.CRITICAL
                details = "Action may cause significant harm"
                
        elif axiom.axiom_id == 3:  # Autonomy
            if action.get("overrides_human", False):
                passed = False
                severity = AxiomViolationSeverity.BLOCKING
                details = "Action overrides human decision-making without authorization"
                
        elif axiom.axiom_id == 4:  # Justice
            if context.get("discriminatory_impact", False):
                passed = False
                severity = AxiomViolationSeverity.CRITICAL
                details = "Action has discriminatory impact"
                
        elif axiom.axiom_id == 5:  # Transparency
            if not action.get("reasoning_explained", True):
                passed = False
                severity = AxiomViolationSeverity.WARNING
                details = "Action lacks transparent reasoning"
                
        elif axiom.axiom_id == 6:  # Privacy
            if action.get("accesses_private_data", False) and not action.get("privacy_safeguards", False):
                passed = False
                severity = AxiomViolationSeverity.CRITICAL
                details = "Action accesses private data without safeguards"
                
        elif axiom.axiom_id == 7:  # Accountability
            if "audit_trail" not in context:
                passed = False
                severity = AxiomViolationSeverity.WARNING
                details = "No audit trail present for action"
                
        elif axiom.axiom_id == 8:  # Fidelity
            if action.get("deviates_from_purpose", False):
                passed = False
                severity = AxiomViolationSeverity.CRITICAL
                details = "Action deviates from APEX's stated purpose"
        
        return AxiomEvaluationResult(
            axiom_id=axiom.axiom_id,
            passed=passed,
            severity=severity,
            details=details,
            timestamp=datetime.now(),
            context_snapshot=context.copy()
        )
    
    def get_violation_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get summary of axiom violations"""
        filtered = self.evaluation_history
        if since:
            filtered = [e for e in filtered if e.timestamp >= since]
            
        violations = [e for e in filtered if not e.passed]
        
        return {
            "total_evaluations": len(filtered),
            "total_violations": len(violations),
            "violations_by_axiom": self._group_by_axiom(violations),
            "violations_by_severity": self._group_by_severity(violations)
        }
    
    def _group_by_axiom(self, violations: List[AxiomEvaluationResult]) -> Dict[int, int]:
        result = {}
        for v in violations:
            result[v.axiom_id] = result.get(v.axiom_id, 0) + 1
        return result
    
    def _group_by_severity(self, violations: List[AxiomEvaluationResult]) -> Dict[str, int]:
        result = {}
        for v in violations:
            key = v.severity.value
            result[key] = result.get(key, 0) + 1
        return result


class HumanFeedbackEngine:
    """
    Section 21: Human Feedback & Expert Intelligence
    Incorporates human feedback and expert knowledge into APEX
    """
    
    def __init__(self):
        self.feedback_log: List[HumanFeedback] = []
        self.expert_knowledge_base: Dict[str, ExpertIntelligence] = {}
        self.feedback_counter = 0
        
    def submit_feedback(self, feedback_type: str, content: str, source: str,
                       expertise_level: str = "intermediate",
                       target_decision_id: str = None,
                       target_analysis_id: str = None) -> str:
        """Submit human feedback"""
        self.feedback_counter += 1
        feedback = HumanFeedback(
            feedback_id=f"FB-{self.feedback_counter:06d}",
            timestamp=datetime.now(),
            feedback_type=feedback_type,
            target_decision_id=target_decision_id,
            target_analysis_id=target_analysis_id,
            content=content,
            source=source,
            expertise_level=expertise_level
        )
        self.feedback_log.append(feedback)
        return feedback.feedback_id
    
    def incorporate_feedback(self, feedback_id: str, notes: str = None):
        """Mark feedback as incorporated"""
        for fb in self.feedback_log:
            if fb.feedback_id == feedback_id:
                fb.incorporated = True
                fb.incorporation_notes = notes
                break
    
    def register_expert(self, expert_id: str, domain: str, credentials: str,
                       knowledge: Dict[str, Any], 
                       confidence_weight: Decimal = Decimal("0.8")) -> ExpertIntelligence:
        """Register domain expert knowledge"""
        expert = ExpertIntelligence(
            expert_id=expert_id,
            domain=domain,
            credentials=credentials,
            knowledge_injection=knowledge,
            confidence_weight=confidence_weight
        )
        self.expert_knowledge_base[expert_id] = expert
        return expert
    
    def validate_expert(self, expert_id: str):
        """Validate an expert's credentials"""
        if expert_id in self.expert_knowledge_base:
            self.expert_knowledge_base[expert_id].validated = True
            self.expert_knowledge_base[expert_id].validation_date = datetime.now()
    
    def get_expert_weighted_knowledge(self, domain: str) -> List[Dict[str, Any]]:
        """Get expert knowledge for a domain, weighted by confidence"""
        relevant = [
            exp for exp in self.expert_knowledge_base.values()
            if exp.domain == domain and exp.validated
        ]
        
        # Sort by confidence weight
        relevant.sort(key=lambda e: float(e.confidence_weight), reverse=True)
        
        return [
            {
                "expert_id": exp.expert_id,
                "knowledge": exp.knowledge_injection,
                "weight": float(exp.confidence_weight)
            }
            for exp in relevant
        ]
    
    def get_feedback_statistics(self) -> Dict[str, Any]:
        """Get statistics on human feedback"""
        by_type = {}
        by_expertise = {}
        incorporated_count = 0
        
        for fb in self.feedback_log:
            by_type[fb.feedback_type] = by_type.get(fb.feedback_type, 0) + 1
            by_expertise[fb.expertise_level] = by_expertise.get(fb.expertise_level, 0) + 1
            if fb.incorporated:
                incorporated_count += 1
                
        return {
            "total_feedback": len(self.feedback_log),
            "by_type": by_type,
            "by_expertise_level": by_expertise,
            "incorporated_count": incorporated_count,
            "incorporation_rate": incorporated_count / len(self.feedback_log) if self.feedback_log else 0
        }
