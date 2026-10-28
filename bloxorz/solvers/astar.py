from collections import deque
from heapq import heappop, heappush
from itertools import count
from typing import TypeAlias

from bloxorz.core.level import FRAGILE, VOID, Level
from bloxorz.core.problem import BloxorzProblem
from bloxorz.core.state import HORIZONTAL, SPLIT, STANDING, VERTICAL, State
from bloxorz.solvers.base import SearchResult

Position: TypeAlias = tuple[int, int, str]
_BFS_CACHE: dict[int, dict[Position, int]] = {}


def _is_valid(level: Level, r: int, c: int, kind: str) -> bool:
    try:
        tile = level.tile(r, c)
        if tile == VOID:
            return False
        if kind == HORIZONTAL and level.tile(r, c + 1) == VOID:
            return False
        if kind == VERTICAL and level.tile(r + 1, c) == VOID:
            return False
    except (IndexError, KeyError, TypeError):
        return False

    return not (kind == STANDING and tile == FRAGILE)


def _reverse_neighbors(r: int, c: int, kind: str) -> tuple[Position, ...]:
    if kind == STANDING:
        return (
            (r - 2, c, VERTICAL),
            (r + 1, c, VERTICAL),
            (r, c - 2, HORIZONTAL),
            (r, c + 1, HORIZONTAL),
        )
    if kind == HORIZONTAL:
        return (
            (r, c - 1, STANDING),
            (r, c + 2, STANDING),
            (r - 1, c, HORIZONTAL),
            (r + 1, c, HORIZONTAL),
        )
    return (
        (r - 1, c, STANDING),
        (r + 2, c, STANDING),
        (r, c - 1, VERTICAL),
        (r, c + 1, VERTICAL),
    )


def _build_bfs(problem: BloxorzProblem) -> dict[Position, int]:
    goal_r, goal_c = problem.level.goal
    goal: Position = (goal_r, goal_c, STANDING)
    distances = {goal: 0}
    queue = deque([goal])

    while queue:
        r, c, kind = queue.popleft()
        next_distance = distances[(r, c, kind)] + 1
        for nxt in _reverse_neighbors(r, c, kind):
            nr, nc, next_kind = nxt
            if nxt in distances or not _is_valid(problem.level, nr, nc, next_kind):
                continue
            distances[nxt] = next_distance
            queue.append(nxt)

    return distances


def bfs(problem: BloxorzProblem) -> dict[Position, int]:
    """Return reverse 3D BFS distances, cached once for each problem."""
    problem_id = id(problem)
    distances = _BFS_CACHE.get(problem_id)
    if distances is None:
        distances = _build_bfs(problem)
        _BFS_CACHE[problem_id] = distances
    return distances


def _manhattan(goal: tuple[int, int], r: int, c: int) -> int:
    return abs(goal[0] - r) + abs(goal[1] - c)


def heuristic(problem: BloxorzProblem, state: State) -> float:
    goal = problem.level.goal
    if state.kind == SPLIT:
        d1 = _manhattan(goal, state.r1, state.c1)
        d2 = _manhattan(goal, state.r2, state.c2)
        d_cubes = abs(state.r1 - state.r2) + abs(state.c1 - state.c2)
        return float(max(max(d1, d2) / 2.0, (d_cubes - 1) / 2.0 + min(d1, d2) / 2.0))

    distance = bfs(problem).get((state.r1, state.c1, state.kind))
    if distance is not None:
        return float(distance)
    return float(_manhattan(goal, state.r1, state.c1) / 2.0)


def _path(came_from: dict[State, tuple[State, str]], state: State) -> list[str]:
    path: list[str] = []
    while state in came_from:
        previous, action = came_from[state]
        path.append(action)
        state = previous
    path.reverse()
    return path


def solve(problem: BloxorzProblem) -> SearchResult:
    start = problem.initial_state()
    frontier: list[tuple[float, int, State]] = []
    sequence = count()
    g_score = {start: 0.0}
    came_from: dict[State, tuple[State, str]] = {}
    closed_set: set[State] = set()
    heappush(frontier, (heuristic(problem, start), next(sequence), start))
    expanded = 0

    while frontier:
        _, _, state = heappop(frontier)
        if state in closed_set:
            continue
        closed_set.add(state)

        if problem.is_goal(state):
            return SearchResult(_path(came_from, state), expanded, g_score[state])

        expanded += 1

        for action, nxt, step_cost in problem.successors(state):
            if nxt in closed_set:
                continue
            tentative_g = g_score[state] + float(step_cost)
            if tentative_g >= g_score.get(nxt, float("inf")):
                continue
            g_score[nxt] = tentative_g
            came_from[nxt] = (state, action)
            f_score = tentative_g + heuristic(problem, nxt)
            heappush(frontier, (f_score, next(sequence), nxt))

    return SearchResult(None, expanded, 0.0)
