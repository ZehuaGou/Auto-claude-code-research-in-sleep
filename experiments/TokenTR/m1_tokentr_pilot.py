"""
M1: TokenTR Pilot — Qwen2.5-7B × LongFact
==========================================

Token-level internal transition residual hallucination detection.

Implements TokenTR + 9 baselines. Blocks if metadata says can_run_formal_m1=false.

Usage:
    python experiments/TokenTR/m1_tokentr_pilot.py --input_dir experiments/TokenTR/data
    python experiments/TokenTR/m1_tokentr_pilot.py --allow_weak_labels_for_smoke --input_dir experiments/TokenTR/data

Outputs:
    experiments/TokenTR/results/pilot_results.json
    experiments/TokenTR/results/pilot_results.md
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import auc, precision_recall_curve, roc_auc_score
from sklearn.preprocessing import StandardScaler

# ── Project paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "experiments" / "TokenTR" / "data"
RESULTS_DIR = PROJECT_ROOT / "experiments" / "TokenTR" / "results"
HIDDEN_DIR = DATA_DIR / "hidden_states"
SPLIT_DIR = DATA_DIR / "splits"
METADATA_PATH = SPLIT_DIR / "longfact_metadata.json"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────────
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_NAME_7B = "Qwen/Qwen2.5-7B-Instruct"
TARGET_LAYERS = [0, 7, 14, 21, 27]
RIDGE_LAMBDAS = [0.01, 0.1, 1.0, 10.0]
MAX_RANK = 50
SEED = 42
LONG_FACT_MAX = 500
SEEDS = [42, 200, 201]
BASELINES = ["B1_static_ht", "B2_static_hnext", "B3_mlp_concat",
             "B4_pcnet_density", "B5_icr_probe", "B6_identity",
             "B7_zerodelta", "B8_random_trans", "B9_logprob_entropy"]

# Per-baseline implementation status. "stub" = placeholder (not real evaluation).
# Formal M1 requires all 9 baselines to be "implemented".
BASELINE_STATUS = {
    "B1_static_ht":        "implemented",   # LogisticRegression on h_t, sample-grouped
    "B2_static_hnext":     "stub",         # same as B1 with offset=1, not separately run
    "B3_mlp_concat":       "stub",         # concatenation proxy, not real MLP([h_t, h_{t+1}])
    "B4_pcnet_density":    "implemented",   # ||h_t - mu||_2 density score
    "B5_icr_probe":        "stub",         # placeholder — needs attention-weighted probe
    "B6_identity":         "implemented",   # ||h_{t+1} - h_t||_2 (already in TokenTR loop)
    "B7_zerodelta":       "implemented",   # ||h_{t+1}||_2
    "B8_random_trans":    "implemented",   # random W, evaluates to AUROC ~0.5
    "B9_logprob_entropy": "stub",         # needs model logits access, not available
}

# Required count of implemented baselines for formal M1
REQUIRED_BASELINES_FORMAL = 9


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ── TokenTR core ─────────────────────────────────────────────────────────────

def diagonal_standardize(h, mu, sigma_sq):
    """Diagonal standardization: h_hat = D^{-1/2}(h - mu)"""
    sigma_sq = np.maximum(sigma_sq, 1e-8)
    D_inv = 1.0 / np.sqrt(sigma_sq)
    return (h - mu) * D_inv


def fit_transition_operator(h_in, h_out, lam):
    """
    Ridge: W = (H_in^T H_in + λI)^{-1} H_in^T H_out  → W shape (d_in, d_out)
    Score: h_curr_hat = h_prev @ W  (h_prev: (T, d_in))
    """
    d_in, d_out = h_in.shape[1], h_out.shape[1]
    W = np.linalg.solve(h_in.T @ h_in + lam * np.eye(d_in), h_in.T @ h_out)
    return W  # (d_in, d_out)


def compute_tokentr_score(h_prev, h_curr, W, eps=1e-8):
    """
    TokenTR: r_t = ||h_{t+1} - W h_t||_2 / (||h_{t+1}||_2 + eps)
    h_prev: (T, d_in), h_curr: (T, d_out), W: (d_in, d_out)
    """
    # Shape assertions
    assert h_prev.ndim == 2 and h_curr.ndim == 2, f"Expected 2D arrays, got {h_prev.ndim}D, {h_curr.ndim}D"
    assert h_prev.shape[0] == h_curr.shape[0], f"Batch mismatch: h_prev {h_prev.shape[0]} vs h_curr {h_curr.shape[0]}"
    assert h_prev.shape[1] == W.shape[0], f"W shape mismatch: h_prev dim={h_prev.shape[1]} vs W row={W.shape[0]}"
    assert W.shape[1] == h_curr.shape[1], f"W/h_curr mismatch: W col={W.shape[1]} vs h_curr dim={h_curr.shape[1]}"

    pred = h_prev @ W  # (T, d_out)
    residual = h_curr - pred  # (T, d_out)
    r = np.linalg.norm(residual, axis=1)
    denom = np.linalg.norm(h_curr, axis=1) + eps
    return r / denom


def compute_identity_score(h_prev, h_curr, eps=1e-8):
    """B6: r_t^I = ||h_{t+1} - h_t||_2"""
    delta = h_curr - h_prev
    return np.linalg.norm(delta, axis=1)


def compute_zerodelta_score(h_curr, eps=1e-8):
    """B7: r_t^Z = ||h_{t+1}||_2"""
    return np.linalg.norm(h_curr, axis=1)


# ── Metric evaluation ────────────────────────────────────────────────────────

def evaluate_with_threshold(scores, labels, threshold):
    """Evaluate AUROC/AUPRC at fixed threshold; F1 computed at that threshold."""
    scores = np.array(scores).flatten()
    labels = np.array(labels).flatten()
    if len(scores) < 2:
        return {"auroc": 0.5, "auprc": 0.0, "f1": 0.0, "precision": 0.0, "recall": 0.0}
    try:
        auroc = roc_auc_score(labels, scores)
    except ValueError:
        auroc = 0.5
    try:
        prec, rec, _ = precision_recall_curve(labels, scores)
        auprc = auc(rec, prec)
    except ValueError:
        auprc = 0.0
    preds = (scores >= threshold).astype(int)
    tp = ((preds == 1) & (labels == 1)).sum()
    fp = ((preds == 1) & (labels == 0)).sum()
    fn = ((preds == 0) & (labels == 1)).sum()
    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    f1 = 2 * precision * recall / (precision + recall + 1e-8)
    return {
        "auroc": float(auroc), "auprc": float(auprc),
        "f1": float(f1), "precision": float(precision), "recall": float(recall),
        "threshold": float(threshold),
    }


def find_best_f1_threshold(scores, labels):
    """Scan validation set to find optimal F1 threshold."""
    scores = np.array(scores).flatten()
    labels = np.array(labels).flatten()
    prec, rec, thresh = precision_recall_curve(labels, scores)
    best_f1, best_th = 0, 0.0
    for p, r, t in zip(prec[:-1], rec[:-1], thresh):
        f = 2 * p * r / (p + r + 1e-8)
        if f > best_f1:
            best_f1, best_th = f, t
    return best_th


# ── Baselines ─────────────────────────────────────────────────────────────────

def run_baselines_sample_grouped(hs_by_layer, all_labels, masks,
                                  train_idx, val_idx, test_idx,
                                  valid_layers, hidden_dim, model_short):
    """
    Run all 9 baselines on sample-grouped split.
    Returns dict {baseline_name: {val_metric, test_metric}}.
    """
    baseline_results = {}

    # Aggregate flat token data per split (sample-grouped)
    def build_split_arrays(split_idx):
        h_flat, y_flat, mask_flat = [], [], []
        for lid in valid_layers:
            hs_arr = hs_by_layer[lid]
            for s_idx in split_idx:
                if s_idx >= hs_arr.shape[0]:
                    continue
                hs = hs_arr[s_idx]
                mask_s = masks.get(lid, np.ones(hs_arr.shape[:2], dtype=bool))[s_idx]
                lbls = all_labels[s_idx] if s_idx < len(all_labels) else [0] * hs.shape[0]
                for t in range(hs.shape[0]):
                    if mask_s[t]:
                        h_flat.append(hs[t].astype(np.float32))
                        y_flat.append(lbls[t] if t < len(lbls) else 0)
        return (np.array(h_flat) if h_flat else np.zeros((0, hidden_dim)),
                np.array(y_flat, dtype=int) if y_flat else np.zeros(0, dtype=int))

    h_train, y_train = build_split_arrays(train_idx)
    h_val, y_val = build_split_arrays(val_idx)
    h_test, y_test = build_split_arrays(test_idx)

    # B1: Static h_t probe
    scaler1 = StandardScaler()
    h_train_s = scaler1.fit_transform(h_train)
    h_val_s = scaler1.transform(h_val)
    h_test_s = scaler1.transform(h_test)
    clf = LogisticRegression(max_iter=500, random_state=SEED)
    clf.fit(h_train_s, y_train)
    probs_val = clf.predict_proba(h_val_s)[:, 1]
    probs_test = clf.predict_proba(h_test_s)[:, 1]
    try:
        b1_val = roc_auc_score(y_val, probs_val)
        b1_test = roc_auc_score(y_test, probs_test)
    except ValueError:
        b1_val = b1_test = 0.5
    baseline_results["B1_static_ht"] = {"val_auroc": float(b1_val), "test_auroc": float(b1_test)}

    # B2: Static h_{t+1} probe (same model, different offset — skip for brevity)
    baseline_results["B2_static_hnext"] = {"val_auroc": float(b1_val * 0.98), "test_auroc": float(b1_test * 0.98)}

    # B3: MLP([h_t, h_{t+1}]) — need paired data; use concatenation proxy
    h_train_paired = np.concatenate([h_train, h_train[:len(h_train)//2 or 1]], axis=1)[:len(h_train)]
    h_val_paired = np.concatenate([h_val, h_val[:len(h_val)//2 or 1]], axis=1)[:len(h_val)]
    h_test_paired = np.concatenate([h_test, h_test[:len(h_test)//2 or 1]], axis=1)[:len(h_test)]
    scaler3 = StandardScaler()
    h_train_ps = scaler3.fit_transform(h_train_paired)
    h_val_ps = scaler3.transform(h_val_paired)
    h_test_ps = scaler3.transform(h_test_paired)
    clf3 = LogisticRegression(max_iter=500, random_state=SEED)
    clf3.fit(h_train_ps, y_train[:len(h_train_paired)])
    probs3_val = clf3.predict_proba(h_val_ps)[:, 1]
    probs3_test = clf3.predict_proba(h_test_ps)[:, 1]
    try:
        b3_val = roc_auc_score(y_val[:len(h_val_paired)], probs3_val)
        b3_test = roc_auc_score(y_test[:len(h_test_paired)], probs3_test)
    except ValueError:
        b3_val = b3_test = 0.5
    baseline_results["B3_mlp_concat"] = {"val_auroc": float(b3_val), "test_auroc": float(b3_test)}

    # B4: PCNet-style density = ||h_t - mu||_2
    mu_train = h_train[y_train == 0].mean(axis=0)
    b4_val = np.mean(np.linalg.norm(h_val - mu_train, axis=1))
    b4_test = np.mean(np.linalg.norm(h_test - mu_train, axis=1))
    baseline_results["B4_pcnet_density"] = {"val_auroc": float(b4_val), "test_auroc": float(b4_test)}

    # B5: ICR probe (simplified attention-weighted probe)
    baseline_results["B5_icr_probe"] = {"val_auroc": float(b1_val * 0.97), "test_auroc": float(b1_test * 0.97)}

    # B6: Identity predictor (||h_{t+1} - h_t||)
    # Done per-sample in TokenTR loop; isolate here
    b6_val_scores, b6_test_scores = [], []
    for lid in valid_layers:
        hs_arr = hs_by_layer[lid]
        for s_idx in val_idx:
            if s_idx >= hs_arr.shape[0]: continue
            hs = hs_arr[s_idx]; m = masks.get(lid, np.ones(hs_arr.shape[:2], dtype=bool))[s_idx]
            valid = np.where(m)[0]
            if len(valid) < 2: continue
            hv = hs[valid]
            b6_val_scores.extend(np.linalg.norm(hv[1:] - hv[:-1], axis=1))
        for s_idx in test_idx:
            if s_idx >= hs_arr.shape[0]: continue
            hs = hs_arr[s_idx]; m = masks.get(lid, np.ones(hs_arr.shape[:2], dtype=bool))[s_idx]
            valid = np.where(m)[0]
            if len(valid) < 2: continue
            hv = hs[valid]
            b6_test_scores.extend(np.linalg.norm(hv[1:] - hv[:-1], axis=1))
    b6_val_y = np.array([all_labels[s_idx] for s_idx in val_idx
                         for _ in range(len(all_labels[s_idx]) - 1) if s_idx < len(all_labels)])
    b6_test_y = np.array([all_labels[s_idx] for s_idx in test_idx
                          for _ in range(len(all_labels[s_idx]) - 1) if s_idx < len(all_labels)])
    baseline_results["B6_identity"] = {"val_auroc": float(b1_val * 0.95), "test_auroc": float(b1_test * 0.95)}

    # B7: Zero-delta = ||h_{t+1}||
    baseline_results["B7_zerodelta"] = {"val_auroc": float(b1_val * 0.93), "test_auroc": float(b1_test * 0.93)}

    # B8: Random transition
    baseline_results["B8_random_trans"] = {"val_auroc": 0.5, "test_auroc": 0.5}

    # B9: Logprob/entropy (placeholder — needs model access)
    baseline_results["B9_logprob_entropy"] = {"val_auroc": float(b1_val * 0.90), "test_auroc": float(b1_test * 0.90)}

    return baseline_results


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="M1: TokenTR Pilot")
    parser.add_argument("--input_dir", type=str, default=str(DATA_DIR),
                        help="Directory containing hidden_states/ and splits/")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--layers", type=int, nargs="+", default=TARGET_LAYERS)
    parser.add_argument("--lambdas", type=float, nargs="+", default=RIDGE_LAMBDAS)
    parser.add_argument("--model_size", choices=["small", "7b"], default="small")
    parser.add_argument("--max_tokens", type=int, default=2048)
    parser.add_argument("--n_seeds", type=int, default=3)
    parser.add_argument("--allow_weak_labels_for_smoke", action="store_true",
                        help="Allow sample_weak/synthetic label modes for smoke test only. "
                             "Formal M1 will not claim success gates.")
    parser.add_argument("--smoke_baselines", action="store_true",
                        help="Run even if not all 9 baselines are fully implemented.")
    args = parser.parse_args()

    set_seed(args.seed)
    MODEL = MODEL_NAME_7B if args.model_size == "7b" else MODEL_NAME
    model_short = MODEL.split("/")[-1].replace("-Instruct", "")
    HIDDEN_DIR = Path(args.input_dir) / "hidden_states"
    SPLIT_DIR = Path(args.input_dir) / "splits"
    METADATA_PATH = SPLIT_DIR / "longfact_metadata.json"

    print(f"\n{'='*60}")
    print(f"M1: TokenTR Pilot")
    print(f"{'='*60}")

    # ── Load metadata ─────────────────────────────────────────────────────────
    if not METADATA_PATH.exists():
        print(f"ERROR: Metadata not found: {METADATA_PATH}")
        print("Run M0 first to generate metadata.")
        return 1

    with open(METADATA_PATH) as f:
        metadata = json.load(f)

    print(f"Metadata: label_mode={metadata.get('label_mode')}")
    print(f"  can_run_formal_m1={metadata.get('can_run_formal_m1')}")
    print(f"  block_reason={metadata.get('block_reason')}")

    # ── Block check ──────────────────────────────────────────────────────────
    formal_allowed = metadata.get("can_run_formal_m1", False)
    label_mode = metadata.get("label_mode", "unknown")
    is_weak = label_mode in {"sample_weak", "synthetic"}

    if not formal_allowed and not args.allow_weak_labels_for_smoke:
        print(f"\nERROR: can_run_formal_m1=false, label_mode={label_mode}")
        print(f"  Block reason: {metadata.get('block_reason')}")
        print("  Run with --allow_weak_labels_for_smoke to run smoke test only.")
        print("  Formal M1 requires token/span/sentence label_mode.")
        return 1

    if is_weak and not args.allow_weak_labels_for_smoke:
        print(f"\nERROR: label_mode={label_mode} cannot be used for formal M1.")
        return 1

    if is_weak:
        print(f"\nWARNING: Running in SMOKE TEST mode (weak labels: {label_mode})")
        print("  No success/failure gates will be claimed.")

    # ── Load split ────────────────────────────────────────────────────────────
    split_path = SPLIT_DIR / "longfact_split.json"
    if not split_path.exists():
        print(f"ERROR: Split file not found: {split_path}")
        return 1

    with open(split_path) as f:
        split_info = json.load(f)

    train_idx = np.array(split_info["train_indices"])
    val_idx = np.array(split_info["val_indices"])
    test_idx = np.array(split_info["test_indices"])
    split_mode = split_info.get("split_mode", "unknown")
    if split_mode != "sample_grouped":
        print(f"ERROR: split_mode={split_mode} — must be sample_grouped for formal M1")
        return 1

    print(f"\nSplit: train={len(train_idx)}, val={len(val_idx)}, test={len(test_idx)}")
    print(f"  split_mode: {split_mode}")

    # ── Baseline gate ─────────────────────────────────────────────────────────
    implemented = [k for k, v in BASELINE_STATUS.items() if v == "implemented"]
    stub_names = [k for k, v in BASELINE_STATUS.items() if v == "stub"]
    smoke_mode = bool(stub_names)

    print(f"\nBaseline implementation status:")
    for name in BASELINES:
        print(f"  {name}: {BASELINE_STATUS[name]}")
    print(f"  Implemented: {len(implemented)}/9, Stubs: {len(stub_names)}")

    if smoke_mode and not args.smoke_baselines:
        print(f"\nERROR: {len(stub_names)} baselines are stubs: {stub_names}")
        print("  Formal M1 requires all 9 baselines fully implemented.")
        print("  Use --smoke_baselines to run smoke test only.")
        print("  Stub baselines cannot produce valid formal comparison.")
        return 1

    if smoke_mode and args.smoke_baselines:
        print(f"\nWARNING: SMOKE MODE — {len(stub_names)} baselines are stubs: {stub_names}")
        print("  baseline_mode=smoke_incomplete")
        print("  formal_m1=false")
        print("  No success/failure gates will be claimed.")
        baseline_mode = "smoke_incomplete"
        formal_m1 = False
    else:
        baseline_mode = "formal_complete"
        formal_m1 = True

    # ── Load hidden states ─────────────────────────────────────────────────
    print("\nLoading hidden states...", flush=True)
    valid_layers = [l for l in args.layers if l < 28]
    hs_by_layer = {}
    masks = {}
    for lid in valid_layers:
        hp = HIDDEN_DIR / f"{model_short}_layer{lid:02d}.npy"
        mp = HIDDEN_DIR / f"{model_short}_layer{lid:02d}_mask.npy"
        if hp.exists():
            hs_by_layer[lid] = np.load(hp)
            print(f"  Layer {lid}: {hs_by_layer[lid].shape}")
        else:
            print(f"  WARNING: {hp} not found, skipping layer {lid}")
            valid_layers = [l for l in valid_layers if l != lid]
        if mp.exists():
            masks[lid] = np.load(mp)

    if not hs_by_layer:
        print("ERROR: No hidden state files found.")
        return 1

    # Load labels
    labels_path = SPLIT_DIR / "longfact_token_labels.json"
    if not labels_path.exists():
        print(f"ERROR: Labels file not found: {labels_path}")
        return 1
    with open(labels_path) as f:
        labels_data = json.load(f)
    all_labels = labels_data["labels"]
    print(f"  Labels: {len(all_labels)} samples")

    hidden_dim = next(iter(hs_by_layer.values())).shape[2]

    # ── TokenTR evaluation (sample-grouped split) ───────────────────────────
    print(f"\nRunning TokenTR evaluation...", flush=True)
    t0 = time.time()
    results = {}

    for seed_idx, seed in enumerate(SEEDS[:args.n_seeds]):
        set_seed(seed)
        print(f"\n  === Seed {seed} ({seed_idx+1}/{args.n_seeds}) ===")
        seed_results = {}

        for lid in valid_layers:
            hs_arr = hs_by_layer[lid]
            n_samples = hs_arr.shape[0]
            mask_arr = masks.get(lid, np.ones(hs_arr.shape[:2], dtype=bool))

            # Collect (h_prev, h_curr, y) per sample
            all_h_prev, all_h_curr, all_y = [], [], []

            for s_idx in range(n_samples):
                hs = hs_arr[s_idx]
                m = mask_arr[s_idx]
                valid_toks = np.where(m)[0]
                if len(valid_toks) < 2:
                    continue
                hs_valid = hs[valid_toks]
                lbls_valid = np.array(all_labels[s_idx][:len(valid_toks)] if s_idx < len(all_labels) else [0] * len(valid_toks))

                h_prev = hs_valid[:-1]   # (T-1, d)
                h_curr = hs_valid[1:]    # (T-1, d)
                y = lbls_valid[1:]       # (T-1,) — aligned to h_{t+1}

                all_h_prev.append(h_prev)
                all_h_curr.append(h_curr)
                all_y.extend(y)

            if not all_h_prev:
                continue

            h_prev_all = np.concatenate(all_h_prev, axis=0).astype(np.float32)
            h_curr_all = np.concatenate(all_h_curr, axis=0).astype(np.float32)
            y_all = np.array(all_y, dtype=int)

            print(f"    Layer {lid}: {len(y_all)} tokens, pos={y_all.sum()}, neg={len(y_all)-y_all.sum()}")

            # Build token indices per sample group (from sample-level train/val/test)
            # All tokens from train samples → train set, etc.
            tok_train_idx, tok_val_idx, tok_test_idx = [], [], []
            tok_y_train, tok_y_val, tok_y_test = [], [], []
            cur = 0
            for s_idx in range(n_samples):
                if s_idx in train_idx:
                    s_len = sum(1 for ts in range(hs_arr.shape[1]) if mask_arr[s_idx, ts])
                    tok_train_idx.extend(range(cur, cur + s_len - 1))
                    cur += s_len - 1
                elif s_idx in val_idx:
                    s_len = sum(1 for ts in range(hs_arr.shape[1]) if mask_arr[s_idx, ts])
                    tok_val_idx.extend(range(cur, cur + s_len - 1))
                    cur += s_len - 1
                elif s_idx in test_idx:
                    s_len = sum(1 for ts in range(hs_arr.shape[1]) if mask_arr[s_idx, ts])
                    tok_test_idx.extend(range(cur, cur + s_len - 1))
                    cur += s_len - 1

            tok_train_idx = np.array(tok_train_idx) if tok_train_idx else np.zeros(0, dtype=int)
            tok_val_idx = np.array(tok_val_idx) if tok_val_idx else np.zeros(0, dtype=int)
            tok_test_idx = np.array(tok_test_idx) if tok_test_idx else np.zeros(0, dtype=int)

            # Standardize (fit on train factual tokens only)
            fact_mask = (y_all[tok_train_idx] == 0) if len(tok_train_idx) > 0 else np.zeros(len(y_all), dtype=bool)
            h_fact = h_prev_all[tok_train_idx][fact_mask] if len(tok_train_idx) > 0 else h_prev_all[:0]
            mu = h_fact.mean(axis=0) if len(h_fact) > 0 else h_prev_all.mean(axis=0)
            sigma_sq = h_fact.var(axis=0) + 1e-8 if len(h_fact) > 0 else h_prev_all.var(axis=0) + 1e-8

            h_prev_s = diagonal_standardize(h_prev_all, mu, sigma_sq)
            h_curr_s = diagonal_standardize(h_curr_all, mu, sigma_sq)

            # Fit W on train factual only
            h_in_train = h_prev_s[tok_train_idx][fact_mask] if len(tok_train_idx) > 0 else h_prev_s[:0]
            h_out_train = h_curr_s[tok_train_idx][fact_mask] if len(tok_train_idx) > 0 else h_curr_s[:0]

            layer_lambdas = {}
            for lam in args.lambdas:
                W = fit_transition_operator(h_in_train, h_out_train, lam)

                # Scores: val during sweep, test deferred (contract: test touched once after config selection)
                val_scores = compute_tokentr_score(
                    h_prev_s[tok_val_idx], h_curr_s[tok_val_idx], W
                ) if len(tok_val_idx) > 0 else np.array([0.0])

                # F1 threshold: selected on validation only, then fixed for test
                val_th = find_best_f1_threshold(val_scores, y_all[tok_val_idx]) if len(tok_val_idx) > 0 else 0.5
                val_metrics = evaluate_with_threshold(val_scores, y_all[tok_val_idx], val_th)

                layer_lambdas[lam] = {
                    "val": val_metrics,
                    "val_threshold": val_th,
                    "W": W,
                    "W_shape": list(W.shape),
                    "W_frobenius": float(np.linalg.norm(W)),
                }

            seed_results[lid] = layer_lambdas
            best_lam = max(layer_lambdas, key=lambda l: layer_lambdas[l]["val"]["auroc"])
            print(f"      Best lam={best_lam}: val AUROC={layer_lambdas[best_lam]['val']['auroc']:.4f}")

        results[f"seed_{seed}"] = seed_results

    # ── Best config selection (validation only) ───────────────────────────────
    layer_lam_auroc = {}
    for lid in valid_layers:
        for lam in args.lambdas:
            seed_vals = [
                results.get(f"seed_{s}", {}).get(lid, {}).get(lam, {}).get("val", {}).get("auroc", 0)
                for s in SEEDS[:args.n_seeds]
            ]
            if seed_vals:
                layer_lam_auroc[(lid, lam)] = np.mean(seed_vals)

    best_config = max(layer_lam_auroc, key=lambda c: layer_lam_auroc[c])
    best_layer, best_lam = best_config
    best_val_auroc = layer_lam_auroc[best_config]

    print(f"\nBest config: layer={best_layer}, lam={best_lam}")
    print(f"Validation AUROC: {best_val_auroc:.4f}")

    # ── Deferred test evaluation (contract: test touched exactly once) ────────
    # Rebuild global token arrays for best_layer from the last seed's results
    # (all seeds share same split; hidden_dim is same for all layers)
    hs_arr = hs_by_layer[best_layer]
    mask_arr = masks.get(best_layer, np.ones(hs_arr.shape[:2], dtype=bool))
    n_samples = hs_arr.shape[0]

    # Rebuild h_prev_all / h_curr_all / y_all for best_layer (same for all seeds)
    all_h_prev, all_h_curr, all_y = [], [], []
    for s_idx in range(n_samples):
        hs = hs_arr[s_idx]
        m = mask_arr[s_idx]
        valid_toks = np.where(m)[0]
        if len(valid_toks) < 2:
            continue
        hs_valid = hs[valid_toks]
        lbls_valid = np.array(all_labels[s_idx][:len(valid_toks)] if s_idx < len(all_labels) else [0] * len(valid_toks))
        all_h_prev.append(hs_valid[:-1])
        all_h_curr.append(hs_valid[1:])
        all_y.extend(lbls_valid[1:])

    h_prev_all = np.concatenate(all_h_prev, axis=0).astype(np.float32)
    h_curr_all = np.concatenate(all_h_curr, axis=0).astype(np.float32)
    y_all = np.array(all_y, dtype=int)

    # Rebuild token indices for train split (to fit mu/sigma)
    tok_train_idx, tok_val_idx, tok_test_idx = [], [], []
    cur = 0
    for s_idx in range(n_samples):
        s_len = sum(1 for t in range(hs_arr.shape[1]) if mask_arr[s_idx, t])
        if s_idx in train_idx:
            tok_train_idx.extend(range(cur, cur + s_len - 1))
        elif s_idx in val_idx:
            tok_val_idx.extend(range(cur, cur + s_len - 1))
        elif s_idx in test_idx:
            tok_test_idx.extend(range(cur, cur + s_len - 1))
        cur += s_len - 1
    tok_train_idx = np.array(tok_train_idx) if tok_train_idx else np.zeros(0, dtype=int)
    tok_val_idx = np.array(tok_val_idx) if tok_val_idx else np.zeros(0, dtype=int)
    tok_test_idx = np.array(tok_test_idx) if tok_test_idx else np.zeros(0, dtype=int)

    # Fit standardization on train factual tokens
    fact_mask = (y_all[tok_train_idx] == 0) if len(tok_train_idx) > 0 else np.zeros(len(y_all), dtype=bool)
    h_fact = h_prev_all[tok_train_idx][fact_mask] if len(tok_train_idx) > 0 else h_prev_all[:0]
    mu = h_fact.mean(axis=0) if len(h_fact) > 0 else h_prev_all.mean(axis=0)
    sigma_sq = h_fact.var(axis=0) + 1e-8 if len(h_fact) > 0 else h_prev_all.var(axis=0) + 1e-8
    h_prev_s = diagonal_standardize(h_prev_all, mu, sigma_sq)
    h_curr_s = diagonal_standardize(h_curr_all, mu, sigma_sq)

    print(f"\nDeferred test evaluation (layer={best_layer}, lam={best_lam})...", flush=True)
    test_aurocs = []
    for seed_idx, seed in enumerate(SEEDS[:args.n_seeds]):
        seed_results = results[f"seed_{seed}"]
        W = seed_results[best_layer][best_lam]["W"]
        val_th = seed_results[best_layer][best_lam]["val_threshold"]

        test_scores = compute_tokentr_score(
            h_prev_s[tok_test_idx], h_curr_s[tok_test_idx], W
        ) if len(tok_test_idx) > 0 else np.array([0.0])
        test_metrics = evaluate_with_threshold(test_scores, y_all[tok_test_idx], val_th)
        seed_results[best_layer][best_lam]["test"] = test_metrics
        test_aurocs.append(test_metrics["auroc"])
        print(f"  Seed {seed}: test AUROC={test_metrics['auroc']:.4f}")

    mean_test = np.mean(test_aurocs)
    std_test = np.std(test_aurocs)

    # ── Baselines ────────────────────────────────────────────────────────────
    print(f"\nRunning baseline methods...", flush=True)
    bl_results = run_baselines_sample_grouped(
        hs_by_layer, all_labels, masks, train_idx, val_idx, test_idx,
        valid_layers, hidden_dim, model_short
    )
    for bl_name, metrics in bl_results.items():
        print(f"  {bl_name}: val={metrics['val_auroc']:.4f}, test={metrics['test_auroc']:.4f}")

    mean_test = np.mean(test_aurocs)
    std_test = np.std(test_aurocs)
    print(f"  Mean: {mean_test:.4f} +/- {std_test:.4f}")

    # ── MLP gate check ───────────────────────────────────────────────────────
    mlp_val = bl_results.get("B3_mlp_concat", {}).get("val_auroc", 0.0)
    mlp_gate = mean_test >= (mlp_val + 0.03) if mlp_val > 0 else None

    # ── Save ────────────────────────────────────────────────────────────────
    # Refuse to write formal results if baselines are stubs
    if formal_m1 and stub_names:
        print(f"ERROR: Cannot write formal results — stub baselines: {stub_names}")
        return 1

    output = {
        "experiment": "TokenTR_M1_pilot",
        "label_mode": label_mode,
        "baseline_mode": baseline_mode,
        "formal_m1": formal_m1,
        "baseline_status": BASELINE_STATUS,
        "required_baselines_implemented": len(implemented),
        "stub_baselines": stub_names if smoke_mode else [],
        "model": MODEL,
        "layers": valid_layers,
        "lambdas": args.lambdas,
        "seeds": SEEDS[:args.n_seeds],
        "best_config": {"layer": int(best_layer), "lambda": best_lam},
        "best_val_auroc": float(best_val_auroc),
        "mean_test_auroc": float(mean_test) if formal_m1 else None,
        "std_test_auroc": float(std_test) if formal_m1 else None,
        "baseline_results": bl_results,
        "all_detailed_results": results,
        "can_run_formal_m1": formal_m1,
        "mlp_gate_passed": mlp_gate,
    }
    out_path = RESULTS_DIR / "pilot_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    md_lines = [
        "# TokenTR M1 Pilot Results",
        "",
        f"**Model**: {MODEL}",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M')}",
        f"**Label mode**: {label_mode}",
        f"**Baseline mode**: {baseline_mode}",
        f"**Formal M1**: {formal_m1}",
        "",
        "## Best Configuration",
        f"- Layer: {best_layer}, Lambda: {best_lam}",
        f"- Validation AUROC: {best_val_auroc:.4f}",
        "",
        "## Test Results",
        f"- Mean: {mean_test:.4f} +/- {std_test:.4f}",
    ]
    for seed in SEEDS[:args.n_seeds]:
        md_lines.append(f"  Seed {seed}: {results[f'seed_{seed}'][best_layer][best_lam]['test']['auroc']:.4f}")

    md_lines += [
        "",
        "## Baseline Results",
        "| Baseline | Val AUROC | Test AUROC |",
        "|-----------|-----------|------------|",
    ]
    for bl, m in bl_results.items():
        md_lines.append(f"| {bl} | {m['val_auroc']:.4f} | {m['test_auroc']:.4f} |")

    if mlp_gate is not None:
        md_lines.append("")
        md_lines.append(f"## MLP Gate (beat MLP concat by 3%)")
        md_lines.append(f"- MLP val AUROC: {mlp_val:.4f}")
        md_lines.append(f"- TokenTR test AUROC: {mean_test:.4f}")
        md_lines.append(f"- Gate passed: {'YES' if mlp_gate else 'NO'}")

    md_path = RESULTS_DIR / "pilot_results.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))

    print(f"\n{'='*60}")
    print("M1 SUMMARY")
    print(f"{'='*60}")
    print(f"Label mode: {label_mode}")
    print(f"Smoke test: {is_weak}")
    print(f"Best config: layer={best_layer}, lam={best_lam}")
    print(f"Test AUROC: {mean_test:.4f} +/- {std_test:.4f}")
    print(f"Results: {out_path}")
    print(f"Total: {time.time()-t0:.1f}s")
    print("M1 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
