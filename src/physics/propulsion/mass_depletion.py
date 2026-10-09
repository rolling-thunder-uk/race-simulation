# Real-time escaping mass calculations (m_dot)
from __future__ import annotations

import math

from .choke_logic import critical_pressure_ratio


def mass_flow_rate(
    upstream_density_kg_m3: float,
    upstream_pressure_pa: float,
    gamma: float,
    throat_area_m2: float,
    downstream_pressure_pa: float,
    discharge_coefficient: float = 1.0,
) -> tuple[float, bool]:
    """Compressible orifice mass flow.

    Returns the mass flow rate (kg/s, positive out of the canister) and a flag
    indicating whether the throat is choked (sonic).
    """
    if (
        throat_area_m2 <= 0.0
        or upstream_pressure_pa <= downstream_pressure_pa
        or upstream_density_kg_m3 <= 0.0
    ):
        return 0.0, False

    if gamma <= 1.0:
        gamma = 1.0001
    pressure_ratio = downstream_pressure_pa / upstream_pressure_pa
    critical_ratio = critical_pressure_ratio(gamma)

    if pressure_ratio <= critical_ratio:
        choked_term = (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
        flow = (
            discharge_coefficient
            * throat_area_m2
            * math.sqrt(gamma * upstream_pressure_pa * upstream_density_kg_m3)
            * choked_term
        )
        return flow, True

    subcritical_term = (gamma / (gamma - 1.0)) * (
        pressure_ratio ** (2.0 / gamma)
        - pressure_ratio ** ((gamma + 1.0) / gamma)
    )
    flow = discharge_coefficient * throat_area_m2 * math.sqrt(
        max(2.0 * upstream_pressure_pa * upstream_density_kg_m3 * subcritical_term, 0.0)
    )
    return flow, False
