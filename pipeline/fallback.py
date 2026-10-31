"""
pipeline/fallback.py
Deterministic offline template-based generation fallback for brief and solution synthesis.
Guarantees byte-identical, reproducible runs when Ollama is unreachable.
"""

from typing import Dict, Any

CATEGORY_DESCRIPTIONS = {
    "fintech-app": "a forward-looking quantitative wealth platform engineered for sovereign digital asset stewardship and serene financial sovereignty.",
    "indie-game": "an atmospheric interactive odyssey exploring spatial distortion, continuum anomalies, and stylized architectural relics.",
    "coffee-roaster": "an artisanal single-origin coffee roastery committed to high-altitude terroir, Dawn-cycle roasting, and sustainable producer partnerships.",
    "ai-research-lab": "a frontier artificial intelligence research collective architecting decentralized alignment primitives and cognitive tensor reasoning.",
    "sustainable-fashion": "a circular botanical textile atelier engineering carbon-negative luxury silhouettes and zero-waste regenerative garments.",
    "cybersecurity-platform": "an enterprise autonomous defense matrix providing continuous cryptographic perimeter defense and zero-trust neutralization.",
    "space-logistics": "a commercial cislunar transit network facilitating autonomous payload insertion and orbital freight routing across planetary vectors.",
    "health-biotech": "a precision molecular medicine laboratory pioneering synthetic epigenetics and targeted cellular longevity interventions.",
}

MOOD_DESCRIPTIONS = {
    "calm": "tranquil, deliberate, and deeply grounded, employing gentle fluid surfaces and rhythmic ambient respirations.",
    "energetic": "vibrant, rhythmic, and kinetic, using fast pulse frequencies and sharp angular velocity changes.",
    "luxurious": "refined, understated, and velvety, featuring luminous metallic specular highlights and deliberate slow reveals.",
    "minimal": "stark, disciplined, and pristine, prioritizing expansive negative space and precise geometric contours.",
    "futuristic": "technological, hyper-precise, and holographic, illuminated by neon grid lines and complex wireframe geometries.",
    "playful": "buoyant, cheerful, and dynamic, utilizing organic bouncing curves and spring-loaded reactive kinetics.",
}


def generate_fallback_brief(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
    cat = spec_dict.get("product_category", "fintech-app")
    mood = spec_dict.get("mood", "calm")
    palette = spec_dict.get("palette", ["#0B192C", "#1E3E62", "#000000", "#F1F6F9"])
    req_copy = spec_dict.get("required_copy", ["Title", "Subtitle", "Action"])
    motion_budget = spec_dict.get("motion_budget_ms", [1200, 2400])
    easings = spec_dict.get("allowed_easings", ["ease-out", "cubic-bezier"])
    interaction = spec_dict.get("interaction", "hover-tilt")

    cat_desc = CATEGORY_DESCRIPTIONS.get(cat, "an innovative digital experience platform.")
    mood_desc = MOOD_DESCRIPTIONS.get(mood, "a refined and captivating modern aesthetic.")

    title = req_copy[0] if len(req_copy) > 0 else "Platform"
    subtitle = req_copy[1] if len(req_copy) > 1 else "Experience"
    cta = req_copy[2] if len(req_copy) > 2 else "Explore"

    palette_bullets = "\n".join([f"- `{c}`" for c in palette])
    copy_bullets = "\n".join([f"- `{c}`" for c in req_copy])
    easing_str = ", ".join([f"`{e}`" for e in easings])

    prose = f"""# {title}: Creative & Technical Landing Page Brief

## 1. Brand Identity & Vision
**{title}** is {cat_desc}
The brand's aesthetic posture is **{mood}**: {mood_desc}

## 2. Technical Deliverable Contract
The developer must deliver a single self-contained `index.html` file hosting an animated Three.js scene utilizing the vendored offline library `vendor/three.min.js`. External CDN script tags or network calls are prohibited.

## 3. Required Copy Architecture
The following exact copy strings must be prominently structured within semantic DOM overlay elements:
{copy_bullets}

The primary headline must showcase `{title}`, accompanied by the descriptive tagline `{subtitle}`, anchored by a clickable action button `{cta}`.

## 4. Visual Palette & Lighting
The visual composition must be strictly constructed from the following color palette:
{palette_bullets}

Lighting must emphasize depth, structural volumetric shadows, and ambient clarity while preserving WCAG AA contrast compliance for all text overlays.

## 5. Kinetic & Interactive Narrative
- **Introductory Sequence**: The 3D scene must animate into place, settling smoothly within the required duration window.
- **Allowed Kinetic Profiles**: All transitions must adhere strictly to permitted easing curves ({easing_str}).
- **Interactive Engagement**: Incorporate responsive `{interaction}` behavior reacting gracefully to pointer input.
- **Accessibility**: Respect `prefers-reduced-motion` media queries by freezing or simplifying dynamic transformations when requested.
"""

    spec_echo = {
        "product_category": cat,
        "mood": mood,
        "palette": palette,
        "required_copy": req_copy,
        "motion_budget_ms": motion_budget,
        "allowed_easings": easings,
        "interaction": interaction,
    }

    return {
        "prose": prose.strip(),
        "spec_echo": spec_echo,
    }

