import { useEffect, useState } from "react";
import Account from "./Account.jsx";
import BatchView from "./BatchView.jsx";
import Batches from "./Batches.jsx";
import AdminCommunity from "./community/AdminCommunity.jsx";
import Compare from "./Compare.jsx";
import ExportButton from "./ExportButton.jsx";
import Ideas from "./ideas/Ideas.jsx";
import Logbook from "./Logbook.jsx";
import Planner from "./sourdough/Planner.jsx";
import Today from "./Today.jsx";
import { API_URL, JarMark } from "./shared.jsx";

// Legacy deep links: ?batch=<id> (pre-router) becomes #/batch/<id>.
const legacyBatch = new URLSearchParams(window.location.search).get("batch");
if (legacyBatch && !window.location.hash) {
  window.history.replaceState(null, "", `${window.location.pathname}#/batch/${legacyBatch}`);
}

// The admin pages' own links: every account's logbook, the community review queue.
function AdminNav({ current }) {
  const link = (href, key, label) => (
    <a
      href={href}
      aria-current={current === key ? "page" : undefined}
      className={`flex min-h-[40px] items-center rounded-lg px-3 text-sm ${
        current === key ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
      }`}
    >
      {label}
    </a>
  );
  return (
    <nav aria-label="Admin" className="flex flex-wrap gap-1">
      {link("#/admin", "log", "Logbook")}
      {link("#/admin/community", "community", "Community review")}
    </nav>
  );
}

function AdminLog() {
  return (
    <div className="space-y-3">
      <AdminNav current="log" />
      <p className="text-sm text-slate-400">
        Every account’s logbook, read-only. Open an entry to see that bake; only its owner can change it.
      </p>
      <Logbook admin />
    </div>
  );
}

function AdminReview() {
  return (
    <div className="space-y-3">
      <AdminNav current="community" />
      <AdminCommunity />
    </div>
  );
}

const PAGES = {
  today: Today,
  logbook: Logbook,
  batches: Batches,
  ideas: Ideas,
  compare: Compare,
  account: Account,
  admin: AdminLog,
  "admin/community": AdminReview,
};
const NAV = [
  ["today", "Today"],
  ["logbook", "Logbook"],
  ["batches", "Batches"],
  ["ideas", "Ideas"],
  ["compare", "Compare"],
  ["levain", "Planner"],
  ["account", "Account"],
];

// #/batch/<id>[/tasting] | #/today | #/logbook | #/batches | #/ideas | #/compare
// | #/levain[?p=<shared plan>] | #/account | #/admin | #/admin/community; anything else → today.
function parseHash(hash) {
  const m = hash.match(/^#\/batch\/([^/?]+)(\/tasting)?\/?$/);
  if (m) return { page: "batch", id: m[1], focus: m[2] ? "tasting" : null };
  const page = hash.slice(2).split("?")[0].replace(/\/$/, ""); // a shared plan rides after "?" (#/levain?p=...)
  if (page === "levain") return { page };
  return { page: Object.prototype.hasOwnProperty.call(PAGES, page) ? page : "today" };
}

// A guest session could not be created (e.g. anonymous sign-ins disabled in Supabase):
// supabase-js auth errors carry __isAuthError; a network failure is not one of them.
const isAuthFailure = (err) => Boolean(err?.__isAuthError || /sign-?ins? .*disabled/i.test(err?.message || ""));

export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  const [me, setMe] = useState(null); // {user_id, admin}
  const [authBlocked, setAuthBlocked] = useState(null);

  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  useEffect(() => {
    fetch(`${API_URL}/me`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setMe)
      .catch((err) => {
        if (isAuthFailure(err)) setAuthBlocked(err.message);
      });
  }, []);

  const { page, id, focus } = parseHash(hash);
  // The levain planner is a full-screen page with its own way back (a baker's entry point).
  if (page === "levain" && !authBlocked) {
    return <Planner onOpenBatch={(batchId) => (window.location.hash = `#/batch/${batchId}`)} />;
  }
  const Page = PAGES[page];
  const adminPage = page === "admin" || page === "admin/community";
  // a batch page lives under Batches, the review queue under Admin
  const active = page === "batch" ? "batches" : adminPage ? "admin" : page;
  const nav = me?.admin ? [...NAV, ["admin", "Admin"]] : NAV;

  let content;
  if (authBlocked) content = <Account blocked={authBlocked} />;
  else if (page === "batch") content = <BatchView key={id} batchId={id} focus={focus} />;
  else if (adminPage && !me?.admin) content = <p className="text-sm text-slate-400">Admins only.</p>;
  else content = <Page />;

  return (
    <main className="mx-auto max-w-2xl space-y-4 px-4 pb-16 pt-3">
      <header className="flex items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 font-display text-xl font-extrabold tracking-tight">
          <JarMark />
          FermentTrack
        </h1>
      </header>

      <nav aria-label="Main" className="flex flex-wrap items-center gap-1 text-sm">
        {nav.map(([key, label]) => (
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

      {content}
    </main>
  );
}
