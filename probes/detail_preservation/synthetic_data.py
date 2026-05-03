"""
Synthetic multivariate time series with known anomalies for detail-preservation probe.

Generates:
- 10 sensor channels with seasonality + noise + trend
- 3 types of anomalies: point spike, level shift, pattern change
- Exact ground-truth deviation values for each anomaly
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

ANOMALY_TYPES = ["point_spike", "level_shift", "pattern_change"]


@dataclass
class AnomalyRecord:
    anomaly_type: str
    sensor_id: int
    timestamp: int
    magnitude_sigma: float
    ground_truth: dict
    window_start: int
    window_end: int
    values: np.ndarray  # shape: (window_len, n_sensors)


@dataclass
class SyntheticDataset:
    data: np.ndarray  # shape: (T, C)
    n_sensors: int
    n_timesteps: int
    anomalies: List[AnomalyRecord]
    sensor_names: List[str]

    def get_normal_statistics(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return per-sensor mean and std of normal (non-anomalous) region."""
        anomaly_mask = np.zeros(self.n_timesteps, dtype=bool)
        for a in self.anomalies:
            anomaly_mask[a.timestamp] = True
        normal = self.data[~anomaly_mask]
        return normal.mean(axis=0), normal.std(axis=0)


def _generate_sensor_signal(
    n_timesteps: int,
    freq: float,
    noise_scale: float,
    trend_slope: float,
    rng: np.random.Generator,
) -> np.ndarray:
    t = np.arange(n_timesteps)
    seasonal = np.sin(2 * np.pi * freq * t)
    noise = noise_scale * rng.standard_normal(n_timesteps)
    trend = trend_slope * t
    return seasonal + noise + trend


def generate_dataset(
    n_timesteps: int = 1000,
    n_sensors: int = 10,
    n_anomalies: int = 5,
    window_size: int = 100,
    anomaly_strength_range: Tuple[float, float] = (3.0, 8.0),
    seed: int = 42,
) -> SyntheticDataset:
    rng = np.random.RandomState(seed)

    sensor_names = [f"sensor_{i}" for i in range(n_sensors)]

    # --- Generate normal signals ---
    data = np.zeros((n_timesteps, n_sensors))
    for c in range(n_sensors):
        freq = rng.uniform(0.01, 0.05)
        noise_scale = rng.uniform(0.1, 0.3)
        trend_slope = rng.uniform(-0.001, 0.001)
        data[:, c] = _generate_sensor_signal(n_timesteps, freq, noise_scale, trend_slope, rng)

    # --- Compute normal stats for anomaly injection ---
    mu = data.mean(axis=0)
    sigma = data.std(axis=0)
    sigma = np.clip(sigma, 0.01, None)  # avoid division by zero

    # --- Inject anomalies ---
    anomaly_records = []
    # pick timestamps spread across the series, avoiding boundaries
    min_gap = n_timesteps // n_anomalies
    possible_positions = list(range(window_size, n_timesteps - window_size, min_gap))
    rng.shuffle(possible_positions)
    positions = sorted(possible_positions[:n_anomalies])

    for idx, t_pos in enumerate(positions):
        sensor_id = rng.randint(0, n_sensors)
        magnitude = rng.uniform(*anomaly_strength_range)
        anomaly_type = ANOMALY_TYPES[idx % len(ANOMALY_TYPES)]

        anomaly_value = mu[sensor_id] + magnitude * sigma[sensor_id]

        original = data[t_pos, sensor_id].copy()

        if anomaly_type == "point_spike":
            data[t_pos, sensor_id] = anomaly_value
        elif anomaly_type == "level_shift":
            shift_len = rng.randint(5, 15)
            end = min(t_pos + shift_len, n_timesteps)
            data[t_pos:end, sensor_id] = anomaly_value
        elif anomaly_type == "pattern_change":
            # Amplify the signal for a short window
            amp_len = rng.randint(10, 20)
            end = min(t_pos + amp_len, n_timesteps)
            data[t_pos:end, sensor_id] *= magnitude / 3.0
            anomaly_value = float(magnitude)  # store as relative amplification

        ws = max(0, t_pos - window_size // 2)
        we = min(n_timesteps, t_pos + window_size // 2)

        record = AnomalyRecord(
            anomaly_type=anomaly_type,
            sensor_id=sensor_id,
            timestamp=t_pos,
            magnitude_sigma=float(magnitude),
            ground_truth={
                "sensor_id": sensor_id,
                "sensor_name": sensor_names[sensor_id],
                "timestamp": t_pos,
                "magnitude_sigma": float(magnitude),
                "expected_text": (
                    f"sensor_{sensor_id}: {anomaly_type}, "
                    f"deviation={magnitude:.2f}σ at t={t_pos}"
                ),
            },
            window_start=ws,
            window_end=we,
            values=data[ws:we, :].copy(),
        )
        anomaly_records.append(record)

    return SyntheticDataset(
        data=data,
        n_sensors=n_sensors,
        n_timesteps=n_timesteps,
        anomalies=anomaly_records,
        sensor_names=sensor_names,
    )
