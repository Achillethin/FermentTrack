# FermentTrack for bakers — the levain planner

A planner that answers the questions a baker asks every day — *when will my levain peak, what feed ratio gets it ready by 7:00, when is bulk done, how sour will it be* — and that **learns your starter** from the bakes you log.

## What it models

You describe the bake; the app runs a few hundred plausible versions of it and shows the range.

| You choose | What it changes in the model |
|---|---|
| **Levain style** — home starter, levain liquide, levain dur, lievito madre, San Francisco, rye sour, Type II liquid sour, Type III dried sour, poolish, biga | Which microbes are in it (e.g. *L. sanfranciscensis* with the yeast *K. humilis* in a San Francisco sponge; mostly *S. cerevisiae* with *L. plantarum* and *L. brevis* in a typical home starter) and how dense they are when ripe |
| **Feed ratio** (1:1:1 … 1:10:10) and **hydration** | How diluted the microbes are (→ time to peak) and how acetic the levain turns: stiff and cool = more vinegar tang, liquid and warm = milder, more lactic |
| **Flour** (French T-number, US name shown) | The T-number is the ash content ×1000; ash buffers acid, so whole-grain and rye levains reach a higher TTA for the same pH. Rye rises less (no gluten network) |
| **Temperature** per step | Every microbe's growth follows its own temperature curve; fridge retards take a few hours to cool the dough |
| **Dough**: levain %, hydration, salt, target bulk rise, optional yeast | Mixing dilutes the ripe levain into fresh flour; salt slows the bacteria more than the yeast |

Outputs: rise of a jar sample (%), pH, TTA (mL 0.1 N NaOH per 10 g), lactic:acetic ratio (FQ), acids, sugars, microbe counts — each as a band (the range covering 90 % of plausible starters) around a middle line.

## Use it

- **Planner** (start screen → *Levain planner*): pick a style, a feed, flour and temperature, set the time you feed. You get *levain doubled*, *levain at peak*, and — if you plan the dough — *bulk done* (your target rise) as clock times with a range.
- **Feeding chart**: the table of ratio → peak time at your temperature and flour. Enter "ready by" and it highlights the ratio to use. Feed at 22:00 for 07:00? Read the row.
- **Track this bake**: saves the plan as a batch on one of your starters. Move the batch to *Bulk ferment* when you mix and to *Shape* when you shape — the forecast re-plans from the real times.

## Readings that teach it your starter

Log any of these on the batch; each makes the next forecast for **that starter** better.

| Reading | How | Accuracy the model assumes |
|---|---|---|
| **Rise %** | Right after feeding (or mixing), put a sample in a straight-sided jar and mark the level. Later: (height − mark) / mark × 100. The most useful reading. | ±10 points |
| **pH** | A calibrated meter, a pinch of levain in a little distilled water | ±0.15 |
| **TTA** | 10 g sample + 90 mL water, titrate with 0.1 N NaOH to pH 8.5; mL used | ±0.5 mL |
| **Temperature** | Of the dough or the room, a few times per step | — |

Three or four rise readings per bake (e.g. at 2, 4 and 6 h) are enough. When the batch is marked done, what the readings revealed is stored as evidence for that starter.

## What it learns, and from whom

Your starter inherits from two classes and then becomes itself:

- **the levain type** — every *levain dur* logged by anyone teaches the *levain dur* class a little (only numbers are shared, never notes or names);
- **the baker** — your kitchen, flour and habits: your second starter starts from what your first one taught;
- **the starter itself** — after a few bakes, its own speed and temperature preference dominate.

With no bakes logged anywhere, the forecast is the published-science default. Each finished bake with readings moves the right levels by the right amount (a proper Bayesian model; nothing is counted twice).

## Honest limits

- It is a **model estimate, not a measurement**: watch the dough, not only the clock. The bands are there to be read.
- Before it knows your starter, the middle line for young, fast levains (1:1:1 at 25 °C) is on the slow side of what vigorous starters do; your first logged bakes correct this.
- Rise is modelled from the gas the microbes make and the acid weakening the gluten — a sound, simple physics, but not a rheology model: shaping, folds and flour strength beyond its grade are not in it.
- Not for food-safety decisions.

The science and every source: `docs/superpowers/specs/2026-09-28-sourdough-engine-design.md`.
