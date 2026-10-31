"""
pipeline/llm.py
Local LLM caller with disk-based persistent caching and deterministic offline fallback.
Calls Ollama /v1/chat/completions with temperature=0 and seed.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional
import requests
import yaml

from pipeline.fallback import generate_fallback_brief


def load_models_config() -> Dict[str, Any]:
    cfg_path = Path(__file__).parent / "models.yaml"
    if cfg_path.exists():
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return {
        "openai_compat_url": "http://localhost:11434/v1/chat/completions",
        "models": {"brief_model": "qwen2.5:3b", "code_model": "qwen2.5-coder:7b"},
        "options": {"temperature": 0.0, "num_predict": 2048},
    }


_OLLAMA_AVAILABLE = None


def check_ollama_available(endpoint: str) -> bool:
    global _OLLAMA_AVAILABLE
    if _OLLAMA_AVAILABLE is not None:
        return _OLLAMA_AVAILABLE
    try:
        base_url = endpoint.split("/v1/")[0]
        r = requests.get(f"{base_url}/api/tags", timeout=0.3)
        _OLLAMA_AVAILABLE = (r.status_code == 200)
    except Exception:
        _OLLAMA_AVAILABLE = False
    return _OLLAMA_AVAILABLE
def compute_cache_key(prompt_name: str, model: str, spec_dict: Dict[str, Any], seed: int) -> str:
    spec_str = json.dumps(spec_dict, sort_keys=True)
    raw = f"{prompt_name}:{model}:{spec_str}:{seed}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def call_llm_brief(
    prompt_file: str,
    spec_dict: Dict[str, Any],
    seed: int,
    prompt_text: str,
    cache_dir: Optional[str] = None
) -> Dict[str, Any]:
    cfg = load_models_config()
    model = cfg.get("models", {}).get("brief_model", "qwen2.5:3b")
    c_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / "cache"
    c_dir.mkdir(parents=True, exist_ok=True)

    cache_key = compute_cache_key(prompt_file, model, spec_dict, seed)
    cache_file = c_dir / f"{cache_key}.json"

    # 1. Check persistent disk cache first
    if cache_file.exists():
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
            cached_data["path"] = "cache"
            return cached_data
        except Exception:
            pass

    # 2. Attempt Ollama HTTP API if available
    endpoint = cfg.get("openai_compat_url", "http://localhost:11434/v1/chat/completions")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an automated creative brief synthesizer that responds strictly in valid JSON."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.0,
        "seed": seed,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"}
    }

    ollama_success = False
    result_data = None
    eval_count = 0
    eval_duration = 0

    if check_ollama_available(endpoint):
        try:
            resp = requests.post(endpoint, json=payload, timeout=(0.5, 5.0))
            if resp.status_code == 200:
                resp_json = resp.json()
                content_str = resp_json["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                if "prose" in parsed and "spec_echo" in parsed:
                    result_data = parsed
                    ollama_success = True
                    eval_count = resp_json.get("usage", {}).get("completion_tokens", 0)
                    eval_duration = resp_json.get("usage", {}).get("total_duration", 0)
        except Exception:
            ollama_success = False

    # 3. Deterministic offline fallback if Ollama was unreachable
    if not ollama_success:
        result_data = generate_fallback_brief(spec_dict)
        result_data["path"] = "fallback"
        result_data["eval_count"] = 0
        result_data["eval_duration"] = 0
    else:
        result_data["path"] = "ollama"
        result_data["eval_count"] = eval_count
        result_data["eval_duration"] = eval_duration

    result_data["cache_key"] = cache_key
    result_data["model"] = model
    result_data["seed"] = seed

    # Write persistent cache entry
    cache_file.write_text(json.dumps(result_data, indent=2), encoding="utf-8")
    return result_data

