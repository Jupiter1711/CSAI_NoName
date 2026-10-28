from dataclasses import dataclass

import pygame

from bloxorz.core.level import HEAVY, SOFT, SPLITTER
from bloxorz.gui import scene

MAIN = "main"
LEVELS = "levels"
HELP = "help"
PLAY = "play"
QUIT = "quit"

TITLE = "BLOXORZ"
TAGLINE = "ROLL ACROSS THE COSMOS"
FONT_NAMES = "bahnschrift,segoeui,arial"

TEXT = (235, 238, 245)
DIM = (140, 158, 192)
SOFT_TEXT = (184, 198, 226)
ACCENT = (90, 215, 255)
WARM = (255, 160, 70)
BUTTON_BG = (10, 16, 36, 190)
BUTTON_FOCUS_BG = (22, 50, 92, 230)
BUTTON_EDGE = (60, 96, 155)
PANEL_BG = (6, 10, 26, 210)
SHADE = (2, 4, 14)

LEFT = 60
RADIUS = 12
BUTTON_W, BUTTON_H, BUTTON_GAP = 320, 54, 14
MAIN_TOP = 262
GRID_COLS = 2
CELL_W, CELL_H, CELL_GAP = 153, 60, 14
GRID_TOP = 150
BACK_TOP = 532
HELP_PANEL = (LEFT, 128, 560, 388)
HELP_PAD = 20
HELP_KEY_W = 110
SCROLL_STEP = 40
SHADE_REACH = 600

CONTROLS = (
    ("Arrow keys", "roll the block"),
    ("Space", "switch cube after a split"),
    ("R  /  N", "restart  /  next level"),
    ("1 - 4", "solve with BFS / DFS / UCS / A*"),
    ("Esc", "back to this menu"),
    ("Mouse", "drag to rotate, wheel to zoom"),
)
SOLVER_NOTES = (
    (
        "BFS",
        "Breadth-first: tries every 1-move path, then every 2-move "
        "path, ... so it finds the fewest moves.",
    ),
    (
        "DFS",
        "Depth-first: follows one path as deep as it can before backing "
        "up. Quick, but the path is usually long.",
    ),
    (
        "UCS",
        "Uniform-cost: always expands the cheapest path so far, so it "
        "finds the lowest total cost.",
    ),
    (
        "A*",
        "Like UCS, but guided by an estimate of the distance to the "
        "portal, so it usually expands fewer states.",
    ),
)
SOLVER_TIP = (
    "In a level, click a solver button at the bottom (or press 1 - 4) to "
    "watch it play. The card shows moves, expanded states, time and memory."
)
TILES = (
    ("goal", "Portal: stand upright on it to win"),
    ("fragile", "Fragile tile: breaks if you stand on it"),
    (SOFT, "Soft switch: any touch flips its bridges"),
    (HEAVY, "Heavy switch: only a standing block presses it"),
    (SPLITTER, "Split switch: splits the block into two cubes"),
    ("bridge", "Bridge: dashed when closed, solid when open"),
)
TILE_KINDS = {kind for kind, _ in TILES}
FADE = 22


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    note: str = ""
    level: int = 0


def _rgb(color: tuple[float, float, float]) -> tuple[int, int, int]:
    return tuple(round(c * 255) for c in color)


def level_title(index: int) -> str:
    return f"LEVEL {index + 1}"


def ui_font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont(FONT_NAMES, size, bold=bold)


def _spaced(font: pygame.font.Font, text: str, color, spacing: int):
    """Render text with extra room between the letters."""
    glyphs = [font.render(ch, True, color) for ch in text]
    width = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
    out = pygame.Surface((max(width, 1), font.get_height()), pygame.SRCALPHA)
    x = 0
    for glyph in glyphs:
        out.blit(glyph, (x, 0))
        x += glyph.get_width() + spacing
    return out


def label(font: pygame.font.Font, text: str, color, spacing: int = 0):
    """Text cropped to its visible pixels, so it can be centred exactly in a
    frame (the font box carries empty room for accents and descenders)."""
    surface = _spaced(font, text, color, spacing)
    return surface.subsurface(surface.get_bounding_rect()).copy()


def blit_centered(surface: pygame.Surface, text: pygame.Surface, rect) -> None:
    surface.blit(text, text.get_rect(center=pygame.Rect(rect).center))


def wrap(font: pygame.font.Font, text: str, width: int) -> list[str]:
    """Split text into lines no wider than `width` pixels."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and font.size(trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


def draw_frame(
    surface: pygame.Surface, rect: pygame.Rect, focused: bool, marker: bool = True
) -> None:
    """Rounded button body, with a soft halo (and a marker) when focused."""
    if focused:
        # Faint widening outlines make a soft halo around the button.
        for i in range(1, 7):
            pygame.draw.rect(
                surface,
                (*ACCENT, 60 - 9 * i),
                rect.inflate(2 * i, 2 * i),
                1,
                border_radius=RADIUS + i,
            )
    fill = BUTTON_FOCUS_BG if focused else BUTTON_BG
    pygame.draw.rect(surface, fill, rect, border_radius=RADIUS)
    edge = ACCENT if focused else BUTTON_EDGE
    pygame.draw.rect(surface, edge, rect, 2, border_radius=RADIUS)
    if focused and marker:
        bar = min(20, rect.height - 20)
        marker = (rect.x + 12, rect.centery - bar // 2, 4, bar)
        pygame.draw.rect(surface, WARM, marker, border_radius=2)


def _glow(surface: pygame.Surface, pad: int, blur: int) -> pygame.Surface:
    """Soft blurred copy of a surface, `pad` pixels bigger on every side."""
    w, h = surface.get_size()
    out = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    out.blit(surface, (pad, pad))
    size = out.get_size()
    small = pygame.transform.smoothscale(out, (size[0] // blur, size[1] // blur))
    return pygame.transform.smoothscale(small, size)


def _backdrop(width: int, height: int) -> pygame.Surface:
    """Dark fade on the left so the buttons stay readable over the stars."""
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    for x in range(SHADE_REACH):
        alpha = round(190 * (1 - x / SHADE_REACH) ** 1.6)
        pygame.draw.line(shade, (*SHADE, alpha), (x, 0), (x, height))
    return shade


def _neighbor(buttons: list[Button], index: int, dx: int, dy: int) -> int:
    """The closest button in a screen direction, preferring straight ahead."""
    x, y = buttons[index].rect.center
    best, best_score = index, None
    for i, button in enumerate(buttons):
        vx, vy = button.rect.centerx - x, button.rect.centery - y
        ahead = vx * dx + vy * dy
        if ahead <= 0:
            continue
        score = ahead + 2 * abs(vx * dy - vy * dx)
        if best_score is None or score < best_score:
            best, best_score = i, score
    return best


def _hit(buttons: list[Button], pos: tuple[int, int]) -> int | None:
    for i, button in enumerate(buttons):
        if button.rect.collidepoint(pos):
            return i
    return None


ARROWS = {
    pygame.K_UP: (0, -1),
    pygame.K_DOWN: (0, 1),
    pygame.K_LEFT: (-1, 0),
    pygame.K_RIGHT: (1, 0),
}
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


class Menu:
    """Start screen drawn over the 3D space scene: main page, level picker
    and how-to-play page. The app draws the slowly orbiting level preview."""

    def __init__(self, count: int, width: int, height: int):
        self.count = count
        self.width = width
        self.height = height
        self.level = 0
        self.page = MAIN
        self.focus = 0
        self.scroll = 0
        self.fonts = {
            "title": ui_font(92, bold=True),
            "tagline": ui_font(18),
            "heading": ui_font(40, bold=True),
            "button": ui_font(21, bold=True),
            "note": ui_font(15, bold=True),
            "cell": ui_font(19, bold=True),
            "small": ui_font(17),
            "section": ui_font(18, bold=True),
        }
        self._backdrop = _backdrop(width, height)
        self._help = self._help_content()
        self._cache: tuple | None = None
        self._surface: pygame.Surface | None = None

    def open(self, level: int) -> None:
        self.level = level
        self._go(MAIN)

    def preview(self) -> int:
        """Index of the level shown in 3D behind the menu."""
        if self.page == LEVELS and self.focus < self.count:
            return self.focus
        return self.level

    def _help_view(self) -> pygame.Rect:
        """Part of the help panel the text scrolls inside."""
        return pygame.Rect(HELP_PANEL).inflate(0, -2 * HELP_PAD)

    def max_scroll(self) -> int:
        return max(self._help.get_height() - self._help_view().height, 0)

    def scroll_by(self, pixels: int) -> None:
        self.scroll = min(max(self.scroll + pixels, 0), self.max_scroll())

    def buttons(self) -> list[Button]:
        if self.page == MAIN:
            items = (
                ("PLAY", PLAY, f"LEVEL {self.level + 1}"),
                ("SELECT LEVEL", LEVELS, ""),
                ("HOW TO PLAY", HELP, ""),
                ("QUIT", QUIT, ""),
            )
            return [
                Button(
                    pygame.Rect(
                        LEFT, MAIN_TOP + i * (BUTTON_H + BUTTON_GAP), BUTTON_W, BUTTON_H
                    ),
                    label,
                    action,
                    note,
                )
                for i, (label, action, note) in enumerate(items)
            ]
        buttons = []
        if self.page == LEVELS:
            for i in range(self.count):
                row, col = divmod(i, GRID_COLS)
                rect = pygame.Rect(
                    LEFT + col * (CELL_W + CELL_GAP),
                    GRID_TOP + row * (CELL_H + CELL_GAP),
                    CELL_W,
                    CELL_H,
                )
                buttons.append(Button(rect, level_title(i), "level", level=i))
        back = pygame.Rect(LEFT, BACK_TOP, BUTTON_W, BUTTON_H)
        buttons.append(Button(back, "BACK", "back"))
        return buttons

    def handle(self, event: pygame.event.Event) -> str | None:
        buttons = self.buttons()
        if event.type == pygame.MOUSEMOTION:
            hit = _hit(buttons, event.pos)
            if hit is not None:
                self.focus = hit
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = _hit(buttons, event.pos)
            if hit is not None:
                self.focus = hit
                return self._press(buttons[hit])
        elif event.type == pygame.MOUSEWHEEL and self.page == HELP:
            self.scroll_by(-event.y * SCROLL_STEP)
        elif event.type == pygame.KEYDOWN:
            if self.page == HELP and event.key in (pygame.K_UP, pygame.K_DOWN):
                self.scroll_by(SCROLL_STEP * ARROWS[event.key][1])
            elif event.key in CONFIRM_KEYS:
                return self._press(buttons[self.focus])
            if event.key == pygame.K_ESCAPE:
                if self.page == MAIN:
                    return QUIT
                self._back()
            elif event.key in ARROWS:
                self.focus = _neighbor(buttons, self.focus, *ARROWS[event.key])
        return None

    def _go(self, page: str, focus: int = 0) -> None:
        self.page = page
        self.focus = focus

    def _back(self) -> None:
        self._go(MAIN, 1 if self.page == LEVELS else 2)

    def _press(self, button: Button) -> str | None:
        if button.action in (PLAY, QUIT):
            return button.action
        if button.action == "level":
            self.level = button.level
            return PLAY
        if button.action == "back":
            self._back()
        elif button.action == LEVELS:
            self._go(LEVELS, self.level)
        elif button.action == HELP:
            self._go(HELP, 0)
            self.scroll = 0
        return None

    def draw(self) -> None:
        key = (self.page, self.focus, self.level, self.scroll)
        if key != self._cache:
            self._surface = self._render()
            self._cache = key
        scene.draw_surface(self._surface, 0, 0, self.height)

    def _render(self) -> pygame.Surface:
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        surface.blit(self._backdrop, (0, 0))
        if self.page == MAIN:
            self._draw_title(surface)
            hint = "Arrows: choose   Enter: confirm   Esc: quit"
        else:
            title = "SELECT LEVEL" if self.page == LEVELS else "HOW TO PLAY"
            self._draw_heading(surface, title)
            hint = "Arrows: choose   Enter: confirm   Esc: back"
            if self.page == HELP:
                hint = "Wheel / Up / Down: scroll   Enter / Esc: back"
        if self.page == HELP:
            self._draw_help(surface)
        for i, button in enumerate(self.buttons()):
            if button.action == "level":
                self._draw_cell(surface, button, i == self.focus)
            else:
                self._draw_button(surface, button, i == self.focus)
        footer = self.fonts["small"].render(hint, True, DIM)
        pill = footer.get_rect(topleft=(LEFT, self.height - 36)).inflate(20, 8)
        pygame.draw.rect(surface, PANEL_BG, pill, border_radius=pill.height // 2)
        surface.blit(footer, (LEFT, self.height - 36))
        return surface

    def _draw_title(self, surface: pygame.Surface) -> None:
        title = _spaced(self.fonts["title"], TITLE, TEXT, 8)
        glow = _glow(_spaced(self.fonts["title"], TITLE, ACCENT, 8), 24, 6)
        top = 74
        for _ in range(2):
            surface.blit(glow, (LEFT - 24, top - 24))
        surface.blit(title, (LEFT, top))
        y = top + title.get_height() + 4
        pygame.draw.rect(surface, WARM, (LEFT + 2, y + 8, 36, 3), border_radius=1)
        tagline = _spaced(self.fonts["tagline"], TAGLINE, WARM, 4)
        surface.blit(tagline, (LEFT + 50, y))

    def _draw_heading(self, surface: pygame.Surface, text: str) -> None:
        heading = _spaced(self.fonts["heading"], text, TEXT, 4)
        glow = _glow(_spaced(self.fonts["heading"], text, ACCENT, 4), 16, 5)
        surface.blit(glow, (LEFT - 16, 70 - 16))
        surface.blit(heading, (LEFT, 70))

    def _draw_button(self, surface: pygame.Surface, button: Button, focused: bool):
        rect = button.rect
        draw_frame(surface, rect, focused)
        text = label(
            self.fonts["button"], button.label, TEXT if focused else SOFT_TEXT, 3
        )
        surface.blit(text, text.get_rect(midleft=(rect.x + 32, rect.centery)))
        if button.note:
            note = label(self.fonts["note"], button.note, WARM, 2)
            surface.blit(note, note.get_rect(midright=(rect.right - 18, rect.centery)))

    def _draw_cell(self, surface: pygame.Surface, button: Button, focused: bool):
        rect = button.rect
        draw_frame(surface, rect, focused)
        color = TEXT if focused else SOFT_TEXT
        blit_centered(surface, label(self.fonts["cell"], button.label, color, 2), rect)
        if button.level == self.level:
            # The level PLAY would start.
            pygame.draw.circle(surface, WARM, (rect.right - 14, rect.y + 14), 4)

    def _help_content(self) -> pygame.Surface:
        """The whole how-to-play text, taller than the panel; it scrolls."""
        small, section = self.fonts["small"], self.fonts["section"]
        width = HELP_PANEL[2] - 2 * HELP_PAD - 16
        line = small.get_linesize()
        blocks: list[tuple] = []

        def heading(text: str) -> None:
            blocks.append(("heading", text))

        def row(key, text: str, indent: int) -> None:
            blocks.append(("row", key, wrap(small, text, width - indent), indent))

        heading("CONTROLS")
        for key, text in CONTROLS:
            row(key, text, HELP_KEY_W)
        heading("TILES")
        for kind, text in TILES:
            row(kind, text, 36)
        heading("AI SOLVERS")
        for key, text in SOLVER_NOTES:
            row(key, text, 56)
        blocks.append(("row", None, wrap(small, SOLVER_TIP, width), 0))

        def height(block) -> int:
            if block[0] == "heading":
                return 40
            return len(block[2]) * line + 10

        out = pygame.Surface((width, sum(map(height, blocks)) - 10), pygame.SRCALPHA)
        y = 0
        for i, block in enumerate(blocks):
            if block[0] == "heading":
                top = y + (12 if i else 0)
                out.blit(label(section, block[1], WARM, 2), (0, top))
            else:
                _, key, lines, indent = block
                if key in TILE_KINDS:
                    _tile_icon(out, key, (10, y + line // 2))
                elif key is not None:
                    out.blit(small.render(key, True, ACCENT), (0, y))
                for j, text in enumerate(lines):
                    color = TEXT if key is not None else DIM
                    out.blit(small.render(text, True, color), (indent, y + j * line))
            y += height(block)
        return out

    def _draw_help(self, surface: pygame.Surface) -> None:
        panel = pygame.Rect(HELP_PANEL)
        pygame.draw.rect(surface, PANEL_BG, panel, border_radius=RADIUS)
        pygame.draw.rect(surface, BUTTON_EDGE, panel, 1, border_radius=RADIUS)
        view = self._help_view()
        content = self._help
        visible = min(view.height, content.get_height())
        part = content.subsurface((0, self.scroll, content.get_width(), visible))
        surface.blit(part, (panel.x + HELP_PAD, view.y))
        limit = self.max_scroll()
        if limit == 0:
            return
        track = pygame.Rect(panel.right - 14, view.y, 4, view.height)
        pygame.draw.rect(surface, (*BUTTON_EDGE, 120), track, border_radius=2)
        thumb_h = max(round(track.height * view.height / content.get_height()), 24)
        thumb_y = track.y + round((track.height - thumb_h) * self.scroll / limit)
        thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
        pygame.draw.rect(surface, ACCENT, thumb, border_radius=2)
        for edge, more in (
            (view.top, self.scroll > 0),
            (view.bottom, self.scroll < limit),
        ):
            if more:
                _fade_edge(surface, panel, edge, edge == view.top)


class Banner:
    """Big caption in the middle of the game view, e.g. LEVEL CLEAR."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.title_font = ui_font(64, bold=True)
        self.subtitle_font = ui_font(22)
        self._key: tuple[str, str] | None = None
        self._surface: pygame.Surface | None = None

    def draw(self, title: str, subtitle: str, alpha: float) -> None:
        if alpha <= 0:
            return
        if (title, subtitle) != self._key:
            self._surface = self._render(title, subtitle)
            self._key = (title, subtitle)
        surface = self._surface
        if alpha < 1:
            surface = surface.copy()
            fade = (255, 255, 255, round(255 * alpha))
            surface.fill(fade, special_flags=pygame.BLEND_RGBA_MULT)
        x = (self.width - surface.get_width()) // 2
        y = (self.height - surface.get_height()) // 2 - 60
        scene.draw_surface(surface, x, y, self.height)

    def _render(self, title: str, subtitle: str) -> pygame.Surface:
        text = _spaced(self.title_font, title, TEXT, 8)
        glow = _glow(_spaced(self.title_font, title, ACCENT, 8), 24, 6)
        sub = _spaced(self.subtitle_font, subtitle, WARM, 5)
        if not subtitle:
            sub = pygame.Surface((1, 0), pygame.SRCALPHA)
        width = glow.get_width()
        size = (width, glow.get_height() + sub.get_height())
        out = pygame.Surface(size, pygame.SRCALPHA)
        band = pygame.Rect(0, 12, width, size[1] - 12)
        pygame.draw.rect(out, (*SHADE, 150), band, border_radius=band.height // 2)
        out.blit(glow, (0, 0))
        out.blit(glow, (0, 0))
        out.blit(text, (24, 24))
        out.blit(sub, ((width - sub.get_width()) // 2, text.get_height() + 28))
        return out


def _fade_edge(surface: pygame.Surface, panel: pygame.Rect, y: int, top: bool):
    """Darken a band of the panel towards one edge of the scrolling text."""
    band = pygame.Surface((panel.width - 24, FADE), pygame.SRCALPHA)
    for i in range(FADE):
        strength = 1 - i / FADE if top else (i + 1) / FADE
        pygame.draw.line(
            band, (*SHADE, round(230 * strength)), (0, i), (band.get_width(), i)
        )
    surface.blit(band, (panel.x + 2, y if top else y - FADE))


def _tile_icon(surface: pygame.Surface, kind: str, center: tuple[int, int]) -> None:
    """Small 2D copies of the markers drawn on the 3D board."""
    x, y = center
    if kind == "goal":
        pygame.draw.circle(surface, _rgb(scene.PORTAL_COLORS[0]), center, 10, 3)
        pygame.draw.circle(surface, _rgb(scene.PORTAL_COLORS[1]), center, 5, 2)
    elif kind == "fragile":
        rect = pygame.Rect(x - 9, y - 9, 18, 18)
        pygame.draw.rect(surface, _rgb(scene.FRAGILE_GLOW), rect, border_radius=3)
    elif kind == SOFT:
        pygame.draw.circle(surface, _rgb(scene.SWITCH_GLOW[SOFT]), center, 9, 3)
    elif kind == HEAVY:
        color = _rgb(scene.SWITCH_GLOW[HEAVY])
        pygame.draw.line(surface, color, (x - 8, y - 8), (x + 8, y + 8), 4)
        pygame.draw.line(surface, color, (x - 8, y + 8), (x + 8, y - 8), 4)
    elif kind == SPLITTER:
        color = _rgb(scene.SWITCH_GLOW[SPLITTER])
        pygame.draw.arc(surface, color, (x - 10, y - 10, 12, 20), 1.9, 4.4, 3)
        pygame.draw.arc(surface, color, (x - 2, y - 10, 12, 20), -1.25, 1.25, 3)
    elif kind == "bridge":
        rect = pygame.Rect(x - 9, y - 9, 18, 18)
        pygame.draw.rect(surface, _rgb(scene.BRIDGE_GLOW), rect, 2, border_radius=2)
