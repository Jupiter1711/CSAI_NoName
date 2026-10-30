from __future__ import annotations

import gc
import signal
import threading
import time
import tracemalloc
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from bloxorz.core.level import (
    BRIDGE,
    FRAGILE,
    HEAVY,
    SOFT,
    SPLITTER,
    Level,
    load_level,
)
from bloxorz.core.problem import BloxorzProblem, CostFn, unit_cost
from bloxorz.core.rules import replay
from bloxorz.solvers import astar
from bloxorz.solvers.base import SearchResult

SolverFn = Callable[[BloxorzProblem], SearchResult]

CATEGORY_ORDER: tuple[str, ...] = ("simple", "fragile", "switches", "combined")


class BenchmarkTimeoutError(TimeoutError):
    """Raised when a solver exceeds the configured time limit."""


@dataclass(frozen=True)
class BenchmarkRecord:
    """Stores the benchmark metrics of running one solver on one level."""

    level_name: str
    category: str
    solver_name: str
    status: str
    found: bool
    valid: bool
    solution_length: int
    cost: float
    expanded: int
    search_time_ms: float
    peak_memory_kb: float
    path: list[str] | None = None

    @property
    def search_time_s(self) -> float:
        return self.search_time_ms / 1000.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_level(level: Level) -> str:
    """Classify a level into one of: simple, fragile, switches, combined."""
    tiles = {ch for row in level.grid for ch in row}
    has_fragile = FRAGILE in tiles
    has_switches_or_bridges = bool(tiles & {BRIDGE, SOFT, HEAVY})
    has_splitter = SPLITTER in tiles

    if has_splitter or (has_fragile and has_switches_or_bridges):
        return "combined"
    if has_switches_or_bridges:
        return "switches"
    if has_fragile:
        return "fragile"
    return "simple"


def verify_solution(problem: BloxorzProblem, path: Iterable[str] | None) -> bool:
    """Verify that a path makes legal moves from start and reaches the goal."""
    if path is None:
        return False
    try:
        states = replay(problem.level, path)
    except ValueError:
        return False
    return bool(states) and problem.is_goal(states[-1])


def get_default_solvers() -> dict[str, SolverFn]:
    """Return available solvers following the `solve(problem)` contract."""
    solvers: dict[str, SolverFn] = {}

    try:
        from bloxorz.solvers.bfs import solve as bfs_solve

        solvers["BFS"] = bfs_solve
    except ImportError:
        pass

    try:
        from bloxorz.solvers.dfs import solve as dfs_solve

        solvers["DFS"] = dfs_solve
    except ImportError:
        pass

    for ucs_module in ("bloxorz.solvers.ucs", "bloxorz.solvers.UCS_solve"):
        try:
            module = __import__(ucs_module, fromlist=["solve"])
            ucs_solve = getattr(module, "solve", None)
            if callable(ucs_solve):
                solvers["UCS"] = ucs_solve
                break
        except ImportError:
            continue

    solvers["A*"] = astar.solve
    return solvers


def _clear_solver_caches() -> None:
    """Clear solver internal caches (e.g., A* reverse BFS cache) before measurement."""
    astar._BFS_CACHE.clear()


def _run_with_timeout(
    solver_fn: SolverFn,
    problem: BloxorzProblem,
    timeout_s: float | None,
) -> SearchResult:
    """Execute `solver_fn(problem)` with an optional timeout on POSIX main thread."""
    use_itimer = (
        timeout_s is not None
        and timeout_s > 0
        and hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )
    if not use_itimer:
        return solver_fn(problem)

    def _handle_timeout(signum: int, frame: object) -> None:
        raise BenchmarkTimeoutError(f"Solver timed out after {timeout_s}s")

    previous_handler = signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
    try:
        return solver_fn(problem)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)


def measure_solver(
    level: Level,
    solver_name: str,
    solver_fn: SolverFn,
    *,
    cost_fn: CostFn = unit_cost,
    category: str | None = None,
    timeout_s: float | None = 30.0,
    repeats: int = 1,
) -> BenchmarkRecord:
    """Run and benchmark a single solver on a single level."""
    if repeats < 1:
        raise ValueError("repeats must be at least 1")

    resolved_category = category if category is not None else classify_level(level)
    total_time_ms = 0.0
    total_peak_kb = 0.0
    last_result: SearchResult | None = None

    for _ in range(repeats):
        problem = BloxorzProblem(level, cost_fn=cost_fn)
        _clear_solver_caches()
        gc.collect()

        tracemalloc.start()
        start_ns = time.perf_counter_ns()
        try:
            result = _run_with_timeout(solver_fn, problem, timeout_s)
        except BenchmarkTimeoutError:
            elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            return BenchmarkRecord(
                level_name=level.name,
                category=resolved_category,
                solver_name=solver_name,
                status="TIMEOUT",
                found=False,
                valid=False,
                solution_length=0,
                cost=0.0,
                expanded=0,
                search_time_ms=round(elapsed_ms, 4),
                peak_memory_kb=round(peak_bytes / 1024.0, 4),
                path=None,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            return BenchmarkRecord(
                level_name=level.name,
                category=resolved_category,
                solver_name=solver_name,
                status=f"ERROR: {type(exc).__name__}",
                found=False,
                valid=False,
                solution_length=0,
                cost=0.0,
                expanded=0,
                search_time_ms=round(elapsed_ms, 4),
                peak_memory_kb=round(peak_bytes / 1024.0, 4),
                path=None,
            )

        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        total_time_ms += elapsed_ms
        total_peak_kb += peak_bytes / 1024.0
        last_result = result

    assert last_result is not None
    verify_problem = BloxorzProblem(level, cost_fn=cost_fn)
    found = last_result.found
    valid = verify_solution(verify_problem, last_result.path) if found else False

    if not found:
        status = "UNSOLVED"
    elif valid:
        status = "OK"
    else:
        status = "INVALID"

    return BenchmarkRecord(
        level_name=level.name,
        category=resolved_category,
        solver_name=solver_name,
        status=status,
        found=found,
        valid=valid,
        solution_length=last_result.length,
        cost=float(last_result.cost),
        expanded=int(last_result.expanded),
        search_time_ms=round(total_time_ms / repeats, 4),
        peak_memory_kb=round(total_peak_kb / repeats, 4),
        path=list(last_result.path) if last_result.path is not None else None,
    )


def load_levels_from_paths(paths: Iterable[str | Path]) -> list[Level]:
    """Load levels from file paths or directories containing `.json` files."""
    levels: list[Level] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for json_file in sorted(path.glob("*.json")):
                levels.append(load_level(json_file))
        else:
            levels.append(load_level(path))
    return levels


def run_benchmarks(
    levels: Iterable[Level],
    solvers: Mapping[str, SolverFn] | None = None,
    *,
    cost_fn: CostFn = unit_cost,
    timeout_s: float | None = 30.0,
    repeats: int = 1,
) -> list[BenchmarkRecord]:
    """Run all specified solvers across all given levels and return records."""
    active_solvers = dict(solvers) if solvers is not None else get_default_solvers()
    records: list[BenchmarkRecord] = []

    for level in levels:
        category = classify_level(level)
        for solver_name, solver_fn in active_solvers.items():
            record = measure_solver(
                level,
                solver_name,
                solver_fn,
                cost_fn=cost_fn,
                category=category,
                timeout_s=timeout_s,
                repeats=repeats,
            )
            records.append(record)

    return records
