# Biochemistry Panel — Organisms, Enzymes, Compounds, Custom Organism — UI Design

**Date:** 2026-09-24
**Status:** DRAFT for owner review
**Builds on:** `2026-09-23-fermentation-biochemistry-design.md` (data model, `/biochemistry`, `/organisms`, `POST /batches/{id}/organisms`; its "UI this increment: None" is what this spec follows up), `2026-09-24-biochemistry-v2-curation-draft.md` (what the data is and is not), `2026-09-23-usda-food-catalog-design.md` (search-and-pick precedent), `docs/STRATEGY.md` Direction 3 (the honesty constraint).

## Problem and goals

The backend can say which organisms, enzymes and compounds are typically associated with a batch's fermentation type, and can override the organism set per batch. Nothing in the frontend shows it. A fermenter looking at a kombucha batch should see "yeast + acetic acid bacteria; these enzymes; these compounds are involved" and, if they used a specific strain, be able to say so.

Goals: (1) show the three lists for the open batch, labelled as reference data; (2) let the user attach an organism already in the reference set; (3) make "attaching replaces the defaults" impossible to miss.

Non-goal: prediction. The data may later feed a model; this panel is a reference card, not a forecast. `docs/STRATEGY.md` Direction 3 deferred this UI because unvalidated compound data risks overclaiming; the 2026-09-23 spec un-deferred it only for the KEGG-identified, hand-curated reference layer. The labelling in section 1 is a condition of shipping, not polish.

## What exists (verified 2026-09-24)

- **Frontend:** one file, `frontend/src/App.jsx` (750 lines), React 18 + Tailwind, no router, no state library, no i18n. Most write paths inline `fetch`, `res.ok` and `body.detail || "Could not X (status)"` (`App.jsx:56-59`, `299-302`); `NewBatch` throws fixed strings (`581`, `589`) and `Recipe`'s options fetch swallows errors (`264`). No shared fetch helper. `Card` takes only `title` and `children` (`32-41`).
- **Load pattern:** `loadPreview` clears `preview` and `composition` (`669-670`), fetches `/preview` then `/composition` sequentially (`672-676`), then renders the cards (`726-747`). Every child therefore unmounts on each reload (stage advance, observation, ingredient add all call it: `733-741`), so a panel that fetches on mount refetches after each.
- **Existing hazard to avoid:** children receive `batchId`, the text-input state (`659`, `714`), not the loaded batch; editing the box after a load changes the prop under a loaded page. The panel takes `preview.batch.id` (`BatchOut.id`, `schemas.py:46`).
- **Search precedent:** `Recipe` debounces 250 ms, ignores `q` under 2 chars, swallows errors, shows a clickable list, suppresses Enter (`267-280`, `367`, `369-388`). No out-of-order guard, and nothing shown for "no results".
- **PWA:** `VitePWA({registerType: "autoUpdate"})`, no runtime caching configured (`vite.config.js:13-26`). `frontend/dist/sw.js` was inspected: `precacheAndRoute` of static assets plus a `NavigationRoute` to `index.html`, no runtime caching (`dist` may be stale, but it matches the config). API calls are network-only; offline means failed fetches.
- **Tests:** none. `package.json` has only `dev`/`build`/`preview`; CI is `npm ci` + `npm run build` (`deploy-frontend.yml:28,30`). Backend endpoint tests exist (`tests/test_batch_biochemistry.py`, `tests/test_organisms.py`).
- **i18n / a11y:** none. `index.html:2` is `lang="en"`; Safety renders only `summary_en` / `reason_text_en` (`App.jsx:536,542`) though the API returns FR. No `aria-*` or `role=` in `frontend/src`; inputs rely on placeholders; the one `<label>` (`603`) has no `htmlFor`.
- **API:** `GET /batches/{id}/biochemistry` (`batches.py:417-452`); `POST /batches/{id}/organisms` (`455-481`); `GET /organisms?q=` (`organisms.py:14-27`, `q` min 2, `limit` 1..50, default 20, ordered by name length). `/preview` deliberately carries no compound/microbial data and is owned by one page (`batches.py:352-359`).
- **Data version:** garum's default set is `[Tetragenococcus halophilus, Aspergillus oryzae]` in `biochem.py:65-69` (v3, migration `alembic/versions/0010_biochemistry_v3.py`, in the repo; whether it is applied on the deployed database is not verified here).

## Decisions (proposed; the ones marked OQ are in the open questions)

| Question | Proposed decision | Rejected, and why |
|---|---|---|
| Data source | Panel makes its own `GET /batches/{id}/biochemistry` | Extending `/preview`: its docstring forbids it (`batches.py:352-359`) and it would resend on every reload. |
| Component shape | New `Biochemistry` component in `App.jsx`, inline-fetch idiom, own `useEffect` keyed on `preview.batch.id` | New file or shared fetch helper: the app is one file; a helper is speculative. Hoisting state into `App`: bigger diff, no gain. |
| Position (OQ6) | After `Composition`, before `Timeline` (`App.jsx:743-744`) | Last: a long Timeline buries it. Above Recipe: reference data should not precede the user's inputs. Safety keeps its place. |
| Layout | Organisms and compounds visible; enzymes in native `<details>`, collapsed | All expanded: miso has 11 enzymes (curation §6), too long on a phone. Tabs: extra state for short lists. |
| Icons / colour | Text labels, neutral slate; source badge is text plus a sky tint | Icons: no icon library in `package.json`, no icon slot in `Card`. `urgencyColor` (`21-30`) for categories: red/orange reads as hazard. |
| Grouping enzymes/compounds by organism | Flat lists in v1 | The response has no organism-to-enzyme edges (section 5); cannot be inferred client-side. |
| EC numbers (OQ5) | `EC 1.1.1.1` linked to `https://www.kegg.jp/entry/ec:<number>`, `target="_blank" rel="noopener noreferrer"` (URL form unverified; manual step 1 checks it) | Plain text: loses the cheap way to verify. The link is user-initiated and carries a public EC number only. |
| Compound links | None in v1 | `CompoundOut` has no KEGG id (`schemas.py:288-293`; the model has the column). A guessed URL from a name would be wrong. Form would be `https://www.kegg.jp/entry/<compound id>` (unverified). |
| Attach when defaults apply (OQ1) | Inline confirm, two explicit choices, "keep defaults and add X" preselected (hidden when X is already a default) | Silent replace (surprise). Replace-only (cannot keep defaults). Waiting for a backend change (not required). |
| "Keep defaults" mechanism | Client-side sequence of N+1 POSTs, defaults first, X last. Not atomic. | New atomic endpoint: recommended follow-up. X-first would leave a silent replace on partial failure. |
| Notes field (OQ4) | Omitted in v1 | `BiochemOrganismOut` has no `notes` (`schemas.py:296-300`); a typed strain or lot could never be shown again. |
| Language | English only | Names come from KEGG with no FR; Safety is effectively EN-only. |
| Caching / offline | None; refetch on mount and after writes | Invalidation logic for a ~1 KB response. |
| Non-`in_progress` batches | Attach is allowed on any loaded batch | The API has no such check (`batches.py:455-481`); `Recipe` is likewise unconditional (`736`), unlike `StageControl` (`101`). |

## 1. Honesty and labelling (mandatory)

**Provenance line**, visible without interaction, directly under the card title:

> Reference data for a kombucha batch: not measured in this batch and not a prediction. Organisms and their enzymes are hand-curated, typical rather than exhaustive, and have not been expert-reviewed; enzyme and compound identities are from KEGG. Compounds come from representative reactions, not full pathways.

Custom set: the first clause becomes "Organisms below were set for this batch; enzymes and compounds are reference data for them, not measured in this batch and not a prediction." followed by the same second and third sentences. Empty type (below): reduced to "Reference data only; nothing is recorded for this type." so the line never claims data exists. Use `text-slate-400`, not the `text-slate-500` used for fine print (`321`, `469`). `Composition` carries an equivalent line (`469-471`).

**Also visible** (small text under the lists, not inside `<details>`): "Enzymes are listed for the whole set, not attributed to individual organisms, and some organisms have no enzymes recorded." The collapsed "What this shows" adds the examples (*Gluconacetobacter xylinus*, *Lactobacillus kefiri*, *L. kefiranofaciens* have organism rows but no enzyme links, curation §8.3), that amylases and proteases have no compound rows (starch and protein are not KEGG compounds, curation §2), and that organism names are the widely used pre-reclassification forms (curation §1).

**Wording rules.** Headings: "Organisms", "Enzymes", "Compounds involved". Never "suggested", "predicted", "expected", "likely", "might", "may", "could produce", "will produce", "detected", "present in your batch". `docs/STRATEGY.md`'s Phase-2 title "What compounds might my batch produce?" must not be reused. "Compounds involved" is deliberate: it lists every substrate and product of the curated reactions (`batches.py:441-443`) and the response does not say which is which (maltose and lactose are substrates; CO2 and Acetate are products). Never "produced".

**No numbers about the data.** No confidence, score or percentage. Item counts ("Enzymes (5)") are fine. The curation record's confidence column stays in the docs.

**Empty and thin states**
- **A list is empty** (organisms exist): `No enzymes recorded in this reference set for kombucha.` (type default) or `... for the organisms in this set.` (custom set); likewise "No compounds recorded". The heading is plain text ("Enzymes (0)"), not a `<details>`. Reachable case: attach *Lactobacillus kefiri* alone with "Use only" (organism row, no enzyme links).
- **No organisms at all** (empty `organisms`, no overrides; reachable because `POST /cultures` accepts any free-string type and `first_stage` tolerates it, `stages.py:381-383`): show "No reference organisms are recorded for this type. You can attach one." plus the attach button. Enzymes and compounds sections are not rendered.
- **Known-thin default sets** are not exposed by the API. v1 keeps a constant `THIN_NOTES` in `App.jsx`, each entry citing the source in a comment, shown only while every organism has `source: "default"`:
  - cheese: `Known gap: proteases such as chymosin are not in this reference set yet.` (curation §7)
  - garum: `Known gap: fish digestive proteases are not in this reference set. Default organisms assume koji-based garum (no koji in traditional garum); use "Set organisms for this batch" to change them.` (curation §7; `biochem.py:65-69`)
  - kefir: `Known gap: two of the four default organisms (Lactobacillus kefiri, L. kefiranofaciens) have no enzymes recorded.` (curation §8.3; the record calls this out but does not label the type thin, so this entry is my call)
  - Kombucha's defaults are debated (curation §8.4) but not flagged separately; the provenance line covers "typical, not exhaustive". It can be added to `THIN_NOTES` if wanted. The manual copy goes away with the `known_gaps` follow-up (section 5).

## 2. Layout

Mobile first, single column in the existing `max-w-2xl` main (`App.jsx:693`). Rows use `flex flex-wrap` so nothing overflows at 360 px; the badge sits on its own line under the name. Sorted client-side because the API has no `ORDER BY` (`batches.py:430,451`): organisms by name, enzymes numerically by dotted EC parts (3.2.1.3 before 3.2.1.20), compounds by category then name.

```
+--------------------------------------+
| BIOCHEMISTRY                         |
| Reference data for a kombucha batch: |
| not measured in this batch and not a |
| prediction. Organisms and their      |
| enzymes are hand-curated, typical    |
| rather than exhaustive, and have not |
| been expert-reviewed; enzyme and     |
| compound identities are from KEGG.   |
| Compounds come from representative   |
| reactions, not full pathways.        |
|                                      |
| Organisms                            |
| Acetobacter aceti                    |
|   bacteria                           |
|   [type default]                     |
| Gluconacetobacter xylinus            |
|   bacteria                           |
|   [type default]                     |
| Saccharomyces cerevisiae             |
|   yeast                              |
|   [type default]                     |
| [ Set organisms for this batch ]     |
|                                      |
| Compounds involved                   |
| Acids     Acetate                    |
| Alcohols  Ethanol                    |
| Gases     CO2                        |
| Other     Acetaldehyde  Pyruvate     |
|                                      |
| > Enzymes (5)                        |
|   alcohol dehydrogenase   EC 1.1.1.1 |
|   ...                                |
| Enzymes are listed for the whole set,|
| not attributed to individual         |
| organisms, and some organisms have   |
| none recorded.                       |
| > What this shows                    |
+--------------------------------------+
```

- **Organisms:** italic name, `kingdom` in `text-slate-400` (not the `text-slate-500` of `383`), then the badge: `type default` (slate border) or `set for this batch` (`text-sky-400 border-sky-500/40 bg-sky-950/40`). Text carries the meaning, not colour. "Keep defaults" re-records defaults as overrides, which the API returns as `custom` (the `BatchOrganism.source` column default), so "set for this batch" is accurate for both and "custom" would not be.
- **Compounds:** chips grouped acid, alcohol, gas, flavor, other; labels Acids, Alcohols, Gases, Flavor compounds, Other; empty groups hidden; unknown categories go to Other. `flavor` has no members today (curation §3). "Other" is the largest group (8 of 13 compounds in `biochem.py` `COMPOUNDS`), so it keeps a neutral label. Names as returned: `(S)-Lactate`, `(R)-Lactate`, `Acetate`, `CO2`.
- **Enzymes:** `<details><summary>Enzymes (n)</summary>`; row = name plus `EC x.x.x.x` link in `font-mono`.
- **Action button:** "Set organisms for this batch" when all sources are `default` or the set is empty; "Add organism" when overrides exist.

## 3. Custom-organism flow

1. **Open.** Secondary button (`bg-slate-700`, as `StageControl`, `App.jsx:73`) toggles an inline form.
2. **Search.** `type="search"` with a visually hidden label, at `text-base` (16 px; the app's `text-sm` inputs trigger iOS focus-zoom). Debounced 250 ms, `GET /organisms?q=<trimmed>`. Under 2 chars: no request, hint "Type at least 2 letters" (the API would 422). Cancel flag in the effect cleanup so a slow response cannot overwrite a newer one (`Recipe` lacks this, `274-277`). "Searching…" while pending; for an empty result: `No organism matching "xx" in the reference set. Only organisms already in the reference set can be attached.` Enter suppressed as at `367`. Reference set is small (14 as of v2), so `max-h-60 overflow-y-auto` (`370`) rarely scrolls.
3. **Result row.** Button, `py-3`: italic name, kingdom on the right. Rows whose organism is already in the set with source `set for this batch` are disabled ("already attached"; the API would 409). Rows in the set as `type default` stay selectable.
4. **Pick.** Shows the chosen organism plus "clear" (pattern at `337-359`).
5. **Confirm.** Warning iff `organisms.length > 0 && organisms.every(o => o.source === "default")`. Amber box (the app's warning tone, `urgencyColor("medium")`, `App.jsx:26`), text computed from the type and count, not hard-coded:
   > This batch currently uses the {type} defaults ({n} organisms). Once you attach an organism, only the organisms attached to this batch are used and the defaults stop applying. The app cannot undo this yet.
   - `(o) Keep the {n} {type} defaults and add <X>` (preselected; **hidden when X is already one of the defaults**, leaving only "Use only <X>", which then sends one POST).
   - `( ) Use only <X>`
   - If overrides already exist: no warning, one line "Adds <X> to the organisms set for this batch."
   - Button `Attach`.
6. **Submit.** Disable the button, label "Attaching…" (`75`, `241`). "Use only" is one POST. "Keep defaults" is a sequence and is **not atomic**: on Confirm, snapshot `plan = { ids: [...defaultIds, X.id], done: [] }` in component state (ids from the current response). POST each in order, defaults first and X last, appending to `done` as each succeeds. A `409` counts as done (already attached), so retry is safe.

```jsx
for (const id of plan.ids.filter((i) => !plan.done.includes(i))) {
  const res = await fetch(`${API_URL}/batches/${batchId}/organisms`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ organism_id: id }),
  });
  if (!res.ok && res.status !== 409) throw new Error(/* body.detail as App.jsx:299-302 */);
  setPlan((p) => ({ ...p, done: [...p.done, id] }));
}
```

7. **Partial failure.** Keep the form open and show: "Attached N of M: <names>. Not attached: <names>. Until you retry, this batch has only some of the defaults and the app cannot undo it." with a **Retry remaining** button that continues from the snapshot (never from a refetched response: once any override exists the response no longer contains `default` rows). Refetch the panel in the background so the lists show what was saved. Clearing the form abandons the plan (the batch stays partial; say so).
8. **Other errors** (inline `text-sm text-red-400`, `446` idiom): `409` in "use only" mode: show `detail`, refetch. `404`: show `detail` ("Organism not found" / "Batch not found"). Network: test `e instanceof TypeError` and show "Could not reach the server" (the raw message at `62`/`681` is "Failed to fetch"). Guard `typeof body.detail === "string"`: a 422 returns a list that the existing idiom would render as `[object Object]`.
9. **Success.** Close the form, clear the plan, refetch `/biochemistry` (panel-local; `loadPreview` would blank the page, `669-670`), "Organisms updated." in an `aria-live="polite"` line.

**Panel states.** Initial load: "Loading biochemistry…". Failure: message plus Retry; other cards unaffected (unlike `composition`, whose failure is silently null, `676`). **Refetch keeps the old data on screen and swaps on success**, so `<details>` open state survives; a cancel flag on the panel's own fetch drops stale responses. A failed refetch shows the error above the old data.

## 4. Data flow and API contract

| When | Call | Notes |
|---|---|---|
| Panel mounts (after `/preview` succeeded) | `GET /batches/{id}/biochemistry` | Refetched on every mount, which includes each `loadPreview`. |
| >= 2 chars, 250 ms idle | `GET /organisms?q=<q>` | Default `limit=20`; no pagination. |
| Attach | `POST /batches/{id}/organisms` `{organism_id}`, 1 to N+1 times | Response ignored; the refetch is the source of truth. |
| After attach or failure | `GET /batches/{id}/biochemistry` | |

The response is derived, not stored: any `batch_organisms` row for the batch means only those organisms, all `source: "custom"`; none means the type defaults, all `source: "default"` (`batches.py:395-414`). So the two states are distinguishable from `source`; an override is permanent (no DELETE route); there is no multi-attach endpoint; a duplicate `409` comes from an application check, not a constraint (`batches.py:463-473`), so a race could double-insert, which is why the UI disables already-attached rows.

**No backend change is required for v1.** The best UX still needs backend follow-ups: atomic attach-with-defaults (`include_defaults`) to remove the partial-failure state, and DELETE for undo. Both are recommended (section 5). Without them: "keep defaults" is non-atomic, re-recorded defaults display as `set for this batch`, and an override cannot be undone from the app.

## 5. Optional backend follow-ups (not part of v1)

| Follow-up | Enables |
|---|---|
| `DELETE /batches/{id}/organisms/{organism_id}` and/or reset-to-defaults | Undo an override. Highest value. |
| `POST` accepts `organism_ids: []` or `include_defaults: true` | Atomic "keep defaults"; removes the partial-failure state and "Retry remaining". |
| `kegg_compound_id` on `CompoundOut` | Compound links (form unverified). One field. |
| `notes` on `BiochemOrganismOut` | Show strain or lot notes, then add the input. |
| `organism_ids` on each `EnzymeOut`, or a `reactions: [{enzyme_id, substrate_id, product_id}]` list | Group enzymes by organism; label compounds substrate or product. Data is already loaded in the handler (`batches.py:425-443`). |
| `known_gaps` per fermentation type | Replaces `THIN_NOTES`. |
| `ORDER BY` in the biochemistry queries | Stable order without client sorting. |
| Doc drift: the `BatchOrganism` docstring in `models.py` and `2026-09-23-fermentation-biochemistry-design.md` (~line 28 "override/addition", ~line 69 "overrides/extends") say overrides extend the set, but the code replaces the defaults | Fix wording so future readers do not design against the wrong semantics. |

## 6. Accessibility and i18n

- Search input has a real (`sr-only`) label; the confirm choice uses native labelled radios.
- Results and status in an `aria-live="polite"` region ("3 organisms found", "Organisms updated."); errors `role="alert"`.
- `<details>`/`<summary>` for enzymes and caveats (keyboard and screen-reader accessible without JS).
- Touch targets `py-3` in the panel; badges carry text; provenance uses `text-slate-400`.
- Focus returns to the action button after a successful attach, to the search input after "clear".
- i18n: none exists, none added. English only. Bilingual would need translated organism, enzyme and compound names the API does not carry; not recommended.

## 7. Testing

- **Automated:** none possible today (no runner; CI is build-only). Gate: `npm run build`. Vitest plus Testing Library would be 3+ dev deps; out of scope. Backend behaviour is covered by `tests/test_batch_biochemistry.py` and `tests/test_organisms.py`.
- **Manual script.** Run every write step (7 onward) against a **local backend** with throwaway batches, not production: attaching is irreversible (no DELETE). Read-only steps 1-6 can use either. Local: set `VITE_API_URL` (`frontend/.env.example`); on the Nestlé network use `curl --ssl-no-revoke` for any API pre-check of the deployed service.
  1. Kombucha: 3 organisms (*Acetobacter aceti*, *Gluconacetobacter xylinus*, *S. cerevisiae*), compounds Ethanol, Acetaldehyde, Pyruvate, Acetate, CO2 grouped, 5 enzymes; each EC link opens the matching kegg.jp entry (this verifies the URL form).
  2. Koji: *A. oryzae* only, 8 enzymes, compounds Maltose, D-Glucose, L-Glutamine, L-Glutamate.
  3. Garum. **Before v3 (0010) is applied:** *T. halophilus* only; enzyme L-lactate dehydrogenase; compounds Pyruvate, (S)-Lactate. **After v3:** adds *A. oryzae* and its eight enzymes (alpha-amylase, glucan 1,4-alpha-glucosidase, alpha-glucosidase, oryzin, deuterolysin, aspergillopepsin I, carboxypeptidase C, glutaminase) plus L-lactate dehydrogenase; compounds add Maltose, D-Glucose, L-Glutamine, L-Glutamate. Garum "Known gap" note in both.
  4. Cheese: only L-lactate dehydrogenase, `Pyruvate`, `(S)-Lactate`, chymosin note. Kefir shows its note.
  5. Miso (11 enzymes) at 360 px: rows wrap, no horizontal scroll, `<details>` usable.
  6. Provenance line and the whole-set enzyme note visible with no tap on every batch; nothing reads as a prediction.
  7. Type with no defaults: create a culture via the API with `type` outside the nine (for example `"test"`) and start a batch. Panel shows "No reference organisms are recorded for this type. You can attach one.", reduced provenance line, no enzymes or compounds sections, no replace warning on attach.
  8. Search: 0 and 1 characters send no request (network tab) and show the hint; 2 characters return results; nonsense shows the "No organism matching" message.
  9. Throwaway kombucha: pick a **non-default** organism (for example *Lactobacillus plantarum*). Amber warning names "kombucha defaults (3 organisms)" and the irreversibility; "keep defaults" preselected. Attach: 4 organisms, all `set for this batch`, "Organisms updated." announced; the next attach shows no warning.
  10. Pick a default (*S. cerevisiae*) on a fresh kombucha batch: only "Use only" is offered.
  11. Throwaway cheese, choose "Use only" *Lactobacillus kefiri* (otherwise *L. lactis* keeps LDH and nothing is empty): enzymes and compounds show "No enzymes recorded in this reference set for the organisms in this set."
  12. Partial failure: on a fresh kombucha batch, "keep defaults" with DevTools request blocking on `/batches/*/organisms` after the first POST (or stopping the local backend mid-sequence): form stays open, lists attached/not attached, "Retry remaining" completes it without duplicating.
  13. Duplicate: pick an already-attached organism (row disabled); force a 409 with a second tab and confirm the `detail` text and refetch.
  14. Network failure: load a batch, then block `/biochemistry` (or go offline) and reload the panel via a stage advance: error plus Retry, rest of page works; offline during attach shows "Could not reach the server". (Offline at initial load cannot test this: `/preview` fails first.)
  15. Edit the batch-id box after loading: the panel sends no requests per keystroke. Advance a stage: the panel remounts and refetches without visible breakage.

## Out of scope

- Ingredient-to-enzyme table (option B); garum fish digestive proteases and cheese chymosin.
- Creating organisms not already in the reference set.
- Predictions, forecasts, confidence or coverage scores.
- Editing or deleting overrides (needs the DELETE follow-up).
- Offline caching or any service-worker change.
- Per-organism grouping, compound links, showing notes, French copy (each blocked on a section 5 item or a translation source).
- Frontend test infrastructure.

## Open questions (recommended default in brackets)

1. **First attach:** offer both "keep defaults and add X" and "use only X" with keep preselected? [Yes; "use only" is needed to drop *A. oryzae* from a traditional garum batch.]
2. **Ship attach before DELETE and atomic attach exist?** [Yes, with the "cannot undo" and partial-failure copy; alternative is a read-only panel first. Both follow-ups are recommended.]
3. **Thin-type notes as a frontend constant (cheese, garum, kefir)?** [Yes, three entries cited to the curation record.]
4. **Omit the notes input until the API returns notes?** [Yes.]
5. **EC numbers link out to kegg.jp?** [Yes, new tab, user-initiated, public EC number only.]
6. **Panel after Composition, before Timeline?** [Yes.]
