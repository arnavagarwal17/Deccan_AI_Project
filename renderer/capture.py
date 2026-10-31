"""
renderer/capture.py
Drives headless Chromium via Playwright using SwiftShader CPU-based WebGL.
Instruments virtual time stepping, captures PNG frames, and collects trace diagnostics.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

CHROMIUM_FLAGS = [
    "--headless=new",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--disable-gpu-sandbox",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

DOM_TEXT_EXTRACT_SCRIPT = """
(() => {
  const elements = Array.from(document.querySelectorAll("body *"));
  const textNodes = [];
  for (const el of elements) {
    if (el.children.length === 0 && el.innerText && el.innerText.trim().length > 0) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      textNodes.push({
        text: el.innerText.trim(),
        tag: el.tagName.toLowerCase(),
        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        color: style.color,
        backgroundColor: style.backgroundColor,
        fontSize: style.fontSize,
        opacity: style.opacity
      });
    }
  }
  return textNodes;
})()
"""


async def capture_submission(
    submission_dir: str,
    output_dir: str,
    frames: int = 8,
    step_ms: float = 16.6667,
    width: int = 1280,
    height: int = 720,
    timeout_ms: int = 15000,
) -> dict:
    sub_path = Path(submission_dir).resolve()
    index_file = sub_path / "index.html"
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    trace_data = {
        "webgl_created": False,
        "webgl_type": None,
        "renderer_string": "unknown",
        "shader_link_ok": False,
        "shader_errors": [],
        "console_errors": [],
        "console_warnings": [],
        "draw_calls_per_frame": [],
        "max_draw_calls": 0,
        "first_frame_ms": None,
        "frame_execution_times_ms": [],
        "network_violations": [],
        "dom_elements": [],
        "captured_frames": [],
        "viewport": {"width": width, "height": height, "dpr": 1.0},
        "success": False,
    }

    if not index_file.exists():
        trace_data["console_errors"].append(f"Missing index.html in {submission_dir}")
        (out_path / "trace.json").write_text(json.dumps(trace_data, indent=2))
        return trace_data

    harness_path = Path(__file__).parent / "harness.js"
    harness_code = harness_path.read_text(encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=CHROMIUM_FLAGS,
        )
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1.0,
            has_touch=False,
        )

        network_violations = []

        async def route_filter(route):
            req = route.request
            url = req.url
            if url.startswith("file:") or url.startswith("data:") or url.startswith("blob:"):
                await route.continue_()
            else:
                network_violations.append(url)
                await route.abort("blockedbyclient")

        await context.route("**/*", route_filter)
        await context.add_init_script(script=harness_code)

        page = await context.new_page()

        try:
            target_url = index_file.as_uri()
            await page.goto(target_url, wait_until="load", timeout=timeout_ms)

            # Step virtual time and capture requested frames
            captured_files = []
            for i in range(frames):
                await page.evaluate(f"window.__stepFrame({step_ms})")
                frame_filename = f"frame_{i:02d}.png"
                frame_file = out_path / frame_filename
                await page.screenshot(path=str(frame_file), type="png")
                captured_files.append(frame_filename)

            raw_trace = await page.evaluate("window.__getTrace ? window.__getTrace() : {}")
            dom_elements = await page.evaluate(DOM_TEXT_EXTRACT_SCRIPT)

            trace_data.update(raw_trace)
            trace_data["network_violations"] = network_violations
            trace_data["dom_elements"] = dom_elements
            trace_data["captured_frames"] = captured_files
            trace_data["success"] = True

        except Exception as exc:
            trace_data["console_errors"].append(f"Capture execution error: {type(exc).__name__}: {str(exc)}")
            trace_data["success"] = False
        finally:
            await browser.close()

    (out_path / "trace.json").write_text(json.dumps(trace_data, indent=2))
    return trace_data


def main():
    parser = argparse.ArgumentParser(description="Headless WebGL capture driver")
    parser.add_argument("--dir", required=True, help="Directory containing index.html")
    parser.add_argument("--out", required=True, help="Output directory for frames & trace")
    parser.add_argument("--frames", type=int, default=8, help="Number of frames to capture")
    parser.add_argument("--step-ms", type=float, default=16.6667, help="Virtual time ms per frame")
    parser.add_argument("--width", type=int, default=1280, help="Viewport width")
    parser.add_argument("--height", type=int, default=720, help="Viewport height")
    parser.add_argument("--timeout-ms", type=int, default=15000, help="Page load timeout in ms")

    args = parser.parse_args()
    trace = asyncio.run(
        capture_submission(
            submission_dir=args.dir,
            output_dir=args.out,
            frames=args.frames,
            step_ms=args.step_ms,
            width=args.width,
            height=args.height,
            timeout_ms=args.timeout_ms,
        )
    )

    print(f"Captured {len(trace.get('captured_frames', []))} frames to {args.out}")
    print(f"WebGL Created: {trace.get('webgl_created')}")
    print(f"Renderer: {trace.get('renderer_string')}")
    print(f"Shader Link OK: {trace.get('shader_link_ok')}")
    print(f"Max Draw Calls: {trace.get('max_draw_calls')}")
    print(f"Console Errors: {len(trace.get('console_errors', []))}")


if __name__ == "__main__":
    main()

