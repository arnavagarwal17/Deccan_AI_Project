"""
pipeline/generate.py
End-to-end pipeline generator producing complete Harbor bundles:
Sampling -> Brief Synthesis -> Deduplication -> Grader Synthesis -> Instruction Rendering -> Solution Generation -> Bundle Writing.
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List

from pipeline.sample import sample_specs
from pipeline.synthesize_brief import synthesize_brief
from pipeline.dedup import deduplicate_briefs
from pipeline.synthesize_grader import synthesize_grader_config
from pipeline.render_instruction import render_and_verify_instruction
from pipeline.synthesize_solution import synthesize_solution


ENV_DOCKERFILE = """# syntax=docker/dockerfile:1
FROM alpine:3.19

RUN adduser -D -u 1000 agent
WORKDIR /workspace

COPY brief.json /workspace/brief.json
COPY scaffold /workspace/

RUN chown -R agent:agent /workspace
USER agent

CMD ["sh"]
"""

TEST_SH = """#!/usr/bin/env bash
set -e

mkdir -p /logs/verifier
# 1. Write fail-safe initial reward 0
echo "0" > /logs/verifier/reward.txt

SUBMISSION_DIR="${1:-/workspace}"
CONFIG_FILE="$(dirname "$0")/grader_config.json"
CAPTURE_DIR="/tmp/cap"

python -m renderer.capture --dir "$SUBMISSION_DIR" --out "$CAPTURE_DIR" --frames 8
python -m reward.score --submission "$SUBMISSION_DIR" --config "$CONFIG_FILE" --capture "$CAPTURE_DIR" --out /logs/verifier/ctrf.json

GATE_PASS=$(python -c 'import json; d=json.load(open("/logs/verifier/ctrf.json")); print(1 if d.get("results",{}).get("extra",{}).get("gate_pass") else 0)' 2>/dev/null || echo 0)

if [ "$GATE_PASS" = "1" ]; then
  echo "1" > /logs/verifier/reward.txt
fi
"""

TEST_DOCKERFILE = """# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    libgl1 libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \\
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \\
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 curl \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /verifier

COPY requirements.txt /verifier/requirements.txt
RUN pip install --no-cache-dir -r /verifier/requirements.txt && \\
    playwright install chromium

COPY renderer /verifier/renderer
COPY reward /verifier/reward
COPY tests /verifier/tests

RUN useradd -m -u 1000 verifier && \\
    mkdir -p /logs/verifier && \\
    chown -R verifier:verifier /verifier /logs/verifier

USER verifier
ENV PYTHONPATH=/verifier

ENTRYPOINT ["bash", "/verifier/tests/test.sh"]
"""


def render_task_toml(spec) -> str:
    tags_str = json.dumps(["webgl", "threejs", "frontend", "animation", spec.product_category])
    return f"""schema_version = "2.0"

[metadata]
name = "{spec.task_id}"
description = "Build a single-file animated WebGL landing page for {spec.required_copy[0]} ({spec.product_category})."
tags = {tags_str}
difficulty = "medium"

[resources]
cpu = 2
memory_mb = 2048
timeout_sec = 120
network = false

[verifier]
dockerfile = "tests/Dockerfile"
entrypoint = "tests/test.sh"

do_not_modify = [
  "vendor/three.min.js",
  "brief.json"
]
"""


def render_scaffold_html(spec) -> str:
    title = spec.required_copy[0] if spec.required_copy else "Landing Page"
    bg = spec.palette[0]
    fg = spec.palette[-1]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body, html {{ width: 100%; height: 100%; overflow: hidden; background: {bg}; color: {fg}; }}
    #webgl-container {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }}
    #hero-overlay {{ position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; }}
  </style>
</head>
<body>
  <div id="webgl-container"></div>
  <div id="hero-overlay"></div>
  <script src="vendor/three.min.js"></script>
  <script>
    // Developer implements WebGL landing page scene here
  </script>
</body>
</html>
"""


def build_bundle(spec, brief_record: Dict[str, Any], solution_record: Dict[str, Any], vendor_src: Path, out_dir: Path):
    bundle_dir = out_dir / spec.task_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # 1. task.toml
    (bundle_dir / "task.toml").write_text(render_task_toml(spec), encoding="utf-8")

    # 2. tests/grader_config.json
    tests_dir = bundle_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    grader_cfg = synthesize_grader_config(spec)
    (tests_dir / "grader_config.json").write_text(json.dumps(grader_cfg, indent=2), encoding="utf-8")
    (tests_dir / "test.sh").write_text(TEST_SH.strip() + "\n", encoding="utf-8")
    (tests_dir / "Dockerfile").write_text(TEST_DOCKERFILE.strip() + "\n", encoding="utf-8")

    # 3. instruction.md (verified through leak linter)
    instruction_text = render_and_verify_instruction(spec, brief_record["prose"], grader_cfg)
    (bundle_dir / "instruction.md").write_text(instruction_text, encoding="utf-8")

    # 4. environment/
    env_dir = bundle_dir / "environment"
    env_scaffold = env_dir / "scaffold"
    env_vendor = env_scaffold / "vendor"
    env_vendor.mkdir(parents=True, exist_ok=True)

    (env_dir / "Dockerfile").write_text(ENV_DOCKERFILE.strip() + "\n", encoding="utf-8")
    (env_dir / "brief.json").write_text(json.dumps(spec.model_dump(), indent=2), encoding="utf-8")
    (env_scaffold / "index.html").write_text(render_scaffold_html(spec), encoding="utf-8")
    shutil.copy(vendor_src, env_vendor / "three.min.js")

    # 5. solution/
    sol_dir = bundle_dir / "solution"
    sol_vendor = sol_dir / "vendor"
    sol_vendor.mkdir(parents=True, exist_ok=True)
    (sol_dir / "index.html").write_text(solution_record["html"], encoding="utf-8")
    shutil.copy(vendor_src, sol_vendor / "three.min.js")


def generate_pipeline(count: int = 30, seed: int = 42, tasks_dir: str = "tasks") -> Dict[str, Any]:
    vendor_src = Path("environment/scaffold/vendor/three.min.js")
    if not vendor_src.exists():
        raise FileNotFoundError(f"Missing vendor Three.js at {vendor_src}")

    target_tasks = Path(tasks_dir)
    target_tasks.mkdir(parents=True, exist_ok=True)

    # Sample and deduplicate until we reach the exact requested training count
    brief_records = []
    batch_idx = 0
    training_pool = []
    heldout_pool = []
    rejected_duplicates = []

    while len(training_pool) < count and batch_idx < 10:
        batch_size = max(20, int(count * 0.8))
        candidates_batch = sample_specs(count=batch_size, seed=seed + batch_idx * 1000)
        batch_idx += 1

        for s in candidates_batch:
            b = synthesize_brief(s, seed=seed)
            b["spec"] = s.model_dump()
            b["spec_obj"] = s
            brief_records.append(b)

        training_pool, heldout_pool, rejected_duplicates = deduplicate_briefs(brief_records, threshold=0.92)

    accepted_specs = [b["spec_obj"] for b in training_pool[:count]]
    accepted_briefs = training_pool[:count]

    # Generate solutions and assemble bundles for accepted training tasks
    bundles_created = []
    rejected_leaks = 0

    for spec, brief in zip(accepted_specs, accepted_briefs):
        sol = synthesize_solution(spec, seed=seed)
        try:
            build_bundle(spec, brief, sol, vendor_src, target_tasks)
            bundles_created.append(spec.task_id)
        except ValueError as leak_err:
            rejected_leaks += 1

    yield_data = {
        "count_requested": count,
        "seed": seed,
        "candidates_sampled": len(brief_records),
        "rejected_duplicate_similarity": len(rejected_duplicates),
        "rejected_leak": rejected_leaks,
        "heldout_count": len(heldout_pool),
        "accepted_count": len(bundles_created),
        "accepted_task_ids": bundles_created,
    }

    yield_file = Path("pipeline/yield.json")
    yield_file.write_text(json.dumps(yield_data, indent=2), encoding="utf-8")
    return yield_data


def main():
    parser = argparse.ArgumentParser(description="Generate full Harbor task bundles")
    parser.add_argument("--count", type=int, default=30, help="Number of tasks to generate")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic generator seed")
    parser.add_argument("--tasks-dir", default="tasks", help="Output directory for task bundles")
    args = parser.parse_args()

    res = generate_pipeline(count=args.count, seed=args.seed, tasks_dir=args.tasks_dir)
    print(f"Generated {res['accepted_count']} accepted tasks (held-out: {res['heldout_count']}) into {args.tasks_dir}/")
    print(f"Yield summary saved to pipeline/yield.json")


if __name__ == "__main__":
    main()
