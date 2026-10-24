from collections.abc import Iterable

from bloxorz.core.level import FRAGILE, Level, Switch
from bloxorz.core.state import (
    HORIZONTAL,
    SPLIT,
    STANDING,
    VERTICAL,
    Cell,
    State,
    block_state,
    cubes_state,
)

DIRECTIONS = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
BLOCK_ACTIONS = ("U", "D", "L", "R")
CUBE_ACTIONS = tuple(f"{i}{d}" for i in "12" for d in BLOCK_ACTIONS)

TRANSITIONS = {
    (STANDING, "U"): (VERTICAL, -2, 0),
    (STANDING, "D"): (VERTICAL, 1, 0),
    (STANDING, "L"): (HORIZONTAL, 0, -2),
    (STANDING, "R"): (HORIZONTAL, 0, 1),
    (HORIZONTAL, "U"): (HORIZONTAL, -1, 0),
    (HORIZONTAL, "D"): (HORIZONTAL, 1, 0),
    (HORIZONTAL, "L"): (STANDING, 0, -1),
    (HORIZONTAL, "R"): (STANDING, 0, 2),
    (VERTICAL, "U"): (STANDING, -1, 0),
    (VERTICAL, "D"): (STANDING, 2, 0),
    (VERTICAL, "L"): (VERTICAL, 0, -1),
    (VERTICAL, "R"): (VERTICAL, 0, 1),
}


def initial_state(level: Level) -> State:
    return block_state(STANDING, *level.start, level.initial_bridges)


def is_goal(level: Level, state: State) -> bool:
    return state.kind == STANDING and (state.r1, state.c1) == level.goal


def actions(state: State) -> tuple[str, ...]:
    return CUBE_ACTIONS if state.kind == SPLIT else BLOCK_ACTIONS


def step(level: Level, state: State, action: str) -> State | None:
    if action not in actions(state):
        raise ValueError(f"action {action!r} not valid for kind {state.kind!r}")
    if state.kind == SPLIT:
        return _step_cube(level, state, action)
    return _step_block(level, state, action)


def replay(level: Level, moves: Iterable[str]) -> list[State]:
    state = initial_state(level)
    states = [state]
    for move in moves:
        nxt = step(level, state, move)
        if nxt is None:
            raise ValueError(f"illegal move {move!r} at step {len(states)}")
        state = nxt
        states.append(state)
    return states


def _supported(level: Level, cells: Iterable[Cell], bridges: int) -> bool:
    return all(level.supports(cell, bridges) for cell in cells)


def _press(switch: Switch, bridges: int) -> int:
    if switch.mode == "toggle":
        return bridges ^ switch.mask
    if switch.mode == "open":
        return bridges | switch.mask
    return bridges & ~switch.mask


def _step_block(level: Level, state: State, action: str) -> State | None:
    kind, dr, dc = TRANSITIONS[(state.kind, action)]
    bridges = state.bridges
    nxt = block_state(kind, state.r1 + dr, state.c1 + dc, bridges)
    cells = nxt.cells
    if not _supported(level, cells, bridges):
        return None
    if kind == STANDING and level.tile(*cells[0]) == FRAGILE:
        return None
    for cell in cells:
        switch = level.switches.get(cell)
        if switch is None:
            continue
        if switch.kind == "soft" or (switch.kind == "heavy" and kind == STANDING):
            bridges = _press(switch, bridges)
        elif switch.kind == "split" and kind == STANDING:
            a, b = switch.targets
            if not _supported(level, (a, b), bridges):
                return None
            return cubes_state(a, b, bridges)
    if not _supported(level, cells, bridges):
        return None
    return nxt._replace(bridges=bridges)


def _step_cube(level: Level, state: State, action: str) -> State | None:
    idx = int(action[0]) - 1
    dr, dc = DIRECTIONS[action[1]]
    cells = state.cells
    (r, c), other = cells[idx], cells[1 - idx]
    moved = (r + dr, c + dc)
    if moved == other:
        return None
    bridges = state.bridges
    if not level.supports(moved, bridges):
        return None
    switch = level.switches.get(moved)
    if switch is not None and switch.kind == "soft":
        bridges = _press(switch, bridges)
    if not _supported(level, (moved, other), bridges):
        return None
    return cubes_state(moved, other, bridges)
