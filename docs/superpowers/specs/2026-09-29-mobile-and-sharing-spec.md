# Mobile and sharing: review and recommendations

**Date:** 2026-09-29 · **Branch:** `feat/share-mobile` (from `feat/sourdough-engine`) · **Status:** items 1–2 implemented here; the rest are proposals.

**Goal:** the owner is handing the Levain planner to a baker friend. The friend will use it on a phone, in a kitchen, probably without an account. This spec reviews what the app does today for that setting, and ranks what to build next by value and cost.

## 1. What exists today (audited on this branch)

| Area | State | Gap |
|---|---|---|
| **Install** | `vite-plugin-pwa` (generateSW, `autoUpdate`), `display: standalone`, dark theme colour, `start_url`/`scope` = base path | The only icon is one SVG marked `"any maskable"`. There are no 192/512 PNGs and no `apple-touch-icon` (iOS ignores manifest icons, so the home-screen icon is a screenshot), and there is no `apple-mobile-web-app-*` meta. Using one icon for both purposes means the maskable crop is applied to the "any" icon too. |
| **Offline** | The SW precaches the shell (index.html, JS, CSS, icon, manifest) and uses a `NavigationRoute` fallback to index.html. Google Fonts are stale-while-revalidate. | **No API response is cached.** The planner needs `GET /sourdough/catalog` before it can show the form at all, and every timing comes from `POST /sourdough/plan` (an ensemble model on the server, which can't cheaply move to the client). Offline, or while Render's free tier wakes up, the planner only shows "Loading levain styles…". |
| **Kitchen UX** | 44–56 px targets, 16 px inputs (no iOS zoom), a large tabular headline, and a sticky bottom bar showing peak and bulk. It works at 360 px with no horizontal scroll. | The screen sleeps mid-bake (no Wake Lock). There is no "next step in 2 h 10" countdown. |
| **Notifications** | Server-side `reminders` rows are computed on stage changes (`reminders.py`), and ARCHITECTURE promises push for critical reminders. | Nothing sends a reminder to a phone. |
| **Sharing** | None before this branch. ARCHITECTURE says "no sharing without explicit opt-in". `cultures.born_from` and `status: shared` exist in the model. | `POST /cultures` accepts **any** `born_from` UUID, including other owners' cultures, with no check. The `born_from` FK has no `ON DELETE`, so once a friend's culture points at the giver's, the giver's `DELETE /me` fails on Postgres. |
| **Accounts** | Every visitor gets an anonymous Supabase session (`auth.js`). `owner_id` = JWT `sub`. `/me/export` and `DELETE /me` exist. | There is no way to claim the account. The session lives in localStorage, so the friend loses every batch and learned starter when storage is cleared, in private mode, on a new phone, or under **Safari ITP (script storage wiped after 7 days without a visit, for sites not added to the home screen)**. A weekly baker hits that last one. |

## 2. Recommendations, ranked

Value is for the baker friend. Cost is S (< ½ day, frontend only), M (backend + migration) or L (M + modelling or infra).

| # | Item | Value | Cost | Backend | New dep | Order |
|---|---|---|---|---|---|---|
| 1 | **Share a plan by link** (`#/levain?p=`) | High: this is how the owner hands the friend a plan | S | no | no | **done** |
| 2 | **Add to calendar** (.ics with alarms) | High: "levain peaks at 06:40" rings with the phone asleep | S | no | no | **done** |
| 3 | **Claim the account** (anonymous → email) | High: protects everything else | S | no (Supabase config) | no | next |
| 4 | **PWA polish**: icons, cached catalog + last answer, Wake Lock | Medium-high | S | no | no | 4 |
| 5 | **`born_from` hygiene**: validate ownership, `ON DELETE SET NULL` | Prerequisite for 7 | S | yes (migration) | no | 5 |
| 6 | **Share a bake read-only** (token link) | Medium | M | yes | no | 6 |
| 7 | **Gift a starter** (lineage inherits learned kinetics) | Medium now, high once bakes are logged | L | yes + model | no | 7 |
| 8 | **Web Push** for tracked batches | Medium | L | yes + scheduler | `pywebpush` | only if 6–7 get used |
| – | Capacitor store app | Low for one friend | L+ | – | many | **no** |

### 2.1 Share a plan by link (implemented)

- **Format:** `<origin><base>#/levain?p=<base64url(JSON {v:1, plan})>`. `plan` is the API plan contract (engine spec § 3), not the form's internal state, so links survive form refactors. It is about 600 characters for a full levain, dough and retard plan.
- **Privacy:** the plan sits in the URL fragment, so it never reaches GitHub Pages or Render logs. It holds recipe numbers only: `culture_id` is nulled, and there is no start time, name, `?batch=` or account id.
- **Untrusted input:** `decodePlan` rejects anything that isn't base64url, strict UTF-8, JSON `{v:1, plan:object}`, or ≤ 4000 characters. `cleanPlan` keeps only known keys and nulls non-finite numbers. It checks enums and keeps only catalog flours. Unknown styles fall back to the default. Range errors are left to `formToPlan`, so a bad value shows up as a highlighted field rather than a crash.
- **UX:** on the receiving side the plan replaces the form once, shows "Opened a shared plan", then rewrites the URL to `#/levain`, so a reload keeps the friend's own edits. The friend picks their own feed time. The sender uses the Web Share API, falling back to the clipboard, then to a read-only field to copy from.

### 2.2 Notifications: .ics now, Web Push later, no store app

| Option | Fires with phone asleep | Updates when readings move the forecast | Cost | Verdict |
|---|---|---|---|---|
| **.ics export** (done) | yes (calendar app) | no (static snapshot; re-export updates events on the same feed time via a stable UID) | S, pure client | **Ship.** Right for the planner, where the plan is a one-off forecast. |
| Local notifications (Notification API / SW `showNotification`) | **no**: the web has no scheduled local notification (Notification Triggers was abandoned), so it only fires while the page or SW is alive | – | S | Not viable alone |
| **Web Push** | yes | yes (reschedule on every reading) | L: VAPID keys, a subscriptions table, and a scheduler (Render free tier sleeps, so it needs an external cron or a paid worker). iOS only supports it for home-screen PWAs (16.4+). | Later, for **tracked batches**, where "your levain now peaks at 07:10" is the real differentiator |
| Capacitor app | yes (LocalNotifications) | yes | L+: $99/yr Apple + $25 Google, two store pipelines, review, same WebView | Not justified. Revisit only if iOS push without install, or widgets, become essential. A Play-Store TWA (Bubblewrap) is the cheap middle ground if store presence is ever wanted. |

The .ics events are the levain/pre-ferment peak, "Mix the dough" (only when it differs from the peak), bulk done and into the oven. Each is 15 min long with a `VALARM` 15 min before. The description carries the likely range ("Likely between 04:30 and 09:00", from the p05–p95 band; omitted when the band is open-ended) and the "watch the dough" caveat. Times are UTC, which is unambiguous and shown in the calendar's own zone. Text is escaped and folded to 75 octets per RFC 5545. Known limits: Google Calendar import ignores `VALARM` (it uses the calendar's default reminders), and iOS Safari's handling of a downloaded .ics should be checked on a real iPhone.

### 2.3 Claim the account (next)

`supabase.auth.updateUser({ email })` turns the anonymous user into a permanent one **with the same `sub`**, so `owner_id` doesn't change and no data migration is needed. The friend confirms by magic link or OTP. On a second device, `signInWithOtp` restores the account (that device's own throwaway anonymous session is dropped). Work: a "Keep my bakes: add your email" prompt after the first tracked bake (not before), Supabase redirect URLs for the GitHub Pages base path, email templates, and CAPTCHA/rate limits on anonymous sign-ins. Also nudge the friend to install to the home screen, which exempts the app from Safari's 7-day wipe. A bonus: the export in `/me/export` makes a claimed account portable.

### 2.4 PWA polish (all S, frontend only)

1. **Icons:** rasterise `icon.svg` once to `icon-192.png` and `icon-512.png` (`purpose: any`), add a padded `icon-maskable-512.png` (`purpose: maskable`) and a 180 px `apple-touch-icon`, plus `apple-mobile-web-app-capable`/`-title` meta. Commit the PNGs, with no build-time dependency.
2. **Offline planner:** a workbox `runtimeCaching` rule for `GET …/sourdough/catalog` (NetworkFirst, 3 s timeout), so the form opens offline and during cold starts. Also keep the last `POST /sourdough/plan` answer in localStorage, keyed by the plan JSON, so the timings on screen survive the kitchen Wi-Fi dropping. The Cache API can't store POST requests, so this has to be app-level.
3. **Keep the screen on:** a "Keep screen on" toggle using `navigator.wakeLock.request("screen")` on the planner and batch pages, re-acquired on `visibilitychange`. It is supported on Chrome/Android and Safari 16.4+. Check home-screen mode on a real iPhone.
4. **Glanceable next step (optional):** on a tracked batch, one line such as "Peak in 2 h 10 (06:40)". The planner has no "now", so it stays with clock times.

### 2.5 Share a bake read-only (backend)

- **Use a signed share token, not a public flag.** A `public` flag turns the batch UUID into the capability, and UUIDs leak (the app writes `?batch=<id>` into the URL). A flag also can't be revoked without changing the id, and it allows only one link. A stateless signed JWT link can't be revoked without a denylist, which is state anyway.
- **Design:** a `share_links` table (`token` = 128-bit random, url-safe; `kind` batch|gift; `target_id`; `created_by`; `created_at`; `expires_at`; `revoked_at`) with CASCADE from batch and culture. Endpoints:
  - `POST /batches/{id}/share` (owner only)
  - `DELETE /share/{token}`
  - `GET /shared/{token}` (no auth), which returns a **projection**: plan, forecast bands, readings and stage times. It never returns notes, photos, culture name (unless opted in), owner id or batch id.
- **GDPR:** sharing is explicit opt-in per link. Tokens are covered by `/me/export` and erased by `DELETE /me` (and by the cascade). The viewer needs no account, and nothing about the viewer is stored. An anonymous-account sender who loses their session can't revoke the link, which is one more reason to do 2.3 first.
- **Cost risk:** an unauthenticated endpoint that runs the ensemble forecast. Serve the last computed prediction for the batch (cache it on write), and rate-limit per token.

### 2.6 Gift a starter (lineage inherits kinetics)

**Today:** learning is `θ = g + d_style + a_baker + e_starter + ε`, with variances (0.30, 0.20, 0.10, 0.30, 0.10), in `prediction/population.py`. `e_starter` is keyed on `culture_id`. A gifted culture has a new id, so it starts from `e_starter = 0` and inherits only the style class and **the recipient's** baker effect. None of the giver's starter evidence carries over.

**Proposal:** a crossed **lineage** effect, splitting the starter variance:

$$\theta_b = g + d_{k(b)} + a_{j(b)} + \ell_{L(b)} + e_{s(b)} + \varepsilon_b,\qquad v_\ell = 0.20,\; v_s = 0.10$$

- The variances still sum to 1, so with no data the prior is still exactly the literature prior. A single, never-gifted starter behaves exactly as today, because its lineage and starter labels coincide, so $v_\ell + v_s = 0.30$ acts as one effect.
- A gifted child shares $\ell$ with its parent. Its prior correlation with the parent's starter-level deviation is $v_\ell/(v_\ell+v_s) = 2/3$, not 1. A community moved to a new kitchen, flour and feeding regime drifts. The recipient's kitchen enters through $a_j$, and the child's own bakes then move $e_s$.
- **Code:** one more `("lineage", "lineage", lineage)` term in `predictive()`, plus a `lineage` label on evidence rows. The same exact Gaussian conditioning applies, so nothing is double-counted. $v_\ell$ stays fixed (est.) until the REML script has at least 3 multi-member lineages. Validate on synthetic data first, by recovering the 2/3 correlation.
- **Data:** `cultures.lineage_id` = the parent's `lineage_id` at adoption, else the culture's own id. It is not an FK, so the lineage survives the parent's deletion. Evidence rows get their lineage by joining cultures. The migration **must backfill `lineage_id = id`**. `_labels()` treats a missing label as a group of one row, which would silently weaken same-starter pooling from 0.30 to 0.10.
- **Flow:** the giver creates a `share_links` row of `kind = gift` (single-use, 7-day expiry). The recipient calls `POST /cultures/adopt {token}`, which creates their culture with `born_from` and `lineage_id` and marks the token used. Raw cross-owner `born_from` is rejected (item 5).
- **Privacy/GDPR:** the recipient's forecast is shaped by the giver's kinetic evidence (numbers only, as the style class already is). When the giver runs `DELETE /me`, their evidence rows are erased, so the recipient's inherited information disappears and their forecast widens. That is the correct outcome for erasure. The UI should say "inherits what <giver's starter> taught the app" only with the giver's consent at gift time.
- **When it pays off:** only after the giver has finished bakes with readings. Until then the gift is a naming/genealogy feature.

## 3. Risks and open points

- **Losing the anonymous session** is the biggest risk for the friend. Do 2.3 before any feature that accumulates data.
- **Router merge:** `feat/product-track-v1` resolves pages with `hash.slice(2)`, which turns `#/levain?p=…` into `levain?p=…`. When that branch absorbs the planner, strip `?…` before the page lookup (one line). This branch matches with `/^#\/levain(\?|$)/`.
- **Link stability:** `v:1` links must keep decoding. `cleanPlan` ignores unknown keys and `formToPlan` re-validates ranges, so additive plan-schema changes are safe. Bump `v` only for breaking changes.
- **Share links are durable and forwardable:** the link carries no personal data, but anyone with it can open the recipe. That is the intent.
- **`born_from`:** it is unvalidated and its FK blocks deletes (§ 1). Fix this before any gift feature.
- **Supabase anonymous users count toward MAU** and can be abused without CAPTCHA.

## 4. Implemented on this branch

- `frontend/src/sourdough/share.js`: `encodePlan` / `decodePlan` / `cleanPlan` / `sharedForm` / `shareUrl`, plus `planEvents` / `buildIcs` / `icsText` / `foldLine`. Pure, with no new dependency.
- `frontend/src/sourdough/share.check.mjs` (`node src/sourdough/share.check.mjs`) covers:
  - the form → link → form round trip, including poolish;
  - `culture_id` being stripped and the link shape;
  - 13 malformed inputs, plus a hostile but well-formed plan;
  - event derivation: the peak = mix merge, and no range claimed on an open band;
  - .ics CRLF, UTC stamps, UID, escaping, and 75-octet folding of multi-byte text and emoji (round-trips on unfold).
- `Planner.jsx`: a "Share and remind" section (Share this plan, Add to calendar; calendar is disabled while timings are updating or failed), and restore from `#/levain?p=` on load and on in-app hash change.
- `App.jsx`: the planner route matches `#/levain` with or without a query (one line).
