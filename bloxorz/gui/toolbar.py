from dataclasses import dataclass

import pygame

from bloxorz.gui import scene
from bloxorz.gui.menu import (
    ACCENT,
    BUTTON_EDGE,
    DIM,
    PANEL_BG,
    RADIUS,
    SOFT_TEXT,
    TEXT,
    WARM,
    Button,
    blit_centered,
    draw_frame,
    label,
    ui_font,
)
from bloxorz.gui.solving import Measured

RESTART = "restart"
MENU = "menu"

MARGIN = 16
BAR_H = 40
GAP = 10
CARD_W = 236
CARD_ROW = 22


@dataclass
class Replay:
    """A solver's answer for the current level, played back move by move."""

    solver: str
    measured: Measured | None
    played: int = 0
    wait: float = 0.0

    @property
    def path(self) -> list[str]:
        if self.measured is None:
            return []
        return self.measured.result.path or []

    @property
    def done(self) -> bool:
        return self.played >= len(self.path)


def _size(num_bytes: int) -> str:
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / 1024 / 1024:.2f} MB"


def _time(seconds: float) -> str:
    return f"{seconds * 1000:.1f} ms" if seconds < 1 else f"{seconds:.2f} s"


class Toolbar:
    """Buttons along the bottom of the game view, plus a card with the stats
    of the last solver run."""

    def __init__(self, solvers: list[str], width: int, height: int):
        self.width = width
        self.height = height
        self.hover: int | None = None
        self.font = ui_font(16, bold=True)
        self.small = ui_font(16)
        self.top = height - MARGIN - BAR_H
        self.buttons = self._layout(solvers)
        self._bar_key: tuple | None = None
        self._bar: pygame.Surface | None = None
        self._card_key: tuple | None = None
        self._card: pygame.Surface | None = None

    def _layout(self, solvers: list[str]) -> list[Button]:
        buttons = []
        x = MARGIN
        for text, action, w in (("RESTART", RESTART, 128), ("MENU", MENU, 96)):
            buttons.append(Button(pygame.Rect(x, self.top, w, BAR_H), text, action))
            x += w + GAP
        w = 76
        x = self.width - MARGIN - len(solvers) * (w + GAP) + GAP
        for name in solvers:
            buttons.append(Button(pygame.Rect(x, self.top, w, BAR_H), name, name))
            x += w + GAP
        return buttons

    def hit(self, pos: tuple[int, int]) -> str | None:
        for button in self.buttons:
            if button.rect.collidepoint(pos):
                return button.action
        return None

    def point(self, pos: tuple[int, int]) -> None:
        self.hover = None
        for i, button in enumerate(self.buttons):
            if button.rect.collidepoint(pos):
                self.hover = i

    def draw(self, replay: Replay | None, solving: str | None = None) -> None:
        key = (self.hover, solving)
        if key != self._bar_key:
            self._bar = self._render_bar(solving)
            self._bar_key = key
        y = self.top - MARGIN
        scene.draw_surface(self._bar, 0, y, self.height)
        if replay is None:
            return
        key = (id(replay), replay.played)
        if key != self._card_key:
            self._card = self._render_card(replay)
            self._card_key = key
        x = self.width - MARGIN - CARD_W
        y = self.top - GAP - self._card.get_height()
        scene.draw_surface(self._card, x, y, self.height)

    def _render_bar(self, solving: str | None) -> pygame.Surface:
        out = pygame.Surface((self.width, BAR_H + 2 * MARGIN), pygame.SRCALPHA)
        first_solver = self.buttons[2].rect
        caption = label(self.small, "AI SOLVE", DIM, 2)
        right = first_solver.x - 12
        out.blit(caption, caption.get_rect(midright=(right, MARGIN + BAR_H // 2)))
        for i, button in enumerate(self.buttons):
            rect = button.rect.move(0, MARGIN - self.top)
            focused = i == self.hover or button.action == solving
            # Small buttons: the halo alone marks focus, the label stays centred.
            draw_frame(out, rect, focused, marker=False)
            color = TEXT if focused else SOFT_TEXT
            blit_centered(out, label(self.font, button.label, color, 2), rect)
        return out

    def _render_card(self, replay: Replay) -> pygame.Surface:
        measured = replay.measured
        if measured is None:
            return self._render_missing(replay)
        result = measured.result
        rows = [
            ("Moves", str(result.length) if result.found else "-"),
            ("Cost", f"{result.cost:g}" if result.found else "-"),
            ("Expanded", f"{result.expanded:,}"),
            ("Time", _time(measured.seconds)),
            ("Memory", _size(measured.peak_bytes)),
        ]
        height = 52 + len(rows) * CARD_ROW + 30
        out = pygame.Surface((CARD_W, height), pygame.SRCALPHA)
        rect = out.get_rect()
        pygame.draw.rect(out, PANEL_BG, rect, border_radius=RADIUS)
        pygame.draw.rect(out, BUTTON_EDGE, rect, 1, border_radius=RADIUS)
        title = label(self.font, f"{replay.solver} SOLUTION", WARM, 2)
        out.blit(title, (18, 18))
        y = 44
        for name, value in rows:
            out.blit(self.small.render(name, True, DIM), (18, y))
            text = self.small.render(value, True, TEXT)
            out.blit(text, (CARD_W - 18 - text.get_width(), y))
            y += CARD_ROW
        # Progress bar for the playback.
        y += 10
        track = pygame.Rect(18, y, CARD_W - 36, 6)
        if not result.found:
            note = self.small.render("No solution found", True, WARM)
            out.blit(note, (18, y - 6))
            return out
        pygame.draw.rect(out, (*BUTTON_EDGE, 140), track, border_radius=3)
        if replay.path:
            fill = track.copy()
            fill.width = round(track.width * replay.played / len(replay.path))
            if fill.width:
                pygame.draw.rect(out, ACCENT, fill, border_radius=3)
        return out

    def _render_missing(self, replay: Replay) -> pygame.Surface:
        out = pygame.Surface((CARD_W, 92), pygame.SRCALPHA)
        rect = out.get_rect()
        pygame.draw.rect(out, PANEL_BG, rect, border_radius=RADIUS)
        pygame.draw.rect(out, BUTTON_EDGE, rect, 1, border_radius=RADIUS)
        out.blit(label(self.font, f"{replay.solver} SOLVER", WARM, 2), (18, 18))
        for i, text in enumerate(("Not added yet,", "coming soon.")):
            out.blit(self.small.render(text, True, DIM), (18, 44 + i * CARD_ROW))
        return out
