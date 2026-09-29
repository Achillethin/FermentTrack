import { useEffect, useRef, useState } from "react";
import { Button, Input, Select } from "./components/ui.jsx";
import { API_URL, Card, apiError, errText } from "./shared.jsx";

const LIMIT = 50;
// Stored types are exact (case-insensitive) matches on the backend; "pH" mirrors
// BatchView's OBSERVATION_TYPES. Custom ("other") types can't be filtered by name.
const TYPE_OPTIONS = ["note", "pH", "temperature", "gravity", "brix", "smell", "taste", "appearance", "stage-change"];
const KIND_LABEL = { measurement: "Measurement", note: "Note", "stage-change": "Stage" };
const KIND_STYLE = {
  measurement: "border-sky-500/40 text-sky-300",
  note: "border-amber-500/40 text-amber-300",
  "stage-change": "border-emerald-500/40 text-emerald-300",
};

// API may send naive ISO (SQLite dev) or aware (Postgres prod); naive means UTC.
function parseUtc(iso) {
  if (typeof iso !== "string") return new Date(NaN);
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/i.test(iso) ? iso : `${iso}Z`);
}

const present = (v) => v !== null && v !== undefined && v !== "";
const dayKey = (d) => (isNaN(d) ? "unknown" : `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`);

function dayLabel(d) {
  if (isNaN(d)) return "Unknown date";
  const now = new Date();
  if (dayKey(d) === dayKey(now)) return "Today";
  if (dayKey(d) === dayKey(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1))) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" });
}

// One section per day, even if an out-of-order tail revisits a day (keeps section keys unique).
function groupByDay(entries) {
  const groups = new Map();
  for (const e of entries) {
    const d = parseUtc(e.timestamp);
    const key = dayKey(d);
    if (!groups.has(key)) groups.set(key, { key, label: dayLabel(d), items: [] });
    groups.get(key).items.push({ e, d });
  }
  return [...groups.values()];
}

// Stage-change ids are their batch's id, so the key must combine kind + id.
const entryKey = (e) => `${e.kind}:${e.id}`;
const localToday = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const fmtNum = (x) => Number(x).toLocaleString(undefined, { maximumFractionDigits: 3 });

function renderDetail(e) {
  const d = e.detail || {};
  if (e.kind === "stage-change") {
    return { main: present(d.stage) ? `Entered stage ${String(d.stage).replace(/_/g, " ")}` : "Entered a new stage", extra: null };
  }
  if (e.kind === "note") {
    return { main: present(d.value_text) ? d.value_text : d.notes, extra: present(d.value_text) ? d.notes : null };
  }
  const value = [present(d.value_numeric) && fmtNum(d.value_numeric), d.value_text].filter(present).join(" · ");
  const label = present(d.type) ? String(d.type) : "measurement";
  return { main: value ? `${label}: ${value}` : label, extra: d.notes };
}

function Entry({ e, d }) {
  const { main, extra } = renderDetail(e);
  const name = e.culture?.name ?? "Unknown culture";
  return (
    <li className="flex gap-3 px-3 py-2 text-sm">
      <time
        dateTime={isNaN(d) ? undefined : d.toISOString()}
        className="w-16 shrink-0 whitespace-nowrap pt-0.5 text-xs text-slate-500"
      >
        {isNaN(d) ? "—" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </time>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          {e.batch?.id ? (
            <a href={`#/batch/${e.batch.id}`} className="font-medium text-slate-200 hover:underline">
              {name}
            </a>
          ) : (
            <span className="font-medium text-slate-200">{name}</span>
          )}
          <span className={`rounded border px-1.5 text-xs ${KIND_STYLE[e.kind] || "border-slate-600 text-slate-400"}`}>
            {KIND_LABEL[e.kind] || e.kind}
          </span>
          {e.owner && (
            <span className="text-xs text-slate-500" title={e.owner}>
              account {e.owner.slice(0, 8)}
            </span>
          )}
        </div>
        {present(main) && <p className="break-words text-slate-300">{main}</p>}
        {present(extra) && <p className="break-words text-xs text-slate-500">{extra}</p>}
      </div>
    </li>
  );
}

// admin: every account's entries (read-only admin access; see routers/admin.py).
export default function Logbook({ admin = false }) {
  const scope = admin ? "/admin" : "/me";
  const [q, setQ] = useState("");
  const [dq, setDq] = useState(""); // debounced q
  const [cultureId, setCultureId] = useState("");
  const [type, setType] = useState("");
  const [since, setSince] = useState(""); // YYYY-MM-DD, local
  const [cultures, setCultures] = useState([]);
  const [items, setItems] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [moreBusy, setMoreBusy] = useState(false);
  const [moreError, setMoreError] = useState(null);
  const [retry, setRetry] = useState(0);
  const ctrl = useRef(null); // one in-flight request at a time; filter change aborts it
  const rawOffset = useRef(0); // rows consumed server-side (items.length undercounts once deduped)

  const active = Boolean(dq || cultureId || type || since);

  useEffect(() => {
    const t = setTimeout(() => setDq(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => () => ctrl.current?.abort(), []); // unmount: also cancel an in-flight loadMore

  useEffect(() => {
    const c = new AbortController();
    fetch(`${API_URL}${admin ? "/admin/cultures" : "/cultures"}`, { signal: c.signal })
      .then((r) => (r.ok ? r.json() : []))
      .then((list) => Array.isArray(list) && setCultures(list))
      .catch(() => {});
    return () => c.abort();
  }, []);

  function fetchPage(offset, signal) {
    const params = new URLSearchParams({ limit: LIMIT, offset });
    if (dq) params.set("q", dq);
    if (cultureId) params.set("culture_id", cultureId);
    if (type) params.set("type", type);
    if (since) {
      const start = new Date(`${since}T00:00:00`); // no offset => local midnight
      if (!isNaN(start)) params.set("since", start.toISOString());
    }
    return fetch(`${API_URL}${scope}/log?${params}`, { signal }).then(async (res) => {
      if (!res.ok) throw new Error(await apiError(res, "Could not load the logbook"));
      const page = await res.json();
      if (!Array.isArray(page)) throw new Error("Unexpected response from the server");
      return page;
    });
  }

  // Any filter change (or Retry) restarts from offset 0.
  useEffect(() => {
    ctrl.current?.abort();
    const c = (ctrl.current = new AbortController());
    setLoading(true);
    setError(null);
    setMoreError(null);
    setMoreBusy(false);
    fetchPage(0, c.signal)
      .then((page) => {
        if (c.signal.aborted) return;
        rawOffset.current = page.length;
        setItems(page);
        setHasMore(page.length >= LIMIT);
        setLoading(false);
      })
      .catch((e) => {
        if (c.signal.aborted) return;
        setItems([]);
        setHasMore(false);
        setError(errText(e));
        setLoading(false);
      });
    return () => c.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dq, cultureId, type, since, retry]);

  function loadMore() {
    ctrl.current?.abort();
    const c = (ctrl.current = new AbortController());
    setMoreBusy(true);
    setMoreError(null);
    fetchPage(rawOffset.current, c.signal)
      .then((page) => {
        if (c.signal.aborted) return;
        rawOffset.current += page.length;
        setItems((prev) => {
          const seen = new Set(prev.map(entryKey));
          return [...prev, ...page.filter((e) => !seen.has(entryKey(e)))];
        });
        setHasMore(page.length >= LIMIT);
        setMoreBusy(false);
      })
      .catch((e) => {
        if (c.signal.aborted) return;
        setMoreError(errText(e)); // keep the list already shown
        setMoreBusy(false);
      });
  }

  function clearFilters() {
    setQ("");
    setDq("");
    setCultureId("");
    setType("");
    setSince("");
  }

  const groups = groupByDay(items);
  const clearBtn = (
    <Button type="button" variant="secondary" size="md" onClick={clearFilters}>
      Clear filters
    </Button>
  );

  return (
    <Card title="Logbook">
      <div className="flex flex-wrap items-end gap-2">
        <Input
          label="Search logbook text"
          type="search"
          className="min-w-[10rem] flex-1"
          placeholder="Search notes and values…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Select label="Filter by culture" value={cultureId} onChange={(e) => setCultureId(e.target.value)}>
          <option value="">all cultures</option>
          {cultures.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.type})
            </option>
          ))}
        </Select>
        <Select label="Filter by entry type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">all types</option>
          {TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
        <label className="flex flex-col text-xs text-slate-400">
          Since
          <Input type="date" size="sm" min="1970-01-01" max={localToday()} value={since} onChange={(e) => setSince(e.target.value)} />
        </label>
        {(active || q) && clearBtn}
      </div>

      <div aria-live="polite" className="mt-3">
        {loading && <p className="text-sm text-slate-500">Loading…</p>}

        {!loading && error && (
          <div className="space-y-2">
            <p className="text-sm text-red-400">{error}</p>
            <Button type="button" variant="secondary" onClick={() => setRetry((n) => n + 1)}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !error && items.length === 0 &&
          (active ? (
            <div className="space-y-2">
              <p className="text-sm text-slate-500">No entries match these filters.</p>
              {clearBtn}
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Nothing logged yet. Log a measurement or note on a batch and it'll show up here.{" "}
              <a href="#/batches" className="text-emerald-400 hover:underline">
                Go to batches
              </a>
            </p>
          ))}
      </div>

      {!loading && !error && groups.map((g) => (
        <section key={g.key} className="mt-3">
          <h3 className="sticky top-0 z-10 bg-slate-950 py-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            {g.label}
          </h3>
          <ul className="divide-y divide-slate-800 rounded-lg border border-slate-800">
            {g.items.map(({ e, d }) => (
              <Entry key={entryKey(e)} e={e} d={d} />
            ))}
          </ul>
        </section>
      ))}

      {!loading && !error && items.length > 0 && (
        <div className="mt-3 space-y-2">
          {moreError && <p className="text-sm text-red-400">{moreError}</p>}
          {hasMore && (
            <Button type="button" variant="secondary" disabled={moreBusy} onClick={loadMore}>
              {moreBusy ? "Loading…" : moreError ? "Retry loading more" : "Load more"}
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
