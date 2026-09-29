// Share a planner plan by link (the plan JSON rides in the URL hash: no backend,
// never sent to any server) and put its timings in a calendar (.ics, RFC 5545).
// Pure, no React, no import.meta: `node share.check.mjs` runs it.
import { clockAt, fmtClock, planToForm } from "./plan.js";

const MAX_PARAM = 4000; // a plan is ~600 chars encoded; anything much longer is not ours

const b64url = (bytes) => {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

// Plan -> URL-safe token. culture_id is dropped: it names the sender's starter.
export function encodePlan(plan) {
  return b64url(new TextEncoder().encode(JSON.stringify({ v: 1, plan: { ...plan, culture_id: null } })));
}

// Token -> the raw payload's plan, or null for anything malformed.
export function decodePlan(token) {
  try {
    if (typeof token !== "string" || !token || token.length > MAX_PARAM || !/^[A-Za-z0-9_-]+$/.test(token)) return null;
    const bin = atob(token.replace(/-/g, "+").replace(/_/g, "/"));
    const json = new TextDecoder("utf-8", { fatal: true }).decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
    const doc = JSON.parse(json);
    return doc && doc.v === 1 && doc.plan && typeof doc.plan === "object" && !Array.isArray(doc.plan) ? doc.plan : null;
  } catch {
    return null;
  }
}

// Untrusted plan -> a plan with only known keys and types (numbers finite or null,
// enums checked, flours from the catalog). Ranges are formToPlan's job: an absurd
// value lands in the form as a highlighted field, not as a crash.
export function cleanPlan(raw, catalog) {
  const obj = (x) => (x && typeof x === "object" && !Array.isArray(x) ? x : null);
  const n = (x) => (typeof x === "number" && Number.isFinite(x) ? x : null);
  const pick = (x, allowed, dflt) => (allowed.includes(x) ? x : dflt);
  const blend = (b) => {
    const out = {};
    for (const [k, s] of Object.entries(obj(b) || {}).slice(0, 4)) {
      if (catalog.flours.some((f) => f.key === k) && n(s) > 0 && s <= 1) out[k] = s;
    }
    return Object.keys(out).length ? out : null;
  };
  const lv = obj(raw.levain);
  const d = obj(raw.dough);
  const p = obj(raw.proof);
  const style = catalog.styles.some((s) => s.key === raw.style) ? raw.style : catalog.styles[0]?.key;
  return {
    style,
    starter: pick(raw.starter, ["ripe", "refrigerated"], "ripe"),
    culture_id: null,
    levain: lv && {
      seed_g: n(lv.seed_g),
      flour_g: n(lv.flour_g),
      water_g: n(lv.water_g),
      flour: blend(lv.flour),
      temperature_c: n(lv.temperature_c),
      hours: n(lv.hours),
    },
    dough: d && {
      flour_g: n(d.flour_g),
      water_g: n(d.water_g),
      salt_g: n(d.salt_g),
      flour: blend(d.flour),
      temperature_c: n(d.temperature_c),
      levain_g: n(d.levain_g),
      yeast_g: n(d.yeast_g) ?? 0,
      yeast: pick(d.yeast, ["instant", "fresh"], "instant"),
      dried_sour_g: n(d.dried_sour_g) ?? 0,
      bulk_hours: n(d.bulk_hours),
      target_rise_pct: n(d.target_rise_pct),
    },
    proof: p && { temperature_c: n(p.temperature_c), hours: n(p.hours) },
  };
}

// "#/levain?p=<token>" -> planner form, or null (no token, or malformed).
export function sharedForm(hash, catalog) {
  const m = /^#\/levain\?(.*)$/.exec(hash || "");
  if (!m) return null;
  const raw = decodePlan(new URLSearchParams(m[1]).get("p"));
  if (!raw) return null;
  try {
    return planToForm(cleanPlan(raw, catalog), catalog);
  } catch {
    return null;
  }
}

// Link to this plan on this deployment (origin + path only: no ?batch=, no start time).
export const shareUrl = (plan, loc) => `${loc.origin}${loc.pathname}#/levain?p=${encodePlan(plan)}`;

// ── calendar ─────────────────────────────────────────────────────────────

// API answer -> the moments a baker acts on, on the same 10-minute clock as the screen.
export function planEvents(data, startMs, name = "Levain") {
  const ms = Object.fromEntries((data?.milestones || []).map((m) => [m.key, m]));
  const ph = Object.fromEntries((data?.phases || []).map((p) => [p.key, p]));
  const c = (h) => fmtClock(clockAt(startMs, h), startMs);
  const range = (t) => (t?.p05 != null && t?.p95 != null ? `Likely between ${c(t.p05)} and ${c(t.p95)}. ` : "");
  const note = "Model estimate from FermentTrack: watch the dough, not only the clock.";
  const out = [];
  const add = (key, title, h, t) => h != null && out.push({ key, title, at: clockAt(startMs, h), description: range(t) + note });
  const peak = ms.levain_peak?.t_h;
  add("peak", `${name} peaks`, peak?.p50, peak);
  const mix = ph.bulk?.start_h;
  // Mixing at the peak (the default) is the same moment: one alarm, not two.
  if (mix != null && (peak?.p50 == null || +clockAt(startMs, mix) !== +clockAt(startMs, peak.p50))) add("mix", "Mix the dough", mix);
  const bulk = ms.bulk_target?.t_h;
  add("bulk", "Bulk done", bulk?.p50, bulk);
  if (ph.proof) add("bake", "Into the oven", ph.proof.end_h);
  return out;
}

const utc = (d) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, ""); // 20260929T044000Z

// RFC 5545 § 3.3.11 TEXT escaping.
export const icsText = (s) => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

// § 3.1: lines of at most 75 octets, continued with CRLF + one space; never split a character.
export function foldLine(line) {
  const parts = [];
  let cur = "";
  let octets = 0;
  for (const ch of line) {
    const cp = ch.codePointAt(0);
    const b = cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
    if (octets + b > (parts.length ? 74 : 75)) {
      parts.push(cur);
      cur = "";
      octets = 0;
    }
    cur += ch;
    octets += b;
  }
  parts.push(cur);
  return parts.join("\r\n ");
}

// Events -> .ics text. Times in UTC (unambiguous; the calendar shows them in its own
// zone). UID keyed on the feed time, so re-exporting the same bake updates, not duplicates.
export function buildIcs(events, startMs, now = new Date()) {
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FermentTrack//Levain planner//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"];
  for (const e of events) {
    lines.push(
      "BEGIN:VEVENT",
      `UID:${startMs}-${e.key}@fermenttrack`,
      `DTSTAMP:${utc(now)}`,
      `DTSTART:${utc(e.at)}`,
      "DURATION:PT15M",
      `SUMMARY:${icsText(e.title)}`,
      `DESCRIPTION:${icsText(e.description)}`,
      "BEGIN:VALARM",
      "ACTION:DISPLAY",
      `DESCRIPTION:${icsText(e.title)}`,
      "TRIGGER:-PT15M",
      "END:VALARM",
      "END:VEVENT"
    );
  }
  lines.push("END:VCALENDAR");
  return lines.map(foldLine).join("\r\n") + "\r\n";
}
