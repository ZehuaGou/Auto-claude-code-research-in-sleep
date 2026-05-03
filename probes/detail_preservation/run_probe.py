#!/usr/bin/env python
"""
Detail-Preservation Probe (Block 0).

Pipeline:
1. Generate synthetic TS with known anomalies
2. Extract numerical hints via Statistics Module
3. Compute hint accuracy vs ground truth
4. Output structured test cases for LLM faithfulness evaluation
"""
import json
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from synthetic_data import generate_dataset, AnomalyRecord
from statistics_module import extract_hints, NumericalHint


def compute_hint_accuracy(
    hint: NumericalHint,
    ground_truth: dict,
    normal_stds: np.ndarray,
) -> dict:
    """Compare extracted hint against ground truth."""
    gt_mag = ground_truth["magnitude_sigma"]
    gt_sensor = ground_truth["sensor_id"]
    gt_pos = ground_truth["timestamp"]

    mag_error = abs(hint.deviation_score - gt_mag) / max(gt_mag, 1e-8) * 100
    sensor_match = hint.sensor_id == gt_sensor

    return {
        "sensor_correct": sensor_match,
        "magnitude_gt": gt_mag,
        "magnitude_extracted": hint.deviation_score,
        "magnitude_error_pct": round(float(mag_error), 2),
        "pattern_classified": hint.pattern_type,
        "pattern_expected": ground_truth.get("anomaly_type", "unknown"),
    }


def main():
    print("=" * 60)
    print("Block 0: Detail-Preservation Probe")
    print("=" * 60)

    # --- Generate synthetic data ---
    print("\n[1/4] Generating synthetic multivariate TS with known anomalies...")
    dataset = generate_dataset(
        n_timesteps=1000,
        n_sensors=10,
        n_anomalies=5,
        window_size=100,
        anomaly_strength_range=(3.0, 8.0),
        seed=42,
    )
    print(f"  Shape: {dataset.data.shape}")
    print(f"  Sensors: {dataset.sensor_names}")
    print(f"  Anomalies injected: {len(dataset.anomalies)}")

    # --- Compute normal statistics ---
    print("\n[2/4] Computing normal statistics...")
    normal_means, normal_stds = dataset.get_normal_statistics()
    for i in range(dataset.n_sensors):
        print(f"  {dataset.sensor_names[i]}: μ={normal_means[i]:.3f}, σ={normal_stds[i]:.3f}")

    # --- Extract hints and evaluate accuracy ---
    print("\n[3/4] Extracting numerical hints and computing accuracy...")
    results = []
    all_passed = True

    for idx, anomaly in enumerate(dataset.anomalies):
        window = anomaly.values
        hints = extract_hints(window, normal_means, normal_stds, dataset.sensor_names, z_threshold=2.5)

        print(f"\n  --- Anomaly {idx+1}: {anomaly.anomaly_type} ---")
        print(f"  Ground truth: sensor={anomaly.ground_truth['sensor_name']}, "
              f"magnitude={anomaly.magnitude_sigma:.2f}σ, t={anomaly.timestamp}")

        if not hints:
            print(f"  ❌ No hints extracted (missed anomaly)")
            all_passed = False
            continue

        # Best hint (highest deviation)
        best_hint = hints[0]
        accuracy = compute_hint_accuracy(best_hint, anomaly.ground_truth, normal_stds)

        result = {
            "anomaly_id": idx + 1,
            "anomaly_type": anomaly.anomaly_type,
            "ground_truth": anomaly.ground_truth,
            "extracted_hint": {
                "sensor": best_hint.to_text(),
                "magnitude": best_hint.deviation_score,
                "pattern": best_hint.pattern_type,
            },
            "accuracy": accuracy,
        }
        results.append(result)

        # Status
        sensor_ok = accuracy["sensor_correct"]
        mag_ok = accuracy["magnitude_error_pct"] < 10.0

        if sensor_ok and mag_ok:
            print(f"  ✅ hint: {best_hint.to_text()}")
            print(f"     magnitude error: {accuracy['magnitude_error_pct']:.1f}%")
        else:
            all_passed = False
            print(f"  ❌ hint: {best_hint.to_text()}")
            print(f"     magnitude error: {accuracy['magnitude_error_pct']:.1f}%")
            if not sensor_ok:
                print(f"     WRONG sensor: extracted #{best_hint.sensor_id}")
            if not mag_ok:
                print(f"     WRONG magnitude: error > 10%")

    # --- Save results for LLM testing ---
    print("\n[4/4] Saving probe results...")
    output = {
        "config": {
            "n_timesteps": dataset.n_timesteps,
            "n_sensors": dataset.n_sensors,
            "n_anomalies": len(dataset.anomalies),
            "window_size": 100,
        },
        "normal_statistics": {
            "means": normal_means.tolist(),
            "stds": normal_stds.tolist(),
            "sensor_names": dataset.sensor_names,
        },
        "results": results,
        "all_extracted_hints_passed": all_passed,
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Saved to: {out_path}")

    # --- Summary ---
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ VERDICT: Statistics Module accurately preserves numerical detail.")
        print("   All anomalies detected with correct sensor ID and <10% magnitude error.")
    else:
        print("❌ VERDICT: Some anomalies missed or inaccurate.")
    print("=" * 60)

    # --- Generate LLM test prompts ---
    print("\n\n--- LLM Faithfulness Test Prompts ---")
    print("(Feed these to the LLM to test numerical faithfulness)\n")

    for idx, anomaly in enumerate(dataset.anomalies):
        window = anomaly.values
        hints = extract_hints(window, normal_means, normal_stds, dataset.sensor_names, z_threshold=2.5)

        if hints:
            hints_text = "\n".join(h.to_text() for h in hints[:3])
        else:
            hints_text = "No significant deviation detected."

        prompt = f"""SYSTEM: You are a time series anomaly explanation system. Given numerical hints from sensor data, generate a concise explanation of what happened.

INPUT (numerical hints):
{hints_text}

OUTPUT: Explain in one sentence: Which sensor was anomalous, what type of anomaly, the deviation magnitude, and at what position (peak_at) it occurred."""

        print(f"-- Test Case {idx+1}: {anomaly.ground_truth['expected_text']} --")
        print(prompt)
        print()


if __name__ == "__main__":
    main()
