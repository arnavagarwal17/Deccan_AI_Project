"""
reward/score.py
Pure function reward scorer:
score(spec: dict, submission_dir: str, capture_dir: str | None = None) -> dict
Calculates binary gates and continuous quality metrics without importing or executing submission code.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

from renderer.capture import capture_submission
from reward.gates import evaluate_gates
from reward.render_signals import compute_render_signals
from reward.code_signals import compute_code_signals


def load_weights() -> Dict[str, Any]:
    weights_path = Path(__file__).parent / "weights.yaml"
    if weights_path.exists():
        return yaml.safe_load(weights_path.read_text(encoding="utf-8"))
    return {}


def score(spec: Dict[str, Any], submission_dir: str, capture_dir: Optional[str] = None) -> Dict[str, Any]:
    weights = load_weights()
    sub_path = Path(submission_dir).resolve()
    index_file = sub_path / "index.html"
    html_content = index_file.read_text(encoding="utf-8", errors="replace") if index_file.exists() else ""

    # Ensure capture output exists
    if capture_dir is None:
        cap_path = sub_path / "_capture"
    else:
        cap_path = Path(capture_dir).resolve()

    trace_file = cap_path / "trace.json"
    if not trace_file.exists() or not list(cap_path.glob("frame_*.png")):
        cap_path.mkdir(parents=True, exist_ok=True)
        asyncio.run(capture_submission(submission_dir=str(sub_path), output_dir=str(cap_path), frames=8))

    trace = json.loads(trace_file.read_text(encoding="utf-8")) if trace_file.exists() else {}

    # 1. Evaluate binary gates
    gate_results = evaluate_gates(spec=spec, trace=trace, html_content=html_content)
    gates = gate_results["gates"]
    gate_pass = gate_results["gate_pass"]
    notes = gate_results["notes"]

    # 2. Compute continuous signal families conditioned on spec
    render_res = compute_render_signals(capture_dir=str(cap_path), spec=spec, weights=weights)
    code_res = compute_code_signals(html_content=html_content, trace=trace, spec=spec, weights=weights)

    render_score = render_res["family_score"]
    code_score = code_res["family_score"]
    judge_score = None  # Model judge omitted; reserved slot set to null

    # Family weights: 0.59 render + 0.41 code (judge=0.0 omitted)
    fam_weights = weights.get("families", {})
    w_render = fam_weights.get("render", 0.59)
    w_code = fam_weights.get("code", 0.41)
    quality_raw = (render_score * w_render + code_score * w_code) / (w_render + w_code)
    quality = round(float(quality_raw), 4)

    # Multiplicative gate enforcement: if any gate fails, quality is 0 and reward is 0
    if not gate_pass:
        final_quality = 0.0
        reward_binary = 0
    else:
        final_quality = quality
        reward_binary = 1

    family_breakdown = {
        "render": {
            "score": round(render_score, 4),
            "sub_signals": {k: round(v, 4) for k, v in render_res["sub_signals"].items()},
            "diagnostics": render_res["diagnostics"],
        },
        "code": {
            "score": round(code_score, 4),
            "sub_signals": {k: round(v, 4) for k, v in code_res["sub_signals"].items()},
            "diagnostics": code_res["diagnostics"],
        },
        "judge": None,
    }

    return {
        "gates": gates,
        "gate_pass": gate_pass,
        "families": {
            "render": round(render_score, 4),
            "code": round(code_score, 4),
            "judge": None,
        },
        "family_breakdown": family_breakdown,
        "quality": final_quality,
        "reward_binary": reward_binary,
        "notes": notes,
    }


def to_ctrf(score_result: Dict[str, Any]) -> Dict[str, Any]:
    tests = []
    passed_count = 0
    failed_count = 0

    for gate_name, passed in score_result["gates"].items():
        if passed:
            passed_count += 1
            status = "passed"
            msg = f"Gate {gate_name} passed successfully."
        else:
            failed_count += 1
            status = "failed"
            msg = f"Gate {gate_name} failed check."

        tests.append({
            "name": gate_name,
            "status": status,
            "duration": 0,
            "message": msg,
        })

    return {
        "results": {
            "tool": {"name": "harbor-webgl-verifier"},
            "summary": {
                "tests": len(tests),
                "passed": passed_count,
                "failed": failed_count,
            },
            "tests": tests,
            "extra": {
                "reward_binary": score_result["reward_binary"],
                "gate_pass": score_result["gate_pass"],
                "quality": score_result["quality"],
                "families": score_result["families"],
                "family_breakdown": score_result["family_breakdown"],
                "notes": score_result["notes"],
            },
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate WebGL submission reward")
    parser.add_argument("--submission", required=True, help="Directory containing submission index.html")
    parser.add_argument("--config", required=True, help="Path to grader_config.json or brief.json")
    parser.add_argument("--capture", default=None, help="Path to pre-captured frame directory")
    parser.add_argument("--out", default=None, help="Output path for ctrf.json report")

    args = parser.parse_args()
    cfg_path = Path(args.config)
    spec = json.loads(cfg_path.read_text(encoding="utf-8"))

    res = score(spec=spec, submission_dir=args.submission, capture_dir=args.capture)
    ctrf = to_ctrf(res)

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(ctrf, indent=2), encoding="utf-8")

    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

