#!/usr/bin/env python3
"""
APEX v3 Gap Analysis: Build Plan + Instruction Set vs. Actual Implementation
"""

import os
import re
from pathlib import Path

WORKSPACE = Path("/workspace")
INSTRUCTION_SET = WORKSPACE / "APEX_v3_INSTRUCTION_SET.md"
BUILD_PLAN = WORKSPACE / "APEX_BUILD_PLAN.md"
BUILD_PROGRESS = WORKSPACE / "BUILD_PROGRESS.md"
RUNTIME_DIR = WORKSPACE / "apex_runtime"

def get_sections():
    sections = {}
    with open(INSTRUCTION_SET) as f:
        content = f.read()
    
    pattern = r'^## SECTION (\d+): (.+)$'
    for match in re.finditer(pattern, content, re.MULTILINE):
        num, title = match.groups()
        sections[int(num)] = {'title': title, 'line': match.start()}
    return sections

def map_files_to_sections():
    mapping = {}
    
    for py_file in RUNTIME_DIR.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        rel_path = py_file.relative_to(WORKSPACE)
        content = py_file.read_text()
        file_classes = set(re.findall(r'class\s+(\w+)', content))
        
        # Mapping logic
        if 'MemoryGuard' in file_classes or 'memory_guard' in py_file.name:
            mapping.setdefault(1, []).append(str(rel_path))
        if 'RuntimeConfig' in file_classes or 'config' in py_file.name:
            mapping.setdefault(2, []).append(str(rel_path))
        if 'Strategy' in str(file_classes) or 'strategy' in py_file.name:
            mapping.setdefault(3, []).append(str(rel_path))
        if 'Tool' in str(file_classes) or 'tools' in py_file.name:
            mapping.setdefault(4, []).append(str(rel_path))
        if 'DataRegistry' in file_classes or ('core' in py_file.name and 'tools' in str(py_file)):
            mapping.setdefault(5, []).append(str(rel_path))
        if 'Cognitive' in str(file_classes) or 'cognitive' in py_file.name:
            mapping.setdefault(6, []).append(str(rel_path))
        if 'RegimeIntelligence' in file_classes or 'OpportunityScout' in file_classes or 'proactive' in py_file.name:
            mapping.setdefault(7, []).append(str(rel_path))
        if 'Pipeline' in str(file_classes) or 'Execution' in str(file_classes):
            mapping.setdefault(8, []).append(str(rel_path))
        if 'WhyEngine' in file_classes or 'why' in py_file.name:
            mapping.setdefault(9, []).append(str(rel_path))
        if 'Reflection' in str(file_classes) or 'reflection' in py_file.name:
            mapping.setdefault(11, []).append(str(rel_path))
        if 'EpistemicState' in file_classes or 'TickerIntelligence' in file_classes or 'core_models' in py_file.name:
            mapping.setdefault(15, []).append(str(rel_path))
        if 'LearningEngine' in file_classes or 'proactive_intelligence' in py_file.name:
            mapping.setdefault(19, []).append(str(rel_path))
        if 'KnowledgeApplication' in str(file_classes):
            mapping.setdefault(20, []).append(str(rel_path))
        if 'HumanFeedback' in str(file_classes) or 'ExpertIntelligence' in str(file_classes) or 'ethical' in py_file.name:
            mapping.setdefault(21, []).append(str(rel_path))
        if 'SecondOrder' in str(file_classes) or 'second_order' in py_file.name:
            mapping.setdefault(24, []).append(str(rel_path))
        if 'NarrativeAgent' in str(file_classes) or 'narrative' in py_file.name.lower():
            mapping.setdefault(25, []).append(str(rel_path))
        if 'AnalyticalDebt' in str(file_classes) or 'analytical_debt' in py_file.name:
            mapping.setdefault(29, []).append(str(rel_path))
        if 'RiskConfig' in file_classes or 'config' in py_file.name and 'risk' in content.lower():
            mapping.setdefault(30, []).append(str(rel_path))
        if 'Observability' in str(file_classes) or 'observability' in py_file.name or 'StructuredLogger' in file_classes:
            mapping.setdefault(32, []).append(str(rel_path))
        if 'EthicalFramework' in str(file_classes) or 'axiom' in py_file.name.lower():
            mapping.setdefault(35, []).append(str(rel_path))
        if 'Canvas' in str(file_classes) or 'canvas' in py_file.name:
            mapping.setdefault(38, []).append(str(rel_path))
        if 'WarRoom' in str(file_classes) or 'war_room' in py_file.name:
            mapping.setdefault(41, []).append(str(rel_path))
        if 'test_' in py_file.name:
            mapping.setdefault(66, []).append(str(rel_path))
        if 'HealthCheck' in file_classes or 'health' in py_file.name:
            mapping.setdefault(1, []).append(str(rel_path))
        if 'SignalHandler' in file_classes or 'signal_handler' in py_file.name:
            mapping.setdefault(1, []).append(str(rel_path))
        if 'LLMOrchestrator' in file_classes or 'llm' in py_file.name.lower():
            mapping.setdefault(32, []).append(str(rel_path))
        if 'ContinuousLearning' in file_classes or 'continuous_learning' in py_file.name:
            mapping.setdefault(26, []).append(str(rel_path))
        if 'SelfHealing' in file_classes or 'self_healing' in py_file.name:
            mapping.setdefault(28, []).append(str(rel_path))
        # UI layer
        if 'jsonl_protocol' in py_file.name or 'PanelBinding' in file_classes or 'core_integration' in py_file.name:
            mapping.setdefault(38, []).append(str(rel_path))
    
    return mapping

def analyze_build_progress():
    with open(BUILD_PROGRESS) as f:
        content = f.read()
    
    claims = {'complete': [], 'partial': [], 'missing': []}
    
    for line in content.split('\n'):
        if '✅' in line or '— ✅ Built' in line:
            claims['complete'].append(line.strip())
        elif '🟡' in line or 'Partial' in line:
            claims['partial'].append(line.strip())
        elif '❌' in line or 'Missing' in line:
            claims['missing'].append(line.strip())
    
    return claims

def main():
    sections = get_sections()
    file_mapping = map_files_to_sections()
    build_claims = analyze_build_progress()
    
    print("=" * 80)
    print("APEX v3 GAP ANALYSIS: Build Plan + Instruction Set vs. Implementation")
    print("=" * 80)
    print()
    
    total_sections = len(sections)
    sections_with_files = len(set(file_mapping.keys()))
    
    print(f"Total Specification Sections: {total_sections}")
    print(f"Sections with Some Implementation: {sections_with_files}")
    print(f"Sections with No Implementation: {total_sections - sections_with_files}")
    print(f"Completion Rate: {sections_with_files/total_sections*100:.1f}%")
    print()
    
    # Count files
    total_py_files = len(list(RUNTIME_DIR.rglob("*.py"))) - len(list((RUNTIME_DIR / "__pycache__").glob("*.py"))) if (RUNTIME_DIR / "__pycache__").exists() else len(list(RUNTIME_DIR.rglob("*.py")))
    total_loc = sum(len(open(f).readlines()) for f in RUNTIME_DIR.rglob("*.py") if "__pycache__" not in str(f))
    
    print(f"Total Python Files: {total_py_files}")
    print(f"Total Lines of Code: ~{total_loc:,}")
    print()
    
    print("-" * 80)
    print("IMPLEMENTED SECTIONS (with files)")
    print("-" * 80)
    
    for sec_num in sorted(file_mapping.keys()):
        files = file_mapping[sec_num]
        sec = sections.get(sec_num, {'title': 'Unknown'})
        status = "✅" if len(files) >= 2 else "🟡"
        print(f"\n{status} §{sec_num:2d}: {sec['title'][:55]}")
        for f in files:
            print(f"           → {f}")
    
    print("\n" + "=" * 80)
    print("CRITICAL GAPS - HIGH PRIORITY MISSING COMPONENTS")
    print("=" * 80)
    
    critical_gaps = [
        (5, "Data Registry - TTL, namespace isolation, memory bounds"),
        (7, "Proactive Intelligence - RegimeIntelligence, OpportunityScout, RiskSentinel"),
        (8, "Execution Pipelines - Compiled workflows"),
        (12, "Decision Contract - Formal decision documentation"),
        (26, "Evolution Engine - Self-improvement mechanisms"),
        (27, "Curiosity Engine - Active learning triggers"),
        (30, "Financial Risk Architecture - Position limits, VaR/CVaR, heat calculations"),
        (32, "Observability Stack - Prometheus metrics, OpenTelemetry traces"),
        (37, "API Catalog - REST/GraphQL endpoints"),
        (39, "Deployment Operations - Kubernetes, systemd integration"),
        (40, "Paper Trading & Simulation"),
        (56, "Hard/Soft Signal Architecture"),
        (66, "Testing Architecture - Comprehensive test suite (need 60%+ coverage)"),
    ]
    
    for sec_num, desc in critical_gaps:
        files = file_mapping.get(sec_num, [])
        if not files:
            print(f"\n❌ §{sec_num:2d}: {desc}")
        elif len(files) < 2:
            print(f"\n🟡 §{sec_num:2d} (PARTIAL): {desc}")
            print(f"            Current: {', '.join(files)}")
    
    print("\n" + "=" * 80)
    print("BUILD PROGRESS REPORT CLAIMS")
    print("=" * 80)
    print(f"\nClaimed Complete: {len(build_claims['complete'])} items")
    print(f"Claimed Partial: {len(build_claims['partial'])} items")
    print(f"Claimed Missing: {len(build_claims['missing'])} items")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS - PRIORITIZED ACTION ITEMS")
    print("=" * 80)
    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│ PRIORITY 1 (FOUNDATION - BLOCKS FURTHER DEVELOPMENT)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. §5  Data Registry with proper TTL, memory limits, namespace isolation    │
│ 2. §30 Financial Risk Architecture (position limits enforcement, heat calc) │
│ 3. §66 Testing Architecture (need 60%+ coverage, currently ~4%)             │
│ 4. FIX: Consolidate duplicate tool systems (tools.py vs tools/core.py)      │
│ 5. FIX: Consolidate duplicate health/signal systems                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PRIORITY 2 (CORE INTELLIGENCE - APEX DIFFERENTIATORS)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ 6. §7  Complete Proactive Intelligence Layer components                     │
│ 7. §8  Execution Pipelines with compiled workflows                          │
│ 8. §26 Evolution Engine for self-improvement                                │
│ 9. §12 Decision Contract formalization                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PRIORITY 3 (PRODUCTION READINESS)                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 10. §32 Full Observability Stack (Prometheus, OpenTelemetry exporters)      │
│ 11. §37 API Catalog (REST server, not just health endpoints)                │
│ 12. §39 Deployment Operations (K8s manifests, systemd units)                │
│ 13. §40 Paper Trading & Replay Mode for validation                          │
│ 14. FIX: Complete 7-phase shutdown sequence                                 │
│ 15. FIX: Add requirements.txt / pyproject.toml                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ PRIORITY 4 (ADVANCED FEATURES)                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ 16. §56 Hard/Soft Signal Architecture                                       │
│ 17. §27 Curiosity Engine                                                    │
│ 18. §44-54 Market Microstructure, Indicators, Options Flow expansion        │
│ 19. §58-60 Position Confirmation, Signal Disposition, Attribution           │
└─────────────────────────────────────────────────────────────────────────────┘
""")
    
    print("\n" + "=" * 80)
    print("CODE QUALITY ISSUES REQUIRING IMMEDIATE ATTENTION")
    print("=" * 80)
    print("""
1. ❌ cognitive.py: Missing import `from .errors import validation_error`
   → Will raise NameError at runtime
   
2. ❌ Strategy Aggregation Math Bug:
   `long_weight = sum(float(s.confidence) * len(long_signals) for s in long_signals)`
   → Multiplies by count twice; should be `* 1` not `* len(long_signals)`
   
3. ❌ Duplicate Tool Systems:
   - apex_runtime/tools.py (ToolRegistry, BaseTool, 4 standard tools)
   - apex_runtime/tools/core.py (DataRegistry, FetchMarketDataTool, etc.)
   - __init__.py imports from both, causing potential ImportError
   
4. ❌ Duplicate Health/Signal Systems:
   - health.py vs health_signals.py
   - signal_handler.py vs health_signals.py
   
5. ❌ Outbox Retry Logic Flaw:
   - Successful events vanish after drain_outbox() (not persisted)
   - For "exactly-once" system, needs acknowledgment/durability
   
6. ❌ __pycache__ directories committed to git
   - Bloats repo, causes cross-environment contamination
   - .gitignore exists but was added after files were committed
""")

if __name__ == "__main__":
    main()
