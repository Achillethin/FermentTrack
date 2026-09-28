"""Learning across batches (prediction/population.py): a crossed Gaussian hierarchy (global
class, levain style, baker, starter, batch) in the literature prior's z-units, conditioned
exactly on per-batch likelihood summaries.
Design: docs/superpowers/specs/2026-09-28-sourdough-engine-design.md § 6.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import (
    Batch,
    BatchEvidence,
    Culture,
    Enzyme,
    FermentationTypeOrganism,
    Ingredient,
    IngredientNutrient,
    Measurement,
    Organism,
    OrganismEnzyme,
)
from fermenttrack.prediction import population
from fermenttrack.prediction.model import ParamSpec
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.population import Row, predictive
from fermenttrack.prediction.priors import Prior
from tests.conftest import TEST_USER_ID

LP = ORGANISM_KINETICS["Lactobacillus plantarum"]


def _rows(n: int, ell: float, style: str, baker: str, starter: str, lam: float = 20.0) -> list[Row]:
    return [Row(style, baker, starter, ell, lam) for _ in range(n)]


def test_no_evidence_is_exactly_the_literature_prior() -> None:
    assert predictive([], "levain_liquide", "achille", "s1") == (0.0, pytest.approx(1.0))
    assert population.learned_prior(LP.mu_max, [], "x", "y", "z") == LP.mu_max
    # to_u / from_u round-trip through the split normal
    lit = LP.mu_max
    back = population.from_u(lit, 0.0, 1.0)
    assert back.median == pytest.approx(lit.median)
    assert back.lo == pytest.approx(lit.lo) and back.hi == pytest.approx(lit.hi)
    assert float(population.to_u(lit, lit.hi)) == pytest.approx(1.6448536, rel=1e-6)


def test_a_starter_inherits_its_style_and_its_baker_but_stays_itself() -> None:
    # Achille's classic levain: 6 well-measured fast batches (u = +1.5)
    rows = _rows(6, 1.5, "levain_liquide", "achille", "achille-classic")
    own_m, own_v = predictive(rows, "levain_liquide", "achille", "achille-classic")
    assert 1.1 < own_m < 1.5 and own_v < 0.35  # learned, but never below the batch scatter
    assert own_v > population.VARIANCES["batch"]
    # a second starter of Achille's, same style: inherits style + baker, not the starter part
    sib_m, sib_v = predictive(rows, "levain_liquide", "achille", "achille-rye")
    assert 0.3 < sib_m < own_m and sib_v > own_v
    # Aymard's classic levain: shares only the style (and the global class)
    aym_m, _ = predictive(rows, "levain_liquide", "aymard", "aymard-classic")
    assert 0.0 < aym_m < sib_m
    # a rye levain of Aymard's: only the global class
    rye_m, rye_v = predictive(rows, "rye_sour", "aymard", "aymard-rye")
    assert 0.0 < rye_m < aym_m and rye_v > 0.7


def test_crossed_classes_combine_additively() -> None:
    # style effect learned from Aymard, baker effect learned from Achille's rye starter
    rows = _rows(8, 1.0, "levain_liquide", "aymard", "aymard-1") + _rows(
        8, -1.0, "rye_sour", "achille", "achille-rye"
    )
    # Achille's new classic levain: pulled up by the classic class, down by Achille
    m_new, _ = predictive(rows, "levain_liquide", "achille", "achille-classic")
    m_style_only, _ = predictive(rows, "levain_liquide", "someone", "x")
    m_baker_only, _ = predictive(rows, "other_style", "achille", "y")
    assert m_baker_only < m_new < m_style_only


def test_one_baker_alone_is_not_double_counted() -> None:
    # a single starter's evidence must not make the class look as certain as the starter:
    # a new, unrelated starter's variance stays well above the starter's own
    rows = _rows(20, 2.0, "levain_liquide", "achille", "s1", lam=100.0)
    m_s, v_s = predictive(rows, "levain_liquide", "achille", "s1")
    m_o, v_o = predictive(rows, "other", "other", "s2")
    assert v_o > 0.6 and v_s < 0.2
    assert m_o < 0.9 * m_s


def test_likelihood_summary_divides_out_the_prior_it_ran_under() -> None:
    class _Kin:
        name = "Lactobacillus plantarum"

    rng = np.random.default_rng(0)
    for prior in (LP.mu_max, population.from_u(LP.mu_max, 0.8, 0.4)):  # literature, learned
        m_pr, v_pr = population.prior_moments_u(LP.mu_max, prior)
        # posterior = prior x likelihood N(1.2, 0.25) (Gaussian in u), sampled via z
        lam_true, ell_true = 4.0, 1.2
        v_post = 1.0 / (1.0 / v_pr + lam_true)
        m_post = v_post * (m_pr / v_pr + lam_true * ell_true)
        u = m_post + np.sqrt(v_post) * rng.standard_normal(20000)
        z = (u - m_pr) / np.sqrt(v_pr)  # the batch's own z-column (prior N(0, 1))
        specs = [ParamSpec("mu_max", prior, 0)]
        (ev,) = population.likelihood_summaries(specs, [_Kin()], z[:, None], np.ones(len(z)))
        assert ev.ell == pytest.approx(ell_true, abs=0.05)
        assert ev.lam == pytest.approx(lam_true, rel=0.1)
    # a batch that learned nothing about the parameter stores nothing
    z = rng.standard_normal((5000, 1))
    assert population.likelihood_summaries(
        [ParamSpec("mu_max", LP.mu_max, 0)], [_Kin()], z, np.ones(5000)
    ) == []


# ── router: a finished, calibrated batch records its evidence once ──────────


async def _finished_batch(db_session: AsyncSession, style: str | None = None) -> Batch:
    lp = Organism(name="Lactobacillus plantarum", kingdom="bacteria", source_version="v1")
    ldh = Enzyme(ec_number="1.1.1.27", name="L-lactate dehydrogenase", source_version="v1")
    cabbage = Ingredient(
        name="Cabbage", default_role="base", fermentation_systems=["lacto_ferment"]
    )
    db_session.add_all([lp, ldh, cabbage])
    await db_session.flush()
    db_session.add(OrganismEnzyme(organism_id=lp.id, enzyme_id=ldh.id))
    db_session.add(FermentationTypeOrganism(fermentation_type="lacto_ferment", organism_id=lp.id))
    for k, v in {"water": 92.2, "sugars_total": 3.2, "glucose": 1.67, "fructose": 1.45}.items():
        db_session.add(
            IngredientNutrient(
                ingredient_id=cabbage.id, nutrient=k, amount_per_100g=v, source="usda_fdc",
                source_food_id="1", source_version="test",
            )
        )  # fmt: skip
    culture = Culture(name="Kraut", type="lacto_ferment", owner_id=TEST_USER_ID, style=style)
    db_session.add(culture)
    await db_session.flush()
    started = datetime.now(UTC) - timedelta(hours=72)
    ended = started + timedelta(hours=48)
    batch = Batch(
        culture_id=culture.id, started_at=started, current_stage="done",
        stage_entered_at=ended, outcome="success", ended_at=ended,
    )  # fmt: skip
    db_session.add(batch)
    await db_session.flush()
    for h, v in ((1, 6.1), (24, 5.2), (47, 4.3)):
        db_session.add(
            Measurement(batch_id=batch.id, measured_at=started + timedelta(hours=h), type="pH",
                        value_numeric=v)
        )  # fmt: skip
    await db_session.commit()
    return batch


async def test_finished_batch_records_evidence_exactly_once(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _finished_batch(db_session)
    ingredients = await client.get("/ingredients", params={"substrate": "lacto_ferment"})
    resp = await client.post(
        f"/batches/{batch.id}/ingredients",
        json={"ingredient_id": ingredients.json()[0]["id"], "quantity": 1, "unit": "kg"},
    )
    assert resp.status_code == 201
    for _ in range(2):
        assert (await client.get(f"/batches/{batch.id}/prediction")).status_code == 200
    await db_session.refresh(batch)
    assert batch.population_pooled_at is not None
    rows = (await db_session.execute(select(BatchEvidence))).scalars().all()
    assert rows, "a calibrated batch that moved mu_max/t_opt must leave evidence"
    assert len({(r.organism, r.param) for r in rows}) == len(rows)  # once, despite two calls
    assert all(r.culture_id == batch.culture_id and r.owner_id == TEST_USER_ID for r in rows)
    assert all(r.style == "lacto_ferment" and r.lam > 0 for r in rows)
    # the next batch of this starter starts from the learned prior
    learned = await population.learned_priors(
        db_session, ["Lactobacillus plantarum"], style="lacto_ferment", baker=TEST_USER_ID,
        starter=batch.culture_id,
    )
    got = {p for p in learned.get("Lactobacillus plantarum", {})}
    assert got == {r.param for r in rows}
    p: Prior = learned["Lactobacillus plantarum"][rows[0].param]
    lit = getattr(LP, rows[0].param)
    # narrower than the literature, in the parameter's own (log or linear) scale
    width = (lambda q: np.log(q.hi / q.lo)) if lit.scale == "log" else (lambda q: q.hi - q.lo)
    assert width(p) < width(lit)


async def test_account_delete_erases_learned_evidence(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _finished_batch(db_session)
    db_session.add(
        BatchEvidence(batch_id=batch.id, culture_id=batch.culture_id, owner_id=TEST_USER_ID,
                      style="lacto_ferment", organism="Lactobacillus plantarum",
                      param="mu_max", ell=0.5, lam=3.0)
    )  # fmt: skip
    await db_session.commit()
    assert (await client.delete("/me")).status_code == 204
    db_session.expire_all()
    assert (await db_session.execute(select(BatchEvidence))).scalars().all() == []
