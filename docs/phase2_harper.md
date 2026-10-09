# Phase 2: Harper Local Analysis Engine Architecture & Integration

## Overview
Phase 2 integrates Harper (`harper.js` WASM package via Node.js local subprocess runner) as the first real local analysis engine implementing the Phase 1 `BaseAnalysisEngine` abstraction.

## Integration Method
- **Selected Mechanism**: Node.js subprocess executing a dedicated runner script (`core/analysis/harper_runner.js`) interacting with the local `harper.js` WASM library.
- **Why Chosen**: Harper is natively distributed as a Rust/WASM library (`harper.js` on npm). Invoking it locally via a Node subprocess is reliable, fully offline, self-contained within the workspace `node_modules/`, avoids heavy native compilation dependencies in Python, and executes with high performance.

## Harper Version & Dependencies
- **Harper Version**: `harper.js` v2.10.0 (WASM-based local grammar linter).
- **Runtime Required**: Node.js (already present in environment). Fully local and offline — no cloud APIs or paid services required.

## Conversion & Mapping
1. **Finding Model**: Harper diagnostics are converted into Phase 1 `Finding` instances.
2. **Character Ranges**: Precise 0-indexed character offsets (`start` and `end`, half-open interval `[start, end)`) provided by Harper are verified against original text (`text[start:end] == original`).
3. **Replacement Text**: Extracted from Harper suggestion objects (`get_replacement_text`).
4. **Auto-Fixable**: Set to `True` if concrete replacement suggestions exist (`len(replacements) > 0`).
5. **Confidence**: Set to `1.0` since Harper is a deterministic rule-based grammar linter.
6. **Category & Severity**: Mapped from Harper's `lint_kind_pretty` (e.g., `"Agreement"` → category `"agreement"`, severity `"error"`, or `"warning"`).
7. **Metadata**: Preserves raw JSON diagnostic data and full replacement lists.

## Error Handling & Pipeline Integration
- Harper engine failures, timeouts (10s), missing runner scripts, or malformed outputs are safely caught and logged, returning an empty list without crashing the `AnalysisPipeline`.
- Registered into `AnalysisPipeline` alongside existing architecture without modifying any UI, hotkey, or AI rewriting behavior.

## Performance Observations
- Short sentences (~20 chars): typically executes in < 300–500 ms (including Node startup).
- Longer paragraphs (~200 chars): executes efficiently within expected limits.
- Fully suitable for future live checking architecture (with debouncing).
