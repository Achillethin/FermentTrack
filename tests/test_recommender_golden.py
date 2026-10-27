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

from fermenttrack.recommender import library, service

P, X, M = "proven", "experimental", "pantry"
DAIRY = {"kefir", "cheese"}
CASES = [
    # pantry-first lacto (V1 audience 1)
    ("cabbage-kraut", [], ["Cabbage"], [], [], P, ("top", {"sauerkraut_dry_salted"})),
    ("kimchi-pantry", [], ["Napa cabbage", "Garlic", "Chilies"], [], [], P,
     ("top", {"napa_kimchi_room_temp"})),
    ("carrot-garlic-is-lacto", [], ["Carrot", "Garlic"], [], [], X, ("top", {"lacto_ferment"})),
    # release 2 exit (v2 § 4): "carrot + garlic returns brined carrots with garlic" (composer)
    ("carrot-garlic-is-brined-carrot", [], ["Carrot", "Garlic"], [], [], M,
     ("top", {"composed:brine:Carrot+Garlic"})),
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
    # a brassica's aroma is mostly sulfur (DMS, DMTS, allyl sulfides); in miso it is one note
    # among many: ranking by the share of the aroma (v2 § 3.1) puts the brassica first
    ("sulfurous-is-a-brassica", [], [], ["sulfurous"], [], P, ("top", {"lacto_ferment"})),
    # no filler: a ferment that can't give the note is not served for it
    ("fishy-no-filler", [], [], ["fishy"], [], P,
     ("none", {"kombucha", "kefir", "cheese", "vinegar", "sourdough", "lacto_ferment"})),
]  # fmt: skip

# Misses on the committed grid, with the reason (the model's, not the query's).
KNOWN_MISSES: dict[str, str] = {}


def _cards(starred, pantry, aromas, tastes, section) -> list[service.Card]:  # type: ignore[no-untyped-def]
    targets = service.parse_targets(aromas, tastes)
    if section == P:
        return service.proven_cards(starred, targets, None, pantry=pantry)[0]
    if section == M:  # "Made from what you have": composed lacto recipes (v2 § 3.3)
        return service.composed_cards(starred, pantry, targets, None)
    return service.experimental_section(starred, targets, None, 1000.0, (), None, pantry)[1]


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


def _target_queries():  # type: ignore[no-untyped-def]
    return [(s, p, service.parse_targets(a, t)) for _, s, p, a, t, _, _ in CASES if a or t]


def test_scores_spread_across_the_golden_target_queries() -> None:
    """Release 1 exit (v2 § 4, revised 2026-10-24): E is no longer pinned near 1 (v1: every card
    E ≈ 1.00, cards separated by float16 steps). Measured over every gated candidate of the
    target queries: the served cards are each query's best 3, so their own IQR says how good
    the top is, not whether the score saturates (0.13 on E there)."""
    es = [
        c.evaluation.e
        for _, _, targets in _target_queries()
        for r in library.active()
        if (c := service.build_card(r, targets, None)[0]) is not None
        and c.evaluation.e is not None
    ]
    q75, q25 = np.percentile(es, [75, 25])
    print(f"\nE over {len(es)} candidates: IQR {q75 - q25:.3f}")
    assert q75 - q25 > 0.2


def test_served_cards_are_ranked_by_more_than_rounding() -> None:
    """v1's order was float16 noise (E ≈ 1.00 ± 10⁻³). The ranking magnitude C (the targets'
    share of the aroma) separates consecutive served cards by a median of more than 0.01."""
    gaps = []
    for starred, pantry, targets in _target_queries():
        served = service.proven_cards(starred, targets, None, pantry=pantry)[0]
        cs = [c.evaluation.c for c in served]
        gaps += [a - b for a, b in zip(cs, cs[1:], strict=False)]
    assert gaps and all(g >= 0 for g in gaps)
    print(f"\nC gaps between served cards: median {np.median(gaps):.3f} over {len(gaps)}")
    assert np.median(gaps) > 0.01
