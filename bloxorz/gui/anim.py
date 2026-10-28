import math
import random
from dataclasses import dataclass, field

from bloxorz.core.rules import DIRECTIONS
from bloxorz.core.state import SPLIT, STANDING, Cell, State

# x0, y0, z0, x1, y1, z1 in world units: x = column, z = row, y = up
Box = tuple[float, float, float, float, float, float]
Vec = tuple[float, float, float]

ROLL_TIME = 0.18
FALL_TIME = 1.2
GRAVITY = 14.0
TUMBLE_SPEED = 260.0
DRIFT_SPEED = 1.5
FALL_MIN_SCALE = 0.3
SPARK_LIFE = 0.6
SPARK_RATE = 90.0
SINK_TIME = 1.1
SINK_DEPTH = 2.3
SINK_SPIN = 540.0
SINK_MIN_SCALE = 0.6
WAVE_SPREAD = 0.7
WAVE_HEIGHT = 10.0
TILE_LAND_TIME = 0.5
WAVE_DEPTH = 25.0
TILE_FALL_TIME = 1.0

ROLL_AXES: dict[str, tuple[Vec, float]] = {
    "U": ((1.0, 0.0, 0.0), -90.0),
    "D": ((1.0, 0.0, 0.0), 90.0),
    "L": ((0.0, 0.0, 1.0), 90.0),
    "R": ((0.0, 0.0, 1.0), -90.0),
}


def cell_box(cell: Cell, height: float = 1.0) -> Box:
    r, c = cell
    return c, 0.0, r, c + 1, height, r + 1


def state_boxes(state: State) -> list[Box]:
    if state.kind == SPLIT:
        return [cell_box(cell) for cell in state.cells]
    (r1, c1), (r2, c2) = state.cells[0], state.cells[-1]
    height = 2.0 if state.kind == STANDING else 1.0
    return [(c1, 0.0, r1, c2 + 1, height, r2 + 1)]


def box_center(box: Box) -> Vec:
    x0, y0, z0, x1, y1, z1 = box
    return (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2


def rotate_point(point: Vec, pivot: Vec, axis: Vec, degrees: float) -> Vec:
    rad = math.radians(degrees)
    cos, sin = math.cos(rad), math.sin(rad)
    x, y, z = (p - q for p, q in zip(point, pivot))
    if axis[0]:
        y, z = y * cos - z * sin, y * sin + z * cos
    else:
        x, y = x * cos - y * sin, x * sin + y * cos
    px, py, pz = pivot
    return x + px, y + py, z + pz


@dataclass
class Spark:
    origin: Vec
    velocity: Vec
    born: float


@dataclass
class Motion:
    moving: Box
    still: tuple[Box, ...]
    direction: str
    falls: bool
    bridges: int
    sinks: bool = False
    t: float = 0.0
    sparks: list[Spark] = field(default_factory=list)
    rng: random.Random = field(default_factory=lambda: random.Random(0), repr=False)

    @classmethod
    def start(
        cls,
        state: State,
        selected: int,
        direction: str,
        falls: bool,
        sinks: bool = False,
    ) -> "Motion":
        if state.kind == SPLIT:
            cells = state.cells
            moving = cell_box(cells[selected])
            still = (cell_box(cells[1 - selected]),)
            return cls(moving, still, direction, falls, state.bridges, sinks)
        moving = state_boxes(state)[0]
        return cls(moving, (), direction, falls, state.bridges, sinks)

    @property
    def duration(self) -> float:
        if self.falls:
            return ROLL_TIME + FALL_TIME + SPARK_LIFE
        if self.sinks:
            return ROLL_TIME + SINK_TIME + SPARK_LIFE
        return ROLL_TIME

    @property
    def done(self) -> bool:
        return self.t >= self.duration

    @property
    def rolling(self) -> bool:
        return self.t < ROLL_TIME

    @property
    def finished_game(self) -> bool:
        return self.falls or self.sinks

    @property
    def after_roll(self) -> float:
        return max(self.t - ROLL_TIME, 0.0)

    def advance(self, dt: float) -> None:
        before = self.t
        self.t = min(self.t + dt, self.duration)
        if not self.finished_game:
            return
        burn = FALL_TIME if self.falls else SINK_TIME
        start, end = max(before, ROLL_TIME), min(self.t, ROLL_TIME + burn)
        if end > start:
            self._emit(int(SPARK_RATE * (end - start) + self.rng.random()), end)
        self.sparks = [s for s in self.sparks if self.t - s.born < SPARK_LIFE]
        if self.done:
            # The duration leaves every spark time to burn out; dropping them
            # here also clears ones left with a rounding-error sliver of life.
            self.sparks = []

    def _emit(self, count: int, born: float) -> None:
        if self.sinks:
            self._emit_wisps(count, born)
            return
        origin = self.center
        for _ in range(count):
            theta = self.rng.uniform(0, 2 * math.pi)
            lift = self.rng.uniform(-0.6, 1.0)
            speed = self.rng.uniform(1.0, 3.0)
            velocity = (
                math.cos(theta) * speed,
                lift * speed,
                math.sin(theta) * speed,
            )
            self.sparks.append(Spark(origin, velocity, born))

    def _emit_wisps(self, count: int, born: float) -> None:
        """Light rising out of the portal where the block dissolves."""
        x, _, z = self.center
        for _ in range(count):
            origin = (
                x + self.rng.uniform(-0.4, 0.4),
                0.0,
                z + self.rng.uniform(-0.4, 0.4),
            )
            theta = self.rng.uniform(0, 2 * math.pi)
            spread = self.rng.uniform(0.1, 0.7)
            velocity = (
                math.cos(theta) * spread,
                self.rng.uniform(0.8, 2.2),
                math.sin(theta) * spread,
            )
            self.sparks.append(Spark(origin, velocity, born))

    def live_sparks(self) -> list[tuple[Vec, float]]:
        result = []
        for spark in self.sparks:
            age = self.t - spark.born
            pos = tuple(o + v * age for o, v in zip(spark.origin, spark.velocity))
            result.append((pos, 1.0 - age / SPARK_LIFE))
        return result

    @property
    def axis(self) -> Vec:
        return ROLL_AXES[self.direction][0]

    @property
    def pivot(self) -> Vec:
        x0, _, z0, x1, _, z1 = self.moving
        if self.direction == "R":
            return x1, 0.0, z0
        if self.direction == "D":
            return x0, 0.0, z1
        return x0, 0.0, z0

    @property
    def angle(self) -> float:
        p = min(self.t / ROLL_TIME, 1.0)
        roll = ROLL_AXES[self.direction][1]
        return roll * p * p * (3 - 2 * p)

    @property
    def tumble(self) -> float:
        if not self.falls:
            return 0.0
        roll = ROLL_AXES[self.direction][1]
        return math.copysign(TUMBLE_SPEED, roll) * self.after_roll

    @property
    def drop(self) -> float:
        after = self.after_roll
        if self.sinks:
            return SINK_DEPTH * self.sink_progress
        return 0.5 * GRAVITY * after * after

    @property
    def offset(self) -> Vec:
        drift = DRIFT_SPEED * self.after_roll if self.falls else 0.0
        dr, dc = DIRECTIONS[self.direction]
        return dc * drift, -self.drop, dr * drift

    @property
    def fade(self) -> float:
        if self.sinks:
            return max(1.0 - self.after_roll / SINK_TIME, 0.0)
        if not self.falls:
            return 1.0
        return max(1.0 - self.after_roll / FALL_TIME, 0.0)

    @property
    def sink_progress(self) -> float:
        if not self.sinks:
            return 0.0
        p = min(self.after_roll / SINK_TIME, 1.0)
        return p * p

    @property
    def spin(self) -> float:
        return SINK_SPIN * self.sink_progress

    @property
    def scale(self) -> float:
        if self.sinks:
            return 1.0 - (1.0 - SINK_MIN_SCALE) * self.sink_progress
        return FALL_MIN_SCALE + (1.0 - FALL_MIN_SCALE) * self.fade

    @property
    def center(self) -> Vec:
        center = rotate_point(
            box_center(self.moving), self.pivot, self.axis, self.angle
        )
        return tuple(c + o for c, o in zip(center, self.offset))


@dataclass
class Wave:
    """Tiles dropping in to build a level, or falling away. The block rides
    on its start tile, so it arrives together with the board."""

    delays: dict[Cell, float]
    building: bool
    t: float = 0.0

    @classmethod
    def build(
        cls, cells: list[Cell], rng: random.Random | None = None, wait: float = 0.0
    ) -> "Wave":
        wave = cls._start(cells, True, rng)
        # Start the clock below zero so nothing moves for `wait` seconds.
        wave.t = -wait
        return wave

    @classmethod
    def collapse(cls, cells: list[Cell], rng: random.Random | None = None) -> "Wave":
        return cls._start(cells, False, rng)

    @classmethod
    def _start(cls, cells: list[Cell], building: bool, rng: random.Random | None):
        rng = rng or random.Random()
        return cls({cell: rng.uniform(0, WAVE_SPREAD) for cell in cells}, building)

    @property
    def tile_time(self) -> float:
        return TILE_LAND_TIME if self.building else TILE_FALL_TIME

    @property
    def duration(self) -> float:
        """When the last tile stops moving."""
        return max(self.delays.values(), default=0.0) + self.tile_time

    @property
    def done(self) -> bool:
        return self.t >= self.duration

    def advance(self, dt: float) -> None:
        self.t = min(self.t + dt, self.duration)

    def lifts(self) -> dict[Cell, float]:
        """Height of every visible tile above (+) or below (-) its place."""
        result = {}
        for cell, delay in self.delays.items():
            p = (self.t - delay) / self.tile_time
            if self.building:
                if p <= 0:
                    continue
                # Fast at first, then it slows down to settle into place.
                result[cell] = WAVE_HEIGHT * (1 - min(p, 1.0)) ** 2
            elif p < 1:
                # Gravity: slow at first, then faster and faster.
                result[cell] = -WAVE_DEPTH * max(p, 0.0) ** 2
        return result
