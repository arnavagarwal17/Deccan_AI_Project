"""
pipeline/sample.py
Combinatorially samples ConstraintSpec instances from taxonomy.yaml using random.Random(seed).
Applies an incoherence rule table to reject inconsistent mood/category/motion pairings.
"""

import argparse
import hashlib
import random
from pathlib import Path
from typing import List, Dict, Any
import yaml

from pipeline.spec import ConstraintSpec, PerfConstraint, A11yConstraint


def load_taxonomy() -> Dict[str, Any]:
    tax_path = Path(__file__).parent / "taxonomy.yaml"
    return yaml.safe_load(tax_path.read_text(encoding="utf-8"))


def is_coherent(spec_dict: Dict[str, Any]) -> bool:
    category = spec_dict["product_category"]
    mood = spec_dict["mood"]
    budget = spec_dict["motion_budget_ms"]
    interaction = spec_dict["interaction"]
    palette = spec_dict["palette"]

    # Rule 1: Calm cannot have fast/short motion budget or aggressive drag-rotate
    if mood == "calm" and (budget[1] <= 1600 or interaction == "drag-rotate"):
        return False

    # Rule 2: Energetic cannot have very slow ambient budget or no interaction
    if mood == "energetic" and (budget[0] >= 1800 or interaction == "none"):
        return False

    # Rule 3: Minimal requires restrained interaction
    if mood == "minimal" and interaction in ("drag-rotate", "cursor-ripple"):
        return False

    # Rule 4: Cybersecurity should not be playful
    if category == "cybersecurity-platform" and mood == "playful":
        return False

    # Rule 5: Coffee roaster should not use cyberpunk neon palette (#00F0FF or #FF007F)
    if category == "coffee-roaster" and any(c in palette for c in ["#00F0FF", "#FF007F"]):
        return False

    # Rule 6: Sustainable fashion should not use neon cyberpunk palette
    if category == "sustainable-fashion" and any(c in palette for c in ["#00F0FF", "#FF007F"]):
        return False

    return True


def sample_specs(count: int, seed: int) -> List[ConstraintSpec]:
    rng = random.Random(seed)
    taxonomy = load_taxonomy()

    categories = taxonomy["product_categories"]
    moods = taxonomy["moods"]
    palettes = taxonomy["palettes"]
    budgets = taxonomy["motion_budgets"]
    easings_list = taxonomy["allowed_easings"]
    interactions = taxonomy["interactions"]
    copy_pools = taxonomy["copy_pools"]

    accepted: List[ConstraintSpec] = []
    attempts = 0
    max_attempts = count * 20

    while len(accepted) < count and attempts < max_attempts:
        attempts += 1
        cat = rng.choice(categories)
        mood = rng.choice(moods)
        pal = rng.choice(palettes)
        budget = rng.choice(budgets)
        easings = rng.choice(easings_list)
        inter = rng.choice(interactions)

        # Select copy from pool
        c_pool = copy_pools[cat]
        title = rng.choice(c_pool["titles"])
        sub = rng.choice(c_pool["subtitles"])
        cta = rng.choice(c_pool["ctas"])
        required_copy = [title, sub, cta]

        # Generate unique deterministic task_id
        idx = len(accepted)
        hash_seed = hashlib.sha256(f"{seed}:{idx}:{cat}:{mood}".encode()).hexdigest()[:6]
        task_id = f"{mood}-{cat.replace('-', '')}-{hash_seed}"

        # Assign perf and a11y thresholds
        perf = PerfConstraint(
            max_draw_calls=rng.choice([25, 30, 35, 40, 50]),
            first_frame_ms=rng.choice([150, 200, 250])
        )
        a11y = A11yConstraint(
            min_contrast_ratio=4.5,
            reduced_motion_respected=True
        )

        candidate = {
            "task_id": task_id,
            "product_category": cat,
            "mood": mood,
            "palette": pal,
            "palette_tolerance": 28.0,
            "required_copy": required_copy,
            "motion_budget_ms": budget,
            "allowed_easings": easings,
            "interaction": inter,
            "perf": perf,
            "a11y": a11y,
            "heldout": False,
        }

        if is_coherent(candidate):
            accepted.append(ConstraintSpec(**candidate))

    if len(accepted) < count:
        raise RuntimeError(f"Could only sample {len(accepted)} coherent specs out of {count} requested.")

    return accepted


def main():
    parser = argparse.ArgumentParser(description="Sample coherent ConstraintSpecs")
    parser.add_argument("--count", type=int, default=30, help="Number of specs to sample")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    specs = sample_specs(count=args.count, seed=args.seed)
    print(f"Sampled {len(specs)} coherent specs using seed={args.seed}:")
    for s in specs[:5]:
        print(f"  - {s.task_id} ({s.product_category}, {s.mood}, copy={s.required_copy[0]})")


if __name__ == "__main__":
    main()

