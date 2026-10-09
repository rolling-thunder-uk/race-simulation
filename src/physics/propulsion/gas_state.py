# Hyper-fast direct T-P state inversion calls
from __future__ import annotations

from dataclasses import dataclass

import CoolProp.CoolProp as CP

FLUID = "CO2"


class FluidPropertyError(RuntimeError):
    """Raised when the NIST Helmholtz backend cannot resolve a fluid state."""


@dataclass(frozen=True)
class FluidState:
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    internal_energy_j_kg: float
    enthalpy_j_kg: float
    entropy_j_kg_k: float
    sound_speed_m_s: float | None
    cp_j_kg_k: float
    phase: str
    quality: float | None

    @property
    def is_two_phase(self) -> bool:
        return self.quality is not None


def _prop(output: str, name_a: str, value_a: float, name_b: str, value_b: float) -> float:
    try:
        return float(CP.PropsSI(output, name_a, value_a, name_b, value_b, FLUID))
    except Exception as exc:  # CoolProp raises ValueError / RuntimeError
        raise FluidPropertyError(
            f"CO2 {output} failed for {name_a}={value_a:g}, {name_b}={value_b:g}"
        ) from exc


def _phase(name_a: str, value_a: float, name_b: str, value_b: float) -> str:
    try:
        return str(CP.PhaseSI(name_a, value_a, name_b, value_b, FLUID))
    except Exception:
        return "unknown"


def _build_state(
    temperature_k: float,
    pressure_pa: float,
    density_kg_m3: float,
    internal_energy_j_kg: float,
    quality: float | None,
    phase: str,
) -> FluidState:
    enthalpy = _prop("H", "D", density_kg_m3, "U", internal_energy_j_kg)
    entropy = _prop("S", "D", density_kg_m3, "U", internal_energy_j_kg)
    cp = _prop("C", "D", density_kg_m3, "U", internal_energy_j_kg)
    try:
        sound_speed = _prop("A", "D", density_kg_m3, "U", internal_energy_j_kg)
    except FluidPropertyError:
        sound_speed = None
    return FluidState(
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        density_kg_m3=density_kg_m3,
        internal_energy_j_kg=internal_energy_j_kg,
        enthalpy_j_kg=enthalpy,
        entropy_j_kg_k=entropy,
        sound_speed_m_s=sound_speed,
        cp_j_kg_k=cp,
        phase=phase,
        quality=quality,
    )


def state_from_rho_u(density_kg_m3: float, internal_energy_j_kg: float) -> FluidState:
    """Invert the Helmholtz EOS from density and internal energy.

    Valid across single-phase and saturated two-phase states, which is the
    regime the propellant occupies during flash-boiling blowdown.
    """
    if density_kg_m3 <= 0.0:
        raise FluidPropertyError("density must be positive")
    temperature = _prop("T", "D", density_kg_m3, "U", internal_energy_j_kg)
    pressure = _prop("P", "D", density_kg_m3, "U", internal_energy_j_kg)
    raw_quality = _prop("Q", "D", density_kg_m3, "U", internal_energy_j_kg)
    quality = raw_quality if 0.0 <= raw_quality <= 1.0 else None
    phase = _phase("D", density_kg_m3, "U", internal_energy_j_kg)
    return _build_state(
        temperature, pressure, density_kg_m3, internal_energy_j_kg, quality, phase
    )


def state_from_t_p(temperature_k: float, pressure_pa: float) -> FluidState:
    """Direct (T, P) property evaluation with no internal Newton iteration."""
    density = _prop("D", "T", temperature_k, "P", pressure_pa)
    internal_energy = _prop("U", "T", temperature_k, "P", pressure_pa)
    phase = _phase("T", temperature_k, "P", pressure_pa)
    return _build_state(
        temperature_k, pressure_pa, density, internal_energy, None, phase
    )


def state_from_t_q(temperature_k: float, quality: float) -> FluidState:
    density = _prop("D", "T", temperature_k, "Q", quality)
    internal_energy = _prop("U", "T", temperature_k, "Q", quality)
    pressure = _prop("P", "T", temperature_k, "Q", quality)
    return _build_state(
        temperature_k, pressure, density, internal_energy, quality, "twophase"
    )


def saturation_pressure(temperature_k: float) -> float:
    return _prop("P", "T", temperature_k, "Q", 0)


def saturation_temperature(pressure_pa: float) -> float:
    return _prop("T", "P", pressure_pa, "Q", 0)


def critical_point() -> tuple[float, float]:
    return (
        float(CP.PropsSI("Tcrit", FLUID)),
        float(CP.PropsSI("pcrit", FLUID)),
    )


def triple_point() -> tuple[float, float]:
    return (
        float(CP.PropsSI("Ttriple", FLUID)),
        float(CP.PropsSI("ptriple", FLUID)),
    )


def mixture_internal_energy(temperature_k: float, density_kg_m3: float) -> float:
    """Specific internal energy of a saturated mixture at a given (T, rho)."""
    rho_f = _prop("D", "T", temperature_k, "Q", 0)
    rho_g = _prop("D", "T", temperature_k, "Q", 1)
    u_f = _prop("U", "T", temperature_k, "Q", 0)
    u_g = _prop("U", "T", temperature_k, "Q", 1)
    span = (1.0 / rho_g) - (1.0 / rho_f)
    if abs(span) < 1e-12:
        return u_f
    quality = ((1.0 / density_kg_m3) - (1.0 / rho_f)) / span
    quality = min(max(quality, 0.0), 1.0)
    return u_f + quality * (u_g - u_f)


def effective_isentropic_exponent(state: FluidState) -> float:
    """Real-gas isentropic exponent, k = rho * c^2 / P.

    Two-phase speed of sound is undefined, so the saturated vapour value is
    used as the effective exponent driving the homogeneous choked-flow model.
    """
    if state.sound_speed_m_s is not None:
        gamma = state.density_kg_m3 * state.sound_speed_m_s**2 / state.pressure_pa
        return gamma if gamma > 1.0 else 1.0001
    rho_g = _prop("D", "T", state.temperature_k, "Q", 1)
    a_g = _prop("A", "T", state.temperature_k, "Q", 1)
    gamma = rho_g * a_g**2 / state.pressure_pa
    return gamma if gamma > 1.0 else 1.0001
