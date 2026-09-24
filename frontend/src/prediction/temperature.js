// Typical fermentation temperature per ferment type, in °C.
// Mirrors the temperature profiles in fermenttrack.prediction (backend); keep
// both in sync. Used for hints/placeholders only: the API is the source of
// truth for the forecast (its response carries temperature.range_c).
export const TYPICAL_TEMPERATURE_C = {
  kombucha: { typical: 24, range: [20, 28] },
  sourdough: { typical: 26, range: [22, 30] },
  koji: { typical: 30, range: [28, 35] },
  cheese: { typical: 30, range: [28, 32] },
  lacto_ferment: { typical: 20, range: [16, 24] },
  miso: { typical: 25, range: [15, 30] },
  garum: { typical: 30, range: [20, 60] },
  kefir: { typical: 22, range: [18, 25] },
  vinegar: { typical: 27, range: [24, 30] },
};

// Same bounds as the API (422 outside them).
export const TEMP_MIN_C = -5;
export const TEMP_MAX_C = 60;

export function formatC(value) {
  if (value == null || Number.isNaN(value)) return "";
  const rounded = Math.round(value * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)} °C`;
}

export function typicalHint(type) {
  const t = TYPICAL_TEMPERATURE_C[type];
  if (!t) return null;
  return `Typical for ${type.replace(/_/g, " ")}: ${t.typical} °C (${t.range[0]}–${t.range[1]} °C)`;
}

// Parses the text of a temperature input. Returns
// { value: number|null, error: string|null, fahrenheitAsC: number|null }.
// Empty input is valid and means "no estimate" (value null).
export function parseTemperature(text) {
  const raw = String(text ?? "").trim().replace(",", ".");
  if (raw === "") return { value: null, error: null, fahrenheitAsC: null };
  const v = Number(raw);
  if (!Number.isFinite(v)) {
    return { value: null, error: "Enter a number in °C, e.g. 21.5", fahrenheitAsC: null };
  }
  if (v > TEMP_MAX_C) {
    // 61-140 °F is -5-60 °C: a value in that span is most likely Fahrenheit.
    const asC = (v - 32) * (5 / 9);
    if (v <= 140) {
      const suggestion = Math.round(asC * 2) / 2;
      return {
        value: null,
        error: `${v} °C is hotter than any ferment here (max ${TEMP_MAX_C} °C). If you meant ${v} °F, that is about ${formatC(suggestion)}.`,
        fahrenheitAsC: suggestion,
      };
    }
    return { value: null, error: `Use a value between ${TEMP_MIN_C} and ${TEMP_MAX_C} °C.`, fahrenheitAsC: null };
  }
  if (v < TEMP_MIN_C) {
    return { value: null, error: `Use a value between ${TEMP_MIN_C} and ${TEMP_MAX_C} °C.`, fahrenheitAsC: null };
  }
  return { value: Math.round(v * 10) / 10, error: null, fahrenheitAsC: null };
}
