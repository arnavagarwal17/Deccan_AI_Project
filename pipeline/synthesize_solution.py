"""
pipeline/synthesize_solution.py
Generates reference solutions (solution/index.html) via cached CODE_MODEL calls
with deterministic procedural fallback.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
import requests

from pipeline.spec import ConstraintSpec
from pipeline.llm import load_models_config, check_ollama_available
from pipeline.fallback_solution import generate_fallback_solution


def render_solution_prompt(spec: ConstraintSpec) -> str:
    prompt_path = Path(__file__).parent / "prompts" / "solution_v1.md"
    template = prompt_path.read_text(encoding="utf-8")

    replacements = {
        "{{task_id}}": spec.task_id,
        "{{product_category}}": spec.product_category,
        "{{mood}}": spec.mood,
        "{{palette}}": str(spec.palette),
        "{{required_copy}}": str(spec.required_copy),
        "{{min_motion_ms}}": str(spec.motion_budget_ms[0]),
        "{{max_motion_ms}}": str(spec.motion_budget_ms[1]),
        "{{allowed_easings}}": str(spec.allowed_easings),
        "{{interaction}}": spec.interaction,
    }

    for placeholder, val in replacements.items():
        template = template.replace(placeholder, val)

    return template


def synthesize_solution(
    spec: ConstraintSpec,
    seed: int,
    cache_dir: Optional[str] = None
) -> Dict[str, Any]:
    cfg = load_models_config()
    model = cfg.get("models", {}).get("code_model", "qwen2.5-coder:7b")
    c_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / "cache"
    c_dir.mkdir(parents=True, exist_ok=True)

    spec_dict = spec.model_dump()
    spec_str = json.dumps(spec_dict, sort_keys=True)
    cache_key = hashlib.sha256(f"solution_v1.md:{model}:{spec_str}:{seed}".encode()).hexdigest()
    cache_file = c_dir / f"{cache_key}.json"

    # 1. Check persistent disk cache
    if cache_file.exists():
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
            cached_data["path"] = "cache"
            return cached_data
        except Exception:
            pass

    prompt_text = render_solution_prompt(spec)
    endpoint = cfg.get("openai_compat_url", "http://localhost:11434/v1/chat/completions")

    ollama_success = False
    html_code = ""
    eval_count = 0
    eval_duration = 0

    if check_ollama_available(endpoint):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an expert Three.js frontend engineer returning clean, runnable HTML code."},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.0,
            "seed": seed,
            "max_tokens": 2048,
        }
        try:
            resp = requests.post(endpoint, json=payload, timeout=(0.5, 30.0))
            if resp.status_code == 200:
                resp_json = resp.json()
                raw_text = resp_json["choices"][0]["message"]["content"]
                # Extract code block if wrapped in markdown
                match = re.search(r"```(?:html)?\s*(<!DOCTYPE.*?</html>)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
                if match:
                    html_code = match.group(1).strip()
                    ollama_success = True
                elif "<!DOCTYPE html>" in raw_text:
                    html_code = raw_text.strip()
                    ollama_success = True
                eval_count = resp_json.get("usage", {}).get("completion_tokens", 0)
                eval_duration = resp_json.get("usage", {}).get("total_duration", 0)
        except Exception:
            ollama_success = False

    if not ollama_success:
        html_code = generate_fallback_solution(spec)
        origin_path = "fallback"
    else:
        origin_path = "ollama"

    record = {
        "task_id": spec.task_id,
        "html": html_code,
        "path": origin_path,
        "cache_key": cache_key,
        "eval_count": eval_count,
        "eval_duration": eval_duration,
        "model": model,
        "seed": seed,
    }

    cache_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record

