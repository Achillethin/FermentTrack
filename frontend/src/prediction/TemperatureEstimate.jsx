import { useRef, useState } from "react";
import TemperatureField from "./TemperatureField.jsx";
import { formatC, parseTemperature } from "./temperature.js";

function ThermometerIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-slate-400" fill="none" aria-hidden="true">
      <path
        d="M14 14.76V5a2 2 0 1 0-4 0v9.76a4 4 0 1 0 4 0Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const btn =
  "inline-flex min-h-[40px] items-center rounded-lg px-3 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:opacity-50";

// Shows the batch's estimated fermentation temperature with an inline editor.
// PATCH /batches/{id} {expected_temperature_c}; onSaved() reloads the batch so
// the forecast is recomputed with the new estimate.
export default function TemperatureEstimate({ apiUrl, batch, type, onSaved }) {
  const current = batch.expected_temperature_c;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const editButton = useRef(null);

  function open() {
    setText(current == null ? "" : String(current));
    setError(null);
    setEditing(true);
  }

  async function save(value) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/batches/${batch.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_temperature_c: value }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(
          typeof body.detail === "string" ? body.detail : `Could not save the temperature (${res.status})`
        );
      }
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(e instanceof TypeError ? "Could not reach the server" : e.message);
    } finally {
      setBusy(false);
    }
  }

  function submit(e) {
    e.preventDefault();
    const parsed = parseTemperature(text);
    if (parsed.error) return;
    save(parsed.value);
  }

  if (!editing) {
    return (
      <div className="mt-2 flex flex-wrap items-center gap-x-1.5 text-sm">
        <ThermometerIcon />
        {current == null ? (
          <span className="text-slate-400">No temperature estimate yet</span>
        ) : (
          <span className="text-slate-300">
            Ferments at ~{formatC(current)} <span className="text-slate-400">(your estimate)</span>
          </span>
        )}
        <button
          ref={editButton}
          type="button"
          onClick={open}
          className={`${btn} -my-2 px-1.5 text-emerald-400 hover:text-emerald-300`}
        >
          {current == null ? "Add estimate" : "Edit"}
        </button>
      </div>
    );
  }

  const parsed = parseTemperature(text);
  return (
    <form className="mt-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3" onSubmit={submit}>
      <TemperatureField type={type} value={text} onChange={setText} autoFocus laterHint={false} />
      {error && (
        <p className="mt-2 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="submit"
          disabled={busy || !!parsed.error || (parsed.value == null && current == null)}
          className={`${btn} bg-emerald-700 text-white hover:bg-emerald-600`}
        >
          {busy ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => {
            setEditing(false);
            setError(null);
            requestAnimationFrame(() => editButton.current?.focus());
          }}
          className={`${btn} bg-slate-700 hover:bg-slate-600`}
        >
          Cancel
        </button>
        {current != null && (
          <button
            type="button"
            disabled={busy}
            onClick={() => save(null)}
            className={`${btn} text-slate-300 hover:text-slate-100`}
          >
            Clear estimate
          </button>
        )}
      </div>
    </form>
  );
}
