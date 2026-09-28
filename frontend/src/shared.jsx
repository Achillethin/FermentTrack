// Helpers shared across views, moved verbatim from App.jsx.

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

// Mirrors fermenttrack.stages.STAGE_MACHINES (kombucha/sourdough/koji/cheese/
// lacto_ferment/miso/garum have real stage progressions) plus kefir/vinegar,
// which have Ingredient/BatchIngredient recipe logging but no stage machine
// yet (single "in_progress" pseudo-stage, no reminder automation).
const SUBSTRATES = [
  "kombucha",
  "sourdough",
  "koji",
  "cheese",
  "lacto_ferment",
  "miso",
  "garum",
  "kefir",
  "vinegar",
];

function urgencyColor(urgency) {
  return (
    {
      critical: "text-red-400 border-red-500/40 bg-red-950/40",
      high: "text-orange-400 border-orange-500/40 bg-orange-950/40",
      medium: "text-amber-400 border-amber-500/40 bg-amber-950/40",
      low: "text-slate-400 border-slate-600/40 bg-slate-800/40",
    }[urgency] || "text-slate-400 border-slate-600/40 bg-slate-800/40"
  );
}

function Card({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

// detail is a string on 404/409 but a list on 422; network failures are TypeErrors.
async function apiError(res, fallback) {
  const body = await res.json().catch(() => ({}));
  return typeof body.detail === "string" ? body.detail : `${fallback} (${res.status})`;
}
const errText = (e) => (e instanceof TypeError ? "Could not reach the server" : e.message);

function timeAgo(iso) {
  const ms = Date.now() - new Date(iso).getTime();
  const days = ms / 86_400_000;
  if (days < 1) return "today";
  if (days < 2) return "yesterday";
  if (days < 30) return `${Math.floor(days)} days ago`;
  return new Date(iso).toLocaleDateString();
}

export { API_URL, SUBSTRATES, urgencyColor, Card, apiError, errText, timeAgo };
