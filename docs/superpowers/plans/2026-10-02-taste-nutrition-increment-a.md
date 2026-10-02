# Taste & Nutrition (Increment A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add nutrition per 100 g and taste over time (activities, taste phases, loose milestones) to every forecast, and a *Process · Taste & aroma · Nutrition* lens in the Forecast tab.

**Architecture:** A pure derived layer (`prediction/derived.py`) reads each ensemble member's trajectory after the unchanged kinetic solve, in both forecast paths (`service._forecast`, `bake._forecast`). Curated, cited reference data lives in `prediction/compounds.py`; per-type taste ladders in `profiles.py`. Results ride the existing series/milestone machinery plus one optional `sensory` block; the frontend adds a lens switch, an "In the jar" card, a phase band and a nutrition table.

**Tech Stack:** Python 3.11, numpy, FastAPI/Pydantic, pytest, mypy strict, ruff; React 18 + Vite + Tailwind, hand-rolled SVG charts, node self-check scripts.

**Spec:** `docs/superpowers/specs/2026-10-02-flavour-nutrition-design.md` (increment A = § 1–3, 6–9 without aroma). Aroma (§ 4–5: diagnostic RHS pass, `compounds` odorants, aroma strip) is increment B, planned separately after curation.

## Global Constraints

- numpy/scipy only in the backend; no new frontend dependencies.
- The kinetic solve and its outputs are unchanged; the existing suite passes untouched.
- Unknown is never zero: a nutrient no ingredient reports is `None` ("–"); partial data is a lower bound ("≥").
- Wording: "may be noticeable", "above detection threshold"; never "tastes like", "safe", "spoiled". Nothing feeds the Safety Advisory.
- `sensory.derived_version = "sensory-v1"`, `sensory.validated = false`.
- A failure in the derived layer never breaks a forecast: the forecast returns without `sensory` and with the warning "Taste and nutrition could not be computed for this batch; the forecast itself is unaffected."
- Dark-only app, chart surface `#191612`; phase ramp `#184f95, #2a78d6, #6da7ec, #b7d3f6` (validated `--ordinal --mode dark`); `#fab219` (`--viz-ref`) stays reserved for the pH 4.6 safety line.
- Python checks run from the worktree: `W=$(pwd -W); PYTHONPATH="$W/src" ../../.venv/Scripts/python.exe -m pytest …` (plain `$PWD` silently imports the main checkout).

## Review Focus

1. **No recipe logged (typical recipe):** fat/fibre/salt rows are "–", energy and carbohydrate are lower bounds — pinned in Task 5 (`test_typical_recipe_nutrition_is_partial`).
2. **"Now" past the window (old or finished batch):** the summary's "now" clamps to the window's end — pinned in Task 4 (`test_now_past_the_window_clamps_to_the_end`).
3. **What-if temperature:** the sensory block is recomputed for the resampled ensemble and differs from the base — pinned in Task 5 (`test_what_if_moves_taste`).
4. **Koji (no taste ladder, pH hidden):** no taste phases, no taste milestones, still a nutrition label — pinned in Task 5 (`test_koji_has_no_taste_ladder`).
5. **Nothing grows (only unknown organisms):** derived values are flat but present — pinned in Task 5 (`test_unmodelled_organisms_still_get_a_label`).

---

### Task 1: Curated taste and nutrition reference data

**Files:**
- Create: `src/fermenttrack/prediction/compounds.py`
- Test: `tests/test_compounds_data.py`

**Interfaces:**
- Produces: `SWEET_THRESHOLD`, `SOUR_THRESHOLD`, `UMAMI_THRESHOLD`, `ALCOHOL_THRESHOLD: Prior`; `SWEETNESS: dict[str, Prior]` (keys `sucrose, hexoses, lactose, maltose`); `GLUTAMATE_SHARE: dict[str, Prior]` (keys `fish, soy, milk, cereal`); `GLUTAMATE_MW: float`; `ENERGY: dict[str, tuple[float, float]]` (kcal, kJ per g); `ETHANOL_G_PER_L_PER_ABV = 7.89`; `SALT_PER_SODIUM = 2.5`.

- [ ] **Step 1: Write the failing test** — `tests/test_compounds_data.py`:

```python
"""Data lint for the derived layer's curated reference data (prediction/compounds.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fermenttrack.prediction import compounds as C


def test_thresholds_are_positive_log_priors() -> None:
    for p in (C.SWEET_THRESHOLD, C.SOUR_THRESHOLD, C.UMAMI_THRESHOLD, C.ALCOHOL_THRESHOLD):
        assert 0 < p.lo < p.median < p.hi and p.scale == "log"


def test_sucrose_threshold_is_the_panel_recognition_median() -> None:
    # Höhl et al. 2014: 3.7 log10 µmol/L = 5.01 mmol/L x 342.3 g/mol = 1.72 g/L
    assert C.SWEET_THRESHOLD.median == pytest.approx(10**3.7 * 1e-6 * 342.3 * 1000, rel=0.01)
    # 90 % of the panel within 10^(±1.645 x 0.5) of the median
    assert C.SWEET_THRESHOLD.hi / C.SWEET_THRESHOLD.median == pytest.approx(
        10 ** (1.6448536 * 0.5), rel=1e-3
    )


def test_sweetness_and_glutamate_shares_are_sane() -> None:
    assert C.SWEETNESS["sucrose"].median == 1.0
    for p in C.SWEETNESS.values():
        assert 0.1 <= p.lo <= p.hi <= 2.0
    for p in C.GLUTAMATE_SHARE.values():
        assert 0.0 < p.lo <= p.hi < 1.0


def test_energy_factors_are_annex_xiv() -> None:
    assert C.ENERGY == {
        "carbohydrate": (4.0, 17.0), "protein": (4.0, 17.0), "fat": (9.0, 37.0),
        "alcohol": (7.0, 29.0), "organic_acid": (3.0, 13.0), "fibre": (2.0, 8.0),
    }  # fmt: skip


def test_every_number_is_cited() -> None:
    text = Path(C.__file__).read_text(encoding="utf-8")
    for cited in ("Höhl", "Johanningsmeier", "Mattes", "Park et al. 2002", "1169/2011", "est."):
        assert cited in text
```

- [ ] **Step 2: Run it to verify it fails** — `… -m pytest tests/test_compounds_data.py -q` → FAIL (`ModuleNotFoundError: fermenttrack.prediction.compounds`).

- [ ] **Step 3: Implement** — `src/fermenttrack/prediction/compounds.py`:

```python
"""Curated reference data for the derived layer (prediction/derived.py): taste thresholds,
relative sweetness, glutamate shares and energy factors. Aroma compounds join in
increment B (docs/superpowers/specs/2026-10-02-flavour-nutrition-design.md § 4-5).

Every number is cited or marked "est.". Taste thresholds are recognition thresholds in
water and their spread is the spread between people (log10 SD across a panel), so
P(above threshold) reads as "share of people who would notice it, in water". In a food,
other tastes mask each other and thresholds are higher.
"""

from __future__ import annotations

from fermenttrack.prediction.priors import Z90, Prior, fixed


def _panel(median: float, sd_log10: float) -> Prior:
    """A log-normal threshold from a panel's median and log10 standard deviation."""
    k = 10.0 ** (Z90 * sd_log10)
    return Prior(median, median / k, median * k, "log")


# Höhl, Schönberger & Busch-Stockfisch 2014, Ernahrungs Umschau 61:130 (70 panelists,
# deionised water; recognition thresholds in log10 µmol/L, mean ± SD): sucrose 3.7 ± 0.5,
# MSG 3.2 ± 0.4, citric acid 2.2 ± 0.1 (ISO/5 series).
SWEET_THRESHOLD = _panel(1.72, 0.5)  # g sucrose / kg (5.01 mmol/L x 342.3 g/mol)
UMAMI_THRESHOLD = _panel(1.58, 0.4)  # mmol glutamate / kg (MSG 1.58 mmol/L)
# Sour: Johanningsmeier, McFeeters & Drake 2005, J Food Sci 70:R44 - sourness follows the
# molar sum of acid species with a protonated carboxyl group plus H+, about equally for
# every organic acid. Citric acid at its recognition threshold (0.16 mmol/L, Höhl 2014)
# gives ~0.29 mmol/L of such species + H+ (pKa1 3.13). The panel SD there (0.1) is
# censored by the lowest dilution, so the spread here is est.
SOUR_THRESHOLD = _panel(0.30, 0.3)  # mmol/kg protonated acid species + H+
# Ethanol: detection ~1.4 % v/v in water, mostly as bitterness (Mattes & DiMeglio 2001,
# Physiol Behav 72:217); spread est.
ALCOHOL_THRESHOLD = Prior(1.4, 0.5, 4.0)  # % ABV

# Sweetness relative to sucrose, by weight. Compiled ranges: fructose 1.17-1.75, glucose
# 0.74-0.8, lactose 0.16-0.4, maltose 0.33-0.45 (DuBois et al. 1991, ACS Symp Ser 450;
# Kemp & Birch 1992; as compiled in the Wikipedia "Sweetness" table). The model lumps
# glucose and fructose ("hexoses"); yeasts eat glucose first, so leftovers lean fructose.
SWEETNESS: dict[str, Prior] = {
    "sucrose": fixed(1.0),
    "hexoses": Prior(1.0, 0.74, 1.5),
    "lactose": Prior(0.25, 0.16, 0.4),
    "maltose": Prior(0.4, 0.33, 0.45),
}

# Free glutamate as a share of the free amino acids, by mass.
GLUTAMATE_SHARE: dict[str, Prior] = {
    # Park et al. 2002, Fish Sci 68:913: a Vietnamese fish sauce, Glu 2.3 of 14.0 g/100 mL
    # free amino acids (0.16); a second batch had half the glutamate.
    "fish": Prior(0.13, 0.08, 0.17),
    # Miso: glutamate is the most abundant free amino acid, 0.4-1.7 g/100 g (share est.).
    "soy": Prior(0.18, 0.10, 0.30),
    "milk": Prior(0.15, 0.08, 0.22),  # est. (casein is ~20 % Glu + Gln)
    "cereal": Prior(0.15, 0.08, 0.25),  # est.
}
GLUTAMATE_MW = 147.13

# Regulation (EU) No 1169/2011, Annex XIV: (kcal, kJ) per g.
ENERGY: dict[str, tuple[float, float]] = {
    "carbohydrate": (4.0, 17.0),
    "protein": (4.0, 17.0),
    "fat": (9.0, 37.0),
    "alcohol": (7.0, 29.0),
    "organic_acid": (3.0, 13.0),
    "fibre": (2.0, 8.0),
}
ETHANOL_G_PER_L_PER_ABV = 7.89  # 1 % v/v = 7.89 g/L (ethanol density 0.789)
SALT_PER_SODIUM = 2.5  # EU labelling: salt = sodium x 2.5
```

- [ ] **Step 4: Run the test** → PASS.
- [ ] **Step 5: Commit** — `git add src/fermenttrack/prediction/compounds.py tests/test_compounds_data.py && git commit -m "Add curated taste and nutrition reference data"`.

---

### Task 2: Taste ladders and milestone lenses in the profiles

**Files:**
- Modify: `src/fermenttrack/prediction/profiles.py` (Milestone, new `Boundary`/`TasteSpec`, FermentProfile fields, per-type entries)
- Test: `tests/test_taste_profiles.py`

**Interfaces:**
- Produces: `Milestone.lens: Literal["process", "taste", "nutrition"] = "process"`; `Boundary(metric: Literal["sugar_acid", "acetic", "acidity_pct", "umami"], kind: Literal["above", "below"], threshold: Prior)`; `TasteSpec(phases: tuple[str, ...], boundaries: tuple[Boundary, ...], notes: tuple[str, ...], glutamate: str = "soy")`; `FermentProfile.taste: TasteSpec | None = None`, `FermentProfile.co2_escapes: bool = True`.

- [ ] **Step 1: Write the failing test** — `tests/test_taste_profiles.py`:

```python
"""Taste ladders and milestone lenses in the per-type profiles."""

from __future__ import annotations

import pytest

from fermenttrack.prediction import compounds as C
from fermenttrack.prediction.profiles import GENERIC_PROFILE, PROFILES, TasteSpec

METRICS = {"sugar_acid", "acetic", "acidity_pct", "umami"}


def test_every_type_but_koji_has_a_taste_ladder() -> None:
    for name, p in {**PROFILES, "generic": GENERIC_PROFILE}.items():
        if name == "koji":
            assert p.taste is None
            continue
        assert p.taste is not None, name
        assert {b.metric for b in p.taste.boundaries} <= METRICS
        assert p.taste.glutamate in C.GLUTAMATE_SHARE


def test_a_ladder_needs_one_boundary_and_note_per_step() -> None:
    with pytest.raises(ValueError):
        TasteSpec(("a", "b"), (), ())


def test_nutrition_milestones_carry_their_lens() -> None:
    lens = {m.key: m.lens for m in PROFILES["kombucha"].milestones}
    assert lens["abv_over_0_5"] == "nutrition"
    assert lens["ph_below_4_2"] == "process"
    assert {m.key: m.lens for m in PROFILES["kefir"].milestones}["lactose_half"] == "nutrition"


def test_dough_keeps_its_gas() -> None:
    assert not PROFILES["sourdough"].co2_escapes
    assert PROFILES["kombucha"].co2_escapes
```

- [ ] **Step 2: Run it** → FAIL (`ImportError: cannot import name 'TasteSpec'`).

- [ ] **Step 3: Implement** in `profiles.py`:

1. `Milestone`: add after `ref`:

```python
    # which lens of the forecast panel lists it (spec 2026-10-02 § 6)
    lens: Literal["process", "taste", "nutrition"] = "process"
```

2. After `Milestone`, add:

```python
@dataclass(frozen=True)
class Boundary:
    """One step up a taste ladder: a derived metric (prediction/derived.py) crosses an
    uncertain threshold. Thresholds are est.: nobody has measured "balanced" for you."""

    metric: Literal["sugar_acid", "acetic", "acidity_pct", "umami"]
    kind: Literal["above", "below"]
    threshold: Prior


@dataclass(frozen=True)
class TasteSpec:
    """Ordered taste phases. A member is in phase k while boundaries 1..k all hold."""

    phases: tuple[str, ...]
    boundaries: tuple[Boundary, ...]
    notes: tuple[str, ...]  # why each phase after the first matters (its milestone note)
    glutamate: str = "soy"  # compounds.GLUTAMATE_SHARE key: the protein source

    def __post_init__(self) -> None:
        if not len(self.phases) == len(self.boundaries) + 1 == len(self.notes) + 1:
            raise ValueError("a taste ladder needs one boundary and one note per step")


def _acid_ladder(
    phases: tuple[str, str, str], tangy: Prior, sour: Prior, notes: tuple[str, str],
    glutamate: str = "soy",
) -> TasteSpec:  # fmt: skip
    return TasteSpec(
        phases,
        (Boundary("acidity_pct", "above", tangy), Boundary("acidity_pct", "above", sour)),
        notes,
        glutamate,
    )


_ABV_05 = Milestone(
    "abv_over_0_5", "Alcohol over 0.5 % ABV",
    "a common legal line for “non-alcoholic” (US kombucha, TTB); limits vary by country",
    "nut:alcohol", "above", 0.5, lens="nutrition",
)  # fmt: skip
_LACTOSE_HALF = Milestone(
    "lactose_half", "Half the lactose fermented",
    "for lactose-sensitive drinkers; not a lactose-free claim",
    "nut:lactose", "consumed_fraction", 0.5, lens="nutrition",
)  # fmt: skip
```

3. `FermentProfile`: add at the end of the fields:

```python
    # Taste phases for the Taste lens (None: no ladder, e.g. koji, an ingredient)
    taste: TasteSpec | None = None
    co2_escapes: bool = True  # False: a dough keeps its gas (per-100 g needs no CO2 loss)
```

4. Per type (inside `PROFILES`), add `taste=` (and milestones as listed):

```python
# kombucha: milestones=(... existing ..., _ABV_05), and
            taste=TasteSpec(
                ("sweet", "balanced", "tart", "vinegary"),
                (
                    Boundary("sugar_acid", "below", _r(12.0, 25.0, 50.0)),
                    Boundary("sugar_acid", "below", _r(4.0, 8.0, 16.0)),
                    Boundary("acetic", "above", _r(4.0, 8.0, 15.0)),
                ),
                (
                    "sweetness and acidity roughly level: a common point to bottle",
                    "the acids lead and little sweetness is left",
                    "acetic acid dominates: heading for vinegar",
                ),
            ),
# sourdough: co2_escapes=False, and
            taste=_acid_ladder(
                ("mild", "tangy", "sharp"), _r(0.2, 0.3, 0.5), _r(0.5, 0.7, 1.0),
                ("a noticeable sour note", "a sharp, sour dough"), "cereal",
            ),
# cheese:
            taste=TasteSpec(
                ("sweet milk", "fresh tang"),
                (Boundary("acidity_pct", "above", _r(0.1, 0.2, 0.35)),),
                ("the curd's lactic tang",),
                "milk",
            ),
# kefir: milestones=(... existing ..., _ABV_05, _LACTOSE_HALF), and
            taste=_acid_ladder(
                ("milky", "tangy", "sour"), _r(0.25, 0.4, 0.6), _r(0.6, 0.8, 1.0),
                ("a fresh tang", "typical finished kefir: 0.8-1 % lactic acid"), "milk",
            ),
# lacto_ferment and GENERIC_PROFILE:
            taste=_acid_ladder(
                ("fresh", "tangy", "sour"), _r(0.15, 0.3, 0.6), _r(0.6, 1.0, 1.5),
                ("lactic acid clearly present",
                 "fully soured: sauerkraut finishes at 1.5-2.3 % acidity"),
            ),
# miso:
            taste=TasteSpec(
                ("mild", "savoury", "deep savoury"),
                (
                    Boundary("umami", "above", _r(1.5, 3.0, 6.0)),
                    Boundary("umami", "above", _r(15.0, 30.0, 60.0)),
                ),
                ("free glutamate clearly savoury", "the deep umami of an aged miso"),
                "soy",
            ),
# garum: same as miso with notes ("savoury", "the deep umami of a mature fish sauce")
#        and glutamate "fish"
# vinegar:
            taste=TasteSpec(
                ("boozy", "sharp", "vinegar"),
                (
                    Boundary("acetic", "above", _r(5.0, 10.0, 20.0)),
                    Boundary("acetic", "above", _t(35.0, 40.0, 45.0)),
                ),
                ("acetic acid now leads the ethanol",
                 "about 4 % acetic acid, the usual minimum for vinegar"),
            ),
# koji: no taste (None)
```

`_t`, `_r` and `Prior` already exist in `profiles.py`. All boundary priors are est.; the kombucha ratio medians follow a sweet tea (70 g/L sucrose) reaching ~13 g/g at day 7 and ~5 at day 14 in the calibrated forecast; the acidity ladders follow the trajectory sources already in the forecast spec (sauerkraut 1.5–2.3 %, kefir 0.8–1 %).

- [ ] **Step 4: Run** `tests/test_taste_profiles.py` and the existing `tests/test_prediction_*.py -q` → PASS (the new fields default, so nothing else changes).
- [ ] **Step 5: Commit** — `git commit -am "Add taste ladders and milestone lenses to the ferment profiles"` (add the new test file first).

---

### Task 3: Derived layer — nutrition per 100 g

**Files:**
- Create: `src/fermenttrack/prediction/derived.py` (nutrition part)
- Test: `tests/test_derived.py`

**Interfaces:**
- Consumes: `compounds.ENERGY`, `ETHANOL_G_PER_L_PER_ABV`, `SALT_PER_SODIUM`; `engine.PI`.
- Produces: `Carried(fat, fibre, sodium, other_carbohydrate: float | None = None, lower: frozenset[str] = frozenset())`, `UNKNOWN = Carried()`; `nutrition(pools: FloatArray (N,T,P), carried: Carried, co2_escapes: bool) -> tuple[dict[str, FloatArray], frozenset[str]]` with row keys from `LABEL_ROWS` (missing = unknown); `mass_left(pools, co2_escapes) -> FloatArray (N,T)`.

- [ ] **Step 1: Write the failing tests** — `tests/test_derived.py`:

```python
"""Derived layer: nutrition per 100 g, taste activities and phases (prediction/derived.py)."""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction import derived, engine, service
from fermenttrack.prediction.engine import N_POOLS, PI
from fermenttrack.prediction.profiles import PROFILES


def _pools(t: int = 1, n: int = 1) -> np.ndarray:
    return np.zeros((n, t, N_POOLS))


def test_energy_abv_and_co2_mass_loss() -> None:
    pools = _pools(2)
    pools[0, 0, PI["sucrose"]] = 100.0
    pools[0, 1, PI["ethanol"]] = 47.0
    pools[0, 1, PI["co2"]] = 45.0
    rows, lower = derived.nutrition(pools, derived.UNKNOWN, co2_escapes=True)
    left = 1.0 - 0.045
    assert rows["sugars"][0, 0] == pytest.approx(10.0)
    assert rows["energy_kcal"][0, 0] == pytest.approx(40.0)
    assert rows["alcohol"][0, 1] == pytest.approx(47.0 / (10 * left) * 10 / 7.89)
    assert rows["energy_kcal"][0, 1] == pytest.approx(7.0 * 47.0 / (10 * left))
    assert "fat" not in rows and {"energy_kcal", "energy_kj", "carbohydrate"} <= lower


def test_a_dough_keeps_its_mass() -> None:
    pools = _pools()
    pools[0, 0, PI["co2"]] = 30.0
    pools[0, 0, PI["maltose"]] = 20.0
    rows, _ = derived.nutrition(pools, derived.UNKNOWN, co2_escapes=False)
    assert rows["sugars"][0, 0] == pytest.approx(2.0)


def test_carried_rows_and_lower_bounds() -> None:
    carried = derived.Carried(
        fat=32.5, fibre=None, sodium=0.43, other_carbohydrate=0.0, lower=frozenset({"fat"})
    )
    rows, lower = derived.nutrition(_pools(), carried, co2_escapes=True)
    assert rows["fat"][0, 0] == pytest.approx(3.25)
    assert rows["salt"][0, 0] == pytest.approx(0.43 * 2.5 / 10)
    assert "fibre" not in rows
    assert {"fat", "energy_kcal", "energy_kj"} <= lower and "salt" not in lower


def _prior_run(ferment: str, n: int = 16) -> np.ndarray:
    profile = PROFILES[ferment]
    inputs = service.PredictionInputs(
        fermentation_type=ferment, now_h=0.0, expected_temperature_c=None,
        organisms=tuple(
            service.OrganismIn(o, ORGANISMS.get(o, "bacteria"), ())
            for o in FERMENTATION_TYPE_ORGANISMS[ferment]
        ),
        organism_source="default", recipe=(), measurements=(),
    )  # fmt: skip
    init = service._initial_state(profile, inputs.recipe)
    plans = service._plan_organisms(inputs, profile)
    sched, *_ = service._schedule(inputs, profile, None, profile.horizon_h)
    spec, _ = service._spec(profile, plans, init, sched, {})
    z = np.random.default_rng(0).standard_normal((n, spec.dim))
    tr = engine.simulate(spec.params(z), np.linspace(0.0, profile.horizon_h, 41))
    return tr.pools


@pytest.mark.parametrize("ferment", sorted(PROFILES))
def test_batch_energy_never_rises(ferment: str) -> None:
    """Fermentation only loses energy. Measured with carbohydrate in monosaccharide
    equivalents (3.75 kcal/g): on the EU label basis (4 kcal/g as weighed) hydrolysis
    alone would add energy (starch -> glucose gains 11 % in mass from water)."""
    p = _prior_run(ferment)

    def g(k: str) -> np.ndarray:
        return p[:, :, PI[k]]

    mono = g("hexoses") + 1.0526 * (g("sucrose") + g("lactose") + g("maltose")) + 1.111 * g(
        "starch"
    )
    kcal = (
        3.75 * mono + 4.0 * (g("protein") + g("peptides") + g("amino_acids")) + 7.0 * g("ethanol")
        + 3.0 * (g("lactic_acid") + g("acetic_acid") + g("gluconic_acid"))
    )  # fmt: skip
    assert np.all(np.diff(kcal, axis=1) <= 1e-3 * kcal[:, :1])
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError: fermenttrack.prediction.derived`).

- [ ] **Step 3: Implement** — create `src/fermenttrack/prediction/derived.py` with the module docstring, constants and nutrition part:

```python
"""Derived readouts of a forecast ensemble: nutrition per 100 g and taste over time.

Pure numpy, no DB. Computed per ensemble member from the trajectories after the kinetic
solve (the solve is unchanged), so the posterior your readings shaped carries over and a
what-if temperature moves these curves too. Aroma joins in increment B.
Design: docs/superpowers/specs/2026-10-02-flavour-nutrition-design.md § 2, 3, 7, 8.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fermenttrack.prediction import compounds as C
from fermenttrack.prediction.engine import PI
from fermenttrack.prediction.priors import FloatArray

SUGARS = ("sucrose", "hexoses", "lactose", "maltose")

# Nutrition-label rows in declaration order (Regulation (EU) 1169/2011): key, label, unit.
LABEL_ROWS: tuple[tuple[str, str, str], ...] = (
    ("energy_kj", "Energy", "kJ"),
    ("energy_kcal", "Energy", "kcal"),
    ("fat", "Fat", "g"),
    ("carbohydrate", "Carbohydrate", "g"),
    ("sugars", "of which sugars", "g"),
    ("lactose", "of which lactose", "g"),
    ("fibre", "Fibre", "g"),
    ("protein", "Protein", "g"),
    ("free_amino_acids", "of which free amino acids", "g"),
    ("salt", "Salt", "g"),
    ("alcohol", "Alcohol", "% ABV"),
    ("organic_acids", "Organic acids", "g"),
)


@dataclass(frozen=True)
class Carried:
    """Recipe nutrients the ferment does not change, g per kg of starting batch. None = no
    ingredient reports it (unknown, never zero); `lower` = label rows that are lower bounds
    (an ingredient without data, or one that does not report that nutrient)."""

    fat: float | None = None
    fibre: float | None = None
    sodium: float | None = None
    other_carbohydrate: float | None = None  # carbohydrate the model does not track
    lower: frozenset[str] = frozenset()


UNKNOWN = Carried()


def mass_left(pools: FloatArray, co2_escapes: bool) -> FloatArray:
    """(N, T) share of the starting mass still in the jar: the CO2 that escapes leaves."""
    co2 = pools[:, :, PI["co2"]]
    if not co2_escapes:
        return np.ones_like(co2)
    return np.asarray(1.0 - np.clip(co2, 0.0, 500.0) / 1000.0)


def nutrition(
    pools: FloatArray, carried: Carried, co2_escapes: bool
) -> tuple[dict[str, FloatArray], frozenset[str]]:
    """Label rows per 100 g of what remains, (N, T) each; unknown rows are absent."""
    left = mass_left(pools, co2_escapes)

    def p(k: str) -> FloatArray:
        return np.asarray(pools[:, :, PI[k]])

    def per100(g_per_kg: FloatArray) -> FloatArray:
        return np.asarray(g_per_kg / (10.0 * left))

    sugars = p("sucrose") + p("hexoses") + p("lactose") + p("maltose")
    ethanol = per100(p("ethanol"))
    rows: dict[str, FloatArray] = {
        "carbohydrate": per100(sugars + p("starch") + (carried.other_carbohydrate or 0.0)),
        "sugars": per100(sugars),
        "lactose": per100(p("lactose")),
        "protein": per100(p("protein") + p("peptides") + p("amino_acids")),
        "free_amino_acids": per100(p("amino_acids")),
        "organic_acids": per100(p("lactic_acid") + p("acetic_acid") + p("gluconic_acid")),
        "alcohol": np.asarray(ethanol * 10.0 / C.ETHANOL_G_PER_L_PER_ABV),
    }
    if carried.fat is not None:
        rows["fat"] = per100(np.full_like(left, carried.fat))
    if carried.fibre is not None:
        rows["fibre"] = per100(np.full_like(left, carried.fibre))
    if carried.sodium is not None:
        rows["salt"] = per100(np.full_like(left, carried.sodium * C.SALT_PER_SODIUM))
    parts = {
        "carbohydrate": rows["carbohydrate"],
        "protein": rows["protein"],
        "fat": rows.get("fat", np.zeros_like(left)),
        "alcohol": ethanol,
        "organic_acid": rows["organic_acids"],
        "fibre": rows.get("fibre", np.zeros_like(left)),
    }
    rows["energy_kcal"] = np.asarray(sum(C.ENERGY[k][0] * v for k, v in parts.items()))
    rows["energy_kj"] = np.asarray(sum(C.ENERGY[k][1] * v for k, v in parts.items()))
    lower = set(carried.lower)
    if carried.other_carbohydrate is None:
        lower.add("carbohydrate")
    if carried.fat is None or carried.fibre is None or lower & {"fat", "fibre", "carbohydrate"}:
        lower |= {"energy_kcal", "energy_kj"}
    return rows, frozenset(lower & rows.keys())
```

- [ ] **Step 4: Run** `tests/test_derived.py` → PASS (the energy invariant runs one prior ensemble per type: ~10–30 s).
- [ ] **Step 5: Commit** — `git add src/fermenttrack/prediction/derived.py tests/test_derived.py && git commit -m "Derived layer: nutrition per 100 g"`.

---

### Task 4: Derived layer — taste activities, phases, series and the sensory block

**Files:**
- Modify: `src/fermenttrack/prediction/derived.py`
- Test: `tests/test_derived.py` (append)

**Interfaces:**
- Consumes: Task 1 thresholds/sweetness/glutamate; Task 2 `TasteSpec`, `Boundary`, `Milestone.lens`; `inference.weighted_quantiles`; `engine.ACIDS`.
- Produces:
  - `Derived(values: dict[str, FloatArray], nutrition: dict[str, FloatArray], lower: frozenset[str], activity: dict[str, FloatArray], phases: tuple[str, ...] = ())` — `values` keys: `nut:energy_kcal, nut:sugars, nut:lactose, nut:organic_acids, nut:free_amino_acids, nut:alcohol, taste:sour, taste:sweet, taste:umami, taste:alcohol` (log10 activity) and `taste_phase` (phase index) when the profile has a ladder.
  - `evaluate(pools, ph, profile, carried, seed: int, co2_escapes: bool = True) -> Derived`
  - `taste_milestones(profile) -> tuple[Milestone, ...]`
  - `series_out(der, idx: NDArray[int], t_grid, w) -> list[dict]` (PredictionSeriesOut-shaped)
  - `sensory_block(der, t, w, idx, now_h: float, end_i: int) -> dict` (SensoryOut-shaped)
  - `META: dict[str, tuple[str, str, str]]`, `DERIVED_VERSION`, `DISCLAIMER`, `FAILED_WARNING`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_derived.py`):

```python
import math  # (at the top with the other imports)

from fermenttrack.prediction import compounds
from fermenttrack.prediction.priors import Z90


def _uniform(n: int) -> np.ndarray:
    return np.full(n, 1.0 / n)


def test_sweet_noticeable_share_is_the_threshold_distribution() -> None:
    n = 20000
    pools = _pools(1, n)
    pools[:, 0, PI["sucrose"]] = 3.0
    der = derived.evaluate(pools, np.full((n, 1), 6.0), PROFILES["kombucha"], derived.UNKNOWN, 1)
    share = float(np.mean(der.activity["sweet"][:, 0] > 1.0))
    prior = compounds.SWEET_THRESHOLD
    z = math.log(3.0 / prior.median) / (math.log(prior.hi / prior.median) / Z90)
    assert share == pytest.approx(0.5 * (1 + math.erf(z / math.sqrt(2))), abs=0.01)


def test_sour_counts_protonated_acid_not_total_acid() -> None:
    pools = _pools(2)
    pools[0, :, PI["lactic_acid"]] = 9.0  # 0.1 mol/kg
    der = derived.evaluate(
        pools, np.array([[3.0, 6.0]]), PROFILES["lacto_ferment"], derived.UNKNOWN, 1
    )
    sour = der.activity["sour"][0]
    assert sour[0] > 50 * sour[1]  # 88 % protonated at pH 3, 0.7 % at pH 6


def test_kombucha_ladder_climbs_with_the_sugar_acid_balance() -> None:
    n = 4000
    pools = _pools(3, n)
    pools[:, :, PI["sucrose"]] = [70.0, 20.0, 5.0]
    pools[:, :, PI["acetic_acid"]] = [0.7, 1.5, 12.0]
    der = derived.evaluate(pools, np.full((n, 3), 3.5), PROFILES["kombucha"], derived.UNKNOWN, 2)
    block = derived.sensory_block(der, np.array([0.0, 1.0, 2.0]), _uniform(n), np.arange(3), 1.0, 2)
    tp = block["taste_phases"]
    prob = np.array([tp["prob"][name] for name in tp["vocabulary"]])
    assert np.allclose(prob.sum(axis=0), 1.0)
    assert list(prob.argmax(axis=0)) == [0, 1, 3]  # sweet, balanced, vinegary


def test_now_past_the_window_clamps_to_the_end() -> None:
    pools = _pools(3)
    der = derived.evaluate(pools, np.full((1, 3), 6.0), PROFILES["kefir"], derived.UNKNOWN, 3)
    block = derived.sensory_block(der, np.array([0.0, 5.0, 10.0]), _uniform(1), np.arange(3), 99.0, 2)
    assert block["now_h"] == block["end_h"] == 10.0


def test_label_rows_and_series() -> None:
    pools = _pools(2, 8)
    pools[:, :, PI["lactose"]] = [48.0, 30.0]
    pools[:, :, PI["lactic_acid"]] = [0.0, 8.0]
    der = derived.evaluate(pools, np.full((8, 2), 4.5), PROFILES["kefir"], derived.UNKNOWN, 4)
    block = derived.sensory_block(der, np.array([0.0, 24.0]), _uniform(8), np.arange(2), 24.0, 1)
    rows = {r["key"]: r for r in block["nutrition_label"]}
    assert rows["lactose"]["start"]["p50"] == pytest.approx(4.8)
    assert rows["fat"]["start"] is None and rows["energy_kcal"]["now"]["lower_bound"]
    assert "alcohol" not in rows  # optional rows with nothing in them are left out
    keys = {s["key"] for s in derived.series_out(der, np.arange(2), np.array([0.0, 24.0]), _uniform(8))}
    assert {"taste:sour", "nut:lactose", "nut:energy_kcal"} <= keys
    assert "taste:umami" not in keys  # no free amino acids: below a tenth of the threshold
    ms = derived.taste_milestones(PROFILES["kefir"])
    assert [m.key for m in ms] == ["taste_tangy", "taste_sour"] and ms[0].lens == "taste"
```

- [ ] **Step 2: Run** → FAIL (`AttributeError: module 'derived' has no attribute 'evaluate'`).

- [ ] **Step 3: Implement** (extend `derived.py`; merge imports at the top):

```python
from typing import Any

from numpy.typing import NDArray

from fermenttrack.prediction.engine import ACIDS, PI
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.priors import FloatArray, Prior
from fermenttrack.prediction.profiles import FermentProfile, Milestone, TasteSpec

DERIVED_VERSION = "sensory-v1"
DISCLAIMER = (
    "Taste shows which tastes may be above their detection threshold for people tasting in "
    "water, not how it will taste to you. Spoilage off-flavours are not modelled: trust your "
    "nose and your pH reading over this view. Nutrition is a model estimate, not a lab "
    "analysis; not for labelling products for sale."
)
FAILED_WARNING = (
    "Taste and nutrition could not be computed for this batch; the forecast itself is "
    "unaffected."
)
ASSUMPTIONS = (
    "Per 100 g of what is in the jar: the CO₂ that escapes is subtracted; ethanol "
    "evaporation is ignored.",
    "Energy uses the EU labelling factors (Regulation (EU) 1169/2011, Annex XIV).",
    "Taste thresholds are measured in water; in a food other tastes mask each other, so "
    "real thresholds are higher.",
    "Glucose and fructose are one pool in the model, so their sweetness is uncertain.",
    "Not modelled yet: bitterness, fizz (dissolved CO₂), aroma.",
)
TASTES = ("sour", "sweet", "umami", "alcohol")
_ACID_IDX = np.array([PI[a] for a, _, _ in ACIDS])
_ACID_MW = np.array([mw for _, mw, _ in ACIDS])
# ponytail: pKa at I = 0; salt shifts it by <= 0.2 (engine.acid_ka), well inside the sour
# threshold's spread. Pass the batch's Ka' if a salty ferment ever needs it.
_ACID_KA = np.array([10.0**-pka for _, _, pka in ACIDS])
_LACTIC_MW = 90.08
FLOOR = -3.0  # log10 activity floor (a thousandth of the threshold): keeps log axes finite

# Displayed series: key -> (label, group, unit). Constant rows are label-only.
META: dict[str, tuple[str, str, str]] = {
    "nut:energy_kcal": ("Energy", "nutrition", "kcal/100 g"),
    "nut:sugars": ("Sugars", "nutrition", "g/100 g"),
    "nut:lactose": ("Lactose", "nutrition", "g/100 g"),
    "nut:organic_acids": ("Organic acids", "nutrition", "g/100 g"),
    "nut:free_amino_acids": ("Free amino acids", "nutrition", "g/100 g"),
    "nut:alcohol": ("Alcohol", "nutrition", "% ABV"),
    "taste:sour": ("Sour", "taste", "× threshold"),
    "taste:sweet": ("Sweet", "taste", "× threshold"),
    "taste:umami": ("Umami", "taste", "× threshold"),
    "taste:alcohol": ("Alcohol", "taste", "× threshold"),
}
# A series is shown only if its 95th percentile ever reaches this (absent: always shown).
_SHOW_IF = {
    "nut:lactose": 0.05, "nut:free_amino_acids": 0.05, "nut:alcohol": 0.05,
    "taste:sweet": -1.0, "taste:umami": -1.0, "taste:alcohol": -1.0,
}  # fmt: skip
_OPTIONAL_ROWS = {"lactose", "free_amino_acids", "alcohol"}  # left out when always ~0


@dataclass
class Derived:
    values: dict[str, FloatArray]  # (N, T): "nut:*" per 100 g, "taste:*" log10 activity,
    #                                "taste_phase" (phase index) when there is a ladder
    nutrition: dict[str, FloatArray]  # label row -> (N, T); unknown rows absent
    lower: frozenset[str]  # label rows that are lower bounds
    activity: dict[str, FloatArray]  # taste -> (N, T) concentration / threshold
    phases: tuple[str, ...] = ()


def _draws(n: int, spec: TasteSpec | None, seed: int) -> dict[str, FloatArray]:
    """Per-member thresholds, sweetness factors, glutamate share and ladder boundaries:
    nothing observes them, so prior draws are their posterior. Shaped (N, 1)."""
    priors: dict[str, Prior] = {
        "sweet": C.SWEET_THRESHOLD, "sour": C.SOUR_THRESHOLD,
        "umami": C.UMAMI_THRESHOLD, "alcohol": C.ALCOHOL_THRESHOLD,
        **{f"x:{k}": v for k, v in C.SWEETNESS.items()},
        "glu": C.GLUTAMATE_SHARE[spec.glutamate if spec else "soy"],
    }  # fmt: skip
    if spec is not None:
        priors.update({f"b{i}": b.threshold for i, b in enumerate(spec.boundaries)})
    z = np.random.default_rng(seed).standard_normal((n, len(priors)))
    return {k: np.asarray(p.value(z[:, j]))[:, None] for j, (k, p) in enumerate(priors.items())}


def evaluate(
    pools: FloatArray, ph: FloatArray, profile: FermentProfile, carried: Carried, seed: int,
    co2_escapes: bool = True,
) -> Derived:  # fmt: skip
    """Nutrition and taste for every member at every time of the trajectory."""
    rows, lower = nutrition(pools, carried, co2_escapes)
    spec = profile.taste
    d = _draws(pools.shape[0], spec, seed)
    left = mass_left(pools, co2_escapes)

    def p(k: str) -> FloatArray:
        return np.asarray(pools[:, :, PI[k]])

    sweet_raw = sum(d[f"x:{k}"] * p(k) for k in SUGARS)  # g sucrose-equivalent / kg start
    h = np.asarray(10.0**-ph)[..., None]  # mol/kg ~ mol/L
    mol = np.maximum(pools[:, :, _ACID_IDX], 0.0) / _ACID_MW  # (N, T, 3) mol/kg
    protonated = np.sum(mol * h / (h + _ACID_KA), axis=2)
    activity = {
        "sour": np.asarray((protonated + h[..., 0]) * 1000.0 / left / d["sour"]),
        "sweet": np.asarray(sweet_raw / left / d["sweet"]),
        "umami": np.asarray(p("amino_acids") * d["glu"] / C.GLUTAMATE_MW * 1000.0 / left / d["umami"]),
        "alcohol": np.asarray(rows["alcohol"] / d["alcohol"]),
    }
    values = {
        f"nut:{k}": rows[k]
        for k in ("energy_kcal", "sugars", "lactose", "organic_acids", "free_amino_acids", "alcohol")
    }
    values.update(
        {f"taste:{k}": np.log10(np.maximum(a, 10.0**FLOOR)) for k, a in activity.items()}
    )
    if spec is None:
        return Derived(values, rows, lower, activity)
    acids = p("lactic_acid") + p("acetic_acid") + p("gluconic_acid")
    metrics = {
        "sugar_acid": np.asarray(sweet_raw / np.maximum(acids, 1e-3)),  # g/g, both per kg
        "acetic": np.asarray(p("acetic_acid") / left),
        "acidity_pct": np.asarray(np.sum(mol, axis=2) * _LACTIC_MW / (10.0 * left)),
        "umami": activity["umami"],
    }
    phase = np.zeros_like(left)
    ok = np.ones(left.shape, dtype=bool)
    for i, b in enumerate(spec.boundaries):
        m, thr = metrics[b.metric], d[f"b{i}"]
        ok &= (m > thr) if b.kind == "above" else (m < thr)
        phase += ok
    values["taste_phase"] = phase
    return Derived(values, rows, lower, activity, spec.phases)


def taste_milestones(profile: FermentProfile) -> tuple[Milestone, ...]:
    """One loose milestone per taste phase after the first: first time a member is there."""
    spec = profile.taste
    if spec is None:
        return ()
    return tuple(
        Milestone(
            f"taste_{name.replace(' ', '_')}", f"{name.capitalize()} phase", note,
            "taste_phase", "above", k - 0.5, lens="taste",
        )  # fmt: skip
        for k, (name, note) in enumerate(zip(spec.phases[1:], spec.notes, strict=True), start=1)
    )


def series_out(
    der: Derived, idx: NDArray[np.intp], t_grid: FloatArray, w: FloatArray
) -> list[dict[str, Any]]:
    """PredictionSeriesOut-shaped bands on the display grid (`idx` into the trajectory)."""
    out: list[dict[str, Any]] = []
    for key, (label, group, unit) in META.items():
        v = der.values.get(key)
        if v is None:
            continue
        q = weighted_quantiles(v[:, idx], w, (0.05, 0.5, 0.95))
        if key in _SHOW_IF and float(np.max(q[2])) < _SHOW_IF[key]:
            continue
        digits = 0 if key == "nut:energy_kcal" else 2
        out.append(
            {
                "key": key, "label": label, "unit": unit, "group": group,
                "t_h": [round(float(x), 3) for x in t_grid],
                "p05": [round(float(x), digits) for x in q[0]],
                "p50": [round(float(x), digits) for x in q[1]],
                "p95": [round(float(x), digits) for x in q[2]],
            }
        )  # fmt: skip
    return out


def sensory_block(
    der: Derived, t: FloatArray, w: FloatArray, idx: NDArray[np.intp], now_h: float,
    end_i: int,
) -> dict[str, Any]:  # fmt: skip
    """PredictionOut.sensory. `t` is the trajectory's time axis, `idx` the display grid in
    it, `end_i` the last index inside the window; "now" clamps into [0, end_i]."""
    wn = w / w.sum()
    i_now = int(np.clip(np.searchsorted(t, now_h + 1e-9, side="right") - 1, 0, end_i))
    points = (("start", 0), ("now", i_now), ("end", end_i))

    def cell(v: FloatArray, i: int, key: str) -> dict[str, Any]:
        q = weighted_quantiles(v[:, i], w, (0.05, 0.5, 0.95))
        return {
            "p05": round(float(q[0]), 2), "p50": round(float(q[1]), 2),
            "p95": round(float(q[2]), 2), "lower_bound": key in der.lower,
        }  # fmt: skip

    label = []
    for key, name, unit in LABEL_ROWS:
        v = der.nutrition.get(key)
        cells = {when: (cell(v, i, key) if v is not None else None) for when, i in points}
        if key in _OPTIONAL_ROWS and all(c is not None and c["p95"] < 0.01 for c in cells.values()):
            continue
        label.append({"key": key, "label": name, "unit": unit, **cells})
    phases = None
    if der.phases:
        at = der.values["taste_phase"][:, idx]
        phases = {
            "vocabulary": list(der.phases),
            "t_h": [round(float(x), 3) for x in t[idx]],
            "prob": {
                name: [round(float(x), 3) for x in wn @ (at == k)]
                for k, name in enumerate(der.phases)
            },
        }
    noticeable = {
        when: {k: round(float(wn[der.activity[k][:, i] > 1.0].sum()), 3) for k in TASTES}
        for when, i in points[1:]
    }
    return {
        "derived_version": DERIVED_VERSION,
        "validated": False,
        "disclaimer": DISCLAIMER,
        "now_h": round(float(t[i_now]), 3),
        "end_h": round(float(t[end_i]), 3),
        "taste_phases": phases,
        "nutrition_label": label,
        "noticeable": noticeable,
        "assumptions": list(ASSUMPTIONS),
    }
```

- [ ] **Step 4: Run** `tests/test_derived.py -q`, then `ruff check src/fermenttrack/prediction/derived.py` and `mypy src/fermenttrack/prediction/derived.py src/fermenttrack/prediction/compounds.py src/fermenttrack/prediction/profiles.py` → all pass (fix types inline if mypy objects; no `type: ignore` without a reason comment).
- [ ] **Step 5: Commit** — `git commit -am "Derived layer: taste activities, phases, series and the sensory block"`.

---

### Task 5: Wire the derived layer into the forecast service and the API schema

**Files:**
- Modify: `src/fermenttrack/prediction/service.py` (`_Initial`, `_initial_state`, `_milestone`, `_forecast`)
- Modify: `src/fermenttrack/schemas.py` (`PredictionSeriesOut.group`, `PredictionMilestoneOut.lens`, new `Sensory*Out`, `PredictionOut.sensory`)
- Modify: `tests/test_prediction_endpoint.py` (assert the block passes the response model)
- Test: `tests/test_prediction_sensory.py`

**Interfaces:**
- Consumes: Task 4 `evaluate`, `series_out`, `sensory_block`, `taste_milestones`, `FAILED_WARNING`; Task 3 `Carried`, `UNKNOWN`.
- Produces: `_Initial.carried: Carried`; forecast dict key `"sensory"` (dict or None); milestone dicts gain `"lens"`; `service._milestone` unchanged signature (bake reuses it).

- [ ] **Step 1: Write the failing tests** — `tests/test_prediction_sensory.py`:

```python
"""Taste and nutrition in the forecast (service path)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction import derived, service
from fermenttrack.prediction.service import OrganismIn, PredictionInputs, RecipeIn, predict

CABBAGE = {
    "water": 92.2, "protein": 1.28, "carbohydrate": 5.8, "fiber": 2.5, "sugars_total": 3.2,
    "sucrose": 0.08, "glucose": 1.67, "fructose": 1.45, "sodium": 0.018,
}  # fmt: skip
SALT = {"water": 0.2, "sodium": 38.8}


@pytest.fixture(autouse=True)
def _fresh() -> None:
    service.clear_caches()


def _inputs(
    ferment: str, temp: float | None = None, recipe: tuple[RecipeIn, ...] = (),
    organisms: list[str] | None = None, now_h: float = 0.0,
) -> PredictionInputs:  # fmt: skip
    names = organisms if organisms is not None else FERMENTATION_TYPE_ORGANISMS[ferment]
    return PredictionInputs(
        fermentation_type=ferment, now_h=now_h, expected_temperature_c=temp,
        organisms=tuple(OrganismIn(n, ORGANISMS.get(n, "bacteria"), ()) for n in names),
        organism_source="default" if organisms is None else "custom",
        recipe=recipe, measurements=(),
    )  # fmt: skip


def _phase_prob(body: dict[str, Any], name: str, i: int) -> float:
    return float(body["sensory"]["taste_phases"]["prob"][name][i])


def _row(body: dict[str, Any], key: str) -> dict[str, Any]:
    return next(r for r in body["sensory"]["nutrition_label"] if r["key"] == key)


def test_sauerkraut_is_sour_by_two_weeks() -> None:
    # Pederson & Albury: 1.5-2.3 % acidity at day 14 (18 °C)
    body = predict(_inputs("lacto_ferment", 18.0), horizon_h=14 * 24)
    assert _phase_prob(body, "fresh", 0) > 0.9
    assert _phase_prob(body, "sour", -1) > 0.5


def test_kombucha_leaves_the_sweet_phase() -> None:
    body = predict(_inputs("kombucha", 24.0), horizon_h=21 * 24)
    assert _phase_prob(body, "sweet", 0) > 0.9
    assert _phase_prob(body, "sweet", -1) < 0.2


def test_kefir_is_tangy_within_a_day() -> None:
    # Irigoyen et al. 2005: 0.8-1 % lactic acid at 24 h
    body = predict(_inputs("kefir", 22.0), horizon_h=24)
    assert _phase_prob(body, "tangy", -1) + _phase_prob(body, "sour", -1) > 0.7


def test_kombucha_alcohol_in_the_published_range() -> None:
    # Chen & Liu 2000, Jayabalan 2007: a few g/L ethanol, i.e. ~0.1-1.5 % ABV
    body = predict(_inputs("kombucha", 24.0), horizon_h=10 * 24)
    assert 0.1 <= _row(body, "alcohol")["end"]["p50"] <= 1.5


def test_recipe_nutrients_carry_through() -> None:
    recipe = (
        RecipeIn("Cabbage", 1000, "g", CABBAGE, "base"),
        RecipeIn("Salt", 20, "g", SALT, "additive"),
    )
    body = predict(_inputs("lacto_ferment", 18.0, recipe), horizon_h=7 * 24)
    salt = (1000 * 0.018 + 20 * 38.8) / 100 * 2.5 / 1020 * 100  # g/100 g at the start
    assert _row(body, "salt")["start"]["p50"] == pytest.approx(salt, rel=0.02)
    assert _row(body, "fat")["start"] is None  # cabbage here reports no fat: unknown
    groups = {s["group"] for s in body["series"]}
    assert {"taste", "nutrition"} <= groups
    assert any(m["lens"] == "taste" for m in body["milestones"])
    assert all(m["lens"] in ("process", "taste", "nutrition") for m in body["milestones"])


def test_typical_recipe_nutrition_is_partial() -> None:
    body = predict(_inputs("lacto_ferment", 18.0), horizon_h=7 * 24)
    assert _row(body, "fat")["start"] is None and _row(body, "salt")["start"] is not None
    assert _row(body, "energy_kcal")["start"]["lower_bound"]


def test_what_if_moves_taste() -> None:
    base = predict(_inputs("kombucha", 24.0), horizon_h=14 * 24)
    warm = predict(_inputs("kombucha", 24.0), temperature_c=30.0, horizon_h=14 * 24)
    assert warm["sensory"] is not None
    assert warm["sensory"]["taste_phases"] != base["sensory"]["taste_phases"]


def test_koji_has_no_taste_ladder() -> None:
    body = predict(_inputs("koji", 30.0), horizon_h=48)
    assert body["sensory"]["taste_phases"] is None
    assert not [m for m in body["milestones"] if m["lens"] == "taste"]
    assert _row(body, "carbohydrate")["start"] is not None


def test_unmodelled_organisms_still_get_a_label() -> None:
    body = predict(_inputs("lacto_ferment", 18.0, organisms=["Nonexistent bacterium"]))
    assert body["sensory"]["nutrition_label"]


def test_forecast_survives_a_derived_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    good = predict(_inputs("kefir", 22.0), horizon_h=24)
    service.clear_caches()

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(derived, "evaluate", boom)
    bad = predict(_inputs("kefir", 22.0), horizon_h=24)
    assert bad["sensory"] is None and derived.FAILED_WARNING in bad["warnings"]
    kinetic = lambda b: [s for s in b["series"] if s["group"] not in ("taste", "nutrition")]  # noqa: E731
    assert kinetic(bad) == kinetic(good)  # the solve is unchanged by the derived layer
    assert np.isfinite(bad["series"][0]["p50"][-1])
```

Append to `tests/test_prediction_endpoint.py::test_prediction_endpoint` after the body is read:

```python
    assert body["sensory"]["derived_version"] == "sensory-v1"
    assert body["sensory"]["validated"] is False
    assert all("lens" in m for m in body["milestones"])
```

- [ ] **Step 2: Run** both files → FAIL (`KeyError: 'sensory'`).

- [ ] **Step 3: Implement**

`service.py`:

```python
import logging
...
from fermenttrack.prediction import derived
...
logger = logging.getLogger(__name__)
```

`_Initial` gains `carried: derived.Carried = field(default_factory=lambda: derived.UNKNOWN)`.

In `_initial_state`: track carried nutrients next to the pools.

```python
    carried = {"fat": 0.0, "fiber": 0.0, "sodium": 0.0, "carbohydrate": 0.0}
    reported: set[str] = set()  # nutrients at least one mapped ingredient reports
    partial: set[str] = set()  # ... and those some mapped ingredient does not report
    # in the loop, in the salt branch before `continue`:
            carried["sodium"] += n.get("sodium", 39.3) * grams / 100.0  # NaCl is 39.3 % Na
            reported.add("sodium")
    # after `mapped += grams; f = grams / 100.0`:
        for nk in carried:
            if nk in n:
                carried[nk] += n[nk] * f
                reported.add(nk)
            else:
                partial.add(nk)
```

In the recipe branch after `pools0` is computed:

```python
        def per_kg(nk: str) -> float | None:
            return carried[nk] / kg if nk in reported else None

        tracked = sum(pools0.get(k, 0.0) for k in (*SUGAR_KEYS, "starch"))
        carb, fibre = per_kg("carbohydrate"), per_kg("fiber")
        names = {"fat": "fat", "fiber": "fibre", "sodium": "salt", "carbohydrate": "carbohydrate"}
        lower = {names[k] for k in partial} | (set(names.values()) if unmapped else set())
        init_carried = derived.Carried(
            fat=per_kg("fat"),
            fibre=fibre,
            sodium=per_kg("sodium"),
            # what the model does not track: inaccessible starch, oligosaccharides, ...
            other_carbohydrate=None if carb is None else max(carb - (fibre or 0.0) - tracked, 0.0),
            lower=frozenset(lower),
        )
```

and pass `carried=init_carried` to that `_Initial(...)`. In the typical-recipe branch pass `carried=derived.Carried(sodium=salt_g * 0.393 if salt_g else None)` (the typical recipe is per kg; its salt is the only carried nutrient it knows).

`_milestone`: add `"lens": ms.lens,` to the returned dict.

`_forecast`, right after `values = _series_values(...)` and the `keep` update:

```python
    der: derived.Derived | None = None
    try:
        der = derived.evaluate(
            tr.pools, tr.ph, profile, init.carried, seed=seed + 1,
            co2_escapes=profile.co2_escapes,
        )  # fmt: skip
    except Exception:  # the derived layer must never break a forecast
        logger.exception("derived layer failed for a %s batch", profile.type)
```

After the kinetic series are filtered (`series = [s for s in series if s["key"] not in drop]`):

```python
    if der is not None:
        series += derived.series_out(der, grid_idx, t_grid, weights)
```

Milestones: replace the `window`/`milestones` block with

```python
    every = {**values, **(der.values if der is not None else {})}
    window = {k: v[:, :in_window] for k, v in every.items()}
    milestones = [
        m
        for ms in (*profile.milestones, *derived.taste_milestones(profile))
        if (m := _milestone(ms, t_eval[:in_window], window, weights)) is not None
    ]
```

Warnings: after the existing warnings, `if der is None: warnings.append(derived.FAILED_WARNING)`. Result dict: add

```python
        "sensory": (
            derived.sensory_block(der, t_eval, weights, grid_idx, inputs.now_h, in_window - 1)
            if der is not None
            else None
        ),
```

`schemas.py`:

```python
class PredictionSeriesOut(BaseModel):
    ...
    group: Literal[
        "ph", "density", "substrates", "products", "growth", "population", "rise", "acidity",
        "nutrition", "taste",
    ]


class PredictionMilestoneOut(BaseModel):
    ...
    lens: Literal["process", "taste", "nutrition"] = "process"  # forecast-panel lens


class NutritionCellOut(BaseModel):
    p05: float
    p50: float
    p95: float
    lower_bound: bool  # "≥": some ingredient has no data for it


class NutritionRowOut(BaseModel):
    key: str
    label: str
    unit: str
    start: NutritionCellOut | None  # None: unknown (no ingredient reports it)
    now: NutritionCellOut | None
    end: NutritionCellOut | None


class TastePhasesOut(BaseModel):
    vocabulary: list[str]  # ordered, mild -> strong
    t_h: list[float]
    prob: dict[str, list[float]]  # phase -> P(most members' phase) per t_h


class SensoryOut(BaseModel):
    # Taste and nutrition derived from the same ensemble (spec 2026-10-02); a model estimate.
    derived_version: str
    validated: bool
    disclaimer: str
    now_h: float
    end_h: float
    taste_phases: TastePhasesOut | None
    nutrition_label: list[NutritionRowOut]
    noticeable: dict[str, dict[str, float]]  # "now"/"end" -> taste -> P(above threshold)
    assumptions: list[str]
```

and `PredictionOut` gains `sensory: SensoryOut | None = None` (after `summary`).

- [ ] **Step 4: Run** `tests/test_prediction_sensory.py tests/test_prediction_endpoint.py tests/test_prediction_service.py tests/test_prediction_trajectories.py -q` → PASS. If a calibration assertion fails, check the boundary prior against its published source first (Task 2); never loosen an assertion without a source.
- [ ] **Step 5: Commit** — `git commit -am "Forecast: taste and nutrition from the derived layer"` (add the new test file).

---

### Task 6: Sourdough plans (bake path)

**Files:**
- Modify: `src/fermenttrack/prediction/bake.py` (`_forecast`)
- Test: `tests/test_sourdough_engine.py` (append)

**Interfaces:**
- Consumes: Task 4 functions; `service._milestone` (import as `_service_milestone`); `profiles.profile_for`.
- Produces: the bake forecast dict gains `"sensory"`; taste milestones from the sourdough ladder.

- [ ] **Step 1: Write the failing test** (append):

```python
def test_a_plan_gets_taste_and_nutrition() -> None:
    out = _run(_levain("levain_liquide", 3, 26))
    assert out["sensory"]["taste_phases"]["vocabulary"] == ["mild", "tangy", "sharp"]
    assert any(s["key"] == "taste:sour" for s in out["series"])
    carb = next(r for r in out["sensory"]["nutrition_label"] if r["key"] == "carbohydrate")
    assert carb["start"]["lower_bound"]  # a plan logs no recipe composition
```

- [ ] **Step 2: Run** → FAIL (`KeyError: 'sensory'`).
- [ ] **Step 3: Implement** in `bake._forecast`, after `series = _series(...)`:

```python
    sd_profile = profile_for("sourdough")
    der: derived.Derived | None = None
    try:  # a dough keeps its gas, and a plan logs no recipe composition
        der = derived.evaluate(
            tr.pools, tr.ph, sd_profile, derived.UNKNOWN, seed=seed + 1, co2_escapes=False
        )
    except Exception:  # never break a bake forecast on the derived layer
        logger.exception("derived layer failed for a sourdough plan")
        warnings.append(derived.FAILED_WARNING)
    if der is not None:
        series += derived.series_out(der, gi, t_eval[gi], w)
        milestones += [
            m
            for ms in derived.taste_milestones(sd_profile)
            if (m := _service_milestone(ms, t_eval, der.values, w)) is not None
        ]
```

and in the returned dict: `"sensory": derived.sensory_block(der, t_eval, w, gi, inputs.now_h, len(t_eval) - 1) if der is not None else None,`. Imports: `import logging`, `logger = logging.getLogger(__name__)`, `from fermenttrack.prediction import derived, population`, `from fermenttrack.prediction.profiles import profile_for`, and add `_milestone as _service_milestone` to the existing `from fermenttrack.prediction.service import (...)`.

- [ ] **Step 4: Run** `tests/test_sourdough_engine.py tests/test_sourdough_api.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -am "Sourdough plans: taste and nutrition"`.

---

### Task 7: Frontend helpers and value formatting

**Files:**
- Create: `frontend/src/prediction/sensory.js`, `frontend/src/prediction/sensory.check.mjs`
- Modify: `frontend/src/prediction/format.js` (`fmtValue`, `unitSuffix`)

**Interfaces:**
- Produces (`sensory.js`): `LENSES`, `lensOf(m)`, `PHASE_HEX`, `phaseColor(k, n)`, `mixHex(a, b, f)`, `phaseRuns(tp)`, `phaseSpans(runs)`, `indexAt(grid, t)`, `fmtNum(v, unit)`, `cellText(cell, unit)`, `changeText(start, now)`, `jarSummary(sensory, which)`, `likelihood(p)`. (`format.js`): `timesThreshold(log10v)`; `fmtValue(v, "× threshold")` → `"×250"`; `unitSuffix("× threshold")` → `""`.

- [ ] **Step 1: Write the failing check** — `frontend/src/prediction/sensory.check.mjs`:

```js
// Self-check for sensory.js (no test runner in this frontend): node src/prediction/sensory.check.mjs
import assert from "node:assert/strict";
import { fmtValue, timesThreshold, unitSuffix } from "./format.js";
import {
  cellText, changeText, indexAt, jarSummary, lensOf, mixHex, phaseColor, phaseRuns, phaseSpans,
} from "./sensory.js";

const tp = {
  vocabulary: ["sweet", "balanced", "tart"],
  t_h: [0, 24, 48, 72],
  prob: { sweet: [1, 0.55, 0.1, 0], balanced: [0, 0.45, 0.7, 0.2], tart: [0, 0, 0.2, 0.8] },
};
const runs = phaseRuns(tp);
assert.deepEqual(runs.map((r) => r.name), ["sweet", "sweet", "balanced", "tart"]);
assert.equal(runs[1].k2, 1);
assert.deepEqual(
  phaseSpans(runs).map((s) => [s.name, s.start_h, s.end_h]),
  [["sweet", 0, 48], ["balanced", 48, 72], ["tart", 72, 72]],
);
assert.equal(indexAt([0, 24, 48], 30), 1);
assert.equal(indexAt([0, 24, 48], -5), 0);
assert.equal(phaseColor(0, 2), "#184f95");
assert.equal(phaseColor(1, 2), "#b7d3f6");
assert.equal(mixHex("#000000", "#ffffff", 0.5), "#808080");

assert.deepEqual(cellText({ p05: 3.1, p50: 4.12, p95: 5.0, lower_bound: false }, "g"), { value: "4.1", range: "3.1–5.0" });
assert.deepEqual(cellText({ p05: 30, p50: 31.4, p95: 33, lower_bound: true }, "kcal"), { value: "≥ 31", range: "30–33" });
assert.deepEqual(cellText(null, "g"), { value: "–", range: null });
assert.equal(changeText({ p50: 4.8 }, { p50: 2.4 }), "−50 %");
assert.equal(changeText({ p50: 0 }, { p50: 2.4 }), null);

assert.equal(timesThreshold(2.4), "×251");
assert.equal(timesThreshold(0.2), "×1.6");
assert.equal(timesThreshold(-1), "×0.10");
assert.equal(fmtValue(2.4, "× threshold", 3), "×251");
assert.equal(unitSuffix("× threshold"), "");

assert.equal(lensOf({}), "process");
const sensory = {
  now_h: 30, end_h: 72, taste_phases: tp,
  noticeable: { now: { sour: 0.9, sweet: 0.6, umami: 0.01, alcohol: 0.2 }, end: { sour: 1, sweet: 0.3 } },
  nutrition_label: [{ key: "sugars", now: { p50: 4.1 }, end: { p50: 1 } }],
};
const now = jarSummary(sensory, "now");
assert.equal(now.phase.name, "sweet");
assert.deepEqual(now.tastes, ["sour", "sweet"]);
assert.equal(now.sugars.p50, 4.1);
assert.equal(jarSummary(sensory, "end").phase.name, "tart");
console.log("sensory.check: ok");
```

- [ ] **Step 2: Run** `node frontend/src/prediction/sensory.check.mjs` → FAIL (`Cannot find module ./sensory.js`).

- [ ] **Step 3: Implement**

`format.js`:

```js
export const THRESHOLD_UNIT = "× threshold";

// A log10 activity (concentration / detection threshold) as "×250".
export function timesThreshold(log10v) {
  const x = 10 ** log10v;
  if (x >= 10) return `×${Math.round(x)}`;
  if (x >= 1) return `×${x.toFixed(1)}`;
  return `×${x.toFixed(2)}`;
}

export function fmtValue(v, unit, span) {
  if (v == null || Number.isNaN(v)) return "–";
  if (unit === THRESHOLD_UNIT) return timesThreshold(v);
  return v.toFixed(decimalsFor(unit, span));
}

export function unitSuffix(unit) {
  if (!unit || unit === "SG" || unit === THRESHOLD_UNIT) return "";
  return ` ${unit}`;
}
```

`sensory.js`:

```js
// Pure helpers for the Taste & aroma and Nutrition lenses (no React).
// Self-check: node src/prediction/sensory.check.mjs

export const LENSES = [
  { id: "process", label: "Process" },
  { id: "taste", label: "Taste & aroma" },
  { id: "nutrition", label: "Nutrition" },
];

export const lensOf = (m) => m.lens ?? "process";

// Ordinal ramp for taste phases (blue 600/450/300/150), validated with the dataviz
// validator: --ordinal --mode dark --surface #191612 (monotone L, light end 2.22:1).
export const PHASE_HEX = ["#184f95", "#2a78d6", "#6da7ec", "#b7d3f6"];

// Spread n phases over the ramp so 2 phases use both ends.
export function phaseColor(k, n) {
  const i = n <= 1 ? 0 : Math.round((k * (PHASE_HEX.length - 1)) / (n - 1));
  return PHASE_HEX[i];
}

export function mixHex(a, b, f) {
  const ch = (h, i) => parseInt(h.slice(1 + 2 * i, 3 + 2 * i), 16);
  const c = [0, 1, 2].map((i) => Math.round(ch(a, i) + (ch(b, i) - ch(a, i)) * f));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

// Most likely phase per grid point, with the runner-up (for blending a transition).
export function phaseRuns(tp) {
  if (!tp?.vocabulary?.length) return [];
  return tp.t_h.map((t_h, i) => {
    const ps = tp.vocabulary.map((name, k) => ({ k, name, p: tp.prob[name][i] })).sort((a, b) => b.p - a.p);
    return { t_h, k: ps[0].k, name: ps[0].name, p: ps[0].p, k2: ps[1]?.k ?? ps[0].k, p2: ps[1]?.p ?? 0 };
  });
}

// Contiguous spans of one most-likely phase; each ends where the next starts.
export function phaseSpans(runs) {
  const spans = [];
  for (const r of runs) {
    const last = spans[spans.length - 1];
    if (last && last.k === r.k) last.end_h = r.t_h;
    else spans.push({ k: r.k, name: r.name, start_h: r.t_h, end_h: r.t_h });
  }
  for (let i = 0; i + 1 < spans.length; i++) spans[i].end_h = spans[i + 1].start_h;
  return spans;
}

// Index of the last grid point at or before t (0 when t is before the grid).
export function indexAt(grid, t) {
  let i = 0;
  while (i + 1 < grid.length && grid[i + 1] <= t) i++;
  return i;
}

export function fmtNum(v, unit) {
  if (unit === "kJ" || unit === "kcal") return String(Math.round(v));
  return Math.abs(v) < 1 ? v.toFixed(2) : v.toFixed(1);
}

export function cellText(cell, unit) {
  if (!cell) return { value: "–", range: null };
  const lo = fmtNum(cell.p05, unit);
  const hi = fmtNum(cell.p95, unit);
  return { value: `${cell.lower_bound ? "≥ " : ""}${fmtNum(cell.p50, unit)}`, range: lo === hi ? null : `${lo}–${hi}` };
}

export function changeText(start, now) {
  if (!start || !now || Math.abs(start.p50) < 1e-9) return null;
  const pct = Math.round((now.p50 / start.p50 - 1) * 100);
  return pct === 0 ? null : `${pct > 0 ? "+" : "−"}${Math.abs(pct)} %`;
}

export const likelihood = (p) => (p >= 0.8 ? "likely" : p >= 0.5 ? "probably" : "possibly");

// "In the jar" at now or at the window's end: phase, noticeable tastes, three key rows.
export function jarSummary(sensory, which) {
  const t = which === "now" ? sensory.now_h : sensory.end_h;
  const tp = sensory.taste_phases;
  const r = tp ? phaseRuns(tp)[indexAt(tp.t_h, t)] : null;
  const row = (key) => sensory.nutrition_label.find((x) => x.key === key)?.[which] ?? null;
  return {
    t_h: t,
    phase: r ? { name: r.name, k: r.k, p: r.p, n: tp.vocabulary.length } : null,
    tastes: Object.entries(sensory.noticeable?.[which] || {})
      .filter(([, p]) => p >= 0.5)
      .sort((a, b) => b[1] - a[1])
      .map(([k]) => k),
    sugars: row("sugars"),
    alcohol: row("alcohol"),
    energy: row("energy_kcal"),
  };
}
```

- [ ] **Step 4: Run** `node frontend/src/prediction/sensory.check.mjs` → `sensory.check: ok`.
- [ ] **Step 5: Commit** — `git add frontend/src/prediction/sensory.js frontend/src/prediction/sensory.check.mjs frontend/src/prediction/format.js && git commit -m "Frontend helpers for the taste and nutrition lenses"`.

---

### Task 8: Taste and Nutrition lens components

**Files:**
- Create: `frontend/src/prediction/TasteAroma.jsx`, `frontend/src/prediction/Nutrition.jsx`
- Modify: `frontend/src/prediction/ForecastChart.jsx` (export `useWidth`; `tone: "neutral"` reference lines), `frontend/src/prediction/prediction.css` (`--viz-ref-neutral`)

**Interfaces:**
- Consumes: Task 7 helpers; `renderChart(c, refs)` from `PredictionPanel` (Task 9).
- Produces: `<TasteAroma data charts renderChart hoverIndex onHover timeUnit />`, `<Nutrition sensory charts renderChart />`.

- [ ] **Step 1: ForecastChart and CSS** — `export function useWidth(ref)`; reference line stroke `style={{ stroke: r.tone === "neutral" ? "var(--viz-ref-neutral)" : "var(--viz-ref)" }}` with `strokeDasharray={r.tone === "neutral" ? "2 3" : "5 4"}`; line keys `r-${r.value}-${r.label}`. In `prediction.css` under `.ft-viz`: `--viz-ref-neutral: #8a7f6f; /* slate-500: an orientation line, not a warning */`.

- [ ] **Step 2: `TasteAroma.jsx`**

```jsx
import { useMemo, useRef } from "react";
import { useWidth } from "./ForecastChart.jsx";
import { timeLabel } from "./format.js";
import { linear, nearestIndex } from "./scale.js";
import { indexAt, mixHex, phaseColor, phaseRuns, phaseSpans } from "./sensory.js";

const M = { left: 36, right: 10 }; // aligned with ForecastChart's plot area
const THRESHOLD_LINE = [{ value: 0, label: "detection threshold", tone: "neutral" }];

function PhaseBand({ tp, nowH, horizonH, timeUnit, hoverIndex, onHover }) {
  const ref = useRef(null);
  const width = useWidth(ref);
  const runs = useMemo(() => phaseRuns(tp), [tp]);
  const spans = useMemo(() => phaseSpans(runs), [runs]);
  const n = tp.vocabulary.length;
  const innerW = Math.max(width - M.left - M.right, 10);
  const x = linear([0, horizonH], [M.left, M.left + innerW]);
  const i = hoverIndex ?? indexAt(tp.t_h, nowH);
  const split = tp.vocabulary
    .map((name) => ({ name, p: tp.prob[name][i] ?? 0 }))
    .filter((s) => s.p >= 0.05)
    .sort((a, b) => b.p - a.p);
  const fill = (r) =>
    r.p >= 0.6 ? phaseColor(r.k, n) : mixHex(phaseColor(r.k, n), phaseColor(r.k2, n), r.p2 / (r.p + r.p2));
  const summary = `Taste phase over time: ${spans
    .map((s) => `${s.name} from ${timeLabel(s.start_h, timeUnit)}`)
    .join(", ")}. Model estimate.`;
  const move = (e) => {
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
    onHover(nearestIndex(tp.t_h, x.invert(px)), "phase");
  };
  return (
    <div ref={ref}>
      <p className="mb-1 font-display text-sm font-bold text-slate-100">Taste phase</p>
      {width > 0 && (
        <svg width={width} height={46} role="img" aria-label={summary} onPointerMove={move} onPointerLeave={() => onHover(null, "phase")}>
          {runs.slice(0, -1).map((r, j) => (
            <rect key={j} x={x(r.t_h)} y={2} height={22} width={Math.max(x(runs[j + 1].t_h) - x(r.t_h), 0.5)} fill={fill(r)} />
          ))}
          <line x1={x(nowH)} x2={x(nowH)} y1={0} y2={26} style={{ stroke: "var(--viz-now)" }} strokeWidth={1} />
          {spans.map((s) =>
            x(s.end_h) - x(s.start_h) > 48 ? (
              <text key={`${s.name}-${s.start_h}`} x={(x(s.start_h) + x(s.end_h)) / 2} y={40} textAnchor="middle" style={{ fill: "var(--viz-text-secondary)", fontSize: 11 }}>
                {s.name}
              </text>
            ) : null
          )}
        </svg>
      )}
      <p className="text-xs text-slate-300" aria-live="polite">
        {timeLabel(tp.t_h[i] ?? 0, timeUnit)}: {split.map((s) => `${s.name} ${Math.round(s.p * 100)} %`).join(", ")}
      </p>
      <details className="mt-1 text-xs text-slate-400">
        <summary className="cursor-pointer">Show as table</summary>
        <table className="ft-num mt-1">
          <thead><tr><th className="pr-3 text-left">Phase</th><th className="text-left">Most likely from</th></tr></thead>
          <tbody>{spans.map((s) => <tr key={`${s.name}-${s.start_h}`}><td className="pr-3">{s.name}</td><td>{timeLabel(s.start_h, timeUnit)}</td></tr>)}</tbody>
        </table>
      </details>
    </div>
  );
}

export default function TasteAroma({ data, charts, renderChart, hoverIndex, onHover, timeUnit }) {
  const s = data.sensory;
  return (
    <div className="space-y-5">
      <p className="border-l-2 border-slate-500 pl-3 text-xs leading-relaxed text-slate-300">{s.disclaimer}</p>
      {s.taste_phases && (
        <PhaseBand tp={s.taste_phases} nowH={data.now_h} horizonH={data.horizon_h} timeUnit={timeUnit} hoverIndex={hoverIndex} onHover={onHover} />
      )}
      {charts.map((c) => renderChart(c, THRESHOLD_LINE))}
      <p className="text-xs text-slate-400">Aroma compounds are coming next; bitterness and fizz are not modelled.</p>
    </div>
  );
}
```

- [ ] **Step 3: `Nutrition.jsx`**

```jsx
import { cellText, changeText } from "./sensory.js";

const ABV_LINE = [{ value: 0.5, label: "0.5 % ABV", tone: "neutral" }];
const INDENT = new Set(["sugars", "lactose", "free_amino_acids"]);

function Cell({ cell, unit, start }) {
  const { value, range } = cellText(cell, unit);
  const change = start ? changeText(start, cell) : null;
  return (
    <td className="px-2 py-1.5 text-right align-top">
      <span className="font-medium text-slate-100">{value}</span>
      {change && <span className="ml-1 text-[11px] text-slate-400">{change}</span>}
      {range && <span className="block text-[11px] text-slate-400">{range}</span>}
    </td>
  );
}

export default function Nutrition({ sensory, charts, renderChart }) {
  const rows = sensory.nutrition_label;
  return (
    <div className="space-y-5">
      <div className="overflow-x-auto">
        <table className="ft-num w-full text-sm">
          <caption className="mb-1 text-left text-xs text-slate-400">
            Per 100 g of what is in the jar · median, 90 % range below · ≥ = at least (some ingredients have no data) · – = unknown
          </caption>
          <thead>
            <tr className="border-b border-slate-800 text-xs text-slate-400">
              <th className="py-1 text-left font-medium">Per 100 g</th>
              <th className="px-2 text-right font-medium">Start</th>
              <th className="px-2 text-right font-medium">Now</th>
              <th className="px-2 text-right font-medium">End of window</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {rows.map((r) => (
              <tr key={r.key}>
                <th scope="row" className={`py-1.5 text-left font-normal text-slate-300 ${INDENT.has(r.key) ? "pl-3" : ""}`}>
                  {r.label} <span className="text-slate-400">({r.unit})</span>
                </th>
                <Cell cell={r.start} unit={r.unit} />
                <Cell cell={r.now} unit={r.unit} start={r.start} />
                <Cell cell={r.end} unit={r.unit} start={r.start} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">Model estimate, not a lab analysis; not for labelling products for sale.</p>
      {charts.map((c) => renderChart(c, c.unit === "% ABV" ? ABV_LINE : []))}
    </div>
  );
}
```

- [ ] **Step 4: Verify** `cd frontend && npx vite build` (after `npm ci` in the worktree) → builds clean.
- [ ] **Step 5: Commit** — `git add frontend/src/prediction && git commit -m "Taste and nutrition lens components"`.

---

### Task 9: Lens switch, "In the jar" card and milestone filtering

**Files:**
- Modify: `frontend/src/prediction/PredictionPanel.jsx`

**Interfaces:**
- Consumes: Task 7 `LENSES`, `lensOf`, `jarSummary`, `likelihood`, `phaseColor`, `fmtNum`; Task 8 components.

- [ ] **Step 1: Implement**
  1. `CANON` gains `nutrition: ["nut:energy_kcal", "nut:sugars", "nut:lactose", "nut:organic_acids", "nut:free_amino_acids", "nut:alcohol"]` and `taste: ["taste:sour", "taste:sweet", "taste:umami", "taste:alcohol"]`; `GROUP_ORDER` appends `"nutrition", "taste"`.
  2. `chartMeta`: `case "taste": return { title: "Taste", subtitle: "× detection threshold in water · log scale", logScale: true };` and `case "nutrition": return unit === "% ABV" ? { title: "Alcohol", subtitle: "% ABV" } : unit === "kcal/100 g" ? { title: "Energy", subtitle: "kcal per 100 g" } : { title: "Sugars, acids, amino acids", subtitle: "g per 100 g" };`.
  3. State `const [lens, setLens] = useState("process");`; `const SENSORY_GROUPS = new Set(["nutrition", "taste"]);` at module level; `processCharts = charts.filter((c) => !SENSORY_GROUPS.has(c.group))` replaces `charts` in `primaryIds`, `primary`, `secondary` and the empty-state check; `const activeLens = data?.sensory ? lens : "process";`.
  4. `renderChart = (c, refs = chartRefs(c)) => …` (pass `refLines={refs}`).
  5. `LensSwitch` (in this file, next to `Tabs`): `role="tablist"` pill group over `LENSES`, arrow/Home/End keys like `Tabs`, `min-h-[40px]`, active pill `bg-slate-700 text-slate-50`, inactive `text-slate-400 hover:text-slate-200`, focus ring `ring-emerald-400`.
  6. `JarCard` (in this file): for `["now", "end"]` render `jarSummary(data.sensory, which)`: a line "Now · {timeLabel}" / "End · {timeLabel}", a 10 px swatch `phaseColor(phase.k, phase.n)` + `{phase.name} ({likelihood(phase.p)})`, the noticeable tastes joined by " · " ("may be noticeable: sour · sweet"), and `sugars g · alcohol % ABV · energy kcal /100 g` from `fmtNum` (skip missing rows). Text in slate ink, never the swatch colour.
  7. Layout order after warnings: `{data.sensory && <JarCard … />}`, `{data.sensory && <LensSwitch … />}`, then `Milestones` with `data={{ ...data, milestones: (data.milestones || []).filter((m) => lensOf(m) === activeLens) }}`, then the what-if box (unchanged, shared), then the lens body: Process = today's chart block; `taste` = `<TasteAroma data={data} charts={charts.filter((c) => c.group === "taste")} renderChart={renderChart} hoverIndex={hover.index} onHover={onHover} timeUnit={timeUnit} />`; `nutrition` = `<Nutrition sensory={data.sensory} charts={charts.filter((c) => c.group === "nutrition")} renderChart={renderChart} />`.
- [ ] **Step 2: Build** `npx vite build` → clean; `node src/prediction/sensory.check.mjs` → ok; `node src/sourdough/plan.check.mjs` and `share.check.mjs` → ok (no regressions in shared helpers).
- [ ] **Step 3: Commit** — `git commit -am "Forecast panel: Taste & aroma and Nutrition lenses, In the jar card"`.

---

### Task 10: Verification and review

- [ ] **Step 1: Backend** — full suite `… -m pytest -q` (expect all green, ~2–4 min); `../../.venv/Scripts/ruff.exe check src tests`; `../../.venv/Scripts/mypy.exe src`.
- [ ] **Step 2: Palette** — `node <dataviz>/scripts/validate_palette.js "#184f95,#2a78d6,#6da7ec,#b7d3f6" --mode dark --surface "#191612" --ordinal` → ALL PASS.
- [ ] **Step 3: Browser** — local backend (port 8123, sqlite, `FERMENTTRACK_CORS_ORIGINS=http://127.0.0.1:5174`, dev JWT) + Vite on 5174; open a kombucha and a sauerkraut batch; screenshot each lens at 375, 500, 1100 px; look for label collisions, overflow, tab focus order; switch the what-if and confirm the taste band moves; confirm Process is unchanged.
- [ ] **Step 4: Review** — independent review of `derived.py`, `compounds.py` and the service/bake wiring (statistical correctness: weights, quantiles, threshold draws, lower-bound semantics) and of the frontend diff; fix findings; re-run Steps 1–3.
- [ ] **Step 5: Spec sync** — mark increment A implemented in the spec's status line, note any deviations, commit.
