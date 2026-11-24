import pygame
from src.rendering.renderer import Renderer
from src.rendering import display_manager
from src.rendering import hdr as hdr_output
from src.rendering import graphics
from src.rendering import backgrounds
from src.ui import ui_style as ui
from utils.path_helper import resource_path


class DisplayMixin:
    """Window, resolution, HDR and graphics settings changes."""

    def _hdr_wanted(self, display_index, enabled=None):
        """HDR output is used when it is switched on and the monitor runs Windows HDR."""
        if enabled is None:
            enabled = bool(self.settings.settings.get("hdr_enabled", False))
        return enabled and hdr_output.display_hdr_info(display_index)[0]

    def _setup_hdr(self):
        """Create the HDR presenter for the current window (None for SDR windows)."""
        self.hdr_presenter = None
        if self.settings.settings.get("hdr_enabled", False):
            paper_white = self.settings.settings.get("hdr_paper_white", hdr_output.PAPER_WHITE_DEFAULT)
            self.hdr_presenter = hdr_output.create_presenter(self.width, self.height, paper_white)

    def apply_graphics_settings(self):
        """Anti-aliasing, VSync and background from the settings, for the current OpenGL context."""
        s = self.settings.settings
        self.scene_target = graphics.SceneTarget(s.get("antialiasing", graphics.DEFAULT_AA))
        graphics.set_vsync(s.get("vsync", graphics.DEFAULT_VSYNC))
        self.renderer.set_background(s.get("background_style", backgrounds.DEFAULT_STYLE),
                                     s.get("background_stars", True))

    def toggle_fullscreen(self):
        """F11: switch between a window and borderless fullscreen on the current monitor"""
        if self.display_mode == "windowed":
            mode = "borderless"
            size = display_manager.desktop_size(self.display_index)
        else:
            mode = "windowed"
            saved = self.settings.settings.get("resolution") or {}
            wanted = (int(saved.get("width", 0) or 0), int(saved.get("height", 0) or 0))
            options = display_manager.windowed_resolutions(self.display_index)
            size = display_manager.nearest(wanted, options) if wanted[0] > 0 else display_manager.default_window_size(self.display_index)
        self.apply_display(mode, self.display_index, size)

    def change_resolution(self, width, height):
        """Change the window size while keeping the current display mode"""
        return self.apply_display(self.display_mode, self.display_index, (width, height))

    def apply_display(self, mode, display_index, size, hdr=None):
        """Switch display mode, monitor, resolution and HDR, keeping the game state"""
        if hdr is None:
            hdr = bool(self.settings.settings.get("hdr_enabled", False))
        self.debug_print(f"Applying display: {mode} on monitor {display_index + 1} at {size[0]}x{size[1]}")
        try:
            # Save cube, camera, animation and game state; the OpenGL context is recreated
            cube_state = None
            camera_rotation = (0, 0)
            animation_state = None
            game_state = None
            if hasattr(self, 'renderer') and self.renderer:
                try:
                    cube_state = self.renderer.rubiks_cube.get_state()
                    camera_rotation = (self.renderer.rotation_x, self.renderer.rotation_y)
                    animation_state = {
                        'is_animating': self.renderer.is_animating,
                        'animation_start_time': self.renderer.animation_start_time,
                        'animating_face': self.renderer.animating_face,
                        'animation_axis': self.renderer.animation_axis,
                        'animation_angle_total': self.renderer.animation_angle_total,
                        'animation_clockwise': self.renderer.animation_clockwise,
                        'pending_move': self.renderer.pending_move
                    }
                    game_state = {
                        'game_started': self.game_started,
                        'new_game_requested': self.new_game_requested,
                        'move_counter': self.move_counter,
                        'start_time': self.start_time,
                        'cube_solved': self.cube_solved,
                        '_ever_started': getattr(self, '_ever_started', False)
                    }
                except Exception as e:
                    self.debug_print(f"Could not save cube state: {e}")

            # Recreate the window from scratch (needed to move between monitors).
            # GL objects die with the old context, so just drop the references.
            self.hdr_presenter = None
            self.settings.settings["hdr_enabled"] = bool(hdr)
            pygame.display.quit()
            pygame.display.init()
            try:
                pygame.display.set_icon(pygame.image.load(resource_path("utils/rubiksCube_Icon.ico")))
            except Exception:
                pass
            self.screen = display_manager.open_window(mode, display_index, size,
                                                      hdr=self._hdr_wanted(display_index, hdr))
            pygame.display.set_caption("Rubik's Cube Simulator")

            self.display_mode = mode
            self.display_index = display_index
            self.is_fullscreen = mode != "windowed"
            self.width, self.height = self.screen.get_size()
            ui.set_screen(self.width, self.height)
            ui.clear_caches()
            self.debug_print(f"Actual screen size: {self.width}x{self.height}")

            # New OpenGL context: rebuild the renderer and restore the cube
            self._overlay_tex = None
            self._snapshot_tex = None
            self._setup_hdr()
            self.renderer = Renderer(self.width, self.height)
            self.apply_graphics_settings()
            skybox_mode = self.menu.get_selected_difficulty() if hasattr(self, 'menu') else None
            if skybox_mode and self.difficulty_change_count > 0:
                self.renderer.set_background_mode(skybox_mode)
            if hasattr(self, 'mouse_interaction'):
                self.mouse_interaction.update_renderer(self.renderer)
            if cube_state is not None:
                try:
                    self.renderer.rubiks_cube.set_state(cube_state)
                    self.renderer.update_cube_colors()
                    self.renderer.rotation_x, self.renderer.rotation_y = camera_rotation
                    if animation_state is not None:
                        for key, value in animation_state.items():
                            setattr(self.renderer, key, value)
                    if game_state is not None:
                        self.game_started = game_state['game_started']
                        self.new_game_requested = game_state['new_game_requested']
                        self.move_counter = game_state['move_counter']
                        self.start_time = game_state['start_time']
                        self.cube_solved = game_state['cube_solved']
                        self._ever_started = game_state['_ever_started']
                except Exception as e:
                    self.debug_print(f"Could not restore cube state: {e}")

            # Save before rebuilding the menu, so it reads the new state
            self.settings.settings["display_mode"] = mode
            self.settings.settings["display_index"] = display_index
            self.settings.settings["fullscreen"] = self.is_fullscreen
            if mode != "borderless":
                # Borderless always uses the native size; keep the window size for later
                self.settings.settings["resolution"] = {"width": self.width, "height": self.height}
            self.settings.save_settings()

            # Rebuild every 2D layer for the new size
            self._achievement_icon_cache = {}
            if hasattr(self, 'menu'):
                self.menu.debug_mode = self.debug_mode
                self.menu._load_display_state()
                self.menu.width, self.menu.height = self.width, self.height
                self.menu._create_menus()
            if hasattr(self, 'results_window'):
                self.results_window.update_dimensions(self.width, self.height)
            if hasattr(self, 'menu_button'):
                self.menu_button.update_dimensions(self.width, self.height)

            self.debug_print(f"Display change complete: {self.width}x{self.height}")
            return True

        except Exception as e:
            print(f"Display change error: {e}")
            self._fallback_resolution()
            return False

    def _fallback_resolution(self):
        """Fall back to a safe window on the primary monitor if a display change fails"""
        try:
            print("Attempting fallback to safe resolution")
            pygame.display.quit()
            pygame.display.init()
            size = display_manager.default_window_size(0)
            self.hdr_presenter = None
            self.screen = display_manager.open_window("windowed", 0, size, hdr=False)
            self.display_mode, self.display_index, self.is_fullscreen = "windowed", 0, False
            self.width, self.height = self.screen.get_size()
            ui.set_screen(self.width, self.height)
            ui.clear_caches()
            self._overlay_tex = None
            self._snapshot_tex = None
            self.renderer = Renderer(self.width, self.height)
            self.apply_graphics_settings()
            if hasattr(self, 'mouse_interaction'):
                self.mouse_interaction.update_renderer(self.renderer)
            if hasattr(self, 'menu'):
                self.menu._load_display_state()
                self.menu.width, self.menu.height = self.width, self.height
                self.menu._create_menus()
            if hasattr(self, 'results_window'):
                self.results_window.update_dimensions(self.width, self.height)
            if hasattr(self, 'menu_button'):
                self.menu_button.update_dimensions(self.width, self.height)
            print(f"Restored a safe window: {self.width}x{self.height}")
        except Exception as e:
            print(f"Critical error in fallback resolution: {e}")
            self.running = False
