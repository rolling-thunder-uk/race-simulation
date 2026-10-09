# Stochastic canister blowdown batches spread across all cores
from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import numpy as np

from ...speed.load_spreader import available_workers, parallel_map
from .orifice_decay import OrificeProfile, area_from_diameter
from .thermo_core import CanisterConfig, ThermoCore


@dataclass(frozen=True)
class CanisterUncertainties:
    mass_std_dev_kg: float = 0.0
    orifice_diameter_std_dev_m: float = 0.0
    ambient_pressure_std_dev_pa: float = 0.0
    ambient_temperature_std_dev_k: float = 0.0
    discharge_coefficient_std_dev: float = 0.0


@dataclass(frozen=True)
class BlowdownMetrics:
    exhaust_time_s: float
    peak_pressure_pa: float
    final_pressure_pa: float
    minimum_temperature_k: float
    exhausted_mass_kg: float


@dataclass(frozen=True)
class BatchSummary:
    runs: int
    metrics: tuple[BlowdownMetrics, ...]
    exhaust_time_mean_s: float
    exhaust_time_std_dev_s: float
    exhaust_time_p95_s: float
    minimum_temperature_k: float
    peak_pressure_mean_pa: float


def _perturbed(
    base: CanisterConfig, uncertainties: CanisterUncertainties, rng: np.random.Generator
) -> CanisterConfig:
    mass = max(base.initial_mass_kg + rng.normal(0.0, uncertainties.mass_std_dev_kg), 1e-6)
    diameter = max(
        base.orifice.diameter_m
        + rng.normal(0.0, uncertainties.orifice_diameter_std_dev_m),
        1e-5,
    )
    ambient_pressure = max(
        base.ambient_pressure_pa
        + rng.normal(0.0, uncertainties.ambient_pressure_std_dev_pa),
        1.0,
    )
    ambient_temperature = (
        base.ambient_temperature_k
        + rng.normal(0.0, uncertainties.ambient_temperature_std_dev_k)
    )
    discharge = min(
        max(
            base.discharge_coefficient
            + rng.normal(0.0, uncertainties.discharge_coefficient_std_dev),
            0.01,
        ),
        1.0,
    )
    return CanisterConfig(
        volume_m3=base.volume_m3,
        initial_mass_kg=mass,
        orifice=OrificeProfile(
            max_area_m2=area_from_diameter(diameter), tau_s=base.orifice.tau_s
        ),
        initial_temperature_k=base.initial_temperature_k,
        discharge_coefficient=discharge,
        ambient_pressure_pa=ambient_pressure,
        ambient_temperature_k=ambient_temperature,
        heat_transfer_coefficient_w_m2k=base.heat_transfer_coefficient_w_m2k,
        surface_area_m2=base.surface_area_m2,
        minimum_pressure_pa=base.minimum_pressure_pa,
    )


def _run_one(
    seed: int,
    *,
    base: CanisterConfig,
    uncertainties: CanisterUncertainties,
    duration_s: float,
    rtol: float,
    atol: float,
) -> BlowdownMetrics:
    rng = np.random.default_rng(seed)
    config = _perturbed(base, uncertainties, rng)
    samples = ThermoCore(config).simulate(duration_s, rtol=rtol, atol=atol)
    return BlowdownMetrics(
        exhaust_time_s=samples[-1].time_s,
        peak_pressure_pa=samples[0].pressure_pa,
        final_pressure_pa=samples[-1].pressure_pa,
        minimum_temperature_k=min(sample.temperature_k for sample in samples),
        exhausted_mass_kg=samples[0].mass_kg - samples[-1].mass_kg,
    )


def run_blowdown_batch(
    base: CanisterConfig,
    uncertainties: CanisterUncertainties,
    runs: int,
    seed: int = 0,
    workers: int | None = None,
    duration_s: float = 0.5,
    rtol: float = 1e-8,
    atol: float = 1e-11,
) -> BatchSummary:
    worker = partial(
        _run_one,
        base=base,
        uncertainties=uncertainties,
        duration_s=duration_s,
        rtol=rtol,
        atol=atol,
    )
    seeds = range(seed, seed + runs)
    worker_count = workers or available_workers()
    chunksize = max(1, runs // (worker_count * 8))
    metrics = tuple(
        parallel_map(worker, seeds, workers=workers, chunksize=chunksize)
    )

    exhaust = np.array([item.exhaust_time_s for item in metrics])
    minimum_temps = np.array([item.minimum_temperature_k for item in metrics])
    peak_pressures = np.array([item.peak_pressure_pa for item in metrics])
    return BatchSummary(
        runs=len(metrics),
        metrics=metrics,
        exhaust_time_mean_s=float(exhaust.mean()),
        exhaust_time_std_dev_s=float(exhaust.std(ddof=1)) if runs > 1 else 0.0,
        exhaust_time_p95_s=float(np.percentile(exhaust, 95)),
        minimum_temperature_k=float(minimum_temps.min()),
        peak_pressure_mean_pa=float(peak_pressures.mean()),
    )
