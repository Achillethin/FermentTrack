"""The lacto composer (recommender v2 § 3.3, release 2): a lacto-ferment recipe assembled for
what the user has, each part a sourced rule or a curated number. Pantry-first lacto fermenters
(audience 1) ask "I have carrots and garlic": the library's 13 non-sourdough recipes and their
single operators can only answer with a kimchi or a sauerkraut bent out of shape.

A composition is the user's base vegetables (catalogue rows tagged lacto_ferment with role
base) and aromatics (rows of AROMATICS below), and nothing else:
- the method by vegetable: cabbages are dry-salted (shredded cabbage and salt make their own
  brine, NCHFP sauerkraut); anything else is covered with brine;
- dry-salted: salt 2.25 % of the batch (the standard 2.0-2.25 %, Johanningsmeier et al. 2007);
- brined: solids 46 % and brine 54 % of the batch (NCHFP dill pickles: 4 lb cucumbers to 8
  cups water and 1/2 cup salt), salt 2.5 % of the batch (v2 V8), so the brine itself is 4.6 %:
  inside UMN's 1-3 Tbsp per quart (1.9-5.4 %);
- aromatics at their sourced share of the batch (AROMATICS), taken from the solids;
- the documented duration 3-4 weeks (NCHFP sauerkraut and dill pickles, UMN wet brines);
- temperature and window from the model, like any Experimental card.

Composed recipes are Experimental: they run live (64 members), carry "composed from sourced
rules" and pass the safety gate like every card. The client only names the ingredients; the
server derives every mass again (`compose`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import library
from fermenttrack.recommender.library import Recipe, RecipeIngredient, Span

TYPE = "lacto_ferment"
DRY_SALTED = frozenset({"Cabbage", "Napa cabbage"})
DRY_SALT_PCT = 2.25
BRINE_SHARE = 0.54
BRINE_SALT_PCT = 2.5
DURATION_H = Span(588.0, 504.0, 672.0)
MAX_BASES = 2
MAX_AROMATICS = 3
LABEL = "composed from sourced rules"
# Aromatic -> (share of the batch: median, lo, hi; where). From the lacto-ingredients research
# round (docs/superpowers/research/aroma/06-lacto-alliums-roots.md on feat/aroma-lacto-
# ingredients). Not T3 rows (library.use_levels): T3 needs aroma data, and garlic and onion
# have none until that round's allium cascade lands, so their aroma shows as "no aroma data".
# ponytail: the kimchi share for garlic in a brine too; pickle recipes use far less (NCHFP dill
# pickles 2 cloves per gallon, ~0.2 %): a method-specific share when a brined source appears.
AROMATICS: dict[str, tuple[float, float, float, str]] = {
    "Garlic": (
        0.025, 0.005, 0.052,
        "median of five kimchi recipes: Lee et al. 2021 Foods 10:423 Table 3; Choi et al. 2023 "
        "Food Chem X 20:100950; Mannaa et al. 2019 Sci Rep 9:17693; Kraouia et al. 2025 "
        "Molecules 30:2731 Table 6; Luo et al. 2025 Food Sci Nutr 13:e71042",
    ),
    "Onion": (
        0.044, 0.015, 0.08,
        "Kraouia et al. 2025 Molecules 30:2731 Table 6 (one recipe; range est.)",
    ),
}  # fmt: skip
SOURCES = (
    "NCHFP-sauerkraut", "Johanningsmeier2007-sauerkraut", "NCHFP-dill-pickles",
    "UMN-fermentation",
)  # fmt: skip


class CompositionError(ValueError):
    """Ingredients the composer cannot assemble (a 422)."""


@dataclass(frozen=True)
class Composition:
    bases: tuple[str, ...]  # sorted
    aromatics: tuple[str, ...]  # sorted

    @property
    def method(self) -> str:
        return "dry_salted" if set(self.bases) <= DRY_SALTED else "brine"

    @property
    def key(self) -> str:
        names = "+".join((*self.bases, *self.aromatics))
        return f"composed:{self.method}:{names}"

    @property
    def name(self) -> str:
        how = "Dry-salted" if self.method == "dry_salted" else "Brined"
        base = " and ".join(b.lower() for b in self.bases)
        if not self.aromatics:
            return f"{how} {base}"
        return f"{how} {base} with {' and '.join(a.lower() for a in self.aromatics)}"


def _tagged(name: str, role: str) -> bool:
    row = library.CATALOGUE.get(name)
    return row is not None and row[0] == role and TYPE in row[1]


def is_base(name: str) -> bool:
    return _tagged(name, "base")


def is_aromatic(name: str) -> bool:
    return _tagged(name, "flavoring") and name in AROMATICS


def composition(bases: Sequence[str], aromatics: Sequence[str]) -> Composition:
    """The validated composition. Raises CompositionError."""
    b = tuple(sorted(dict.fromkeys(bases)))
    a = tuple(sorted(dict.fromkeys(aromatics)))
    if not 1 <= len(b) <= MAX_BASES:
        raise CompositionError(f"a composed lacto ferment has 1 to {MAX_BASES} base vegetables")
    if len(a) > MAX_AROMATICS:
        raise CompositionError(f"at most {MAX_AROMATICS} aromatics")
    for n in b:
        if not is_base(n):
            raise CompositionError(f"{n!r} is not a lacto-ferment base vegetable")
    for n in a:
        if not is_aromatic(n):
            raise CompositionError(f"{n!r} has no sourced amount in a lacto ferment yet")
    return Composition(b, a)


def _row(name: str, role: str, g: float, source: str) -> RecipeIngredient:
    status = "existing" if name in library.AROMA_INGREDIENTS else "existing_no_aroma"
    return RecipeIngredient(
        name=name, catalogue_status=status, role=role, g_per_kg=Span(g, g, g), required="core",
        source=source, notes="composer", label=None,
    )  # fmt: skip


def compose(c: Composition, temperature_c: float | None = None) -> Recipe:
    """The recipe (g per kg of batch) for a composition, at temperature_c (default: the
    profile's typical temperature, clipped into its range)."""
    profile = PROFILES[TYPE]
    lo, hi = profile.temp_range  # the documented span: the model's range (any lacto ferment)
    temp = min(max(temperature_c if temperature_c is not None else profile.temp_c, lo), hi)
    aromatic_g = {a: 1000.0 * AROMATICS[a][0] for a in c.aromatics}
    rows: list[RecipeIngredient] = []
    if c.method == "dry_salted":
        salt = 10.0 * DRY_SALT_PCT
        solids = 1000.0 - salt
        water = 0.0
        salt_source = "Johanningsmeier2007-sauerkraut: standard 2.0-2.25 % NaCl"
    else:
        salt = 10.0 * BRINE_SALT_PCT
        water = 1000.0 * BRINE_SHARE - salt
        solids = 1000.0 - salt - water
        salt_source = "v2 V8 default 2.5 %; brine 4.6 % within UMN-fermentation 1-3 Tbsp/qt"
    base_g = (solids - sum(aromatic_g.values())) / len(c.bases)
    if base_g <= 0:
        raise CompositionError("the aromatics leave no room for the vegetables")
    rows += [_row(b, "base", base_g, "composer: solids share") for b in c.bases]
    rows += [_row(a, "flavoring", g, AROMATICS[a][3]) for a, g in aromatic_g.items()]
    if water:
        rows.append(_row("Water", "liquid", water, "NCHFP-dill-pickles brine share"))
    rows.append(_row("Salt", "additive", salt, salt_source))
    salt_pct = salt / 10.0
    return Recipe(
        key=c.key, name=c.name, fermentation_type=TYPE, style_region="composed",
        provenance="composed", temp_c=Span(temp, lo, hi), duration_h=DURATION_H,
        salt_pct=Span(salt_pct, salt_pct, salt_pct), sugar_g_per_kg=None, aerobic=False,
        method=c.method, stages="",
        safety_targets="pH<=4.6 before consuming; keep the vegetables under the brine",
        reported_aromas=(), sources=SOURCES,
        status="active", notes=LABEL, temp_schedule=(), envelope_basis="composed",
        model_scope=("in_range",), handoff=None, planner_style=None, ingredients=tuple(rows),
    )  # fmt: skip


def _in_library(c: Composition) -> bool:
    """A library recipe already has exactly these non-staple ingredients (dry-salted cabbage is
    the sauerkraut): Proven serves it, with its own sources."""
    names = {*c.bases, *c.aromatics}
    return any(
        r.fermentation_type == TYPE
        and {i.name for i in r.ingredients if i.name not in library.STAPLES} == names
        for r in library.active()
    )


def notes(c: Composition) -> tuple[str, ...]:
    """What the card says about how it was composed."""
    if c.method == "dry_salted":
        out = [
            f"composed: dry-salted at {DRY_SALT_PCT:g} % salt, the standard for shredded cabbage"
        ]
    else:
        brine = 100.0 * BRINE_SALT_PCT / (100.0 * BRINE_SHARE)
        out = [
            f"composed: vegetables {100 * (1 - BRINE_SHARE):.0f} % and brine "
            f"{100 * BRINE_SHARE:.0f} % of the jar, the brine at {brine:.1f} % salt "
            f"({BRINE_SALT_PCT:g} % of the batch); keep everything under the brine"
        ]
    if "Garlic" in c.aromatics and c.method == "brine":
        out.append("garlic at the usual kimchi share (2.5 %); pickle recipes use less")
    return tuple(out)


def candidates(have: Sequence[str], must: Sequence[str] = ()) -> list[Composition]:
    """Compositions from what the user has (have) holding every must-use item (must): every
    base alone and every pair (cabbage with cabbage aside), each with all the aromatics the
    user has, at most MAX_AROMATICS; none a library recipe already is. The ones using more of
    the pantry first. Empty when a must-use item can't be composed."""
    names = list(dict.fromkeys((*must, *have)))
    bases = [n for n in names if is_base(n)]
    aromatics = sorted(n for n in names if is_aromatic(n))[:MAX_AROMATICS]
    if any(not (is_base(m) or is_aromatic(m)) for m in must if m not in library.STAPLES):
        return []
    out: list[Composition] = []
    seen: set[tuple[str, ...]] = set()
    for i, b in enumerate(bases):
        for group in ((b,), *((b, b2) for b2 in bases[i + 1 :])):
            if len(group) == 2 and set(group) <= DRY_SALTED:
                continue  # two cabbages: one sauerkraut, not a composition
            key = tuple(sorted(group))
            if key in seen:
                continue
            seen.add(key)
            c = Composition(key, tuple(aromatics))
            wanted = {m for m in must if m not in library.STAPLES}
            if wanted <= {*c.bases, *c.aromatics} and not _in_library(c):
                out.append(c)
    return sorted(out, key=lambda c: (-len(c.bases) - len(c.aromatics), c.key))
