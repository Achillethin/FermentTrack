// Minimal linear scales and "nice" ticks for the hand-rolled SVG charts.

export function linear([d0, d1], [r0, r1]) {
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  const f = (v) => r0 + (v - d0) * k;
  f.invert = (px) => (k === 0 ? d0 : d0 + (px - r0) / k);
  return f;
}

function niceStep(span, maxTicks) {
  const raw = span / Math.max(1, maxTicks);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  return step * mag;
}

// Nice y-domain + ticks covering [lo, hi].
export function niceTicks(lo, hi, maxTicks = 4) {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return { domain: [0, 1], ticks: [0, 1] };
  if (hi - lo < 1e-9) {
    const pad = Math.abs(hi) * 0.1 || 1;
    lo -= pad;
    hi += pad;
  }
  const step = niceStep(hi - lo, maxTicks);
  const d0 = Math.floor(lo / step + 1e-9) * step;
  const d1 = Math.ceil(hi / step - 1e-9) * step;
  const ticks = [];
  for (let v = d0; v <= d1 + step * 1e-6; v += step) ticks.push(Math.round(v / step) * step);
  return { domain: [d0, d1], ticks, step };
}

// Time ticks in hours for a [0, horizonH] axis, stepping in hours or days.
export function timeTicks(horizonH, unit, maxTicks) {
  const hourSteps = [1, 2, 3, 4, 6, 12, 24];
  const daySteps = [1, 2, 3, 7, 14, 30, 60, 90];
  const steps = unit === "h" ? hourSteps : daySteps.map((d) => d * 24);
  const cap = Math.min(maxTicks, 8);
  // Prefer a step that lands exactly on the horizon (0, 7, 14, 21, 28 d).
  const divides = (s) => Math.abs(horizonH / s - Math.round(horizonH / s)) < 1e-6;
  const step =
    steps.find((s) => horizonH / s <= cap && horizonH / s >= 2 && divides(s)) ??
    steps.find((s) => horizonH / s <= cap) ??
    steps[steps.length - 1];
  const ticks = [];
  for (let t = 0; t <= horizonH + 1e-6; t += step) ticks.push(t);
  return ticks;
}

// Index of the grid point nearest to t (grid sorted ascending).
export function nearestIndex(grid, t) {
  let lo = 0;
  let hi = grid.length - 1;
  if (t <= grid[0]) return 0;
  if (t >= grid[hi]) return hi;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (grid[mid] <= t) lo = mid;
    else hi = mid;
  }
  return t - grid[lo] < grid[hi] - t ? lo : hi;
}

// Linear interpolation of ys over grid at t.
export function valueAt(grid, ys, t) {
  const i = nearestIndex(grid, t);
  const j = grid[i] <= t ? Math.min(i + 1, grid.length - 1) : Math.max(i - 1, 0);
  if (i === j || grid[i] === grid[j]) return ys[i];
  const f = (t - grid[i]) / (grid[j] - grid[i]);
  return ys[i] + f * (ys[j] - ys[i]);
}
