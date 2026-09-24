"""Prior distributions for kinetic parameters.

A Prior is a literature median plus a ~90 % range. Sampling uses a split normal in
log space (rates, concentrations: strictly positive) or in linear space (temperatures,
pH, offsets), so asymmetric literature ranges keep their shape. Every ensemble member
draws z ~ N(0, 1) per parameter; inference works on those z-scores, so the prior
density is a standard normal whatever the parameter's unit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

Z90 = 1.6448536269514722  # a 90 % interval spans +-1.645 standard deviations

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Prior:
    median: float
    lo: float  # ~5th percentile
    hi: float  # ~95th percentile
    scale: Literal["log", "lin"] = "log"

    def __post_init__(self) -> None:
        if not self.lo <= self.median <= self.hi:
            raise ValueError(f"need lo <= median <= hi, got {self}")
        if self.scale == "log" and self.lo <= 0:
            raise ValueError(f"log-scale prior needs lo > 0, got {self}")

    def value(self, z: FloatArray) -> FloatArray:
        """Map standard-normal draws to parameter values (split normal around the median)."""
        if self.scale == "log":
            s_lo = math.log(self.median / self.lo) / Z90
            s_hi = math.log(self.hi / self.median) / Z90
            return np.asarray(self.median * np.exp(np.where(z < 0, z * s_lo, z * s_hi)))
        s_lo = (self.median - self.lo) / Z90
        s_hi = (self.hi - self.median) / Z90
        return np.asarray(self.median + np.where(z < 0, z * s_lo, z * s_hi))


def fixed(value: float, scale: Literal["log", "lin"] = "log") -> Prior:
    """A parameter held at one value (no spread)."""
    return Prior(value, value, value, scale)
