import importlib
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass

from bloxorz.core.level import Level
from bloxorz.core.problem import BloxorzProblem, unit_cost
from bloxorz.solvers.base import SearchResult

SOLVERS = {
    "BFS": "bfs",
    "DFS": "dfs",
    "UCS": "ucs",
    "A*": "astar",
}

Solve = Callable[[BloxorzProblem], SearchResult]


@dataclass
class Measured:
    result: SearchResult
    seconds: float
    peak_bytes: int


def find(name: str) -> tuple[Solve, Callable] | None:
    """The solver behind a button, or None if its module is not written yet."""
    try:
        module = importlib.import_module(f"bloxorz.solvers.{SOLVERS[name]}")
    except ModuleNotFoundError:
        return None
    solve = getattr(module, "solve", None)
    if solve is None:
        return None
    return solve, getattr(module, "cost_fn", unit_cost)


def run(name: str, level: Level) -> Measured | None:
    """Solve the level from its start, recording search time and peak memory."""
    found = find(name)
    if found is None:
        return None
    solve, cost_fn = found
    problem = BloxorzProblem(level, cost_fn)
    tracemalloc.start()
    start = time.perf_counter()
    try:
        result = solve(problem)
        seconds = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return Measured(result, seconds, peak)
