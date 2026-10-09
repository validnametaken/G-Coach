# Phase 1: Unified Analysis Foundation Architecture

## Overview
Phase 1 establishes the internal architecture and data structures for independent writing-analysis engines to produce standardized findings, separating **Correction**, **Rewriting**, and **Coaching**.

## Components

### 1. Standardized Finding (`core/analysis/finding.py`)
`Finding` represents a detected writing issue or suggestion:
- **`id`**: Unique identifier (UUID4 string)
- **`source`**: Source engine name (e.g. `"harper"`, `"gector"`, `"no-ai-slop"`)
- **`category`**: Problem category (e.g. `"grammar"`, `"spelling"`, `"style"`)
- **`message`**: Human-readable explanation
- **`original`**: Original text snippet
- **`replacement`**: Suggested replacement text
- **`start` & `end`**: Precise text location range in the original text using **Python string character offsets** (0-indexed, half-open interval `[start, end)`).
- **`confidence`**: Float value from `0.0` to `1.0` representing engine confidence.
- **`severity`**: Classification level (`"error"`, `"warning"`, `"style"`).
- **`auto_fixable`**: Boolean indicating whether the finding can be automatically fixed.
- **`status`**: User decision state supporting future Writing Coach and history (`"detected"`, `"accepted"`, `"rejected"`, `"ignored"`).
- **`metadata`**: Flexible dictionary for engine-specific metadata.
- **Serialization**: Supports `.to_dict()` and `.from_dict(d)` for JSON-safe representation.

### 2. Analysis Engine Abstraction (`core/analysis/engine.py`)
`BaseAnalysisEngine` is an abstract base class for all analysis engines.
- Exposes metadata properties: `name`, `version`, `is_local`, `supported_types`, `supports_auto_fix`.
- Implements `analyze(text: str) -> List[Finding]`.
- Completely decoupled from PyQt UI, global hotkeys, clipboard handling, and API clients.

### 3. Analysis Pipeline / Coordinator (`core/analysis/pipeline.py`)
`AnalysisPipeline` coordinates multiple independent analysis engines.
- `register_engine(engine)` and `unregister_engine(name)`
- `analyze(text: str) -> List[Finding]` executes registered engines, handles engine failures gracefully without crashing the pipeline, and aggregates all findings.

## Future Integration
- **Harper**: Deterministic / local grammar checking.
- **GECToR**: Contextual / local grammar correction with confidence probabilities.
- **no-ai-slop**: Writing and style analysis.
- **Writing Coach & History**: Consumes standardized findings and user decision statuses (`status`).
