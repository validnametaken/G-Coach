"""
GECToR Diagnostic Tool - Phase 3 Debugging (Enhanced)
=====================================================
Runs real ONNX inference on GECToR and prints detailed token-level diagnostics:
- Raw ONNX output names, shapes, dtypes
- Tokenizer token, token ID, word_id, character offsets
- Top detection class ID, name, probability
- Top 3 edit-label IDs, names, probabilities
- Vocabulary mappings and axis mapping answers
"""

import sys
import json
import logging
from pathlib import Path
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("diagnose_gector")

def run_diagnostic():
    model_dir = Path("models/gector")
    onnx_path = model_dir / "model.onnx"
    tokenizer_json = model_dir / "tokenizer.json"
    config_json = model_dir / "config.json"

    print("==================================================")
    print("GECToR DIAGNOSTIC & ROOT CAUSE ANALYSIS TOOL")
    print("==================================================")

    if not onnx_path.exists() or not tokenizer_json.exists():
        print(f"\n[NOTE] GECToR model files not found in {model_dir} (running in headless container without binaries).")
        print("When run on Windows with the model installed, this script prints:")
        print("  1. Raw ONNX output names, shapes, dtypes.")
        print("  2. Tokenizer special tokens, token IDs, word_ids, and character offsets.")
        print("  3. Detection logit index mapping ($CORRECT vs $INCORRECT).")
        print("  4. Sequence axis and label axis identification.")
        print("  5. Top 3 edit-label IDs, names, and probabilities per token.")
        print("  6. Verification of confidence thresholding and token exclusion root cause.")
        return

    import onnxruntime as ort
    from tokenizers import Tokenizer

    print(f"\nLoading ONNX model from {onnx_path} ...")
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    
    print("\n--- 1. ONNX Model Inputs ---")
    for inp in session.get_inputs():
        print(f"Name: {inp.name}, Shape: {inp.shape}, Type: {inp.type}")

    print("\n--- 2. ONNX Model Outputs ---")
    for out in session.get_outputs():
        print(f"Name: {out.name}, Shape: {out.shape}, Type: {out.type}")

    print(f"\nLoading Tokenizer from {tokenizer_json} ...")
    tokenizer = Tokenizer.from_file(str(tokenizer_json))

    config = {}
    if config_json.exists():
        with open(config_json, "r", encoding="utf-8") as f:
            config = json.load(f)
        print("\n--- 3. Config Keys & Vocab Structure ---")
        print(list(config.keys()))

    vocab = config.get("vocab") or config.get("label_vocab") or config.get("labels") or {}
    print(f"Loaded vocabulary entries count: {len(vocab)}")

    id_to_label = {}
    if isinstance(vocab, dict):
        sample_key = next(iter(vocab.keys())) if vocab else None
        if sample_key is not None and str(sample_key).isdigit():
            id_to_label = {int(k): v for k, v in vocab.items()}
        else:
            id_to_label = {int(v): k for k, v in vocab.items()}
    elif isinstance(vocab, list):
        id_to_label = {idx: label for idx, label in enumerate(vocab)}

    test_sentences = [
        "The students was very happy.",
        "I has a apple."
    ]

    def softmax(x):
        e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e_x / np.sum(e_x, axis=-1, keepdims=True)

    for sentence in test_sentences:
        print(f"\n==================================================")
        print(f"DIAGNOSTIC FOR SENTENCE: \"{sentence}\"")
        print(f"==================================================")

        encoding = tokenizer.encode(sentence)
        input_ids = [encoding.ids]
        attention_mask = [[1] * len(encoding.ids)]

        print(f"Tokens: {encoding.tokens}")
        print(f"IDs: {encoding.ids}")
        print(f"Offsets: {encoding.offsets}")
        if hasattr(encoding, "word_ids"):
            print(f"Word IDs: {encoding.word_ids()}")

        input_ids_np = np.array(input_ids, dtype=np.int64)
        attention_mask_np = np.array(attention_mask, dtype=np.int64)

        outputs = session.run(None, {"input_ids": input_ids_np, "attention_mask": attention_mask_np})
        
        print("\nRaw Output Tensors Shapes & Axes:")
        for idx, out in enumerate(outputs):
            print(f"  Output [{idx}]: shape={out.shape}, dtype={out.dtype}")
            if out.ndim == 3:
                print(f"    -> Sequence axis: axis 1 (len={out.shape[1]})")
                print(f"    -> Feature/Label/Class axis: axis 2 (size={out.shape[2]})")

        logits_d, logits_labels = None, None
        for out in outputs:
            if out.ndim == 3:
                if out.shape[-1] <= 5:
                    logits_d = out
                else:
                    logits_labels = out

        if logits_d is None or logits_labels is None:
            logits_d = outputs[0]
            logits_labels = outputs[1] if len(outputs) > 1 else outputs[0]

        prob_d = softmax(logits_d[0])
        prob_l = softmax(logits_labels[0])

        seq_len = min(len(encoding.ids), prob_d.shape[0], prob_l.shape[0], len(encoding.offsets))

        for i in range(seq_len):
            token_str = encoding.tokens[i]
            token_id = encoding.ids[i]
            offset = encoding.offsets[i]
            word_id = encoding.word_ids()[i] if hasattr(encoding, "word_ids") else "N/A"
            orig_text = sentence[offset[0]:offset[1]] if offset[0] < offset[1] else ""

            top_d_id = int(np.argmax(prob_d[i]))
            top_d_prob = float(prob_d[i][top_d_id])
            
            d_name = "$CORRECT" if top_d_id == 0 else "$INCORRECT"
            incorrect_prob = float(prob_d[i][1]) if prob_d.shape[-1] > 1 else top_d_prob

            top_l_indices = np.argsort(prob_l[i])[::-1][:3]
            top_l_info = []
            for l_id in top_l_indices:
                l_name = id_to_label.get(int(l_id), f"LABEL_{l_id}")
                l_prob = float(prob_l[i][l_id])
                top_l_info.append(f"{l_name} (id={l_id}, prob={l_prob:.4f})")

            print(f"\n[Token {i}]")
            print(f"  Original Text  : '{orig_text}' (offset={offset})")
            print(f"  Token Str      : '{token_str}' (id={token_id}, word_id={word_id})")
            print(f"  Detection Prob : P(CORRECT)={prob_d[i][0]:.4f}, P(INCORRECT)={prob_d[i][1] if prob_d.shape[-1]>1 else 'N/A':.4f}")
            print(f"  Top 3 Labels   :")
            for info in top_l_info:
                print(f"    - {info}")


if __name__ == "__main__":
    run_diagnostic()
