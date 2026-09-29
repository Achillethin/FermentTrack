// DEV-ONLY fixture for the /sourdough routes, shaped like Appendix A of
// docs/superpowers/specs/2026-09-28-sourdough-engine-design.md. Loaded only
// with ?fixture in `npm run dev` (see api.js); never in a production build.
// The numbers are a toy (Q10 = 2, log-ratio peak times), not the engine: they
// only move the right way when an input changes so the UI can be exercised.

const style = (key, name, native_name, type, seed, description, organisms, defaults) => ({
  key,
  name,
  native_name,
  type,
  seed,
  description,
  organisms,
  defaults: { hours: null, ...defaults },
  notes: [],
  sources: ["fixture"],
});

const LSF = "Lactobacillus sanfranciscensis";
const SC = "Saccharomyces cerevisiae";
const KH = "Kazachstania humilis";

export const CATALOG = {
  styles: [
    style("home_starter", "Home wheat starter", "Home wheat starter", "I", "starter", "The jar on your counter: fed with white or wholemeal flour, mild and lively.", [SC, "Lactobacillus plantarum", "Lactobacillus brevis"], { hydration_pct: 100, seed_ratio: 5, temperature_c: 24, flour: "t65" }),
    style("levain_liquide", "Levain liquide", "Levain liquide", "I", "starter", "French liquid levain at 100–125 %: fast, mild, creamy acidity.", [LSF, SC], { hydration_pct: 100, seed_ratio: 3, temperature_c: 26, flour: "t65" }),
    style("levain_dur", "Stiff levain", "Levain dur", "I", "starter", "A firm dough-like levain at 55 %: slower, more acetic, more tang.", [LSF, KH, SC], { hydration_pct: 55, seed_ratio: 3, temperature_c: 24, flour: "t65" }),
    style("lievito_madre", "Lievito madre", "Lievito madre", "I", "starter", "Italian sweet stiff starter for panettone: fed often, kept young and mild.", [LSF, KH], { hydration_pct: 45, seed_ratio: 1, temperature_c: 27, flour: "t45" }),
    style("san_francisco", "San Francisco sour", "San Francisco sour", "I", "starter", "The classic tangy firm starter, refreshed every 8 h.", [LSF, KH], { hydration_pct: 50, seed_ratio: 2.5, temperature_c: 27, flour: "t65", hours: 8 }),
    style("rye_sour", "Rye sour", "Roggensauer", "I", "starter", "German rye sourdough: wet, warm, sour; it acidifies rye so it can bake.", [LSF, "Lactobacillus brevis", KH], { hydration_pct: 90, seed_ratio: 10, temperature_c: 28, flour: "rye_t130" }),
    style("type_ii", "Liquid sour (Type II)", "Liquid sour", "II", "starter", "Industrial warm liquid sour: acid for flavour, no leavening.", ["Lactobacillus reuteri"], { hydration_pct: 200, seed_ratio: 10, temperature_c: 37, flour: "t65" }),
    style("type_iii", "Dried sourdough (Type III)", "Dried sourdough", "III", "dried", "A flavouring powder: adds acidity, needs baker's yeast to rise.", [], { hydration_pct: null, seed_ratio: null, temperature_c: 25, flour: "t65" }),
    style("poolish", "Poolish", "Poolish", "0", "yeast", "Wet yeasted pre-ferment (100 %) for baguettes: nutty, not sour.", [SC], { hydration_pct: 100, seed_ratio: 1000, temperature_c: 20, flour: "t55", hours: 12 }),
    style("biga", "Biga", "Biga", "0", "yeast", "Stiff Italian yeasted pre-ferment (50 %) for ciabatta.", [SC], { hydration_pct: 50, seed_ratio: 200, temperature_c: 18, flour: "t55", hours: 16 }),
  ],
  flours: [
    ["t45", "T45", "Pastry flour", "wheat", 0.45, 9.5],
    ["t55", "T55", "All-purpose flour", "wheat", 0.55, 10.5],
    ["t65", "T65", "Bread flour", "wheat", 0.65, 12.0],
    ["t80", "T80", "High-extraction flour", "wheat", 0.8, 12.5],
    ["t110", "T110", "Light whole wheat", "wheat", 1.1, 13.0],
    ["t150", "T150", "Whole wheat flour", "wheat", 1.5, 13.5],
    ["rye_t85", "Rye T85", "Light rye", "rye", 0.85, 8.0],
    ["rye_t130", "Rye T130", "Medium rye", "rye", 1.3, 9.0],
    ["rye_t170", "Rye T170", "Dark rye (pumpernickel)", "rye", 1.7, 10.0],
  ].map(([key, name, us_name, grain, ash_pct, protein_pct]) => ({ key, name, us_name, grain, ash_pct, protein_pct })),
};

const q10 = (t) => 2 ** ((26 - t) / 10);
const peakH = (r, t, starter) => (2 + 2.4 * Math.log2(1 + Math.min(r, 20))) * q10(t) + (starter === "refrigerated" ? 2 : 0);
const band = (p50, lo = 0.82, hi = 1.3, cap = 48) => ({
  p05: p50 * lo > cap ? null : +(p50 * lo).toFixed(2),
  p50: p50 > cap ? null : +p50.toFixed(2),
  p95: p50 * hi > cap ? null : +(p50 * hi).toFixed(2),
});
const logistic = (x) => 1 / (1 + Math.exp(-x));

function simulate(plan) {
  const lv = plan.levain;
  const d = plan.dough;
  const r = lv ? lv.flour_g / lv.seed_g : 0;
  const hyd = lv && lv.flour_g ? (lv.water_g / lv.flour_g) * 100 : 100;
  const tl = lv?.temperature_c ?? 25;
  const peak = lv ? peakH(r, tl, plan.starter) : 0;
  const levEnd = lv ? lv.hours ?? peak : 0;
  const phases = [];
  if (lv) phases.push({ key: "levain", label: "Levain", start_h: 0, end_h: +levEnd.toFixed(2), temperature_c: tl });
  let bulkEnd = levEnd;
  let bulk = 0;
  if (d) {
    const pct = d.levain_g ? (d.levain_g / (d.flour_g + d.levain_g / 2)) * 100 : 20;
    bulk = d.bulk_hours ?? 4.5 * q10(d.temperature_c) * ((d.target_rise_pct ?? 75) / 75) * (20 / Math.max(5, pct)) ** 0.3;
    bulkEnd = levEnd + bulk;
    phases.push({ key: "bulk", label: "Bulk", start_h: +levEnd.toFixed(2), end_h: +bulkEnd.toFixed(2), temperature_c: d.temperature_c });
    if (plan.proof) {
      const cold = plan.proof.temperature_c <= 10;
      phases.push({
        key: "proof",
        label: cold ? "Cold retard" : "Proof",
        start_h: +bulkEnd.toFixed(2),
        end_h: +(bulkEnd + plan.proof.hours).toFixed(2),
        temperature_c: plan.proof.temperature_c,
      });
    }
  }
  const end = phases.length ? phases[phases.length - 1].end_h : 12;
  const horizon = Math.min(72, Math.ceil(d ? end + 1 : Math.max(end, peak) * 1.7));
  const n = 121;
  const t = Array.from({ length: n }, (_, i) => +((horizon * i) / (n - 1)).toFixed(3));
  const rmax = hyd < 70 ? 110 : 160;
  const stiff = (100 / hyd) ** 0.8;

  const rise = t.map((x) => {
    if (x <= levEnd || !d) return rmax * logistic((x - 0.6 * peak) / (0.13 * peak)) * (x > peak ? Math.max(0.55, 1 - (0.3 * (x - peak)) / peak) : 1);
    const tau = Math.min(x, bulkEnd) - levEnd;
    const base = 1.35 * (d.target_rise_pct ?? 75) * logistic((tau - 0.6 * bulk) / (0.16 * bulk)) - 1.35 * (d.target_rise_pct ?? 75) * logistic(-0.6 / 0.16);
    return x > bulkEnd ? base + (plan.proof && plan.proof.temperature_c > 10 ? 20 : 5) * (1 - Math.exp(-(x - bulkEnd) / 3)) : base;
  });
  const ph = t.map((x) => {
    if (x <= levEnd || !d) return 6.1 - 2.2 * (1 - Math.exp(-x / (0.55 * peak)));
    return 5.5 - 1.4 * (1 - Math.exp(-(x - levEnd) / (d.temperature_c < 10 ? 20 : 7)));
  });
  const tta = ph.map((p) => 0.4 + (6.2 - p) * 3.1 * (hyd < 70 ? 1.2 : 1));
  const fq = t.map(() => 4.2 / stiff);
  const spread = (ys, abs, rel) => ({
    p05: ys.map((y) => +(y - abs - rel * Math.abs(y)).toFixed(3)),
    p50: ys.map((y) => +y.toFixed(3)),
    p95: ys.map((y) => +(y + abs + rel * Math.abs(y)).toFixed(3)),
  });
  const s = (key, label, unit, group, ys, abs, rel) => ({ key, label, unit, group, t_h: t, ...spread(ys, abs, rel) });
  const lactic = tta.map((v) => v * 0.55);
  const series = [
    s("rise", "Rise", "%", "rise", rise, 6, 0.12),
    s("ph", "pH", "", "ph", ph, 0.06, 0.02),
    s("tta", "TTA", "mL", "acidity", tta, 0.3, 0.1),
    s("fq", "Lactic : acetic", "mol/mol", "acidity", fq, 0.3, 0.15),
    s("lactic_acid", "Lactic acid", "g/kg", "products", lactic, 0.1, 0.1),
    s("acetic_acid", "Acetic acid", "g/kg", "products", lactic.map((v, i) => (v / fq[i]) * 0.67), 0.05, 0.12),
    s("ethanol", "Ethanol", "g/kg", "products", t.map((x) => 4 * (1 - Math.exp(-x / 8))), 0.2, 0.1),
    s("maltose", "Maltose", "g/kg", "substrates", t.map((x) => 18 * Math.exp(-x / 14) + 4), 0.5, 0.08),
    s("hexoses", "Glucose + fructose", "g/kg", "substrates", t.map((x) => 6 * Math.exp(-x / 6) + 1), 0.3, 0.1),
    s(`pop:${LSF}`, LSF, "log CFU/g", "population", t.map((x) => 7.4 + 1.8 * logistic((x - 0.5 * peak) / (0.15 * peak))), 0.15, 0),
    s(`pop:${SC}`, SC, "log CFU/g", "population", t.map((x) => 6.0 + 1.4 * logistic((x - 0.55 * peak) / (0.18 * peak))), 0.15, 0),
  ];
  const crossing = (ys, v) => {
    const i = ys.findIndex((y) => y < v);
    return i < 0 ? null : t[i];
  };
  const milestone = (key, title, note, series_key, value, kind, p50, extra = {}) => ({
    key,
    label: `${title} (${note})`,
    title,
    note,
    threshold: { series: series_key, value, kind },
    t_h: p50 == null ? { p05: null, p50: null, p95: null } : band(p50, 0.82, 1.3, horizon),
    probability: p50 == null ? 0.1 : 0.97,
    ...extra,
  });
  const milestones = [];
  if (lv) {
    milestones.push(milestone("levain_doubled", "Levain doubled", "100 % above the mark", "rise", 100, "above", peak * 0.62));
    milestones.push(milestone("levain_peak", "Levain peak", "highest point; use it now", "rise", 0, "max", peak));
  }
  if (d) milestones.push(milestone("bulk_target", "Bulk done", `+${d.target_rise_pct ?? 75} % rise`, "rise", d.target_rise_pct ?? 75, "above", bulkEnd));
  milestones.push(milestone("ph_below_4_2", "pH below 4.2", "pleasantly sour", "ph", 4.2, "below", crossing(ph, 4.2)));
  milestones.push(milestone("ph_below_4_0", "pH below 4.0", "clearly sour", "ph", 4.0, "below", crossing(ph, 4.0)));

  const total = d ? d.flour_g + (d.levain_g ?? 0) / 2 : lv?.flour_g ?? 0;
  return {
    model: {
      name: "kinetic-v1",
      version: "fixture",
      method: "Fixture curves (dev only, not the engine)",
      members: 200,
      effective_members: 200,
      confidence: "established",
      confidence_note: null,
      validated: false,
      sources: ["fixture.js"],
    },
    fermentation_type: "sourdough",
    started_at: new Date().toISOString(),
    now_h: 0,
    horizon_h: horizon,
    horizon_options_h: [horizon],
    temperature: { forecast_c: tl, source: "expected", type_default_c: 26, range_c: [22, 30], readings: 0 },
    status: "prior_only",
    series,
    observations: [],
    milestones,
    reference_lines: [],
    organisms: (CATALOG.styles.find((x) => x.key === plan.style)?.organisms || []).map((name) => ({
      name,
      kingdom: name === SC || name === KH ? "fungi" : "bacteria",
      modelled: true,
      growing: true,
      role: name === SC || name === KH ? "yeast: CO₂ and ethanol" : "lactic acid bacterium: acids",
      note: null,
      series_key: `pop:${name}`,
      pathways: [],
      sources: ["fixture"],
    })),
    initial: { source: "recipe", values: { ph: 6.1, maltose: 22 } },
    assumptions: ["Fixture data: shapes only, not model output."],
    warnings: r > 12 ? ["Very small seed: the first hours are slow and the timing is less certain."] : [],
    disclaimer:
      "A model estimate from published sourdough kinetics, not a measurement. Your flour, starter and kitchen differ: watch the dough, not the clock.",
    phases,
    summary: {
      style: plan.style,
      levain_hydration_pct: lv ? Math.round(hyd) : null,
      seed_ratio: lv ? `1:${+r.toFixed(2)}:${+((r * hyd) / 100).toFixed(2)}` : null,
      levain_pct_of_flour: d?.levain_g ? +((d.levain_g / total) * 100).toFixed(1) : null,
      dough_hydration_pct: d ? +(((d.water_g + (d.levain_g ?? 0) / 2) / total) * 100).toFixed(1) : null,
      salt_pct_of_flour: d ? +((d.salt_g / total) * 100).toFixed(1) : null,
      total_flour_g: Math.round(total),
    },
  };
}

function feedingChart(body) {
  return {
    temperature_c: body.temperature_c,
    rows: body.ratios.map((r) => {
      const p = peakH(r, body.temperature_c, body.starter);
      return {
        ratio: r,
        label: `1:${r}:${+((r * body.hydration_pct) / 100).toFixed(2)}`,
        peak_h: band(p),
        doubled_h: band(p * 0.62),
        ph_at_peak: +(4.3 - 0.02 * r).toFixed(2),
        rise_at_peak_pct: body.hydration_pct < 70 ? 110 : 170,
      };
    }),
  };
}

export function fixtureAnswer(path, body, signal) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      if (path === "/sourdough/catalog") resolve(CATALOG);
      else if (path === "/sourdough/plan") resolve(simulate(body));
      else if (path === "/sourdough/feeding-chart") resolve(feedingChart(body));
      else reject(new Error(`fixture: no answer for ${path}`));
    }, 700);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}
