from typing import NamedTuple

STANDING = "S"
HORIZONTAL = "H"
VERTICAL = "V"
SPLIT = "X"
Cell = tuple[int, int]


class State(NamedTuple):
    kind: str
    r1: int
    c1: int
    r2: int
    c2: int
    bridges: int

    @property
    def cells(self) -> tuple[Cell, ...]:
        if self.kind == STANDING:
            return ((self.r1, self.c1),)
        return ((self.r1, self.c1), (self.r2, self.c2))


def block_state(kind: str, r: int, c: int, bridges: int) -> State:
    if kind == STANDING:
        return State(STANDING, r, c, r, c, bridges)
    if kind == HORIZONTAL:
        return State(HORIZONTAL, r, c, r, c + 1, bridges)
    if kind == VERTICAL:
        return State(VERTICAL, r, c, r + 1, c, bridges)
    raise ValueError(f"Unknown block kind: {kind!r}")


def cubes_state(a: Cell, b: Cell, bridges: int) -> State:
    a, b = sorted((a, b))
    if a[0] == b[0] and b[1] - a[1] == 1:
        return block_state(HORIZONTAL, a[0], a[1], bridges)
    if a[1] == b[1] and b[0] - a[0] == 1:
        return block_state(VERTICAL, a[0], a[1], bridges)
    return State(SPLIT, a[0], a[1], b[0], b[1], bridges)
