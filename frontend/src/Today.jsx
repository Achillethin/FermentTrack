import { useEffect, useRef, useState } from "react";
import { Button } from "./components/ui.jsx";
import { API_URL, Card, apiError, errText } from "./shared.jsx";
import { parseReading, unusualPh } from "./readings.js";
import { isDue } from "./tastings/tasting.js";

// Reminder urgency is low | medium | high | critical (stages.py); shared.urgencyColor keys safety actions.
const URGENCY_CLASS = {
  critical: "text-red-400 border-red-500/40 bg-red-950/40",
  high: "text-orange-400 border-orange-500/40 bg-orange-950/40",
  medium: "text-amber-400 border-amber-500/40 bg-amber-950/40",
  low: "text-slate-400 border-slate-600/40 bg-slate-800/40",
};
const urgencyColor = (u) => URGENCY_CLASS[u] || URGENCY_CLASS.low;

const HOUR = 3_600_000;
const DAY = 24 * HOUR;
const SNOOZES = [1, 6, 24]; // hours

// SQLite dev returns naive ISO strings, Postgres prod returns aware ones; naive means UTC.
const parseUtc = (iso) => new Date(/(Z|[+-]\d{2}:?\d{2})$/i.test(iso) ? iso : `${iso}Z`);

function span(ms) {
  const m = Math.round(ms / 60_000);
  if (m < 60) return `${m}m`;
  const h = Math.round(ms / HOUR);
  return h < 48 ? `${h}h` : `${Math.round(ms / DAY)}d`;
}

function dueText(due, now) {
  const ms = due.getTime() - now;
  if (Number.isNaN(ms)) return "";
  if (Math.abs(ms) < 60_000) return "due now";
  return ms < 0 ? `overdue by ${span(-ms)}` : `due in ${span(ms)}`;
}

const label = (s) => (s || "").replace(/_/g, " ");

async function send(path, method, body) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    ...(body && { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  if (!res.ok) throw Object.assign(new Error(await apiError(res, "Request failed")), { status: res.status });
  return res.json();
}

// A pH safety reminder takes the reading it asks for (site critique fix 5): "Done" without a
// reading would close it unanswered.
function PhField({ r, name, busy, onLogPh }) {
  const [text, setText] = useState("");
  const id = `ph-${r.id}`;
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onLogPh(r, text, () => setText(""));
      }}
    >
      <label htmlFor={id} className="sr-only">
        pH reading for {name}
      </label>
      <input
        id={id}
        inputMode="decimal"
        autoComplete="off"
        placeholder="pH"
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-base tabular-nums text-slate-100 sm:text-sm"
      />
      <Button type="submit" size="sm" className="min-h-[32px]" disabled={busy}>
        Log pH
      </Button>
    </form>
  );
}

function ReminderRow({ r, batch, busy, error, note, now, onDone, onSnooze, onLogPh }) {
  const due = parseUtc(r.due_at);
  const overdue = due.getTime() <= now;
  const name = batch?.culture_name ?? "Batch";
  const who = `${r.action} for ${name}`;
  return (
    <li className={`rounded-lg border p-3 ${urgencyColor(r.urgency)}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="font-medium text-slate-100">{r.action}</span>
        <span className="text-xs">
          {overdue && <span aria-hidden="true">! </span>}
          {dueText(due, now)}
          {r.urgency && ` · ${r.urgency}`}
        </span>
      </div>
      <a href={`#/batch/${r.batch_id}`} className="text-sm text-emerald-400 hover:underline">
        {name}
      </a>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {/* the tasting form once the stop-by time has come, never before (tasting.isDue) */}
        {r.kind === "tasting" && isDue(r, now) && (
          <a
            href={`#/batch/${r.batch_id}/tasting`}
            aria-label={`Fill in the tasting form for ${name}`}
            className="inline-flex min-h-[32px] items-center rounded-lg bg-emerald-700 px-3 text-xs font-medium text-white hover:bg-emerald-600"
          >
            Fill in the tasting form
          </a>
        )}
        {r.kind === "safety" ? (
          <PhField r={r} name={name} busy={busy} onLogPh={onLogPh} />
        ) : (
          <Button
            size="sm"
            variant={r.kind === "tasting" ? "secondary" : "primary"}
            disabled={busy}
            aria-label={`${r.kind === "tasting" ? "Dismiss" : "Mark done"}: ${who}`}
            onClick={() => onDone(r)}
          >
            {r.kind === "tasting" ? "Dismiss" : "Done"}
          </Button>
        )}
        {SNOOZES.map((h) => (
          <Button
            key={h}
            size="sm"
            variant="secondary"
            disabled={busy}
            aria-label={`Snooze ${h} hour${h > 1 ? "s" : ""}: ${who}`}
            onClick={() => onSnooze(r, h)}
          >
            Snooze {h}h
          </Button>
        ))}
      </div>
      {note && (
        <p role="status" className="mt-2 text-xs text-slate-200">
          {note}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          {error}
        </p>
      )}
    </li>
  );
}

function BatchCard({ b, now }) {
  const entered = parseUtc(b.stage_entered_at || b.started_at);
  const day = Number.isNaN(entered.getTime())
    ? null
    : Math.max(1, Math.floor((now - entered.getTime()) / DAY) + 1);
  return (
    <li>
      <a
        href={`#/batch/${b.id}`}
        className="block rounded-lg border border-slate-800 bg-slate-900/60 p-3 hover:border-slate-600"
      >
        <span className="font-medium text-slate-100">{b.culture_name}</span>
        <span className="block text-sm text-slate-400">
          {[label(b.culture_type), label(b.current_stage), day && `day ${day} in stage`]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </a>
    </li>
  );
}

export default function Today() {
  const [state, setState] = useState({ loading: true, error: null, reminders: [], batches: [] });
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState({}); // reminder id -> true while a request is in flight
  const [errors, setErrors] = useState({}); // reminder id -> inline message
  const [notes, setNotes] = useState({}); // reminder id -> what a logged reading did
  const [logged, setLogged] = useState(null); // a reading that closed its reminder
  const inflight = useRef(new Set()); // synchronous double-submit guard
  const mounted = useRef(true);
  const [now, setNow] = useState(Date.now); // ticks each minute so relative times and Overdue/Coming up stay current

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    Promise.all([send("/reminders", "GET"), send("/batches?outcome=in_progress&limit=200", "GET")])
      .then(([reminders, batches]) => {
        if (!ignore) setState({ loading: false, error: null, reminders, batches });
      })
      .catch((e) => {
        if (!ignore) setState((s) => ({ ...s, loading: false, error: errText(e) }));
      });
    return () => {
      ignore = true;
    };
  }, [attempt]);

  async function act(r, path, body, onOk) {
    if (inflight.current.has(r.id)) return;
    inflight.current.add(r.id);
    setBusy((m) => ({ ...m, [r.id]: true }));
    setErrors((m) => ({ ...m, [r.id]: null }));
    try {
      const out = await send(`/reminders/${r.id}/${path}`, "PATCH", body);
      if (mounted.current) onOk(out);
    } catch (e) {
      // 404: the batch/reminder is gone, so the row can never succeed; drop it.
      if (e.status === 404) {
        if (mounted.current) drop(r.id);
      } else if (mounted.current) setErrors((m) => ({ ...m, [r.id]: errText(e) }));
    } finally {
      inflight.current.delete(r.id);
      if (mounted.current) setBusy((m) => ({ ...m, [r.id]: false }));
    }
  }

  // The pH a safety reminder asks for: logged on the batch; the server closes the reminder when
  // the reading meets the 48 h step, else it stays open with a word on why.
  async function logPh(r, text, clear) {
    const reading = parseReading(text, "pH");
    if (reading.error || reading.value === null) {
      setErrors((m) => ({ ...m, [r.id]: reading.error ?? "Enter a pH value" }));
      return;
    }
    if (reading.unusual && !window.confirm(unusualPh(reading.value))) return;
    if (inflight.current.has(r.id)) return;
    inflight.current.add(r.id);
    setBusy((m) => ({ ...m, [r.id]: true }));
    setErrors((m) => ({ ...m, [r.id]: null }));
    try {
      await send(`/batches/${r.batch_id}/measure`, "POST", { type: "pH", value_numeric: reading.value });
      const reminders = await send("/reminders", "GET");
      if (!mounted.current) return;
      clear();
      const closed = !reminders.some((x) => x.id === r.id);
      setState((s) => ({ ...s, reminders }));
      setNotes((m) => ({
        ...m,
        [r.id]: closed ? null : `Logged pH ${reading.value}: not there yet, so this stays open. The batch page says what to do.`,
      }));
      if (closed) setLogged(`Logged pH ${reading.value}: the pH check is done.`);
    } catch (e) {
      if (mounted.current) setErrors((m) => ({ ...m, [r.id]: errText(e) }));
    } finally {
      inflight.current.delete(r.id);
      if (mounted.current) setBusy((m) => ({ ...m, [r.id]: false }));
    }
  }

  const drop = (id) => setState((s) => ({ ...s, reminders: s.reminders.filter((x) => x.id !== id) }));
  const onDone = (r) => act(r, "done", undefined, () => drop(r.id));
  const onSnooze = (r, h) => {
    // Push out from the later of now and the current due time, so snoozing never pulls a reminder earlier.
    const cur = parseUtc(r.due_at).getTime();
    const until = new Date(Math.max(Date.now(), Number.isNaN(cur) ? 0 : cur) + h * HOUR).toISOString();
    return act(r, "snooze", { until }, (out) => {
      // Moves to "Coming up"; leaves the list if the new time is past the 48h window.
      const due_at = out?.due_at ?? until;
      if (parseUtc(due_at).getTime() > Date.now() + 48 * HOUR) return drop(r.id);
      setState((s) => ({
        ...s,
        reminders: s.reminders.map((x) => (x.id === r.id ? { ...x, due_at } : x)),
      }));
    });
  };

  const { loading, error, reminders, batches } = state;

  if (loading) return <p className="text-sm text-slate-500">Loading today…</p>;
  if (error)
    return (
      <Card title="Today">
        <p role="alert" className="mb-3 text-sm text-red-400">
          {error}
        </p>
        <Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>
          Retry
        </Button>
      </Card>
    );

  const byId = new Map(batches.map((b) => [b.id, b]));
  const sorted = [...reminders].sort((a, b) => parseUtc(a.due_at) - parseUtc(b.due_at));
  const overdue = sorted.filter((r) => parseUtc(r.due_at).getTime() <= now);
  const upcoming = sorted.filter((r) => parseUtc(r.due_at).getTime() > now);
  const stageStart = (b) => parseUtc(b.stage_entered_at || b.started_at).getTime() || Infinity;
  const active = [...batches].sort((a, b) => stageStart(a) - stageStart(b));

  const list = (items, heading) =>
    items.length > 0 && (
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{heading}</h3>
        <ul className="space-y-2">
          {items.map((r) => (
            <ReminderRow
              key={r.id}
              r={r}
              batch={byId.get(r.batch_id)}
              busy={!!busy[r.id]}
              error={errors[r.id]}
              note={notes[r.id]}
              now={now}
              onDone={onDone}
              onSnooze={onSnooze}
              onLogPh={logPh}
            />
          ))}
        </ul>
      </div>
    );

  return (
    <div className="space-y-4">
      {active.length === 0 && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-center">
          <h2 className="text-lg font-semibold text-slate-100">Start a batch in 30 seconds</h2>
          <p className="mb-4 mt-1 text-sm text-slate-400">
            Pick what you're fermenting and we'll show you here when it's time to act.
          </p>
          <a
            href="#/batches"
            className="inline-block rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500"
          >
            Start your first batch
          </a>
        </section>
      )}

      {(reminders.length > 0 || active.length > 0) && (
        <Card title="Needs you now">
          {logged && (
            <p role="status" className="mb-3 text-sm text-emerald-300">
              {logged}
            </p>
          )}
          {reminders.length === 0 ? (
            <p className="text-sm text-slate-400">
              Nothing due in the next 48h. You're all caught up.
            </p>
          ) : (
            <div className="space-y-4">
              {list(overdue, "Overdue")}
              {list(upcoming, "Coming up (next 48h)")}
            </div>
          )}
        </Card>
      )}

      {active.length > 0 && (
        <Card title="Active batches">
          <ul className="grid gap-2 sm:grid-cols-2">
            {active.map((b) => (
              <BatchCard key={b.id} b={b} now={now} />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
