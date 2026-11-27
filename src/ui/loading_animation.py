import pygame
import time
import threading
from pygame.locals import *
from OpenGL.GL import *
from utils.path_helper import resource_path
from src.rendering import display_manager
from src.rendering import hdr as hdr_output
from src.ui import ui_style as ui

""" Puts the application in the taskbar with a custom icon on Windows."""
import ctypes
myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


class LoadingAnimation:
    def __init__(self, mode="windowed", display_index=0, size=(1280, 720), hdr=False,
                 paper_white=hdr_output.PAPER_WHITE_DEFAULT):
        # Set caption and icon before the window appears
        pygame.display.set_caption("Rubik's Cube Simulator")
        try:
            pygame.display.set_icon(pygame.image.load(resource_path("utils/rubiksCube_Icon.ico")))
        except Exception:
            print("Icon not found")

        # Create the final window right away so Game can reuse the OpenGL context
        self.screen = display_manager.open_window(mode, display_index, size, hdr=hdr)
        self.width, self.height = self.screen.get_size()
        ui.set_screen(self.width, self.height)
        self.hdr_presenter = hdr_output.create_presenter(self.width, self.height, paper_white) if hdr else None

        glViewport(0, 0, self.width, self.height)
        glClearColor(*(c / 255 for c in ui.BG), 1.0)
        glDisable(GL_DEPTH_TEST)

        self.clock = pygame.time.Clock()

        # Loading state
        self.loading_complete = False
        self.min_display_time = 3.2
        self.start_time = time.time()
        self.loading_progress = 0.0  # 0.0 to 1.0
        self.shown_progress = 0.0    # eased value used for drawing
        self.current_step = 0

        # Loading steps with descriptions
        self.loading_steps = [
            "Initializing OpenGL",
            "Loading cube model",
            "Loading textures",
            "Loading sound effects",
            "Loading soundtrack",
            "Setting up renderer",
            "Preparing game engine",
            "Finalizing setup",
            "Ready",
        ]

    def preload_game_resources(self):
        """Step through the loading stages in a background thread"""
        total_steps = len(self.loading_steps) - 1  # last step is "Ready"
        for i in range(total_steps):
            self.current_step = i
            if i == 0:
                time.sleep(0.5)
            elif i in (1, 2, 3, 4):
                time.sleep(0.4)
            else:
                time.sleep(0.3)
            self.loading_progress = (i + 1) / total_steps
        self.current_step = total_steps
        self.loading_progress = 1.0
        time.sleep(0.4)
        self.loading_complete = True

    def update(self):
        elapsed = time.time() - self.start_time
        can_exit = self.loading_complete and elapsed >= self.min_display_time

        # Ease the drawn progress toward the real progress
        self.shown_progress += (self.loading_progress - self.shown_progress) * 0.12

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        return not can_exit

    def _draw(self, surface):
        surface.fill(ui.BG)
        w, h = self.width, self.height
        elapsed = time.time() - self.start_time
        t = min(1.0, elapsed / 0.7)
        alpha = int(255 * (1 - (1 - t) ** 3))  # ease-out fade in

        layer = pygame.Surface((w, h), pygame.SRCALPHA)

        # Layout: progress cube, game logo, progress bar and step, centered as one block
        edge = ui.px(74)
        logo = ui.logo("rubiks_logo_text", ui.px(560), ui.px(210))
        logo_h = logo.get_height() if logo else 0
        small = ui.body_font(ui.SIZE_SMALL)
        bar_h = max(3, ui.px(6))
        block_h = 2 * edge + ui.px(36) + logo_h + ui.px(32) + bar_h + ui.px(14) + small.get_height()
        top = (h - block_h) // 2

        # Signature cube: facelets light up as loading progresses
        lit = int(round(self.shown_progress * 27))
        ui.cube_mark(layer, (w // 2, top + edge), edge, lit=lit, rounded=True,
                     colors=(ui.FACE["yellow"], ui.FACE["green"], ui.FACE["red"]))  # same faces as the logo cube

        # Game logo (the text of utils/rubiks_logo.png)
        logo_y = top + 2 * edge + ui.px(36)
        if logo:
            layer.blit(logo, logo.get_rect(midtop=(w // 2, logo_y)))

        # Progress bar
        bar_w = ui.px(360)
        bar = pygame.Rect(w // 2 - bar_w // 2, logo_y + logo_h + ui.px(32), bar_w, bar_h)
        ui.progress_bar(layer, bar, self.shown_progress)

        # Current step and percentage
        step = self.loading_steps[min(self.current_step, len(self.loading_steps) - 1)]
        ui.draw_text(layer, step, small, ui.MUTED, (bar.left, bar.bottom + ui.px(14)), "topleft")
        ui.draw_text(layer, f"{int(self.shown_progress * 100 + 0.5)}%", ui.mono_font(ui.SIZE_SMALL),
                     ui.MUTED, (bar.right, bar.bottom + ui.px(14)), "topright")

        layer.set_alpha(alpha)
        surface.blit(layer, (0, 0))

    def render(self):
        if self.hdr_presenter:
            self.hdr_presenter.begin()
        glClear(GL_COLOR_BUFFER_BIT)

        surface = pygame.Surface((self.width, self.height))
        self._draw(surface)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        texture_data = pygame.image.tostring(surface, 'RGB', True)
        glRasterPos2f(0, self.height)
        glDrawPixels(self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE, texture_data)

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        if self.hdr_presenter:
            self.hdr_presenter.end()
        pygame.display.flip()
        self.clock.tick(60)

    def run(self):
        loading_thread = threading.Thread(target=self.preload_game_resources, daemon=True)
        loading_thread.start()

        while self.update():
            self.render()

        while not self.loading_complete:
            self.render()

        # The game creates its own HDR presenter in the same window
        if self.hdr_presenter:
            self.hdr_presenter.delete()
            self.hdr_presenter = None
        return True
