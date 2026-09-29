import { useState } from "react";
import { API_URL, apiError, errText } from "./shared.jsx";
import { toCsv } from "./csv.js";

export default function ExportButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/me/export`);
      if (!res.ok) throw new Error(await apiError(res, "Export failed"));
      const csv = toCsv(await res.json());
      const d = new Date();
      const pad = (n) => String(n).padStart(2, "0");
      const url = URL.createObjectURL(
        new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `fermenttrack-export-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      {error && (
        <span role="alert" className="text-xs text-red-400">
          {error}
        </span>
      )}
      <button
        type="button"
        onClick={run}
        disabled={busy}
        aria-busy={busy}
        title="Download my batches and measurements as CSV"
        className="rounded-lg border border-slate-700 px-3 py-2 text-slate-300 hover:bg-slate-800 disabled:opacity-50"
      >
        {busy ? "Exporting…" : "Export CSV"}
      </button>
    </span>
  );
}
