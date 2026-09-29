// Pure helpers for the levain planner: the form a baker fills in (text inputs,
// baker's percentages) <-> the plan JSON the API takes (grams), plus clock
// formatting. Contract: docs/superpowers/specs/2026-09-28-sourdough-engine-design.md
// § 3 and Appendix A. No React, no import.meta: `node plan.check.mjs` runs it.

export const PRESETS = [1, 2, 3, 5, 10];
export const CHART_RATIOS = [1, 2, 3, 5, 8, 10];

export const num = (s) => {
  const v = parseFloat(String(s ?? "").trim().replace(",", "."));
  return Number.isFinite(v) ? v : NaN;
};
const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d;
const str = (v) => (v == null ? "" : String(v));

// seed_ratio r means feed 1 : r : r·hydration.
export const ratioLabel = (r, hydration) => `1:${round(r, 2)}:${round((r * hydration) / 100, 2)}`;

export const styleOf = (catalog, key) => catalog.styles.find((s) => s.key === key);
export const seedKind = (catalog, key) => styleOf(catalog, key)?.seed ?? "starter";
export const flourLabel = (f) => (f.us_name ? `${f.name} · ${f.us_name}` : f.name);

export function applyStyle(form, catalog, key) {
  const s = styleOf(catalog, key);
  const d = s?.defaults || {};
  const next = { ...form, style: key, custom: false, flour2: "", levainHours: str(d.hours) };
  if (d.hydration_pct > 0) next.hydration = str(d.hydration_pct);
  if (d.seed_ratio > 0) next.ratio = d.seed_ratio;
  if (d.temperature_c != null) next.levainTemp = str(d.temperature_c);
  if (d.flour) next.flour = d.flour;
  if (s?.seed === "yeast") next.pYeast = str(round(num(next.pFlour) / (d.seed_ratio || 1000), 2));
  // Type III has no build: it only exists in a yeasted dough.
  if (s?.seed === "dried") Object.assign(next, { doughOn: true, yeastG: num(next.yeastG) > 0 ? next.yeastG : "5" });
  return next;
}

export function defaultForm(catalog, style = catalog.styles[0]?.key) {
  const base = {
    style,
    starter: "ripe",
    cultureId: "",
    // levain build
    ratio: 3,
    custom: false,
    seedG: "20",
    cSeed: "20",
    cFlour: "60",
    cWater: "60",
    pFlour: "100", // pre-ferment (seed: yeast) flour
    pYeast: "0.1",
    hydration: "100",
    flour: catalog.flours[0]?.key ?? "t65",
    flour2: "",
    share2: "20",
    levainTemp: "24",
    levainHours: "", // "" = mix at the median peak
    // dough
    doughOn: false,
    totalFlour: "500",
    doughHydration: "72",
    saltPct: "2",
    levainPct: "20",
    doughFlour: "", // "" = same flour as the levain
    targetRise: "75",
    doughTemp: "25",
    yeastG: "0",
    yeastType: "instant",
    driedG: "25",
    bulkHours: "", // "" = until target rise
    proof: "none", // none | room | cold
    proofTemp: "4",
    proofHours: "14",
  };
  return applyStyle(base, catalog, style);
}

export function blendOf(f) {
  const s = num(f.share2) / 100;
  return f.flour2 && f.flour2 !== f.flour && s > 0 && s < 1
    ? { [f.flour]: round(1 - s, 3), [f.flour2]: round(s, 3) }
    : { [f.flour]: 1 };
}

/**
 * Form -> { plan, errors, info }. plan is null while any field is invalid.
 * info carries the derived grams the form shows back to the baker.
 */
export function formToPlan(f, catalog) {
  const kind = seedKind(catalog, f.style);
  const errors = {};
  const check = (key, raw, lo, hi, { optional = false, open = false } = {}) => {
    if (optional && String(raw ?? "").trim() === "") return null;
    const v = num(raw);
    if (!Number.isFinite(v)) errors[key] = "Enter a number";
    else if (v < lo || (open && v === lo) || v > hi) errors[key] = open ? `More than ${lo}, up to ${hi}` : `Between ${lo} and ${hi}`;
    return v;
  };
  const info = {};
  const blend = blendOf(f);
  if (f.flour2) check("share2", f.share2, 1, 99);

  let levain = null;
  if (kind !== "dried") {
    let seed;
    let flour;
    let water;
    if (kind === "yeast") {
      flour = check("pFlour", f.pFlour, 0, 20000, { open: true });
      seed = check("pYeast", f.pYeast, 0, 200, { open: true });
      water = (flour * check("hydration", f.hydration, 20, 300)) / 100;
    } else if (f.custom) {
      seed = check("cSeed", f.cSeed, 0, 5000, { open: true });
      flour = check("cFlour", f.cFlour, 0, 20000, { open: true });
      water = check("cWater", f.cWater, 0, 20000);
    } else {
      seed = check("seedG", f.seedG, 0, 5000, { open: true });
      if (!(f.ratio > 0 && f.ratio <= 1000)) errors.ratio = "Pick a feeding ratio";
      flour = seed * f.ratio;
      water = (flour * check("hydration", f.hydration, 20, 300)) / 100;
    }
    const hours = check("levainHours", f.levainHours, 0, 72, { optional: true, open: true });
    levain = {
      seed_g: round(seed, 2),
      flour_g: round(flour, 1),
      water_g: round(water, 1),
      flour: blend,
      temperature_c: check("levainTemp", f.levainTemp, 0, 45),
      hours,
    };
    info.levainG = seed + flour + water;
    info.levainHydration = flour > 0 ? (water / flour) * 100 : NaN;
  }

  let dough = null;
  let proof = null;
  if (f.doughOn) {
    const total = check("totalFlour", f.totalFlour, 0, 100000, { open: true });
    const hyd = check("doughHydration", f.doughHydration, 30, 150);
    const salt = check("saltPct", f.saltPct, 0, 5);
    const pct = kind === "dried" ? 0 : check("levainPct", f.levainPct, 0, 100, { open: true });
    // The levain carries flour and water at its own hydration (the seed is
    // taken to be at the same hydration as the build).
    const ff = kind === "dried" ? 1 : 1 / (1 + info.levainHydration / 100);
    const levainG = (total * pct) / 100;
    const flourG = total - levainG * ff;
    const waterG = (total * hyd) / 100 - levainG * (1 - ff);
    if (flourG <= 0) errors.levainPct = "More levain than flour";
    if (waterG < 0) errors.doughHydration = "Too low for this much levain";
    Object.assign(info, { doughFlourG: flourG, doughWaterG: waterG, saltG: (total * salt) / 100, doughLevainG: levainG });
    if (kind !== "dried" && levainG > info.levainG + 0.05) {
      info.short = levainG - info.levainG;
      errors.levainPct = "More than the build makes";
    }
    dough = {
      flour_g: round(flourG, 1),
      water_g: round(waterG, 1),
      salt_g: round((total * salt) / 100, 1),
      flour: f.doughFlour ? { [f.doughFlour]: 1 } : blend,
      temperature_c: check("doughTemp", f.doughTemp, 0, 45),
      levain_g: kind === "dried" ? null : round(levainG, 1),
      yeast_g: check("yeastG", f.yeastG, 0, 500),
      yeast: f.yeastType,
      dried_sour_g: kind === "dried" ? check("driedG", f.driedG, 0, 5000, { open: true }) : 0,
      bulk_hours: check("bulkHours", f.bulkHours, 0, 48, { optional: true, open: true }),
      target_rise_pct: check("targetRise", f.targetRise, 10, 300),
    };
    if (f.proof !== "none") {
      proof = {
        temperature_c: check("proofTemp", f.proofTemp, -5, 45),
        hours: check("proofHours", f.proofHours, 0, 96, { open: true }),
      };
    }
  }

  const plan = { style: f.style, starter: f.starter, culture_id: f.cultureId || null, levain, dough, proof };
  return { plan: Object.keys(errors).length ? null : plan, errors, info };
}

// Scale the build so it makes at least `grams` (rounded up to whole grams of seed).
export function scaleBuild(f, catalog, grams) {
  const kind = seedKind(catalog, f.style);
  const h = num(f.hydration) / 100;
  if (kind === "yeast") {
    const k = grams / (num(f.pFlour) * (1 + h) + num(f.pYeast));
    return { ...f, pFlour: str(Math.ceil(num(f.pFlour) * k)), pYeast: str(round(num(f.pYeast) * k, 2)) };
  }
  if (f.custom) {
    const k = grams / (num(f.cSeed) + num(f.cFlour) + num(f.cWater));
    return { ...f, cSeed: str(Math.ceil(num(f.cSeed) * k)), cFlour: str(Math.ceil(num(f.cFlour) * k)), cWater: str(Math.ceil(num(f.cWater) * k)) };
  }
  return { ...f, seedG: str(Math.ceil(grams / (1 + f.ratio * (1 + h)))) };
}

const sameBlend = (a = {}, b = {}) => {
  const ka = Object.keys(a);
  return ka.length === Object.keys(b).length && ka.every((k) => Math.abs(a[k] - (b[k] ?? -1)) < 1e-6);
};

// Stored plan -> form, for editing a batch's plan. ponytail: a dough blend of
// several flours that differs from the levain's keeps only its main flour
// (the form offers one dough flour); plans made here never have one.
export function planToForm(plan, catalog) {
  const f = defaultForm(catalog, styleOf(catalog, plan.style) ? plan.style : undefined);
  f.starter = plan.starter || "ripe";
  f.cultureId = plan.culture_id || "";
  const kind = seedKind(catalog, f.style);
  const lv = plan.levain;
  let levainBlend = { [f.flour]: 1 };
  let ff = 1;
  let built = 0;
  if (lv) {
    levainBlend = lv.flour || levainBlend;
    const [a, b] = Object.entries(levainBlend).sort((x, y) => y[1] - x[1]);
    if (a) f.flour = a[0];
    f.flour2 = b ? b[0] : "";
    if (b) f.share2 = str(round(b[1] * 100, 1));
    f.levainTemp = str(lv.temperature_c);
    f.levainHours = str(lv.hours);
    const h = lv.flour_g > 0 ? (lv.water_g / lv.flour_g) * 100 : 100;
    ff = 1 / (1 + h / 100);
    built = lv.seed_g + lv.flour_g + lv.water_g;
    if (kind === "yeast") {
      Object.assign(f, { pFlour: str(lv.flour_g), pYeast: str(lv.seed_g), hydration: str(round(h, 1)) });
    } else {
      // Ratio mode only for a half-step ratio (1:2.5) whose grams it reproduces.
      const r = Math.round((lv.flour_g / lv.seed_g) * 2) / 2;
      const exact =
        Math.abs(round(lv.seed_g * r, 1) - lv.flour_g) < 0.051 &&
        Math.abs(round((lv.flour_g * round(h, 1)) / 100, 1) - lv.water_g) < 0.051;
      if (exact) Object.assign(f, { custom: false, ratio: r, seedG: str(lv.seed_g), hydration: str(round(h, 1)) });
      else Object.assign(f, { custom: true, cSeed: str(lv.seed_g), cFlour: str(lv.flour_g), cWater: str(lv.water_g) });
    }
  }
  const d = plan.dough;
  f.doughOn = !!d || kind === "dried";
  if (d) {
    const levainG = kind === "dried" ? 0 : d.levain_g ?? built;
    const total = d.flour_g + levainG * ff;
    Object.assign(f, {
      totalFlour: str(round(total, 1)),
      doughHydration: str(round(((d.water_g + levainG * (1 - ff)) / total) * 100, 1)),
      saltPct: str(round((d.salt_g / total) * 100, 2)),
      levainPct: str(round((levainG / total) * 100, 1)),
      doughFlour: !d.flour || sameBlend(d.flour, levainBlend)
        ? ""
        : Object.entries(d.flour || {}).sort((x, y) => y[1] - x[1])[0]?.[0] ?? "",
      targetRise: str(d.target_rise_pct ?? 75),
      doughTemp: str(d.temperature_c),
      yeastG: str(d.yeast_g ?? 0),
      yeastType: d.yeast || "instant",
      driedG: str(d.dried_sour_g ?? 0),
      bulkHours: str(d.bulk_hours),
    });
  }
  const p = plan.proof;
  f.proof = !p ? "none" : p.temperature_c <= 10 ? "cold" : "room";
  if (p) Object.assign(f, { proofTemp: str(p.temperature_c), proofHours: str(p.hours) });
  return f;
}

// One line per part, for the plan card on a batch.
export function describePlan(plan, catalog) {
  const style = styleOf(catalog, plan.style);
  const flourName = (blend) =>
    Object.entries(blend || {})
      .sort((a, b) => b[1] - a[1])
      .map(([k, s]) => {
        const n = catalog.flours.find((x) => x.key === k)?.name ?? k;
        return s < 1 ? `${n} ${Math.round(s * 100)} %` : n;
      })
      .join(" + ");
  const lines = [];
  const lv = plan.levain;
  if (lv) {
    const h = lv.flour_g > 0 ? (lv.water_g / lv.flour_g) * 100 : 100;
    const seed = style?.seed === "yeast" ? `${lv.seed_g} g yeast` : `${lv.seed_g} g starter`;
    const ratio = style?.seed === "yeast" ? "" : ` (${ratioLabel(lv.flour_g / lv.seed_g, h)})`;
    lines.push(
      `${style?.name ?? plan.style}: ${seed} + ${lv.flour_g} g flour + ${lv.water_g} g water${ratio}, ${flourName(lv.flour)}, ${lv.temperature_c} °C` +
        (plan.starter === "refrigerated" ? ", starter from the fridge" : "")
    );
  } else if (style) lines.push(style.name);
  const d = plan.dough;
  if (d) {
    const extra = [
      d.levain_g ? `${d.levain_g} g levain` : null,
      d.dried_sour_g ? `${d.dried_sour_g} g dried sourdough` : null,
      d.yeast_g ? `${d.yeast_g} g ${d.yeast} yeast` : null,
    ].filter(Boolean);
    lines.push(
      `Dough: ${d.flour_g} g flour + ${d.water_g} g water + ${d.salt_g} g salt${extra.length ? ` + ${extra.join(" + ")}` : ""}, ${d.temperature_c} °C, ` +
        (d.bulk_hours ? `bulk ${d.bulk_hours} h` : `bulk until +${d.target_rise_pct ?? 75} %`)
    );
  }
  const p = plan.proof;
  if (p) lines.push(`${p.temperature_c <= 10 ? "Cold retard" : "Proof"}: ${p.hours} h at ${p.temperature_c} °C`);
  return lines;
}

// ── clock ────────────────────────────────────────────────────────────────

const pad = (n) => String(n).padStart(2, "0");

// "2026-09-28T22:00" for <input type="datetime-local">, in local time.
export function toLocalInput(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}`;
}

// Model hours -> wall clock, rounded to 10 minutes (the model is not finer).
export function clockAt(startMs, h) {
  return new Date(Math.round((startMs + h * 3_600_000) / 600_000) * 600_000);
}

// "06:40", or "Tue 06:40" when it falls on another day than the start.
export function fmtClock(date, startMs) {
  const hm = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  return new Date(startMs).toDateString() === date.toDateString()
    ? hm
    : `${date.toLocaleDateString(undefined, { weekday: "short" })} ${hm}`;
}

export const clock = (startMs, h) => (h == null ? null : fmtClock(clockAt(startMs, h), startMs));

// "07:00" -> hours from the start to the next 07:00 after it.
export function hoursUntil(startMs, hhmm) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm || "");
  if (!m) return null;
  const t = new Date(startMs);
  t.setHours(+m[1], +m[2], 0, 0);
  if (t.getTime() <= startMs) t.setDate(t.getDate() + 1);
  return (t.getTime() - startMs) / 3_600_000;
}

// Index of the feeding-chart row whose median peak is nearest to targetH.
export function closestRow(rows, targetH) {
  let best = -1;
  rows.forEach((r, i) => {
    const p = r.peak_h?.p50;
    if (p == null) return;
    if (best < 0 || Math.abs(p - targetH) < Math.abs(rows[best].peak_h.p50 - targetH)) best = i;
  });
  return best;
}
