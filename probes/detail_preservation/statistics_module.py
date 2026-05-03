"""
Statistics Module v2: Extract numerical hints from TS windows.

Three-pronged detection:
1. Z-score: point_spike, level_shift detection via max deviation
2. Rolling variance ratio: pattern_change (amplitude modulation) detection
3. CUSUM: cumulative shift / drift detection

Deterministic (no learned parameters).
"""
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np


@dataclass
class NumericalHint:
    sensor_id: int
    sensor_name: str
    deviation_score: float  # unified anomaly magnitude from best detector
    peak_position: int       # position within window
    window_mean: float
    window_std: float
    pattern_type: str        # "point_spike", "level_shift", "pattern_change", "drift"
    detection_method: str    # "z_score", "variance_ratio", "cusum"

    def to_text(self) -> str:
        return (
            f"[{self.sensor_name}] "
            f"score={self.deviation_score:.2f} "
            f"peak_at={self.peak_position} "
            f"window_mean={self.window_mean:.3f} "
            f"window_std={self.window_std:.3f} "
            f"pattern={self.pattern_type} "
            f"via={self.detection_method}"
        )


def _detect_z_score(
    values: np.ndarray, mu: float, sigma: float
) -> Tuple[float, int, str]:
    """Z-score based detection. Best for point_spike and level_shift."""
    z = (values - mu) / sigma
    max_z_idx = int(np.argmax(np.abs(z)))
    max_z = float(np.abs(z[max_z_idx]))

    # Distinguish spike vs level shift
    if max_z < 2.0:
        return 0.0, max_z_idx, "none"

    # Distinguish spike vs level shift by counting consecutive exceedances
    left = max_z_idx
    while left > 0 and np.abs(z[left - 1]) > 2.0:
        left -= 1
    right = max_z_idx
    while right < len(z) - 1 and np.abs(z[right + 1]) > 2.0:
        right += 1
    run_len = right - left + 1

    if run_len >= 5:
        pattern = "level_shift"
    else:
        pattern = "point_spike"

    return max_z, max_z_idx, pattern


def _detect_variance_ratio(
    values: np.ndarray, sigma: float, sub_window: int = 15
) -> Tuple[float, int, str]:
    """Rolling variance ratio detection. Best for pattern_change (amplitude modulation)."""
    n = len(values)
    if sigma < 1e-8 or n < sub_window * 2:
        return 0.0, 0, "none"

    normal_var = sigma * sigma
    variance_ratios = np.zeros(n - sub_window + 1)

    for i in range(len(variance_ratios)):
        local_var = np.var(values[i : i + sub_window])
        variance_ratios[i] = local_var / normal_var if normal_var > 1e-10 else 1.0

    max_ratio = float(np.max(variance_ratios))
    max_idx = int(np.argmax(variance_ratios)) + sub_window // 2

    if max_ratio > 2.0:  # return actual ratio above minimal threshold
        return max_ratio, max_idx, "pattern_change"
    return 0.0, max_idx, "none"


def _detect_cusum(
    values: np.ndarray, mu: float, sigma: float, drift: float = 0.25
) -> Tuple[float, int, str]:
    """CUSUM (Cumulative Sum) detection. Best for cumulative drift and subtle shifts."""
    if sigma < 1e-8:
        return 0.0, 0, "none"

    standardized = (values - mu) / sigma

    # Two-sided CUSUM
    s_high = np.maximum.accumulate(np.insert(standardized - drift, 0, 0))[:-1]
    s_low = np.maximum.accumulate(np.insert(-standardized - drift, 0, 0))[:-1]

    # CUSUM statistics
    cusum_stat = np.maximum(s_high, s_low)
    max_cusum = float(np.max(cusum_stat))
    max_idx = int(np.argmax(cusum_stat))

    if max_cusum > 3.0:
        return max_cusum, max_idx, "drift"
    return 0.0, max_idx, "none"


def extract_hints(
    window: np.ndarray,
    normal_means: np.ndarray,
    normal_stds: np.ndarray,
    sensor_names: List[str],
    z_threshold: float = 2.5,
    var_threshold: float = 3.0,
    cusum_threshold: float = 3.0,
) -> List[NumericalHint]:
    """
    Extract numerical hints from a TS window using three-pronged detection.

    Args:
        window: shape (window_len, n_sensors)
        normal_means: per-sensor mean during normal operation
        normal_stds: per-sensor std during normal operation
        sensor_names: list of sensor names
        z_threshold: minimum z-score to flag
        var_threshold: minimum variance ratio to flag
        cusum_threshold: minimum CUSUM to flag

    Returns:
        List of NumericalHint for sensors exceeding any threshold
    """
    n_sensors = window.shape[1]
    hints = []

    for s in range(n_sensors):
        sensor_values = window[:, s]
        mu = normal_means[s]
        sigma = normal_stds[s]

        if sigma < 1e-8:
            continue

        # Run all three detectors
        z_mag, z_pos, z_pattern = _detect_z_score(sensor_values, mu, sigma)
        v_mag, v_pos, v_pattern = _detect_variance_ratio(sensor_values, sigma)
        c_mag, c_pos, c_pattern = _detect_cusum(sensor_values, mu, sigma)

        if z_mag == 0.0 and v_mag == 0.0 and c_mag == 0.0:
            continue

        # --- Priority-based fusion ---
        # Always use z_score magnitude (sigma units, most interpretable).
        # Override pattern type based on which detector is most distinctive:
        # - z_score alone → point_spike or level_shift (based on run length)
        # - var_ratio high relative to z_score → pattern_change
        # - cusum high relative to z_score → drift

        z_strong = z_mag >= z_threshold
        v_strong = v_mag >= var_threshold
        c_strong = c_mag >= cusum_threshold

        if not z_strong and not v_strong and not c_strong:
            continue

        # Default: use z_score magnitude
        if z_strong:
            best_mag, best_pos, best_pattern = z_mag, z_pos, z_pattern
        elif v_strong:
            best_mag, best_pos, best_pattern = v_mag, v_pos, "pattern_change"
        else:
            best_mag, best_pos, best_pattern = c_mag, c_pos, "drift"

        best_method = "z_score"  # keep z_score as the primary magnitude source

        # Override pattern: when var_ratio is elevated relative to z_score,
        # and z_score is not dominating, it's likely amplitude modulation
        if v_mag > 2.0 and z_mag < 4.0 and v_mag > z_mag * 0.8:
            best_pattern = "pattern_change"

        # Override to drift when CUSUM is the dominant signal
        if c_mag > 3.0 and c_mag > z_mag * 1.5:
            best_pattern = "drift"

        # If only var_ratio or CUSUM fires (no z_score), use their magnitude
        if not z_strong:
            if v_strong:
                best_mag, best_pos = v_mag, v_pos
                best_method = "variance_ratio"
            elif c_strong:
                best_mag, best_pos = c_mag, c_pos
                best_method = "cusum"

        hint = NumericalHint(
            sensor_id=s,
            sensor_name=sensor_names[s],
            deviation_score=round(best_mag, 2),
            peak_position=best_pos,
            window_mean=float(np.mean(sensor_values)),
            window_std=float(np.std(sensor_values)),
            pattern_type=best_pattern,
            detection_method=best_method,
        )
        hints.append(hint)

    hints.sort(key=lambda h: h.deviation_score, reverse=True)
    return hints
