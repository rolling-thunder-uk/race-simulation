# Multi-core process load spreading for stochastic batches
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")

_WORKER: Callable[[T], R] | None = None


def _init_worker(worker: Callable[[T], R]) -> None:
    global _WORKER
    _WORKER = worker


def _run_task(task: T) -> R:
    if _WORKER is None:
        raise RuntimeError("worker process was not initialised")
    return _WORKER(task)


def available_workers() -> int:
    return os.cpu_count() or 1


def parallel_map(
    worker: Callable[[T], R],
    tasks: Iterable[T],
    workers: int | None = None,
    chunksize: int = 1,
) -> list[R]:
    """Fan a batch of independent tasks across all available cores.

    The worker must be a module-level (picklable) callable so it can be sent
    to each spawned process; per-run variation should live in the task payload.
    """
    task_list = list(tasks)
    if not task_list:
        return []

    worker_count = min(workers or available_workers(), len(task_list))
    worker_count = max(1, worker_count)

    if worker_count == 1:
        return [worker(task) for task in task_list]

    with ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=_init_worker,
        initargs=(worker,),
    ) as executor:
        return list(executor.map(_run_task, task_list, chunksize=chunksize))
