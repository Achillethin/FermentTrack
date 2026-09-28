# Seeding FermentTrack: community posts, checklist, first-run copy

Pitch for every post: **start a batch in 30 seconds, see what's due when you open it.**
Goal of seeding: get a handful of real people through ONE full batch each and learn where it breaks. Not downloads.

Not pitched anywhere in this file: the biochemistry panel and the forecast/prediction feature.

## Fill in before posting

- `{{APP_URL}}`: the public app link. The repo never states it. `frontend/vite.config.js` only says the frontend is served from `https://<user>.github.io/FermentTrack/` (GitHub Pages, base path `/FermentTrack/`), and the deploy workflow does not print the URL. Paste the real link, open it on a phone, and confirm it loads before posting.

## Before you post

What the app does today, checked against the code in this worktree (`src/fermenttrack/reminders.py`, `stages.py`, `routers/reminders.py`, `frontend/src/Today.jsx`):

- The backend creates a reminder when a batch starts and again each time the stage is advanced. `due_at` = stage entry + a fixed duration for that stage.
- The Today screen (the home screen) lists open reminders in the app: an "Overdue" list and "Coming up (next 48h)", each with a "Done" button and "Snooze 1h / 6h / 24h" buttons, plus "Active batches" cards showing "day N in stage" and linking into each batch.
- **Reminders are in-app only.** No push, email or SMS reaches the phone. `docs/ARCHITECTURE.md` says critical reminders "use push notifications"; that is not built. So every draft says "open the app to see what's due", and none of them implies anything arrives on its own.
- "Done" closes the reminder; it does not advance the stage. The user presses "Advance to next stage" themselves.

Other facts the copy relies on, all verified:

- Starting a batch: name a culture, pick a substrate from a dropdown, optionally add a target and an estimated temperature, press "Start batch" (`NewBatch` in `frontend/src/Batches.jsx`, previously `App.jsx`). Whether that takes 30 seconds is not measured. Time it yourself on a phone before you say "30 seconds" anywhere you can't edit.
- Substrates with stage machines and timed reminders: kombucha, sourdough, koji, cheese, lacto_ferment, miso, garum. Kefir and vinegar are selectable but only get an "in_progress" stage with no reminders. The dropdown shows raw names such as `lacto_ferment`.
- Reminder timers are fixed midpoints of typical ranges (for example koji incubate = 42 h, kombucha 1F = 10 days). They do **not** adapt to temperature. The temperature you enter feeds the forecast, not the reminders.
- Advancing is manual. The app doesn't know a step is done until you press "Advance to next stage."
- Each stage carries one reminder at its end. Nothing recurs (no "burp every day", no "feed every 12 h").
- Sign-in is anonymous (`frontend/src/auth.js`): no signup, but the batches belong to that browser's session, and clearing site data loses them. There is no "claim with email" flow yet. Say this in posts; it matters most for the 90-day miso ask.
- Logging: pH, temperature, gravity, brix, smell, taste, appearance, free-text notes, and a timeline.
- Data lives on a free-tier backend that can cold-start slowly. The repo has a 10-minute keep-warm health-check workflow to keep it warm.

## Ready-to-post drafts

Recommended order is in the checklist. Voice is first person, one person's side project, no employer mentioned.

Personal-experience lines ("I make koji at home (mostly rice)", "I keep losing track of where each jar is", "I make miso at home") are placeholders for a genuine backstory. Edit each to what is actually true of you before posting; don't post claims about your own brewing you can't back up in the comments.

### 1. r/Koji

**Title:** I built a small free app that shows you what koji step is due next. Would anyone run one batch through it and tell me where it's wrong?

**Body:**

> I make koji at home (mostly rice) and my recurring failure is not the mold, it's forgetting when I started the steam, or losing track of how long the box has been in the incubator. I built a small web app for myself and I'd like a few koji people to try it and tell me what's off. I made it, so treat this as feedback wanted, not a launch.
>
> What you do: open the link, name your batch, pick "koji" from the substrate dropdown, hit Start. That's the whole setup. It should take about 30 seconds on a phone. No signup.
>
> The stages and timings it uses for koji, all fixed defaults:
> - soak, 8 h
> - steam, 1 h
> - inoculate, 1 h
> - incubate, 42 h (its reminder is "check for even white mycelium coverage, harvest when ready")
> - harvest, 1 h
>
> How the reminders work: each stage has a due time. **It's in-app only. There's no push, email or text**, so open the app to see what's due; a Today screen lists what's overdue and what's coming up in the next 48 h, with Done and Snooze. Marking a reminder Done doesn't move the batch on: you press "Advance to next stage" yourself when you finish a step. You can log temperature, pH, smell, appearance and notes on the batch timeline.
>
> What I know is missing: there's nothing between "start incubating" and hour 42. No mid-incubation "mix it / check the box temperature" nudge, and the timers don't adapt to your incubator temperature. I'd like to hear what you'd want there, because I don't know your process better than you do. It also won't tell you a batch is safe or spoiled. That's your call.
>
> What I'd love: run one batch start to finish (it's a ~2 day thing, so it's a cheap test), then tell me: which reminder was late, wrong or annoying, where you stopped using it, and what you ended up logging. Also, honest heads-up: there's no account, so clearing your browser data loses your batches.
>
> Link: {{APP_URL}}
>
> Happy to hear "this is pointless because I just use a phone timer" too.

**Check before posting:** read the r/Koji sidebar and pinned posts for self-promotion and "I made" rules; if promotion is restricted or unclear, message the mods with the draft first. Do not assume the rules.

### 2. r/fermentation

**Title:** Made a free batch tracker that shows what's due, for kraut/kimchi/kombucha/koji etc. Looking for people to try one full batch and tell me what breaks

**Body:**

> I ferment a lot of different things and could never keep them straight (what went in, when I salted it, when I was supposed to taste it). So I built a small web app for myself. I'm the developer and I'm here for feedback, not installs.
>
> What it does: you start a batch by naming it and picking the type, and it fills in the next step and a due time. Types with steps built in: lacto-ferments (kraut, kimchi, veg), kombucha, koji, miso, garum, sourdough and cheese. Kefir and vinegar are in the dropdown for notes only, with no reminders.
>
> For a lacto-ferment it does exactly two things:
> - after 1 h: "salted/brined, make sure the vegetables stay fully submerged"
> - after 7 days: "taste test: keep fermenting or move to the fridge"
>
> That's it. It's a fixed 7 days, not adjusted for your room temperature or salt level, and it can't tell you if something has gone wrong. You log pH, temperature, taste, smell, notes yourself.
>
> How the reminders work: each step has a due time, and you open the app to see what's due. **In-app only. No push, email or text.** Marking a reminder Done doesn't advance the batch; you press "Advance" yourself when a step is done.
>
> Setup takes about 30 seconds and needs no signup. Fair warning: it's an anonymous session, so clearing your browser data loses your batches.
>
> Link: {{APP_URL}}
>
> If you're willing, please run ONE batch start to finish and tell me: where the reminders were late, wrong or annoying, where you drifted away from using it, and what you actually logged. "7 days is silly for my kimchi" is exactly the kind of answer I want.

**Check before posting:** read the r/fermentation sidebar rules and any pinned or weekly threads for self-promotion and "I made this" policy; message the mods first if it's restricted or ambiguous. Don't assert what the rules say until you've read them.

### 3. r/Kombucha

**Title:** I made a free app that shows what's due (taste, bottle, burp) for your kombucha. Would a few brewers run one batch and tell me what's off?

**Body:**

> I'm a home brewer and I keep losing track of where each jar is: is it day 8 of 1F or day 11? did I bottle on Sunday or Monday? I built a small web app for it. I made it, so this is a feedback ask, not an ad.
>
> Start a batch by naming it and choosing "kombucha". It takes about 30 seconds, no signup.
>
> The stages and the due-time defaults:
> - brew sweet tea, 1 h ("cool tea to room temp, add SCOBY, start 1F")
> - 1F, 10 days ("taste test, check for readiness to move to 2F")
> - 2F flavoring, 3 days ("check carbonation before bottling")
> - bottling, 1 day ("burp bottles, over-carbonation risk")
> - conditioning, 3 days ("check progress, move to fridge when ready")
> - ready
>
> Those numbers are the midpoints of the usual ranges (7 to 14 days for 1F, and so on). They are **not** adjusted to your room temperature, so a warm kitchen will make them wrong. You can log pH, temperature, taste, smell and notes.
>
> How the reminders work: every stage has one due time. Open the app to see what's due. **In-app only, no push, email or text**, and it's one reminder per stage, not a daily burp reminder. You press "Advance" when you move to the next stage; Done alone doesn't do that.
>
> I'd love a brewer to run one batch through 1F, 2F and bottling and tell me: which reminders were late, wrong or annoying, where you stopped bothering, and what you logged. Especially the burp timing: I'm not sure one reminder is enough for bottles.
>
> No account, so clearing browser data loses your batches.
>
> Link: {{APP_URL}}

**Check before posting:** read the r/Kombucha sidebar rules on self-promotion and app or link posts before submitting; if restricted, message the mods first. Don't claim to know the rules.

### 4. Miso / garum-adjacent: r/Miso

**Why this venue:** the product has real miso and garum stage machines, and miso is the koji-adjacent long ferment. I believe r/Miso exists, but I can't confirm it from here. Confirm it's active (recent posts) before posting. If it's dormant or absent, skip this post and put the miso/garum ask inside the r/fermentation thread as a reply to interested people, rather than inventing a venue. I don't know of a dedicated garum community; don't assume one exists.

**Title:** Free app to track a miso batch (koji + salt) and see when the check-in is due. Would someone try it and tell me if the timings are off?

**Body:**

> I make miso at home and I always lose the date I packed it. I built a small web app to keep the batch, the recipe and notes in one place. I'm the developer, and I'm after feedback, not users.
>
> Start a batch: name it, pick "miso", press Start. About 30 seconds, no signup.
>
> The steps it knows:
> - cook soybeans, 3 h ("cooked and cooled, mix with koji and salt")
> - mix koji and salt, 1 h ("packed into the vessel, begin fermentation")
> - ferment, **90 days** ("check for surface mold, press down, taste periodically")
> - ready
>
> Honest limitation: for the long ferment there is **one** check-in at day 90. Nothing in between, and 90 days is a fixed default, not something that adapts to your room temperature, salt ratio or how you like it. I know real miso is a range (weeks to years), so tell me what timings you'd use.
>
> How the reminders work: open the app to see what's due. **In-app only, no push, email or text.** And because it's an anonymous session, **clearing your browser data loses the batch**, which really matters for a 90-day ferment. Please don't use this as your only record.
>
> Since a full 90-day test is long, a good "full batch" ask here is: start it, tell me whether the first two steps and their timing matched your process, and come back at the check-in with how it went. If you also make garum, it has salt-fish then a 180-day ferment then strain, with the same caveats.
>
> Link: {{APP_URL}}

**Check before posting:** read the sidebar rules and mod contact for r/Miso (if it exists and is active) before posting; message the mods first if promotion is restricted or unclear.

## Posting checklist

**Before any post**
- [ ] Every draft says reminders are in-app only and to open the app to see what's due; none implies a push, email or text.
- [ ] `{{APP_URL}}` replaced; app opened on a phone and a koji batch started end-to-end yourself.
- [ ] Timed the start flow on a phone. If it's not roughly 30 seconds, change "about 30 seconds" in each draft.
- [ ] Backend awake (open the app once; it's on a free tier that can be slow to wake).
- [ ] Read each subreddit's sidebar and pinned posts; message mods where promotion is restricted or unclear. Post nothing you'd be unhappy to have removed.
- [ ] A feedback place ready: a simple doc or sheet (see "Logging responses").

**Order and pacing (one at a time, not all at once)**
1. **r/Koji first.** A koji batch is about 2 days, so it gives the fastest full-batch signal and forces every stage's timing to be tested.
2. Wait for feedback from the first before the next. Fix anything reported twice.
3. **r/fermentation** (a 7-day lacto batch is a quick second signal).
4. **r/Kombucha** (1F alone is 7 to 14 days; expect slow replies).
5. **r/Miso** last (a full batch is 90 days; the ask is partial by design).

**Timing.** I don't have verified data on best posting times, so I'm not giving any. Pick a slot where you can answer comments for the first few hours, avoid days you'll be travelling, and don't post in the evening and then vanish. Reply to every comment, including the negative ones. Follow up with a reply, not a new post, at roughly the point a full batch should have finished.

**What to ask each responder**
- Run ONE full batch, start to finish, on their own real ferment.
- Report back on:
  1. Which reminders were late, wrong or annoying (name the stage).
  2. Where they dropped off: which step, or which day, they stopped opening it, and why.
  3. What they actually logged (measurements, notes, nothing).
- Optional, light touch (don't pitch these in the posts): whether the one-tap "Repeat this batch" on a batch page was useful for the next round, whether the Logbook (searchable feed of everything logged) or the Compare view (two batches side by side) got used, and whether "Export CSV" worked and had what they expected.
- Optional, in one line: what would have made them come back.

**Logging responses.** Keep one sheet: date, community, username, substrate, batch started (y/n), stage reached, wrong-timing stages, dropped at, what they logged, quote, action taken. Log dropouts too: "started and never came back" is the main finding. Use their words verbatim; don't average them.

**Stop / iterate rule**
- Don't post to the next community until the previous one has produced at least a few replies you can act on, or a week has passed with none. No replies is a result: fix the pitch or the product, don't blast more places.
- If two or more people report the same broken thing (a reminder that never appears, a confusing form, lost batches), stop posting, fix it, then continue.
- If people start a batch but almost none finish, treat that as the problem to solve before any new posts.
- If a mod removes a post or asks you to stop, stop in that community and don't repost.

## First-run empty-state copy

For a user with zero batches (fits the Today and Batches pages; the Today screen already has an empty state, so the variants below are optional alternatives to its current copy: headline "Start a batch in 30 seconds", subline "Pick what you're fermenting and we'll show you here when it's time to act.", button "Start your first batch"). Written for a narrow mobile card.

**Variant A: plain (closest to the app's current voice)**
- Headline: No batches yet
- Subline: Start one and see what's due next.
- Primary button: Start a batch
- Hint: Pick koji, kombucha, kraut, miso or sourdough. Takes about 30 seconds.

**Variant B: warmer**
- Headline: What are you fermenting?
- Subline: Name it, pick the type, and we'll show you the next step and when it's due.
- Primary button: Start my first batch
- Hint: Reminders show up here in the app. No signup needed.

**Variant C: terse**
- Headline: Nothing fermenting
- Subline: Start a batch to get a due list.
- Primary button: Start batch
- Hint: In-app reminders only. Clearing browser data erases batches.

Notes: the hint text in A and C is deliberately honest about scope (in-app, no signup, browser-bound). Use the substrate names the dropdown shows (`lacto_ferment` renders raw; either rename it in the UI or write "kraut" in copy and expect the mismatch).
