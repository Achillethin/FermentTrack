import { useEffect, useState } from "react";
import BatchView from "./BatchView.jsx";
import Batches from "./Batches.jsx";
import Compare from "./Compare.jsx";
import ExportButton from "./ExportButton.jsx";
import Logbook from "./Logbook.jsx";
import Today from "./Today.jsx";

// Legacy deep links: ?batch=<id> (pre-router) becomes #/batch/<id>.
const legacyBatch = new URLSearchParams(window.location.search).get("batch");
if (legacyBatch && !window.location.hash) {
  window.history.replaceState(null, "", `${window.location.pathname}#/batch/${legacyBatch}`);
}

const PAGES = { today: Today, logbook: Logbook, batches: Batches, compare: Compare };
const NAV = [
  ["today", "Today"],
  ["logbook", "Logbook"],
  ["batches", "Batches"],
  ["compare", "Compare"],
];

// #/batch/<id> | #/today | #/logbook | #/batches | #/compare; anything else → today.
function parseHash(hash) {
  const m = hash.match(/^#\/batch\/([^/?]+)\/?$/);
  if (m) return { page: "batch", id: m[1] };
  const page = hash.slice(2);
  return { page: Object.prototype.hasOwnProperty.call(PAGES, page) ? page : "today" };
}

export default function App() {
  const [hash, setHash] = useState(window.location.hash);

  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const { page, id } = parseHash(hash);
  const Page = PAGES[page];
  const active = page === "batch" ? "batches" : page; // a batch page lives under Batches

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-4">
      <h1 className="text-2xl font-bold">🧫 FermentTrack</h1>

      <nav aria-label="Main" className="flex flex-wrap items-center gap-1 text-sm">
        {NAV.map(([key, label]) => (
          <a
            key={key}
            href={`#/${key}`}
            aria-current={active === key ? "page" : undefined}
            className={`rounded-lg px-3 py-2 ${
              active === key ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {label}
          </a>
        ))}
        <span className="ml-auto">
          <ExportButton />
        </span>
      </nav>

      {page === "batch" ? <BatchView key={id} batchId={id} /> : <Page />}
    </main>
  );
}
