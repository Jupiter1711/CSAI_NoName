import math
import random
from pathlib import Path

import pygame
from OpenGL import GL as gl
from OpenGL import GLU as glu

TEXTURE_DIR = Path(__file__).resolve().parents[2] / "assets" / "textures"
SIZE = 64
SPRITE_SIZE = 128

Color = tuple[int, int, int]


def upload(surface: pygame.Surface, mipmap: bool = False, clamp: bool = False) -> int:
    data = pygame.image.tobytes(surface, "RGBA", True)
    width, height = surface.get_size()
    texture = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    # Sprites must not wrap, or their edges bleed in from the opposite side.
    wrap = gl.GL_CLAMP_TO_EDGE if clamp else gl.GL_REPEAT
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    if mipmap:
        glu.gluBuild2DMipmaps(
            gl.GL_TEXTURE_2D,
            gl.GL_RGBA,
            width,
            height,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            data,
        )
        min_filter = gl.GL_LINEAR_MIPMAP_LINEAR
    else:
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA,
            width,
            height,
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            data,
        )
        min_filter = gl.GL_LINEAR
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)
    return texture


def load_file(name: str) -> int | None:
    path = TEXTURE_DIR / name
    if not path.exists():
        return None
    image = pygame.image.load(str(path))
    surface = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    surface.blit(image, (0, 0))
    return upload(surface, mipmap=True)


def _shade(color: Color, delta: int) -> Color:
    return tuple(max(0, min(255, c + delta)) for c in color)


def _add_noise(surface: pygame.Surface, rng: random.Random, amount: int) -> None:
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b, a = surface.get_at((x, y))
            d = rng.randint(-amount, amount)
            surface.set_at((x, y), (*_shade((r, g, b), d), a))


def _plate(surface: pygame.Surface, base: Color, plate: Color, inset: int) -> None:
    surface.fill(base)
    size = SIZE - 2 * inset
    pygame.draw.rect(surface, plate, (inset, inset, size, size))
    far = SIZE - inset - 1
    pygame.draw.line(surface, _shade(plate, 30), (inset, inset), (far, inset))
    pygame.draw.line(surface, _shade(plate, 30), (inset, inset), (inset, far))
    pygame.draw.line(surface, _shade(plate, -40), (inset, far), (far, far))
    pygame.draw.line(surface, _shade(plate, -40), (far, inset), (far, far))


def _rivets(surface: pygame.Surface, color: Color, margin: int) -> None:
    for x in (margin, SIZE - margin - 1):
        for y in (margin, SIZE - margin - 1):
            pygame.draw.circle(surface, color, (x, y), 2)
            surface.set_at((x, y), _shade(color, -60))


def floor_panel(rng: random.Random) -> pygame.Surface:
    surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    plate = (98, 110, 128)
    _plate(surface, (66, 75, 90), plate, 6)
    pygame.draw.line(surface, _shade(plate, -35), (7, 32), (56, 32))
    pygame.draw.line(surface, _shade(plate, 20), (7, 33), (56, 33))
    _rivets(surface, (150, 160, 175), 10)
    pygame.draw.rect(surface, (90, 210, 255), (27, 13, 10, 3))
    _add_noise(surface, rng, 5)
    return surface


def fragile_panel(rng: random.Random) -> pygame.Surface:
    surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    _plate(surface, (80, 40, 18), (118, 60, 26), 6)
    for _ in range(5):
        x, y = SIZE / 2, SIZE / 2
        for _ in range(6):
            nx = x + rng.uniform(-9, 9)
            ny = y + rng.uniform(-9, 9)
            pygame.draw.line(surface, (255, 150, 60), (x, y), (nx, ny))
            x, y = nx, ny
    _add_noise(surface, rng, 6)
    return surface


def hull_panel(rng: random.Random) -> pygame.Surface:
    surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    plate = (196, 202, 212)
    _plate(surface, (150, 156, 168), plate, 4)
    _rivets(surface, (120, 126, 138), 8)
    pygame.draw.rect(surface, (255, 150, 50), (22, 22, 20, 20), 3)
    pygame.draw.rect(surface, (255, 215, 150), (26, 26, 12, 12))
    _add_noise(surface, rng, 4)
    return surface


def hologram(rng: random.Random) -> pygame.Surface:
    surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    surface.fill((60, 170, 255, 45))
    for i in range(0, SIZE, 8):
        alpha = rng.randint(80, 130)
        pygame.draw.line(surface, (120, 220, 255, alpha), (0, i), (SIZE - 1, i))
        pygame.draw.line(surface, (120, 220, 255, alpha), (i, 0), (i, SIZE - 1))
    pygame.draw.rect(surface, (170, 240, 255, 210), (0, 0, SIZE, SIZE), 2)
    return surface


def _sprite(alpha_at) -> pygame.Surface:
    data = bytearray()
    half = SPRITE_SIZE / 2
    for y in range(SPRITE_SIZE):
        for x in range(SPRITE_SIZE):
            dx, dy = (x + 0.5 - half) / half, (y + 0.5 - half) / half
            r = math.hypot(dx, dy)
            a = alpha_at(r, math.atan2(dy, dx)) if r < 1 else 0.0
            data += bytes((255, 255, 255, int(255 * max(0.0, min(1.0, a)))))
    return pygame.image.frombuffer(bytes(data), (SPRITE_SIZE, SPRITE_SIZE), "RGBA")


def glow_sprite() -> pygame.Surface:
    return _sprite(lambda r, _: (1 - r) ** 2.2)


def halo_sprite(edge: float = 0.77) -> pygame.Surface:
    # Brightest just outside the planet's edge, like light through an atmosphere.
    def alpha(r: float, _: float) -> float:
        if r < edge:
            return 0.3 * (r / edge) ** 6
        return 0.3 + 0.7 * (1 - (r - edge) / (1 - edge)) ** 2 if r < 1 else 0.0

    return _sprite(alpha)


def rays_sprite() -> pygame.Surface:
    def alpha(r: float, angle: float) -> float:
        long_rays = abs(math.cos(angle * 4)) ** 40
        short_rays = 0.5 * abs(math.cos(angle * 4 + math.pi / 4)) ** 30
        return (long_rays + short_rays * (1 - r)) * (1 - r) ** 1.5

    return _sprite(alpha)


def galaxy_sprite(rng: random.Random) -> pygame.Surface:
    def alpha(r: float, angle: float) -> float:
        arms = max(0.0, math.cos(2 * angle - 6 * math.log(r + 0.08))) ** 3
        core = 1.2 * math.exp(-r * r * 30)
        dust = 0.6 + 0.6 * rng.random()
        return (core + 0.8 * arms * (1 - r) ** 1.5) * dust

    return _sprite(alpha)


GREEN_PLANET_STOPS = (
    (0.0, (18, 80, 100)),
    (0.5, (40, 150, 150)),
    (0.54, (150, 215, 170)),
    (0.57, (80, 175, 70)),
    (0.75, (45, 125, 55)),
    (1.0, (170, 220, 140)),
)


def _height_rows(rng: random.Random, width: int, height: int, octaves: int = 4):
    grids = []
    for octave in range(octaves):
        cells_x, cells_y = 6 * 2**octave, 3 * 2**octave
        grid = [[rng.random() for _ in range(cells_x)] for _ in range(cells_y + 1)]
        grids.append((cells_x, cells_y, grid, 0.5**octave))
    total = sum(amp for *_, amp in grids)
    for y in range(height):
        row = []
        for x in range(width):
            h = 0.0
            for cells_x, cells_y, grid, amp in grids:
                fx, fy = x * cells_x / width, y * cells_y / (height - 1)
                ix, iy = int(fx), min(int(fy), cells_y - 1)
                tx, ty = fx - ix, fy - iy
                tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
                x0, x1 = ix % cells_x, (ix + 1) % cells_x
                top = grid[iy][x0] + (grid[iy][x1] - grid[iy][x0]) * tx
                bottom = grid[iy + 1][x0] + (grid[iy + 1][x1] - grid[iy + 1][x0]) * tx
                h += amp * (top + (bottom - top) * ty)
            row.append(h / total)
        yield row


def _ramp(h: float) -> Color:
    for (h0, c0), (h1, c1) in zip(GREEN_PLANET_STOPS, GREEN_PLANET_STOPS[1:]):
        if h <= h1:
            t = (h - h0) / (h1 - h0)
            return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
    return GREEN_PLANET_STOPS[-1][1]


def green_planet(rng: random.Random, width: int = 256, height: int = 128):
    data = bytearray()
    for row in _height_rows(rng, width, height):
        for h in row:
            # Stretch the values (they cluster around 0.5) to get real islands.
            data += bytes((*_ramp(max(0.0, min(1.0, (h - 0.5) * 2.4 + 0.5))), 255))
    return pygame.image.frombuffer(bytes(data), (width, height), "RGBA")


def build() -> dict[str, int]:
    rng = random.Random(42)
    return {
        "floor": upload(floor_panel(rng)),
        "fragile": upload(fragile_panel(rng)),
        "hull": upload(hull_panel(rng)),
        "hologram": upload(hologram(rng)),
        "glow": upload(glow_sprite(), clamp=True),
        "halo": upload(halo_sprite(), clamp=True),
        "rays": upload(rays_sprite(), clamp=True),
        "galaxy": upload(galaxy_sprite(rng), clamp=True),
        "green_planet": upload(green_planet(rng), mipmap=True),
    }
