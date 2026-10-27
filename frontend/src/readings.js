// A typed reading (site critique fixes 2 and 5), shared by the batch page and Today: "5,8" is
// 5.8 (a French keyboard), never 5; pH sits on its 0-14 scale, as the API requires, and one
// outside 3-7 is unusual for a ferment, so the caller asks before saving it.
export function parseReading(text, type) {
  const t = String(text ?? "").trim().replace(",", ".");
  if (!t) return { value: null };
  const value = Number(t);
  if (!Number.isFinite(value)) return { error: "Enter a number, e.g. 4.2" };
  if (type === "pH" && (value < 0 || value > 14)) return { error: "pH runs from 0 to 14" };
  return { value, unusual: type === "pH" && (value < 3 || value > 7) };
}

export const unusualPh = (v) => `pH ${v}? Most ferments sit between 3 and 7. Save anyway?`;
