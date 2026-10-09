# Primary DOP853 8th-Order integrator with tight tolerances
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from scipy.integrate import solve_ivp

BLAST_END_S = 0.15
RTOL = 1e-10
ATOL = 1e-12


class IntegrationError(RuntimeError):
    """Raised when a solver stage fails to converge."""


@dataclass
class StagedSolution:
    t: np.ndarray
    y: np.ndarray

    def state_at(self, time_s: float) -> np.ndarray:
        return np.array([np.interp(time_s, self.t, row) for row in self.y])


def integrate_staged(
    rhs: Callable[[float, np.ndarray], np.ndarray],
    t_span: tuple[float, float],
    y0: np.ndarray,
    blast_end_s: float = BLAST_END_S,
    rtol: float = RTOL,
    atol: float = ATOL,
    max_step: float = np.inf,
    events: Sequence[Callable[[float, np.ndarray], float]] | None = None,
) -> StagedSolution:
    """Two-stage pipeline: stiff Radau IIA for the launch blast, then DOP853.

    The launcher puncture produces a discontinuous mass-flow spike that defies
    explicit methods; the down-track cruise is smooth and switches to the
    higher-order explicit Dormand-Prince scheme.
    """
    t0, t1 = float(t_span[0]), float(t_span[1])
    y0 = np.asarray(y0, dtype=float)
    if t1 <= t0:
        return StagedSolution(np.array([t0]), y0.reshape(-1, 1))

    blast_end = min(blast_end_s, t1)
    blast = solve_ivp(
        rhs,
        (t0, blast_end),
        y0,
        method="Radau",
        rtol=rtol,
        atol=atol,
        max_step=max_step,
        events=events,
    )
    if not blast.success:
        raise IntegrationError(f"Radau stage failed: {blast.message}")

    if blast_end >= t1 or _event_triggered(blast):
        return StagedSolution(blast.t, blast.y)

    cruise = solve_ivp(
        rhs,
        (blast_end, t1),
        blast.y[:, -1],
        method="DOP853",
        rtol=rtol,
        atol=atol,
        max_step=max_step,
        events=events,
    )
    if not cruise.success:
        raise IntegrationError(f"DOP853 stage failed: {cruise.message}")

    t = np.concatenate([blast.t, cruise.t[1:]])
    y = np.concatenate([blast.y, cruise.y[:, 1:]], axis=1)
    return StagedSolution(t, y)


def _event_triggered(solution) -> bool:
    return bool(solution.t_events) and any(roots.size for roots in solution.t_events)
