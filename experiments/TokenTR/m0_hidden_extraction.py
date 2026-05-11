"""
M0: Hidden-State Extraction Pipeline for TokenTR
================================================
Token-level internal transition residual hallucination detection.

Extracts hidden states at target layers for Qwen2.5-7B from LongFact dataset.
Enforces DATA_REQUIREMENTS.md label protocol.

Usage:
    python experiments/TokenTR/m0_hidden_extraction.py --max_samples 200 --seed 42
    python experiments/TokenTR/m0_hidden_extraction.py --dataset_path /path/to/local/data.jsonl --label_mode token

Outputs:
    experiments/TokenTR/data/hidden_states/{model}_layer{NN}.npy
    experiments/TokenTR/data/splits/longfact_metadata.json
    experiments/TokenTR/data/splits/longfact_split.json
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ── Project paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "experiments" / "TokenTR" / "data"
HIDDEN_DIR = OUTPUT_DIR / "hidden_states"
SPLIT_DIR = OUTPUT_DIR / "splits"
METADATA_PATH = SPLIT_DIR / "longfact_metadata.json"

# ── Model config ─────────────────────────────────────────────────────────────
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_NAME_7B = "Qwen/Qwen2.5-7B-Instruct"
TARGET_LAYERS = [0, 7, 14, 21, 27]
LONG_FACT_MAX_SAMPLES = 500
SEED = 42

VALID_LABEL_MODES = {"token", "span", "sentence", "sample_weak", "synthetic"}
FORMAL_LABEL_MODES = {"token", "span", "sentence"}
WEAK_LABEL_MODES = {"sample_weak", "synthetic"}


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def validate_dataset_schema(rows, label_mode, dataset_path):
    """
    Validate dataset has required fields.
    Returns (is_valid, error_msg, metadata_dict).
    """
    errors = []

    # Check sample_id presence
    for i, row in enumerate(rows):
        if "sample_id" not in row:
            errors.append(f"Sample {i}: missing 'sample_id' field")

    if errors:
        return False, "; ".join(errors), {}

    # Detect available label types
    has_token_labels = False
    has_spans = False
    has_sample_hallu = False
    sample_ids = []

    for row in rows:
        sample_ids.append(row.get("sample_id"))
        if "token_labels" in row:
            has_token_labels = True
        if "hallucination_spans" in row:
            has_spans = True
        if "is_hallucinated" in row:
            has_sample_hallu = True

    # Require ALL rows to have formal field (not just any row)
    has_token_labels = all("token_labels" in r for r in rows)
    has_spans = all("hallucination_spans" in r for r in rows)

    hallu_count = sum(1 for r in rows if r.get("is_hallucinated", 0) == 1)
    hallu_prevalence = hallu_count / len(rows) if rows else 0.0

    # Determine effective label mode
    if label_mode in FORMAL_LABEL_MODES:
        if label_mode == "token" and not has_token_labels:
            return False, f"--label_mode token but no 'token_labels' field found", {}
        if label_mode == "span" and not has_spans:
            return False, f"--label_mode span but no 'hallucination_spans' field found", {}
        if label_mode == "sentence" and not has_sample_hallu:
            return False, f"--label_mode sentence requires 'is_hallucinated' per sentence", {}
        if label_mode == "sentence":
            # sentence mode requires verified mapping metadata, not just is_hallucinated
            return False, f"--label_mode sentence blocked: requires verified sentence_token_mapping metadata", {}

    if label_mode == "sample_weak" and not has_sample_hallu:
        return False, f"--label_mode sample_weak but no 'is_hallucinated' field found", {}

    # Block sample-level label from being used as token label
    if label_mode not in VALID_LABEL_MODES:
        return False, f"Invalid --label_mode '{label_mode}'. Must be one of {VALID_LABEL_MODES}", {}

    # Compute n_tokens estimate
    n_tokens_est = sum(len(r.get("response", "").split()) * 2 for r in rows)

    metadata = {
        "label_mode": label_mode,
        "dataset_source": str(dataset_path) if dataset_path else "ZhongangQi/LongFact-Objects",
        "split_mode": "sample_grouped",
        "n_samples": len(rows),
        "n_tokens_approx": n_tokens_est,
        "has_token_labels": has_token_labels,
        "has_spans": has_spans,
        "hallu_prevalence": hallu_prevalence,
        "can_run_formal_m1": label_mode in FORMAL_LABEL_MODES,
        "block_reason": None if label_mode in FORMAL_LABEL_MODES
                        else f"label_mode={label_mode} — only weak/synthetic sanity permitted",
    }

    return True, "OK", metadata


def compute_sample_grouped_split(rows, seed):
    """
    Deterministic 60/20/20 split grouped by unique sample_id.
    All rows with the same sample_id stay in the same split.
    """
    # Group by sample_id
    sample_to_group = {}
    for i, row in enumerate(rows):
        sid = row.get("sample_id", i)
        if sid not in sample_to_group:
            sample_to_group[sid] = []
        sample_to_group[sid].append(i)

    groups = list(sample_to_group.values())
    rng = np.random.RandomState(seed)
    rng.shuffle(groups)
    n = len(groups)
    n_train = int(n * 0.6)
    n_val = int(n * 0.2)

    train_groups = groups[:n_train]
    val_groups = groups[n_train:n_train + n_val]
    test_groups = groups[n_train + n_val:]

    train_idx = sorted(idx for g in train_groups for idx in g)
    val_idx = sorted(idx for g in val_groups for idx in g)
    test_idx = sorted(idx for g in test_groups for idx in g)
    return train_idx, val_idx, test_idx


def extract_and_align_labels(row, tok, full_text, prompt_len, comp_start, comp_len, label_mode):
    """
    Extract token-level labels aligned to completion tokens.
    Returns labels list (len = comp_len) or None if not formal.
    Raises ValueError if formal token extraction fails.
    """
    if label_mode == "token":
        raw = row.get("token_labels", None)
        if raw is None:
            raise ValueError(f"token mode requires token_labels but none found for sample {row.get('sample_id')}")
        if len(raw) < comp_len:
            raise ValueError(f"token_labels too short ({len(raw)}) for comp_len={comp_len}")
        return raw[:comp_len]

    elif label_mode == "span":
        spans = row.get("hallucination_spans", [])
        # Empty spans list is valid — means all tokens are factual (no hallucinations)
        labels = [0] * comp_len
        for span in spans:
            start = span.get("start", 0)
            end = span.get("end", start + 1)
            for t in range(int(start), int(min(end, comp_len))):
                labels[t] = 1
        return labels

    elif label_mode == "sample_weak":
        # Sample-level only — return None to signal weak labels
        return None

    elif label_mode == "synthetic":
        return None

    return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="M0: Hidden-state extraction for TokenTR")
    parser.add_argument("--max_samples", type=int, default=LONG_FACT_MAX_SAMPLES)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--layers", type=int, nargs="+", default=TARGET_LAYERS)
    parser.add_argument("--model_size", choices=["small", "7b"], default="small")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max_tokens", type=int, default=2048)
    parser.add_argument("--dataset_path", type=str, default=None,
                        help="Local path to dataset (JSON/JSONL). Overrides --dataset_name.")
    parser.add_argument("--dataset_name", type=str, default="ZhongangQi/LongFact-Objects")
    parser.add_argument("--label_mode", type=str, required=True,
                        choices=list(VALID_LABEL_MODES),
                        help="Token-level label mode. Must be 'token', 'span', or 'sentence' for formal M1. "
                             "'sample_weak' or 'synthetic' for weak-label sanity only.")
    parser.add_argument("--dry_run", action="store_true",
                        help="Validate data schema and metadata only; skip hidden state extraction.")

    args = parser.parse_args()
    set_seed(args.seed)
    device = torch.device(args.device)
    MODEL = MODEL_NAME_7B if args.model_size == "7b" else MODEL_NAME

    print(f"\n{'='*60}")
    print(f"M0: Hidden-State Extraction")
    print(f"{'='*60}")
    print(f"Model: {MODEL}")
    print(f"Layers: {args.layers}")
    print(f"Max samples: {args.max_samples}")
    print(f"Label mode: {args.label_mode}")
    print(f"Dry run: {args.dry_run}")
    print()

    # ── Load dataset ──────────────────────────────────────────────────────────
    if args.dataset_path:
        p = Path(args.dataset_path)
        if not p.exists():
            print(f"ERROR: dataset_path not found: {p}")
            return 1
        if p.suffix == ".jsonl":
            rows = [json.loads(l) for l in open(p, encoding="utf-8")]
        elif p.suffix == ".json":
            rows = json.load(open(p, encoding="utf-8"))
        else:
            print(f"ERROR: unsupported file type: {p.suffix}")
            return 1
        print(f"Loaded {len(rows)} samples from local: {p}")
        dataset_source = str(p.absolute())
    else:
        try:
            from datasets import load_dataset
            ds = load_dataset(args.dataset_name, split="train")
            ds = ds.shuffle(seed=args.seed).select(range(min(args.max_samples, len(ds))))
            rows = [dict(r) for r in ds]
            print(f"Loaded {len(rows)} samples from HuggingFace: {args.dataset_name}")
            dataset_source = args.dataset_name
        except Exception as e:
            print(f"ERROR: HF load failed ({e})")
            return 1

    rows = rows[:args.max_samples]

    # ── Schema validation ──────────────────────────────────────────────────────
    is_valid, err_msg, metadata = validate_dataset_schema(rows, args.label_mode, args.dataset_path)
    if not is_valid:
        print(f"ERROR: {err_msg}")
        metadata["can_run_formal_m1"] = False
        metadata["block_reason"] = err_msg
        SPLIT_DIR.mkdir(parents=True, exist_ok=True)
        with open(METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Metadata written (with block): {METADATA_PATH}")
        return 1

    print(f"\nDataset schema valid.")
    print(f"  has_token_labels={metadata['has_token_labels']}")
    print(f"  has_spans={metadata['has_spans']}")
    print(f"  hallu_prevalence={metadata['hallu_prevalence']:.3f}")

    if args.dry_run:
        print(f"\nDRY RUN: schema validation only — no extraction performed.")
        print(f"Metadata: can_run_formal_m1={metadata['can_run_formal_m1']}")
        if not metadata["can_run_formal_m1"]:
            print(f"  block_reason: {metadata['block_reason']}")
        SPLIT_DIR.mkdir(parents=True, exist_ok=True)
        with open(METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Metadata: {METADATA_PATH}")
        return 0

    # ── Load tokenizer + model ───────────────────────────────────────────────
    print("Loading tokenizer...", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL, local_files_only=False)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    print("Loading model...", flush=True)
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.float16, device_map="auto",
        local_files_only=False, output_hidden_states=True, return_dict=True,
    )
    model.eval()
    hidden_dim = model.config.hidden_size
    n_layers_model = len(model.model.layers)
    print(f"Model loaded in {time.time()-t0:.1f}s  (hidden_dim={hidden_dim}, layers={n_layers_model})")

    valid_layers = [l for l in args.layers if l < n_layers_model]

    # ── Sample-grouped split ──────────────────────────────────────────────────
    train_idx, val_idx, test_idx = compute_sample_grouped_split(rows, args.seed)
    split_info = {
        "n_total": len(rows),
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "n_test": len(test_idx),
        "train_indices": train_idx,
        "val_indices": val_idx,
        "test_indices": test_idx,
        "seed": args.seed,
        "split_mode": "sample_grouped",
    }

    # ── Extraction loop ───────────────────────────────────────────────────────
    print(f"\nExtracting hidden states for {len(rows)} samples...", flush=True)

    all_hs_by_layer = {lid: [] for lid in valid_layers}
    all_labels = []
    all_prompt_lens = []
    extraction_errors = 0

    for i, row in enumerate(rows):
        if i % 50 == 0:
            print(f"  [{i}/{len(rows)}]", flush=True)

        prompt = row.get("prompt", row.get("user_prompt", ""))
        response = row.get("response", row.get("assistant_response", ""))
        full_text = prompt + " " + response

        prompt_tok = tok(prompt, return_tensors="pt", truncation=True, max_length=args.max_tokens)
        response_tok = tok(response, return_tensors="pt", truncation=True, max_length=args.max_tokens)
        prompt_len = prompt_tok.input_ids.shape[1]
        resp_len = response_tok.input_ids.shape[1]
        total_len = min(prompt_len + resp_len, args.max_tokens)

        try:
            inputs = tok(full_text, return_tensors="pt", truncation=True,
                        max_length=args.max_tokens).to(device)
            with torch.no_grad():
                outputs = model(**inputs, output_hidden_states=True, return_dict=True)
                hss = outputs.hidden_states

            seq_len = inputs.input_ids.shape[1]
            comp_start = min(prompt_len, seq_len - 1)
            comp_len = seq_len - comp_start

            # Label extraction FIRST (may raise for formal modes) — before appending hidden states
            if args.label_mode in FORMAL_LABEL_MODES:
                # Raises ValueError on failure → caught by except, no hidden states appended
                labels = extract_and_align_labels(row, tok, full_text, prompt_len, comp_start, comp_len, args.label_mode)
            elif args.label_mode in ("sample_weak", "synthetic"):
                labels = None  # signals weak/synthetic label
            else:
                labels = None

            # Only append hidden states after labels are successfully extracted
            for lid in valid_layers:
                hs = hss[lid][0, comp_start:].cpu().numpy()
                all_hs_by_layer[lid].append(hs)

            all_labels.append(labels)
            all_prompt_lens.append(prompt_len)

        except Exception as e:
            print(f"  ERROR {i}: {e}", flush=True)
            extraction_errors += 1
            continue

    # ── Save outputs ─────────────────────────────────────────────────────────
    HIDDEN_DIR.mkdir(parents=True, exist_ok=True)
    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    model_short = MODEL.split("/")[-1].replace("-Instruct", "")

    for lid in valid_layers:
        hs_list = all_hs_by_layer[lid]
        max_len = max(arr.shape[0] for arr in hs_list)
        padded = np.zeros((len(hs_list), max_len, hidden_dim), dtype=np.float16)
        mask = np.zeros((len(hs_list), max_len), dtype=bool)
        for j, arr in enumerate(hs_list):
            n = arr.shape[0]
            padded[j, :n] = arr
            mask[j, :n] = True
        np.save(HIDDEN_DIR / f"{model_short}_layer{lid:02d}.npy", padded)
        np.save(HIDDEN_DIR / f"{model_short}_layer{lid:02d}_mask.npy", mask)

    # Labels
    labels_out = SPLIT_DIR / "longfact_token_labels.json"
    with open(labels_out, "w") as f:
        json.dump({"labels": all_labels, "prompt_lens": all_prompt_lens,
                   "label_mode": args.label_mode}, f)

    # Split
    split_path = SPLIT_DIR / "longfact_split.json"
    with open(split_path, "w") as f:
        json.dump(split_info, f, indent=2)

    # Metadata
    final_metadata = dict(metadata)
    final_metadata["n_extracted"] = len(rows) - extraction_errors
    final_metadata["extraction_errors"] = extraction_errors
    with open(METADATA_PATH, "w") as f:
        json.dump(final_metadata, f, indent=2)

    print(f"\n{'='*60}")
    print("M0 SUMMARY")
    print(f"{'='*60}")
    print(f"Model: {MODEL}")
    print(f"Layers: {valid_layers}")
    print(f"Samples: {len(rows)} (errors={extraction_errors})")
    print(f"Label mode: {args.label_mode}")
    print(f"Can run formal M1: {final_metadata['can_run_formal_m1']}")
    if final_metadata.get("block_reason"):
        print(f"Block reason: {final_metadata['block_reason']}")
    print(f"Metadata: {METADATA_PATH}")
    print(f"Hidden states: {HIDDEN_DIR.resolve()}")
    print(f"Split: {SPLIT_DIR.resolve()}")
    print(f"Total time: {time.time()-t0:.1f}s")
    print("M0 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
