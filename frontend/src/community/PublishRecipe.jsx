import { useId, useRef, useState } from "react";
import { Button, Input } from "../components/ui.jsx";
import { Card } from "../shared.jsx";
import { publishRecipe } from "./api.js";
import { PRIVACY_NOTICE, PSEUDONYM_RULE, publishBody, pseudonymError, refusal, TITLE_MAX, titleError } from "./community.js";

// Publish a finished batch as a community recipe (design § 10.3): title and pen name; the
// privacy notice before sending and in the answer; the API's refusal reasons, verbatim.
export default function PublishRecipe({ batchId, defaultTitle }) {
  const [title, setTitle] = useState(defaultTitle || "");
  const [pseudonym, setPseudonym] = useState("");
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState(null); // {message, reasons}
  const [published, setPublished] = useState(null);
  const id = useId();
  const alertRef = useRef(null);
  const doneRef = useRef(null);

  const titleErr = titleError(title);
  const nameErr = pseudonymError(pseudonym);

  async function submit(e) {
    e.preventDefault();
    setTried(true);
    if (titleErr || nameErr || busy) return;
    setBusy(true);
    setRefused(null);
    try {
      const out = await publishRecipe(publishBody(batchId, title, pseudonym));
      setPublished(out);
      requestAnimationFrame(() => doneRef.current?.focus());
    } catch (err) {
      setRefused(refusal(err));
      requestAnimationFrame(() => alertRef.current?.focus());
    } finally {
      setBusy(false);
    }
  }

  if (published) {
    return (
      <Card title="Shared with the community">
        <div ref={doneRef} tabIndex={-1} role="status" className="space-y-2 text-sm text-slate-200 focus:outline-none">
          <p>
            “{published.title}” by {published.pseudonym} is waiting for review. Once an admin approves it, it appears in the
            Ideas page under “Community — not proven”.
          </p>
          <p className="rounded-lg border border-sky-500/30 bg-sky-950/30 p-2 text-sky-100">{published.notice}</p>
          <p>
            <a href="#/account" className="text-emerald-400 underline hover:text-emerald-300">
              Your community recipes
            </a>{" "}
            shows its status.
          </p>
        </div>
      </Card>
    );
  }

  const field = (err) => (tried && err ? "border-red-500/70" : "");
  return (
    <Card title="Share as a community recipe">
      <p className="text-sm text-slate-300">
        Other fermenters see it in the Ideas page under “Community — not proven”, after an admin’s review. Shared: the
        title, your pen name, the ferment type, the ingredients per kg, its temperature and its duration. Not shared:
        your notes, readings, tastings and account.
      </p>
      <p className="mt-2 text-xs text-slate-400">
        Before it can be shared: the batch ended as a success, it has at least one tasting, every ingredient has a
        quantity, it passes the recommender’s safety checks, and an acid-safety ferment has a logged pH of 4.6 or below.
        The checks run when you send it; anything missing is listed.
      </p>
      <form className="mt-3 space-y-3" onSubmit={submit} noValidate>
        <div>
          <label htmlFor={`${id}-title`} className="mb-1 block text-xs text-slate-300">
            Title
          </label>
          <Input
            id={`${id}-title`}
            className={`min-h-[44px] w-full text-base sm:text-sm ${field(titleErr)}`}
            maxLength={TITLE_MAX + 20}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            aria-invalid={tried && titleErr ? "true" : undefined}
            aria-describedby={tried && titleErr ? `${id}-title-err` : undefined}
          />
          {tried && titleErr && (
            <p id={`${id}-title-err`} className="mt-1 text-xs text-red-400">
              {titleErr}
            </p>
          )}
        </div>
        <div>
          <label htmlFor={`${id}-name`} className="mb-1 block text-xs text-slate-300">
            Pen name (shown with the recipe)
          </label>
          <Input
            id={`${id}-name`}
            className={`min-h-[44px] w-full text-base sm:text-sm ${field(nameErr)}`}
            autoComplete="nickname"
            value={pseudonym}
            onChange={(e) => setPseudonym(e.target.value)}
            aria-invalid={tried && nameErr ? "true" : undefined}
            aria-describedby={`${id}-name-hint${tried && nameErr ? ` ${id}-name-err` : ""}`}
          />
          <p id={`${id}-name-hint`} className="mt-1 text-xs text-slate-400">
            {PSEUDONYM_RULE} Not your real name or e-mail, unless you want it shown.
          </p>
          {tried && nameErr && (
            <p id={`${id}-name-err`} className="mt-1 text-xs text-red-400">
              {nameErr}
            </p>
          )}
        </div>
        <p id={`${id}-notice`} className="rounded-lg border border-sky-500/30 bg-sky-950/30 p-2 text-sm text-sky-100">
          <strong>Before you share:</strong> {PRIVACY_NOTICE}
        </p>
        {refused && (
          <div ref={alertRef} tabIndex={-1} role="alert" className="rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-sm text-red-300 focus:outline-none">
            <p>{refused.message}</p>
            {refused.reasons.length > 0 && (
              <ul className="mt-1 list-disc pl-5">
                {refused.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        <Button type="submit" size="lg" className="min-h-[44px]" disabled={busy} aria-describedby={`${id}-notice`}>
          {busy ? "Sending…" : "Send for review"}
        </Button>
      </form>
    </Card>
  );
}
