"""
reward/code_signals.py
Extracts AST-based and runtime code quality signals:
- duration_in_budget (AST numeric duration analysis vs spec motion budget)
- easing_allowed (AST easing function identification vs allowed list)
- draw_calls (runtime harness counter vs perf budget)
- frame_stability (variance of per-tick JS execution times)
- reduced_motion (AST/DOM evidence of prefers-reduced-motion handling)
"""

import re
from typing import Dict, Any, List, Tuple
import esprima
import numpy as np

KNOWN_EASINGS = {
    "linear", "ease", "easein", "easeout", "easeinout",
    "easeinoutquad", "easeinquad", "easeoutquad",
    "easeincubic", "easeoutcubic", "easeinoutcubic",
    "cubicbezier", "power1", "power2", "power3"
}


def extract_scripts(html_text: str) -> List[str]:
    pattern = re.compile(r"<script(?:\s+[^>]*)?>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    scripts = []
    for match in pattern.finditer(html_text):
        content = match.group(1).strip()
        if content:
            scripts.append(content)
    return scripts


def parse_ast_durations(scripts: List[str]) -> List[float]:
    durations = []
    for script in scripts:
        try:
            tree = esprima.parseScript(script, tolerant=True)
        except Exception:
            try:
                tree = esprima.parseModule(script, tolerant=True)
            except Exception:
                continue

        def walk(node):
            if not isinstance(node, dict) and not hasattr(node, "type"):
                return
            n_type = getattr(node, "type", None) or (node.get("type") if isinstance(node, dict) else None)

            # Variable declarations: const duration = 1800;
            if n_type == "VariableDeclarator":
                init = getattr(node, "init", None)
                id_node = getattr(node, "id", None)
                name = getattr(id_node, "name", "") if id_node else ""
                if init and getattr(init, "type", None) == "Literal":
                    val = getattr(init, "value", None)
                    if isinstance(val, (int, float)) and any(k in name.lower() for k in ["dur", "delay", "intro", "budget", "anim", "time"]):
                        # Convert second scale to ms if small
                        ms_val = val * 1000.0 if val < 20 else float(val)
                        durations.append(ms_val)

            # Property definitions: { duration: 1.8 }
            if n_type == "Property":
                key = getattr(node, "key", None)
                val_node = getattr(node, "value", None)
                k_name = getattr(key, "name", "") if key else ""
                if val_node and getattr(val_node, "type", None) == "Literal":
                    v = getattr(val_node, "value", None)
                    if isinstance(v, (int, float)) and "dur" in k_name.lower():
                        ms_val = v * 1000.0 if v < 20 else float(v)
                        durations.append(ms_val)

            # Recurse children
            for attr in ["body", "declarations", "expression", "arguments", "properties", "consequent", "alternate", "callee", "init"]:
                child = getattr(node, attr, None)
                if isinstance(child, list):
                    for c in child:
                        walk(c)
                elif child:
                    walk(child)

        walk(tree)
    return durations


def parse_ast_easings(scripts: List[str]) -> List[str]:
    easings_found = []
    for script in scripts:
        try:
            tree = esprima.parseScript(script, tolerant=True)
        except Exception:
            continue

        def walk(node):
            if not hasattr(node, "type"):
                return
            n_type = getattr(node, "type", None)

            if n_type in ("Identifier", "FunctionDeclaration"):
                name = getattr(node, "name", None) or getattr(getattr(node, "id", None), "name", "")
                norm = re.sub(r"[^a-zA-Z]", "", name.lower())
                if norm in KNOWN_EASINGS:
                    easings_found.append(name)

            if n_type == "Literal":
                val = str(getattr(node, "value", ""))
                norm = re.sub(r"[^a-zA-Z]", "", val.lower())
                if norm in KNOWN_EASINGS or "cubic-bezier" in val.lower():
                    easings_found.append(val)

            for attr in ["body", "declarations", "expression", "arguments", "properties", "init", "callee", "consequent", "alternate"]:
                child = getattr(node, attr, None)
                if isinstance(child, list):
                    for c in child:
                        walk(c)
                elif child:
                    walk(child)

        walk(tree)
    return easings_found


def evaluate_duration_budget(durations: List[float], budget_ms: List[int]) -> Tuple[float, Dict[str, Any]]:
    min_ms, max_ms = budget_ms[0], budget_ms[1]
    if not durations:
        # Fallback to midpoint assumption if no explicit duration variable was extracted
        return 0.7, {"detected_durations": [], "assumed_in_band": True}

    # Find the duration closest to the budget band
    best_dist = float("inf")
    best_dur = durations[0]
    for d in durations:
        if min_ms <= d <= max_ms:
            return 1.0, {"detected_durations": durations, "chosen_duration": d, "in_budget": True}
        dist = min(abs(d - min_ms), abs(d - max_ms))
        if dist < best_dist:
            best_dist = dist
            best_dur = d

    # Linear decay outside budget window
    decay_range = (max_ms - min_ms) or 1000.0
    score = max(0.0, 1.0 - (best_dist / decay_range))
    return float(score), {"detected_durations": durations, "chosen_duration": best_dur, "in_budget": False}


def evaluate_easing_allowed(detected: List[str], allowed: List[str]) -> Tuple[float, Dict[str, Any]]:
    if not detected:
        return 0.8, {"detected": [], "allowed": allowed}

    allowed_norm = {re.sub(r"[^a-zA-Z]", "", a.lower()) for a in allowed}
    valid_count = 0
    for d in detected:
        d_norm = re.sub(r"[^a-zA-Z]", "", d.lower())
        if d_norm in allowed_norm or any(a in d.lower() for a in allowed_norm):
            valid_count += 1

    score = valid_count / len(detected)
    return float(score), {"detected": detected, "valid_count": valid_count, "allowed": allowed}


def evaluate_draw_calls(max_draw_calls: int, budget: int) -> Tuple[float, Dict[str, Any]]:
    if max_draw_calls <= budget:
        return 1.0, {"max_draw_calls": max_draw_calls, "budget": budget}
    overshoot = max_draw_calls - budget
    score = max(0.0, 1.0 - (overshoot / float(budget)))
    return float(score), {"max_draw_calls": max_draw_calls, "budget": budget}


def evaluate_frame_stability(exec_times: List[float]) -> Tuple[float, Dict[str, Any]]:
    if len(exec_times) < 2:
        return 0.8, {"variance": 0.0}
    var = float(np.var(exec_times))
    # Normalized score: var=0 -> 1.0, var=10ms^2 -> 0.5
    score = 1.0 / (1.0 + (var / 10.0))
    return float(score), {"variance": var, "mean_ms": float(np.mean(exec_times))}


def evaluate_reduced_motion(html_text: str, required: bool) -> Tuple[float, Dict[str, Any]]:
    if not required:
        return 1.0, {"required": False}
    pattern = re.compile(r"prefers-reduced-motion", re.IGNORECASE)
    has_reduced_motion = bool(pattern.search(html_text))
    score = 1.0 if has_reduced_motion else 0.0
    return score, {"required": True, "present": has_reduced_motion}


def compute_code_signals(html_content: str, trace: Dict[str, Any], spec: Dict[str, Any], weights: Dict[str, Any]) -> Dict[str, Any]:
    scripts = extract_scripts(html_content)
    durations = parse_ast_durations(scripts)
    easings = parse_ast_easings(scripts)

    thresholds = spec.get("thresholds", {})
    budget_ms = spec.get("motion_budget_ms") or thresholds.get("motion_budget_ms", [1000, 2500])
    dur_score, dur_diag = evaluate_duration_budget(durations, budget_ms)

    allowed_easings = spec.get("allowed_easings") or thresholds.get("allowed_easings", ["ease-out", "cubic-bezier"])
    ease_score, ease_diag = evaluate_easing_allowed(easings, allowed_easings)

    perf_budget = spec.get("perf", {}).get("max_draw_calls") or thresholds.get("max_draw_calls", 40)
    max_calls = trace.get("max_draw_calls", 0)
    draw_score, draw_diag = evaluate_draw_calls(max_calls, perf_budget)

    exec_times = trace.get("frame_execution_times_ms", [])
    stab_score, stab_diag = evaluate_frame_stability(exec_times)

    req_reduced = (
        spec.get("a11y", {}).get("reduced_motion_respected")
        if "a11y" in spec
        else thresholds.get("reduced_motion_respected", True)
    )
    rm_score, rm_diag = evaluate_reduced_motion(html_content, req_reduced)

    code_w = weights.get("code_signals", {})
    w_dur = code_w.get("duration_in_budget", 0.25)
    w_ease = code_w.get("easing_allowed", 0.20)
    w_draw = code_w.get("draw_calls", 0.20)
    w_stab = code_w.get("frame_stability", 0.15)
    w_rm = code_w.get("reduced_motion", 0.20)

    family_score = (
        dur_score * w_dur +
        ease_score * w_ease +
        draw_score * w_draw +
        stab_score * w_stab +
        rm_score * w_rm
    ) / (w_dur + w_ease + w_draw + w_stab + w_rm)

    return {
        "family_score": float(np.clip(family_score, 0.0, 1.0)),
        "sub_signals": {
            "duration_in_budget": float(dur_score),
            "easing_allowed": float(ease_score),
            "draw_calls": float(draw_score),
            "frame_stability": float(stab_score),
            "reduced_motion": float(rm_score),
        },
        "diagnostics": {
            "duration": dur_diag,
            "easing": ease_diag,
            "draw_calls": draw_diag,
            "stability": stab_diag,
            "reduced_motion": rm_diag,
        },
    }
