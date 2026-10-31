"""
pipeline/dedup.py
Deduplicates prose briefs via sentence-transformers cosine similarity (reject threshold > 0.92).
Splits accepted briefs into training set (80%) and held-out evaluation set (20%).
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np

_EMBEDDING_MODEL = None


def get_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBEDDING_MODEL


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    dot = float(np.dot(vec_a, vec_b))
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def deduplicate_briefs(
    brief_records: List[Dict[str, Any]],
    threshold: float = 0.92
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (accepted_training_pool, heldout_pool, rejected_duplicates).
    """
    model = get_embedding_model()
    accepted: List[Dict[str, Any]] = []
    accepted_vectors: List[np.ndarray] = []
    rejected: List[Dict[str, Any]] = []

    for item in brief_records:
        prose_text = item.get("prose", "")
        vec = model.encode(prose_text, convert_to_numpy=True)

        is_dup = False
        max_sim = 0.0
        matching_task = None

        for existing_vec, existing_item in zip(accepted_vectors, accepted):
            sim = cosine_similarity(vec, existing_vec)
            if sim > max_sim:
                max_sim = sim
                matching_task = existing_item.get("task_id")
            if sim > threshold:
                is_dup = True
                break

        if is_dup:
            item["rejection_reason"] = f"embedding_similarity_above_{threshold}"
            item["max_similarity"] = float(max_sim)
            item["similar_to"] = matching_task
            rejected.append(item)
        else:
            item["max_similarity"] = float(max_sim)
            accepted.append(item)
            accepted_vectors.append(vec)

    # Held-out split: last 20% of accepted briefs
    total_acc = len(accepted)
    heldout_count = max(1, int(round(total_acc * 0.20))) if total_acc >= 5 else 0
    split_idx = total_acc - heldout_count

    training_pool = accepted[:split_idx]
    heldout_pool = accepted[split_idx:]

    for h in heldout_pool:
        h["heldout"] = True
        if "spec" in h:
            h["spec"]["heldout"] = True

    # Persist held-out briefs to quality/heldout/
    heldout_dir = Path("quality/heldout")
    heldout_dir.mkdir(parents=True, exist_ok=True)
    for h in heldout_pool:
        t_id = h.get("task_id", "heldout_task")
        out_f = heldout_dir / f"{t_id}.json"
        serializable_h = {k: v for k, v in h.items() if k != "spec_obj"}
        out_f.write_text(json.dumps(serializable_h, indent=2), encoding="utf-8")

    return training_pool, heldout_pool, rejected

