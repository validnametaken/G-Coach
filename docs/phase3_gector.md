# Phase 3: GECToR Local Analysis Engine Architecture & Integration (Complete)

## Overview
Phase 3 integrates GECToR (Contextual Grammatical Error Correction via ONNX Runtime and Tokenizers) as an independent local analysis engine implementing the Phase 1 `BaseAnalysisEngine` abstraction.

## Architecture & Real ONNX Inference
- **Inference Mechanism**: Python-based `GectorAnalysisEngine` using ONNX Runtime (`onnxruntime`) and HuggingFace `tokenizers` (`tokenizer.json`) for local inference and byte-level BPE token/word range alignment.
- **Model Distribution & Location**: Configurable via `model_dir` (defaulting to `models/gector/` or `GECTOR_MODEL_DIR`). Model files (`model.onnx`, `tokenizer.json`, `config.json`, `verb-form-vocab.txt`) are placed in local deployment storage or downloaded externally, with graceful fallback/simulation support when missing during unit testing.
- **Offline Capability**: Fully local and offline (`CPUExecutionProvider`). No cloud APIs required.

## Tokenization & Character Range Mapping
- Uses RoBERTa-based byte-level BPE tokenizer (`tokenizer.json`) with offset mappings (`encoding.offsets`).
- Maps BPE token pieces back to exact character spans `[start, end)`.
- Enforces strict validation: `text[start:end] == original`.

## Edit Operations & Iterative Passes
- Supports GECToR tag-based correction operations (`$KEEP`, `$DELETE`, `$APPEND_x`, `$REPLACE_x`, `$TRANSFORM_VERB_*`).
- Implements multi-pass iterative correction (configurable `max_passes`, default 5) with right-to-left offset-preserving application.

## Confidence & Thresholding
- **Confidence Calculation**: Derived from model output probabilities: `confidence = min(det_probability, lab_probability)`.
- **Thresholds**: Configurable detection (`det_threshold`, default 0.5) and label (`lab_threshold`, default 0.5) thresholds to suppress low-confidence predictions.

## Metadata & Severity
- Retains raw GECToR labels, detection probabilities, label probabilities, pass index, and action type in `Finding.metadata`.
- Standardizes category (`subject_verb_agreement`, `verb_form`, `article`, etc.) and severity (`error`).

## Pipeline & Pipeline Independence
- Integrated into `AnalysisPipeline` alongside Harper.
- Preserves absolute engine independence: no combined policy, deduplication, ranking, or overriding between Harper and GECToR. Both output independent findings.
- Existing G-Coach rewriting, hotkeys, clipboard handling, and PyQt UI remain completely unaffected.
