import { useEffect, useState } from "react";
import BatchView from "./BatchView.jsx";
import Batches from "./Batches.jsx";
import Compare from "./Compare.jsx";
import ExportButton from "./ExportButton.jsx";
import Logbook from "./Logbook.jsx";
import Planner from "./sourdough/Planner.jsx";
import Today from "./Today.jsx";
import { JarMark } from "./shared.jsx";

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
  ["levain", "Planner"],
];

// #/batch/<id> | #/today | #/logbook | #/batches | #/compare | #/levain[?p=<shared plan>];
// anything else → today.
function parseHash(hash) {
  const m = hash.match(/^#\/batch\/([^/?]+)\/?$/);
  if (m) return { page: "batch", id: m[1] };
  const page = hash.slice(2).split("?")[0]; // a shared plan rides after "?" (#/levain?p=...)
  if (page === "levain") return { page };
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
  // The levain planner is a full-screen page with its own way back (a baker's entry point).
  if (page === "levain") {
    return <Planner onOpenBatch={(batchId) => (window.location.hash = `#/batch/${batchId}`)} />;
  }
  const Page = PAGES[page];
  const active = page === "batch" ? "batches" : page; // a batch page lives under Batches

  return (
    <main className="mx-auto max-w-2xl space-y-4 px-4 pb-16 pt-3">
      <header className="flex items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 font-display text-xl font-extrabold tracking-tight">
          <JarMark />
          FermentTrack
        </h1>
      </header>

      <nav aria-label="Main" className="flex flex-wrap items-center gap-1 text-sm">
        {NAV.map(([key, label]) => (
          <a
            key={key}
            href={`#/${key}`}
            aria-current={active === key ? "page" : undefined}
            className={`flex min-h-[44px] items-center rounded-lg px-3 ${
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
