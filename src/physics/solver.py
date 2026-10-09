# Primary DOP853 8th-Order integrator with tight tolerances
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from scipy.integrate import solve_ivp

BLAST_END_S = 0.15
RTOL = 1e-10
ATOL = 1e-12
DEFAULT_METHOD = "DOP853"
BLAST_METHOD = "Radau"


class IntegrationError(RuntimeError):
    """Raised when a solver stage fails to converge."""


@dataclass
class Solution:
    t: np.ndarray
    y: np.ndarray
    terminated: bool = False

    def state_at(self, time_s: float) -> np.ndarray:
        return np.array([np.interp(time_s, self.t, row) for row in self.y])


def _solve(
    rhs: Callable[[float, np.ndarray], np.ndarray],
    t_span: tuple[float, float],
    y0: np.ndarray,
    method: str,
    rtol: float,
    atol: float,
    max_step: float,
    events,
) -> Solution:
    solution = solve_ivp(
        rhs,
        t_span,
        y0,
        method=method,
        rtol=rtol,
        atol=atol,
        max_step=max_step,
        events=events,
    )
    if not solution.success:
        raise IntegrationError(f"{method} stage failed: {solution.message}")
    terminated = bool(solution.t_events) and any(
        roots.size for roots in solution.t_events
    )
    return Solution(solution.t, solution.y, terminated)


def integrate(
    rhs: Callable[[float, np.ndarray], np.ndarray],
    t_span: tuple[float, float],
    y0: np.ndarray,
    method: str = DEFAULT_METHOD,
    rtol: float = RTOL,
    atol: float = ATOL,
    max_step: float = np.inf,
    events: Sequence[Callable[[float, np.ndarray], float]] | None = None,
) -> Solution:
    """Single-method integration, DOP853 by default."""
    t0, t1 = float(t_span[0]), float(t_span[1])
    y0 = np.asarray(y0, dtype=float)
    if t1 <= t0:
        return Solution(np.array([t0]), y0.reshape(-1, 1))
    return _solve(rhs, (t0, t1), y0, method, rtol, atol, max_step, events)


def integrate_staged(
    rhs: Callable[[float, np.ndarray], np.ndarray],
    t_span: tuple[float, float],
    y0: np.ndarray,
    blast_end_s: float = BLAST_END_S,
    rtol: float = RTOL,
    atol: float = ATOL,
    max_step: float = np.inf,
    events: Sequence[Callable[[float, np.ndarray], float]] | None = None,
) -> Solution:
    """Two-stage pipeline: stiff Radau IIA for the launch blast, then DOP853.

    Kept for the fully coupled vehicle run where the puncture transient can be
    genuinely stiff. The isolated canister blowdown runs DOP853 directly.
    """
    t0, t1 = float(t_span[0]), float(t_span[1])
    y0 = np.asarray(y0, dtype=float)
    if t1 <= t0:
        return Solution(np.array([t0]), y0.reshape(-1, 1))

    blast_end = min(blast_end_s, t1)
    blast = _solve(rhs, (t0, blast_end), y0, BLAST_METHOD, rtol, atol, max_step, events)
    if blast_end >= t1 or blast.terminated:
        return blast

    cruise = _solve(
        rhs, (blast_end, t1), blast.y[:, -1], DEFAULT_METHOD, rtol, atol, max_step, events
    )
    t = np.concatenate([blast.t, cruise.t[1:]])
    y = np.concatenate([blast.y, cruise.y[:, 1:]], axis=1)
    return Solution(t, y, cruise.terminated)
