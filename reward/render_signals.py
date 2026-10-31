"""
reward/render_signals.py
Computes continuous render signals strictly from captured PNG frames and trace data:
- palette_adherence (CIELAB k-means with coverage anti-gaming)
- text_contrast (WCAG AA ratio on DOM text bounding boxes)
- temporal_motion (inter-frame diff vs mood band + smoothness CV)
- composition_balance (luminance center of mass distance)
"""

import math
from pathlib import Path
from typing import Dict, Any, List, Tuple
import cv2
import numpy as np


def hex_to_rgb(hex_str: str) -> Tuple[float, float, float]:
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0
    return (r, g, b)


def rgb_to_lab(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    # Standard sRGB to CIELAB via D65 illuminant
    def pivot(n):
        return (n / 12.92) if n <= 0.04045 else (((n + 0.055) / 1.055) ** 2.4)

    r, g, b = [pivot(c) for c in rgb]
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.00000
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t + 16.0 / 116.0)

    fx, fy, fz = f(x), f(y), f(z)
    L = max(0.0, 116.0 * fy - 16.0)
    a = 500.0 * (fx - fy)
    b_val = 200.0 * (fy - fz)
    return (L, a, b_val)


def delta_e(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    return math.sqrt((lab1[0] - lab2[0]) ** 2 + (lab1[1] - lab2[1]) ** 2 + (lab1[2] - lab2[2]) ** 2)


def evaluate_palette_adherence(frames: List[np.ndarray], palette_hex: List[str], tolerance: float) -> Tuple[float, Dict[str, Any]]:
    if not frames:
        return 0.0, {"error": "no frames"}

    # Subsample 20,000 pixels across frames for robust k-means
    sample_pixels = []
    step = max(1, len(frames) // 3)
    for frame in frames[::step]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        indices_y = np.linspace(0, h - 1, 70, dtype=int)
        indices_x = np.linspace(0, w - 1, 100, dtype=int)
        grid = rgb[np.ix_(indices_y, indices_x)].reshape(-1, 3)
        sample_pixels.append(grid)

    pixels = np.vstack(sample_pixels).astype(np.float32) / 255.0
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 0.2)
    _, labels, centers = cv2.kmeans(pixels, 5, None, criteria, 5, cv2.KMEANS_PP_CENTERS)

    spec_labs = [rgb_to_lab(hex_to_rgb(h)) for h in palette_hex]
    cluster_fractions = [(labels == i).mean() for i in range(5)]

    total_dist = 0.0
    distinct_matched = set()

    for i, center in enumerate(centers):
        c_lab = rgb_to_lab(tuple(center))
        dists = [delta_e(c_lab, s_lab) for s_lab in spec_labs]
        min_idx = int(np.argmin(dists))
        min_d = dists[min_idx]
        total_dist += min_d * cluster_fractions[i]

        # Check coverage for anti-gaming (cluster fraction between 0.05 and 0.70)
        if min_d <= tolerance and (0.05 <= cluster_fractions[i] <= 0.70):
            distinct_matched.add(min_idx)

    # Base score normalized by tolerance
    raw_score = max(0.0, min(1.0, 1.0 - (total_dist / (tolerance + 1e-5))))

    # Anti-gaming penalty if less than 3 distinct palette colors meet coverage
    gaming_penalty = 1.0
    if len(distinct_matched) < min(3, len(palette_hex)):
        gaming_penalty = 0.5

    final_score = raw_score * gaming_penalty
    return final_score, {
        "mean_lab_distance": float(total_dist),
        "distinct_colors_meeting_coverage": len(distinct_matched),
        "gaming_penalty": gaming_penalty,
    }


def compute_wcag_contrast(fg_rgb: Tuple[float, float, float], bg_rgb: Tuple[float, float, float]) -> float:
    def lum(c):
        return (c / 12.92) if c <= 0.03928 else (((c + 0.055) / 1.055) ** 2.4)

    l1 = 0.2126 * lum(fg_rgb[0]) + 0.7152 * lum(fg_rgb[1]) + 0.0722 * lum(fg_rgb[2])
    l2 = 0.2126 * lum(bg_rgb[0]) + 0.7152 * lum(bg_rgb[1]) + 0.0722 * lum(bg_rgb[2])
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


def evaluate_text_contrast(frame: np.ndarray, dom_elements: List[Dict[str, Any]], target_contrast: float) -> Tuple[float, Dict[str, Any]]:
    if frame is None or not dom_elements:
        return 0.5, {"ratios": [], "mean_contrast": 0.0}

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    h, w, _ = rgb.shape
    ratios = []

    for el in dom_elements:
        rect = el.get("rect", {})
        rx, ry, rw, rh = int(rect.get("x", 0)), int(rect.get("y", 0)), int(rect.get("width", 0)), int(rect.get("height", 0))
        if rw < 4 or rh < 4 or rx >= w or ry >= h:
            continue

        x0, y0 = max(0, rx), max(0, ry)
        x1, y1 = min(w, rx + rw), min(h, ry + rh)
        patch = rgb[y0:y1, x0:x1]
        if patch.size == 0:
            continue

        # Pixel luminance range inside the bounding rect captures text vs bg
        lums = 0.2126 * patch[:, :, 0] + 0.7152 * patch[:, :, 1] + 0.0722 * patch[:, :, 2]
        p95 = np.percentile(lums, 95)
        p05 = np.percentile(lums, 5)
        ratio = (p95 + 0.05) / (p05 + 0.05)
        ratios.append(float(ratio))

    if not ratios:
        return 0.5, {"ratios": [], "mean_contrast": 0.0}

    mean_contrast = float(np.mean(ratios))
    # Normalized score: reaches 1.0 at target_contrast
    norm_score = min(1.0, mean_contrast / target_contrast)
    return norm_score, {"ratios": ratios, "mean_contrast": mean_contrast}


def evaluate_temporal_motion(frames: List[np.ndarray], mood: str, mood_bands: Dict[str, List[float]]) -> Tuple[float, Dict[str, Any]]:
    if len(frames) < 2:
        return 0.0, {"diffs": [], "mean_diff": 0.0, "smoothness": 0.0}

    diffs = []
    for i in range(1, len(frames)):
        f_prev = cv2.cvtColor(frames[i - 1], cv2.COLOR_BGR2GRAY).astype(np.float32)
        f_curr = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY).astype(np.float32)
        diff = float(np.mean(np.abs(f_curr - f_prev)))
        diffs.append(diff)

    mean_diff = float(np.mean(diffs))
    # Anti-gaming: frozen page (< 0.01) scores 0.0; strobing (> 65.0) scores 0.1
    if mean_diff < 0.01:
        return 0.0, {"diffs": diffs, "mean_diff": mean_diff, "reason": "frozen_page"}
    if mean_diff > 65.0:
        return 0.1, {"diffs": diffs, "mean_diff": mean_diff, "reason": "strobing_detected"}

    band = mood_bands.get(mood.lower(), [2.0, 20.0])
    b_min, b_max = band[0], band[1]

    if b_min <= mean_diff <= b_max:
        intensity_score = 1.0
    elif mean_diff < b_min:
        intensity_score = max(0.0, mean_diff / b_min)
    else:
        overshoot = mean_diff - b_max
        intensity_score = max(0.2, 1.0 - (overshoot / 40.0))

    # Smoothness: lower CV (variance across frames) is better
    std_diff = float(np.std(diffs))
    cv_score = max(0.0, 1.0 - (std_diff / (mean_diff + 1e-4)))
    temporal_score = 0.6 * intensity_score + 0.4 * cv_score

    return float(temporal_score), {
        "diffs": diffs,
        "mean_diff": mean_diff,
        "intensity_score": intensity_score,
        "cv_score": cv_score,
    }


def evaluate_composition_balance(frame: np.ndarray) -> Tuple[float, Dict[str, Any]]:
    if frame is None:
        return 0.5, {}

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    total_mass = float(np.sum(gray))
    if total_mass == 0:
        return 0.5, {"distance": 0.0}

    h, w = gray.shape
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    cx = float(np.sum(x_coords * gray) / total_mass)
    cy = float(np.sum(y_coords * gray) / total_mass)

    target_cx = w / 2.0
    target_cy = h / 2.0
    dist = math.sqrt((cx - target_cx) ** 2 + (cy - target_cy) ** 2)
    max_dist = math.sqrt(target_cx ** 2 + target_cy ** 2)

    balance_score = max(0.0, min(1.0, 1.0 - (dist / max_dist)))
    return float(balance_score), {"cx": cx, "cy": cy, "distance": dist}


def compute_render_signals(capture_dir: str, spec: Dict[str, Any], weights: Dict[str, Any]) -> Dict[str, Any]:
    cap_path = Path(capture_dir)
    frame_files = sorted(list(cap_path.glob("frame_*.png")))
    frames = [cv2.imread(str(f)) for f in frame_files if f.is_file()]

    import json
    trace_path = cap_path / "trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else {}

    thresholds = spec.get("thresholds", {})
    palette = spec.get("palette", ["#0B192C", "#1E3E62", "#000000", "#F1F6F9"])
    tolerance = spec.get("palette_tolerance") or thresholds.get("palette_tolerance", 28.0)
    palette_score, palette_diag = evaluate_palette_adherence(frames, palette, tolerance)

    min_contrast = (
        spec.get("a11y", {}).get("min_contrast_ratio")
        if "a11y" in spec
        else thresholds.get("min_contrast_ratio", 4.5)
    )
    if min_contrast is None:
        min_contrast = 4.5
    f0 = frames[0] if frames else None
    contrast_score, contrast_diag = evaluate_text_contrast(f0, trace.get("dom_elements", []), min_contrast)

    mood = spec.get("mood", "calm")
    mood_bands = weights.get("mood_motion_bands", {})
    motion_score, motion_diag = evaluate_temporal_motion(frames, mood, mood_bands)

    balance_score, balance_diag = evaluate_composition_balance(f0)

    render_w = weights.get("render_signals", {})
    w_p = render_w.get("palette_adherence", 0.35)
    w_c = render_w.get("text_contrast", 0.25)
    w_m = render_w.get("temporal_motion", 0.25)
    w_b = render_w.get("composition_balance", 0.15)

    family_score = (
        palette_score * w_p +
        contrast_score * w_c +
        motion_score * w_m +
        balance_score * w_b
    ) / (w_p + w_c + w_m + w_b)

    return {
        "family_score": float(np.clip(family_score, 0.0, 1.0)),
        "sub_signals": {
            "palette_adherence": float(palette_score),
            "text_contrast": float(contrast_score),
            "temporal_motion": float(motion_score),
            "composition_balance": float(balance_score),
        },
        "diagnostics": {
            "palette": palette_diag,
            "contrast": contrast_diag,
            "motion": motion_diag,
            "balance": balance_diag,
        },
    }
