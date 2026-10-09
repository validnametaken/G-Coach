# Phase 4: Analysis Resolution Layer Architecture & Integration

## Overview
Phase 4 introduces the **Analysis Resolution Layer** (`core/analysis/resolver.py`), which bridges multi-engine detection (Harper and GECToR) and future UI presentation/coaching by combining raw findings into a unified set of findings without losing essential provenance or information.

## Core Responsibilities & Architecture
```
Harper ────────┐
               │
               ▼
          Resolution
             Layer
               │
               ▼
        Unified Findings
               ▲
               │
GECToR ────────┘
```

1. **Detection vs. Resolution vs. Presentation**:
   - **Detection**: Handled by independent analysis engines (Harper, GECToR).
   - **Resolution**: Handled by `AnalysisResolver`, merging identical corrections and marking conflicts.
   - **Presentation**: Left for future UI / live monitoring phases.

2. **Resolution Rules**:
   - **Identical Findings**: Findings sharing the exact same range (`start`, `end`, `original`) and normalized replacement text are merged into a single finding. `metadata` tracks `sources` (e.g. `["harper", "gector"]`), `is_merged = True`, `has_conflict = False`, and preserves individual per-source confidences and IDs.
   - **Same Location, Different Corrections**: When engines propose conflicting replacements at the exact same location (e.g., Harper suggests `"goes"` vs. GECToR suggests `"went"`), no arbitrary winner is chosen. Both candidates are preserved and flagged with `has_conflict = True` along with a list of `conflicting_findings` in metadata.
   - **Non-Overlapping Findings**: Findings addressing different text locations are independently retained and sorted deterministically.
   - **Overlapping Findings**: Overlapping spans that are not equivalent are handled safely to preserve conflicts for the future UI.
   - **Determinism**: Sorting and resolution are strictly deterministic (sorted by `start`, length, and `source`), ensuring consistent output ordering.

## Real GECToR Benchmark Utility
- Implemented `tests/test_benchmark.py` to measure real GECToR model performance (model load time, first inference, subsequent inference, paragraph inference) when installed.
- Gracefully skips benchmark execution when model binaries are absent, avoiding false metrics.

## Scope Compliance
- **No UI changes**, **no live monitoring**, **no background workers**, **no database**, **no AI rewriting changes**, **no preference given to Harper over GECToR or vice versa**.
- Existing G-Coach behavior, hotkeys, and tests remain 100% intact.
