"""Aroma tracers on a forecast ensemble (increment B).

Each odorant obeys dC/dt = S(t) - K(t)·C on every member, with S and K built from the
engine's per-organism growth and flux, its pools, pH and temperature, and from the
batch's ingredients. Templates run in dependency order (precursor -> product), so each
tracer is linear with known coefficients and is integrated exactly per interval. Data:
aroma_data.py; design: docs/superpowers/specs/2026-10-05-aroma-curation.md.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from fermenttrack.prediction import aroma_data as A
from fermenttrack.prediction import engine
from fermenttrack.prediction.derived import mass_left
from fermenttrack.prediction.engine import PI
from fermenttrack.prediction.priors import FloatArray

if TYPE_CHECKING:
    from fermenttrack.prediction.engine import EnsembleParams, Trajectories
    from fermenttrack.prediction.organisms import OrganismKinetics
    from fermenttrack.prediction.profiles import FermentProfile

Draws = dict[str, FloatArray]
Route = tuple[str, str, str]  # (kind: ingredient | organism | chemistry, name, via)


def _phi(x: FloatArray) -> tuple[FloatArray, FloatArray]:
    """phi1 = (1 - e^-x)/x and phi2 = (x - 1 + e^-x)/x^2, stable near 0."""
    small = x < 1e-4
    xs = np.where(small, 1.0, x)
    em = -np.expm1(-xs)
    p1 = np.where(small, 1.0 - x / 2.0 + x * x / 6.0, em / xs)
    p2 = np.where(small, 0.5 - x / 6.0 + x * x / 24.0, (xs - em) / (xs * xs))
    return p1, p2


def integrate(t: FloatArray, source: FloatArray, k: FloatArray, c0: FloatArray) -> FloatArray:
    """C' = S - K·C with S linear and K at its interval mean: exact per interval.
    source (N, T) µg/kg/h, k (N, T) 1/h, c0 (N,) µg/kg -> (N, T) µg/kg."""
    n, nt = source.shape
    c = np.empty((n, nt))
    c[:, 0] = c0
    for i in range(nt - 1):
        h = float(t[i + 1] - t[i])
        if h <= 0.0:
            c[:, i + 1] = c[:, i]
            continue
        x = 0.5 * (k[:, i] + k[:, i + 1]) * h
        p1, p2 = _phi(x)
        s0 = source[:, i]
        s1 = (source[:, i + 1] - s0) / h
        c[:, i + 1] = np.maximum(c[:, i] * np.exp(-x) + s0 * h * p1 + s1 * h * h * p2, 0.0)
    return c


def neutral_fraction(ph: FloatArray, kind: str, pka: float | None) -> FloatArray:
    """Share of an acid or amine in its volatile, uncharged form (curation spec D5)."""
    ph = np.asarray(ph, dtype=float)
    if kind == "acid" and pka is not None:
        return np.asarray(1.0 / (1.0 + 10.0 ** (ph - pka)))
    if kind == "base" and pka is not None:
        return np.asarray(1.0 / (1.0 + 10.0 ** (pka - ph)))
    return np.ones_like(ph)


def draws(n: int, seed: int) -> Draws:
    """Template parameters, thresholds, ingredient pools and the shared matrix factor per
    member: nothing observes them yet, so prior draws are their posterior (spec 2026-10-02
    § 1). Each value is (N, 1)."""
    priors = dict(A.PARAMS)
    priors.update({f"thr:{k}": c.threshold for k, c in A.COMPOUNDS.items() if c.threshold})
    priors.update({f"ing:{i}:{k}": p for i, e in A.AROMA_INGREDIENTS.items() for k, p in e.items()})
    z = np.random.default_rng(seed).standard_normal((n, len(priors)))
    out = {}
    for j, (k, p) in enumerate(priors.items()):
        v = np.asarray(p.value(z[:, j]))
        # Split-normal tails can cross 0 (lin rates) or 1 (shares, either scale). Shares
        # stop at 0.95 so that s / (1 - s) stays finite in the templates.
        if k.startswith(("share_", "excr_")):
            v = np.clip(v, 0.0, 0.95)
        elif p.scale == "lin":
            v = np.maximum(v, 0.0)
        out[k] = v[:, None]
    return out


def kaw25(key: str, d: Draws) -> FloatArray | float:
    """K_aw at 25 °C: measured (§ 5.12), else the class stand-in x the member's factor."""
    if key in A.KAW:
        return A.KAW[key]
    return A.KAW[A.KAW_CLASS[key]] * d["kaw_standin"]


def volatility(
    key: str, temp: FloatArray, f_neutral: FloatArray, co2_rate: FloatArray, d: Draws,
    co2_escapes: bool, k_surf_d: FloatArray | float = 0.0,
) -> FloatArray:  # fmt: skip
    """Loss rate (1/h): CO2 stripping of the neutral form plus open-surface loss (§ 5.12).
    co2_rate in g/kg/h; k_surf_d in 1/d (0 for a closed jar)."""
    kaw = kaw25(key, d) * d["kaw_tfactor"] ** ((temp - 25.0) / 10.0) * f_neutral
    strip = (np.maximum(co2_rate, 0.0) / 44.01 * 24.5) * kaw * d["kaw_eta"] if co2_escapes else 0.0
    return np.asarray(strip + k_surf_d * kaw / 24.0)


def odour_activity(conc: FloatArray, key: str, f_neutral: FloatArray, d: Draws) -> FloatArray:
    """Concentration of the volatile form over the member's threshold x shared matrix factor."""
    return np.asarray(conc * f_neutral / (d[f"thr:{key}"] * d["matrix"]))


# ── context: what the engine and the recipe give the templates ──────────

LAB = frozenset({"lab", "lab_hetero", "lactococcus"})
YEAST = frozenset({"yeast"})
NONYEAST_AT = LAB | {"mould"}  # aminotransferase route of non-yeast organisms (§ 5.1)
REDUCERS_LIPID = frozenset({"lab", "lab_hetero", "yeast"})  # § 5.8: not Lactococcus
_LAB_GENERA = ("Lactobacillus", "Leuconostoc", "Tetragenococcus")
_NOT_AROMA = frozenset({"Water"})  # logged, but no aroma data expected


def organism_class(kin: OrganismKinetics) -> str:
    """The template class of a model organism (yeast, LAB kinds, AAB, mould, unknown)."""
    if kin.kingdom == "yeast":
        return "yeast"
    if kin.kingdom == "mold":
        return "mould"
    if kin.obligate_aerobe:
        return "aab"
    if kin.name.startswith("Lactococcus"):
        return "lactococcus"
    if any({"lactic_acid", "ethanol"} <= ch.products.keys() for ch in kin.channels):
        return "lab_hetero"
    return "lab" if kin.name.startswith(_LAB_GENERA) else "unknown"


def ingredient_shares(
    items: list[tuple[str, float | None, str]], ferment: str
) -> tuple[dict[str, float], list[str]]:
    """Mass share of each logged ingredient (name, grams, role), and the ingredients that
    carry no aroma data. No quantified item: the type's default ingredients."""
    weighed = [(n, g, r) for n, g, r in items if g is not None and g > 0.0]
    total = sum(g for _, g, _ in weighed)
    if total <= 0.0:
        return dict(A.DEFAULT_INGREDIENTS.get(ferment, {})), []
    shares: dict[str, float] = {}
    for n, g, _ in weighed:
        shares[n] = shares.get(n, 0.0) + g / total
    no_data = [
        n for n, _, r in weighed
        if n not in A.AROMA_INGREDIENTS and n not in _NOT_AROMA and r not in ("starter", "additive")
    ]  # fmt: skip
    return shares, list(dict.fromkeys(no_data))


@dataclass
class Context:
    t: FloatArray  # (T,) h
    pools: FloatArray  # (N, T, P) g/kg
    ph: FloatArray  # (N, T)
    temp: FloatArray  # (N, T) °C
    co2: FloatArray  # (N, T) g/kg/h
    left: FloatArray  # (N, T) mass share still in the jar
    growth: list[FloatArray]  # per organism (N, T) g/kg/h
    flux: list[FloatArray]  # per organism (N, T) hexose-equivalent g/kg/h
    biomass: FloatArray  # (N, T, M) g/kg
    x_max: list[FloatArray]  # per organism (N, 1) g/kg
    names: list[str]
    classes: list[str]
    products: list[frozenset[str]]  # engine pools each organism makes
    shares: dict[str, float]  # ingredient -> mass share
    ferment: str
    co2_escapes: bool


def build_context(
    params: EnsembleParams, tr: Trajectories, profile: FermentProfile,
    shares: dict[str, float], co2_escapes: bool,
) -> Context:  # fmt: skip
    if tr.y is None:
        raise ValueError("aroma needs raw states (simulate(..., keep_states=True))")
    diag = engine.diagnose(params, tr.t_h, tr.y)
    orgs = params.organisms
    temp = np.stack(
        [np.broadcast_to(params.temperature(float(ti)), (params.n,)) for ti in tr.t_h], axis=1
    )
    return Context(
        t=np.asarray(tr.t_h, dtype=float), pools=tr.pools, ph=tr.ph, temp=temp,
        co2=diag["co2"], left=mass_left(tr.pools, co2_escapes),
        growth=[diag[f"growth:{j}"] for j in range(len(orgs))],
        flux=[diag[f"flux:{j}"] for j in range(len(orgs))],
        biomass=tr.biomass_g, x_max=[o.x_max_g[:, None] for o in orgs],
        names=[o.kin.name for o in orgs], classes=[organism_class(o.kin) for o in orgs],
        products=[frozenset(k for ch in o.kin.channels for k in ch.products) for o in orgs],
        shares=dict(shares), ferment=profile.type, co2_escapes=co2_escapes,
    )  # fmt: skip


def _gate(ctx: Context, cls: Iterable[str]) -> FloatArray:
    """Σ X_j / x_max_j over organisms of these classes: the k_max multiplier (N, T)."""
    cls = set(cls)
    out = np.zeros_like(ctx.ph)
    for j, c in enumerate(ctx.classes):
        if c in cls:
            out = out + ctx.biomass[:, :, j] / ctx.x_max[j]
    return out


def _flux(
    ctx: Context, cls: Iterable[str], mult: Callable[[str], FloatArray | float] | None = None
) -> FloatArray:
    """Σ v_j (hexose-equivalent g/kg/h) over organisms of these classes, x a per-name factor."""
    cls = set(cls)
    out = np.zeros_like(ctx.ph)
    for j, c in enumerate(ctx.classes):
        if c in cls:
            out = out + ctx.flux[j] * (mult(ctx.names[j]) if mult else 1.0)
    return out


# ── templates ───────────────────────────────────────────────────────────

EHRLICH = "Ehrlich pathway (amino acids → fusel alcohols)"
AA_BREAKDOWN = "amino-acid breakdown"
ESTERS = "ester synthesis"
_ALD_ALC = (  # aldehyde -> the alcohol it is reduced to (§ 5.1)
    ("methylbutanal_3", "methylbutanol_3"), ("methylbutanal_2", "methylbutanol_2"),
    ("methylpropanal_2", "methylpropanol_2"), ("phenylacetaldehyde", "phenylethanol_2"),
    ("methional", "methionol"),
)  # fmt: skip
_ALC_ALD_ACID = (  # yeast Ehrlich products (§ 5.1)
    ("methylbutanol_3", "methylbutanal_3", "methylbutanoic_3"),
    ("methylbutanol_2", "methylbutanal_2", "methylbutanoic_2"),
    ("methylpropanol_2", "methylpropanal_2", "methylpropanoic_2"),
    ("phenylethanol_2", "phenylacetaldehyde", None),
)
_AA_ROUTE = (  # amino acid, share, aldehyde, acid (§ 5.1)
    ("leucine", "share_leu", "methylbutanal_3", "methylbutanoic_3"),
    ("isoleucine", "share_ile", "methylbutanal_2", "methylbutanoic_2"),
    ("valine", "share_val", "methylpropanal_2", "methylpropanoic_2"),
    ("phenylalanine", "share_phe", "phenylacetaldehyde", None),
    ("methionine", "share_met", "methional", None),
)
_KHYD = {  # ester -> hydrolysis constant (§ 5.5)
    "isoamyl_acetate": "khyd_iaac", "isobutyl_acetate": "khyd_ibac",
    "phenylethyl_acetate": "khyd_peac", "ethyl_butanoate": "khyd_eb",
    "ethyl_hexanoate": "khyd_eh", "ethyl_octanoate": "khyd_eo",
    "ethyl_acetate": "khyd_other", "ethyl_lactate": "khyd_other",
    "ethyl_decanoate": "khyd_other", "ethyl_2methylbutanoate": "khyd_other",
    "ethyl_2methylpropanoate": "khyd_other",
}  # fmt: skip
_ESTERIFIED = {  # chemical ester -> (acid pool, g/mol, pKa) (§ 5.5)
    "ethyl_acetate": ("acetic_acid", 60.05, 4.76),
    "ethyl_lactate": ("lactic_acid", 90.08, 3.86),
}
_CARRIED_VIA = {  # initial pools that are a precursor's product (named after it)
    "dmds": "@smcso", "dmts": "@smcso", "butenyl_itc": "@gluconapin", "allyl_itc": "@sinigrin",
}  # fmt: skip
SMCSO_REF = 5700.0  # µmol/kg: a cabbage-only batch at § 6.1's median; est. (B1)
METHIONAL_SHARE = 0.2  # of converted methionine not ending as methionol; est. (B1)


def _is_km(name: str) -> bool:
    return name.startswith("Kluyveromyces")


class _Tracers:
    """Sources, losses and initial pools per compound; `solve` integrates one when final."""

    def __init__(self, ctx: Context, d: Draws) -> None:
        self.ctx, self.d = ctx, d
        self.zero = np.zeros_like(ctx.ph)
        self.src: dict[str, FloatArray] = {}
        self.k: dict[str, FloatArray] = {}
        self.c0: dict[str, FloatArray] = {}
        self.conc: dict[str, FloatArray] = {}
        self.routes: dict[str, list[Route]] = {}

    def route(self, key: str, r: Route) -> None:
        lst = self.routes.setdefault(key, [])
        if r not in lst:
            lst.append(r)

    def organisms(self, key: str, cls: Iterable[str], via: str) -> None:
        """Route `key` to every organism of these classes that ferments anything."""
        cls = set(cls)
        for j, (name, c) in enumerate(zip(self.ctx.names, self.ctx.classes, strict=True)):
            if c in cls and float(np.max(self.ctx.flux[j])) > 0.0:
                self.route(key, ("organism", name, via))

    def add(self, key: str, arr: FloatArray | float) -> bool:
        """Add a source (µg/kg/h); True when it is positive somewhere."""
        a = np.broadcast_to(np.asarray(arr, dtype=float), self.zero.shape)
        self.src[key] = self.src.get(key, self.zero) + a
        return bool(np.any(a > 0.0))

    def loss(self, key: str, arr: FloatArray | float) -> None:
        a = np.broadcast_to(np.asarray(arr, dtype=float), self.zero.shape)
        self.k[key] = self.k.get(key, self.zero) + a

    def f_neutral(self, key: str) -> FloatArray:
        c = A.COMPOUNDS[key]
        return neutral_fraction(self.ctx.ph, c.ph_kind, c.pka)

    def solve(
        self, key: str, *, c0: FloatArray | None = None, src: FloatArray | None = None,
        k: FloatArray | None = None,
    ) -> FloatArray:  # fmt: skip
        """Integrate `key` with its own (or the given) source, loss and initial pool, plus
        volatility. Stored as the compound's tracer unless explicit parts were given."""
        ctx, d = self.ctx, self.d
        vol = volatility(key, ctx.temp, self.f_neutral(key), ctx.co2, d, ctx.co2_escapes)
        c0_ = self.c0.get(key, self.zero[:, 0]) if c0 is None else c0
        src_ = self.src.get(key, self.zero) if src is None else src
        k_ = (self.k.get(key, self.zero) if k is None else k) + vol
        out = integrate(ctx.t, src_, k_, c0_)
        if c0 is None and src is None and k is None:
            self.conc[key] = out
        return out


def concentrations(
    ctx: Context, d: Draws
) -> tuple[dict[str, FloatArray], dict[str, list[Route]]]:
    """µg/kg (N, T) of every compound the batch can make, and where each one comes from.
    Keys starting with "_" are internal (tests only)."""
    tr = _Tracers(ctx, d)
    temp, mw = ctx.temp, A.MW

    def q(key: str, ref: float) -> FloatArray:
        return np.asarray(d[key] ** ((temp - ref) / 10.0))

    # 1. ingredient pools (§ 6): compounds carried in, and precursors
    pre: dict[str, FloatArray] = {}
    pre_from: dict[str, list[str]] = {}
    for name, share in ctx.shares.items():
        for key in A.AROMA_INGREDIENTS.get(name, {}):
            v = share * d[f"ing:{name}:{key}"][:, 0]
            if key.startswith("@"):
                scale = 1.0 if key == "@hexenol_residual" else 1000.0  # µmol/g -> µmol/kg
                pre[key] = pre.get(key, 0.0) + v * scale
                pre_from.setdefault(key, []).append(name)
            else:
                tr.c0[key] = tr.c0.get(key, 0.0) + v
                via = A.PRECURSOR_LABEL.get(_CARRIED_VIA.get(key, ""), "carried in")
                tr.route(key, ("ingredient", name, via))

    def from_precursor(key: str, p: str) -> None:
        for name in pre_from.get(p, []):
            tr.route(key, ("ingredient", name, A.PRECURSOR_LABEL[p]))

    # 2. T1, yeast Ehrlich (§ 5.1); Q10 reference 23 °C (middle of Godillot's series)
    def m_yeast(name: str) -> FloatArray | float:
        return 1.0 if name.startswith("Saccharomyces") else d["mult_nonsacch"]

    def m_pe(name: str) -> FloatArray | float:
        return d["mult_km_pe"] if _is_km(name) else m_yeast(name)

    fy = _flux(ctx, YEAST, m_yeast)
    f_lab = _flux(ctx, LAB)
    mb = 1000.0 * (d["b_mb_yeast"] * q("q10_mb", 23.0) * fy + d["b_mb_lab"] * f_lab)
    alc = {
        "methylbutanol_3": mb * (1.0 - d["share_2mb"]),
        "methylbutanol_2": mb * d["share_2mb"],
        "methylpropanol_2": 1000.0 * d["b_mp_yeast"] * q("q10_mp", 23.0) * fy,
        "phenylethanol_2": 1000.0 * d["b_pe_yeast"] * _flux(ctx, YEAST, m_pe),
    }
    s_acid, s_ald = d["share_fusel_acid"], d["share_fusel_ald"]
    for a, ald, acid in _ALC_ALD_ACID:
        if tr.add(a, alc[a]):
            tr.organisms(a, YEAST, EHRLICH)
            if a.startswith("methylbutanol"):
                tr.organisms(a, LAB, EHRLICH)
        if tr.add(ald, alc[a] * s_ald / (1.0 - s_acid) * mw[ald] / mw[a]):
            tr.organisms(ald, YEAST, EHRLICH)
        if acid and tr.add(acid, alc[a] * s_acid / (1.0 - s_acid) * mw[acid] / mw[a]):
            tr.organisms(acid, YEAST, EHRLICH)
    aa = ctx.pools[:, :, PI["amino_acids"]] * 1e6 / ctx.left  # µg/kg free amino acids
    met = d["kmax_met_yeast"] / 24.0 * _gate(ctx, YEAST) * aa * d["share_met"]
    if tr.add("methionol", met * d["share_methionol"] * mw["methionol"] / mw["methionine"]):
        tr.organisms("methionol", YEAST, EHRLICH)
    rest = met * (1.0 - d["share_methionol"]) * METHIONAL_SHARE
    if tr.add("methional", rest * mw["methional"] / mw["methionine"]):
        tr.organisms("methional", YEAST, EHRLICH)

    # 3. T1, aminotransferase route of LAB and moulds (§ 5.1)
    g_at = d["kmax_at_nonyeast"] / 24.0 * _gate(ctx, NONYEAST_AT)
    for aa_key, aa_share, ald, acid in _AA_ROUTE:
        f = g_at * aa * d[aa_share]
        if tr.add(ald, f * (1.0 - s_acid) * mw[ald] / mw[aa_key]):
            tr.organisms(ald, NONYEAST_AT, AA_BREAKDOWN)
        if acid and tr.add(acid, f * s_acid * mw[acid] / mw[aa_key]):
            tr.organisms(acid, NONYEAST_AT, AA_BREAKDOWN)

    # 4. aldehydes, then the alcohols they are reduced to. ponytail: the yeast route's 1 %
    # aldehyde share is also inside its measured alcohol yield, so it counts twice (well
    # inside the b-term ranges).
    k_red = d["kmax_ald_reduction"] / 24.0 * _gate(ctx, YEAST | LAB)
    for ald, a in _ALD_ALC:
        tr.loss(ald, k_red)
        if ald in tr.src or ald in tr.c0:
            c_ald = tr.solve(ald)
            if tr.add(a, k_red * c_ald * mw[a] / mw[ald]):
                for r in tr.routes.get(ald, []):
                    tr.route(a, r)
    for a in (*alc, "methionol", "methylbutanoic_3", "methylbutanoic_2", "methylpropanoic_2"):
        if a in tr.src or a in tr.c0:
            tr.solve(a)

    # 5. T2 esters and medium-chain fatty acids (§ 5.2)
    def km_acet(name: str) -> FloatArray | float:
        return d["mult_km_acetates"] if _is_km(name) else 1.0

    fy_acet = _flux(ctx, YEAST, lambda n: m_yeast(n) * km_acet(n))
    fpe_acet = _flux(ctx, YEAST, lambda n: m_pe(n) * km_acet(n))
    acetates = {
        "isoamyl_acetate": d["ratio_iaac"] * 1000.0 * d["b_mb_yeast"] * q("q10_mb", 23.0)
        * (1.0 - d["share_2mb"]) * fy_acet * mw["isoamyl_acetate"] / mw["methylbutanol_3"],
        "isobutyl_acetate": d["ratio_other_acetates"] * 1000.0 * d["b_mp_yeast"]
        * q("q10_mp", 23.0) * fy_acet * mw["isobutyl_acetate"] / mw["methylpropanol_2"],
        "phenylethyl_acetate": d["ratio_other_acetates"] * 1000.0 * d["b_pe_yeast"]
        * fpe_acet * mw["phenylethyl_acetate"] / mw["phenylethanol_2"],
    }  # fmt: skip
    for key, s in acetates.items():
        if tr.add(key, s):
            tr.organisms(key, YEAST, ESTERS)
    q_ee = q("q10_ethyl_esters", 23.0)
    for key, b in (
        ("ethyl_butanoate", "b_eb"), ("ethyl_hexanoate", "b_eh"), ("ethyl_octanoate", "b_eo"),
        ("ethyl_decanoate", "b_ed"), ("ethyl_2methylbutanoate", "b_e2mb"),
        ("ethyl_2methylpropanoate", "b_e2mb"),
    ):  # fmt: skip
        if tr.add(key, 1000.0 * d[b] * q_ee * fy):
            tr.organisms(key, YEAST, ESTERS)
    for key in ("ethyl_butanoate", "ethyl_2methylbutanoate"):
        if tr.add(key, 1000.0 * d["b_eb_lab"] * f_lab):
            tr.organisms(key, LAB, ESTERS)
    ea = 1000.0 * (
        d["b_ea_sc"] * _flux(ctx, YEAST, lambda n: 0.0 if _is_km(n) else m_yeast(n))
        + d["b_ea_km"] * _flux(ctx, YEAST, lambda n: 1.0 if _is_km(n) else 0.0)
    )
    if tr.add("ethyl_acetate", ea):
        tr.organisms("ethyl_acetate", YEAST, ESTERS)
    if tr.add("ethyl_acetate", 1000.0 * d["b_ea_lab_hetero"] * _flux(ctx, {"lab_hetero"})):
        tr.organisms("ethyl_acetate", {"lab_hetero"}, ESTERS)
    for key, ex in (("hexanoic", 1.0), ("octanoic", d["excr_c8"]), ("decanoic", d["excr_c10"])):
        if tr.add(key, 1000.0 * d["b_mcfa"] * ex * fy):
            tr.organisms(key, YEAST, ESTERS)

    # 6. T5 chemistry (§ 5.5): hydrolysis of every ester, esterification of acetic and
    # lactic acid (forward = k_hyd·K/55.5·[neutral acid]·[EtOH], mol/kg)
    ph = ctx.ph
    etoh = ctx.pools[:, :, PI["ethanol"]] / 46.07 / ctx.left
    for key, kh in _KHYD.items():
        rate = d[kh] * 1e-9 * 3600.0 * 10.0 ** (d["khyd_n"] * (3.58 - ph)) * q("khyd_q10", 21.0)
        tr.loss(key, rate)
        if key in _ESTERIFIED:
            pool, m_acid, pka = _ESTERIFIED[key]
            acid_m = ctx.pools[:, :, PI[pool]] / m_acid / ctx.left
            acid_m = acid_m * neutral_fraction(ph, "acid", pka)
            if tr.add(key, rate * d["ester_k"] / 55.5 * acid_m * etoh * mw[key] * 1e6):
                tr.route(key, ("chemistry", "acid + ethanol", "esterification"))
        if key in tr.src or key in tr.c0:
            tr.solve(key)
    for key in ("hexanoic", "octanoic", "decanoic"):
        if key in tr.src or key in tr.c0:
            tr.solve(key)

    # 7. T3 acetaldehyde (§ 5.3)
    ac = 1000.0 * (
        d["b_acetaldehyde_yeast"] * _flux(ctx, YEAST, lambda n: 0.0 if _is_km(n) else m_yeast(n))
        + d["b_acetaldehyde_km"] * _flux(ctx, YEAST, lambda n: 1.0 if _is_km(n) else 0.0)
    )
    if tr.add("acetaldehyde", ac):
        tr.organisms("acetaldehyde", YEAST, "pyruvate overflow")
    if tr.add("acetaldehyde", 1000.0 * d["b_acetaldehyde_lab"] * f_lab):
        tr.organisms("acetaldehyde", LAB, "pyruvate overflow")
    tr.loss("acetaldehyde", d["kmax_acetaldehyde_yeast"] / 24.0 * _gate(ctx, YEAST))

    # 8. T4, sugar route (§ 5.4): acetoin, reduced to 2,3-butanediol
    if tr.add("acetoin", 1000.0 * d["b_acetoin_lab"] * f_lab):
        tr.organisms("acetoin", LAB, "sugar → acetoin")
    k_bdo = d["kmax_acetoin_bdo"] / 24.0 * _gate(ctx, YEAST | LAB)
    tr.loss("acetoin", k_bdo)
    if "acetoin" in tr.src or "acetoin" in tr.c0:
        acetoin = tr.solve("acetoin")
        if tr.add("butanediol_23", k_bdo * acetoin * mw["butanediol_23"] / mw["acetoin"]):
            for r in tr.routes.get("acetoin", []):
                tr.route("butanediol_23", r)

    # 9. T6 glucosinolates (§ 5.6): myrosinase release -> isothiocyanate / nitrile
    k_rel = d["gsl_release"] / 24.0 * q("q10_default", 20.0)
    for p, itc, nitrile in (
        ("@sinigrin", "allyl_itc", "allyl_cyanide"), ("@gluconapin", "butenyl_itc", None),
    ):  # fmt: skip
        if p in pre:
            gsl = integrate(ctx.t, tr.zero, k_rel, pre[p])  # µmol/kg still bound
            tr.conc[f"_released:{p}"] = pre[p][:, None] - gsl
            rate = k_rel * gsl * d["gsl_volatile_share"]  # µmol/kg/h of volatile product
            if tr.add(itc, rate * d["itc_fraction"] * mw[itc]):
                from_precursor(itc, p)
            if nitrile and tr.add(nitrile, rate * (1.0 - d["itc_fraction"]) * mw[nitrile]):
                from_precursor(nitrile, p)
        tr.loss(itc, d["itc_loss"] / 24.0 * q("q10_default", 15.0))

    # 10. T7 sulfur (§ 5.7): a burst pool made at salting + a LAB fermentation pool that
    # scales with the batch's S-methylcysteine sulfoxide
    if "@smcso" in pre:
        fl = f_lab * (pre["@smcso"] / SMCSO_REF)[:, None]
        k_mesh = d["mesh_oxidation"] / 24.0
        dmds_made = 1000.0 * d["b_dmds_lab"] * fl  # µg/kg/h of DMDS-equivalent sulfur
        if tr.add("methanethiol", dmds_made * 2.0 * mw["methanethiol"] / mw["dmds"]):
            tr.organisms("methanethiol", LAB, "sulfur metabolism")
            from_precursor("methanethiol", "@smcso")
        tr.loss("methanethiol", k_mesh)
        mesh = tr.solve("methanethiol")
        if tr.add("dms", d["dms_per_dmds"] * dmds_made / mw["dmds"] * mw["dms"]):
            tr.organisms("dms", LAB, "sulfur metabolism")
            from_precursor("dms", "@smcso")
        made = {
            "dmds": k_mesh * mesh * mw["dmds"] / (2.0 * mw["methanethiol"]),
            "dmts": 1000.0 * d["b_dmts_lab"] * fl,
        }
    else:
        made = {"dmds": tr.zero, "dmts": tr.zero}
    for key, decay in (("dmds", "dmds_burst_decay"), ("dmts", "dmts_burst_decay")):
        has_burst = key in tr.c0
        if not has_burst and not np.any(made[key] > 0.0):
            continue
        k_burst = d[decay] / 24.0 * q("q10_default", 15.0) * np.ones_like(tr.zero)
        burst = tr.solve(key, c0=tr.c0.get(key, tr.zero[:, 0]), src=tr.zero, k=k_burst)
        ferm = tr.solve(key, c0=tr.zero[:, 0], src=made[key], k=tr.zero)
        if np.any(made[key] > 0.0):
            tr.organisms(key, LAB, "sulfur metabolism")
        tr.conc[key] = burst + ferm

    # 11. T8 vegetables (§ 5.8): reduction by LAB and yeast, brine loss, residual release
    red = d["kmax_lipid_reduction"] / 24.0 * _gate(ctx, REDUCERS_LIPID)
    brine = ctx.ferment == "lacto_ferment"
    for key in ("hexanal", "nonanal", "e2_nonenal"):
        tr.loss(key, red)
    if brine:
        for key in ("e2_nonenal", "z3_hexenal"):
            tr.loss(key, d["brine_aldehyde_loss"] / 24.0)
        tr.loss("z3_hexenol", d["hexenol_loss"] / 24.0 * q("q10_default", 15.0))
    if "@hexenol_residual" in pre:
        r_rel = d["hexenol_release"] / 24.0 * q("q10_default", 15.0)
        residual = integrate(ctx.t, tr.zero, r_rel, pre["@hexenol_residual"])
        if tr.add("z3_hexenol", r_rel * residual):
            from_precursor("z3_hexenol", "@hexenol_residual")
    tr.loss("linalool", d["loss_linalool"] / 24.0 * q("q10_default", 30.0))

    # everything not solved above (carried in, or a source without its own step)
    for key in [*tr.c0, *tr.src]:
        if key not in tr.conc:
            tr.solve(key)

    # 12. engine pools (§ 3 `engine`)
    for key, pool in (("acetic", "acetic_acid"), ("ethanol", "ethanol")):
        v = ctx.pools[:, :, PI[pool]] * 1e6 / ctx.left
        if np.any(v > 0.0):
            tr.conc[key] = v
            for j, name in enumerate(ctx.names):
                if pool in ctx.products[j] and float(np.max(ctx.flux[j])) > 0.0:
                    tr.route(key, ("organism", name, "the fermentation itself"))

    # a template whose producers are absent leaves an all-zero, routeless tracer: not made
    made_here = {
        k: v for k, v in tr.conc.items() if k.startswith("_") or k in tr.routes or np.any(v > 0.0)
    }
    return made_here, {k: r for k, r in tr.routes.items() if k in made_here}


# ── odour activity, series sums, and what is not modelled ──────────────

FLOOR = 1e-3  # odour activity floor for log10 values (a thousandth of the threshold)
_LATER = {  # evidence compounds without a B1 route -> why (curation spec § 4, § 11)
    "diacetyl": "the citrate → α-acetolactate chain arrives in a later increment",
    "pentanedione_23": "the citrate → α-acetolactate chain arrives in a later increment",
    "linalool": "bound terpenes of the vegetable are not curated yet",
    "geraniol": "bound terpenes of the vegetable are not curated yet",
    "carvone": "the spice precursor (caraway, dill, mint) is not curated yet",
    "geranial": "the spice precursor (ginger, lemongrass, citrus) is not curated yet",
    "neral": "the spice precursor (ginger, lemongrass, citrus) is not curated yet",
    "vinylguaiacol_4": "the vegetable's ferulic acid is not curated yet",
    "methional": "the vegetable's free amino acids are not tracked yet",
    "phenylacetaldehyde": "the vegetable's free amino acids are not tracked yet",
}


@dataclass
class AromaResult:
    conc: dict[str, FloatArray]  # µg/kg (N, T)
    oav: dict[str, FloatArray]  # odour activity (N, T): active compounds with a threshold
    series: dict[str, FloatArray]  # log10 summed odour activity per aromatic series (N, T)
    members: dict[str, list[str]]  # series -> its compounds in this batch
    compounds: list[str]  # computed compounds, by evidence tier then key
    routes: dict[str, list[Route]]
    tiers: dict[str, tuple[str, str, tuple[str, ...]]]  # key -> (tier, anchor, sources)
    not_modelled: dict[str, list[str]]  # notes, organisms, ingredients


def _empty(note: str, no_data: list[str]) -> AromaResult:
    return AromaResult({}, {}, {}, {}, [], {}, {}, {"notes": [note], "organisms": [],
                                                   "ingredients": no_data})  # fmt: skip


def evaluate(
    params: EnsembleParams, tr: Trajectories, profile: FermentProfile,
    shares: dict[str, float], no_data: list[str], seed: int, co2_escapes: bool,
) -> AromaResult:  # fmt: skip
    """Aroma for every member at every time: concentrations, odour activities and series
    sums (every active compound with a threshold counts: owner decision 2026-10-06)."""
    if profile.type not in A.B1_TYPES or tr.y is None:
        return _empty(f"Aroma for {profile.type.replace('_', ' ')} arrives in a later increment.",
                      no_data)  # fmt: skip
    ctx = build_context(params, tr, profile, shares, co2_escapes)
    d = draws(params.n, seed)
    conc, routes = concentrations(ctx, d)
    evidence = A.EVIDENCE.get(profile.type, {})
    made = [k for k in conc if not k.startswith("_")]
    oav: dict[str, FloatArray] = {}
    members: dict[str, list[str]] = {}
    for key in made:
        c = A.COMPOUNDS[key]
        if c.status != "active" or c.threshold is None:
            continue
        oav[key] = odour_activity(conc[key], key, neutral_fraction(ctx.ph, c.ph_kind, c.pka), d)
        for s in c.series:
            members.setdefault(s, []).append(key)
    series = {
        s: np.log10(np.maximum(np.sum([oav[k] for k in ks], axis=0), FLOOR))
        for s, ks in members.items()
    }
    rank = {"calibrated": 0, "reported": 1, "plausible": 2, "engine": 3}
    tiers = {k: evidence.get(k, ("plausible", "", ())) for k in made}
    notes: dict[str, list[str]] = {}
    for key in evidence:
        c = A.COMPOUNDS[key]
        if key in made and float(np.max(conc[key])) > 0.0:
            continue
        why = (
            "no organism in the model makes it yet" if c.status == "inactive"
            else _LATER.get(key, "no route in this recipe")
        )  # fmt: skip
        notes.setdefault(why, []).append(c.name)
    return AromaResult(
        conc={k: conc[k] for k in made}, oav=oav, series=series, members=members,
        compounds=sorted(made, key=lambda k: (rank[tiers[k][0]], k)), routes=routes,
        tiers=tiers,
        not_modelled={
            "notes": [f"{', '.join(names)}: {why}." for why, names in notes.items()],
            "organisms": [n for n, c in zip(ctx.names, ctx.classes, strict=True) if c == "unknown"],
            "ingredients": no_data,
        },
    )  # fmt: skip
