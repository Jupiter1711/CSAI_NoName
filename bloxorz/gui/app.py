from collections.abc import Callable
from pathlib import Path

import pygame

from bloxorz.core.level import Level, load_level
from bloxorz.core.rules import initial_state
from bloxorz.core.state import State
from bloxorz.gui import scene
from bloxorz.gui.anim import Motion, Wave
from bloxorz.gui.camera import FLIGHT_TIME, Camera, Flight, clamp, smoothstep
from bloxorz.gui.game import LOST, PLAYING, WON, GameSession
from bloxorz.gui.menu import PLAY, QUIT, Banner, Menu, level_title
from bloxorz.gui.solving import SOLVERS
from bloxorz.gui.solving import run as run_solver
from bloxorz.gui.space import Space
from bloxorz.gui.toolbar import MENU as MENU_BUTTON
from bloxorz.gui.toolbar import RESTART, Replay, Toolbar

WIDTH, HEIGHT = 960, 640
FPS = 60
LEVEL_DIR = Path(__file__).resolve().parents[2] / "levels"

MENU = "menu"
GAME = "game"
MENU_SHIFT = 0.42
MENU_PITCH = 40.0
MENU_ORBIT = 7.0
MENU_DISTANCE = 1.4
CLEAR_PAUSE = 1.0
DIVE_TIME = 1.1
DIVE_DISTANCE = 1.2
DIVE_PITCH = 85.0
ARRIVE_ZOOM = 2.6
ARRIVE_PITCH = 80.0
ARRIVE_TURN = 70.0
FADE_OUT = "out"
FADE_IN = "in"
REPLAY_PAUSE = 0.12
MAX_DT = 0.1

KEYS = {
    pygame.K_UP: "U",
    pygame.K_DOWN: "D",
    pygame.K_LEFT: "L",
    pygame.K_RIGHT: "R",
}
SOLVER_KEYS = dict(zip((pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4), SOLVERS))


def status_text(session: GameSession, index: int) -> str:
    return f"Level {index + 1}   Moves: {session.moves}"


def menu_camera(level: Level, time: float) -> Camera:
    camera = Camera.for_level(level.rows, level.cols)
    camera.yaw = time * MENU_ORBIT
    camera.pitch = MENU_PITCH
    camera.distance *= MENU_DISTANCE
    return camera


def draw_world(
    camera: Camera,
    view: scene.LevelView,
    space: Space,
    state: State,
    selected: int,
    motion: Motion | None,
    time: float,
    wave: Wave | None = None,
) -> None:
    level = view.level
    span = max(level.rows, level.cols)
    scene.begin_frame(camera, *space.lights(camera.target, span))
    space.draw_background(camera, time)
    space.draw_bodies(camera, camera.target, span, time)
    rolling = motion is not None and motion.rolling
    bridges = motion.bridges if rolling else state.bridges
    lifts = wave.lifts() if wave is not None else None
    view.draw_solid(bridges, lifts)
    block_lift = 0.0 if lifts is None else lifts.get(state.cells[0])
    if motion is not None:
        scene.draw_motion(motion, lifts)
    elif block_lift is not None:
        scene.draw_state(state, selected, block_lift)
    view.draw_glow(bridges, time, lifts)


class App:
    def __init__(self, levels: list[Level]):
        self.levels = levels
        self.space = Space.load(scene.sprites())
        self.font = pygame.font.SysFont(None, 24)
        self.menu = Menu(len(levels), WIDTH, HEIGHT)
        self.banner = Banner(WIDTH, HEIGHT)
        self.toolbar = Toolbar(list(SOLVERS), WIDTH, HEIGHT)
        self.replay: Replay | None = None
        self.mode = MENU
        self.index = 0
        self.view: scene.LevelView | None = None
        self.session = GameSession(levels[0])
        self.camera = Camera.for_level(levels[0].rows, levels[0].cols)
        self.motion: Motion | None = None
        self.wave: Wave | None = None
        self.flight: Flight | None = None
        self.fade: str | None = None
        self.on_landed: Callable[[], None] | None = None
        self.cleared = 0.0
        self.dragging = False
        self.running = True

    def level_view(self, index: int) -> scene.LevelView:
        level = self.levels[index]
        if self.view is None or self.view.level is not level:
            if self.view is not None:
                self.view.release()
            self.view = scene.LevelView(level)
        return self.view

    def load(self, index: int) -> None:
        self.index = index
        level = self.levels[index]
        self.session = GameSession(level)
        self.camera = Camera.for_level(level.rows, level.cols)
        self.motion = None
        self.wave = None
        self.cleared = 0.0
        self.replay = None

    def tiles(self) -> list[tuple[int, int]]:
        return [(r, c) for r, c, _ in self.level_view(self.index).cells]

    def restart(self, rebuild: bool) -> None:
        self.session.restart()
        self.motion = None
        self.cleared = 0.0
        self.replay = None
        self.wave = Wave.build(self.tiles()) if rebuild else None

    def retry(self) -> None:
        self.restart(rebuild=self.session.status == LOST or self.wave is not None)

    def roll(self, direction: str) -> None:
        session = self.session
        state, selected = session.state, session.selected
        session.move(direction)
        falls = session.status == LOST
        sinks = session.status == WON
        self.motion = Motion.start(state, selected, direction, falls, sinks)

    def solve(self, name: str) -> None:
        """Run a solver from the start of the level, then play its answer."""
        if self.session.status == WON:
            return
        self.draw(solving=name)
        pygame.display.flip()
        measured = run_solver(name, self.session.level)
        self.retry()
        self.replay = Replay(name, measured)

    def play_replay(self, dt: float) -> None:
        replay = self.replay
        ready = self.wave is None and self.settled()
        if replay.done or not ready or self.session.status != PLAYING:
            return
        replay.wait += dt
        if replay.wait < REPLAY_PAUSE:
            return
        replay.wait = 0.0
        action = replay.path[replay.played]
        replay.played += 1
        if len(action) == 2:
            self.session.selected = int(action[0]) - 1
            action = action[1]
        self.roll(action)

    def press(self, action: str) -> None:
        if action == RESTART:
            self.retry()
        elif action == MENU_BUTTON:
            self.back_to_menu()
        else:
            self.solve(action)

    def fly(
        self,
        flight: Flight,
        fade: str | None = None,
        on_landed: Callable[[], None] | None = None,
    ) -> None:
        self.flight = flight
        self.fade = fade
        self.on_landed = on_landed
        self.dragging = False

    def start_game(self, index: int) -> None:
        self.load(index)
        now = pygame.time.get_ticks() / 1000
        start = menu_camera(self.levels[index], now)
        self.fly(Flight(start, self.camera, MENU_SHIFT, 0.0))
        self.mode = GAME

    def back_to_menu(self, level: int | None = None) -> None:
        self.menu.open(self.index if level is None else level)
        later = pygame.time.get_ticks() / 1000 + FLIGHT_TIME
        end = menu_camera(self.levels[self.menu.level], later)
        self.fly(Flight(self.camera, end, 0.0, MENU_SHIFT), on_landed=self.enter_menu)

    def enter_menu(self) -> None:
        self.mode = MENU
        self.motion = None
        self.wave = None

    def next_level(self) -> None:
        index = self.index + 1
        if index == len(self.levels):
            self.back_to_menu(0)
            return
        r, c = self.session.level.goal
        cam = self.camera
        portal = Camera((c + 0.5, 0.0, r + 0.5), DIVE_DISTANCE, cam.yaw, DIVE_PITCH)
        flight = Flight(cam, portal, duration=DIVE_TIME)
        self.fly(flight, FADE_OUT, lambda: self.arrive(index))

    def arrive(self, index: int) -> None:
        self.load(index)
        self.wave = Wave.build(self.tiles(), wait=FLIGHT_TIME / 2)
        end = self.camera
        start = Camera(
            end.target, end.distance * ARRIVE_ZOOM, end.yaw + ARRIVE_TURN, ARRIVE_PITCH
        )
        self.fly(Flight(start, end), FADE_IN)

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = min(clock.tick(FPS) / 1000, MAX_DT)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif self.flight is not None:
                    continue
                elif self.mode == MENU:
                    self.menu_event(event)
                else:
                    self.game_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def menu_event(self, event: pygame.event.Event) -> None:
        action = self.menu.handle(event)
        if action == PLAY:
            self.start_game(self.menu.level)
        elif action == QUIT:
            self.running = False

    def game_event(self, event: pygame.event.Event) -> None:
        session, motion = self.session, self.motion
        busy = (motion is not None and not motion.done) or self.wave is not None
        busy = busy or (self.replay is not None and not self.replay.done)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            action = self.toolbar.hit(event.pos)
            if action is None:
                self.dragging = True
            else:
                self.press(action)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            self.toolbar.point(event.pos)
            if self.dragging:
                self.camera.orbit(*event.rel)
        elif event.type == pygame.MOUSEWHEEL:
            self.camera.zoom(event.y)
        elif event.type == pygame.KEYDOWN:
            if event.key in KEYS:
                if busy or session.status != PLAYING:
                    return
                self.roll(self.camera.world_direction(KEYS[event.key]))
            elif event.key == pygame.K_SPACE and not busy:
                session.switch_cube()
            elif event.key in SOLVER_KEYS:
                self.solve(SOLVER_KEYS[event.key])
            elif event.key == pygame.K_r:
                self.retry()
            elif event.key == pygame.K_n:
                self.load((self.index + 1) % len(self.levels))
                self.wave = Wave.build(self.tiles())
            elif event.key == pygame.K_ESCAPE:
                self.back_to_menu()

    def update(self, dt: float) -> None:
        if self.flight is not None:
            self.flight.advance(dt)
            if self.flight.done:
                landed = self.on_landed
                self.flight, self.fade, self.on_landed = None, None, None
                if landed is not None:
                    landed()
        if self.motion is not None:
            self.motion.advance(dt)
            if self.motion.done and not self.motion.finished_game:
                self.motion = None
        if self.wave is not None:
            self.wave.advance(dt)
            if self.wave.done:
                if self.wave.building:
                    self.wave = None
                else:
                    self.restart(rebuild=True)
        if self.mode != GAME or self.flight is not None:
            return
        if self.won():
            self.cleared += dt
            if self.cleared >= CLEAR_PAUSE:
                self.next_level()
        elif self.fell() and self.wave is None:
            self.wave = Wave.collapse(self.tiles())
        elif self.replay is not None:
            self.play_replay(dt)

    def settled(self) -> bool:
        return self.motion is None or self.motion.done

    def won(self) -> bool:
        """Won, and the block has finished sinking into the portal."""
        return self.session.status == WON and self.settled()

    def fell(self) -> bool:
        """Lost, and the block has finished falling out of sight."""
        return self.session.status == LOST and self.settled()

    def shade(self) -> float:
        if self.flight is None or self.fade is None:
            return 0.0
        t = self.flight.progress
        if self.fade == FADE_OUT:
            return smoothstep(clamp(t * 2 - 1, 0.0, 1.0))
        return 1 - smoothstep(clamp(t * 2, 0.0, 1.0))

    def draw(self, solving: str | None = None) -> None:
        time = pygame.time.get_ticks() / 1000
        if self.mode == MENU:
            index = self.menu.preview()
            level = self.levels[index]
            camera, shift = menu_camera(level, time), MENU_SHIFT
            state, selected, motion = initial_state(level), 0, None
        else:
            index = self.index
            camera, shift = self.camera, 0.0
            state, selected = self.session.state, self.session.selected
            motion = self.motion
        if self.flight is not None:
            camera, shift = self.flight.pose()
        scene.set_projection(WIDTH, HEIGHT, shift)
        wave = self.wave if self.mode == GAME else None
        view = self.level_view(index)
        draw_world(camera, view, self.space, state, selected, motion, time, wave)
        shade = self.shade()
        if shade > 0:
            scene.draw_shade(shade, WIDTH, HEIGHT)
        if self.mode == MENU:
            self.menu.draw()
            return
        if self.flight is None or self.fade == FADE_OUT:
            if self.won():
                moves = f"{self.session.moves} MOVES"
                self.banner.draw("LEVEL CLEAR", moves, 1 - shade)
        elif self.on_landed is None:
            t = self.flight.progress
            fade = 1 - smoothstep(clamp(t * 2.5 - 1.5, 0.0, 1.0))
            self.banner.draw(level_title(self.index), "", fade)
        if self.flight is None:
            lines = [status_text(self.session, self.index)]
            scene.draw_hud(lines, self.font, WIDTH, HEIGHT)
            self.toolbar.draw(self.replay, solving)
        if solving is not None:
            self.banner.draw("SOLVING", f"{solving} SEARCH", 1.0)


def run(level_paths: list[Path]) -> None:
    pygame.init()
    pygame.display.set_caption("Bloxorz 3D")
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF | pygame.OPENGL)
    scene.init(WIDTH, HEIGHT)
    App([load_level(path) for path in level_paths]).run()
    pygame.quit()


def main() -> None:
    level_paths = sorted(LEVEL_DIR.glob("*.json"))
    if not level_paths:
        raise SystemExit(f"No level files (*.json) found in {LEVEL_DIR}")
    run(level_paths)
