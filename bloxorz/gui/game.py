from bloxorz.core.level import Level
from bloxorz.core.rules import DIRECTIONS, initial_state, is_goal, step
from bloxorz.core.state import SPLIT, State

PLAYING = "playing"
WON = "won"
LOST = "lost"


class GameSession:
    def __init__(self, level: Level):
        self.level = level
        self.restart()

    def restart(self) -> None:
        self.state: State = initial_state(self.level)
        self.selected = 0
        self.moves = 0
        self.status = PLAYING

    def move(self, direction: str) -> None:
        if self.status != PLAYING:
            return
        split = self.state.kind == SPLIT
        if split:
            cube = self.state.cells[self.selected]
            action = f"{self.selected + 1}{direction}"
        else:
            action = direction
        nxt = step(self.level, self.state, action)
        self.moves += 1
        if nxt is None:
            self.status = LOST
            return
        if split and nxt.kind == SPLIT:
            dr, dc = DIRECTIONS[direction]
            self.selected = nxt.cells.index((cube[0] + dr, cube[1] + dc))
        else:
            self.selected = 0
        self.state = nxt
        if is_goal(self.level, nxt):
            self.status = WON

    def switch_cube(self) -> None:
        if self.state.kind == SPLIT:
            self.selected = 1 - self.selected
