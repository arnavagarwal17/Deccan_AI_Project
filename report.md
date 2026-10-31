# Report — RL Task Factory (Phases 1–4)

> **Submission scope**: Phases 1–4 are complete and tested. Phases 5–8 (Docker, quality gates runner, rollouts, full report data) are not yet implemented. All numbers in this report are real measured values from code the system ran; nothing is fabricated.

---

## 1. What This Is

### Task Family
Every task in this factory asks a coding agent to write a **single-file animated WebGL landing page** for a generated company brief. The page must:
- Use the vendored Three.js r160 (`vendor/three.min.js`) with no network access
- Render a GPU-accelerated 3D scene within a CPU-only SwiftShader environment
- Display exact required copy strings in high-contrast DOM overlays
- Complete an introductory animation within a spec-bounded duration window
- Respond to pointer interaction (hover-tilt, scroll-parallax, etc.)
- Respect `prefers-reduced-motion` for vestibular accessibility

### Example Task (End to End)

**Task ID**: `calm-fintechapp-234645`

**Generated Constraint Spec** (`environment/brief.json`):
```json
{
  "task_id": "calm-fintechapp-234645",
  "product_category": "fintech-app",
  "mood": "calm",
  "palette": ["#0A192F", "#172A45", "#64FFDA", "#CCD6F6"],
  "palette_tolerance": 28.0,
  "required_copy": ["Aura Capital", "Autonomous Yield Intelligence", "Open Account"],
  "motion_budget_ms": [1500, 3000],
  "allowed_easings": ["ease-in-out", "cubic-bezier", "easeOutCubic"],
  "interaction": "hover-tilt",
  "perf": {"max_draw_calls": 40, "first_frame_ms": 150},
  "a11y": {"min_contrast_ratio": 4.5, "reduced_motion_respected": true}
}
```

**Generated Instruction** (`instruction.md`, excerpt — thresholds stripped):
```
# Aura Capital WebGL Landing Page
...implement a smooth introductory animation sequence that gracefully reveals
the scene elements. Ensure the motion settles cleanly...
Respect user accessibility preferences by honoring `prefers-reduced-motion`.
```

**Grader Output on Reference Solution** (measured):
```json
{
  "gates": { "compiles": true, "webgl_context": true, "no_console_errors": true,
             "first_frame_under_budget": true, "required_copy_present": true },
  "gate_pass": true,
  "families": { "render": 0.7688, "code": 0.9525, "judge": null },
  "quality": 0.8441,
  "reward_binary": 1
}
```

---

## 2. What Was Built

### Pipeline Architecture

```
taxonomy.yaml (axes)
    → sample.py (random.Random(seed) + incoherence rules)
    → synthesize_brief.py (qwen2.5:3b via Ollama, cached → fallback.py offline)
    → dedup.py (all-MiniLM-L6-v2 cosine similarity > 0.92 → reject; last 20% → heldout/)
    → synthesize_grader.py (spec fields → grader_config.json, no hardcoded thresholds)
    → render_instruction.py (brief prose + spec → instruction.md, leak linter enforced)
    → synthesize_solution.py (qwen2.5-coder:7b → fallback_solution.py offline)
    → generate.py (assembles full Harbor bundle, writes pipeline/yield.json)
```

### Reward System (Phase 2)
Five **multiplicative binary gates** (all must pass or reward = 0):
1. `compiles` — HTML non-empty, shader programs link without errors
2. `webgl_context` — WebGL canvas created and instrumented
3. `no_console_errors` — Zero console errors, no Worker spawning
4. `first_frame_under_budget` — First draw call within `perf.first_frame_ms`
5. `required_copy_present` — All required strings found in rendered DOM

Two **continuous signal families** (computed only when gates pass):
- **Render** (0.59 weight): palette adherence (CIELAB k-means, anti-gaming coverage check), text contrast (WCAG AA on DOM bounding boxes), temporal motion (inter-frame diff vs mood band), composition balance (luminance CoM)
- **Code** (0.41 weight): AST duration extraction, easing compliance, draw call budget, frame execution stability, reduced-motion presence
- **Judge** (0.0 weight, reserved): Omitted — a local vision model on CPU is too slow and noisy; slot exists in `weights.yaml` for a future pinned judge

### Determinism
- Rendering uses virtual time: `Date.now`, `performance.now`, and `requestAnimationFrame` are hooked in `renderer/harness.js`, advancing exactly 16.6667 ms per `window.__stepFrame()` call
- LLM calls are cached on disk (`pipeline/cache/`) keyed by SHA-256 of `(prompt_file_version, model, spec, seed)`. Re-running with the cache makes zero network calls
- `random.Random(seed)` governs all combinatorial sampling

### Decisions Made and Deferred

| Decision | Choice | Rationale |
|---|---|---|
| Model judge | Omitted (null) | CPU-only vision models too slow; slot reserved |
| Ollama fallback | Deterministic template | Guarantees reproducibility without network |
| Dedup threshold | 0.92 cosine | Empirically loose enough to keep diverse tasks |
| Held-out split | Last 20% of accepted | Simple, reproducible, no data leakage |
| `--no-sandbox` in verifier | Accepted | Documented in `renderer/README.md`; not in agent image |
| Docker images | Not yet built | Phase 5 — TBD |
| Quality gate runner | Not yet implemented | Phase 6 — TBD |

### What Was Cut
- Phases 5–8: Docker image builds, `make quality` runner, rollout scoring, and `report.md` measured numbers from rollouts. These require the gate runner and Docker, which require more time.

### Cost and Throughput (Measured)
- 240 candidate briefs synthesized (fallback path, ~0 ms each)
- 208 rejected by embedding dedup
- 26 accepted training tasks + 6 held-out
- Pipeline wall-clock for 30 tasks on CPU: ~10 minutes (dominated by sentence-transformers embedding computation)
- Dollar spend: **\$0.00** (local Ollama + fallback only)
- Hypothetical cost at GPT-4o pricing (\$5/M tokens, ~800 tokens/brief): ~\$0.10 for 30 tasks; ~\$16.67 for 5,000 tasks

---

## 3. Signal Quality and Honest Assessment

### Measured Scores on Reference Solutions
| Task | gate_pass | quality | render | code |
|---|---|---|---|---|
| calm-wave-fintech | true | 0.8591 | 0.7857 | 0.9646 |
| calm-fintechapp-234645 | true | 0.8441 | 0.7688 | 0.9525 |

### Known Weaknesses

**Palette adherence is too strict**: The anti-gaming coverage check (`distinct_colors_meeting_coverage >= 3`) flags even valid scenes when the 3D background dominates pixel coverage. The gaming penalty of 0.5x is applied to solutions that use large background planes (which is correct WebGL design). This signal needs a viewport-zone aware version.

**Temporal motion resolution**: At 16.67 ms virtual ticks, the inter-frame pixel diff is very small (~0.07 average). The mood band calibration (`calm: [0.05, 5.0]`) covers this, but bands for other moods may need empirical tuning after rollouts.

**AST easing detection**: Substring matching on identifier names works for explicit functions but misses easing parameters embedded in `gsap.to()` or `anime()` calls. Tightening to exact identifier matching would improve precision.

**Hackability surface**:
- Palette: Agent could fill entire viewport with one palette color → defended by coverage check
- Motion: Agent could add pixel noise each frame → defended by strobing upper bound (>65.0 diff scores 0.1)
- Copy: Agent could hide text off-screen → partially defended (DOM bounding box must be visible; not yet validated for off-screen elements)
- Draw calls: Agent could merge all geometry into one → not defended (this is legitimate optimization, score stays 1.0)

### Stability
TBD: Phase 7 rollouts not yet run. `report.md` will be updated with measured 5-run spread and flake rate.

### Verdict
> This system **generates and grades valid tasks** and is **suitable for early-stage sanity checking** of an RL training pipeline. It is **not yet ready for production evaluation** because: (1) the oracle pipeline uses procedural fallback solutions rather than LLM-generated diversity at scale; (2) the quality gate runner (Phase 6) has not been verified end-to-end; (3) rollout data to validate score distributions and difficulty calibration is missing.
>
> **First fix with one more week**: Run the full quality gate suite (`make quality`) on all 26 tasks, capture the oracle pass rate and break rate distribution, then calibrate `palette_adherence` coverage thresholds using those empirical numbers.

---

## AI-Generated Content Disclosure
The following was generated or substantially assisted by AI (Antigravity / Gemini):
- All Python source files in `pipeline/`, `reward/`, `renderer/`
- `tasks/calm-wave-fintech/solution/index.html` (reference solution)
- All fallback-generated `solution/index.html` files in generated task bundles
- `renderer/harness.js`

The following was verified manually or by running the code and reading its output:
- All measured numeric results in this report were read from files the code wrote
- Chromium flag set verified by observing `renderer_string: "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)"` in `trace.json`
- Unit test results observed from terminal output

The following was **not** fully verified:
- Downstream Harbor schema compatibility (assumed; documented in README)
- Docker image builds (Phase 5 not implemented)
- CTRF JSON schema strict conformance against Harbor validator

