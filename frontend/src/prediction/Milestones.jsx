import { describeMilestone, duration } from "./format.js";

function Icon({ state }) {
  const common = { viewBox: "0 0 16 16", className: "mt-0.5 h-4 w-4 shrink-0", fill: "none", "aria-hidden": true };
  if (state === "reached" || state === "probably") {
    return (
      <svg {...common} className={`${common.className} text-slate-400`}>
        <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.5" />
        <path d="M5.2 8.2l1.9 1.9 3.7-3.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (state === "unlikely") {
    return (
      <svg {...common} className={`${common.className} text-slate-400`}>
        <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2.5 2" />
      </svg>
    );
  }
  return (
    <svg {...common} className={`${common.className} text-emerald-400`}>
      <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 4.8V8l2.2 1.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

const SERIES_NAME = { ph: "pH", gravity: "gravity", brix: "Brix" };

// Plain title/note from the API; older responses only had "title (note)".
function titleOf(m) {
  if (m.title) return { title: m.title, note: m.note ?? null };
  const x = /^(.*?)\s*\((.+)\)\s*$/.exec(m.label || "");
  return x ? { title: x[1], note: x[2] } : { title: m.label, note: null };
}

export default function Milestones({ data, whatIf, exploratory }) {
  const { milestones = [], now_h: nowH, horizon_h: horizonH, started_at: startedAt } = data;
  const kind = whatIf ? `what-if at ${whatIf}` : exploratory ? "exploratory estimate" : "model estimate";
  if (milestones.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No milestones are defined for this ferment type yet; the charts below still show the forecast.
      </p>
    );
  }
  const items = milestones
    .map((m) => ({ m, d: describeMilestone(m, nowH, horizonH, startedAt), ...titleOf(m) }))
    .sort((a, b) => a.d.sortKey - b.d.sortKey);
  const hero = items.find((i) => i.d.state === "soon" || i.d.state === "upcoming");
  const rest = items.filter((i) => i !== hero);

  // For a threshold on something you can measure (pH, gravity, Brix), put your
  // latest reading next to a milestone the model thinks is already reached.
  function readingNote(item) {
    const t = item.m.threshold;
    if (!t || (t.kind !== "below" && t.kind !== "above") || !SERIES_NAME[t.series]) return null;
    if (item.d.state !== "reached" && item.d.state !== "probably") return null;
    const name = SERIES_NAME[t.series];
    const latest = (data.observations || [])
      .filter((o) => o.key === t.series)
      .sort((a, b) => b.t_h - a.t_h)[0];
    const confirm = /confirm/i.test(item.note || "") ? "" : ` Confirm with a fresh ${name} reading.`;
    if (!latest) return `No ${name} reading logged: measure to confirm.`;
    const crossed = t.kind === "below" ? latest.value < t.value : latest.value > t.value;
    return `Your latest reading: ${name === "pH" ? "pH " : ""}${latest.value}, ${duration(nowH - latest.t_h)} ago${
      crossed ? "" : ` (still ${t.kind === "below" ? "above" : "below"} ${t.value})`
    }.${confirm}`;
  }

  return (
    <div>
      {hero && (
        <div
          className={`rounded-xl border bg-gradient-to-b to-slate-900/0 p-4 ${
            whatIf ? "border-amber-400/35 from-amber-950/40" : "border-emerald-500/25 from-emerald-950/50"
          }`}
        >
          <p
            className={`text-xs font-medium uppercase tracking-wide ${
              whatIf ? "text-amber-200" : "text-emerald-300/90"
            }`}
          >
            Next milestone · {kind}
          </p>
          <p className="mt-1.5 text-base font-medium text-slate-100">{hero.title}</p>
          <p className="mt-0.5 text-3xl font-semibold tracking-tight text-white sm:text-4xl">{hero.d.when}</p>
          <p className="mt-1 text-sm text-slate-300">
            {hero.d.range && <span>{hero.d.range}</span>}
            {hero.d.date && (
              <>
                <span className="text-slate-400"> · </span>
                <span className="whitespace-nowrap text-slate-400">around {hero.d.date}</span>
              </>
            )}
          </p>
          {hero.d.showProb && (
            <p className="mt-1 text-sm text-slate-300">
              Reached in {Math.round(hero.d.prob * 100)} % of model runs within the window
            </p>
          )}
          {hero.note && <p className="mt-2 text-xs text-slate-400">{hero.note}</p>}
        </div>
      )}

      {!hero && <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Milestones · {kind}</p>}
      {rest.length > 0 && (
        <ul className={`${hero ? "mt-3" : "mt-1"} divide-y divide-slate-800/80`}>
          {rest.map((i) => {
            const reading = readingNote(i);
            const past = i.d.state === "reached" || i.d.state === "unlikely";
            return (
              <li key={i.m.key} className="flex gap-3 py-2.5">
                <Icon state={i.d.state} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <p className={`text-sm font-medium ${past ? "text-slate-300" : "text-slate-100"}`}>{i.title}</p>
                    <p className={`text-sm ${past ? "text-slate-300" : "font-medium text-slate-100"}`}>{i.d.when}</p>
                  </div>
                  {(i.d.range || i.d.date || i.d.showProb) && (
                    <p className="text-xs text-slate-400">
                      {[
                        i.d.range && <span key="r">{i.d.range.replace(/^90 % range: /, "range ")}</span>,
                        i.d.date && (
                          <span key="d" className="whitespace-nowrap">
                            {i.d.date}
                          </span>
                        ),
                        i.d.showProb && (
                          <span key="p" className="whitespace-nowrap">
                            reached in {Math.round(i.d.prob * 100)} % of model runs
                          </span>
                        ),
                      ]
                        .filter(Boolean)
                        .flatMap((el, k) => (k ? [" · ", el] : [el]))}
                    </p>
                  )}
                  {i.note && <p className="text-xs text-slate-400">{i.note}</p>}
                  {reading && <p className="mt-1 text-xs text-amber-300/90">{reading}</p>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
