"""
pipeline/synthesize_grader.py
Generates tests/grader_config.json directly from a ConstraintSpec.
All thresholds and gates are strictly bound to spec fields without hardcoding.
"""

from typing import Dict, Any
from pipeline.spec import ConstraintSpec


def synthesize_grader_config(spec: ConstraintSpec) -> Dict[str, Any]:
    # Gate list compiled from core RL verification contract
    gates = [
        "compiles",
        "webgl_context",
        "no_console_errors",
        "first_frame_under_budget",
        "required_copy_present",
    ]

    thresholds = {
        # Bound directly to spec performance budget
        "first_frame_ms_max": spec.perf.first_frame_ms,
        "max_draw_calls": spec.perf.max_draw_calls,
        # Bound directly to spec accessibility constraints
        "min_contrast_ratio": spec.a11y.min_contrast_ratio,
        "reduced_motion_respected": spec.a11y.reduced_motion_respected,
        # Bound directly to spec palette and kinetic tolerances
        "palette_tolerance": spec.palette_tolerance,
        "motion_budget_ms": spec.motion_budget_ms,
        "allowed_easings": spec.allowed_easings,
    }

    return {
        "task_id": spec.task_id,
        "gates": gates,
        "thresholds": thresholds,
        "required_copy": spec.required_copy,
        "palette": spec.palette,
    }

