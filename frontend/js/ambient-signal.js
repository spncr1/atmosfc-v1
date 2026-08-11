(function () {
  const CANVAS_SELECTOR = "[data-ambient-signal]";
  const DEFAULT_COLOR = "#c8ff47";
  const DEFAULT_POINTS = [28, 34, 29, 48, 36, 54, 42, 58, 47, 52];
  const MAX_DPR = 1.5;
  const RESIZE_DELAY_MS = 140;
  const COMPACT_SIGNAL_MAX_WIDTH = 520;

  let currentOptions = null;
  let resizeTimer = null;

  function render(options = {}) {
    const canvas = ensureCanvas();
    if (!canvas) return;

    currentOptions = {
      mode: options.mode === "bloom" ? "bloom" : "signal",
      variant: options.variant || "default",
      color: resolveColor(options.color),
      buckets: normaliseBuckets(options.buckets),
      peakIndex: Number.isInteger(options.peakIndex) ? options.peakIndex : null,
    };

    canvas.dataset.ambientMode = currentOptions.mode;
    document.body.classList.add("has-ambient-signal");
    draw(canvas, currentOptions);
    bindResize();
  }

  function clear() {
    const canvas = document.querySelector(CANVAS_SELECTOR);
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    currentOptions = null;
  }

  function ensureCanvas() {
    let canvas = document.querySelector(CANVAS_SELECTOR);
    if (canvas) return canvas;

    canvas = document.createElement("canvas");
    canvas.className = "ambient-signal";
    canvas.dataset.ambientSignal = "";
    canvas.setAttribute("aria-hidden", "true");
    document.body.insertBefore(canvas, document.body.firstChild);
    return canvas;
  }

  function bindResize() {
    if (window.AtmosAmbientSignal?.hasResizeListener) return;

    window.addEventListener("resize", () => {
      if (!currentOptions) return;
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        const canvas = document.querySelector(CANVAS_SELECTOR);
        if (canvas) draw(canvas, currentOptions);
      }, RESIZE_DELAY_MS);
    });

    window.AtmosAmbientSignal.hasResizeListener = true;
  }

  function draw(canvas, options) {
    const width = window.innerWidth || document.documentElement.clientWidth || 1;
    const height = window.innerHeight || document.documentElement.clientHeight || 1;
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    const context = canvas.getContext("2d", { alpha: true, desynchronized: true });
    if (!context) return;

    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, width, height);

    if (options.mode === "bloom") {
      drawBloomMode(context, width, height, options);
      return;
    }

    drawSignalMode(context, width, height, options);
  }

  function drawSignalMode(context, width, height, options) {
    const points = buildSignalPoints(options.buckets, width, height, options.variant);
    if (points.length < 2) return;

    drawBaseHaze(context, width, height, options.color);

    if (width > COMPACT_SIGNAL_MAX_WIDTH) {
      drawSignalEchoes(context, points, options.color, width, height);
      drawRibbon(context, points, options.color, width);
    }

    drawPeaks(context, points, options);
  }

  function drawBloomMode(context, width, height, options) {
    const color = options.color;
    const primary = bloomAnchor(options.variant, width, height);

    drawRadialGlow(context, primary.x, primary.y, primary.radius, color, primary.alpha);

    if (width > 700) {
      drawRadialGlow(context, width * 0.34, height * 0.76, Math.min(width * 0.22, 420), color, 0.05);
    }
  }

  function bloomAnchor(variant, width, height) {
    if (width <= 700) {
      return { x: width * 0.52, y: height * 0.28, radius: width * 0.46, alpha: 0.14 };
    }

    if (variant === "team") {
      return { x: width * 0.73, y: height * 0.3, radius: Math.min(width * 0.3, 560), alpha: 0.15 };
    }

    return { x: width * 0.58, y: height * 0.3, radius: Math.min(width * 0.36, 640), alpha: 0.13 };
  }

  function drawBaseHaze(context, width, height, color) {
    drawRadialGlow(context, width * 0.34, height * 0.3, Math.min(width * 0.36, 680), color, 0.045);

    if (width > 700) {
      drawRadialGlow(context, width * 0.62, height * 0.58, Math.min(width * 0.34, 620), color, 0.04);
      drawRadialGlow(context, width * 0.86, height * 0.86, Math.min(width * 0.22, 420), color, 0.026);
    }
  }

  function drawRibbon(context, points, color, width) {
    const wide = width > 700;
    const blur = wide ? 36 : 20;
    const stroke = wide ? 22 : 12;

    context.save();
    context.shadowColor = withAlpha(color, 0.28);
    context.shadowBlur = blur;
    context.lineWidth = stroke;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.strokeStyle = withAlpha(color, 0.045);
    tracePath(context, points);
    context.stroke();

    context.shadowBlur = blur * 0.45;
    context.lineWidth = Math.max(2, stroke * 0.28);
    context.strokeStyle = withAlpha(color, 0.06);
    tracePath(context, points);
    context.stroke();
    context.restore();
  }

  function drawSignalEchoes(context, points, color, width, height) {
    const echoes = signalEchoLayout(width, height);

    echoes.forEach((echo) => {
      const echoPoints = scalePoints(points, echo);
      drawEchoRibbon(context, echoPoints, color, echo);

      if (echo.bloomIndex !== null && echoPoints[echo.bloomIndex]) {
        const bloom = echoPoints[echo.bloomIndex];
        drawRadialGlow(context, bloom.x, bloom.y, echo.bloomRadius, color, echo.bloomAlpha);
      }
    });
  }

  function drawEchoRibbon(context, points, color, echo) {
    context.save();
    context.shadowColor = withAlpha(color, echo.shadowAlpha);
    context.shadowBlur = echo.blur;
    context.lineWidth = echo.stroke;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.strokeStyle = withAlpha(color, echo.alpha);
    tracePath(context, points);
    context.stroke();
    context.restore();
  }

  function signalEchoLayout(width, height) {
    const compact = width <= 900;
    return [
      {
        scaleX: compact ? 0.58 : 0.38,
        scaleY: compact ? 0.58 : 0.5,
        offsetX: compact ? width * 0.48 : width * 0.08,
        offsetY: compact ? height * 0.53 : height * 0.58,
        alpha: compact ? 0.022 : 0.026,
        shadowAlpha: compact ? 0.12 : 0.14,
        blur: compact ? 18 : 24,
        stroke: compact ? 9 : 13,
        bloomIndex: 2,
        bloomRadius: compact ? 92 : 160,
        bloomAlpha: compact ? 0.055 : 0.062,
      },
      {
        scaleX: compact ? 0.5 : 0.32,
        scaleY: compact ? 0.48 : 0.42,
        offsetX: compact ? width * 0.02 : width * 0.66,
        offsetY: compact ? height * 0.74 : height * 0.14,
        alpha: compact ? 0.018 : 0.023,
        shadowAlpha: compact ? 0.1 : 0.13,
        blur: compact ? 16 : 22,
        stroke: compact ? 8 : 11,
        bloomIndex: 6,
        bloomRadius: compact ? 82 : 138,
        bloomAlpha: compact ? 0.048 : 0.054,
      },
    ];
  }

  function scalePoints(points, echo) {
    const minX = Math.min(...points.map((point) => point.x));
    const maxX = Math.max(...points.map((point) => point.x));
    const minY = Math.min(...points.map((point) => point.y));
    const maxY = Math.max(...points.map((point) => point.y));
    const sourceWidth = Math.max(1, maxX - minX);
    const sourceHeight = Math.max(1, maxY - minY);

    return points.map((point) => ({
      ...point,
      x: echo.offsetX + ((point.x - minX) / sourceWidth) * sourceWidth * echo.scaleX,
      y: echo.offsetY + ((point.y - minY) / sourceHeight) * sourceHeight * echo.scaleY,
    }));
  }

  function drawPeaks(context, points, options) {
    const peakIndexes = selectPeakIndexes(points, options.peakIndex);
    const compact = window.innerWidth <= COMPACT_SIGNAL_MAX_WIDTH;

    peakIndexes.forEach((index, rank) => {
      if (compact && rank > 0) return;

      const point = points[index];
      const strength = rank === 0 ? 1 : 0.64;
      const radius = point.bloomRadius * strength;
      drawRadialGlow(context, point.x, point.y, radius, options.color, (compact ? 0.1 : 0.14) * strength);
    });
  }

  function tracePath(context, points) {
    context.beginPath();
    context.moveTo(points[0].x, points[0].y);

    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const current = points[index];
      const controlX = (previous.x + current.x) / 2;
      context.bezierCurveTo(controlX, previous.y, controlX, current.y, current.x, current.y);
    }
  }

  function buildSignalPoints(buckets, width, height, variant) {
    const values = buckets.length ? buckets : DEFAULT_POINTS;
    const layout = signalLayout(width, height, variant);
    const horizontalInset = layout.inset;
    const availableWidth = Math.max(1, width - horizontalInset * 2);
    const baseline = layout.baseline;
    const amplitude = layout.amplitude;
    const max = Math.max(...values, 100);
    const min = Math.min(...values, 0);
    const range = Math.max(1, max - min);

    return values.map((value, index) => {
      const progress = values.length === 1 ? 0.5 : index / (values.length - 1);
      const normalised = (value - min) / range;
      const drift = Math.sin(progress * Math.PI * 2) * amplitude * 0.16;

      return {
        x: horizontalInset + availableWidth * progress,
        y: baseline - normalised * amplitude + drift,
        value,
        bloomRadius: layout.bloomBase + normalised * layout.bloomRange,
      };
    });
  }

  function signalLayout(width, height, variant) {
    if (width <= 700) {
      return {
        inset: width * 0.1,
        baseline: variant === "analysis" ? height * 0.34 : height * 0.3,
        amplitude: height * 0.12,
        bloomBase: 130,
        bloomRange: 70,
      };
    }

    return {
      inset: width * 0.08,
      baseline: variant === "analysis" ? height * 0.42 : height * 0.34,
      amplitude: variant === "analysis" ? height * 0.16 : height * 0.18,
      bloomBase: 260,
      bloomRange: 160,
    };
  }

  function selectPeakIndexes(points, explicitPeakIndex) {
    const indexes = points
      .map((point, index) => ({ index, value: point.value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 3)
      .map((entry) => entry.index);

    if (Number.isInteger(explicitPeakIndex) && points[explicitPeakIndex]) {
      return [explicitPeakIndex, ...indexes.filter((index) => index !== explicitPeakIndex)].slice(0, 3);
    }

    return indexes;
  }

  function drawRadialGlow(context, x, y, radius, color, alpha) {
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStop(0, withAlpha(color, alpha));
    gradient.addColorStop(0.42, withAlpha(color, alpha * 0.42));
    gradient.addColorStop(1, withAlpha(color, 0));

    context.save();
    context.fillStyle = gradient;
    context.fillRect(x - radius, y - radius, radius * 2, radius * 2);
    context.restore();
  }

  function normaliseBuckets(buckets) {
    if (!Array.isArray(buckets)) return [];

    return buckets
      .map((bucket) => {
        const value = typeof bucket === "number" ? bucket : bucket?.intensity;
        return Number(value);
      })
      .filter((value) => Number.isFinite(value));
  }

  function resolveColor(color) {
    if (color && !String(color).includes("var(")) return String(color);

    const accent = getComputedStyle(document.documentElement)
      .getPropertyValue("--accent")
      .trim();

    return accent || DEFAULT_COLOR;
  }

  function withAlpha(color, alpha) {
    const rgb = colorToRgb(color);
    if (!rgb) return `rgba(200, 255, 71, ${alpha})`;
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
  }

  function colorToRgb(color) {
    const value = String(color || "").trim();
    const hex = value.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
    if (hex) {
      return {
        r: parseInt(hex[1], 16),
        g: parseInt(hex[2], 16),
        b: parseInt(hex[3], 16),
      };
    }

    const rgb = value.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    if (rgb) {
      return {
        r: Number(rgb[1]),
        g: Number(rgb[2]),
        b: Number(rgb[3]),
      };
    }

    return null;
  }

  window.AtmosAmbientSignal = {
    render,
    clear,
    hasResizeListener: false,
  };
})();
