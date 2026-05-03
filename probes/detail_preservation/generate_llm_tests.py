#!/usr/bin/env python
"""
LLM Faithfulness Test — verify that an LLM can produce numerically faithful
explanations from explicit numerical hints (from Statistics Module).
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synthetic_data import generate_dataset
from statistics_module import extract_hints


def make_prompt(hints, anomaly_type):
    hints_text = "\n".join(h.to_text() for h in hints[:3])

    return f"""You are a time series anomaly explanation system. Given numerical hints extracted from sensor data, generate a concise one-sentence explanation.

INPUT (numerical hints):
{hints_text}

OUTPUT: A single sentence identifying: which sensor was anomalous, the anomaly type (approximated as {anomaly_type}), the approximate deviation magnitude in sigma, and the position. Keep it concise."""


def main():
    dataset = generate_dataset(
        n_timesteps=1000, n_sensors=10, n_anomalies=5,
        window_size=100, anomaly_strength_range=(3.0, 8.0), seed=42,
    )
    normal_means, normal_stds = dataset.get_normal_statistics()

    test_cases = []
    for idx, anomaly in enumerate(dataset.anomalies):
        window = anomaly.values
        hints = extract_hints(window, normal_means, normal_stds, dataset.sensor_names, z_threshold=2.5)
        prompt = make_prompt(hints, anomaly.anomaly_type)
        test_cases.append({
            "id": idx + 1,
            "ground_truth": anomaly.ground_truth["expected_text"],
            "prompt": prompt,
        })

    # Output as JSON
    print(json.dumps({"test_cases": test_cases}, indent=2))


if __name__ == "__main__":
    main()
