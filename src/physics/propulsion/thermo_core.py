# Coupled canister blowdown: real-fluid mass and energy conservation
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..solver import ATOL, RTOL, StagedSolution, integrate_staged
from . import gas_state
from .mass_depletion import mass_flow_rate
from .orifice_decay import OrificeProfile


@dataclass(frozen=True)
class CanisterConfig:
    volume_m3: float
    initial_mass_kg: float
    orifice: OrificeProfile
    initial_temperature_k: float = 293.15
    discharge_coefficient: float = 0.85
    ambient_pressure_pa: float = 101_325.0
    ambient_temperature_k: float = 293.15
    heat_transfer_coefficient_w_m2k: float = 0.0
    surface_area_m2: float = 0.0
    minimum_pressure_pa: float | None = None


@dataclass(frozen=True)
class CanisterSample:
    time_s: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    internal_energy_j_kg: float
    mass_kg: float
    quality: float | None
    mass_flow_kg_s: float
    choked: bool
    orifice_area_m2: float
    isentropic_exponent: float
    phase: str


class ThermoCore:
    """Transient CO2 canister expansion model.

    The ODE state vector tracks density (rho) and specific internal energy (u).
    At every micro-step the NIST Helmholtz backend is queried for the full
    state (T, P, h, phase, quality), so the non-linear flash-boiling path and
    the associated expansion cooling emerge directly from the equation of
    state rather than from ideal-gas shortcuts.
    """

    def __init__(self, config: CanisterConfig) -> None:
        self.config = config
        if config.minimum_pressure_pa is not None:
            self.minimum_pressure_pa = config.minimum_pressure_pa
        else:
            _, triple_pressure = gas_state.triple_point()
            self.minimum_pressure_pa = max(triple_pressure, config.ambient_pressure_pa)

    def initial_density(self) -> float:
        return self.config.initial_mass_kg / self.config.volume_m3

    def initial_internal_energy(self) -> float:
        density = self.initial_density()
        return gas_state.mixture_internal_energy(
            self.config.initial_temperature_k, density
        )

    def initial_state(self) -> np.ndarray:
        return np.array([self.initial_density(), self.initial_internal_energy()])

    def derivatives(self, time_s: float, state_vector: np.ndarray) -> np.ndarray:
        density, internal_energy = float(state_vector[0]), float(state_vector[1])
        volume = self.config.volume_m3
        try:
            flow = gas_state.flow_from_rho_u(density, internal_energy)
        except gas_state.FluidPropertyError:
            return np.zeros(2)

        area = self.config.orifice.area(time_s)
        mass_flow, _ = mass_flow_rate(
            density,
            flow.pressure_pa,
            flow.isentropic_exponent,
            area,
            self.config.ambient_pressure_pa,
            self.config.discharge_coefficient,
        )

        heat_flow = (
            self.config.heat_transfer_coefficient_w_m2k
            * self.config.surface_area_m2
            * (self.config.ambient_temperature_k - flow.temperature_k)
        )

        density_rate = -mass_flow / volume
        rho_u_rate = (-mass_flow * flow.enthalpy_j_kg + heat_flow) / volume
        energy_rate = (rho_u_rate - internal_energy * density_rate) / density
        return np.array([density_rate, energy_rate])

    def sample_at(self, time_s: float, state_vector: np.ndarray) -> CanisterSample:
        density, internal_energy = float(state_vector[0]), float(state_vector[1])
        state = gas_state.state_from_rho_u(density, internal_energy)
        flow = gas_state.flow_from_rho_u(density, internal_energy)
        gamma = flow.isentropic_exponent
        area = self.config.orifice.area(time_s)
        mass_flow, choked = mass_flow_rate(
            state.density_kg_m3,
            state.pressure_pa,
            gamma,
            area,
            self.config.ambient_pressure_pa,
            self.config.discharge_coefficient,
        )
        return CanisterSample(
            time_s=time_s,
            temperature_k=state.temperature_k,
            pressure_pa=state.pressure_pa,
            density_kg_m3=density,
            internal_energy_j_kg=internal_energy,
            mass_kg=density * self.config.volume_m3,
            quality=state.quality,
            mass_flow_kg_s=mass_flow,
            choked=choked,
            orifice_area_m2=area,
            isentropic_exponent=gamma,
            phase=state.phase,
        )

    def _floor_event(self, time_s: float, state_vector: np.ndarray) -> float:
        try:
            flow = gas_state.flow_from_rho_u(
                float(state_vector[0]), float(state_vector[1])
            )
        except gas_state.FluidPropertyError:
            return -1.0
        return flow.pressure_pa - self.minimum_pressure_pa

    _floor_event.terminal = True
    _floor_event.direction = -1

    def simulate(
        self,
        duration_s: float,
        rtol: float = RTOL,
        atol: float = ATOL,
        max_step: float = np.inf,
    ) -> list[CanisterSample]:
        solution: StagedSolution = integrate_staged(
            self.derivatives,
            (0.0, duration_s),
            self.initial_state(),
            rtol=rtol,
            atol=atol,
            max_step=max_step,
            events=[self._floor_event],
        )
        return [
            self.sample_at(float(solution.t[index]), solution.y[:, index])
            for index in range(solution.t.size)
        ]

    def pressure_curve(
        self, duration_s: float, rtol: float = RTOL, atol: float = ATOL
    ) -> tuple[np.ndarray, np.ndarray]:
        samples = self.simulate(duration_s, rtol=rtol, atol=atol)
        times = np.array([sample.time_s for sample in samples])
        pressures = np.array([sample.pressure_pa for sample in samples])
        return times, pressures
