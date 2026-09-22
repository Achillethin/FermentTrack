import { useEffect, useState } from "react";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

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

function BatchHeader({ batch, culture, daysInStage }) {
  return (
    <Card title="Batch">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-lg font-medium">{culture.name}</p>
          <p className="text-sm text-slate-400">{culture.type}</p>
        </div>
        <div className="text-right">
          <p className="text-lg font-medium">{batch.current_stage}</p>
          <p className="text-sm text-slate-400">
            {daysInStage.toFixed(1)} day{daysInStage === 1 ? "" : "s"} in stage
          </p>
        </div>
      </div>
      {batch.target && <p className="mt-2 text-sm text-slate-300">Target: {batch.target}</p>}
      <p className="mt-2 text-xs text-slate-500">
        Started {new Date(batch.started_at).toLocaleString()} · outcome: {batch.outcome}
      </p>
    </Card>
  );
}

function Recipe({ recipe }) {
  if (recipe.length === 0) {
    return (
      <Card title="Recipe">
        <p className="text-sm text-slate-500">No ingredients logged yet.</p>
      </Card>
    );
  }
  return (
    <Card title="Recipe">
      <ul className="divide-y divide-slate-800">
        {recipe.map((item) => (
          <li key={item.id} className="flex justify-between py-2 text-sm">
            <span className="text-slate-200">
              {item.quantity ?? ""} {item.unit ?? ""}
            </span>
            <span className="text-slate-500">{item.role}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Timeline({ timeline }) {
  if (timeline.length === 0) {
    return (
      <Card title="Timeline">
        <p className="text-sm text-slate-500">No events yet.</p>
      </Card>
    );
  }
  return (
    <Card title="Timeline">
      <ul className="space-y-2">
        {timeline
          .slice()
          .reverse()
          .map((event, i) => (
            <li key={i} className="text-sm">
              <span className="text-slate-500">
                {new Date(event.timestamp).toLocaleString()}
              </span>{" "}
              <span className="text-slate-300">· {event.kind}</span>
              <div className="text-slate-400">{JSON.stringify(event.detail)}</div>
            </li>
          ))}
      </ul>
    </Card>
  );
}

function Safety({ safety }) {
  const verdicts = [...safety.hard_stops, ...safety.warnings];
  return (
    <Card title="Safety Advisory">
      <p className={`mb-2 text-sm font-medium ${safety.safe ? "text-emerald-400" : "text-red-400"}`}>
        {safety.summary_en}
      </p>
      {verdicts.length > 0 && (
        <ul className="space-y-2">
          {verdicts.map((v) => (
            <li key={v.rule_id} className={`rounded-lg border p-2 text-sm ${urgencyColor(v.action)}`}>
              <p>{v.reason_text_en}</p>
              <p className="mt-1 text-xs opacity-70">{v.source_citation}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const [batchId, setBatchId] = useState(params.get("batch") || "");
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadPreview(id) {
    if (!id) return;
    setLoading(true);
    setError(null);
    setPreview(null);
    try {
      const res = await fetch(`${API_URL}/batches/${id}/preview`);
      if (!res.ok) throw new Error(res.status === 404 ? "Batch not found" : `API error (${res.status})`);
      setPreview(await res.json());
      const url = new URL(window.location);
      url.searchParams.set("batch", id);
      window.history.replaceState({}, "", url);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (batchId) loadPreview(batchId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-4">
      <h1 className="text-2xl font-bold">🧫 FermentTrack</h1>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          loadPreview(batchId);
        }}
      >
        <input
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          placeholder="Batch ID"
          value={batchId}
          onChange={(e) => setBatchId(e.target.value)}
        />
        <button
          type="submit"
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500"
        >
          {loading ? "Loading…" : "Load"}
        </button>
      </form>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {preview && (
        <>
          <BatchHeader batch={preview.batch} culture={preview.culture} daysInStage={preview.days_in_stage} />
          <Recipe recipe={preview.recipe} />
          <Timeline timeline={preview.timeline} />
          <Safety safety={preview.safety} />
        </>
      )}
    </main>
  );
}
