import math
from dataclasses import dataclass

from bloxorz.gui.anim import Vec

SCREEN_DIRS = ("U", "L", "D", "R")
FOV_Y = 45.0
NEAR, FAR = 0.1, 200.0
FLIGHT_TIME = 1.4


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def dot(a: Vec, b: Vec) -> float:
    return sum(x * y for x, y in zip(a, b))


def cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def normalize(v: Vec) -> Vec:
    length = math.sqrt(dot(v, v))
    return v[0] / length, v[1] / length, v[2] / length


@dataclass
class Camera:
    target: Vec
    distance: float
    yaw: float = 0.0
    pitch: float = 55.0

    @classmethod
    def for_level(cls, rows: int, cols: int) -> "Camera":
        return cls((cols / 2, 0.0, rows / 2), max(rows, cols) * 0.9 + 4)

    def eye(self) -> Vec:
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        x, y, z = self.target
        flat = self.distance * math.cos(pitch)
        return (
            x + flat * math.sin(yaw),
            y + self.distance * math.sin(pitch),
            z + flat * math.cos(yaw),
        )

    def orbit(self, dx: float, dy: float) -> None:
        self.yaw -= dx * 0.4
        self.pitch = clamp(self.pitch + dy * 0.3, 15.0, 85.0)

    def zoom(self, steps: float) -> None:
        self.distance = clamp(self.distance * 0.9**steps, 4.0, 80.0)

    def world_direction(self, screen: str) -> str:
        quarter = round(self.yaw / 90) % 4
        return SCREEN_DIRS[(SCREEN_DIRS.index(screen) + quarter) % 4]

    def basis(self) -> tuple[Vec, Vec, Vec]:
        eye = self.eye()
        forward = normalize(tuple(t - e for t, e in zip(self.target, eye)))
        right = normalize(cross(forward, (0.0, 1.0, 0.0)))
        return right, cross(right, forward), forward


def smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


@dataclass
class Flight:
    """Glides the camera between two poses, e.g. from the menu into a level."""

    start: Camera
    end: Camera
    # Lens shift (see scene.set_projection) at both ends of the flight.
    start_shift: float = 0.0
    end_shift: float = 0.0
    duration: float = FLIGHT_TIME
    time: float = 0.0

    def advance(self, dt: float) -> None:
        self.time = min(self.duration, self.time + dt)

    @property
    def done(self) -> bool:
        return self.time >= self.duration

    @property
    def progress(self) -> float:
        return self.time / self.duration

    def pose(self) -> tuple[Camera, float]:
        k = smoothstep(self.progress)

        def mix(a: float, b: float) -> float:
            return a + (b - a) * k

        # Turn the short way round, however many full turns the yaws hold.
        turn = (self.end.yaw - self.start.yaw + 180) % 360 - 180
        camera = Camera(
            tuple(mix(a, b) for a, b in zip(self.start.target, self.end.target)),
            mix(self.start.distance, self.end.distance),
            self.start.yaw + turn * k,
            mix(self.start.pitch, self.end.pitch),
        )
        return camera, mix(self.start_shift, self.end_shift)
