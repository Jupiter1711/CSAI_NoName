from collections.abc import Callable

from bloxorz.core import rules
from bloxorz.core.level import Level, load_level
from bloxorz.core.state import State

CostFn = Callable[[Level, State, str, State], float]


def unit_cost(level: Level, state: State, action: str, nxt: State) -> float:
    return 1


class BloxorzProblem:
    def __init__(self, level: Level, cost_fn: CostFn = unit_cost):
        self.level = level
        self.cost_fn = cost_fn

    @classmethod
    def from_file(cls, path, cost_fn: CostFn = unit_cost) -> "BloxorzProblem":
        return cls(load_level(path), cost_fn)

    def initial_state(self) -> State:
        return rules.initial_state(self.level)

    def is_goal(self, state: State) -> bool:
        return rules.is_goal(self.level, state)

    def successors(self, state: State) -> list[tuple[str, State, float]]:
        result = []
        for action in rules.actions(state):
            nxt = rules.step(self.level, state, action)
            if nxt is not None:
                result.append(
                    (action, nxt, self.cost_fn(self.level, state, action, nxt))
                )
        return result
