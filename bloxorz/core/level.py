import json
from dataclasses import dataclass
from pathlib import Path

from bloxorz.core.state import Cell

# Define
VOID = "."
FLOOR = "#"
START = "S"
GOAL = "G"
FRAGILE = "F"
BRIDGE = "B"
SOFT = "O"
HEAVY = "X"
SPLITTER = "P"

TILES = frozenset({VOID, FLOOR, START, GOAL, FRAGILE, BRIDGE, SOFT, HEAVY, SPLITTER})
SWITCH_KINDS = {SOFT: "soft", HEAVY: "heavy", SPLITTER: "split"}
MODES = frozenset({"toggle", "open", "close"})


class LevelError(ValueError):
    pass


@dataclass(frozen=True)
class Switch:
    kind: str
    mode: str = "toggle"
    mask: int = 0
    targets: tuple[Cell, Cell] | None = None


@dataclass(frozen=True, eq=False)
class Level:
    name: str
    grid: tuple[str, ...]
    start: Cell
    goal: Cell
    bridges: tuple[Cell, ...]
    bridge_bits: dict[Cell, int]
    initial_bridges: int
    switches: dict[Cell, Switch]

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0])

    def tile(self, r: int, c: int) -> str:
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.grid[r][c]
        return VOID

    def supports(self, cell: Cell, bridges: int) -> bool:
        t = self.tile(*cell)
        if t == VOID:
            return False
        if t == BRIDGE:
            return bool(bridges >> self.bridge_bits[cell] & 1)
        return True


def _cell(value, where: str) -> Cell:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    ):
        raise LevelError(f"{where}: expect [row, col], got {value!r}")
    return value[0], value[1]


def parse_level(data: dict, name: str = "untitled") -> Level:
    raw = data.get("grid")
    if not raw or not all(isinstance(row, str) for row in raw):
        raise LevelError("grid must be a non-empty list of strings")
    width = max(len(row) for row in raw)
    grid = tuple(row.ljust(width, VOID) for row in raw)

    starts, goals, bridges = [], [], []
    for r, row in enumerate(grid):
        for c, t in enumerate(row):
            if t not in TILES:
                raise LevelError(f"Unknown tile {t!r} at ({r}, {c})")
            if t == START:
                starts.append((r, c))
            elif t == GOAL:
                goals.append((r, c))
            elif t == BRIDGE:
                bridges.append((r, c))
    if len(starts) != 1:
        raise LevelError(f"expected exactly one start, found {len(starts)}")
    if len(goals) != 1:
        raise LevelError(f"expect exactly one goal, found {len(goals)}")

    bridge_bits = {cell: i for i, cell in enumerate(bridges)}

    def bridge_mask(cells, where: str) -> int:
        mask = 0
        for value in cells:
            cell = _cell(value, where)
            if cell not in bridge_bits:
                raise LevelError(f"{where}: {cell} is not a bridge tile")
            mask |= 1 << bridge_bits[cell]
        return mask

    def in_board(cell: Cell) -> bool:
        return 0 <= cell[0] < len(grid) and 0 <= cell[1] < width

    initial = bridge_mask(data.get("open_bridges", []), "open_bridges")

    switches: dict[Cell, Switch] = {}
    for i, entry in enumerate(data.get("switches", [])):
        where = f"switches[{i}]"
        pos = _cell(entry.get("pos"), f"{where}.pos")
        t = grid[pos[0]][pos[1]] if in_board(pos) else VOID
        if t not in SWITCH_KINDS:
            raise LevelError(f"{where}: {pos} is not a switch tile (O, X, P)")
        if pos in switches:
            raise LevelError(f"{where}: duplicate switch at {pos}")
        kind = SWITCH_KINDS[t]
        if kind == "split":
            targets = entry.get("targets")
            if not isinstance(targets, list) or len(targets) != 2:
                raise LevelError(f"{where} split switch needs two targets")
            a = _cell(targets[0], f"{where}.targets")
            b = _cell(targets[1], f"{where}.targets")
            if a == b or not in_board(a) or not in_board(b):
                raise LevelError(f"{where}: targets must be two distinct cells")
            switches[pos] = Switch(kind, targets=(a, b))

        else:
            mode = entry.get("mode", "toggle")
            if mode not in MODES:
                raise LevelError(f"{where}: mode must be one of {sorted(MODES)}")
            mask = bridge_mask(entry.get("bridges", []), f"{where}.bridges")
            switches[pos] = Switch(kind, mode, mask)

    for r, row in enumerate(grid):
        for c, t in enumerate(row):
            if t in SWITCH_KINDS and (r, c) not in switches:
                raise LevelError(f"switch tile at ({r}, {c}) has no entry")

    return Level(
        name=data.get("name", name),
        grid=grid,
        start=starts[0],
        goal=goals[0],
        bridges=tuple(bridges),
        bridge_bits=bridge_bits,
        initial_bridges=initial,
        switches=switches,
    )


def load_level(path: str | Path) -> Level:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        return parse_level(json.load(f), name=path.stem)
