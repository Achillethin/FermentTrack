import { useEffect, useState } from "react";
import TemperatureField from "./prediction/TemperatureField.jsx";
import { parseTemperature } from "./prediction/temperature.js";
import { Button, Input, Select } from "./components/ui.jsx";
import { API_URL, SUBSTRATES, humanize, Card, timeAgo } from "./shared.jsx";

function NewBatch({ onCreated }) {
  const [cultures, setCultures] = useState([]);
  const [cultureId, setCultureId] = useState("");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("kombucha");
  const [target, setTarget] = useState("");
  const [expectedTemp, setExpectedTemp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const selectedType = cultureId ? cultures.find((c) => c.id === cultureId)?.type : newType;

  useEffect(() => {
    fetch(`${API_URL}/cultures`)
      .then((r) => r.json())
      .then(setCultures)
      .catch(() => {});
  }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const temp = parseTemperature(expectedTemp);
      if (temp.error) throw new Error(temp.error);
      let id = cultureId;
      if (!id) {
        if (!newName.trim()) throw new Error("Pick a culture or name a new one");
        const res = await fetch(`${API_URL}/cultures`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: newName, type: newType }),
        });
        if (!res.ok) throw new Error("Could not create culture");
        id = (await res.json()).id;
      }
      const res = await fetch(`${API_URL}/batches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          culture_id: id,
          target: target || null,
          expected_temperature_c: temp.value,
        }),
      });
      if (!res.ok) throw new Error("Could not start batch");
      const batch = await res.json();
      onCreated(batch.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Start a batch">
      <form className="space-y-3" onSubmit={submit}>
        <div>
          <label htmlFor="culture-select" className="mb-1 block text-xs text-slate-400">
            Existing culture
          </label>
          <Select
            id="culture-select"
            className="w-full"
            value={cultureId}
            onChange={(e) => setCultureId(e.target.value)}
          >
            <option value="">— start a new culture —</option>
            {cultures.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type})
              </option>
            ))}
          </Select>
        </div>
        {!cultureId && (
          <div className="flex gap-2">
            <Input
              label="New culture name"
              className="flex-1"
              placeholder="New culture name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <Select
              label="New culture substrate type"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            >
              {SUBSTRATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </div>
        )}
        <Input
          label="Batch target (optional)"
          className="w-full"
          placeholder="Target (optional)"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <TemperatureField type={selectedType} value={expectedTemp} onChange={setExpectedTemp} />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? "Starting…" : "Start batch"}
        </Button>
      </form>
    </Card>
  );
}

function BatchPicker({ onPick, defaultOutcome = "in_progress" }) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [outcome, setOutcome] = useState(defaultOutcome);
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showIdField, setShowIdField] = useState(false);
  const [manualId, setManualId] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (type) params.set("type", type);
      if (outcome) params.set("outcome", outcome);
      fetch(`${API_URL}/batches?${params}`)
        .then((r) => {
          if (!r.ok) throw new Error(`Could not load batches (${r.status})`);
          return r.json();
        })
        .then(setBatches)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [query, type, outcome]);

  return (
    <Card title="Your batches">
      <div className="flex flex-wrap gap-2">
        <Input
          label="Search batches by culture name"
          className="min-w-[10rem] flex-1"
          placeholder="Search by culture name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Select label="Filter by substrate" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">all substrates</option>
          {SUBSTRATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Select
          label="Filter by outcome"
          value={outcome}
          onChange={(e) => setOutcome(e.target.value)}
        >
          <option value="">any outcome</option>
          <option value="in_progress">in progress</option>
          <option value="success">completed</option>
          <option value="failed">failed</option>
        </Select>
      </div>

      {loading && <p className="mt-2 text-xs text-slate-500">Searching…</p>}
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

      {!loading && batches.length === 0 && !error && (
        <p className="mt-2 text-sm text-slate-500">No batches match.</p>
      )}

      {batches.length > 0 && (
        <ul className="mt-2 max-h-72 divide-y divide-slate-800 overflow-y-auto rounded-lg border border-slate-800">
          {batches.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => onPick(b.id)}
                className="flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-0.5 px-3 py-2 text-left text-sm hover:bg-slate-800"
              >
                <span className="text-slate-200">{b.culture_name}</span>
                <span className="text-slate-500">{b.culture_type}</span>
                <span className="text-slate-500">{humanize(b.current_stage)}</span>
                <span className="text-xs text-slate-400">{timeAgo(b.started_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setShowIdField((v) => !v)}
        className="mt-3 text-xs text-slate-500 hover:text-slate-300"
      >
        {showIdField ? "Hide" : "Have a batch ID instead?"}
      </button>
      {showIdField && (
        <form
          className="mt-2 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (manualId.trim()) onPick(manualId.trim());
          }}
        >
          <Input
            label="Batch ID"
            className="flex-1"
            placeholder="Batch ID"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
          />
          <Button type="submit" variant="secondary" size="lg">
            Load
          </Button>
        </form>
      )}
    </Card>
  );
}

export { BatchPicker };

export default function Batches() {
  const open = (id) => {
    window.location.hash = "#/batch/" + id;
  };
  return (
    <>
      <p className="max-w-[60ch] text-slate-300">
        A journal and forecast for every batch you ferment: log what you see, check the model, stay in the safe range.
      </p>
      <BatchPicker onPick={open} />
      <NewBatch onCreated={open} />
    </>
  );
}
