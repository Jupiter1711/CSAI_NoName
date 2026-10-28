import math
import random
from dataclasses import dataclass

from OpenGL import GL as gl
from OpenGL import GLU as glu

from bloxorz.gui import textures
from bloxorz.gui.anim import Vec
from bloxorz.gui.camera import Camera, normalize

Rgb = tuple[float, float, float]

SKY_FILE = "2k_stars_milky_way.jpg"
SUN_FILE = "1k_sun.jpg"
CLOUDS_FILE = "1k_earth_clouds.jpg"

SKY_RADIUS = 90.0
SKY_TINT = (0.8, 0.8, 0.9)
STAR_COUNT = 350
STAR_RADIUS = 80.0
STAR_COLOR = (0.85, 0.9, 1.0)

SUN_OFFSET = (-2.6, -2.7, -3.6)
SUN_RADIUS = 0.35
SUN_TINT = (1.0, 0.93, 0.8)
KEY_ELEVATION = 50.0
FILL_ELEVATION = 25.0
PLANET_AMBIENT = (0.06, 0.06, 0.08, 1.0)


@dataclass(frozen=True)
class Orbit:
    """Circle around the sun's vertical axis, in board sizes."""

    radius: float
    height: float
    phase: float
    period: float

    def offset(self, time: float) -> Vec:
        angle = math.radians(self.phase) + 2 * math.pi * time / self.period
        # Counterclockwise seen from above, like the real planets.
        r = self.radius
        return (r * math.cos(angle), self.height, -r * math.sin(angle))


@dataclass(frozen=True)
class Body:
    texture: str
    orbit: Orbit | None
    radius: float
    spin: float
    tilt: float = 0.0
    halo: Rgb | None = None
    shininess: float = 0.0
    rings: tuple[tuple[float, float, Rgb, float], ...] = ()


SATURN_RINGS = (
    (1.25, 1.55, (0.85, 0.78, 0.62), 0.55),
    (1.6, 1.95, (0.9, 0.84, 0.7), 0.7),
    (2.0, 2.25, (0.7, 0.65, 0.55), 0.35),
)
URANUS_RINGS = (
    (1.6, 1.68, (0.7, 0.85, 0.9), 0.5),
    (1.85, 1.95, (0.7, 0.85, 0.9), 0.35),
)

MERCURY = Body("1k_mercury.jpg", Orbit(1.0, -0.3, 100.0, 30.0), 0.12, 2.0)
VENUS = Body(
    "1k_venus_atmosphere.jpg",
    Orbit(1.5, -1.2, -60.0, 40.0),
    0.2,
    1.5,
    halo=(1.0, 0.85, 0.55),
)
EARTH = Body(
    "1k_earth_daymap.jpg",
    Orbit(2.1, -2.4, -90.0, 52.0),
    0.3,
    6.0,
    23.0,
    halo=(0.35, 0.65, 1.0),
    shininess=20.0,
)
MOON = Body("1k_moon.jpg", None, 0.08, 2.0)
MOON_ORBIT = 2.4
MOON_SPEED = 12.0
MARS = Body(
    "1k_mars.jpg",
    Orbit(2.6, -0.7, 20.0, 65.0),
    0.16,
    7.0,
    25.0,
    halo=(1.0, 0.55, 0.35),
)
GREEN_PLANET = Body(
    "green_planet",
    Orbit(3.1, -1.5, 90.0, 80.0),
    0.32,
    5.0,
    -12.0,
    halo=(0.45, 1.0, 0.6),
)
JUPITER = Body("1k_jupiter.jpg", Orbit(3.8, -0.5, -20.0, 95.0), 0.55, 9.0, 3.0)
SATURN = Body(
    "2k_saturn.jpg",
    Orbit(4.6, -2.6, 60.0, 115.0),
    0.42,
    3.0,
    25.0,
    rings=SATURN_RINGS,
)
URANUS = Body(
    "1k_uranus.jpg",
    Orbit(5.3, -4.4, 100.0, 135.0),
    0.3,
    -5.0,
    98.0,
    halo=(0.5, 0.9, 1.0),
    rings=URANUS_RINGS,
)
NEPTUNE = Body(
    "1k_neptune.jpg",
    Orbit(5.9, -2.0, 10.0, 160.0),
    0.26,
    5.5,
    28.0,
    halo=(0.35, 0.55, 1.0),
)
PLANETS = (
    MERCURY,
    VENUS,
    EARTH,
    MARS,
    JUPITER,
    SATURN,
    URANUS,
    NEPTUNE,
    GREEN_PLANET,
)

GALAXY_DISTANCE = 70.0
GALAXIES = (
    ((0.0, -1.1, -0.3), 9.0, (0.85, 0.7, 1.0), 25.0, 0.45),
    ((-1.0, -0.9, -0.1), 7.0, (0.6, 0.8, 1.0), -40.0, 0.6),
    ((0.7, -0.9, 1.0), 8.0, (1.0, 0.85, 0.6), 70.0, 0.4),
)


def _place(center: Vec, span: float, offset: Vec) -> Vec:
    return tuple(c + o * span for c, o in zip(center, offset))


class Space:
    def __init__(self, sprites: dict[str, int], files: dict[str, int | None]):
        self.sprites = sprites
        self.files = files
        self.quadric = glu.gluNewQuadric()
        glu.gluQuadricTexture(self.quadric, gl.GL_TRUE)
        rng = random.Random(7)
        self.stars = []
        for _ in range(STAR_COUNT):
            y = rng.uniform(-1, 1)
            theta = rng.uniform(0, 2 * math.pi)
            ring = math.sqrt(1 - y * y)
            direction = (ring * math.cos(theta), y, ring * math.sin(theta))
            self.stars.append(
                (direction, rng.uniform(0, 2 * math.pi), rng.uniform(1, 3))
            )
        self.sun_pos: Vec = (0.0, 0.0, 0.0)

    @classmethod
    def load(cls, sprites: dict[str, int]) -> "Space":
        names = [SKY_FILE, SUN_FILE, CLOUDS_FILE, MOON.texture]
        names += [body.texture for body in PLANETS if body.texture not in sprites]
        return cls(sprites, {name: textures.load_file(name) for name in names})

    def _texture(self, name: str) -> int | None:
        return self.sprites.get(name) or self.files.get(name)

    def lights(self, center: Vec, span: float) -> tuple[Vec, Vec]:
        sun = _place(center, span, SUN_OFFSET)
        dx, dz = sun[0] - center[0], sun[2] - center[2]
        flat = math.hypot(dx, dz)
        key, fill = math.radians(KEY_ELEVATION), math.radians(FILL_ELEVATION)
        return (
            (dx / flat * math.cos(key), math.sin(key), dz / flat * math.cos(key)),
            (-dx / flat * math.cos(fill), math.sin(fill), -dz / flat * math.cos(fill)),
        )

    def draw_background(self, camera: Camera, time: float) -> None:
        gl.glDisable(gl.GL_LIGHTING)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glPushMatrix()
        # Centered on the eye so the sky never gets closer when zooming.
        gl.glTranslatef(*camera.eye())
        sky = self.files.get(SKY_FILE)
        if sky is not None:
            gl.glEnable(gl.GL_TEXTURE_2D)
            gl.glBindTexture(gl.GL_TEXTURE_2D, sky)
            gl.glColor3f(*SKY_TINT)
            gl.glPushMatrix()
            gl.glRotatef(-90, 1, 0, 0)
            gl.glRotatef(time * 0.6, 0, 0, 1)
            glu.gluSphere(self.quadric, SKY_RADIUS, 48, 24)
            gl.glPopMatrix()
            gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
        gl.glPointSize(2.5)
        gl.glBegin(gl.GL_POINTS)
        for (x, y, z), phase, speed in self.stars:
            twinkle = 0.5 + 0.5 * math.sin(time * speed + phase)
            gl.glColor4f(*STAR_COLOR, 0.35 + 0.65 * twinkle)
            gl.glVertex3f(x * STAR_RADIUS, y * STAR_RADIUS, z * STAR_RADIUS)
        gl.glEnd()
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        right, up, _ = camera.basis()
        for direction, half, color, angle, aspect in GALAXIES:
            pos = tuple(GALAXY_DISTANCE * d for d in normalize(direction))
            spin = angle + time * 0.8
            self._sprite("galaxy", pos, half, right, up, color, 0.85, spin, aspect)
        gl.glPopMatrix()
        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_LIGHTING)

    def draw_bodies(
        self, camera: Camera, center: Vec, span: float, time: float
    ) -> None:
        right, up, _ = camera.basis()
        self.sun_pos = _place(center, span, SUN_OFFSET)
        self._draw_sun(SUN_RADIUS * span, right, up, time)
        for body in PLANETS:
            offset = tuple(s + o for s, o in zip(SUN_OFFSET, body.orbit.offset(time)))
            pos = _place(center, span, offset)
            self._draw_planet(body, pos, span, time, right, up)
            if body is EARTH:
                self._draw_clouds(pos, EARTH.radius * span, time)
                orbit = EARTH.radius * span * MOON_ORBIT
                angle = math.radians(time * MOON_SPEED)
                moon = (
                    pos[0] + orbit * math.cos(angle),
                    pos[1] + orbit * 0.25 * math.sin(angle),
                    pos[2] + orbit * math.sin(angle),
                )
                self._draw_planet(MOON, moon, span, time, right, up)

    def _sun_light(self, pos: Vec) -> None:
        to_sun = normalize(tuple(s - p for s, p in zip(self.sun_pos, pos)))
        gl.glDisable(gl.GL_LIGHT1)
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, (*to_sun, 0.0))
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_AMBIENT, PLANET_AMBIENT)

    def _draw_sun(self, radius: float, right: Vec, up: Vec, time: float) -> None:
        pulse = 1 + 0.06 * math.sin(time * 2.5)
        gl.glPushAttrib(gl.GL_ENABLE_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glDisable(gl.GL_LIGHTING)
        # No depth write, or the sphere's front would hide the glow sprites
        # that pass through its center.
        gl.glDepthMask(gl.GL_FALSE)
        texture = self.files.get(SUN_FILE)
        if texture is not None:
            gl.glEnable(gl.GL_TEXTURE_2D)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glColor3f(*SUN_TINT)
        gl.glPushMatrix()
        gl.glTranslatef(*self.sun_pos)
        gl.glRotatef(-90, 1, 0, 0)
        gl.glRotatef(time * 2, 0, 0, 1)
        glu.gluSphere(self.quadric, radius, 48, 32)
        gl.glPopMatrix()
        gl.glPopAttrib()
        pos = self.sun_pos
        self._sprite(
            "glow", pos, radius * 2.6 * pulse, right, up, (1.0, 0.75, 0.35), 0.9
        )
        self._sprite("glow", pos, radius * 6 * pulse, right, up, (1.0, 0.55, 0.25), 0.3)
        self._sprite(
            "rays", pos, radius * 5, right, up, (1.0, 0.85, 0.6), 0.55, time * 4
        )
        self._sprite(
            "rays", pos, radius * 3.6, right, up, (1.0, 0.9, 0.7), 0.4, 22 - time * 6
        )

    def _draw_planet(
        self, body: Body, pos: Vec, span: float, time: float, right: Vec, up: Vec
    ) -> None:
        radius = body.radius * span
        gl.glPushAttrib(gl.GL_LIGHTING_BIT | gl.GL_ENABLE_BIT)
        self._sun_light(pos)
        shine = 0.45 if body.shininess else 0.0
        gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_SPECULAR, (shine, shine, shine, 1))
        gl.glMaterialf(gl.GL_FRONT_AND_BACK, gl.GL_SHININESS, body.shininess or 1.0)
        texture = self._texture(body.texture)
        if texture is not None:
            gl.glEnable(gl.GL_TEXTURE_2D)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glColor3f(1.0, 1.0, 1.0)
        gl.glPushMatrix()
        gl.glTranslatef(*pos)
        gl.glRotatef(body.tilt, 0, 0, 1)
        # GLU spheres are built around z; turn that axis to point up.
        gl.glRotatef(-90, 1, 0, 0)
        gl.glRotatef(time * body.spin, 0, 0, 1)
        glu.gluSphere(self.quadric, radius, 48, 32)
        gl.glPopMatrix()
        gl.glPopAttrib()
        if body.rings:
            self._draw_rings(body, pos, radius)
        if body.halo is not None:
            self._sprite("halo", pos, radius * 1.3, right, up, body.halo, 0.8)

    def _draw_clouds(self, pos: Vec, radius: float, time: float) -> None:
        texture = self.files.get(CLOUDS_FILE)
        if texture is None:
            return
        gl.glPushAttrib(
            gl.GL_LIGHTING_BIT
            | gl.GL_ENABLE_BIT
            | gl.GL_COLOR_BUFFER_BIT
            | gl.GL_DEPTH_BUFFER_BIT
        )
        self._sun_light(pos)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glColor3f(1.0, 1.0, 1.0)
        gl.glDepthMask(gl.GL_FALSE)
        # Screen blending: white clouds brighten, black parts leave Earth as is.
        gl.glBlendFunc(gl.GL_ONE, gl.GL_ONE_MINUS_SRC_COLOR)
        gl.glPushMatrix()
        gl.glTranslatef(*pos)
        gl.glRotatef(EARTH.tilt, 0, 0, 1)
        gl.glRotatef(-90, 1, 0, 0)
        gl.glRotatef(time * EARTH.spin * 1.3, 0, 0, 1)
        glu.gluSphere(self.quadric, radius * 1.015, 48, 32)
        gl.glPopMatrix()
        gl.glPopAttrib()

    def _draw_rings(self, body: Body, pos: Vec, radius: float) -> None:
        gl.glPushAttrib(gl.GL_ENABLE_BIT | gl.GL_DEPTH_BUFFER_BIT)
        gl.glDisable(gl.GL_LIGHTING)
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glPushMatrix()
        gl.glTranslatef(*pos)
        gl.glRotatef(body.tilt, 0, 0, 1)
        gl.glRotatef(-90, 1, 0, 0)
        for inner, outer, color, alpha in body.rings:
            gl.glColor4f(*color, alpha)
            glu.gluDisk(self.quadric, inner * radius, outer * radius, 96, 1)
        gl.glPopMatrix()
        gl.glPopAttrib()

    def _sprite(
        self,
        name: str,
        pos: Vec,
        half: float,
        right: Vec,
        up: Vec,
        color: Rgb,
        alpha: float,
        angle: float = 0.0,
        aspect: float = 1.0,
    ) -> None:
        """Camera-facing glowing quad, added on top of what is behind it."""
        rad = math.radians(angle)
        cos, sin = math.cos(rad), math.sin(rad)
        r = tuple(a * cos + b * sin for a, b in zip(right, up))
        u = tuple((b * cos - a * sin) * aspect for a, b in zip(right, up))
        gl.glPushAttrib(
            gl.GL_ENABLE_BIT | gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT
        )
        gl.glDisable(gl.GL_LIGHTING)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.sprites[name])
        gl.glDepthMask(gl.GL_FALSE)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
        gl.glColor4f(*color, alpha)
        gl.glBegin(gl.GL_QUADS)
        for tu, tv, sx, sy in (
            (0, 0, -1, -1),
            (1, 0, 1, -1),
            (1, 1, 1, 1),
            (0, 1, -1, 1),
        ):
            gl.glTexCoord2f(tu, tv)
            gl.glVertex3f(*(p + (a * sx + b * sy) * half for p, a, b in zip(pos, r, u)))
        gl.glEnd()
        gl.glPopAttrib()
