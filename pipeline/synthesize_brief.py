"""
pipeline/synthesize_brief.py
Renders brief_v1.md prompt, calls llm.py, and strictly validates that spec_echo matches
the original ConstraintSpec without altered or hallucinated constraints.
"""

from pathlib import Path
from typing import Dict, Any

from pipeline.spec import ConstraintSpec
from pipeline.llm import call_llm_brief


def render_brief_prompt(spec: ConstraintSpec) -> str:
    prompt_path = Path(__file__).parent / "prompts" / "brief_v1.md"
    template = prompt_path.read_text(encoding="utf-8")

    replacements = {
        "{{product_category}}": spec.product_category,
        "{{mood}}": spec.mood,
        "{{palette}}": str(spec.palette),
        "{{required_copy}}": str(spec.required_copy),
        "{{motion_budget_ms}}": str(spec.motion_budget_ms),
        "{{allowed_easings}}": str(spec.allowed_easings),
        "{{interaction}}": spec.interaction,
    }

    for placeholder, val in replacements.items():
        template = template.replace(placeholder, val)

    return template


def validate_spec_echo(original: ConstraintSpec, echo: Dict[str, Any]) -> None:
    errors = []

    if echo.get("product_category") != original.product_category:
        errors.append(f"product_category mismatch: echo '{echo.get('product_category')}' vs '{original.product_category}'")

    if echo.get("mood") != original.mood:
        errors.append(f"mood mismatch: echo '{echo.get('mood')}' vs '{original.mood}'")

    if echo.get("palette") != original.palette:
        errors.append(f"palette mismatch: echo {echo.get('palette')} vs {original.palette}")

    if echo.get("required_copy") != original.required_copy:
        errors.append(f"required_copy mismatch: echo {echo.get('required_copy')} vs {original.required_copy}")

    if echo.get("motion_budget_ms") != original.motion_budget_ms:
        errors.append(f"motion_budget_ms mismatch: echo {echo.get('motion_budget_ms')} vs {original.motion_budget_ms}")

    if echo.get("allowed_easings") != original.allowed_easings:
        errors.append(f"allowed_easings mismatch: echo {echo.get('allowed_easings')} vs {original.allowed_easings}")

    if echo.get("interaction") != original.interaction:
        errors.append(f"interaction mismatch: echo '{echo.get('interaction')}' vs '{original.interaction}'")

    if errors:
        raise ValueError("Constraint alteration detected in LLM spec_echo:\n" + "\n".join(errors))


def synthesize_brief(spec: ConstraintSpec, seed: int) -> Dict[str, Any]:
    prompt_text = render_brief_prompt(spec)
    spec_dict = spec.model_dump()

    llm_resp = call_llm_brief(
        prompt_file="brief_v1.md",
        spec_dict=spec_dict,
        seed=seed,
        prompt_text=prompt_text
    )

    echo = llm_resp.get("spec_echo", {})
    validate_spec_echo(original=spec, echo=echo)

    return {
        "task_id": spec.task_id,
        "prose": llm_resp["prose"],
        "spec_echo": echo,
        "path": llm_resp.get("path", "unknown"),
        "cache_key": llm_resp.get("cache_key"),
        "eval_count": llm_resp.get("eval_count", 0),
        "eval_duration": llm_resp.get("eval_duration", 0),
    }

