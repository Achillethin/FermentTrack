# Frontend Design-System Pass — Shared Components, Visual Consistency, Mobile

**Date:** 2026-09-25
**Status:** DRAFT — spec only, not implemented
**Builds on:** the recipe-editing/batch-search work merged in PR #4 (`GET /batches`, `PATCH`/`DELETE /batches/{id}/ingredients/{row_id}`, `BatchPicker`, `RecipeRow`)

## Problem and goals

`frontend/src/App.jsx` is one file (~950 lines after PR #4) with no shared UI primitives. Every input/select/button repeats the same Tailwind class string by hand (`"rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"` appears ~20+ times). There's no visual identity beyond default Tailwind slate/emerald, no consistent spacing rhythm, weak loading/empty states, no accessibility labelling, and the form rows (qty/unit/role selects in `Recipe`/`RecipeRow`) haven't been checked at phone width.

Goals:
1. Extract shared `Input`, `Select`, `Button` (primary/secondary/danger variants) components — kill class-string duplication.
2. Apply them consistently across all forms (`NewBatch`, `LogObservation`, `Recipe`/`RecipeRow`, `BatchPicker`).
3. Fix accessibility gaps: every input gets a label (visually-hidden is fine), replace color-only urgency coding in `Safety` with an icon/text marker too.
4. Verify and fix mobile layout (375px viewport) for the `Recipe`/`RecipeRow` form rows and `BatchPicker` filter row, which currently `flex flex-wrap` several fixed-width controls.
5. (Optional, lower priority) Split `App.jsx` into `components/*.jsx` files.

Non-goals: no new features, no behavior changes, no new dependencies (stay on Tailwind, no component library). No change to the API surface — this is presentation-only.

## What exists (verified 2026-09-25, post PR #4)

- **File:** `frontend/src/App.jsx`, single file, React 18 + Tailwind, no router, no state library.
- **Components already present:** `Card` (title + children wrapper, `App.jsx` — the only existing shared primitive), `RecipeRow` (edit/delete, added in PR #4), `BatchPicker` (search/filter/pick, added in PR #4), `NewBatch`, `LogObservation`, `Recipe`, `Composition`, `Timeline`, `Safety`, `StageControl`, `BatchHeader`.
- **Repeated class strings (candidates for `Input`/`Select`):**
  - Text input: `"w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"` and the narrower `"... px-2 py-2 text-sm"` / `"... px-2 py-1 text-sm"` variants — in `NewBatch`, `LogObservation`, `Recipe`, `RecipeRow`, `BatchPicker`.
  - Select: same border/bg pattern, used for substrate, unit, role, outcome dropdowns in the same components.
  - Primary button: `"rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"` (submit buttons) and a smaller `px-2 py-1 text-xs` variant (`RecipeRow` Save).
  - Secondary/neutral button: `"rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-medium hover:bg-slate-600"` (`StageControl`, `RecipeRow` Cancel, `BatchPicker`'s manual-ID Load).
  - Danger text button: `"text-xs text-red-400 hover:text-red-300"` (`RecipeRow` remove).
- **No labels:** every input/select relies on `placeholder` only; no `<label>`/`aria-label` pairing anywhere except one bare `<label>` in `NewBatch` with no `htmlFor`.
- **Color-only signal:** `urgencyColor()` in `App.jsx` maps urgency → Tailwind color classes only (text/border/bg), no icon or text prefix distinguishing critical/high/medium/low beyond the color and the word itself already in `v.action`/`reason_text_en` — check whether the action word is always visible before adding a marker.
- **Viewport not yet checked:** `Recipe`'s add-ingredient row (`ingredient select` + `qty input` + `unit select` + `Add button`) and `RecipeRow`'s edit row (`qty` + `unit` + `role` + `Save`/`Cancel`) both use `flex flex-wrap gap-2` with several `w-20`/`w-24`/`min-w-[9rem]` fixed-width children — likely wraps into a cramped 2-3 line stack at 375px. `BatchPicker`'s filter row (search input + substrate select + outcome select) has the same shape.
- **Build:** `npx vite build` from `frontend/` is the check; no visual regression tooling (no Storybook/Chromatic), so verification is manual (dev server + browser resize, or Playwright screenshots at a phone viewport as done for PR #4).
- **Tests:** none on the frontend (`package.json` has only `dev`/`build`/`preview`). This pass doesn't need to add any — it's presentation-only — but should not break the `vite build`.

## Decisions (proposed)

| Question | Proposed decision | Rejected, and why |
|---|---|---|
| Where do shared components live? | New `frontend/src/components/ui.jsx` exporting `Input`, `Select`, `Button` | Splitting into one-file-per-component is more churn than a ~950-line app needs right now |
| Component API | `Button` takes `variant="primary"|"secondary"|"danger"` + standard button props; `Input`/`Select` take `label` (for accessibility) + standard input/select props, forwarding `className` for one-off width overrides (`w-20`, `w-24` etc. stay as call-site overrides) | A fully-themed design-token system (CSS variables, dark/light mode) — out of scope, this app is dark-only today and the ask was consistency, not a theme system |
| Label style | Visually-hidden (`sr-only`) label by default; only render visibly where there's already a visible label pattern (e.g. `NewBatch`'s "Existing culture") | Always-visible labels — would visually bloat the compact rows (qty/unit) that currently rely on placeholder-as-label |
| Mobile fix approach | Change fixed-width (`w-20`, `w-24`) qty/unit controls to flex-basis with `min-w-0` and let the row wrap onto two lines cleanly at narrow widths, rather than forcing single-line | Redesigning these forms as stacked/vertical on mobile — bigger change, not needed if wrapping is clean |
| Urgency color-only fix | Prefix each `Safety` verdict with the action word already in data (`v.action`, e.g. "CRITICAL:") in bold, ahead of `reason_text_en` | Adding icons — needs new dependency or hand-drawn SVG set for 4 states, more effort than the ask needs |
| Split `App.jsx` into files? | Defer — call out as a follow-up, not required for this pass | Doing it now risks a much larger diff than "design pass" implies; do it as its own PR if wanted |

## Work breakdown (in order)

1. **`frontend/src/components/ui.jsx`** — `Input`, `Select`, `Button` components per the API above. Export `ROLES`/shared constants stay where they are (`App.jsx`) unless moved for reuse.
2. **Swap-in pass** — replace every raw `<input>`/`<select>`/`<button>` in `NewBatch`, `LogObservation`, `Recipe`, `RecipeRow`, `BatchPicker`, `StageControl` with the shared components. No behavior change — same `value`/`onChange`/`disabled` props, same class-string results (verify via visual diff, not just "compiles").
3. **Accessibility labels** — add `label` prop (sr-only) to every swapped `Input`/`Select` describing its purpose ("Ingredient quantity", "Search batches by culture name", etc.).
4. **Safety urgency fix** — prefix verdict text with the action word in `Safety` (`App.jsx`).
5. **Mobile check** — run `npm run dev`, resize to 375×800 (or reuse the Playwright pattern from PR #4: `chromium.launch({executablePath: '/opt/pw-browsers/chromium'})`, `viewport: {width: 375, height: 800}`), screenshot `Recipe`, `RecipeRow` (in edit mode), and `BatchPicker`; fix any row that overflows or clips.
6. **Verify:** `npx vite build` clean; manual click-through of add/edit/delete ingredient and batch search on both a 500px and 375px viewport (repeat the PR #4 Playwright smoke test: search → open batch → edit qty → remove ingredient) to confirm no regression from the component swap.

## Open questions

- **OQ1:** Should `Button`'s `danger` variant be a solid red background (matches `primary`'s solid-emerald weight) or stay as a text-only link style like today's "remove"? Proposed: keep text-only for inline row actions (matches current low-emphasis feel), add a solid variant only if a future full-width danger button is needed.
- **OQ2:** Split `App.jsx` into `components/*.jsx` — do now as part of this pass, or as a separate follow-up PR? Proposed: separate PR (see Decisions table) — flag to the user before starting if they want it folded in.

## Test plan for whoever implements this

- [ ] `npx vite build` — clean build, no new warnings
- [ ] Manual/Playwright smoke test at 500px width: start a batch, search for it via `BatchPicker`, log an observation, add/edit/remove a recipe ingredient — all still work post-swap
- [ ] Same smoke test at 375px width — confirm no clipped/overlapping controls in `Recipe`, `RecipeRow` (editing state), `BatchPicker`'s filter row
- [ ] Visual check that swapped components render identically to before (same colors/spacing) — this is a refactor, not a redesign
