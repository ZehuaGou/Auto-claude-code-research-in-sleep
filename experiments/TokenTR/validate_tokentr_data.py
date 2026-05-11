"""
Data Validator for TokenTR experiments.

Validates dataset has required label structure and writes validation report.

Usage:
    python experiments/TokenTR/validate_tokentr_data.py \
        --dataset_path experiments/TokenTR/fixtures/tokentr_sanity.jsonl

Output:
    PASS_FORMAL_TOKEN_LABELS
    PASS_SPAN_LABELS
    PASS_WEAK_SAMPLE_LABELS_ONLY
    FAIL_NO_LABELS
    FAIL_SCHEMA
    experiments/TokenTR/reports/data_validation_report.json
"""

import argparse
import json
import sys
from pathlib import Path

VALID_LABEL_MODES = {"token", "span", "sentence", "sample_weak", "synthetic"}
FORMAL_MODES = {"token", "span", "sentence"}


def validate_dataset(rows):
    """
    Validate dataset for TokenTR requirements.
    Returns (verdict, report_dict).
    """
    report = {
        "n_samples": len(rows),
        "has_sample_id": False,
        "has_token_labels": False,
        "has_spans": False,
        "has_sentence_labels": False,
        "has_sample_hallu": False,
        "label_mode_detected": None,
        "hallu_prevalence": 0.0,
        "verdict": "FAIL_NO_LABELS",
        "can_run_formal_m1": False,
        "block_reason": None,
        "sample_issues": [],
    }

    # Check sample_id
    for i, row in enumerate(rows):
        if "sample_id" not in row:
            report["sample_issues"].append(f"Sample {i}: missing sample_id")

    if any("sample_id" in r for r in rows):
        report["has_sample_id"] = True

    # Check label fields — ALL rows must have the formal field (not just any row)
    has_token_labels = all("token_labels" in r for r in rows)
    has_spans = all("hallucination_spans" in r for r in rows)
    has_sample_hallu = all("is_hallucinated" in r for r in rows)
    has_sentence_labels = all("sentence_labels" in r for r in rows)

    report["has_token_labels"] = has_token_labels
    report["has_spans"] = has_spans
    report["has_sample_hallu"] = has_sample_hallu
    report["has_sentence_labels"] = has_sentence_labels

    hallu_count = sum(1 for r in rows if r.get("is_hallucinated", 0) == 1)
    report["hallu_prevalence"] = hallu_count / len(rows) if rows else 0.0

    # Determine verdict
    if has_token_labels:
        report["label_mode_detected"] = "token"
        report["verdict"] = "PASS_FORMAL_TOKEN_LABELS"
        report["can_run_formal_m1"] = True
    elif has_spans:
        report["label_mode_detected"] = "span"
        report["verdict"] = "PASS_SPAN_LABELS"
        report["can_run_formal_m1"] = True
    elif has_sentence_labels:
        report["label_mode_detected"] = "sentence"
        report["verdict"] = "FAIL_SENTENCE_REQUIRES_MAPPING"  # sentence requires verified mapping metadata
        report["can_run_formal_m1"] = False
        report["block_reason"] = "sentence mode requires verified sentence_token_mapping metadata"
    elif has_sample_hallu:
        report["label_mode_detected"] = "sample_weak"
        report["verdict"] = "PASS_WEAK_SAMPLE_LABELS_ONLY"
        report["can_run_formal_m1"] = False
        report["block_reason"] = "Only sample-level labels available; token-level detection not possible"
    else:
        report["verdict"] = "FAIL_NO_LABELS"
        report["block_reason"] = "No recognized label fields found (token_labels, hallucination_spans, is_hallucinated)"

    # Schema checks
    if report["sample_issues"]:
        report["verdict"] = "FAIL_SCHEMA"
        report["block_reason"] = f"Schema errors: {report['sample_issues'][:3]}"
        report["can_run_formal_m1"] = False

    return report["verdict"], report


def main():
    parser = argparse.ArgumentParser(description="Validate TokenTR dataset")
    parser.add_argument("--dataset_path", type=str, required=True,
                        help="Path to dataset JSON/JSONL file")
    parser.add_argument("--output_dir", type=str, default=None,
                        help="Directory to write report (default: experiments/TokenTR/reports)")
    args = parser.parse_args()

    p = Path(args.dataset_path)
    if not p.exists():
        print(f"FAIL_NO_LABELS")
        print(f"ERROR: dataset_path not found: {p}")
        return 1

    # Load
    if p.suffix == ".jsonl":
        rows = [json.loads(l) for l in open(p, encoding="utf-8")]
    elif p.suffix == ".json":
        rows = json.load(open(p, encoding="utf-8"))
    else:
        print(f"FAIL_SCHEMA")
        print(f"ERROR: unsupported file type: {p.suffix}")
        return 1

    verdict, report = validate_dataset(rows)

    # Print verdict
    print(f"\n{verdict}")
    print(f"  n_samples: {report['n_samples']}")
    print(f"  label_mode: {report['label_mode_detected']}")
    print(f"  can_run_formal_m1: {report['can_run_formal_m1']}")
    if report.get("block_reason"):
        print(f"  block_reason: {report['block_reason']}")
    print(f"  hallu_prevalence: {report['hallu_prevalence']:.3f}")
    if report.get("sample_issues"):
        print(f"  sample_issues: {report['sample_issues'][:3]}")

    # Write report
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = Path("experiments/TokenTR/reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "data_validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
