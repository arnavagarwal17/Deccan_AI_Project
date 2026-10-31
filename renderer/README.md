# Headless WebGL Renderer & Chromium Configuration

## Overview
This renderer runs headless Chromium driven by Playwright to capture deterministic, virtual-time frame sequences and runtime diagnostics for single-file WebGL landing pages without physical GPU hardware.

## Chromium Flags
The verified working flag set for CPU-only WebGL via SwiftShader:
- `--headless=new`: Modern Chrome headless implementation ensuring standard layout and DOM behavior.
- `--use-angle=swiftshader`: Directs ANGLE (Almost Native Graphics Engine) to use Google's CPU-based SwiftShader Vulkan/OpenGL software rasterizer.
- `--enable-unsafe-swiftshader`: Permits WebGL execution on untrusted/unprivileged environments without hardware GPU acceleration.
- `--disable-gpu-sandbox`: Allows SwiftShader thread pools and memory allocations to operate without restrictive kernel sandbox crashes on CPU-only machines.
- `--no-sandbox`: Note: `--no-sandbox` is **NOT** allowed in the agent environment image (preventing privilege escape), but is accepted inside the isolated containerized verifier image.

## Determinism & Virtual Time
- Viewport is pinned at 1280x720 with device pixel ratio (DPR) = 1.0.
- Real-time clocks (`Date.now`, `performance.now`, `requestAnimationFrame`) are hooked by `harness.js`.
- Each frame advances virtual time by exactly 16.6667 ms (60 FPS tick), guaranteeing identical animation state across runs.

## Failure Mode Safeguards
1. **Infinite loops / hangs**: Handled via Playwright page timeout (e.g. 5000 ms), aborting the render and failing the `first_frame_under_budget` gate with reward 0.
2. **Shader compilation/link failure**: `harness.js` intercepts `gl.getProgramParameter(program, gl.LINK_STATUS)`. If any program fails linking, `shader_link_ok` becomes `false` and the `compiles` gate fails.
3. **Web Worker spawning**: `harness.js` overrides `window.Worker` with a throwing constructor; logged as a console error, causing the `no_console_errors` gate to fail.
4. **Network requests**: Playwright routing blocks all external HTTP/HTTPS network traffic, recording violations in `trace.json`.

