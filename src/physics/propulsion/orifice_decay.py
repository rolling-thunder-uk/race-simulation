# Exponential launcher pin withdrawal area masking
from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_TAU_S = 0.004


def orifice_area(time_s: float, max_area_m2: float, tau_s: float = DEFAULT_TAU_S) -> float:
    """Effective throat area as the launcher pin withdraws.

    A(t) = A_max * (1 - exp(-t / tau)). At t = 0 the seal is closed and the
    area opens asymptotically towards the full geometric throat.
    """
    if max_area_m2 <= 0.0 or tau_s <= 0.0:
        return 0.0
    if time_s <= 0.0:
        return 0.0
    return max_area_m2 * (1.0 - math.exp(-time_s / tau_s))


def area_from_diameter(diameter_m: float) -> float:
    return math.pi * diameter_m**2 / 4.0


@dataclass(frozen=True)
class OrificeProfile:
    max_area_m2: float
    tau_s: float = DEFAULT_TAU_S

    @classmethod
    def from_diameter(cls, diameter_m: float, tau_s: float = DEFAULT_TAU_S) -> "OrificeProfile":
        return cls(max_area_m2=area_from_diameter(diameter_m), tau_s=tau_s)

    def area(self, time_s: float) -> float:
        return orifice_area(time_s, self.max_area_m2, self.tau_s)
