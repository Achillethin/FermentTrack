# Biochemistry Panel — Organisms, Enzymes, Compounds, Custom Organism — UI Design

**Date:** 2026-09-24
**Status:** FINAL — implemented (`frontend/src/App.jsx`, `Biochemistry` component, lines 506-972; mounted at line 1215). Browser test against a local backend is the controller's step; build verified.
**Builds on:** `2026-09-23-fermentation-biochemistry-design.md` (data model, `/biochemistry`, `/organisms`, `POST /batches/{id}/organisms`), `2026-09-24-biochemistry-v2-curation-draft.md` (what the data is and is not), `2026-09-23-usda-food-catalog-design.md` (search-and-pick precedent), `docs/STRATEGY.md` Direction 3 (the honesty constraint).

## Problem and goals

The backend can say which organisms, enzymes and compounds are typically associated with a batch's fermentation type, and lets a batch add organisms of its own. Nothing in the frontend showed it. A fermenter looking at a kombucha batch should see "yeast + acetic acid bacteria; these enzymes, carried by these organisms; these compounds are involved" and, if they used a specific strain, be able to say so.

Goals: (1) show the three lists for the open batch, labelled as reference data; (2) let the user attach an organism from the reference set, with an optional note (a strain name), and remove that attachment again; (3) make clear that attaching adds to the type defaults and never replaces them.

Non-goal: prediction. This panel is a reference card, not a forecast. `docs/STRATEGY.md` Direction 3 deferred this UI because unvalidated compound data risks overclaiming; the 2026-09-23 spec un-deferred it only for the KEGG-identified, hand-curated reference layer. The labelling in section 1 is a condition of shipping, not polish.

## API contract (built against; implemented by the backend in the same change)

- `GET /batches/{id}/biochemistry` -> `{ organisms: [{id, name, kingdom, source: "default"|"custom", notes}], enzymes: [{id, ec_number, name, organism_ids}], compounds: [{id, name, category, kegg_compound_id|null}] }`. Sorted server-side (organisms by name, enzymes by EC numerically, compounds by category then name); the client does not re-sort. Organisms = type defaults plus custom attachments, deduplicated with custom winning.
- `GET /organisms?q=&limit=` (`q` >= 2 chars, `limit` 1..50).
- `POST /batches/{id}/organisms` `{organism_id, notes?}` -> 201; 404 (`Batch not found` / `Organism not found`); 409 (`'<name>' is already attached to this batch`); 422 for notes > 500 chars. Attaching an organism that is already a type default is allowed (it then shows once, as custom, with the note).
- `DELETE /batches/{id}/organisms/{organism_id}` -> 204; 404 (`Organism is not attached to this batch` / `Batch not found`). Never touches defaults.

## What exists (frontend, verified 2026-09-24)

- One file, `frontend/src/App.jsx`, React 18 + Tailwind, no router, no state library, no i18n, no tests; CI is `npm ci` + `npm run build`. Inline `fetch` with `body.detail || "Could not X (status)"`; `Card` takes only `title` and `children`.
- `loadPreview` clears `preview` and `composition` and refetches, so every child unmounts and remounts on each stage advance, observation or ingredient add. The panel therefore refetches on mount. It takes `preview.batch.id` (not the editable batch-id text box) and `preview.culture.type` as props.
- Search precedent: `Recipe` debounces 250 ms, ignores `q` under 2 chars, swallows errors, no out-of-order guard, no "no results" message.
- PWA: no runtime caching; API calls are network-only.

## Decisions (final)

Owner decisions are marked **[owner]**; they override the earlier draft.

| Question | Decision | Rejected, and why |
|---|---|---|
| Data source | Panel makes its own `GET /batches/{id}/biochemistry` | Extending `/preview`: its docstring forbids it (`batches.py`) and it would resend on every reload. |
| Component shape | New `Biochemistry` component in `App.jsx`, inline-fetch idiom, own `useEffect` keyed on batch id and a reload counter | New file or shared fetch helper: the app is one file. |
| Position | After `Composition`, before `Timeline` (line 1215) | Last: a long Timeline buries it. Above Recipe: reference data should not precede the user's inputs. |
| Layout | Organisms and compounds visible; enzymes in native `<details>`, collapsed, with count | All expanded: miso has 11 enzymes. Tabs: extra state for short lists. |
| Attach semantics **[owner]** | Attaching **adds** to the type defaults; it never replaces them. One POST attaches one organism. No "use only", no replace warning, no client-side multi-POST sequence | The earlier "replace" semantics, "keep defaults / use only" choice, `defaultIds` snapshot and "Retry remaining" are removed. |
| Explanation copy **[owner]** | Form text: "Adds to the default organisms for <type>; it does not replace them." | A warning box: nothing is lost by attaching. |
| Notes **[owner]** | Optional free-text note, max 500 chars (`maxLength`), in the attach form; `text-base` (16 px, no iOS focus zoom); shown under the organism, custom rows only | Omission (earlier draft): the API now returns notes. |
| KEGG links **[owner]** | Enzyme: `https://www.kegg.jp/entry/ec:<ec_number>`. Compound (only when `kegg_compound_id` is non-null): `https://www.kegg.jp/entry/<id>`. `target="_blank" rel="noopener noreferrer"`, link text "KEGG", `title` and `aria-label` carry the description, plus a visible legend line | Plain text EC numbers; guessed compound URLs. |
| Remove **[owner]** | Two-step inline button on custom rows: "Remove" -> "Confirm remove" / "Cancel"; `DELETE`, then refetch. A default that also has a custom attachment shows once as "custom"; removing reverts it to a plain default | `window.confirm` (blocking, unstyled, poor on mobile). |
| Enzyme attribution | `organism_ids` on each enzyme drives "Carried by: <names>"; an organism in no enzyme's `organism_ids` gets "No enzymes recorded for this organism." | The earlier whole-set caveat ("enzymes are not attributed to organisms"): no longer true. |
| Thin-type notes | `THIN_NOTES` constant (cheese, garum, kefir), shown for every batch of that type (line 506) | A server-side flag: does not exist yet (follow-up). |
| Icons / colour | Text labels, neutral slate; "custom" badge is text plus sky tint | Icon library / `urgencyColor` (red/orange reads as hazard). |
| Language | English only | Names come from KEGG with no FR. |
| Caching / offline | None; refetch on mount and after writes; a refetch keeps old data on screen and swaps on success; requests abort on unmount and on the next reload | Invalidation logic for a ~1 KB response. |
| Non-`in_progress` batches | Attach and remove allowed on any loaded batch | The API has no such check; `Recipe` is likewise unconditional. |

## 1. Honesty and labelling (mandatory)

**Provenance line**, visible without interaction, directly under the card title (`App.jsx:682-683`, `text-slate-400`, not the dimmer `text-slate-500`):

> Reference data for a {type} batch: not measured in this batch and not a forecast. Organisms and their enzymes are hand-curated, typical rather than exhaustive, and have not been expert-reviewed; enzyme and compound identities are from KEGG. Compounds come from representative reactions, not full pathways.

When any organism is custom, it appends "Organisms marked custom were attached to this batch by you." When there are no organisms at all it reduces to "Reference data only; nothing is recorded for this type." so the line never claims data exists. ("forecast" rather than "prediction" so that the banned stem does not appear in the panel at all.)

**KEGG legend**, visible under the lists (`App.jsx:827`): "KEGG is a public biochemistry database; links open kegg.jp in a new tab. Enzyme links show the reaction and references; compound links show structure and pathways." Each link additionally carries a `title` and `aria-label`: enzyme "KEGG ENZYME entry for EC <n>: reaction, systematic name and references"; compound "KEGG COMPOUND entry <id>: structure, reactions and pathways" (`KeggLink`, `App.jsx:529`).

**Wording rules.** Headings: "Organisms", "Enzymes", "Compounds involved". Banned in the panel: "suggest", "predict", "expected", "likely", "will produce", "might", "may", "could produce", "detected", "present in your batch". Checked by grep on `App.jsx`: the only remaining hits are the pre-existing Recipe salt-suggestion code (`saltSuggestion`, "Suggested salt"), outside the panel. "Compounds involved" is deliberate: it lists every substrate and product of the curated reactions and the response does not say which is which. Never "produced".

**No numbers about the data.** No confidence, score or percentage. Item counts ("Enzymes (5)") are fine.

**Empty and thin states**
- **A list is empty** (organisms exist): "No enzymes recorded in this reference set for the organisms listed above." / "No compounds recorded ...". The heading is plain text ("Enzymes (0)"), not a `<details>`.
- **No organisms at all** (reachable: `POST /cultures` accepts a free-string type): "No reference organisms are recorded for this type. You can attach one." Enzymes and compounds sections are not rendered.
- **Organism with no enzymes** (in no `organism_ids`): "No enzymes recorded for this organism." under that organism, so the gap is visible where it applies.
- **Known-thin default sets** (`THIN_NOTES`, `App.jsx:506`, curation §7 and §8.3):
  - cheese: "Known gap: proteases such as chymosin are not in this reference set yet."
  - garum: "Known gap: fish digestive proteases are not modeled. The default organisms describe koji garum (Aspergillus oryzae is included); traditional garum uses no koji."
  - kefir: "Known gap: some default organisms (Lactobacillus kefiri, L. kefiranofaciens) have no enzymes recorded."

## 2. Layout

Mobile first, single column in the existing `max-w-2xl` main. Rows use `flex flex-wrap` so nothing overflows at 360 px.

```
+--------------------------------------+
| BIOCHEMISTRY                         |
| Reference data for a kombucha batch: |
| not measured ... not a forecast. ... |
|                                      |
| Organisms                            |
| Acetobacter aceti  bacteria          |
|   [type default]                     |
| Saccharomyces cerevisiae  yeast      |
|   [custom]                           |
|   Note: Fermentis SafAle US-05       |
|   [ Remove ]                         |
|                                      |
| Compounds involved                   |
| Acids                                |
| [Acetate KEGG]                       |
| Alcohols                             |
| [Ethanol KEGG]                       |
|                                      |
| > Enzymes (5)                        |
|   alcohol dehydrogenase  EC 1.1.1.1  |
|   Carried by: A. aceti, S. cerevisiae|
| Known-gap note (cheese/garum/kefir)  |
| KEGG is a public biochemistry ...    |
| > What this shows                    |
|                                      |
| [ Add organism ]                     |
+--------------------------------------+
```

- **Organisms** (`App.jsx:~695-745`): italic name, kingdom in `text-slate-400`, badge `type default` (slate border) or `custom` (`text-sky-400 border-sky-500/40 bg-sky-950/40`); text carries the meaning, not colour. Custom rows show the note and the Remove control.
- **Compounds:** chips grouped Acids, Alcohols, Gases, Flavor compounds, Other (`COMPOUND_GROUPS`, `App.jsx:514`); empty groups hidden; unknown categories go to Other. Names as returned. A KEGG link sits in the chip when `kegg_compound_id` is non-null.
- **Enzymes:** `<details><summary>Enzymes (n)</summary>`; row = name, `EC x.x.x.x` in `font-mono` with a KEGG link, then "Carried by: <organism names>" resolved from `organism_ids` against the returned organisms.
- **"What this shows"** (collapsed): compounds are substrates and products of the curated reactions and the data does not say which is which; amylases and proteases have no compound rows (starch and protein are not KEGG compounds); organism names are the widely used pre-reclassification forms; three organisms have no enzymes recorded.
- **Action button:** always "Add organism" (toggles to "Cancel"), `py-3`.

## 3. Attach flow (`attach`, `App.jsx:614`)

1. **Open.** Secondary button (`bg-slate-700`) toggles an inline form; the search box takes focus.
2. **Explain.** "Adds to the default organisms for {type}; it does not replace them."
3. **Search.** `type="search"` with an `sr-only` label (`htmlFor`), `text-base`. Debounced 250 ms, `GET /organisms?q=<trimmed>&limit=20`. Under 2 chars: no request, hint "Type at least 2 letters." A per-effect `AbortController` cancels stale requests. Status line (`aria-live="polite"`): "Searching…", "N organisms found.", or `No organism matching "xx" in the reference set. Only organisms already in the reference set can be attached.`; search errors show in the same line. Enter is suppressed in the search box.
4. **Result row.** Button, `py-3`: italic name, kingdom. Organisms already custom-attached are disabled ("already attached"; the API would 409). Type defaults stay selectable (labelled "type default").
5. **Pick.** Shows the chosen organism plus "clear" (focus returns to the search box). For a default: "Already a {type} default; attaching it records your note and shows it as custom."
6. **Note.** Labelled optional input, max 500 characters, `text-base`, placeholder "e.g. Fermentis SafAle US-05". Enter submits (native form).
7. **Submit.** One POST `{organism_id, notes?}`. Button "Attaching…" while busy. Success: close and reset the form, status "<name> attached." (`aria-live="polite"`), focus returns to the "Add organism" button, panel refetches. Failure: inline `role="alert"` message (`detail` when it is a string, otherwise "Could not attach organism (status)"; `TypeError` -> "Could not reach the server"). The panel refetches after every attempt, so a 409 shows the row that already exists.

## 4. Remove flow (`remove`, `App.jsx:641`)

"Remove" on a custom row becomes "Confirm remove" + "Cancel" (aria-labels name the organism). Confirm sends `DELETE /batches/{id}/organisms/{organism_id}`, status "Custom attachment for <name> removed.", focus moves to the "Organisms" heading (`tabIndex=-1`), then refetch. A 404 shows the `detail` and refetches. Defaults have no Remove control.

## 5. Panel states and data flow

| When | Call |
|---|---|
| Panel mounts (each `loadPreview`) | `GET /batches/{id}/biochemistry` |
| >= 2 chars, 250 ms idle | `GET /organisms?q=<q>&limit=20` |
| Attach | `POST /batches/{id}/organisms` |
| Remove | `DELETE /batches/{id}/organisms/{organism_id}` |
| After attach or remove (success or failure) | `GET /batches/{id}/biochemistry` |

States: initial "Loading biochemistry…"; load failure: message plus **Retry** (`role="alert"`), other cards unaffected; a failed refetch shows the same error above the old data; a refetch keeps old data on screen and swaps on success, so `<details>` open state survives. Requests use `AbortController` (abort on unmount and on the next reload).

## 6. Accessibility and i18n

- Search and note inputs have real labels (`htmlFor`); search label is `sr-only`.
- Status and search results in `aria-live="polite"` regions; errors `role="alert"`.
- `<details>`/`<summary>` for enzymes and the explainer (keyboard and screen-reader accessible without JS).
- Touch targets `py-2` to `py-3`; badges carry text; fine print uses `text-slate-400` (not `text-slate-500`) for contrast on the slate-900 card.
- Focus: search box on open and after "clear"; "Add organism" button after attach; "Organisms" heading after remove.
- KEGG links: `aria-label` includes "opens kegg.jp in a new tab".
- i18n: none exists, none added. English only.

## 7. KEGG URL verification (run 2026-09-25, `curl -sIL --ssl-no-revoke`)

| URL | Result |
|---|---|
| `https://www.kegg.jp/entry/ec:1.1.1.1` | 200, no redirect; page title "KEGG ENZYME: 1.1.1.1" |
| `https://www.kegg.jp/entry/ec:3.2.1.3` | 200, no redirect |
| `https://www.kegg.jp/entry/C00469` | 200, no redirect; page title "KEGG COMPOUND: C00469" |
| `https://www.kegg.jp/entry/C00033` | 200, no redirect |

Both forms resolve as written, so no fallback form was needed. Only these public GETs were sent. Not verified: that every EC number in the curated set has a KEGG ENZYME entry (a missing entry may still return 200 with an error page); the manual script step 1 spot-checks.

## 8. Testing

- **Automated:** none possible today (no runner; CI is build-only). Gate: `cd frontend && npm run build` (passes). Vitest plus Testing Library would be 3+ dev deps; out of scope. Backend behaviour is covered by `tests/test_batch_biochemistry.py` and `tests/test_organisms.py`.
- **Manual script.** Run write steps against a **local backend** with throwaway batches, not production. Local: set `VITE_API_URL` (`frontend/.env.example`); on the Nestlé network use `curl --ssl-no-revoke` for any pre-check of the deployed service.
  1. Kombucha: 3 default organisms with "type default" badges, compounds grouped, 5 enzymes each with "Carried by"; KEGG links open the matching kegg.jp entries (ec: form for enzymes, `C…` form for compounds) in a new tab; the legend line is visible.
  2. Koji: *A. oryzae* only, its enzymes, compounds Maltose, D-Glucose, L-Glutamine, L-Glutamate.
  3. Garum: *T. halophilus* and *A. oryzae* (v3 applied); note says koji garum is the default and fish digestive proteases are not modeled. Cheese: chymosin note. Kefir: kefir note, and *L. kefiri* shows "No enzymes recorded for this organism."
  4. Miso (11 enzymes) at 360 px: rows wrap, no horizontal scroll, `<details>` usable, long organism names wrap.
  5. Provenance line visible with no tap on every batch; nothing reads as a forecast; no banned wording.
  6. Search: 0 and 1 characters send no request (network tab) and show the hint; 2 characters return results; nonsense shows the "No organism matching" message.
  7. Attach with note: on a throwaway kombucha pick a non-default organism (for example *Lactobacillus plantarum*), note "Fermentis SafAle US-05" -> attached as "custom" with the note under it, the 3 defaults still present, "attached." announced, focus on "Add organism"; the organism's enzymes (if any) show it under "Carried by".
  8. Attach a default with a note: pick *S. cerevisiae* on a fresh kombucha batch -> it appears once, badge "custom", with the note; total organism count unchanged.
  9. Remove: on the row from step 8 click Remove -> "Confirm remove"/"Cancel" appear; Cancel restores; Confirm -> the row reverts to "type default" without the note, or (step 7 organism) disappears; defaults have no Remove button.
  10. 409: pick an already-attached organism (row disabled); force a 409 by attaching the same organism from a second tab and confirm the `detail` text appears and the panel refetches.
  11. 404: remove an already-removed attachment from a second tab: `Organism is not attached to this batch` shown, panel refetches. Attaching to a deleted or unknown batch shows `Batch not found`.
  12. Notes over 500 characters cannot be typed (`maxLength`); if forced through the API, the 422 shows "Could not attach organism (422)" (not `[object Object]`).
  13. Type with no defaults: create a culture via the API with a `type` outside the nine (for example `"test"`) and start a batch -> "No reference organisms are recorded for this type. You can attach one.", reduced provenance line, no enzymes or compounds sections; attach an organism -> sections appear.
  14. Network failure: load a batch, then block `/biochemistry` in DevTools and trigger a stage advance: message plus **Retry**, rest of the page works; unblock and Retry loads the data. Offline during attach/remove shows "Could not reach the server".
  15. Edit the batch-id box after loading: the panel sends no requests per keystroke. Advance a stage: the panel remounts and refetches without visible breakage.

## Follow-ups (still open)

| Follow-up | Enables |
|---|---|
| Server-side `known_gaps` per fermentation type | Replaces the `THIN_NOTES` frontend constant. |
| Edit an attachment's note (PATCH) | Today: remove and re-attach. |
| KEGG link descriptions as data (or a KEGG name/definition per entry) | Today the descriptions are generic strings in the frontend. |
| Reactions list `[{enzyme_id, substrate_id, product_id}]` | Label compounds substrate or product. |

## Out of scope

- Ingredient-to-enzyme table (option B); garum fish digestive proteases and cheese chymosin.
- Creating organisms not already in the reference set.
- Predictions, forecasts, confidence or coverage scores.
- Offline caching or any service-worker change.
- French copy (needs a translation source for organism, enzyme and compound names).
- Frontend test infrastructure.

## Decided

1. Attaching adds to the type defaults, never replaces them; no "use only", no replace warning, one POST per attach.
2. Optional note (max 500) included, shown under custom organisms.
3. KEGG links included (enzyme `ec:` form, compound id form) with descriptions and a legend; URLs verified.
4. Remove of custom attachments included, two-step inline confirm; defaults never removed.
5. Panel after Composition, before Timeline; thin-type notes as a frontend constant (cheese, garum, kefir); enzymes collapsed with counts; provenance line always visible; per-enzyme "Carried by".
