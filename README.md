# Deccan AI Project — WebGL Task Factory & Evaluation Pipeline

An automated framework designed to synthesize, validate, and benchmark LLM-generated interactive WebGL landing pages using local model inference (`qwen2.5:3b`), CPU-bound headless rendering (SwiftShader), and multi-variable deterministic reward evaluation.

# Deccan AI — RL Task Factory (Phases 1–4)

## What This Is
A pipeline that generates, validates, and scores distinct animated WebGL landing page tasks for training RL coding agents. Each task includes a machine-readable constraint spec, a human-readable agent instruction (leak-free), a grader config, a reference solution, and a Harbor-compatible bundle.

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\playwright.exe install chromium
```

> **Important**: always use `.\.venv\Scripts\python.exe` to invoke Python — the project dependencies are installed in the virtual environment, not the system Python.

## Make Targets

| Target | Description |
|--------|-------------|
| `make setup` | Install dependencies and download Chromium |
| `make pipeline COUNT=30 SEED=42` | Generate 30 task bundles into `tasks/` |
| `make quality` | Run 6 quality gates on all bundles |
| `make score` | Score reference solution for the demo task |
| `make rollouts` | Run full episode rollouts (Phase 7, TBD) |
| `make report-data` | Generate rollouts summary (Phase 7, TBD) |
| `make zip` | Package submission archive |

## Quick Verification (Phases 1–4)

```bash
# Phase 1: WebGL renders via SwiftShader CPU
.\.venv\Scripts\python.exe -m renderer.capture \
  --dir tasks/calm-wave-fintech/solution --frames 8 --out /tmp/cap

# Phase 2: Reward function unit tests
.\.venv\Scripts\python.exe -m unittest tests/test_reward.py

# Phase 3: Brief synthesis unit tests (uses disk cache, no Ollama needed)
.\.venv\Scripts\python.exe -m unittest tests/test_phase3.py

# Phase 4: Full pipeline run (uses cache — fast second run)
.\.venv\Scripts\python.exe -m pipeline.generate --count 30 --seed 42

# Phase 4: Score a generated task's reference solution
.\.venv\Scripts\python.exe -m reward.score \
  --submission tasks/calm-fintechapp-234645/solution \
  --config tasks/calm-fintechapp-234645/tests/grader_config.json
```

## Key Assumptions & Deviations

- **Harbor schema 2.0**: `task.toml` uses the fields described in the prompt. If the real schema differs in key names, the generator in `pipeline/generate.py` is the only file to update.
- **No GPU**: Chromium is launched with `--use-angle=swiftshader --enable-unsafe-swiftshader --disable-gpu-sandbox`. Verified on Playwright build v1148 (Chromium 131.0.6778.33).
- **`--no-sandbox`**: Used in the verifier image only (documented in `renderer/README.md`). NOT used in the agent environment image.
- **Model judge omitted**: The `judge` reward family is reserved (`weight=0.0` in `reward/weights.yaml`) and always returns `null`. A local vision model on CPU is too slow and noisy; the slot exists for a future pinned judge.
- **Ollama models**: `qwen2.5:3b` (brief) and `qwen2.5-coder:7b` (code), Ollama `v0.40.13`. All LLM calls are disk-cached in `pipeline/cache/`; re-running with the cache requires zero network calls.
- **Three.js r160**: Sourced from `unpkg.com/three@0.160.0/build/three.min.js` and vendored locally. CDN deprecation warning for `build/three.min.js` is logged as a console warning (not an error) and does not affect scoring.
- **Phases 5–8**: Docker images, full quality gate runner, rollouts, and report.md are not yet implemented. Stubs and inline comments indicate intended integration points.

