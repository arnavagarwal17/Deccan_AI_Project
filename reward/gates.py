"""
reward/gates.py
Evaluates the five binary gates. If any gate fails, gate_pass is False,
reward is 0, and continuous quality scoring is bypassed.
"""

from typing import Dict, Any, List


def evaluate_gates(spec: Dict[str, Any], trace: Dict[str, Any], html_content: str) -> Dict[str, Any]:
    notes: List[str] = []
    gates: Dict[str, bool] = {
        "compiles": False,
        "webgl_context": False,
        "no_console_errors": False,
        "first_frame_under_budget": False,
        "required_copy_present": False,
    }

    # 1. compiles: HTML exists and no fatal shader/script compilation errors
    has_html = bool(html_content and len(html_content.strip()) > 0)
    shader_ok = trace.get("shader_link_ok", True)
    has_shader_errors = bool(trace.get("shader_errors"))

    if has_html and shader_ok and not has_shader_errors:
        gates["compiles"] = True
    else:
        notes.append("Gate 'compiles' failed: empty HTML or shader program link failure.")

    # 2. webgl_context: verified creation of WebGL context on a canvas
    webgl_created = bool(trace.get("webgl_created"))
    canvas_count = trace.get("canvas_count", 0)
    if webgl_created and canvas_count > 0:
        gates["webgl_context"] = True
    else:
        notes.append(f"Gate 'webgl_context' failed: webgl_created={webgl_created}, canvas_count={canvas_count}.")

    # 3. no_console_errors: zero console errors and no unpermitted Worker spawning
    console_errors = trace.get("console_errors", [])
    worker_spawned = trace.get("worker_spawn_attempted", False)
    if len(console_errors) == 0 and not worker_spawned:
        gates["no_console_errors"] = True
    else:
        notes.append(f"Gate 'no_console_errors' failed: {len(console_errors)} errors, worker_spawned={worker_spawned}.")

    # 4. first_frame_under_budget: first WebGL render timestamp within spec budget
    thresholds = spec.get("thresholds", {})
    perf_spec = spec.get("perf", {})
    max_first_frame_ms = (
        perf_spec.get("first_frame_ms")
        if "perf" in spec
        else thresholds.get("first_frame_ms_max", 250)
    )
    if max_first_frame_ms is None:
        max_first_frame_ms = 250
    first_frame_ms = trace.get("first_frame_ms")

    if first_frame_ms is not None and first_frame_ms <= max_first_frame_ms:
        gates["first_frame_under_budget"] = True
    else:
        notes.append(f"Gate 'first_frame_under_budget' failed: {first_frame_ms} ms vs max {max_first_frame_ms} ms.")

    # 5. required_copy_present: all required copy strings must appear in DOM
    required_copy = spec.get("required_copy", [])
    dom_elements = trace.get("dom_elements", [])
    rendered_texts = [el.get("text", "") for el in dom_elements]
    joined_dom_text = " ".join(rendered_texts).lower()

    missing_copy = []
    for req in required_copy:
        if req.lower() not in joined_dom_text:
            missing_copy.append(req)

    if not missing_copy and len(required_copy) > 0:
        gates["required_copy_present"] = True
    else:
        notes.append(f"Gate 'required_copy_present' failed. Missing: {missing_copy}.")

    gate_pass = all(gates.values())
    return {
        "gates": gates,
        "gate_pass": gate_pass,
        "notes": notes,
    }
