import { useEffect, useId, useRef, useState } from "react";
import { Button } from "../components/ui.jsx";
import TemperatureField from "../prediction/TemperatureField.jsx";
import { parseTemperature } from "../prediction/temperature.js";
import { Card } from "../shared.jsx";
import { getCalibration, postRecommendations } from "./api.js";
import { DeepSearchPanel, useDeepSearch } from "./DeepSearch.jsx";
import { isActive } from "./deep.js";
import IdeaCard from "./IdeaCard.jsx";
import { calibrationText, groupByParent, mergeDeep, sameSearch, targetBody } from "./ideas.js";
import { IngredientPicker, ModeToggle, ParentPicker, TargetChips, UsdaPicker } from "./Pickers.jsx";

const MAX_BATCH_G = 200_000; // the API's limit

function parseBatch(text) {
  const v = Number(String(text).trim().replace(",", "."));
  return Number.isFinite(v) && v > 0 && v <= MAX_BATCH_G ? v : null;
}

// The sections in display order: [key, title, what it is].
const SECTIONS = [
  ["proven", "Proven", "curated, cited recipes"],
  ["experimental", "Experimental", "model-guided changes, untested"],
  ["community", "Community — not proven", "shared by other fermenters, reviewed, not proven"],
];

function foundText(data) {
  const parts = SECTIONS.filter(([key]) => data[key]).map(([key]) => {
    const n = data[key].cards.length;
    return `${n || "no"} ${key} idea${n === 1 ? "" : "s"}`;
  });
  return parts.length ? `Found ${parts.slice(0, -1).join(", ")}${parts.length > 1 ? " and " : ""}${parts[parts.length - 1]}.` : "";
}

function Section({ name, title, what, section, cards, query, seq, onUseAsParent }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="font-display text-lg font-bold text-slate-100">
        {title} <span className="text-sm font-normal text-slate-400">· {what}</span>
      </h2>
      {cards.length === 0 ? (
        name === "proven" ? (
          <Card title="No proven recipe matches">
            {section.message && <p className="text-sm text-slate-300">{section.message}</p>}
            <p className="mt-1 text-sm text-slate-400">Try fewer ingredients, other aromas and tastes, or Experimental ideas.</p>
          </Card>
        ) : (
          <p className="rounded-lg border border-slate-800 px-3 py-2 text-sm text-slate-400">
            {section.message || "Nothing matches this request here."}
          </p>
        )
      ) : (
        cards.map((card) => (
          <IdeaCard
            key={`${seq}-${card.id}-${card.screened ? "s" : "c"}`}
            card={card}
            query={query}
            onUseAsParent={name === "community" ? onUseAsParent : undefined}
          />
        ))
      )}
    </section>
  );
}

function Results({ result, experimentalCards, statusRef, onUseAsParent }) {
  const { status, data, query, error, seq } = result;
  let said = "";
  if (status === "loading") said = "Finding ideas…";
  else if (status === "done") said = foundText(data);

  return (
    <section aria-label="Ideas found" aria-busy={status === "loading"} className="space-y-6">
      <p ref={statusRef} tabIndex={-1} role="status" aria-live="polite" className="min-h-[1.25rem] text-sm text-slate-300 focus:outline-none">
        {said}
      </p>
      {status === "error" && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-sm text-red-300">
          Could not find ideas: {error}
        </div>
      )}
      {data && (
        <div className={`space-y-6 ${status === "loading" ? "opacity-60" : ""}`}>
          {data.notes.map((n, i) => (
            <p key={i} className="text-sm text-slate-400">
              {n}
            </p>
          ))}
          {SECTIONS.filter(([key]) => data[key]).map(([key, title, what]) => (
            <Section
              key={key}
              name={key}
              title={title}
              what={what}
              section={data[key]}
              cards={key === "experimental" ? experimentalCards : data[key].cards}
              query={query}
              seq={seq}
              onUseAsParent={onUseAsParent}
            />
          ))}
        </div>
      )}
    </section>
  );
}

// The calibration gate's status line (design § 13.2), read once: 404 is "not calibrated yet";
// any other failure shows nothing (the cards say Low / Med / High or numbers by themselves).
function useCalibration() {
  const [text, setText] = useState(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getCalibration(ctrl.signal)
      .then((report) => setText(calibrationText(report, Date.now())))
      .catch((e) => e.status === 404 && setText(calibrationText(null)));
    return () => ctrl.abort();
  }, []);
  return text;
}

// #/ideas: ingredients and/or target aromas in; Proven, Experimental and Community cards out
// (design §§ 5, 10, 11), and Search deeper under them.
export default function Ideas() {
  const [ingredients, setIngredients] = useState([]);
  const [targets, setTargets] = useState([]);
  const [mode, setMode] = useState("proven");
  const [parent, setParent] = useState(null); // Experimental: {kind: "batch" | "community", id, …}
  const [usda, setUsda] = useState([]); // [{fdc_id, description}]
  const [tempText, setTempText] = useState("");
  const [batchText, setBatchText] = useState("1000");
  const [result, setResult] = useState({ status: "idle", seq: 0 });
  const deep = useDeepSearch();
  const calibration = useCalibration();
  const statusRef = useRef(null);
  const batchId = useId();

  const temp = parseTemperature(tempText);
  const batchG = parseBatch(batchText);
  const experimental = mode !== "proven";
  const empty = ingredients.length === 0 && targets.length === 0 && !(experimental && parent);
  const loading = result.status === "loading";
  const invalid = Boolean(temp.error) || batchG == null;

  function buildQuery(m = mode, p = parent) {
    const exp = m !== "proven";
    return {
      ingredients,
      ...targetBody(targets),
      mode: m,
      temperature_c: temp.value,
      batch_g: batchG,
      ...(exp && p?.kind === "batch" ? { parent_batch_id: p.id } : {}),
      ...(exp && p?.kind === "community" ? { community_recipe_id: p.id } : {}),
      ...(exp && usda.length ? { usda_fdc_ids: usda.map((f) => f.fdc_id) } : {}),
    };
  }

  async function run(query) {
    const ds = deep.state;
    // a finished deep search of another request does not belong under the new results
    if (ds.status !== "starting" && !isActive(ds.status) && !sameSearch(ds.request ?? ds.job?.request, query)) deep.reset();
    setResult((r) => ({ ...r, status: "loading" }));
    try {
      const data = await postRecommendations(query);
      setResult((r) => ({ status: "done", data, query, seq: r.seq + 1 }));
    } catch (err) {
      // The previous query's cards would read as answers to this one: drop them.
      setResult((r) => ({ status: "error", error: err.message, seq: r.seq }));
    }
  }

  function submit(e) {
    e.preventDefault();
    if (empty || invalid || loading) return;
    run(buildQuery());
  }

  // A community card's "Use as a starting point": its variants (Experimental), at once.
  function useAsParent(community) {
    const p = { kind: "community", id: community.id, title: community.title, pseudonym: community.pseudonym };
    const m = mode === "proven" ? "experimental" : mode;
    setParent(p);
    setMode(m);
    if (invalid || loading) return;
    run(buildQuery(m, p));
    statusRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    statusRef.current?.focus({ preventScroll: true });
  }

  const ds = deep.state;
  const done = result.status === "done";
  const deepCards = ds.job?.results ?? [];
  const same = done && sameSearch(ds.request ?? ds.job?.request, result.query);
  const merged = same && result.data.experimental ? mergeDeep(result.data.experimental.cards, deepCards) : null;
  const experimentalCards = merged ? merged.cards : (result.data?.experimental?.cards ?? []);
  const groups = merged ? merged.groups : groupByParent(deepCards);
  // With a parent (your batch, a community recipe) no new search starts; one running still shows.
  const withParent = done && Boolean(result.query.parent_batch_id || result.query.community_recipe_id);

  return (
    <div className="space-y-4">
      <Card title="Ideas">
        <p className="mb-4 text-sm text-slate-300">
          Start from what you have, what you would like to notice, or both. Ideas are model-guided: timings and aroma
          levels are model estimates, not validated.
        </p>
        <form className="space-y-5" onSubmit={submit} noValidate>
          <IngredientPicker value={ingredients} onChange={setIngredients} />
          <TargetChips value={targets} onChange={setTargets} />
          <ModeToggle value={mode} onChange={setMode} note={calibration} />
          {experimental && (
            <div className="space-y-5 rounded-lg border border-amber-500/30 bg-amber-950/10 p-3">
              <p className="text-xs text-amber-200">
                Experimental ideas change a recipe in ways no source has tested. Treat them as experiments, and follow the
                safety lines on each card.
              </p>
              <ParentPicker value={parent} onChange={setParent} />
              <UsdaPicker value={usda} onChange={setUsda} />
            </div>
          )}
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <TemperatureField
              value={tempText}
              onChange={setTempText}
              label="Your kitchen temperature (°C)"
              laterHint={false}
            />
            <div>
              <label htmlFor={batchId} className="mb-1 block text-xs text-slate-400">
                Batch size (g)
              </label>
              <input
                id={batchId}
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={batchText}
                onChange={(e) => setBatchText(e.target.value)}
                aria-invalid={batchG == null ? "true" : undefined}
                aria-describedby={`${batchId}-hint`}
                className={`w-28 rounded-lg border bg-slate-900 px-3 py-2 text-base tabular-nums sm:text-sm ${
                  batchG == null ? "border-red-500/70" : "border-slate-700"
                }`}
              />
              <p id={`${batchId}-hint`} className={`mt-1 text-xs ${batchG == null ? "text-red-400" : "text-slate-400"}`}>
                {batchG == null ? `Use a weight above 0 and up to ${MAX_BATCH_G / 1000} kg.` : "Recipes are scaled to it."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="lg" className="min-h-[44px]" disabled={empty || loading || invalid}>
              {loading ? "Finding ideas…" : "Find ideas"}
            </Button>
            {empty && (
              <p className="text-xs text-slate-400">
                Pick at least one ingredient, aroma or taste{experimental ? ", or a batch to start from" : ""}.
              </p>
            )}
          </div>
        </form>
      </Card>
      <Results result={result} experimentalCards={experimentalCards} statusRef={statusRef} onUseAsParent={useAsParent} />
      {/* always mounted: it renders nothing until there is something to show */}
      <DeepSearchPanel
        deep={deep}
        canStart={done && !withParent}
        hasResults={done}
        sameAsResults={same}
        groups={groups}
        onStart={() => deep.start(result.query)}
        onHide={deep.hide}
        onRetry={deep.reset}
      />
    </div>
  );
}
