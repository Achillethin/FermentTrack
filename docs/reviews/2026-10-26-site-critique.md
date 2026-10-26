# FermentTrack: site critique, 2026-10-26

**Method.** I used the local app (same code as production, local SQLite) at 1366 px and 390 px, read the frontend code, and ran one read-only probe of `safety/service.get_safety_report` with synthetic batches. Screenshots are in `.playwright-mcp/critique/`. Another session took over the shared Playwright tab, so most of the walk-through ran in my own headless Chromium (en-GB, Europe/Paris). I did not touch any other tab.

The local database now holds these test leftovers:
- pH 15 on "Brined carrot with garlic";
- a new batch, "Brined cabbage and carrot with garlic", started from Ideas, with a pH reading of "5,8" that was saved as 5 and two notes.

Effort: **S** < ½ day, **M** 1–3 days, **L** > 3 days.

---

## 1. Verdict

A beginner would come back tomorrow once, to log the pH that Today shouts about, and then stop. These are the reasons:
- The green "All safety checks passed." banner is shown no matter what you do, so it tells you nothing.
- The pH field silently turns "5,8" into 5, and a wrong reading can never be removed.
- The app recommends a recipe, then its own forecast says the recipe will fail the app's own "≤ 4.6 in 48 h or discard" rule.
- The answer to "I have cabbage, garlic and carrot" is hidden behind a toggle labelled *Experimental*.

The modelling under all of this is serious and honest. The product on top of it explains the model and forgets to tell you what to do next.

---

## 2. The 10 fixes that matter most

### 1. The safety banner is wrong by construction · **P0 · S–M**
- **What is wrong.** The batch page says "All safety checks passed." on a lacto batch with no pH reading at day 1.8, while Today, for the same batch, says "Log pH by 48 h … if not, discard · critical". In `safety/service.py`:
  - `time_hours` is measured to the *last reading*, not to now. With no readings it is 0, so GEN-001 ("No pH reading after 24h") can never fire.
  - The `grounded()` filter drops any rule that mentions an unmeasured variable. That removes GEN-001 again (it mentions `ph`), and it removes BOT-002 unless the user logged a separate *temperature* reading. The batch's own `expected_temperature_c` is ignored.
  - BOT-001 needs a `salt_pct` measurement, and the Log form cannot record one.
- **What the probe returned.** Every case below came back "safe":
  - no readings, day 5;
  - pH 5.5 at 60 h with no temperature reading;
  - pH 15.
  
  The only hard stop I could trigger needed a manually logged temperature.
- **Why it matters.** This hits audience 1, the people least able to judge a ferment themselves. A green tick next to "discard if not ≤ 4.6" teaches them to ignore both.
- **Fix.**
  - Compute `time_hours` from `max(now, last reading)`.
  - When no temperature was logged, use `batch.expected_temperature_c` and, failing that, the recipe temperature.
  - Use the recipe's salt % for `salt_pct`.
  - Exempt rules whose condition *is* "ph == None" from the grounded filter.
  - Replace the binary banner with three states:
    - amber "No pH yet: measure by Wed 14:00";
    - green "On track: pH 4.3 at 40 h";
    - red "Stop: …".
  - Add one `test_*` that covers the five probe cases above.

### 2. Readings: no validation, comma decimals truncated, no undo · **P0 · S (front end) + M (edit/delete)**
- **What is wrong.**
  - Log tab → "Log observation" → pH → "15" is accepted and shown as "pH: 15" in History and in the Logbook.
  - "5,8" is saved as **5**: the code calls `parseFloat("5,8")` (BatchView.jsx:212). The owner's own browser runs in a French locale.
  - There is no edit or delete for measurements (no route exists), no "measured at" field, and no confirmation after saving.
  - The forecast then warns "1 of your readings (pH 5 at 0 h) fall outside what the model can explain … Check those readings". You check them, and there is nothing you can press.
- **Why it matters.** This hits every audience. One typo permanently corrupts both the calibration and the safety status.
- **Fix.**
  - `inputMode="decimal"`, then `value.replace(",", ".")`.
  - Range checks per type: reject pH outside 0–14, and ask "pH 2.1? Most ferments sit at 3–7. Save anyway?" outside 3–7.
  - After saving, show a toast "Logged pH 5.8 · Undo".
  - Add `DELETE`/`PATCH /batches/{id}/measurements/{mid}` and a "⋯" button on each History row.
  - Add an optional "Measured at" field that defaults to now.

### 3. The app contradicts itself on its own recipe · **P0 · M**
- **What is wrong.**
  - Ideas serves the composed card "Brined cabbage and carrot with garlic", which says "Taste from 21 days · Peak 25 days · Stop by 42 days".
  - Start the batch, and its forecast says "pH below 4.6 in ~3.8 days, 90 % range: 2–8.6 days" and "Tangy phase in ~2.4 days".
  - Meanwhile the card, the Log tab and Today all say "It must reach ≤ 4.6 within 48 h at > 10 °C; if not, discard."
  - So the model predicts that roughly 95 % of batches of the app's own recipe fail the app's own discard rule. The card and the batch also disagree by about 18 days on when to taste.
  - The kimchi card collapses to "Taste from 3 days · Peak 3 days · Stop by 3 days" with "modelled acidification (P90) not reached within the forecast". Section 1 of the spec already knows that only 1–11 % of kimchi members reach pH 4.6 by 72 h.
- **Why it matters.** This hits audience 1. A beginner who follows the app exactly will be told to throw out a normal jar of brined carrots.
- **Fix.**
  - One source of truth per batch: the Ideas card shows the same milestones as the batch forecast at the same temperature, and states the documented duration as "NCHFP: 3–4 weeks".
  - Put **P(pH ≤ 4.6 by 48 h)** on every lacto card and batch. If it is below 0.5, say so in words.
  - Then decide with a source which side is wrong: the model's acidification rate, or the rule's wording for properly salted (≥ 2 %) vegetable ferments. Do not loosen the rule without a citation; BOT-002's ANSES reference currently has an empty `source_url`.
  - Either way, the reminder needs a decision path, not just "discard". For example: "Still above 4.6 at 48 h? Check salt ≥ 2 % and that everything is under the brine, measure again at 72 h; discard if still above 4.6 at day X, or if there is pink or slimy growth."

### 4. The pantry-first answer is hidden by default · **P0 · S**
- **What is wrong.** On Ideas, with Cabbage + Garlic + Carrot and the default "Proven" mode, you get:
  - "Dry-salted sauerkraut", which uses 1 of your 3 ingredients;
  - "Napa-cabbage kimchi", with "To buy: Napa cabbage, Chilies, Radish, Fresh ginger, Onion".
  
  The recipe composed for exactly what you have only appears in "Experimental" or "Both", labelled "Experimental · model-guided changes, untested". The mode hint even describes something else: "up to 3 changes to a recipe…". Release 2's exit criterion ("carrot + garlic returns brined carrots with garlic") passes in the API and fails in the UI.
- **Why it matters.** This is audience 1's first question, and it is the reason the app exists.
- **Fix.**
  - Rank across sections by pantry coverage, as V7 in the spec says. A composed recipe that covers 3 of 3 goes first, whatever the mode.
  - Give composed recipes their own label: "Made from what you have · standard 2.5 % brine (NCHFP, UMN)" rather than "Experimental".
  - Put a coverage line on every card: "Uses cabbage, carrot, garlic ✓ · nothing to buy".
  - Collapse the search form into a one-line summary once results are shown; today the results start below the fold on desktop.

### 5. The batch page buries the one action that matters · **P0/P1 · M**
- **What is wrong.**
  - The page opens on Forecast, three stacked disclaimers deep.
  - The Log tab opens with a full "Tasting" form (aroma picker, "How much did you like it?", "Would you make it again?") on day 0. The pH field sits below it, under "Log an observation".
  - Today's "Log pH by 48 h" card has a "Done" button that dismisses the reminder **without logging anything**.
  - Logging a pH does not close that reminder; Today still showed it "due in 5h · critical" after I logged one.
  - After logging, the whole page blanks to "Loading batch…" and, on a phone, jumps from scrollY 1260 to 0, with no confirmation.
- **Why it matters.** This hits audiences 1 and 2. "Come back tomorrow, log a pH, see what changed" is the core loop, and it currently takes four taps plus a scroll, and loses your place.
- **Fix.**
  - Add a sticky quick-log strip under the header on lacto and levain batches: `pH [ 4.8 ] Log`, or `Rise % [ ] Log` for levain.
  - On Today, replace "Done" on a pH reminder with an inline pH field. A reading closes the safety reminder on the server.
  - Collapse the tasting form until the taste window opens; until then show "Tasting opens around Wed".
  - Keep the old `preview` on screen while reloading (no `setPreview(null)`), and show "Logged pH 4.8".

### 6. Stages are friction, and "discard" is a dead end · **P1 · S–M**
- **What is wrong.**
  - Lacto starts in "prep and salt", which lasts 1 h (stages.py). Nothing advances it. The batch I found had sat at "Prep And Salt · 1.8 d in this stage" with "salted/brined — ensure vegetables stay fully submerged to avoid mold · ! overdue by 41h · medium" on Today. "Done" on that reminder does not advance the stage.
  - "Advance to next stage" doesn't say what the next stage is, has no confirmation and no undo, and is a 28 px button directly above the equally small "Repeat this batch", which creates a new batch in one click.
  - There is **no way to mark a batch failed or discarded**, although the app tells you to discard and Batches has a "failed" filter. Reaching "ready" sets the outcome to success.
- **Why it matters.** This hits audience 1. A mouldy jar either stays "in progress" forever, haunting Today, or gets recorded as a success.
- **Fix.**
  - Auto-advance prep → ferment when the batch starts, or when that reminder is ticked. Reword the reminder as a check: "Is everything under the brine? ✓".
  - Rename the button "Fermenting → Move to fridge (finish)".
  - Add "Discard this batch…" with reasons (mould, slime, pH not dropping, smell) that sets `outcome = failed`.
  - Ask for confirmation before Repeat, or move it into the finished state.

### 7. The levain planner answers the wrong question · **P1 · M**
- **What is wrong.**
  - "I want it ready by" is a bare time field in the fourth card, after microbiology ("Mostly S. cerevisiae with L. plantarum and L. brevis (a 500-starter survey)").
  - Enter 08:00 tomorrow and it says: "Feed at 09:20, ready by Tue 08:00: use 1:10:10 (peaks around Tue 03:00). None of these lands within 1.5 h … a warmer or cooler spot shifts them all." The obvious answer, "feed at about 15:00 at 1:5:5", is never offered.
  - The headline "Levain peaks at **Tue 01:20**" is set in 2.5 rem type over "likely between 19:20 and Tue 11:30", a 16-hour band.
  - The chart's "yours" row for the same 1:5:5 feed says "Tue 00:50 · 19:30–Tue 13:50".
  - At 24 °C, 1:1:1 is shown peaking 12 h after the feed. Most bakers expect about 4–6 h, and spec section 1 row 5 already admits the model is 1.5–2× slow.
  - Pro details say "At the levain peak … pH 5.83 … Rise 0 %", while the chart shows about 120 % rise and pH ≈ 4.5 at that hour.
  - The dough plan says "Mix at Tue 01:20" (in the middle of the night) and "Bulk done at Tue 11:20", 10 h at 25 °C with 20 % levain, while the timeline bar says "Tue 01:20 → Wed 15:20 · 38 h".
- **Why it matters.** This hits audience 2. A baker checks the first number against their own starter once. If it is off by 2×, they never return.
- **Fix.**
  - Lead with: "Ready by [date + time]", "I can feed between [20:00]–[23:00]", "my kitchen is [21] °C". Solve for feed time × ratio and answer: "Feed at 21:40, 1:5:5". Even before release 4, that is a grid search over the chart you already compute.
  - Until the levain xfail passes, print the bakers' rule of thumb next to the model ("most starters: 4–6 h at 1:1:1, 24 °C") and ask for one logged rise to calibrate.
  - Make the headline and the chart row come from the same call.
  - Fix the "at the levain peak" readout, which appears to read the dough at mix time.
  - Flag dough steps that fall between 23:00 and 06:00.

### 8. Internal state and jargon leak into the UI · **P1 · M**
- **What is wrong.**
  - Raw enums and casing: "lacto_ferment" (Batches list, start form, Biochemistry intro, Logbook filter), "Prep And Salt", "stage-change".
  - Domain words that mean nothing to a home fermenter: "substrate", and "Existing culture / — start a new culture —" for what is just a jar of carrots.
  - Model and data internals: "LOW RES", "P90", "single-value source, widened", "reached in 50 % of model runs", "× detection threshold in water · log scale", "Not calibrated yet: 0 of 30 tasted batches", "Search all USDA foods…", "shape now (aliquot jar)".
  - Catalogue notes shown on recipe lines: "Chilies flavoring · dried powder booked as fresh chili: dry matter understated several-fold" and "Salted shrimp … not in the catalogue yet: Start batch skips it".
  - Roles glued to names: "Salt additive", "Starter/cheese culture starter".
  - Citation keys printed instead of sources: "Sources NCHFP-sauerkraut, Morton-salt, NIST-conversions".
- **Why it matters.** Audience 1 feels stupid. Audience 3 can't tell a defect from a feature.
- **Fix.**
  - Run every enum through `humanize()` plus sentence case, in one place.
  - Rename "culture" to "What are you fermenting?" for lacto, and keep "starter / SCOBY / grains" for the types that really have one.
  - Move catalogue and model internals into the existing "How far to trust this" disclosure.
  - Turn source keys into titled links.
  - Replace "reached in N % of model runs" with "likely / maybe / unlikely within the window".

### 9. Disclaimer fatigue, and uncertainty that doesn't help you decide · **P1 · S**
- **What is wrong.**
  - Before the first number, the forecast shows a "Model estimate" badge, "Not calibrated yet: literature values only", a second sentence about the literature, a bordered paragraph ("Model estimate from literature kinetics… real batches vary more… Never use this to decide food safety… not yet been validated"), then "In the jar · model estimate" and "Next milestone · model estimate".
  - Every Ideas card repeats the same orange Safety box and "Model-guided idea · model estimate, not validated" right above "Model confidence: established".
  - "fresh (probably)" and "sour (likely)" are hedges with no scale.
- **Why it matters.** This hits all audiences. Say something six times and it gets read zero times, including the one sentence that matters ("measure pH").
- **Fix.**
  - One disclaimer per page, placed once at the top, with a "How sure?" chip that opens the details.
  - Phrase intervals as actions: "Check pH on Wed or Thu", not "90 % range: now to 6.1 days".
  - Show the per-card safety line only when it differs from the type default.
  - Rename "Model confidence: established" to "Kinetics from published studies", so it stops contradicting "not validated".

### 10. Navigation and first run point the wrong way · **P1 · S–M**
- **What is wrong.**
  - Seven tabs plus an "Export CSV" button. On a 390 px phone the nav wraps to two rows and takes about 150 px.
  - "Planner" doesn't say it is about bread.
  - "Compare", and "Logbook" next to the batch's "Log" tab and "History" card, give three names for one concept.
  - First run: Today's empty state, "Start a batch in 30 seconds", links to Batches. That form defaults to **kombucha** and asks about "culture", "substrate" and a "Target (optional)" that is never explained. Neither Ideas (audience 1) nor the levain planner (audience 2) is offered.
  - The levain page drops the main nav for a "← FermentTrack" link.
- **Why it matters.** The first 30 seconds decide whether any of the three audiences gets through the door.
- **Fix.**
  - Use four tabs: Today · Batches · Ideas · Levain. Move Compare into Batches ("compare two"), Logbook into Batches ("All activity"), and Export into Account.
  - Make the empty Today offer three doors in the owner's order:
    - "What can I make with what I have?" → Ideas
    - "When should I feed my starter?" → Levain
    - "Track a jar I've already started" → Batches, with lacto preselected
  - Default the start form's type to lacto, and keep the main nav on the levain page.

---

## 3. Findings by area

### First-run and navigation
- The PWA manifest says "Batch journal and smart reminders for **serious** fermenters". That is the opposite of audience 1. → "Know what to make, when it's ready, and that it's safe." **P2·S**
- `document.title` is "FermentTrack" on every route, so tabs, history and screen readers can't tell pages apart. → Set the title per route ("Brined carrot · FermentTrack"). **P2·S**
- There is no "New batch" button on Today once you have a batch; you must go to Batches and scroll to the form at the bottom. → Add "+ New batch" to Today, and put the form first on Batches. **P2·S**
- "Have a batch ID instead?" is a developer escape hatch shown to every user. → Remove it, or move it to Account. **P2·S**

### Today
- Reminder titles are lower-case sentence fragments ("salted/brined — ensure…"), and "· medium" / "· critical" are severity labels without meaning. → Write the action first, sentence case, and use colour and icon for severity: "Check everything is under the brine". **P1·S**
- You can snooze a critical safety reminder by 24 h, past its own 48 h deadline. → Hide "Snooze 24h" on critical reminders, or cap the snooze at the deadline. **P1·S**
- The Snooze buttons are 28 px tall and their text has 3.81 : 1 contrast at 12 px on the amber cards; on a phone, three reminder cards fill the screen. → Use a single "Later ▾" menu with 44 px targets and one line per reminder, expanding on tap. **P2·S**
- The "Active batches" cards say "prep and salt · day 2 in stage", which describes stage bookkeeping rather than the jar. → Show "Day 2 · pH not logged · tangy around Wed". **P1·S**

### Batch page
- The header shows "1.8 d since it started" and "1.8 d in this stage", the same number twice. → Show "Day 2" with the stage in words, and drop the duplicate. **P2·S**
- The recipe's method is lost when you start from Ideas: the card's "keep everything under the brine" and "vegetables 46 % and brine 54 % of the jar" do not reach the batch. The Recipe tab shows masses plus a "Starting composition" table (lactose ≥ 0.0 g, alcohol 0.0 g). → Carry a "How to make it" list onto the Recipe tab, and fold the composition table into a disclosure. **P1·S–M**
- Biochemistry is a top-level tab equal to Log: KEGG chips, "D-Xylulose 5-phosphate". This is audience 3 material at audience 1 prominence. → Move it under Forecast → "About the model", or behind a "Science" disclosure. **P2·S**
- Taxonomy: "*Lactobacillus plantarum*" (Biochemistry) and "L. plantarum and L. brevis" (levain style card) are pre-2020 names. → Use *Lactiplantibacillus plantarum* and *Levilactobacillus brevis* (Zheng et al. 2020, IJSEM 70:2782). **P2·S**
- The observation types offer "gravity" and "brix" on a lacto batch, but not salt %, the variable the botulism rule needs. → Filter the types by ferment, and add "Salt %" for lacto. **P1·S**
- The tasting form asks for a "When you tasted it · leave empty for now" date with a locale placeholder ("jj/mm/aaaa" in a French browser). → Default it to now and hide it behind "Tasted earlier?". **P2·S**

### Forecast and science communication
- Units disagree on one screen: the "In the jar" card gives "1.8 g sugar … per 100 g", the chart below uses g/kg (18.4), and "0.02 % ABV" on brined carrots will alarm some users. → Use per 100 g everywhere, and hide ABV below 0.5 % with a one-line note. **P1·S**
- The aroma panel saturates: eight bars all read "likely · 100 % of runs", and "Solvent · probably · 72 % · think nail polish" appears on a cabbage-carrot brine. Telling a beginner their kraut may smell of nail polish needs a reason, or it should be left out. → Rank by character share (the release-1 C), show the top 3, and push "present but not characteristic" behind a disclosure. **P1·M**
- The aroma timeline flips back and forth: "day 1.9 fruity & green → day 3 fruity & pungent → day 15 fruity & green → day 16 fruity & pungent → day 18 fruity & green". This is label noise. → Smooth it (minimum dwell of 3 days) or show it only in Pro. **P2·S**
- "No aroma data for: Carrot, Garlic", while the Sulfurous gloss says "think cabbage, garlic…". → Say "garlic's own aroma isn't modelled yet" once, in the trust box. **P2·S**
- The "Next milestone" changes with the sub-tab ("pH below 4.6" on Process, "Tangy phase" on Taste, and "No milestones are defined for this ferment type yet" on Nutrition, for the app's main ferment type). → Pin one milestone above the sub-tabs. **P2·S**
- Three levels of tabs (Forecast/Log/Recipe/Biochemistry → Process/Taste & aroma/Nutrition → Substrates/Products/Microbes) plus four accordions. → Use two levels at most, and make the Substrates/Products/Microbes charts Pro-only. **P2·M**
- The ideas for "fruity" + "buttery" (kefir, lactic fresh cheese) are both "Led by δ-dodecalactone", so the two targets collapse into one compound. For dairy LAB ferments a food scientist expects buttery to be led by diacetyl (2,3-butanedione), which `aroma.py` does model. → Check diacetyl's yield, reduction and family assignment against the lactone. **P1·M** (audience 3 credibility)

### Safety
- See fixes 1 and 3. In addition: every reminder assumes the user owns a pH meter, and there is no "I don't have one" path. → Add strips as an option, plus a no-meter checklist (salt ≥ 2 % weighed, everything submerged, temperature, what spoilage looks like), clearly labelled less certain. Spec section 3.5 already plans calibration without a meter. **P1·M**
- The identical orange safety box on every Ideas card leads to banner blindness. → Show it once per type in the results header, and on a card only when it differs. **P2·S**

### Ideas / recommender
- The catalogue is too thin for pantry-first use: beetroot, beet, kale, turnip, jalapeño and the plural "cabbages" all return "No catalogue ingredient matches". → Add simple stemming and synonyms (cabbages → cabbage, beet → beetroot), offer "Not in our list yet: tell us" (logged), and prioritise curation of the 20 most common lacto vegetables. **P1·M**
- The aroma chips include off-notes as targets ("solvent", "fishy", "sulfurous", "cheesy"). The "think …" glosses live only in a `title` tooltip, which is invisible on touch. → Split them into "Aim for" and "Avoid" (V14), and show the gloss inline under a selected chip. **P2·S**
- "Not calibrated yet: 0 of 30 tasted batches; scores show as Low / Med / High" is meaningless to a user. → Drop it, or say "Scores get personal after you taste a few batches". **P2·S**
- The temperature-variant card "22.5 → 16 °C … cheesy: likely more noticeable" sells a defect as a feature. → Phrase the deltas against the user's targets, and flag off-notes as a risk. **P2·S**
- Card subtitles come from dataset fields ("Korean laboratory antimicrobial study", "Milk kefir from grains 10% extended"). → Use a curated display title and a region line. **P2·S**
- Masses are shown to 0.1 g ("978.9 g", "2.11 % of the batch", "22.5 °C"). → Round to kitchen precision (980 g, 21 g salt, about 22 °C), with exact values in Pro. **P2·S**

### Levain planner
- See fix 7. Also: the "Pro" switch in the corner is never explained. → Rename it "Show the science" and give it a one-line hint. **P2·S**
- The "Starter right now" choice is "Ripe, at room temperature" or "Straight from the fridge", with nothing for "fed 12 h ago / peaked / sluggish". → Add "Past its peak" and "Sluggish (fed < 2 days)", since lag is exactly where the model is off. **P2·S**

### Logbook
- At 390 px the "all cultures" select overflows the card (page scrollWidth 406 > 390). → Give the filter row `min-w-0` / `w-full` and wrap it. **P1·S**
- It is a raw event feed: "Entered stage prep and salt", "pH: 15" with no flag, and the filter shows "lacto_ferment" and "stage-change". It doesn't answer "what happened since yesterday, what's next?" → Group by batch, with "since your last visit" plus the next action per batch, and mark implausible values. **P2·M**

### Account
- No account deletion exists, although `DELETE /me` exists and the copy says "Your recipe stays in the library if you delete your account". For EU users that is a GDPR right-to-erasure gap. → Add a "Delete my account and data" button with typed confirmation. **P1·S**
- A guest sees two email forms ("Keep your starters / Save my account" and "Sign in with email / Email me a sign-in link") and has to work out which is which. "Keep your starters" uses sourdough wording for kraut makers. → One form: "Keep your batches: add your email"; then a small "Already have an account? Sign in". **P1·S**
- "Account id: 00000000-…-beef copy" shows a UUID to people who will never need it. → Hide it behind "Support details". **P2·S**
- The risk of losing anonymous data (Safari clears it after 7 days) is mentioned only on Account. → Nudge once on Today after the second logged reading. **P1·S**

### Mobile (390 px)
- The nav takes two rows (fix 10).
- On the batch page the forecast starts at about 800 px and the "Biochemistry" tab label is clipped at the right edge.
- On the levain page, "ready by" is several screens down.
- After logging, the page jumps to the top (fix 5). → Quick-log strip, four tabs, keep scroll position. **P1·M**
- Good: no horizontal scroll except in the Logbook, and the levain page's sticky "Peak Tue 01:20 · details ↓" bar works well.

### Accessibility
- Small targets: "Advance to next stage" and "Repeat this batch" are 28 px tall, side by side, and both irreversible. → At least 44 px, separated, with confirmation. **P1·S**
- Dates follow the browser locale inside an English UI ("mer. 28 oct., 07 h", "dim. 1 nov."), giving mixed French and English to the owner's own users. → Use a fixed UI locale for dates, or follow one language setting consistently. **P2·S**
- Dev only, but the root cause is shared: the header uses `new Date(started_at)` while the forecast uses `parseApiDate`. The same batch shows "Started 24 oct. 13:47" and "day 0 = 24 oct. 15:47"; the History tab and the Logbook disagree by an hour on the same reading. → Use one date-parse helper (Today's `parseUtc`) everywhere. **P2·S**
- Good: chart text alternatives with real numbers, "Table view", arrow-key reading, per-reminder `aria-label`s, the `role="switch"` toggles, and Atkinson Hyperlegible. Contrast is ≥ 4.5 : 1 almost everywhere (exceptions: the snooze text at 3.81 : 1, and the batch-list metadata at 4.40 : 1).

### Performance as felt
- Locally: the first open of a batch shows a skeleton for about 2.8 s, then about 50 ms on later opens; Ideas returns in about 0.4 s. Fine.
- Logging blanks the whole page (fix 5). That is the one place where it *feels* slow even though it is fast.
- "Search deeper — takes a few minutes" is honest. Add a progress count ("7 of 20 forecasts") and a notification on return. **P2·S**
- Prod cold start on Render was not tested (out of scope). The single 426 KB JS bundle loads the planner, charts and admin for everyone. → Lazy-load the planner, community admin and charts with `React.lazy`. **P2·S**

---

## 4. What is genuinely good (keep it)

- **Honest uncertainty.** Bands, table views and "your reading" dots are exactly right; they just need fewer words around them.
- **The calibration warning** ("1 of your readings … fall outside what the model can explain") catches bad data. Give it a delete button and it becomes a great feature.
- **Ideas → Start batch in one tap.** The recipe arrives with masses already filled in, and the composed recipe follows real kitchen practice (46/54 jar, 4.6 % brine, garlic at 2.5 %, "keep everything under the brine").
- **Safety above the tabs**, "so a hard stop is never hidden on another tab". That is the right instinct; it only needs the right data (fix 1).
- **Today's Overdue / Coming up split.** Snoozing never pulls a reminder earlier, and the double-submit guards are in place.
- **The paper-label batch header** and the dark, warm palette are distinctive and readable.
- **Levain sharing and calendar export** with 15-minute alerts, and "Track this bake". These are the right baker hooks.
- **Sourced recipes with citations, and the gate on every card.** That is the moat, so keep it visible but not loud.
