"""Re-estimate the population hierarchy's variance components by REML from the stored
evidence (table batch_evidence; prediction/variance_components.py). Prints, per ferment type
x organism x parameter, the rows, the levels per factor, the estimates +- se [95 % CI] and the
identifiability verdict; then the pooled fit per ferment type (shared components; the only
one that estimates v_global) and its proposed VARIANCES. Changes nothing: copy the proposal
into prediction/population.py by hand if the decision rule (sourdough spec § 6.2) holds.

Rows used are the ones the app conditions on: outcome == "success", per ferment type.

Usage:
    FERMENTTRACK_DATABASE_URL=... python scripts/estimate_variance_components.py
    python scripts/estimate_variance_components.py --csv evidence.csv
      (columns: ferment_type, outcome, organism, param, style, owner_id, culture_id, ell, lam)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from collections.abc import Iterable, Mapping

from fermenttrack.prediction.population import VARIANCES, Row
from fermenttrack.prediction.variance_components import Fit, estimate, estimate_pooled

Key = tuple[str, str, str]  # ferment type, organism, param


def group(records: Iterable[Mapping[str, object]]) -> dict[Key, list[Row]]:
    out: dict[Key, list[Row]] = {}
    for r in records:
        if r["outcome"] != "success":
            continue
        out.setdefault((str(r["ferment_type"]), str(r["organism"]), str(r["param"])), []).append(
            Row(
                r["style"] or None,
                r["owner_id"] or None,
                str(r["culture_id"]),  # type: ignore[arg-type]
                float(r["ell"]),
                float(r["lam"]),
            )  # type: ignore[arg-type]
        )
    return out


def from_csv(path: str) -> dict[Key, list[Row]]:
    with open(path, newline="", encoding="utf-8") as f:
        return group(csv.DictReader(f))


async def from_db() -> dict[Key, list[Row]]:
    from sqlalchemy import select

    from fermenttrack.database import async_session_maker
    from fermenttrack.models import BatchEvidence

    async with async_session_maker() as db:
        rows = (await db.execute(select(BatchEvidence))).scalars().all()
    return group(
        {
            c: getattr(e, c)
            for c in (
                "ferment_type",
                "outcome",
                "organism",
                "param",
                "style",
                "owner_id",
                "culture_id",
                "ell",
                "lam",
            )
        }
        for e in rows
    )


def show(title: str, fit: Fit) -> None:
    lv = fit.levels
    print(
        f"\n{title}: n={fit.n}  styles={lv.get('style', 0)} bakers={lv.get('baker', 0)} "
        f"starters={lv.get('starter', 0)} within-starter df={lv.get('batch', 0)}"
        + (f" groups={lv['global']}" if "global" in lv else "")
        + (
            f"  intercept {fit.intercept[0]:+.3f} +- {fit.intercept[1]:.3f}"
            if fit.intercept
            else ""
        )
        + ("" if fit.converged or fit.loglik is None else "  [optimiser did not converge]")
    )
    for name, c in fit.components.items():
        if not c.identifiable:
            print(f"  {name:8} {c.estimate:6.3f}  default kept: {c.note}")
            continue
        se = f"+- {c.se:.3f}" if c.se is not None else "        "
        ci = f"[{c.ci95[0]:.3f}, {c.ci95[1]:.3f}]" if c.ci95 else ""
        flag = "BOUNDARY " + c.note if c.boundary else c.note
        print(f"  {name:8} {c.estimate:6.3f} {se} {ci} {flag}")


def main(groups: dict[Key, list[Row]]) -> None:
    if not groups:
        print("No successful evidence rows: keep VARIANCES =", VARIANCES)
        return
    for key in sorted(groups):
        show(" x ".join(key), estimate(groups[key]))
    for ftype in sorted({k[0] for k in groups}):
        fit = estimate_pooled({k: v for k, v in groups.items() if k[0] == ftype})
        show(f"POOLED {ftype} (shared components, g random with mean 0)", fit)
        proposed = {k: round(v, 3) for k, v in fit.proposed().items()}
        print(
            f"  proposed VARIANCES for {ftype} = {proposed}  (sum {sum(proposed.values()):.2f}; "
            f"current {VARIANCES})"
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", help="read an export instead of FERMENTTRACK_DATABASE_URL")
    a = ap.parse_args()
    main(from_csv(a.csv) if a.csv else asyncio.run(from_db()))
