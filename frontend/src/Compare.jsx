import { useEffect, useState } from "react";
import { BatchPicker } from "./Batches.jsx";
import { Button } from "./components/ui.jsx";
import { API_URL, Card, apiError, errText } from "./shared.jsx";

// SQLite (dev) returns naive ISO strings, Postgres (prod) aware ones: treat naive as UTC.
const parseUtc = (iso) => new Date(/(Z|[+-]\d\d:?\d\d)$/i.test(iso) ? iso : iso + "Z");
// Manual IDs may be upper-case / un-hyphenated; the API echoes canonical UUIDs.
const norm = (id) => String(id).replace(/-/g, "").toLowerCase();
const shortId = (id) => String(id).slice(0, 8);
// Whole elapsed days so batches started at different hours still share rows; pre-start readings land in Day 0.
const dayKey = (m, started) =>
  Math.max(0, Math.floor((parseUtc(m.measured_at) - parseUtc(started)) / 86_400_000));

const SLOTS = ["A", "B"];

function Slot({ label, id, meta, open, onChange }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Batch {label}</h3>
      {id ? (
        <div className="mt-1 text-sm">
          <p className="text-slate-200">{meta.name}</p>
          <p className="text-slate-500">
            {[meta.type, meta.stage, meta.started && `started ${meta.started}`].filter(Boolean).join(" · ")}
          </p>
          <a href={`#/batch/${meta.id}`} className="text-xs text-emerald-400 hover:underline">
            Open batch
          </a>
        </div>
      ) : (
        <p className="mt-1 text-sm text-slate-500">No batch chosen</p>
      )}
      <Button
        id={`compare-slot-${label}`}
        variant="secondary"
        size="sm"
        className="mt-2"
        aria-expanded={open}
        onClick={onChange}
      >
        {id ? `Change batch ${label}` : `Choose batch ${label}`}
      </Button>
    </div>
  );
}

function TypeTable({ type, days, cols, names }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="mb-1 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
          {type}
        </caption>
        <thead>
          <tr className="text-left text-xs text-slate-500">
            <th scope="col" className="py-1 pr-3 font-normal">Day</th>
            {names.map((n, i) => (
              <th key={i} scope="col" className="py-1 pr-3 font-normal">
                {SLOTS[i]} · {n}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {days.map((d) => (
            <tr key={d}>
              <th scope="row" className="py-1 pr-3 text-left font-normal text-slate-500">
                Day {d}
              </th>
              {cols.map((c, i) => (
                <td key={i} className="py-1 pr-3 text-slate-200">
                  {c.get(d)?.join(", ") ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Results({ data, ids, names }) {
  const byId = Object.fromEntries(data.batches.map((b) => [norm(b.id), b]));
  const msById = Object.fromEntries(Object.entries(data.measurements).map(([k, v]) => [norm(k), v]));
  const label = {}; // type key -> first-seen spelling
  const per = ids.map((id) => {
    const started = byId[norm(id)]?.started_at;
    const ms = started ? msById[norm(id)] || [] : [];
    const numeric = {}; // type key (lower-case) -> Map(day -> [values])
    const text = [];
    for (const m of ms) {
      const day = dayKey(m, started);
      const key = String(m.type).toLowerCase();
      label[key] ||= m.type;
      if (m.value_numeric != null) {
        const byDay = (numeric[key] ||= new Map());
        byDay.set(day, [...(byDay.get(day) || []), m.value_numeric]);
      }
      const txt = (m.value_numeric != null ? [m.notes] : [m.value_text, m.notes]).filter(Boolean).join(" — ");
      if (txt) text.push({ day, type: m.type, text: txt });
    }
    return { numeric, text };
  });

  const types = [...new Set(per.flatMap((p) => Object.keys(p.numeric)))].sort();
  if (types.length === 0 && per.every((p) => p.text.length === 0)) {
    return <p className="text-sm text-slate-500">Neither batch has measurements yet.</p>;
  }
  return (
    <div className="space-y-4">
      {types.map((t) => {
        const cols = per.map((p) => p.numeric[t] || new Map());
        const days = [...new Set(cols.flatMap((c) => [...c.keys()]))].sort((x, y) => x - y);
        return <TypeTable key={t} type={label[t]} days={days} cols={cols} names={names} />;
      })}
      {per.some((p) => p.text.length > 0) && (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Notes and observations
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {per.map((p, i) => (
              <div key={i}>
                <h4 className="text-xs text-slate-500">
                  {SLOTS[i]} · {names[i]}
                </h4>
                {p.text.length === 0 ? (
                  <p className="text-sm text-slate-600">None</p>
                ) : (
                  <ul className="text-sm text-slate-300">
                    {p.text.map((t, j) => (
                      <li key={j}>
                        <span className="text-slate-500">Day {t.day} · {t.type}:</span> {t.text}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Compare() {
  const [ids, setIds] = useState(["", ""]);
  const [picking, setPicking] = useState(null); // slot index or null
  const [info, setInfo] = useState({}); // norm(id) -> BatchSummaryOut
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [a, b] = ids;
  const same = !!a && !!b && norm(a) === norm(b);

  useEffect(() => {
    fetch(`${API_URL}/batches?limit=200`)
      .then((r) => (r.ok ? r.json() : []))
      .then((rows) => setInfo(Object.fromEntries(rows.map((r) => [norm(r.id), r]))))
      .catch(() => {}); // names are cosmetic; manual selection still works
  }, []);

  useEffect(() => {
    setData(null);
    setError(null);
    if (!a || !b || same) {
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    (async () => {
      try {
        const q = new URLSearchParams([["batch_id", a], ["batch_id", b]]);
        const res = await fetch(`${API_URL}/batches/compare?${q}`);
        if (res.status === 404) throw new Error("One of these batches could not be found");
        if (res.status === 422) throw new Error("That doesn't look like a valid batch ID");
        if (!res.ok) throw new Error(await apiError(res, "Could not compare batches"));
        const body = await res.json();
        if (live) setData(body);
      } catch (e) {
        if (live) setError(errText(e));
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [a, b, same]);

  const metaFor = (id) => {
    const k = norm(id);
    const s = info[k];
    const cb = data?.batches.find((x) => norm(x.id) === k);
    const started = s?.started_at || cb?.started_at;
    return {
      id: cb?.id || id,
      name: s?.culture_name || `Batch ${shortId(id)}`,
      type: s?.culture_type,
      stage: s?.current_stage || cb?.current_stage,
      started: started && parseUtc(started).toLocaleDateString(),
    };
  };
  const metas = ids.map((id) => (id ? metaFor(id) : null));

  return (
    <>
      <Card title="Compare batches">
        <div className="grid gap-3 sm:grid-cols-2">
          {SLOTS.map((label, i) => (
            <Slot
              key={label}
              label={label}
              id={ids[i]}
              meta={metas[i]}
              open={picking === i}
              onChange={() => setPicking(picking === i ? null : i)}
            />
          ))}
        </div>
        {same && <p className="mt-3 text-sm text-amber-400">Pick two different batches</p>}
      </Card>

      {picking !== null && (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm text-slate-300">Choose batch {SLOTS[picking]}</h3>
            <Button variant="secondary" size="xs" onClick={() => setPicking(null)}>
              Cancel
            </Button>
          </div>
          <BatchPicker
            key={picking}
            defaultOutcome=""
            onPick={(id) => {
              setIds((cur) => cur.map((c, i) => (i === picking ? id.toLowerCase() : c)));
              document.getElementById(`compare-slot-${SLOTS[picking]}`)?.focus();
              setPicking(null);
            }}
          />
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">Loading comparison…</p>}
      {error && (
        <p role="alert" className="text-sm text-red-400">
          {error}. Use the Change buttons above to pick different batches.
        </p>
      )}
      {data && (
        <Card title="Measurements by day since start">
          <Results data={data} ids={ids} names={metas.map((m) => (m.started ? `${m.name} · ${m.started}` : m.name))} />
        </Card>
      )}
    </>
  );
}
