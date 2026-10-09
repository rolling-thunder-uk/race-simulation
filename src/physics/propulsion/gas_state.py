# Hyper-fast direct T-P state inversion calls
from __future__ import annotations

import threading
from dataclasses import dataclass

import CoolProp.CoolProp as CP
from CoolProp.CoolProp import AbstractState

FLUID = "CO2"

_INPUT_MAP = {
    ("D", "U"): (CP.DmassUmass_INPUTS, False),
    ("T", "P"): (CP.PT_INPUTS, True),
    ("T", "Q"): (CP.QT_INPUTS, True),
    ("P", "Q"): (CP.PQ_INPUTS, False),
}

_READERS = {
    "T": lambda backend: backend.T(),
    "P": lambda backend: backend.p(),
    "D": lambda backend: backend.rhomass(),
    "U": lambda backend: backend.umass(),
    "H": lambda backend: backend.hmass(),
    "S": lambda backend: backend.smass(),
    "C": lambda backend: backend.cpmass(),
    "O": lambda backend: backend.cvmass(),
    "A": lambda backend: backend.speed_sound(),
    "Q": lambda backend: backend.Q(),
}

_local = threading.local()


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


def _backend() -> AbstractState:
    """One high-order Helmholtz state object per thread (process-safe)."""
    backend = getattr(_local, "backend", None)
    if backend is None:
        backend = AbstractState("HEOS", FLUID)
        _local.backend = backend
    return backend


def _update(name_a: str, value_a: float, name_b: str, value_b: float) -> AbstractState:
    entry = _INPUT_MAP.get((name_a, name_b))
    if entry is None:
        raise FluidPropertyError(f"unsupported input pair ({name_a}, {name_b})")
    inputs, swap = entry
    first, second = (value_b, value_a) if swap else (value_a, value_b)
    backend = _backend()
    try:
        backend.update(inputs, float(first), float(second))
    except Exception as exc:
        raise FluidPropertyError(
            f"CO2 update failed for {name_a}={value_a:g}, {name_b}={value_b:g}"
        ) from exc
    return backend


def _prop(output: str, name_a: str, value_a: float, name_b: str, value_b: float) -> float:
    reader = _READERS.get(output)
    if reader is None:
        raise FluidPropertyError(f"unsupported output {output!r}")
    backend = _update(name_a, value_a, name_b, value_b)
    try:
        return float(reader(backend))
    except Exception as exc:
        raise FluidPropertyError(
            f"CO2 {output} failed for {name_a}={value_a:g}, {name_b}={value_b:g}"
        ) from exc


def _phase(name_a: str, value_a: float, name_b: str, value_b: float) -> str:
    return _phase_from(_update(name_a, value_a, name_b, value_b))


def _phase_from(backend: AbstractState) -> str:
    try:
        return str(backend.phase()).rsplit(".", 1)[-1].replace("iphase_", "")
    except Exception:
        return "unknown"


def _state_from_backend(
    backend: AbstractState,
    temperature_k: float,
    pressure_pa: float,
    density_kg_m3: float,
    internal_energy_j_kg: float,
    quality: float | None,
) -> FluidState:
    try:
        sound_speed: float | None = float(backend.speed_sound())
    except Exception:
        sound_speed = None
    return FluidState(
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        density_kg_m3=density_kg_m3,
        internal_energy_j_kg=internal_energy_j_kg,
        enthalpy_j_kg=float(backend.hmass()),
        entropy_j_kg_k=float(backend.smass()),
        sound_speed_m_s=sound_speed,
        cp_j_kg_k=float(backend.cpmass()),
        phase=_phase_from(backend),
        quality=quality,
    )


@dataclass(frozen=True)
class FlowState:
    temperature_k: float
    pressure_pa: float
    enthalpy_j_kg: float
    quality: float | None
    isentropic_exponent: float


def state_from_rho_u(density_kg_m3: float, internal_energy_j_kg: float) -> FluidState:
    """Invert the Helmholtz EOS from density and internal energy.

    Valid across single-phase and saturated two-phase states, which is the
    regime the propellant occupies during flash-boiling blowdown.
    """
    if density_kg_m3 <= 0.0:
        raise FluidPropertyError("density must be positive")
    backend = _update("D", density_kg_m3, "U", internal_energy_j_kg)
    raw_quality = float(backend.Q())
    quality = raw_quality if 0.0 <= raw_quality <= 1.0 else None
    return _state_from_backend(
        backend,
        float(backend.T()),
        float(backend.p()),
        density_kg_m3,
        internal_energy_j_kg,
        quality,
    )


def flow_from_rho_u(density_kg_m3: float, internal_energy_j_kg: float) -> FlowState:
    """Minimal property set the ODE right-hand side actually needs.

    A single Helmholtz update yields pressure, enthalpy and phase; the
    isentropic exponent is read from the same evaluation.
    """
    backend = _update("D", density_kg_m3, "U", internal_energy_j_kg)
    temperature = float(backend.T())
    pressure = float(backend.p())
    enthalpy = float(backend.hmass())
    raw_quality = float(backend.Q())
    quality = raw_quality if 0.0 <= raw_quality <= 1.0 else None
    if quality is None:
        try:
            sound = float(backend.speed_sound())
        except Exception:
            sound = None
        gamma = density_kg_m3 * sound * sound / pressure if sound else 1.0001
    else:
        backend.update(CP.QT_INPUTS, 1.0, temperature)
        rho_g = float(backend.rhomass())
        a_g = float(backend.speed_sound())
        gamma = rho_g * a_g * a_g / pressure
    if not gamma > 1.0:
        gamma = 1.0001
    return FlowState(temperature, pressure, enthalpy, quality, gamma)


def state_from_t_p(temperature_k: float, pressure_pa: float) -> FluidState:
    """Direct (T, P) property evaluation with no internal Newton iteration."""
    backend = _update("T", temperature_k, "P", pressure_pa)
    return _state_from_backend(
        backend,
        temperature_k,
        pressure_pa,
        float(backend.rhomass()),
        float(backend.umass()),
        None,
    )


def state_from_t_q(temperature_k: float, quality: float) -> FluidState:
    backend = _update("T", temperature_k, "Q", quality)
    return _state_from_backend(
        backend,
        temperature_k,
        float(backend.p()),
        float(backend.rhomass()),
        float(backend.umass()),
        quality,
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
