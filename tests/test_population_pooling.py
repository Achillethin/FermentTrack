"""Empirical-Bayes plug-in pooling (prediction/population.py): a finished batch's AMIS
posterior updates a population-level prior per (organism, mu_max/t_opt), and subsequent
batches of the same organism start from it once there are enough pooled batches.
Design: docs/superpowers/specs/2026-09-28-population-pooling-design.md.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import (
    Batch,
    Culture,
    Enzyme,
    FermentationTypeOrganism,
    Ingredient,
    IngredientNutrient,
    Measurement,
    Organism,
    OrganismEnzyme,
    PopulationPrior,
)
from fermenttrack.prediction import population
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from tests.conftest import TEST_USER_ID

LP_MU_MAX = ORGANISM_KINETICS["Lactobacillus plantarum"].mu_max  # log-scale literature prior


async def _organism(db: AsyncSession, name: str = "Lactobacillus plantarum") -> Organism:
    o = Organism(name=name, kingdom="bacteria", source_version="v1")
    db.add(o)
    await db.flush()
    return o


async def _row(db: AsyncSession, organism_id, param_name: str) -> PopulationPrior:
    return (
        await db.execute(
            select(PopulationPrior).where(
                PopulationPrior.organism_id == organism_id,
                PopulationPrior.param_name == param_name,
            )
        )
    ).scalar_one()


def _samples(log_value: float, n: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """n identical weighted samples whose log-space weighted mean is exactly `log_value`
    (deterministic: no RNG noise to make the statistical assertions flaky)."""
    return np.full(n, math.exp(log_value)), np.full(n, 1.0 / n)


def test_transformed_mean_actually_uses_the_weights() -> None:
    # Two distinct values, weight skewed 99:1 toward the low one: a broken
    # implementation that silently ignored `weights` (plain np.mean) would give ~1.0335
    # (log((0.7+1.1)/2)-ish) instead of landing close to log(0.7).
    values = np.array([0.7, 1.1])
    weights = np.array([0.99, 0.01])
    mean_b = population._transformed_mean(values, weights, "log")
    assert mean_b == pytest.approx(math.log(0.7), abs=0.02)


# ── 1. a single finished batch shrinks the row toward its own posterior ───────────────


async def test_single_batch_updates_row_away_from_literature(db_session: AsyncSession) -> None:
    org = await _organism(db_session)
    values, weights = _samples(math.log(1.1))  # literature median is ~0.7: far from 1.1
    await population.update_population_prior(db_session, org.id, "mu_max", values, weights, "log")
    await db_session.commit()

    row = await _row(db_session, org.id, "mu_max")
    assert row.n_obs == 1
    assert row.median != LP_MU_MAX.median
    assert row.median == pytest.approx(1.1, rel=1e-6)  # n_obs=1: pooled mean == batch 1's own


# ── 2. below MIN_POOLED_OBS, the literature prior is used unchanged ───────────────────


async def test_below_threshold_falls_back_to_literature(db_session: AsyncSession) -> None:
    org = await _organism(db_session)
    values, weights = _samples(math.log(1.1))

    for _ in range(population.MIN_POOLED_OBS - 1):
        await population.update_population_prior(
            db_session, org.id, "mu_max", values, weights, "log"
        )
        prior = await population.population_prior_for(db_session, org.id, "mu_max", LP_MU_MAX)
        assert prior == LP_MU_MAX
    await db_session.commit()

    await population.update_population_prior(db_session, org.id, "mu_max", values, weights, "log")
    prior = await population.population_prior_for(db_session, org.id, "mu_max", LP_MU_MAX)
    assert prior != LP_MU_MAX
    assert prior.median == pytest.approx(1.1, rel=1e-6)


# ── 3. pooled spread narrows as more (agreeing) batches accumulate ────────────────────


async def test_pooled_spread_shrinks_as_batches_accumulate(db_session: AsyncSession) -> None:
    org = await _organism(db_session)
    # batch 1 is a little off; batches 2-5 all confirm the same value exactly, so the
    # running estimate settles and the standard error of the pooled mean must shrink.
    targets = [1.1, 1.0, 1.0, 1.0, 1.0]
    widths = []
    for t in targets:
        values, weights = _samples(math.log(t))
        await population.update_population_prior(
            db_session, org.id, "mu_max", values, weights, "log"
        )
        row = await _row(db_session, org.id, "mu_max")
        widths.append(row.hi - row.lo)
    await db_session.commit()

    # n_obs=1 is degenerate (a single point has no spread); compare from n_obs=2 on.
    assert widths[1] > 0
    assert widths[1:] == sorted(widths[1:], reverse=True)
    assert widths[-1] < widths[1]


# ── 4. /prediction on a finished batch pools exactly once, however many times it's hit ─


async def _finished_batch(db_session: AsyncSession) -> Batch:
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
    culture = Culture(name="Kraut", type="lacto_ferment", owner_id=TEST_USER_ID)
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
    db_session.add_all(
        [
            Measurement(batch_id=batch.id, measured_at=started + timedelta(hours=1), type="pH",
                        value_numeric=6.1),
            Measurement(batch_id=batch.id, measured_at=started + timedelta(hours=24), type="pH",
                        value_numeric=5.2),
            Measurement(batch_id=batch.id, measured_at=started + timedelta(hours=47), type="pH",
                        value_numeric=4.3),
        ]
    )  # fmt: skip
    await db_session.commit()
    return batch


async def test_finished_batch_pools_exactly_once(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _finished_batch(db_session)
    ingredients = await client.get("/ingredients", params={"substrate": "lacto_ferment"})
    cabbage_id = ingredients.json()[0]["id"]
    resp = await client.post(
        f"/batches/{batch.id}/ingredients",
        json={"ingredient_id": cabbage_id, "quantity": 1, "unit": "kg"},
    )
    assert resp.status_code == 201

    resp1 = await client.get(f"/batches/{batch.id}/prediction")
    assert resp1.status_code == 200
    resp2 = await client.get(f"/batches/{batch.id}/prediction")
    assert resp2.status_code == 200

    await db_session.refresh(batch)
    assert batch.population_pooled_at is not None

    org = (
        await db_session.execute(
            select(Organism).where(Organism.name == "Lactobacillus plantarum")
        )
    ).scalar_one()
    row = await _row(db_session, org.id, "mu_max")
    assert row.n_obs == 1  # not 2, despite two /prediction calls
