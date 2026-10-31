"""
pipeline/fallback_solution.py
Procedurally generates a complete, valid, high-scoring reference solution (index.html)
strictly matching any given ConstraintSpec without external dependencies.
"""

from typing import Dict, Any
from pipeline.spec import ConstraintSpec


def generate_fallback_solution(spec: ConstraintSpec) -> str:
    palette = spec.palette
    bg_color = palette[0]
    primary_color = palette[1] if len(palette) > 1 else palette[0]
    accent_color = palette[2] if len(palette) > 2 else palette[0]
    text_color = palette[-1]

    req_copy = spec.required_copy
    title = req_copy[0] if len(req_copy) > 0 else "Platform"
    sub = req_copy[1] if len(req_copy) > 1 else "Experience"
    cta = req_copy[2] if len(req_copy) > 2 else "Explore"

    min_ms, max_ms = spec.motion_budget_ms
    intro_ms = int((min_ms + max_ms) / 2)

    # Select allowed easing
    chosen_easing = spec.allowed_easings[0] if spec.allowed_easings else "ease-out"
    if "quad" in chosen_easing.lower():
        easing_func = "function easeInOutQuad(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }"
        easing_call = "easeInOutQuad(progress)"
    elif "cubic" in chosen_easing.lower():
        easing_func = "function easeOutCubic(t) { return (--t) * t * t + 1; }"
        easing_call = "easeOutCubic(progress)"
    else:
        easing_func = "function easeInOutQuad(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }"
        easing_call = "easeInOutQuad(progress)"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 100%; height: 100%; overflow: hidden;
      background-color: {bg_color}; color: {text_color};
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    #webgl-canvas {{
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      display: block; z-index: 1;
    }}
    .hero-container {{
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      z-index: 10; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      pointer-events: none; text-align: center; padding: 2rem;
    }}
    h1 {{
      font-size: 3.2rem; font-weight: 700; margin-bottom: 1rem;
      color: {text_color}; background: rgba(0, 0, 0, 0.45);
      padding: 0.3rem 1.2rem; border-radius: 8px;
    }}
    p {{
      font-size: 1.4rem; font-weight: 400; margin-bottom: 2rem;
      color: {text_color}; background: rgba(0, 0, 0, 0.45);
      padding: 0.2rem 1rem; border-radius: 6px;
    }}
    .cta-btn {{
      pointer-events: auto; background-color: {primary_color};
      color: {text_color}; border: 1px solid {text_color};
      padding: 0.85rem 2.2rem; font-size: 1.1rem; font-weight: 600;
      border-radius: 6px; cursor: pointer;
      transition: transform 0.2s ease-out, background-color 0.2s ease-out;
    }}
    .cta-btn:hover {{
      background-color: {accent_color};
      transform: translateY(-2px);
    }}
  </style>
</head>
<body>
  <canvas id="webgl-canvas"></canvas>
  <main class="hero-container">
    <h1>{title}</h1>
    <p>{sub}</p>
    <button class="cta-btn" type="button">{cta}</button>
  </main>

  <script src="vendor/three.min.js"></script>
  <script>
    (function () {{
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const canvas = document.getElementById("webgl-canvas");
      const width = window.innerWidth || 1280;
      const height = window.innerHeight || 720;

      const renderer = new THREE.WebGLRenderer({{
        canvas: canvas,
        antialias: true,
        alpha: false,
        powerPreference: "high-performance"
      }});
      renderer.setSize(width, height);
      renderer.setPixelRatio(1.0);
      renderer.setClearColor("{bg_color}", 1.0);

      const scene = new THREE.Scene();
      scene.background = new THREE.Color("{bg_color}");

      const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
      camera.position.set(0, 2, 9);
      camera.lookAt(0, 0, 0);

      const ambientLight = new THREE.AmbientLight("{primary_color}", 1.4);
      scene.add(ambientLight);

      const dirLight = new THREE.DirectionalLight("{text_color}", 1.6);
      dirLight.position.set(5, 8, 6);
      scene.add(dirLight);

      // Primary geometric sculpture
      const gridX = 32, gridY = 32;
      const geo = new THREE.PlaneGeometry(14, 14, gridX, gridY);
      geo.rotateX(-Math.PI / 2.6);

      const mat = new THREE.MeshStandardMaterial({{
        color: "{primary_color}",
        roughness: 0.4,
        metalness: 0.25,
        flatShading: true
      }});
      const mainMesh = new THREE.Mesh(geo, mat);
      mainMesh.position.set(0, -1, 0);
      scene.add(mainMesh);

      // Accent torus ring
      const ringGeo = new THREE.TorusGeometry(3.8, 0.06, 16, 64);
      const ringMat = new THREE.MeshBasicMaterial({{ color: "{accent_color}", wireframe: true }});
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.position.set(0, 0.6, -2.5);
      scene.add(ringMesh);

      const pos = geo.attributes.position;
      const origZ = new Float32Array(pos.count);
      for (let i = 0; i < pos.count; i++) origZ[i] = pos.getZ(i);

      // Timing and kinematics
      const introDurationMs = {intro_ms};
      let startTime = null;
      let mouseX = 0, mouseY = 0;
      let targetTiltX = 0, targetTiltY = 0;

      window.addEventListener("mousemove", function (e) {{
        const nx = (e.clientX / window.innerWidth) * 2 - 1;
        const ny = -(e.clientY / window.innerHeight) * 2 + 1;
        targetTiltX = ny * 0.18;
        targetTiltY = nx * 0.28;
      }});

      {easing_func}

      function animate(now) {{
        requestAnimationFrame(animate);
        if (startTime === null) startTime = now;
        const elapsed = now - startTime;
        const progress = prefersReducedMotion ? 1.0 : Math.min(1.0, elapsed / introDurationMs);
        const introFactor = {easing_call};

        const timeSec = prefersReducedMotion ? 0 : now * 0.001;
        for (let i = 0; i < pos.count; i++) {{
          const u = (i % (gridX + 1)) / gridX;
          const v = Math.floor(i / (gridX + 1)) / gridY;
          const wave = (Math.sin(u * 4.5 + timeSec * 1.4) + Math.cos(v * 4.0 + timeSec * 1.1)) * 0.35 * introFactor;
          pos.setZ(i, origZ[i] + wave);
        }}
        pos.needsUpdate = true;
        geo.computeVertexNormals();

        mouseX += (targetTiltX - mouseX) * 0.05;
        mouseY += (targetTiltY - mouseY) * 0.05;
        mainMesh.rotation.z = mouseY * 0.45;
        mainMesh.rotation.x = mouseX * 0.45;
        ringMesh.rotation.z = timeSec * 0.25;

        renderer.render(scene, camera);
      }}

      renderer.render(scene, camera);
      requestAnimationFrame(animate);
    }})();
  </script>
</body>
</html>
"""
    return html.strip()

