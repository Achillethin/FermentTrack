const INITIAL_LABELS = {
  sugars_total: ["Sugars (total)", "g/kg"],
  sucrose: ["Sucrose", "g/kg"],
  hexoses: ["Glucose + fructose", "g/kg"],
  lactose: ["Lactose", "g/kg"],
  maltose: ["Maltose", "g/kg"],
  starch: ["Starch", "g/kg"],
  protein: ["Protein", "g/kg"],
  ethanol: ["Ethanol", "g/kg"],
  lactic_acid: ["Lactic acid (from the starter)", "g/kg"],
  acetic_acid: ["Acetic acid (from the starter)", "g/kg"],
  gluconic_acid: ["Gluconic acid (from the starter)", "g/kg"],
  salt_water_phase_pct: ["Salt in the water phase", "%"],
  ph: ["pH", ""],
};

const unique = (xs) => [...new Set((xs || []).filter(Boolean))];

function Sources({ items, className = "" }) {
  const list = unique(items);
  if (!list.length) return null;
  return (
    <ul className={`list-disc space-y-0.5 pl-5 text-xs text-slate-400 marker:text-slate-600 ${className}`}>
      {list.map((src) => (
        <li key={src}>{src}</li>
      ))}
    </ul>
  );
}

function Pathways({ pathways }) {
  if (!pathways?.length) return null;
  return (
    <ul className="mt-2 space-y-1.5">
      {pathways.map((pw) => (
        <li key={pw.label} className="text-xs">
          <p className="text-slate-300">
            {pw.label}
            {pw.in_reference_graph === false && (
              <span className="ml-2 whitespace-nowrap rounded border border-dashed border-slate-600 px-1.5 py-px text-[10px] text-slate-400">
                not yet in the reference graph
              </span>
            )}
          </p>
          {/* 40 px tall targets, pulled together visually with a negative margin */}
          <div className="-my-2 flex flex-wrap gap-x-3">
            {pw.ec_numbers.map((ec) => (
              <a
                key={ec}
                href={`https://www.kegg.jp/entry/ec:${ec}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-[40px] items-center font-mono text-[11px] text-emerald-300/90 underline decoration-emerald-400/30 underline-offset-2 hover:text-emerald-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              >
                EC {ec}
                <span className="sr-only"> (opens KEGG)</span>
              </a>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}

function Disclosure({ summary, children }) {
  return (
    <details className="group border-t border-slate-800">
      <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-3 rounded text-sm text-slate-300 hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 [&::-webkit-details-marker]:hidden">
        <span>{summary}</span>
        <svg viewBox="0 0 16 16" className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-open:rotate-180" aria-hidden="true">
          <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="pb-3 text-sm">{children}</div>
    </details>
  );
}

export function Warnings({ warnings }) {
  if (!warnings?.length) return null;
  return (
    <ul className="space-y-1.5 rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2">
      {warnings.map((w) => (
        <li key={w} className="flex gap-2 text-sm text-amber-200">
          <svg viewBox="0 0 16 16" className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true">
            <path d="M8 2.2l6.2 11H1.8L8 2.2z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            <path d="M8 6.5v3M8 11.4v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          <span>
            <span className="sr-only">Warning: </span>
            {w}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function ModelDetails({ data }) {
  const organisms = data.organisms || [];
  const modelled = organisms.filter((o) => o.modelled);
  const notModelled = organisms.filter((o) => !o.modelled);
  const notGrowing = organisms.filter((o) => o.modelled && o.growing === false);
  const initial = data.initial || { values: {} };
  // Zero amounts carry no information here (no starch in kombucha); pH always shows.
  const initialRows = Object.entries(initial.values || {}).filter(([k, v]) => v != null && (v !== 0 || k === "ph"));
  const type = (data.fermentation_type || "").replace(/_/g, " ");

  return (
    <div>
      {notModelled.length > 0 && (
        <p className="mb-2 text-xs text-slate-400">
          Not modelled (no kinetic profile yet):{" "}
          {notModelled.map((o, i) => (
            <span key={o.name}>
              {i > 0 && ", "}
              <i className="text-slate-300">{o.name}</i>
            </span>
          ))}
          . The forecast leaves out what they do.
        </p>
      )}

      <Disclosure
        summary={
          <>
            Organisms{" "}
            <span className="text-slate-400">
              · {modelled.length} of {organisms.length} modelled
              {notGrowing.length > 0 && `, ${notGrowing.length} not growing`}
            </span>
          </>
        }
      >
        <ul className="divide-y divide-slate-800/70">
          {organisms.map((o) => (
            <li key={o.name} className="py-2 first:pt-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <i className="text-slate-200">{o.name}</i>
                <span className="text-xs text-slate-400">{o.kingdom}</span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[11px] ${
                    o.modelled
                      ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-300"
                      : "border-slate-600 bg-slate-800/60 text-slate-300"
                  }`}
                >
                  {o.modelled ? "modelled" : "not modelled"}
                </span>
                {o.modelled && o.growing === false && (
                  <span className="rounded-full border border-slate-600 bg-slate-800/60 px-2 py-0.5 text-[11px] text-slate-300">
                    not growing
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">{o.role}</p>
              {o.note && <p className="mt-0.5 text-xs text-slate-300">{o.note.charAt(0).toUpperCase() + o.note.slice(1)}.</p>}
              <Pathways pathways={o.pathways} />
              {unique(o.sources).length > 0 && (
                <details className="mt-0.5">
                  <summary className="inline-flex min-h-[40px] cursor-pointer items-center text-[11px] text-slate-400 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400">
                    Sources ({unique(o.sources).length})
                  </summary>
                  <Sources items={o.sources} />
                </details>
              )}
            </li>
          ))}
        </ul>
      </Disclosure>

      <Disclosure
        summary={
          <>
            Starting point{" "}
            <span className="text-slate-400">
              · {initial.source === "recipe" ? "from your recipe" : `a typical ${type} recipe`}
            </span>
          </>
        }
      >
        {initial.source !== "recipe" && (
          <p className="mb-2 text-xs text-slate-400">
            No quantified recipe is logged for this batch, so the model starts from a typical {type} recipe. Log
            ingredient quantities to use yours.
          </p>
        )}
        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
          {initialRows.map(([k, v]) => {
            const [label, unit] = INITIAL_LABELS[k] || [k.replace(/_/g, " "), ""];
            return (
              <div key={k} className="contents">
                <dt className="text-slate-400">{label}</dt>
                <dd className="text-right tabular-nums text-slate-200">
                  {v}
                  {unit && <span className="text-slate-400"> {unit}</span>}
                </dd>
              </div>
            );
          })}
        </dl>
      </Disclosure>

      {data.assumptions?.length > 0 && (
        <Disclosure summary={<>Assumptions <span className="text-slate-400">· {data.assumptions.length}</span></>}>
          <ul className="list-disc space-y-1 pl-5 text-slate-300 marker:text-slate-500">
            {data.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </Disclosure>
      )}

      <Disclosure summary="About the model">
        <dl className="space-y-1.5 text-slate-300">
          <div>
            <dt className="inline text-slate-400">Model: </dt>
            <dd className="inline">
              {data.model.name} <span className="text-slate-400">({data.model.version})</span>
            </dd>
          </div>
          <div>
            <dt className="inline text-slate-400">Method: </dt>
            <dd className="inline">{data.model.method}</dd>
          </div>
          <div>
            <dt className="inline text-slate-400">Confidence: </dt>
            <dd className="inline">
              {data.model.confidence === "exploratory"
                ? "exploratory (little published kinetic data for this ferment)"
                : "established kinetics from the literature"}
              {data.model.validated === false && "; not yet validated against real batches"}
            </dd>
          </div>
          <div>
            <dt className="inline text-slate-400">Ensemble: </dt>
            <dd className="inline tabular-nums">
              {data.model.members} parameter sets
              {data.status === "calibrated" &&
                `, effectively ${Math.round(data.model.effective_members)} after weighting on your measurements`}
            </dd>
          </div>
        </dl>
        {unique(data.model.sources).length > 0 && (
          <>
            <p className="mt-3 text-slate-400">Literature</p>
            <Sources items={data.model.sources} className="mt-1" />
          </>
        )}
      </Disclosure>
    </div>
  );
}
