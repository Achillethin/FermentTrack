"""Golden queries (recommender v2 § 4, release 1): hand-written requests whose answers come
from fermentation knowledge, not from what the model says today. Drafted by Claude for the
owner's review; a case the model misses is a strict xfail carrying the reason, so a fix shows
up as an XPASS. On the committed grid, no database.

Each case: (id, starred, pantry, aromas, tastes, section, check).
- section: "proven" or "experimental";
- check: ("top", {types or recipe keys}) = the first card is one of them;
  ("in", {...}) = one of the cards is; ("none", {...}) = no card is.
"""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.recommender import service

P, X = "proven", "experimental"
DAIRY = {"kefir", "cheese"}
CASES = [
    # pantry-first lacto (V1 audience 1)
    ("cabbage-kraut", [], ["Cabbage"], [], [], P, ("top", {"sauerkraut_dry_salted"})),
    ("kimchi-pantry", [], ["Napa cabbage", "Garlic", "Chilies"], [], [], P,
     ("top", {"napa_kimchi_room_temp"})),
    ("carrot-garlic-is-lacto", [], ["Carrot", "Garlic"], [], [], X, ("top", {"lacto_ferment"})),
    ("cabbage-never-kombucha", [], ["Cabbage"], [], [], X, ("none", {"kombucha", "miso"})),
    # one base ingredient -> its classic ferment
    ("milk-is-dairy", [], ["Milk"], [], [], P, ("top", DAIRY)),
    ("soy-rice-is-miso", [], ["Soybeans", "White rice"], [], [], P, ("top", {"miso"})),
    ("anchovies-is-fish-sauce", [], ["Anchovies"], [], [], P, ("top", {"garum"})),
    ("cider-is-vinegar", [], ["Hard cider"], [], [], P, ("top", {"cider_vinegar_surface"})),
    # aroma and taste targets (V1 audience 3), each the textbook source of that note
    ("fruity", [], [], ["fruity"], [], P, ("top", {"kombucha", "kefir"})),
    ("fruity-not-a-starter", [], [], ["fruity"], [], P, ("none", {"sourdough"})),
    ("buttery-is-dairy", [], [], ["buttery"], [], P, ("top", DAIRY)),  # citrate -> diacetyl
    ("floral-is-tea", [], [], ["floral"], [], P, ("top", {"kombucha"})),  # tea terpenes
    ("mushroom-is-koji", [], [], ["mushroom"], [], P, ("top", {"koji"})),  # mould C8 volatiles
    ("fishy-is-fish-sauce", [], [], ["fishy"], [], P, ("top", {"garum"})),
    ("vinegary", [], [], ["vinegary"], [], P, ("top", {"vinegar", "kombucha"})),
    ("umami", [], [], [], ["umami"], P, ("top", {"garum", "miso"})),
    ("sulfurous-has-a-brassica", [], [], ["sulfurous"], [], P, ("in", {"lacto_ferment"})),
]  # fmt: skip

# Misses on the committed grid, with the reason (the model's, not the query's).
KNOWN_MISSES: dict[str, str] = {
    "sulfurous-has-a-brassica": "2026-10-20: the top 3 are two misos and the fish sauce; the "
    "engine's miso/garum sulfur volatiles outrank cabbage DMS/DMTS (aroma calibration gap)",
}


def _cards(starred, pantry, aromas, tastes, section) -> list[service.Card]:  # type: ignore[no-untyped-def]
    targets = service.parse_targets(aromas, tastes)
    if section == P:
        return service.proven_cards(starred, targets, None, pantry=pantry)[0]
    return service.experimental_cards(starred, targets, None, pantry=pantry)


def _labels(card: service.Card) -> set[str]:
    parent = card.variant.parent.recipe if card.variant else card.recipe
    return {parent.key, parent.fermentation_type}


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(c, id=c[0], marks=pytest.mark.xfail(strict=True, reason=KNOWN_MISSES[c[0]]))
        if c[0] in KNOWN_MISSES else pytest.param(c, id=c[0])
        for c in CASES
    ],
)  # fmt: skip
def test_golden_query(case) -> None:  # type: ignore[no-untyped-def]
    _, starred, pantry, aromas, tastes, section, (kind, want) = case
    cards = _cards(starred, pantry, aromas, tastes, section)
    labels = [_labels(c) for c in cards]
    shown = [sorted(x) for x in labels]
    if kind == "top":
        assert labels and labels[0] & want, shown
    elif kind == "in":
        assert any(x & want for x in labels), shown
    else:
        assert not any(x & want for x in labels), shown


@pytest.mark.xfail(strict=True, reason="2026-10-20: IQR 0.122 over 27 cards (v1 ~0.00); the "
                   "release-1 target is 0.2, not met yet")
def test_scores_spread_across_the_golden_target_queries() -> None:
    """Release 1 exit: the served cards' E is no longer pinned near 1 (v1: every card E ≈ 1.00,
    separated by float16 steps). IQR over every Proven card of the target queries."""
    es = [
        c.evaluation.e
        for _, starred, pantry, aromas, tastes, _, _ in CASES
        if aromas or tastes
        for c in service.proven_cards(
            starred, service.parse_targets(aromas, tastes), None, pantry=pantry
        )[0]
        if c.evaluation.e is not None
    ]
    q75, q25 = np.percentile(es, [75, 25])
    print(f"\nE over {len(es)} cards: IQR {q75 - q25:.3f}, min {min(es):.3f}, max {max(es):.3f}")
    assert q75 - q25 > 0.2
