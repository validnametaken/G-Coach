"""
G-Coach Real GECToR Diagnostic Tool (Multi-Test Suite)
=====================================================
Standalone diagnostic script for testing 8 distinct test cases against the GECToR engine
(real ONNX model or simulation fallback) and reporting tokens, offsets, findings, and comparison table.
"""

import sys
import json
import os
from pathlib import Path

# 将项目根目录加入 sys.path，支持通过 python tools/diagnose_real_gector.py 从根目录直接运行
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.analysis.gector import GectorAnalysisEngine
from core.analysis.harper import HarperAnalysisEngine


TEST_CASES = [
    ("Test 1 — Original", "The students were very happy. are you doing today on this super duper nice day?"),
    ("Test 2 — Capitalized 'Are'", "The students were very happy. Are you doing today on this super duper nice day?"),
    ("Test 3 — Shorter lowercase question", "The students were very happy. are you doing today?"),
    ("Test 4 — Shorter capitalized question", "The students were very happy. Are you doing today?"),
    ("Test 5 — Explicit 'What'", "The students were very happy. What are you doing today?"),
    ("Test 6 — No sentence boundary", "The students were very happy and are you doing today?"),
    ("Test 7 — Normal second sentence", "The students were very happy. They are doing their work today."),
    ("Test 8 — Question without preceding sentence", "Are you doing today?"),
]


def run_diagnostic():
    print("=== ENVIRONMENT ===")
    print(f"Python Version: {sys.version}")
    print(f"Current Working Directory: {os.getcwd()}")

    engine = GectorAnalysisEngine()
    print("\n=== MODEL AVAILABILITY ===")
    print(f"Model Directory: {engine.model_dir}")
    onnx_path = engine.model_dir / "model.onnx"
    tokenizer_json = engine.model_dir / "tokenizer.json"
    config_json = engine.model_dir / "config.json"
    
    print(f"model.onnx exists: {onnx_path.exists()}")
    print(f"tokenizer.json exists: {tokenizer_json.exists()}")
    print(f"config.json exists: {config_json.exists()}")

    is_loaded = engine._load_model()
    print("\n=== GECToR MODE ===")
    if is_loaded and engine._model is not None:
        print("Execution Mode: REAL ONNX MODEL")
    else:
        print("Execution Mode: SIMULATION FALLBACK (Real ONNX model binaries not found)")
        print("\n[NOTE] To run this diagnostic with the real model, ensure the 513MB ONNX model files are placed in models/gector/ on Windows.")

    summary_results = []

    for label, text in TEST_CASES:
        print(f"\n==================================================")
        print(f"{label}")
        print(f"==================================================")
        print(f"Input Text: {repr(text)}")
        print(f"Length: {len(text)}")

        # Tokens & Offsets
        tokens, offsets = [], []
        if is_loaded and engine._tokenizer is not None:
            encoding = engine._tokenizer.encode(text)
            tokens = encoding.tokens
            offsets = encoding.offsets
            print(f"Tokens: {tokens}")
            print(f"Offsets: {offsets}")
        else:
            print("Tokens/Offsets: [Tokenizer unavailable in simulation mode]")

        # GECToR Findings
        gector_findings = engine.analyze(text)
        print(f"GECToR Findings Count: {len(gector_findings)}")
        has_dot_what = False
        has_append_what = False
        other_findings_summary = []

        for f in gector_findings:
            print(f"  - Source: {f.source}")
            print(f"    Category: {f.category}")
            print(f"    Original: {repr(f.original)}")
            print(f"    Replacement: {repr(f.replacement)}")
            print(f"    Start: {f.start}, End: {f.end}")
            print(f"    Slice check text[start:end]: {repr(text[f.start:f.end])}")
            print(f"    Message: {f.message}")
            print(f"    Confidence: {f.confidence}")
            print(f"    Severity: {f.severity}")
            print(f"    Auto Fixable: {f.auto_fixable}")
            print(f"    Metadata: {f.metadata}")
            
            meta = f.metadata or {}
            g_label = meta.get("gector_label", "")
            print(f"    gector_label: {g_label}")
            print(f"    det_probability: {meta.get('det_probability')}")
            print(f"    lab_probability: {meta.get('lab_probability')}")
            print(f"    pass_index: {meta.get('pass_index')}")
            print(f"    action_type: {meta.get('action_type')}")

            if f.original == "." and "What" in f.replacement:
                has_dot_what = True
            if "What" in g_label or "$APPEND_What" in g_label:
                has_append_what = True
            
            other_findings_summary.append(f"{repr(f.original)} -> {repr(f.replacement)} ({f.category})")

        summary_results.append({
            "test": label,
            "dot_what": "YES" if has_dot_what else "NO",
            "append_what": "YES" if has_append_what else "NO",
            "other": "; ".join(other_findings_summary) if other_findings_summary else "None"
        })

    print(f"\n==================================================")
    print("=== SUMMARY COMPARISON TABLE ===")
    print(f"==================================================")
    print(f"{'Test':<35} | {'GECToR \". -> .What\"?':<20} | {'$APPEND_What?':<15} | {'Other GECToR findings':<30}")
    print("-" * 110)
    for row in summary_results:
        print(f"{row['test']:<35} | {row['dot_what']:<20} | {row['append_what']:<15} | {row['other']:<30}")


if __name__ == "__main__":
    run_diagnostic()
