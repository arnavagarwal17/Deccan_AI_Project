You are an expert creative technologist.
Write a complete, single-file HTML landing page (index.html) implementing an animated Three.js WebGL scene according to the specification below.

### Specification
- Task ID: {{task_id}}
- Product Category: {{product_category}}
- Mood: {{mood}}
- Color Palette: {{palette}}
- Required Copy Strings: {{required_copy}}
- Motion Duration Budget (ms): [{{min_motion_ms}}, {{max_motion_ms}}]
- Allowed Easings: {{allowed_easings}}
- Interaction: {{interaction}}

### Implementation Requirements
1. Structure: Complete standalone HTML with <!DOCTYPE html>, inline CSS, semantic DOM elements for required copy, and inline JavaScript.
2. Library: Must use <script src="vendor/three.min.js"></script>. Zero external CDN imports.
3. DOM Text: Every required copy string must appear prominently with high contrast against the background canvas.
4. WebGL Scene: Set up WebGLRenderer, Scene, PerspectiveCamera, materials with palette colors, and an animation loop.
5. Timing: Intro animation duration must be set within [{{min_motion_ms}}, {{max_motion_ms}}] ms.
6. Accessibility: Must respect window.matchMedia('(prefers-reduced-motion: reduce)').
7. Performance: Keep draw calls low (under 30 draw calls per frame).

Return ONLY the raw HTML code inside a ```html code block.

