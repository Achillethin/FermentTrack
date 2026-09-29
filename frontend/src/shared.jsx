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

// v.action from the safety API is "hard_stop" or "warning" (risk_rules.yaml), not a
// critical/high/medium/low scale — key on the values that actually appear.
function urgencyColor(action) {
  return (
    {
      hard_stop: "text-red-400 border-red-500/40 bg-red-950/40",
      warning: "text-amber-400 border-amber-500/40 bg-amber-950/40",
    }[action] || "text-slate-400 border-slate-600/40 bg-slate-800/40"
  );
}

const humanize = (s) => String(s ?? "").replace(/_/g, " ");

function Card({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <h2 className="mb-3 font-display text-lg font-bold text-slate-100">{title}</h2>
      {children}
    </section>
  );
}

function JarMark({ className = "h-7 w-7" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} fill="none" aria-hidden="true">
      <rect x="10" y="3" width="12" height="4" rx="1.5" className="fill-emerald-400" />
      <path
        d="M11 8h10a3 3 0 0 1 3 3v14a4 4 0 0 1-4 4H12a4 4 0 0 1-4-4V11a3 3 0 0 1 3-3Z"
        className="stroke-slate-100"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <rect x="12" y="17" width="8" height="6" rx="1" className="fill-paper" />
      <circle cx="13.5" cy="12" r="1.3" className="fill-emerald-400" />
      <circle cx="18" cy="11" r="0.9" className="fill-emerald-400" />
    </svg>
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

export { API_URL, SUBSTRATES, urgencyColor, humanize, Card, JarMark, apiError, errText, timeAgo };
