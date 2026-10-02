// Pure helpers for the Taste & aroma and Nutrition lenses (no React).
// Self-check: node src/prediction/sensory.check.mjs

export const LENSES = [
  { id: "process", label: "Process" },
  { id: "taste", label: "Taste & aroma" },
  { id: "nutrition", label: "Nutrition" },
];

export const lensOf = (m) => m.lens ?? "process";

// Ordinal ramp for taste phases (blue 600/450/300/150), validated with the dataviz
// validator: --ordinal --mode dark --surface #191612 (monotone L, light end 2.22:1).
export const PHASE_HEX = ["#184f95", "#2a78d6", "#6da7ec", "#b7d3f6"];

// Spread n phases over the ramp so 2 phases use both ends.
export function phaseColor(k, n) {
  const i = n <= 1 ? 0 : Math.round((k * (PHASE_HEX.length - 1)) / (n - 1));
  return PHASE_HEX[i];
}

export function mixHex(a, b, f) {
  const ch = (h, i) => parseInt(h.slice(1 + 2 * i, 3 + 2 * i), 16);
  const c = [0, 1, 2].map((i) => Math.round(ch(a, i) + (ch(b, i) - ch(a, i)) * f));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

// Most likely phase per grid point, with the runner-up (for blending a transition).
export function phaseRuns(tp) {
  if (!tp?.vocabulary?.length) return [];
  return tp.t_h.map((t_h, i) => {
    const ps = tp.vocabulary.map((name, k) => ({ k, name, p: tp.prob[name][i] })).sort((a, b) => b.p - a.p);
    return { t_h, k: ps[0].k, name: ps[0].name, p: ps[0].p, k2: ps[1]?.k ?? ps[0].k, p2: ps[1]?.p ?? 0 };
  });
}

// Contiguous spans of one most-likely phase; each ends where the next starts.
export function phaseSpans(runs) {
  const spans = [];
  for (const r of runs) {
    const last = spans[spans.length - 1];
    if (last && last.k === r.k) last.end_h = r.t_h;
    else spans.push({ k: r.k, name: r.name, start_h: r.t_h, end_h: r.t_h });
  }
  for (let i = 0; i + 1 < spans.length; i++) spans[i].end_h = spans[i + 1].start_h;
  return spans;
}

// Index of the last grid point at or before t (0 when t is before the grid).
export function indexAt(grid, t) {
  let i = 0;
  while (i + 1 < grid.length && grid[i + 1] <= t) i++;
  return i;
}

export function fmtNum(v, unit) {
  if (unit === "kJ" || unit === "kcal") return String(Math.round(v));
  return Math.abs(v) < 1 ? v.toFixed(2) : v.toFixed(1);
}

export function cellText(cell, unit) {
  if (!cell) return { value: "–", range: null };
  const lo = fmtNum(cell.p05, unit);
  const hi = fmtNum(cell.p95, unit);
  return { value: `${cell.lower_bound ? "≥ " : ""}${fmtNum(cell.p50, unit)}`, range: lo === hi ? null : `${lo}–${hi}` };
}

export function changeText(start, now) {
  if (!start || !now || Math.abs(start.p50) < 1e-9) return null;
  const pct = Math.round((now.p50 / start.p50 - 1) * 100);
  return pct === 0 ? null : `${pct > 0 ? "+" : "−"}${Math.abs(pct)} %`;
}

export const likelihood = (p) => (p >= 0.8 ? "likely" : p >= 0.5 ? "probably" : "possibly");

// "In the jar" at now or at the window's end: phase, noticeable tastes, three key rows.
export function jarSummary(sensory, which) {
  const t = which === "now" ? sensory.now_h : sensory.end_h;
  const tp = sensory.taste_phases;
  const r = tp ? phaseRuns(tp)[indexAt(tp.t_h, t)] : null;
  const row = (key) => sensory.nutrition_label.find((x) => x.key === key)?.[which] ?? null;
  return {
    t_h: t,
    phase: r ? { name: r.name, k: r.k, p: r.p, n: tp.vocabulary.length } : null,
    tastes: Object.entries(sensory.noticeable?.[which] || {})
      .filter(([, p]) => p >= 0.5)
      .sort((a, b) => b[1] - a[1])
      .map(([k]) => k),
    sugars: row("sugars"),
    alcohol: row("alcohol"),
    energy: row("energy_kcal"),
  };
}
