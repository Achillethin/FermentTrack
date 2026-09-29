"""scripts/validate_forecasts.py on one finished batch: inputs truncated at the cut (no
leakage), one scored pair per later reading, finite scores."""

from __future__ import annotations

import importlib.util
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Measurement
from fermenttrack.prediction import bake
from fermenttrack.prediction.bake import BakeInputs, forecast
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.sourdough import plan_from_dict
from tests.test_population_pooling import _finished_batch

_spec = importlib.util.spec_from_file_location(
    "validate_forecasts", Path(__file__).parents[1] / "scripts" / "validate_forecasts.py"
)
assert _spec is not None and _spec.loader is not None
vf = sys.modules["validate_forecasts"] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vf)


async def test_leave_future_out_scores_only_later_readings(db_session: AsyncSession) -> None:
    batch = await _finished_batch(db_session)  # daily pH, 24 ... 239 h
    db_session.add(Measurement(batch_id=batch.id, type="temperature", value_numeric=30.0,
                               measured_at=batch.started_at + timedelta(hours=30)))  # fmt: skip
    await db_session.commit()
    await db_session.refresh(batch, ["measurements", "culture"])

    ctx = await vf.forecast_context(db_session, batch)
    plan, inputs = await vf.inputs_at(db_session, batch, ctx, 24.0)
    assert plan is None and inputs.now_h == 24.0 and not inputs.finished
    assert max(m.t_h for m in inputs.measurements) <= 24.0  # the 30 h temperature is future
    _, prior_only = await vf.inputs_at(db_session, batch, ctx, 24.0, with_readings=False)
    assert not any(m.type == "pH" for m in prior_only.measurements)

    pairs = await vf.evaluate(db_session, max_cuts=2)  # the first and last cut
    later = [48.0, 72.0, 96.0, 120.0, 144.0, 168.0, 192.0, 216.0, 239.0]
    assert [(p["cut_h"], p["t_h"]) for p in pairs] == [(24.0, t) for t in later] + [(216.0, 239.0)]
    for p in pairs:
        assert 0.0 <= p["pit"] <= 1.0 and math.isfinite(p["crps"]) and p["crps_clim"] is None
    (row,) = [r for r in vf.summarise(pairs) if r["style"] == "*"]
    assert row["pairs"] == 10 and sum(row["pit_hist"]) == 10
    assert row["skill_prior"] > 0  # readings a little faster than the prior: calibration helps


def test_bake_members_are_the_forecast_ensemble() -> None:
    d = {"style": "home_starter", "levain": {"seed_g": 20, "flour_g": 100, "water_g": 100,
         "flour": {"t65": 1}, "temperature_c": 24}}  # fmt: skip
    inputs = BakeInputs(plan=d, now_h=5.0, measurements=(("rise", 2.0, 15.0), ("rise", 5.0, 90.0)))
    plan = plan_from_dict(d)
    out = forecast(plan, inputs)
    t, values, w = bake.member_values(plan, inputs)
    for key in ("rise", "ph"):
        s = next(s for s in out["series"] if s["key"] == key)
        idx = np.abs(t[:, None] - np.asarray(s["t_h"])[None, :]).argmin(axis=0)
        med = weighted_quantiles(values[key][:, idx], w, (0.5,))[0]
        assert np.allclose(med, s["p50"], atol=0.051), key  # the series' own rounding
