You are an expert creative director writing a creative and technical brief for a frontend developer.
The developer will build a single-file animated WebGL landing page using Three.js based on the specification below.

### Input Constraint Spec
- Product Category: {{product_category}}
- Mood & Aesthetic: {{mood}}
- Color Palette: {{palette}}
- Required Copy Strings: {{required_copy}}
- Motion Duration Budget (ms): {{motion_budget_ms}}
- Allowed Easings: {{allowed_easings}}
- Interaction Pattern: {{interaction}}

### Instructions
1. Write a compelling, professional creative brief in markdown prose. Describe the company identity, visual atmosphere, lighting, 3D geometric concept, typography styling, and motion narrative.
2. Under no circumstances may you invent, modify, or drop any constraint from the input spec.
3. Return a valid JSON object with EXACTLY two top-level keys:
   - "prose": A string containing the full markdown creative brief for the developer.
   - "spec_echo": A JSON object containing the exact copy of the input constraint spec fields (product_category, mood, palette, required_copy, motion_budget_ms, allowed_easings, interaction).

Respond ONLY with valid JSON.

