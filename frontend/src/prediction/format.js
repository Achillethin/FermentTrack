// Formatting helpers for the forecast panel. Everything here is pure.

// Unit for a span of hours: hours under 48 h, days otherwise.
export function unitFor(hours) {
  return Math.abs(hours) < 48 ? "h" : "d";
}

function roundIn(hours, unit) {
  if (unit === "h") {
    const h = Math.abs(hours);
    return h < 1 ? Math.round(h * 10) / 10 : Math.round(h);
  }
  const d = Math.abs(hours) / 24;
  return d < 10 ? Math.round(d * 10) / 10 : Math.round(d);
}

function unitWord(n, unit) {
  if (unit === "h") return "h";
  return n === 1 ? "day" : "days";
}

// "7 h", "1.8 days", "12 days"
export function duration(hours, unit = unitFor(hours)) {
  const n = roundIn(hours, unit);
  if (unit === "h" && n < 1) return "<1 h";
  return `${n} ${unitWord(n, unit)}`;
}

// "34–58 h", "1.4–2.4 days"; ends in different units keep their own:
// "20 h – 4.3 days". `unit` forces one unit for both ends when they agree.
export function durationRange(a, b, unit) {
  const ua = unitFor(a);
  const ub = unitFor(b);
  if (ua !== ub) return `${duration(a, ua)} – ${duration(b, ub)}`;
  const u = unit && unit === ua ? unit : ua;
  const x = roundIn(a, u);
  const y = roundIn(b, u);
  if (x === y) return duration(a, u);
  return `${x}–${y} ${unitWord(y, u)}`;
}

// API timestamps are UTC; some arrive without a zone ("2026-09-23T18:49:45"),
// which JS would read as local time. Treat zone-less ones as UTC.
export function parseApiDate(s) {
  if (s == null) return null;
  const str = String(s);
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(str) ? str : `${str}Z`);
}

export function dateAt(startedAt, tH) {
  return new Date(parseApiDate(startedAt).getTime() + tH * 3600 * 1000);
}

// Wall-clock for a model time. Includes the hour only when it is close
// enough (< 48 h away) for the hour to mean something.
export function wallClock(startedAt, tH, withHour = true) {
  const d = dateAt(startedAt, tH);
  const day = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  if (!withHour) return day;
  const hour = d.toLocaleTimeString(undefined, { hour: "numeric" });
  return `${day}, ${hour}`;
}

// Axis time unit for a horizon: hours up to 3 days, days beyond.
export function axisUnit(horizonH) {
  return horizonH <= 72 ? "h" : "d";
}

export function timeLabel(tH, unit) {
  if (unit === "h") return `${Math.round(tH * 10) / 10} h`;
  const d = tH / 24;
  return `day ${d < 10 ? Math.round(d * 10) / 10 : Math.round(d)}`;
}

// Value formatting by series unit.
export function decimalsFor(unit, span = 10) {
  if (unit === "SG") return 4; // gravity: 1.0309
  if (unit === "") return 2; // pH
  if (unit === "%") return 0;
  if (unit === "log CFU/g") return 1;
  if (span < 2) return 2;
  return 1;
}

export function fmtValue(v, unit, span) {
  if (v == null || Number.isNaN(v)) return "–";
  return v.toFixed(decimalsFor(unit, span));
}

export function unitSuffix(unit) {
  if (!unit) return "";
  if (unit === "SG") return "";
  return ` ${unit}`;
}

export function pct(p) {
  return `${Math.round(p * 100)} %`;
}

// Classifies a milestone relative to now and builds the plain-language text.
// All model times are hours since started_at.
export function describeMilestone(m, nowH, horizonH, startedAt) {
  const { p05, p50, p95 } = m.t_h || {};
  const prob = m.probability ?? 1;
  const showProb = prob < 0.95;
  if (p50 == null) {
    return {
      state: "unlikely",
      when: `Not within the forecast window (${duration(horizonH)}) in most model runs`,
      range: prob > 0 ? `reached in ${pct(prob)} of model runs` : null,
      date: null,
      prob,
      showProb: false,
      sortKey: Infinity,
    };
  }

  const closeBy = Math.abs(p50 - nowH) < 48;
  // Times of exactly 0 mean "already true when the batch started" (e.g. a
  // kombucha starter that acidifies the tea at once): say so, not "N h ago".
  const atStart = p50 <= 0;
  const startDate = { date: null };

  if (p95 != null && p95 <= nowH) {
    const unit = unitFor(nowH - p50);
    let range;
    if (atStart) range = p95 > 0 ? `90 % range: from the start up to ${duration(p95)} after it` : null;
    else if (p05 != null && p05 <= 0) range = `90 % range: from the start to ${duration(nowH - p95)} ago`;
    else range = `90 % range: ${durationRange(nowH - p95, nowH - (p05 ?? p50), unit)} ago`;
    return {
      state: "reached",
      when: atStart ? "Likely already true at the start" : `Likely reached ~${duration(nowH - p50, unit)} ago`,
      range,
      ...(atStart ? startDate : { date: wallClock(startedAt, p50, closeBy) }),
      prob,
      showProb: false,
      sortKey: p50,
    };
  }
  if (p50 <= nowH) {
    return {
      state: "probably",
      when: atStart ? "Probably already true at the start" : `Probably reached ~${duration(nowH - p50)} ago`,
      range:
        p95 != null
          ? `could still be up to ${duration(p95 - nowH)} away`
          : "could still be after the forecast window",
      ...(atStart ? startDate : { date: wallClock(startedAt, p50, closeBy) }),
      prob,
      showProb,
      sortKey: p50,
    };
  }
  const unit = unitFor(p50 - nowH);
  const lo = p05 == null || p05 <= nowH ? "now" : null;
  let range;
  if (p95 == null) {
    range = lo
      ? `90 % range: from now to after the window`
      : `90 % range: ${duration(p05 - nowH)} to after the window`;
  } else if (lo) {
    range = `90 % range: now to ${duration(p95 - nowH)}`;
  } else {
    range = `90 % range: ${durationRange(p05 - nowH, p95 - nowH, unit)}`;
  }
  return {
    state: lo ? "soon" : "upcoming",
    when: `in ~${duration(p50 - nowH, unit)}`,
    range,
    date: wallClock(startedAt, p50, closeBy),
    prob,
    showProb,
    sortKey: p50,
  };
}

export const TEMP_SOURCE_TEXT = {
  override: "what-if, not saved",
  expected: "your estimate",
  measured: "from your logged temperatures",
  type_default: "typical for this ferment",
};
