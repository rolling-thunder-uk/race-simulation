# Pressure ratios separating choked and unchoked states
from __future__ import annotations

from .gas_state import FluidState, effective_isentropic_exponent


def critical_pressure_ratio(gamma: float) -> float:
    """P*/P0 below which the throat reaches sonic (choked) conditions."""
    if gamma <= 1.0:
        gamma = 1.0001
    return (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))


def is_choked(
    upstream_pressure_pa: float,
    downstream_pressure_pa: float,
    gamma: float,
) -> bool:
    if upstream_pressure_pa <= 0.0:
        return False
    return (
        downstream_pressure_pa / upstream_pressure_pa
        <= critical_pressure_ratio(gamma)
    )


def isentropic_exponent(state: FluidState) -> float:
    return effective_isentropic_exponent(state)
