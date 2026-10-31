# HOW TO USE THIS FILE (read this part yourself, do not paste it)

1. Use a coding AGENT, not a chat window. The AI must be able to create files and run commands. Free options: Claude Code (free tier), Gemini CLI (free), Cursor (free trial), GitHub Copilot CLI (free tier). A plain ChatGPT tab cannot run Docker and will hand you broken code.
2. Make an empty folder, open the agent inside it, and paste everything below the line "=== PROMPT STARTS HERE ===".
3. The prompt tells the AI to build in 8 phases and STOP after each one. Do not say "continue" until you have run the command for that phase yourself and seen it work. This is the single biggest protection against nonsense output.
4. Never let the AI invent numbers for the report. Every number in report.md must come from a file the pipeline actually wrote. If it writes "break rate 0.42" ask it "which file did that come from?"
5. No API keys anywhere. Install Ollama (ollama.com, one installer, free, runs fully on your laptop) and pull two models before you start:
   ollama pull qwen2.5-coder:7b     (writes the Three.js solutions and probe attempts; needs about 8 GB RAM)
   ollama pull qwen2.5:3b           (writes the prose briefs; small and fast)
   If your laptop has under 8 GB free RAM, use qwen2.5-coder:3b for both. Check it works with: ollama run qwen2.5:3b "say hi"
   The pipeline caches every model response to disk and commits the cache, so the reviewers never need Ollama; they just re-run with the cache.
   Speed reality: on an Apple Silicon Mac the 7b model does 20 to 40 tokens per second. On an Intel laptop with no GPU it does 3 to 8. Generating 50 solutions plus the difficulty probe can take 2 to 10 hours of pure model time, so start those runs early and let them run overnight.
6. Before you start, email rlteam@deccan.ai one question: "Should the verifier be a separate Docker image from the environment image, or does tests/test.sh run inside the environment container as in standard Harbor? I am building a separate image per the spec unless told otherwise." Questions do not count against you and it shows you read carefully.
7. Budget: Phases 1 to 4 on day one. Phases 5 to 8 on day two. If you are behind at the end of day one, cut the difficulty probe to n=2 and generate 30 tasks instead of 50, and WRITE DOWN that you cut it. Honest cuts are explicitly allowed by the assignment.

=== PROMPT STARTS HERE ===

You are a senior engineer helping me complete a take-home assignment for an "RL Engineer (Environments & Rewards)" role. You will build the entire project in this empty folder, phase by phase. After every phase you STOP, list the files you created, give me the exact command to run to verify it, and wait for my confirmation before going on. Do not skip ahead. Do not fabricate any measured number; every statistic must be read from a file the code wrote.

## 1. WHAT WE ARE BUILDING (read fully before writing any code)

### 1.1 Plain-language summary
A company trains AI coding agents with reinforcement learning (RL). RL means: give the agent a task, let it attempt it, score the attempt automatically, and use the score to improve the agent. To do that you need many tasks, each with an automatic scorer, and a way to reject broken tasks before they are used.

We are building the TASK FACTORY and the SCORER. We are NOT building a pretty web page. The agent being trained is the one that writes the web page. Our deliverable is:

- A pipeline that, from one command with a count and a seed, generates 50 distinct tasks. Each task asks an agent to write a single-file animated WebGL landing page that satisfies a brief.
- A grader generated automatically for each task from that task's machine-readable constraint spec.
- Six automatic quality gates that reject bad tasks and log why.
- A report with real measured numbers and an honest verdict.

The reviewers grade, in order of importance: (1) tasks and graders are produced by a system, not written by hand; (2) task quality is checked automatically; (3) the grader is hard to cheat; (4) we tested our own grader for weaknesses. Visual beauty is explicitly NOT graded.

### 1.2 Jargon you must understand and use correctly
- **Agent / policy**: the AI model being trained. In our system it is simulated by either an LLM call or a stub. We never train anything; we build what the trainer plugs into.
- **Environment**: the thing that gives the agent a task, runs its answer, and returns a score. That is our whole project.
- **Episode**: one attempt. Brief goes in, agent writes code, code is built and rendered, score comes out.
- **Reward**: the number returned to the trainer. Ours has two layers: a binary gate result (0 or 1) and a continuous quality score (0.0 to 1.0).
- **Grader / verifier / scorer**: the program that computes the reward. "Verifier" is the Harbor word for it.
- **Gate**: a pass/fail check. If any gate fails, the episode scores exactly 0 and the quality score is not computed.
- **Dense shaping signal**: a continuous score that gives partial credit so the agent gets gradient even when imperfect. **Terminal signal**: the final pass/fail. Dense signals are easier to "farm" (the agent finds a cheap way to raise them without doing the real task), so each one must be bounded and conditioned on the brief.
- **Reward hacking / gaming**: the agent raising its score without actually doing the task better. Example: hard-coding the exact RGB values from the palette into a full-screen rectangle to max the colour score. Our grader must be designed with this in mind.
- **Brief**: the human-readable task description given to the agent. **Constraint spec**: the same thing as structured JSON (palette hex values, required copy strings, animation duration range, etc). The spec is the source of truth; the brief and the grader are both generated from it.
- **Held-out split**: a subset of generated briefs that is kept out of the training task pool so it can be used later for clean evaluation. Nothing in the generated graders may be tuned on them.
- **Leak**: when the agent-facing instruction accidentally reveals a threshold, test name, or exact value the grader checks. Example: instruction says "animation must be under 1800ms" when the grader asserts 1800. The instruction may say "keep the intro animation brief"; the spec and grader hold the number.
- **Harbor bundle**: a standard folder layout for an RL task. It contains task.toml (metadata), instruction.md (what the agent sees), environment/ (Docker image the agent works in), tests/ (the verifier that scores), solution/ (a reference answer). The verifier writes the reward to /logs/verifier/reward.txt and per-check results to /logs/verifier/ctrf.json.
- **task.toml schema 2.0**: the metadata file. We will include: schema_version = "2.0", a [metadata] table (name, description, tags, difficulty), a [resources] table (cpu, memory_mb, timeout_sec, network = false), a [verifier] table pointing to tests/Dockerfile, and a do_not_modify array listing harness files the agent must not touch. If exact key names in the real Harbor schema differ, note it in the README as an assumption.
- **CTRF**: Common Test Report Format. A JSON file: {"results": {"tool": {"name": ...}, "summary": {"tests": N, "passed": N, "failed": N}, "tests": [{"name": ..., "status": "passed"|"failed", "duration": ms, "message": ...}]}}. We also add an "extra" object carrying the continuous score breakdown.
- **Oracle run**: scoring the reference solution in solution/. It must pass all gates and score high. If it does not, the task is discarded, never patched by hand.
- **NOP run**: scoring an empty or stub submission. It must score 0 and every gate must fail. If a gate passes on an empty page, that gate is not doing anything.
- **Flake**: scoring the same submission multiple times and getting different gate verdicts. A task that flakes is rejected.
- **Difficulty probe / break rate**: run a capable agent n times on a task and record how often it fails. 0% failure means the task teaches nothing; 100% usually means the task is broken.
- **Determinism / seed**: the same seed must regenerate byte-identical tasks. LLM calls are made non-deterministic by the provider, so we cache every LLM response on disk keyed by a hash of (prompt file version, input spec, seed) and commit the cache. Re-running with the cache present makes no network calls.
- **Embedding similarity**: converting text into a vector so similar briefs have a high cosine similarity. Used to deduplicate briefs. We use a local sentence-transformers model, no API needed.
- **WebGL**: the browser API for GPU drawing. **Three.js**: a popular library on top of it. **Shader**: a small GPU program in GLSL. **Uniform**: a parameter passed to a shader. **Draw call**: one GPU draw command; more draw calls means more cost.
- **Headless Chromium**: Chrome without a window, driven by code. **SwiftShader**: a software renderer so WebGL works with no GPU. **Viewport** and **device pixel ratio (DPR)**: window size and pixel density, which we fix so screenshots are identical every run.
- **Virtual time**: instead of letting the animation run on the real clock, the harness overrides Date.now, performance.now, and requestAnimationFrame so it can step the page forward by exactly 16.67ms per tick under program control. This makes frame captures reproducible.
- **AST**: abstract syntax tree, the parsed structure of source code. We parse the agent's JavaScript to extract numeric animation parameters and easing function names without executing it.
- **Easing**: the curve of an animation (linear, ease-in-out, cubic-bezier). **Stagger**: delay between successive elements animating.
- **Normalisation**: scaling each signal family to 0..1 so a family with large raw values cannot dominate the sum.
- **Unprivileged execution**: agent code runs as a non-root user and is never imported or require()'d by the scoring process. The scorer only ever reads the submission as text and observes it through the browser.

## 2. STACK (fixed, do not change)
- Python 3.11 for pipeline, quality gates, reward, and renderer driver.
- Playwright for Python with pinned Chromium (pin the exact Playwright version in requirements.txt and record the Chromium build in renderer/VERSION).
- numpy, Pillow, opencv-python-headless for image signals. esprima (Python package) for JS AST parsing. sentence-transformers with model all-MiniLM-L6-v2 for embeddings. tomli-w / tomllib for TOML. pydantic for the spec schema.
- LLM: local models through Ollama's HTTP API at http://localhost:11434 (OpenAI-compatible /v1/chat/completions endpoint, use the plain `requests` library, no SDK). Two models, both set in pipeline/models.yaml: BRIEF_MODEL = qwen2.5:3b for prose briefs, CODE_MODEL = qwen2.5-coder:7b for reference solutions and probe attempts. Pass options {"temperature": 0, "seed": <task seed>, "num_predict": 2048}. Every call goes through pipeline/llm.py which (a) hashes (prompt file name + version, model name, input spec, seed) and checks pipeline/cache/ first, (b) only calls Ollama on a cache miss, (c) falls back to a deterministic template-based expansion in pipeline/fallback.py if Ollama is not reachable, and records which path was used in the output JSON. The cache is committed, so a clean machine with no Ollama reproduces the run with zero model calls. No cloud API, no key, no .env file. Record the exact Ollama version and model digests (from `ollama list`) in pipeline/models.yaml for reproducibility.
- Three.js r160 vendored as a local file (environment/scaffold/vendor/three.min.js). The scene runs with NO network, so nothing may load from a CDN.
- Docker for both images. Makefile as the entry point.
- No GPU anywhere. Chromium flags: --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --disable-gpu-sandbox --no-sandbox is NOT allowed in the agent image but is acceptable in the verifier image; document it. Verify the flag set actually produces a WebGL context on the pinned build and record the working set in renderer/README.md.

## 3. REQUIRED FINAL LAYOUT
```
Makefile                         targets: setup, pipeline, quality, score, rollouts, report-data, zip
README.md                        setup and commands only, under one page
report.md                        Part E (see section 11)
requirements.txt
pipeline/
  taxonomy.yaml                  the axes and their values
  sample.py                      combinatorial sampling with seed
  spec.py                        pydantic ConstraintSpec model
  synthesize_brief.py            spec -> prose brief via LLM (cached)
  synthesize_grader.py           spec -> grader_config.json per task
  render_instruction.py          spec + brief -> instruction.md with grader specifics stripped
  dedup.py                       embedding dedup + held-out split
  llm.py, fallback.py, cache/    LLM wrapper, offline fallback, committed response cache
  prompts/
    brief_v1.md                  every prompt is a versioned file, never inline
    solution_v1.md
    probe_agent_v1.md
  generate.py                    the one command: --count N --seed S
quality/
  gates/oracle.py nop.py leak.py difficulty.py flake.py diversity.py
  run_all.py                     runs the six gates, writes reject_log.jsonl and yield_report.md
  heldout/                       held-out briefs, never copied into tasks/
reward/
  score.py                       pure function score(spec: dict, submission_dir: str) -> dict
  gates.py render_signals.py code_signals.py judge.py (optional, skippable)
  weights.yaml                   every number has a one-line comment with its origin
renderer/
  capture.py                     headless capture, virtual time, determinism controls
  harness.js                     injected before page scripts: clock stub, rAF stepping, WebGL call counters, console capture
  Dockerfile                     verifier base image
  VERSION
tasks/<kebab-case-name>/
  task.toml
  instruction.md
  environment/Dockerfile  environment/brief.json  environment/scaffold/index.html  environment/scaffold/vendor/three.min.js
  tests/Dockerfile  tests/test.sh  tests/grader_config.json
  solution/index.html
rollouts/                        episode logs, scores, sampled frames (keep under 150 MB total)
```

## 4. PHASE 1: Skeleton and one end-to-end task (do this first, before any cleverness)
Create the layout, requirements.txt, Makefile, and the ConstraintSpec model:
```
ConstraintSpec:
  task_id: str (kebab-case, derived from seed + index)
  product_category: str        e.g. "fintech-app", "indie-game", "coffee-roaster"
  mood: str                    e.g. "calm", "energetic", "luxurious"
  palette: list[str]           3 to 5 hex colours
  palette_tolerance: float     max allowed Lab distance, used by grader only
  required_copy: list[str]     exact strings that must appear in the DOM
  motion_budget_ms: [min, max] total intro animation duration window
  allowed_easings: list[str]
  interaction: str             e.g. "hover-tilt", "scroll-parallax", "none"
  perf: {max_draw_calls: int, first_frame_ms: int}
  a11y: {min_contrast_ratio: float, reduced_motion_respected: bool}
  heldout: bool
```
Write ONE task by running the spec through template-based generation (no LLM yet), including a working solution/index.html that uses the vendored Three.js and animates a simple scene. Write renderer/harness.js and renderer/capture.py so that `python -m renderer.capture --dir tasks/<name>/solution --frames 8 --out /tmp/cap` produces 8 PNGs plus a trace.json with console errors, WebGL context status, draw-call counts per frame, and first-frame virtual time. STOP and give me the command. I will confirm WebGL actually renders under SwiftShader before we continue. If it does not, we fix the Chromium flags before anything else.

## 5. PHASE 2: Reward as a pure function
Implement reward/score.py. Signature: score(spec: dict, submission_dir: str, capture_dir: str | None = None) -> dict. It must never import or exec the submission. Output shape:
```
{
 "gates": {"compiles": bool, "webgl_context": bool, "no_console_errors": bool, "first_frame_under_budget": bool, "required_copy_present": bool},
 "gate_pass": bool,
 "families": {"render": 0..1, "code": 0..1, "judge": 0..1 | null},
 "family_breakdown": {...every sub-signal raw and normalised...},
 "quality": 0..1,
 "reward_binary": 0 | 1,
 "notes": [...]
}
```
Gates are multiplicative: gate_pass false means quality = 0 and reward_binary = 0.

Render family (from captured frames only, never from source):
- palette_adherence: convert frames to CIELAB, k-means to 5 dominant colours, mean distance to nearest spec palette colour, mapped to 0..1 via the tolerance. Anti-gaming: also require that at least 3 distinct palette colours each cover between 5% and 70% of pixels; a single flat colour fill scores low.
- text_contrast: locate required_copy elements via DOM bounding boxes from the trace, sample rendered pixels inside and around each box, compute WCAG contrast ratio, score against a11y.min_contrast_ratio.
- temporal_motion: mean absolute inter-frame difference across the virtual-time sequence, scored against a band derived from mood (calm expects low, energetic expects higher). Smoothness: coefficient of variation of the diffs; lower is better. Anti-gaming: a frozen page (zero diff) and a strobing page (max diff) both score low.
- composition_balance: luminance centre of mass distance from frame centre, mapped to 0..1.
Code family (from AST plus runtime trace):
- duration_in_budget: all numeric literals attached to duration/delay-like identifiers or to known Three.js/GSAP-style timing calls, summed intro duration vs motion_budget_ms band.
- easing_allowed: fraction of detected easing identifiers that are in allowed_easings.
- draw_calls: per-frame draw-call count from the harness counters vs perf.max_draw_calls; score 1 inside budget, decays above.
- frame_stability: variance of per-tick JS execution time from the harness; lower is better.
- reduced_motion: AST or DOM evidence of prefers-reduced-motion handling if a11y.reduced_motion_respected.
Judge family: SKIP IT. Set judge to null and renormalise. Explain in the report that a model judge was omitted because a local vision model on CPU is too slow and noisy to be a defensible term, and that the slot exists in weights.yaml for a future pinned judge. This is allowed by the assignment (model judges are optional).

Normalisation: every sub-signal is clamped 0..1 before weighting. Family score is the weighted mean of its sub-signals. quality = 0.59*render + 0.41*code (the judge slot in weights.yaml is 0.0 with a comment that it is reserved). Put every number in weights.yaml with a comment such as "# 0.5: render carries the most weight because it is computed from pixels the agent cannot edit directly; chosen so no single family can exceed half the total". Brief conditioning: every signal takes the spec as input, so one memorised scene cannot score well across tasks; make this explicit in the code.

Write quick unit tests: NOP submission scores 0 on every gate; the Phase 1 solution passes gates and scores above 0.6. STOP.

## 6. PHASE 3: Brief synthesis
taxonomy.yaml with at least 6 values per axis. sample.py takes count and seed, uses random.Random(seed), samples combinations, rejects obviously incoherent combos with a small rule table (e.g. mood "calm" with motion budget at the top of the range). synthesize_brief.py loads pipeline/prompts/brief_v1.md, fills in the spec, calls llm.py, and returns prose plus a spec echo that is validated against the original (reject if the LLM altered any constraint). dedup.py embeds briefs, rejects any with cosine similarity above 0.92 to an already accepted brief, then marks the last 20% of accepted briefs as heldout and writes them to quality/heldout/ instead of tasks/. The LLM cache under pipeline/cache/ is committed so a second run with the same seed produces identical output with zero network calls. STOP.

## 7. PHASE 4: Grader synthesis and instruction rendering
synthesize_grader.py takes a spec and emits tests/grader_config.json: the gate list compiled from the spec (required_copy strings, first_frame_ms, max_draw_calls, contrast ratio), the parameter ranges bound to motion_budget_ms and allowed_easings, and the render assertions bound to palette and tolerance. tests/test.sh must: (1) write 0 to /logs/verifier/reward.txt FIRST, before anything else; (2) run the capture and scorer as an unprivileged user with no network; (3) write ctrf.json with one test per gate plus the quality breakdown in "extra"; (4) overwrite reward.txt with 1 only if all gates pass. render_instruction.py produces instruction.md from the spec and brief, then runs the leak linter: it extracts every number, hex colour tolerance, threshold, easing list, and test name from grader_config.json and fails generation if any appears verbatim in instruction.md. Required copy strings and palette hex values ARE allowed in the instruction because the agent needs them; thresholds, tolerances, counts, and durations are NOT. generate.py chains sampling, brief synthesis, dedup, grader synthesis, instruction rendering, solution generation (prompts/solution_v1.md, cached), and bundle writing. `make pipeline COUNT=50 SEED=42` must produce 50 bundles plus pipeline/yield.json counting generated, rejected per reason, accepted. STOP.

## 8. PHASE 5: Docker images and Harbor contract
environment/Dockerfile: minimal image with the scaffold, brief.json, vendored three.min.js, a non-root user, no verifier code. tests/Dockerfile: based on renderer/Dockerfile (Python + Playwright + pinned Chromium), copies reward/ and renderer/, runs test.sh as non-root, resource caps applied via docker run flags documented in task.toml [resources] (memory 2048 MB, 2 CPUs, 120 second timeout, network none). Handle failure modes explicitly in capture.py and document each in renderer/README.md: hang or infinite loop (Playwright timeout kills the page, gate first_frame_under_budget fails, reward 0); shader never compiles (WebGL context exists but gl.getProgramParameter LINK_STATUS false captured by the harness, gate compiles fails); page spawns Workers (harness replaces window.Worker with a stub that throws, logged as a console error, gate fails); network access (Playwright route blocks all requests, logged). Validate every task.toml against a schema in pipeline/task_toml_schema.py. STOP and give me the docker commands to build and run one task's verifier end to end.

## 9. PHASE 6: The six quality gates
quality/run_all.py runs on every bundle in tasks/ and writes quality/reject_log.jsonl (one line per rejection with task id, gate, reason) and quality/yield_report.md (pass rate per gate, table of rejected tasks). Gates:
1. oracle: score solution/; reject if gate_pass is false or quality < 0.6. Never patch; just reject.
2. nop: score an empty index.html and a stub that only prints the required copy with no WebGL; both must give reward 0 with every gate failing on the empty file.
3. leak: the mechanical linter from Phase 4, re-run.
4. difficulty: run prompts/probe_agent_v1.md through CODE_MODEL n=3 times per task with seeds (seed, seed+1, seed+2) so the three attempts differ (cached), score each, break rate = fraction failing gates. Keep tasks with break rate in [0.2, 0.8]. Make n configurable (PROBE_N) so it can be dropped to 2 if the machine is slow. If Ollama is unreachable, fall back to a documented proxy: three deterministic mutations of the oracle (shortened durations, removed one copy string, swapped a palette colour) and record in the yield report that the proxy was used. Note in the report that a 7b local coder is a weaker agent than the frontier models the trainer will use, so measured break rates are an upper bound.
5. flake: score the oracle 5 times; reject if any gate verdict differs; record the spread of render-derived signals and assert it is below 0.02 absolute.
6. diversity: pairwise embedding similarity of accepted briefs must be below 0.92, and the set of grader_config.json files must have no duplicate content hashes; report the similarity distribution.
`make quality` runs all six. Rejected bundles are moved to quality/rejected/<task>/ so tasks/ contains only accepted bundles. STOP.

## 10. PHASE 7: Rollouts and signal validation
`make rollouts` scores, for each accepted task: oracle, NOP, stub, and the probe attempts, writing rollouts/<task>/*.json and a sample of frames (no more than 2 frames per episode to control size). Then build three hand-ranked submissions for one task: deliberately bad (wrong palette, no animation), mediocre (right copy and palette, crude motion), good (the oracle). Score them and assert the order. Write rollouts/summary.json with per-family score distributions (min, p25, median, p75, max, fraction at 0, fraction at 1) over all episodes, flake spread, wall-clock per episode, model token counts and model wall-clock per accepted task (read from Ollama's response fields eval_count and eval_duration), dollar spend of zero with a hypothetical cost at a hosted API price of your choosing stated as an assumption, and an extrapolation to 5,000 tasks and 10,000 episodes in both wall-clock and hypothetical dollars. STOP.

## 11. PHASE 8: report.md and README.md
report.md has exactly three sections in this order, readable without opening code:
1. What this is: the task family in one page; one generated example end to end (brief, spec, rendered instruction, grader output on the oracle), pasted verbatim from files.
2. What you did: the pipeline as built, decisions made and deferred, what each gate rejected and why (from reject_log.jsonl), what was cut, cost and throughput from summary.json.
3. Is this good for training, evaluation, or neither: signal (hand-ranked order result and distributions, flag any term that is constant, bimodal, or pinned at ceiling), headroom (break-rate distribution and the fraction in the kept band), hackability (list the ways an agent could saturate each signal, e.g. palette fill, fake motion via noise, copy-only stubs, and which we defend against), stability (5-run spread and fraction of variance that is harness noise), cost, contamination (how held-out stays clean). End with a one-line verdict, what you would not yet trust, and the first fix with one more week. A negative verdict backed by numbers is acceptable.
Also include a section listing which parts were AI-generated and anything kept without full verification, as the assignment requires.
README.md: setup, make targets, assumptions, under one page. `make zip` produces submission.zip excluding caches larger than 20 MB, and anything that pushes the archive above 190 MB, with a note on what was sampled.

## 12. RULES FOR YOU, THE AI
- Never hand-write a task. If I ask for "just one more example task", refuse and generate it through the pipeline.
- Never hard-code a threshold inside a grader; thresholds come from grader_config.json which comes from the spec.
- Never import or exec submission code in the scorer.
- Never invent a number. If a measurement does not exist yet, write "TBD: run make rollouts" and tell me.
- Every magic number in reward/weights.yaml and grader generation gets a one-line origin comment.
- Keep each file under 300 lines; split otherwise.
- At the end of each phase, output: files created, the verification command, and one sentence on what could still be wrong.

Begin with Phase 1.
