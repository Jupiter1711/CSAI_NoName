import math
from itertools import combinations, product

import pygame
from OpenGL import GL as gl
from OpenGL import GLU as glu

from bloxorz.core.level import (
    BRIDGE,
    FRAGILE,
    GOAL,
    HEAVY,
    SOFT,
    SPLITTER,
    VOID,
    Level,
)
from bloxorz.core.state import SPLIT, Cell, State
from bloxorz.gui import textures
from bloxorz.gui.anim import Box, Motion, Vec, box_center, state_boxes
from bloxorz.gui.camera import FAR, FOV_Y, NEAR, Camera

Rgb = tuple[float, float, float]

BG = (0.01, 0.01, 0.03)
WHITE = (1.0, 1.0, 1.0)
GOAL_COLOR = (0.02, 0.0, 0.05)
FLOOR_GLOW = (0.35, 0.85, 1.0)
FRAGILE_GLOW = (1.0, 0.55, 0.15)
BRIDGE_GLOW = (0.4, 0.8, 1.0)
SWITCH_GLOW = {
    SOFT: (0.3, 0.9, 1.0),
    HEAVY: (1.0, 0.3, 0.35),
    SPLITTER: (0.75, 0.45, 1.0),
}
PORTAL_COLORS = ((0.65, 0.35, 1.0), (0.3, 0.85, 1.0))
BLOCK_GLOW = (1.0, 0.55, 0.15)
SELECTED_GLOW = (1.0, 0.85, 0.3)
IDLE_GLOW = (0.35, 0.55, 0.9)
SPARK_COLORS = ((0.45, 0.85, 1.0), (1.0, 0.65, 0.30))
TEXT_COLOR = (235, 235, 240)
HUD_BG = (5, 8, 18, 170)

TILE_DEPTH = 0.25
GAP = 0.03
KEY_DIFFUSE = (1.0, 0.93, 0.82, 1.0)
KEY_AMBIENT = (0.26, 0.26, 0.32, 1.0)
FILL_DIFFUSE = (0.16, 0.24, 0.45, 1.0)
SPECULAR = (0.25, 0.25, 0.25, 1.0)
HULL_SPECULAR = (0.9, 0.85, 0.8, 1.0)
GLOW_PASSES = ((6.0, 0.25), (1.8, 1.0))
BEAM_HEIGHT = 1.6
BEAM_RADIUS = 0.38

CORNERS = list(product((0, 1), repeat=3))
EDGES = [
    (a, b)
    for a, b in combinations(CORNERS, 2)
    if sum(i != j for i, j in zip(a, b)) == 1
]
TOP_EDGES = [(a, b) for a, b in EDGES if a[1] == b[1] == 1]
FACES = (
    ((1, 0, 0), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
    ((-1, 0, 0), ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
    ((0, 1, 0), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
    ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
    ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
    ((0, 0, -1), ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0))),
)
FACE_AXES = [tuple(i for i in range(3) if not normal[i]) for normal, _ in FACES]

_quadric = None
_tex: dict[str, int] = {}


def init(width: int, height: int) -> None:
    global _quadric
    _quadric = glu.gluNewQuadric()
    _tex.update(textures.build())
    gl.glViewport(0, 0, width, height)
    set_projection(width, height)
    gl.glClearColor(*BG, 1.0)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_NORMALIZE)
    gl.glEnable(gl.GL_LIGHTING)
    gl.glEnable(gl.GL_LIGHT0)
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_AMBIENT, KEY_AMBIENT)
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE, KEY_DIFFUSE)
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_SPECULAR, KEY_DIFFUSE)
    gl.glEnable(gl.GL_LIGHT1)
    gl.glLightfv(gl.GL_LIGHT1, gl.GL_AMBIENT, (0.0, 0.0, 0.0, 1.0))
    gl.glLightfv(gl.GL_LIGHT1, gl.GL_DIFFUSE, FILL_DIFFUSE)
    gl.glLightfv(gl.GL_LIGHT1, gl.GL_SPECULAR, (0.0, 0.0, 0.0, 1.0))
    # Add highlights after texturing so shiny metal stays bright.
    gl.glLightModeli(gl.GL_LIGHT_MODEL_COLOR_CONTROL, gl.GL_SEPARATE_SPECULAR_COLOR)
    gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_SPECULAR, SPECULAR)
    gl.glMaterialf(gl.GL_FRONT_AND_BACK, gl.GL_SHININESS, 24.0)
    gl.glEnable(gl.GL_COLOR_MATERIAL)
    gl.glColorMaterial(gl.GL_FRONT_AND_BACK, gl.GL_AMBIENT_AND_DIFFUSE)
    # Push faces back a little so edge lines are not hidden by z-fighting.
    gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
    gl.glPolygonOffset(1.0, 1.0)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
    gl.glEnable(gl.GL_LINE_SMOOTH)
    gl.glHint(gl.GL_LINE_SMOOTH_HINT, gl.GL_NICEST)


def set_projection(width: int, height: int, shift: float = 0.0) -> None:
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glLoadIdentity()
    # Lens shift: slides the whole picture sideways (in screen halves) without
    # turning the camera, e.g. to put the menu's 3D preview beside the buttons.
    gl.glTranslatef(shift, 0.0, 0.0)
    glu.gluPerspective(FOV_Y, width / height, NEAR, FAR)
    gl.glMatrixMode(gl.GL_MODELVIEW)


def sprites() -> dict[str, int]:
    return _tex


def begin_frame(camera: Camera, key: Vec, fill: Vec) -> None:
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    gl.glLoadIdentity()
    glu.gluLookAt(*camera.eye(), *camera.target, 0.0, 1.0, 0.0)
    gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, (*key, 0.0))
    gl.glLightfv(gl.GL_LIGHT1, gl.GL_POSITION, (*fill, 0.0))


def _point(box: Box, corner: tuple[int, int, int]) -> tuple[float, float, float]:
    x0, y0, z0, x1, y1, z1 = box
    cx, cy, cz = corner
    return (x1 if cx else x0, y1 if cy else y0, z1 if cz else z0)


def _box_quads(box: Box, fit: bool) -> None:
    x0, y0, z0, x1, y1, z1 = box
    size = (x1 - x0, y1 - y0, z1 - z0)
    for (normal, corners), (a, b) in zip(FACES, FACE_AXES):
        gl.glNormal3f(*normal)
        for corner in corners:
            # fit: one texture per face; otherwise repeat once per world unit
            u = corner[a] if fit else corner[a] * size[a]
            v = corner[b] if fit else corner[b] * size[b]
            gl.glTexCoord2f(u, v)
            gl.glVertex3f(*_point(box, corner))


def draw_box(
    box: Box,
    color: Rgb = WHITE,
    alpha: float = 1.0,
    texture: int | None = None,
    fit: bool = False,
) -> None:
    if texture is not None:
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    gl.glColor4f(*color, alpha)
    gl.glBegin(gl.GL_QUADS)
    _box_quads(box, fit)
    gl.glEnd()
    if texture is not None:
        gl.glDisable(gl.GL_TEXTURE_2D)


def _begin_glow() -> None:
    gl.glDisable(gl.GL_LIGHTING)
    gl.glDepthMask(gl.GL_FALSE)
    # Additive blending: overlapping glows add up and look brighter.
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)


def _end_glow() -> None:
    gl.glLineWidth(1.0)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
    gl.glDepthMask(gl.GL_TRUE)
    gl.glEnable(gl.GL_LIGHTING)


def _glow_edges(box: Box, color: Rgb, strength: float) -> None:
    _begin_glow()
    for width, k in GLOW_PASSES:
        gl.glLineWidth(width)
        gl.glColor4f(*color, strength * k)
        gl.glBegin(gl.GL_LINES)
        for a, b in EDGES:
            gl.glVertex3f(*_point(box, a))
            gl.glVertex3f(*_point(box, b))
        gl.glEnd()
    _end_glow()


def _draw_hull(box: Box, glow: Rgb, strength: float = 1.0, alpha: float = 1.0):
    gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_SPECULAR, HULL_SPECULAR)
    gl.glMaterialf(gl.GL_FRONT_AND_BACK, gl.GL_SHININESS, 48.0)
    draw_box(box, alpha=alpha, texture=_tex["hull"])
    gl.glMaterialfv(gl.GL_FRONT_AND_BACK, gl.GL_SPECULAR, SPECULAR)
    gl.glMaterialf(gl.GL_FRONT_AND_BACK, gl.GL_SHININESS, 24.0)
    _glow_edges(box, glow, strength * alpha)


def _tile_box(r: int, c: int, top: float = 0.0, lift: float = 0.0) -> Box:
    return c + GAP, lift - TILE_DEPTH, r + GAP, c + 1 - GAP, lift + top, r + 1 - GAP


def _lift(lifts: dict[Cell, float] | None, r: int, c: int) -> float | None:
    """How far a tile is moved up or down; None if it is not on screen."""
    return 0.0 if lifts is None else lifts.get((r, c))


def _flat_bar(length: float, width: float) -> None:
    gl.glBegin(gl.GL_QUADS)
    for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        gl.glVertex3f(x * length / 2, y * width / 2, 0.0)
    gl.glEnd()


class LevelView:
    def __init__(self, level: Level):
        self.level = level
        self.cells = [
            (r, c, level.tile(r, c))
            for r in range(level.rows)
            for c in range(level.cols)
            if level.tile(r, c) != VOID
        ]
        self._lists: dict[int, int] = {}

    def release(self) -> None:
        for display_list in self._lists.values():
            gl.glDeleteLists(display_list, 1)
        self._lists.clear()

    def draw_solid(self, bridges: int, lifts: dict[Cell, float] | None = None):
        if lifts is not None:
            self._compile_solid(lifts)
            return
        if bridges not in self._lists:
            display_list = gl.glGenLists(1)
            gl.glNewList(display_list, gl.GL_COMPILE)
            self._compile_solid()
            gl.glEndList()
            self._lists[bridges] = display_list
        gl.glCallList(self._lists[bridges])

    def _compile_solid(self, lifts: dict[Cell, float] | None = None) -> None:
        for r, c, t in self.cells:
            lift = _lift(lifts, r, c)
            if lift is None:
                continue
            if t == GOAL:
                draw_box(_tile_box(r, c, 0.02 - TILE_DEPTH, lift), GOAL_COLOR)
            elif t != BRIDGE:
                texture = _tex["fragile" if t == FRAGILE else "floor"]
                draw_box(_tile_box(r, c, lift=lift), texture=texture, fit=True)

    def draw_glow(
        self, bridges: int, time: float, lifts: dict[Cell, float] | None = None
    ) -> None:
        _begin_glow()
        open_bridges = []
        closed_bridges = []
        rims = []
        for r, c, t in self.cells:
            lift = _lift(lifts, r, c)
            if t == GOAL or lift is None:
                continue
            box = _tile_box(r, c, lift=lift)
            if t == BRIDGE:
                if self.level.supports((r, c), bridges):
                    open_bridges.append(box)
                else:
                    closed_bridges.append(box)
                    continue
            pulse = 0.45 + 0.25 * math.sin(time * 2.2 - (r + c) * 0.45)
            if t == FRAGILE:
                color = FRAGILE_GLOW
            elif t == BRIDGE:
                color = BRIDGE_GLOW
            else:
                color = FLOOR_GLOW
            rims.append((box, color, pulse))
        self._draw_holograms(open_bridges)
        self._draw_rims(rims)
        self._draw_closed(closed_bridges)
        for r, c in self.level.switches:
            lift = _lift(lifts, r, c)
            if lift is not None:
                self._draw_switch(self.level.tile(r, c), r, c, time, lift)
        lift = _lift(lifts, *self.level.goal)
        if lift is not None:
            self._draw_portal(*self.level.goal, time, lift)
        _end_glow()

    def _draw_rims(self, rims: list[tuple[Box, Rgb, float]]) -> None:
        for width, k in GLOW_PASSES:
            gl.glLineWidth(width)
            gl.glBegin(gl.GL_LINES)
            for box, color, pulse in rims:
                gl.glColor4f(*color, pulse * k)
                for a, b in TOP_EDGES:
                    gl.glVertex3f(*_point(box, a))
                    gl.glVertex3f(*_point(box, b))
            gl.glEnd()

    def _draw_holograms(self, boxes: list[Box]) -> None:
        if not boxes:
            return
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, _tex["hologram"])
        gl.glColor4f(1.0, 1.0, 1.0, 0.9)
        gl.glBegin(gl.GL_QUADS)
        for box in boxes:
            _box_quads(box, fit=True)
        gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)

    def _draw_closed(self, boxes: list[Box]) -> None:
        if not boxes:
            return
        gl.glEnable(gl.GL_LINE_STIPPLE)
        gl.glLineStipple(2, 0x0F0F)
        gl.glLineWidth(1.5)
        gl.glColor4f(*BRIDGE_GLOW, 0.35)
        gl.glBegin(gl.GL_LINES)
        for box in boxes:
            for a, b in TOP_EDGES:
                gl.glVertex3f(*_point(box, a))
                gl.glVertex3f(*_point(box, b))
        gl.glEnd()
        gl.glDisable(gl.GL_LINE_STIPPLE)

    def _draw_switch(self, t: str, r: int, c: int, time: float, lift: float):
        pulse = 0.65 + 0.35 * math.sin(time * 3.0 + r + c)
        gl.glPushMatrix()
        gl.glTranslatef(c + 0.5, 0.01 + lift, r + 0.5)
        gl.glRotatef(-90, 1, 0, 0)
        gl.glColor4f(*SWITCH_GLOW[t], pulse)
        if t == SOFT:
            glu.gluDisk(_quadric, 0.18, 0.3, 32, 1)
        elif t == HEAVY:
            for angle in (45, -45):
                gl.glPushMatrix()
                gl.glRotatef(angle, 0, 0, 1)
                _flat_bar(0.6, 0.12)
                gl.glPopMatrix()
        elif t == SPLITTER:
            glu.gluPartialDisk(_quadric, 0.16, 0.26, 16, 1, 200, 140)
            glu.gluPartialDisk(_quadric, 0.16, 0.26, 16, 1, 20, 140)
        gl.glPopMatrix()

    def _draw_portal(self, r: int, c: int, time: float, lift: float) -> None:
        gl.glPushMatrix()
        gl.glTranslatef(c + 0.5, 0.03 - TILE_DEPTH + lift, r + 0.5)
        gl.glPushMatrix()
        gl.glRotatef(-90, 1, 0, 0)
        for i in range(3):
            gl.glPushMatrix()
            spin = time * (90 + 40 * i) * (-1) ** i
            gl.glRotatef(spin, 0, 0, 1)
            gl.glColor4f(*PORTAL_COLORS[i % 2], 0.8)
            inner = 0.1 + 0.11 * i
            glu.gluPartialDisk(_quadric, inner, inner + 0.06, 24, 1, 0, 230)
            gl.glPopMatrix()
        gl.glPopMatrix()
        # Beam of light rising from the hole, fading out towards the top.
        pulse = 0.25 + 0.1 * math.sin(time * 4)
        gl.glBegin(gl.GL_QUAD_STRIP)
        for i in range(25):
            angle = 2 * math.pi * i / 24
            x, z = BEAM_RADIUS * math.cos(angle), BEAM_RADIUS * math.sin(angle)
            gl.glColor4f(*PORTAL_COLORS[0], pulse)
            gl.glVertex3f(x, 0.0, z)
            gl.glColor4f(*PORTAL_COLORS[1], 0.0)
            gl.glVertex3f(x, BEAM_HEIGHT, z)
        gl.glEnd()
        gl.glPopMatrix()


def draw_state(state: State, selected: int, lift: float = 0.0) -> None:
    if lift:
        gl.glPushMatrix()
        gl.glTranslatef(0.0, lift, 0.0)
        draw_state(state, selected)
        gl.glPopMatrix()
        return
    boxes = state_boxes(state)
    if state.kind != SPLIT:
        _draw_hull(boxes[0], BLOCK_GLOW)
        return
    for i, box in enumerate(boxes):
        if i == selected:
            _draw_hull(box, SELECTED_GLOW)
        else:
            _draw_hull(box, IDLE_GLOW, strength=0.6)


def draw_motion(motion: Motion, lifts: dict[Cell, float] | None = None) -> None:
    for box in motion.still:
        lift = _lift(lifts, int(box[2]), int(box[0]))
        if lift is None:
            continue
        gl.glPushMatrix()
        gl.glTranslatef(0.0, lift, 0.0)
        _draw_hull(box, IDLE_GLOW, strength=0.6)
        gl.glPopMatrix()
    if motion.fade <= 0:
        _draw_sparks(motion)
        return
    if motion.sinks:
        gl.glClipPlane(gl.GL_CLIP_PLANE0, (0.0, 1.0, 0.0, 0.0))
        gl.glEnable(gl.GL_CLIP_PLANE0)
    px, py, pz = motion.pivot
    cx, cy, cz = box_center(motion.moving)
    wx, _, wz = motion.center
    gl.glPushMatrix()
    gl.glTranslatef(*motion.offset)
    gl.glTranslatef(wx, 0.0, wz)
    gl.glRotatef(motion.spin, 0, 1, 0)
    gl.glTranslatef(-wx, 0.0, -wz)
    gl.glTranslatef(px, py, pz)
    gl.glRotatef(motion.angle, *motion.axis)
    gl.glTranslatef(-px, -py, -pz)
    gl.glTranslatef(cx, cy, cz)
    gl.glRotatef(motion.tumble, *motion.axis)
    gl.glScalef(motion.scale, motion.scale, motion.scale)
    gl.glTranslatef(-cx, -cy, -cz)
    glow = SELECTED_GLOW if motion.still else BLOCK_GLOW
    _draw_hull(motion.moving, glow, alpha=motion.fade)
    gl.glPopMatrix()
    gl.glDisable(gl.GL_CLIP_PLANE0)
    _draw_sparks(motion)


def _draw_sparks(motion: Motion) -> None:
    sparks = motion.live_sparks()
    if not sparks:
        return
    _begin_glow()
    gl.glEnable(gl.GL_POINT_SMOOTH)
    gl.glPointSize(5.0)
    colors = PORTAL_COLORS if motion.sinks else SPARK_COLORS
    gl.glBegin(gl.GL_POINTS)
    for i, (pos, life) in enumerate(sparks):
        gl.glColor4f(*colors[i % len(colors)], life)
        gl.glVertex3f(*pos)
    gl.glEnd()
    _end_glow()


def draw_hud(lines: list[str], font: pygame.font.Font, width: int, height: int):
    rendered = [font.render(line, True, TEXT_COLOR) for line in lines]
    bar_height = sum(s.get_height() + 4 for s in rendered) + 12
    hud = pygame.Surface((width, bar_height), pygame.SRCALPHA)
    hud.fill(HUD_BG)
    y = 8
    for surface in rendered:
        hud.blit(surface, (12, y))
        y += surface.get_height() + 4
    draw_surface(hud, 0, 0, height)


def draw_shade(alpha: float, width: int, height: int) -> None:
    """Darken the whole window: 0 leaves it as is, 1 paints it black."""
    pixel = bytes((0, 0, 0, round(255 * alpha)))
    gl.glDisable(gl.GL_LIGHTING)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glWindowPos2d(0, 0)
    gl.glPixelZoom(width, height)
    gl.glDrawPixels(1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, pixel)
    gl.glPixelZoom(1, 1)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_LIGHTING)


def draw_surface(surface: pygame.Surface, x: int, y: int, height: int) -> None:
    """Paint a pygame surface over the 3D scene, (x, y) being its top-left
    corner in window pixels (y going down, as in pygame)."""
    w, h = surface.get_size()
    data = pygame.image.tobytes(surface, "RGBA", True)
    gl.glDisable(gl.GL_LIGHTING)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glWindowPos2d(x, height - y - h)
    gl.glDrawPixels(w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_LIGHTING)
