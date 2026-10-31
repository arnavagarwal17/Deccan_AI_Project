"""
pipeline/render_instruction.py
Renders agent-facing instruction.md with all grader thresholds, gate names, and tolerances stripped.
Enforces an automated leak linter ensuring no internal verifier secrets leak to the agent.
"""

import re
from typing import Dict, Any, List
from pipeline.spec import ConstraintSpec


def render_instruction_content(spec: ConstraintSpec, brief_prose: str) -> str:
    title = spec.required_copy[0] if spec.required_copy else "Landing Page"
    cat_clean = spec.product_category.replace("-", " ").title()

    palette_lines = "\n".join([f"- `{c}`" for c in spec.palette])
    copy_lines = "\n".join([f"- `{c}`" for c in spec.required_copy])

    instruction = f"""# {title} WebGL Landing Page

## Overview
You are tasked with building a high-performance single-file animated WebGL landing page for **{title}** ({cat_clean}).
The aesthetic direction is **{spec.mood}**. Review the creative brief below for context.

---

### Creative Brief
{brief_prose}

---

## Technical Deliverable & Environment Rules
1. **Single File**: Implement your entire application inside `index.html`.
2. **Offline Assets Only**: You must use the local Three.js build at `vendor/three.min.js`. Do not import any remote libraries or load fonts/images over the network. External network traffic is blocked by client policy.
3. **No Web Workers**: All animation and rendering logic must run client-side on the main browser thread.

## Visual & Content Requirements

### Required Copy
The rendered page must visibly display the following exact copy strings within semantic DOM elements:
{copy_lines}

### Color Palette
The visual composition (3D scene, background, materials, and typography) must adhere strictly to this palette:
{palette_lines}

### Animation, Interaction & Accessibility
- **Intro Sequence**: Implement a smooth introductory animation sequence that gracefully reveals the scene elements. Ensure the motion settles cleanly without abrupt jumps.
- **Interaction**: The scene should react smoothly to pointer movements ({spec.interaction}).
- **Accessibility & Contrast**: Ensure all typography overlay elements maintain strong readability and high contrast against the 3D animated canvas.
- **Vestibular Motion Safety**: Respect user accessibility preferences by honoring `prefers-reduced-motion` media queries.
"""
    return instruction.strip()


def lint_instruction_leaks(instruction_text: str, grader_config: Dict[str, Any]) -> List[str]:
    leaks = []
    text_lower = instruction_text.lower()

    # 1. Gate names must never leak
    gates = grader_config.get("gates", [])
    for gate in gates:
        if gate.lower() in text_lower:
            leaks.append(f"Gate name leaked: '{gate}'")

    # 2. Thresholds and internal parameters must never leak
    thresholds = grader_config.get("thresholds", {})

    # Numeric thresholds
    leakable_numbers = []
    if "first_frame_ms_max" in thresholds:
        leakable_numbers.append(("first_frame_ms_max", str(thresholds["first_frame_ms_max"])))
    if "max_draw_calls" in thresholds:
        leakable_numbers.append(("max_draw_calls", str(thresholds["max_draw_calls"])))
    if "palette_tolerance" in thresholds:
        leakable_numbers.append(("palette_tolerance", str(thresholds["palette_tolerance"])))
    if "min_contrast_ratio" in thresholds:
        leakable_numbers.append(("min_contrast_ratio", str(thresholds["min_contrast_ratio"])))

    # Motion budget window
    budget = thresholds.get("motion_budget_ms", [])
    for b in budget:
        leakable_numbers.append(("motion_budget_ms", str(b)))

    for label, num_str in leakable_numbers:
        # Check whole word match for the number to avoid false positives on hex letters
        pattern = r"\b" + re.escape(num_str) + r"\b"
        if re.search(pattern, instruction_text):
            leaks.append(f"Threshold leaked: {label}='{num_str}'")

    return leaks


def render_and_verify_instruction(spec: ConstraintSpec, brief_prose: str, grader_config: Dict[str, Any]) -> str:
    instruction = render_instruction_content(spec, brief_prose)
    leaks = lint_instruction_leaks(instruction, grader_config)
    if leaks:
        raise ValueError(f"Information leak detected in instruction for {spec.task_id}:\n" + "\n".join(leaks))
    return instruction

