import heapq
import itertools

from bloxorz.core.level import FRAGILE, HEAVY, SOFT, SPLITTER, Level
from bloxorz.core.problem import BloxorzProblem
from bloxorz.core.rules import (
    DIRECTIONS,
    TRANSITIONS,
    actions,
    initial_state,
    is_goal,
    step,
)
from bloxorz.core.state import SPLIT, STANDING, Cell, State

from .base import SearchResult


def cal_initial_cost(level: Level, cell: Cell, kind: str) -> int:
    tile = level.tile(*cell)
    cost = 1

    if tile == FRAGILE:
        cost += 1

    switch = level.switches.get(cell)
    if switch is None:
        return cost

    if tile == SOFT:
        cost += switch.mask.bit_count()
    elif tile == HEAVY and kind == STANDING:
        cost += switch.mask.bit_count()
    elif tile == SPLITTER and kind == STANDING:
        cost += len(switch.targets)

    return cost

class UCSstate:
    def __init__(
        self,
        state: State,
        path: list[str],
        total_cost: int,
    ) -> None:
        self.state = state
        self.path = path
        self.total_cost = total_cost


def solve(problem: BloxorzProblem) -> SearchResult:
    level = problem.level
    start_node = UCSstate(
        state=initial_state(level),
        path=[],
        total_cost=0,
    )

    labels = {start_node.state: start_node.total_cost}

    expanded = 0
    mincost_heap = []
    counter = itertools.count()
    heapq.heappush(mincost_heap, (0, next(counter), start_node))

    while mincost_heap:
        curcost, _, curnode = heapq.heappop(mincost_heap)

        if labels.get(curnode.state) != curcost:
            continue

        if is_goal(level, curnode.state):
            return SearchResult(
                path=curnode.path,
                expanded=expanded,
                cost=float(curcost),
            )

        expanded += 1

        for action in actions(curnode.state):
            next_state = step(level, curnode.state, action)
            if next_state is None:
                continue

            new_cost = curcost

            moved_cell = None
            if curnode.state.kind == SPLIT:
                cube_index = int(action[0]) - 1
                dr, dc = DIRECTIONS[action[1]]
                r, c = curnode.state.cells[cube_index]
                moved_cell = (r + dr, c + dc)

            # Tìm xem action của khối liền có kích hoạt P không.
            split_switch_cell = None
            if curnode.state.kind != SPLIT:
                next_kind, dr, dc = TRANSITIONS[(curnode.state.kind, action)]
                destination = (
                    curnode.state.r1 + dr,
                    curnode.state.c1 + dc,
                )

                if next_kind == STANDING and level.tile(*destination) == SPLITTER:
                    split_switch_cell = destination

            for cell in next_state.cells:
                cell_cost = cal_initial_cost(
                    level,
                    cell,
                    next_state.kind,
                )

                if level.tile(*cell) == SOFT and (
                    curnode.state.kind == SPLIT and cell != moved_cell
                ):
                    switch = level.switches.get(cell)
                    if switch is not None:
                        cell_cost -= switch.mask.bit_count()

                new_cost += cell_cost

            if split_switch_cell is not None:
                switch = level.switches[split_switch_cell]

                new_cost += 1 + len(switch.targets)

            new_path = curnode.path + [action]

            next_node = UCSstate(
                state=next_state,
                path=new_path,
                total_cost=new_cost,
            )

            exist_node_cost = labels.get(next_state)

            if exist_node_cost is not None and exist_node_cost <= new_cost:
                continue
            
            labels[next_state] = new_cost
            
            heapq.heappush(
                mincost_heap,
                (new_cost, next(counter), next_node),
            )
    return SearchResult(path=None, expanded=expanded, cost=0.0)
