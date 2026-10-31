/**
 * renderer/harness.js
 * Injected before page scripts to establish deterministic virtual time,
 * WebGL call instrumentation, Worker blocking, and diagnostic tracing.
 */
(() => {
  let virtualTime = 0.0;
  let rafIdCounter = 1;
  const rafCallbacks = new Map();
  const timerCallbacks = [];
  let timerIdCounter = 1;

  const trace = {
    webgl_created: false,
    webgl_type: null,
    renderer_string: "unknown",
    shader_link_ok: true,
    shader_errors: [],
    console_errors: [],
    console_warnings: [],
    draw_calls_per_frame: [],
    max_draw_calls: 0,
    first_frame_ms: null,
    frame_execution_times_ms: [],
    worker_spawn_attempted: false,
    canvas_count: 0
  };

  let currentFrameDrawCalls = 0;

  // 1. Worker blocking
  const originalWorker = window.Worker;
  window.Worker = function WorkerStub(...args) {
    trace.worker_spawn_attempted = true;
    const msg = "Security violation: Worker creation is disabled in harness";
    trace.console_errors.push(msg);
    console.error(msg);
    throw new Error(msg);
  };

  // 2. Error and console interception
  const origError = console.error;
  const origWarn = console.warn;
  console.error = function (...args) {
    const formatted = args.map(a => (typeof a === "object" ? JSON.stringify(a) : String(a))).join(" ");
    trace.console_errors.push(formatted);
    origError.apply(console, args);
  };
  console.warn = function (...args) {
    const formatted = args.map(a => (typeof a === "object" ? JSON.stringify(a) : String(a))).join(" ");
    trace.console_warnings.push(formatted);
    origWarn.apply(console, args);
  };

  window.addEventListener("error", (event) => {
    trace.console_errors.push(event.message || "Unknown window error");
  });
  window.addEventListener("unhandledrejection", (event) => {
    trace.console_errors.push(String(event.reason || "Unhandled promise rejection"));
  });

  // 3. Virtual Clock Stubs
  const originalDateNow = Date.now;
  const originalPerfNow = performance.now.bind(performance);

  Date.now = () => Math.floor(virtualTime);
  performance.now = () => virtualTime;

  window.requestAnimationFrame = (callback) => {
    const id = rafIdCounter++;
    rafCallbacks.set(id, callback);
    return id;
  };

  window.cancelAnimationFrame = (id) => {
    rafCallbacks.delete(id);
  };

  window.setTimeout = (callback, delay = 0, ...args) => {
    const id = timerIdCounter++;
    timerCallbacks.push({ id, targetTime: virtualTime + Math.max(0, delay), callback, args, repeat: null });
    return id;
  };

  window.setInterval = (callback, interval = 0, ...args) => {
    const id = timerIdCounter++;
    const safeInterval = Math.max(16.6667, interval);
    timerCallbacks.push({ id, targetTime: virtualTime + safeInterval, callback, args, repeat: safeInterval });
    return id;
  };

  window.clearTimeout = (id) => {
    const idx = timerCallbacks.findIndex(t => t.id === id);
    if (idx !== -1) timerCallbacks.splice(idx, 1);
  };
  window.clearInterval = window.clearTimeout;

  // 4. WebGL Instrumentation
  function wrapWebGLContext(gl, type) {
    if (!gl || gl.__harness_wrapped) return gl;
    gl.__harness_wrapped = true;
    trace.webgl_created = true;
    trace.webgl_type = type;

    // Detect renderer
    try {
      const dbg = gl.getExtension("WEBGL_debug_renderer_info");
      if (dbg) {
        trace.renderer_string = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || "unknown";
      }
    } catch (_) {}

    // Track draw calls
    const drawMethods = [
      "drawArrays", "drawElements",
      "drawArraysInstanced", "drawElementsInstanced", "drawArraysInstancedANGLE", "drawElementsInstancedANGLE"
    ];

    drawMethods.forEach((method) => {
      if (typeof gl[method] === "function") {
        const orig = gl[method].bind(gl);
        gl[method] = function (...args) {
          currentFrameDrawCalls++;
          if (trace.first_frame_ms === null) {
            trace.first_frame_ms = virtualTime;
          }
          return orig(...args);
        };
      }
    });

    // Intercept shader / program linking
    const origLink = gl.linkProgram.bind(gl);
    gl.linkProgram = function (program) {
      origLink(program);
      const linkStatus = gl.getProgramParameter(program, gl.LINK_STATUS);
      if (!linkStatus) {
        trace.shader_link_ok = false;
        const err = gl.getProgramInfoLog(program) || "Shader program linking failed";
        trace.shader_errors.push(err);
        trace.console_errors.push(`WebGL Shader Link Error: ${err}`);
      }
    };

    return gl;
  }

  const origGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (contextType, ...args) {
    const ctx = origGetContext.call(this, contextType, ...args);
    trace.canvas_count++;
    if (contextType === "webgl" || contextType === "experimental-webgl") {
      return wrapWebGLContext(ctx, "webgl");
    }
    if (contextType === "webgl2") {
      return wrapWebGLContext(ctx, "webgl2");
    }
    return ctx;
  };

  // 5. Virtual time advancement driver
  window.__stepFrame = (dtMs = 16.6667) => {
    const startReal = originalPerfNow();
    virtualTime += dtMs;

    // Flush scheduled timers due up to virtualTime
    for (let i = 0; i < timerCallbacks.length; i++) {
      const item = timerCallbacks[i];
      if (item.targetTime <= virtualTime) {
        try {
          item.callback.apply(window, item.args);
        } catch (err) {
          trace.console_errors.push(String(err));
        }
        if (item.repeat) {
          item.targetTime = virtualTime + item.repeat;
        } else {
          timerCallbacks.splice(i, 1);
          i--;
        }
      }
    }

    // Flush pending rAF callbacks
    const currentCallbacks = Array.from(rafCallbacks.values());
    rafCallbacks.clear();
    for (let i = 0; i < currentCallbacks.length; i++) {
      try {
        currentCallbacks[i](virtualTime);
      } catch (err) {
        trace.console_errors.push(String(err));
      }
    }

    // Record draw call counts for this tick
    trace.draw_calls_per_frame.push(currentFrameDrawCalls);
    if (currentFrameDrawCalls > trace.max_draw_calls) {
      trace.max_draw_calls = currentFrameDrawCalls;
    }
    currentFrameDrawCalls = 0;

    const execDuration = originalPerfNow() - startReal;
    trace.frame_execution_times_ms.push(execDuration);
    return virtualTime;
  };

  window.__getTrace = () => {
    return JSON.parse(JSON.stringify(trace));
  };
})();

