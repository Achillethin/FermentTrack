// Flatten GET /me/export (cultures -> batches -> measurements) to RFC 4180 CSV.
// Column kind: "t" = user-authored text (formula-injection guarded), "r" = raw (ids, timestamps, numbers).
const COLS = [
  ["culture_id", "r", (c) => c.id],
  ["culture_name", "t", (c) => c.name],
  ["culture_type", "t", (c) => c.type],
  ["culture_born_from", "r", (c) => c.born_from],
  ["culture_status", "t", (c) => c.status],
  ["culture_created_at", "r", (c) => c.created_at],
  ["batch_id", "r", (c, b) => b?.id],
  ["batch_started_at", "r", (c, b) => b?.started_at],
  ["batch_current_stage", "t", (c, b) => b?.current_stage],
  ["batch_target", "t", (c, b) => b?.target],
  ["batch_expected_temperature_c", "r", (c, b) => b?.expected_temperature_c],
  ["batch_outcome", "t", (c, b) => b?.outcome],
  ["batch_ended_at", "r", (c, b) => b?.ended_at],
  ["measurement_id", "r", (c, b, m) => m?.id],
  ["measured_at", "r", (c, b, m) => m?.measured_at],
  ["measurement_type", "t", (c, b, m) => m?.type],
  ["value_numeric", "r", (c, b, m) => m?.value_numeric],
  ["value_text", "t", (c, b, m) => m?.value_text],
  ["notes", "t", (c, b, m) => m?.notes],
];

function cell(v, kind) {
  if (v == null) return "";
  let s = typeof v === "object" ? JSON.stringify(v) : String(v);
  // Leading quote defuses spreadsheet formulas (OWASP CSV injection), incl. after whitespace/NBSP and
  // full-width look-alikes; never applied to numbers.
  if (kind === "t" && /^[\s ]*[=+\-@＝＋－＠]|^[\t\r]/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv(cultures) {
  const rows = [COLS.map(([h]) => h).join(",")];
  const push = (c, b, m) => rows.push(COLS.map(([, k, get]) => cell(get(c, b, m), k)).join(","));
  for (const c of cultures) {
    if (!c.batches?.length) push(c);
    for (const b of c.batches ?? []) {
      if (!b.measurements?.length) push(c, b);
      // Chronological within a batch (ISO strings sort lexically; stable on ties).
      const ms = [...(b.measurements ?? [])].sort((x, y) => (x.measured_at < y.measured_at ? -1 : x.measured_at > y.measured_at ? 1 : 0));
      for (const m of ms) push(c, b, m);
    }
  }
  return rows.join("\r\n") + "\r\n";
}
