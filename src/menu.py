import os
import time
import threading
from datetime import datetime, timezone

import pygame
import pygame_menu
from pygame_menu.locals import (ALIGN_CENTER, ALIGN_LEFT, ALIGN_RIGHT, ORIENTATION_VERTICAL,
                                POSITION_CENTER, POSITION_EAST)

from src.settings_manager import SettingsManager
from src.sound_manager import SoundManager
from src.personal_best_manager import PersonalBestManager
from src.user_manager import UserManager, REGIONS
from src.achievements_manager import AchievementsManager
from src import display_manager
from src import hdr as hdr_output
from src import ui_style as ui
from utils.path_helper import resource_path

# Leaderboard filter options
GAME_MODE_OPTIONS = ["All Modes", "easy", "medium", "hard", "limited_time", "limited_moves"]
GAME_MODE_DISPLAY = {
    "All Modes": "All modes",
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
    "limited_time": "Limited Time",
    "limited_moves": "Limited Moves"
}
REGION_OPTIONS = ["All Regions"] + REGIONS
REGION_DISPLAY = {"All Regions": "All regions"}

NAV_KEYS = (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB)


class _Layout:
    """Screen geometry for the current resolution."""

    def __init__(self, width, height):
        ui.set_screen(width, height)
        self.width, self.height = width, height
        self.margin = max(ui.px(32), int(width * 0.035))
        self.header_h = ui.px(124)
        self.sb_space = max(8, ui.px(16))
        self.content_w = min(ui.px(1180), width - 2 * self.margin - 2 * self.sb_space)
        self.content_x = (width - self.content_w) // 2
        self.panel_w = max(min(int(width * 0.33), ui.px(620)), min(ui.px(440), int(width * 0.45)))
        self.panel_pad = ui.px(48)
        self.gap = ui.px(20)


class Menu:
    def __init__(self, screen_width, screen_height, game_instance=None):
        self.width = screen_width
        self.height = screen_height
        self.game = game_instance
        self.debug_mode = False

        self.settings_manager = SettingsManager()
        self.personal_best_manager = PersonalBestManager()
        self.user_manager = UserManager()
        self.achievements_manager = AchievementsManager()
        self.supabase_manager = None  # set by the game instance

        self.sound_manager = SoundManager()
        self.sound_manager.load_volumes_from_settings(self.settings_manager)

        # Menu state
        self.active = False
        self.resolution_changed_flag = False
        self.settings_changed = False
        self.selected_difficulty = "freeplay"
        self.has_difficulty_changed = False
        self.difficulty_ever_selected = False
        self.game_rendered = False

        # Profile form state
        self.user_setup_active = False
        self.user_setup_username = ""
        self.user_setup_region_index = 0
        self.username_error = None

        # Statistics tab: "personal_records", "global_leaderboard" or "daily_leaderboard"
        self.statistics_tab = "personal_records"

        # Global leaderboard state
        self.leaderboard_data = []
        self.leaderboard_loading = False
        self.leaderboard_error = None
        self.leaderboard_is_offline = False
        self.leaderboard_filter_mode = "All Modes"
        self.leaderboard_filter_region = "All Regions"
        self.leaderboard_last_fetch = 0
        self.leaderboard_ui_refresh_pending = False

        # Daily leaderboard state
        self.daily_leaderboard_data = []
        self.daily_leaderboard_loading = False
        self.daily_leaderboard_error = None
        self.daily_leaderboard_is_offline = False
        self.daily_leaderboard_filter_region = "All Regions"
        self.daily_leaderboard_last_fetch = 0
        self.daily_leaderboard_ui_refresh_pending = False

        # Challenge settings
        self.selected_time_limit = 300
        self.time_limit_options = [60, 300, 600, 900]
        self.selected_move_limit = 25
        self.move_limit_options = list(range(15, 51, 5))

        self.game_modes = self._initialize_game_modes()

        # Open/close fade
        self.is_animating = False
        self.animation_start_time = 0
        self.animation_duration = 0.2
        self.is_opening = False
        self.target_alpha = 1.0
        self.current_alpha = 0.0

        # Settings values
        self.show_fps = self.settings_manager.settings.get("show_fps", False)
        self.hints_enabled = self.settings_manager.get_hints_enabled()
        self.master_volume = self.settings_manager.get_master_volume()
        self.music_volume = self.settings_manager.get_music_volume()
        self.effects_volume = self.settings_manager.get_effects_volume()
        self.menu_volume = self.settings_manager.get_menu_volume()
        self.volume = int(self.settings_manager.settings.get("volume", 50))
        self._load_display_state()

        # Interaction state
        self.pages = {}
        self._sliders = []
        self.hover_widget = None
        self.keyboard_mode = False
        self.header_back_rect = None
        self._skip_pygame_menu_update_once = False
        self._ach_icon_cache = {}

        self._patch_pygame_menu_scrollbar_render()
        self._create_menus()
        self.current_menu = self.main_menu

    # ================================================================ setup
    @staticmethod
    def _patch_pygame_menu_scrollbar_render() -> None:
        """Clamp the scrollbar thumb to its track (pygame-menu can let it drift off)."""
        try:
            from pygame_menu.widgets.widget.scrollbar import ScrollBar
        except Exception:
            return
        if getattr(ScrollBar, '_rubik_sim_render_patched', False):
            return
        original_render = getattr(ScrollBar, '_render', None)
        if original_render is None:
            return

        def _render_patched(self):  # type: ignore[no-redef]
            try:
                r = getattr(self, '_slider_rect', None)
                if r is not None:
                    pad = int(getattr(self, '_slider_pad', 0) or 0)
                    if getattr(self, '_orientation', None) == 1:
                        r.x = pad
                    else:
                        r.y = pad
            except Exception:
                pass
            return original_render(self)

        ScrollBar._render = _render_patched  # type: ignore[assignment]
        ScrollBar._rubik_sim_render_patched = True

        # The focus dimming replaces pixels on our transparent overlay, which
        # punches holes in it; the menu has its own scrim, so turn it off.
        pygame_menu.Menu._draw_focus_widget = lambda self, surface, widget, force=False: None

    def _build_theme(self):
        t = pygame_menu.themes.THEME_DARK.copy()
        t.background_color = (0, 0, 0, 0)
        t.title_bar_style = pygame_menu.widgets.MENUBAR_STYLE_NONE
        t.title_font = ui.FONT_DISPLAY
        t.title_font_color = ui.TEXT
        t.title_font_shadow = False
        t.widget_font = ui.FONT_BODY
        t.widget_font_size = ui.fs(ui.SIZE_BODY)
        t.widget_font_color = ui.TEXT
        t.widget_font_shadow = False
        t.widget_font_antialias = True
        t.widget_selection_effect = pygame_menu.widgets.NoneSelection()
        t.widget_background_color = (0, 0, 0, 0)
        t.widget_border_width = 0
        t.widget_padding = 0
        t.widget_margin = (0, 0)
        t.widget_alignment = ALIGN_CENTER
        t.selection_color = ui.ACCENT
        t.cursor_color = ui.ACCENT
        t.cursor_selection_color = (*ui.ACCENT, 90)
        t.readonly_font_color = ui.DIM
        t.readonly_selected_color = ui.DIM
        t.focus_background_color = (*ui.BG, 150)
        t.scrollbar_color = ui.BG
        t.scrollbar_slider_color = ui.SURFACE_3
        t.scrollbar_slider_hover_color = ui.MUTED
        t.scrollbar_slider_pad = 0
        t.scrollbar_thick = max(6, ui.px(8))
        t.scrollbar_shadow = False
        t.scrollarea_position = POSITION_EAST
        t.scrollarea_outer_margin = (0, 0)
        t.menubar_close_button = False
        t.title_updates_pygame_display = False  # keep the window caption
        self.theme = t

    def _initialize_game_modes(self):
        """Available game modes and their configuration."""
        return {
            "freeplay": {
                "name": "Free Play",
                "description": "A solved cube, no timer. Press X to scramble it whenever you like.",
                "scramble_moves": 0,
                "timer_enabled": False,
            },
            "easy": {
                "name": "Easy",
                "description": "Five move scramble. A gentle warm up.",
                "scramble_moves": 5,
                "timer_enabled": True,
            },
            "medium": {
                "name": "Medium",
                "description": "Ten move scramble. Plan a few moves ahead.",
                "scramble_moves": 10,
                "timer_enabled": True,
            },
            "hard": {
                "name": "Hard",
                "description": "Fully random scramble. The real thing.",
                "scramble_moves": -1,
                "timer_enabled": True,
            },
            "limited_time": {
                "name": "Limited Time",
                "description": "Solve a 15 move scramble before the clock runs out.",
                "scramble_moves": 15,
                "timer_enabled": True,
                "countdown_mode": True,
            },
            "limited_moves": {
                "name": "Limited Moves",
                "description": "Solve a 15 move scramble within a move budget.",
                "scramble_moves": 15,
                "timer_enabled": True,
                "countdown_moves": True,
            },
            "daily_cube": {
                "name": "Daily Cube",
                "description": "One scramble for everyone today, ranked worldwide.",
                "scramble_moves": 20,
                "timer_enabled": True,
                "daily_mode": True,
            }
        }

    def get_game_mode_config(self, difficulty):
        """Configuration for a game mode, including the chosen challenge limits."""
        if difficulty == "limited_time":
            self.game_modes["limited_time"]["time_limit"] = self.selected_time_limit
        if difficulty == "limited_moves":
            self.game_modes["limited_moves"]["move_limit"] = self.selected_move_limit
        return self.game_modes.get(difficulty, self.game_modes["medium"])

    # ================================================================ display settings
    def _load_display_state(self):
        mode, index, size = display_manager.resolve(self.settings_manager.settings)
        self.display_mode = mode
        self.display_index = index
        saved = self.settings_manager.settings.get("resolution") or {}
        saved_size = (int(saved.get("width", size[0])), int(saved.get("height", size[1])))
        self.display_size = size if mode != "borderless" else saved_size
        self.pending_mode = self.display_mode
        self.pending_index = self.display_index
        self.pending_size = size
        self.fullscreen = self.display_mode != "windowed"
        settings = self.settings_manager.settings
        self.hdr_enabled = bool(settings.get("hdr_enabled", False))
        self.pending_hdr = self.hdr_enabled
        self.hdr_paper_white = int(settings.get("hdr_paper_white", hdr_output.PAPER_WHITE_DEFAULT))
        self.settings_changed = False

    def _pending_options(self):
        options = display_manager.resolutions_for(self.pending_mode, self.pending_index)
        # A custom window size (e.g. from an older version) stays selectable as is
        current = (self.width, self.height)
        if (self.pending_mode == "windowed" and self.display_mode == "windowed"
                and self.pending_index == self.display_index and current not in options):
            options = sorted(options + [current], key=lambda s: (s[0], s[1]), reverse=True)
        return options

    def _resolution_items(self):
        items = []
        for i, (w, h) in enumerate(self._pending_options()):
            items.append((f"{w} x {h}   {ui.aspect_label(w, h)}", i))
        return items

    def _refresh_pending_resolution(self):
        options = self._pending_options()
        if self.pending_mode == "borderless":
            self.pending_size = options[0]
        else:
            preferred = self.display_size if self.display_mode != "borderless" else self.pending_size
            self.pending_size = display_manager.nearest(preferred, options)
        if getattr(self, "resolution_select", None) is not None:
            try:
                items = self._resolution_items()
                self.resolution_select.update_items(items)
                self.resolution_select.set_value(options.index(self.pending_size))
                self.resolution_select.readonly = self.pending_mode == "borderless"
            except Exception as e:
                print(f"Could not refresh resolution list: {e}")
        self._update_settings_changed()

    def _update_settings_changed(self):
        current_size = (self.width, self.height)
        self.settings_changed = (
            self.pending_mode != self.display_mode
            or self.pending_index != self.display_index
            or (self.pending_mode != "borderless" and self.pending_size != current_size)
            or self.pending_hdr != self.hdr_enabled
        )
        if getattr(self, "apply_button", None) is not None:
            self.apply_button.readonly = not self.settings_changed

    def _on_display_mode_change(self, selected, index):
        self.sound_manager.play("menu_select")
        self.pending_mode = display_manager.MODES[index]
        self._refresh_pending_resolution()

    def _on_monitor_change(self, selected, index):
        self.sound_manager.play("menu_select")
        self.pending_index = index
        self._refresh_pending_resolution()
        if not hdr_output.display_hdr_info(index)[0]:
            self.pending_hdr = False
            self._update_settings_changed()
        # HDR options depend on the monitor: rebuild the page to show them
        self._rebuild_settings_page("display_monitor")

    def _rebuild_settings_page(self, select):
        self._build_settings_page(self.settings_menu)
        try:
            self.settings_menu.select_widget(select)
        except Exception:
            pass

    def _on_hdr_toggle(self, value):
        self.sound_manager.play("menu_select")
        self.pending_hdr = bool(value)
        self._update_settings_changed()
        # The brightness slider only exists while HDR is on
        self._rebuild_settings_page("display_hdr")

    def _on_paper_white_change(self, value):
        self._slider_dirty = True
        self.hdr_paper_white = int(round(value / 5) * 5)
        self.settings_manager.settings["hdr_paper_white"] = self.hdr_paper_white
        self.settings_manager.save_settings()
        presenter = getattr(self.game, "hdr_presenter", None) if self.game else None
        if presenter is not None:
            presenter.paper_white = self.hdr_paper_white  # applies on the next frame
        if getattr(self, "paper_white_label", None) is not None:
            self.paper_white_label.set_title(f"{self.hdr_paper_white:>3} nits")

    def _on_resolution_change(self, selected, index):
        self.sound_manager.play("menu_select")
        options = self._pending_options()
        if 0 <= index < len(options):
            self.pending_size = options[index]
        self._update_settings_changed()

    def _apply_settings(self):
        """Ask the game to switch to the pending display settings."""
        if not self.settings_changed:
            return
        self.sound_manager.play("menu_apply")
        self.fullscreen = self.pending_mode != "windowed"
        self.resolution_changed_flag = True

    def get_display_request(self):
        return self.pending_mode, self.pending_index, self.pending_size, self.pending_hdr

    def get_current_resolution(self):
        return self.pending_size

    def resolution_changed(self):
        return self.resolution_changed_flag

    def reset_resolution_changed(self):
        self.resolution_changed_flag = False

    def get_setting(self, name):
        if name == "show_fps":
            return self.show_fps
        if name == "fullscreen":
            return self.fullscreen
        if name == "volume":
            return self.volume
        if name == "difficulty":
            return self.selected_difficulty
        return None

    def get_selected_difficulty(self):
        return self.selected_difficulty

    # ================================================================ simple settings
    def _on_fps_toggle(self, value):
        self.sound_manager.play("menu_select")
        self.show_fps = value
        self.settings_manager.settings["show_fps"] = value
        self.settings_manager.save_settings()
        if self.game:
            self.game.show_fps = value

    def _on_hints_toggle(self, value):
        self.sound_manager.play("menu_select")
        self.hints_enabled = value
        self.settings_manager.set_hints_enabled(value)
        if self.game:
            self.game.hints_enabled = value
            if not value:
                self.game.hint_banner_active = False
                self.game.hint_expanded = False
                self.game.hint_banner_alpha = 0.0

    def _set_volume(self, key, value):
        value = int(value)
        self._slider_dirty = True
        setattr(self, key, value)
        setter = {
            "master_volume": self.sound_manager.set_master_volume,
            "music_volume": self.sound_manager.set_music_volume,
            "effects_volume": self.sound_manager.set_effects_volume,
            "menu_volume": self.sound_manager.set_menu_volume,
        }[key]
        setter(value / 100.0)
        self.settings_manager.set_audio_volume(key, value)
        self.settings_manager.save_settings()
        if self.game:
            self.game.sound_manager.load_volumes_from_settings(self.settings_manager)
        label = self.volume_labels.get(key)
        if label is not None:
            label.set_title(f"{value:>3}%")

    # ================================================================ navigation actions
    def _in_game(self):
        return bool(self.game and getattr(self.game, "difficulty_change_count", 0) >= 1)

    def _change_menu(self, new_menu):
        self.current_menu = new_menu
        self.hover_widget = None
        self.keyboard_mode = False
        try:
            new_menu.get_scrollarea().scroll_to(ORIENTATION_VERTICAL, 0)
        except Exception:
            pass

    def _go(self, menu):
        self.sound_manager.play("menu_select")
        self._change_menu(menu)

    def _go_back(self):
        page = self.pages.get(self.current_menu, {})
        back = page.get("back")
        if back:
            back()

    def _start_game(self, difficulty="normal"):
        """Start a game in the given mode and close the menu"""
        self.sound_manager.play("menu_select")
        difficulty_changed = (difficulty != self.selected_difficulty) or not self.difficulty_ever_selected
        self.selected_difficulty = difficulty
        if difficulty_changed:
            self.has_difficulty_changed = True
            self.difficulty_ever_selected = True
            if self.game:
                self.game.increment_difficulty_change_count()
        if self.game:
            self.game.renderer.reload_skybox_texture(difficulty)
            if difficulty_changed:
                self.game.request_new_game()
        self.refresh_main_menu_buttons()
        if not self.is_animating:
            self.toggle()

    def _start_challenge(self, difficulty):
        """Challenges always start a fresh game"""
        self.sound_manager.play("menu_select")
        self.selected_difficulty = difficulty
        self.has_difficulty_changed = True
        self.difficulty_ever_selected = True
        if self.game:
            self.game.increment_difficulty_change_count()
            self.game.renderer.reload_skybox_texture(difficulty)
            self.game.request_new_game()
        self.refresh_main_menu_buttons()
        if not self.is_animating:
            self.toggle()

    def _start_limited_time_game(self):
        self._start_challenge("limited_time")

    def _start_limited_moves_game(self):
        self._start_challenge("limited_moves")

    def _play_current_difficulty(self):
        """Resume the current game"""
        self.sound_manager.play("menu_select")
        if not self.is_animating:
            self.toggle()

    def _open_difficulty_select(self):
        self.sound_manager.play("menu_select")
        if not self.user_manager.is_setup_completed():
            self.show_user_setup()
        else:
            self._build_modes_page(self.difficulty_menu)
            self._change_menu(self.difficulty_menu)

    def _open_settings(self):
        self._load_display_state()
        self._build_settings_page(self.settings_menu)
        self._go(self.settings_menu)

    def _open_audio_settings(self):
        self._open_settings()

    def _open_controls(self):
        self._go(self.controls_menu)

    def _show_quit_confirmation(self):
        self._go(self.quit_confirmation_menu)
        try:
            self.quit_confirmation_menu.select_widget("quit_cancel")
        except Exception:
            pass

    def _cancel_quit(self):
        self._back_to_main()

    def _quit_game(self):
        self.sound_manager.play("menu_select")
        if self.game:
            self.game.running = False
        else:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _open_personal_best(self):
        self.sound_manager.play("menu_select")
        if not self.user_manager.is_setup_completed():
            self.show_user_setup()
            return
        if self.statistics_tab == "global_leaderboard":
            self._fetch_leaderboard_data()
        elif self.statistics_tab == "daily_leaderboard":
            self._fetch_daily_leaderboard_data()
        self._create_personal_best_content()
        self._change_menu(self.personal_best_menu)

    def _open_achievements(self):
        self.sound_manager.play("menu_select")
        self._create_achievements_content()
        self._change_menu(self.achievements_menu)

    def _open_time_selection(self):
        self._go(self.time_selection_menu)

    def _open_moves_selection(self):
        self._go(self.moves_selection_menu)

    def _back_to_main(self):
        self.sound_manager.play("menu_select")
        self.refresh_main_menu_buttons()
        self._change_menu(self.main_menu)

    def _back_to_difficulty(self):
        self._go(self.difficulty_menu)

    def _back_to_settings(self):
        self._go(self.settings_menu)

    def _back_to_statistics(self):
        self.sound_manager.play("menu_select")
        self._create_personal_best_content()
        self._change_menu(self.personal_best_menu)

    def _close_from_main(self):
        if not self.is_animating:
            self.toggle()

    # ================================================================ challenge limits
    def _format_time_display(self, seconds):
        minutes = seconds // 60
        return f"{minutes} min"

    def _on_time_limit_change_and_update_display(self, value):
        self.selected_time_limit = self.time_limit_options[int(round(value))]
        self._slider_dirty = True
        if getattr(self, "time_display_label", None) is not None:
            self.time_display_label.set_title(self._format_time_display(self.selected_time_limit).replace(" ", "  "))

    def _on_move_limit_change_and_update_display(self, value):
        self.selected_move_limit = self.move_limit_options[int(round(value))]
        self._slider_dirty = True
        if getattr(self, "moves_display_label", None) is not None:
            self.moves_display_label.set_title(f"{self.selected_move_limit}  moves")

    # ================================================================ leaderboards
    def _switch_tab(self, tab):
        self.sound_manager.play("menu_select")
        self.statistics_tab = tab
        if tab == "global_leaderboard":
            self._fetch_leaderboard_data()
        elif tab == "daily_leaderboard":
            self._fetch_daily_leaderboard_data()
        self._create_personal_best_content(select_id=f"tab_{tab}")

    def _fetch_leaderboard_data(self, force_refresh=False):
        """Fetch the global leaderboard in a background thread."""
        if self.leaderboard_loading:
            return
        if not force_refresh and self.leaderboard_data and (time.time() - self.leaderboard_last_fetch) < 30:
            return
        if not self.supabase_manager or not self.supabase_manager.is_configured():
            self.leaderboard_error = "not_configured"
            self.leaderboard_data = []
            return

        self.leaderboard_loading = True
        self.leaderboard_error = None
        self.leaderboard_ui_refresh_pending = True

        def fetch_task():
            try:
                game_mode = None if self.leaderboard_filter_mode == "All Modes" else self.leaderboard_filter_mode
                region = None if self.leaderboard_filter_region == "All Regions" else self.leaderboard_filter_region
                data, is_offline = self.supabase_manager.get_leaderboard(
                    game_mode=game_mode, region=region, sort_by="best_time", limit=50, ascending=True)
                self.leaderboard_data = data if data else []
                self.leaderboard_last_fetch = time.time()
                self.leaderboard_is_offline = is_offline
                self.leaderboard_error = None
            except Exception as e:
                print(f"Error fetching leaderboard: {e}")
                self.leaderboard_error = "failed"
                self.leaderboard_is_offline = False
                self.leaderboard_data = []
            finally:
                self.leaderboard_loading = False
                if self.statistics_tab == "global_leaderboard":
                    self.leaderboard_ui_refresh_pending = True

        threading.Thread(target=fetch_task, daemon=True).start()

    def _fetch_daily_leaderboard_data(self, force_refresh=False):
        """Fetch the daily leaderboard in a background thread."""
        if self.daily_leaderboard_loading:
            return
        if (not force_refresh and self.daily_leaderboard_data
                and (time.time() - self.daily_leaderboard_last_fetch) < 30):
            return
        if not self.supabase_manager or not self.supabase_manager.is_configured():
            self.daily_leaderboard_error = "not_configured"
            self.daily_leaderboard_data = []
            return

        self.daily_leaderboard_loading = True
        self.daily_leaderboard_error = None
        self.daily_leaderboard_ui_refresh_pending = True

        def fetch_task():
            try:
                region = None if self.daily_leaderboard_filter_region == "All Regions" else self.daily_leaderboard_filter_region
                data, is_offline = self.supabase_manager.get_daily_leaderboard(region=region, limit=50)
                self.daily_leaderboard_data = data if data else []
                self.daily_leaderboard_last_fetch = time.time()
                self.daily_leaderboard_is_offline = is_offline
                self.daily_leaderboard_error = None
            except Exception as e:
                print(f"Error fetching daily leaderboard: {e}")
                self.daily_leaderboard_error = "failed"
                self.daily_leaderboard_is_offline = False
                self.daily_leaderboard_data = []
            finally:
                self.daily_leaderboard_loading = False
                if self.statistics_tab == "daily_leaderboard":
                    self.daily_leaderboard_ui_refresh_pending = True

        threading.Thread(target=fetch_task, daemon=True).start()

    def _on_leaderboard_mode_filter_change(self, selected, index):
        self.sound_manager.play("menu_select")
        self.leaderboard_filter_mode = GAME_MODE_OPTIONS[index] if 0 <= index < len(GAME_MODE_OPTIONS) else "All Modes"
        self._fetch_leaderboard_data(force_refresh=True)

    def _on_leaderboard_region_filter_change(self, selected, index):
        self.sound_manager.play("menu_select")
        self.leaderboard_filter_region = REGION_OPTIONS[index] if 0 <= index < len(REGION_OPTIONS) else "All Regions"
        self._fetch_leaderboard_data(force_refresh=True)

    def _on_daily_leaderboard_region_filter_change(self, selected, index):
        self.sound_manager.play("menu_select")
        self.daily_leaderboard_filter_region = REGION_OPTIONS[index] if 0 <= index < len(REGION_OPTIONS) else "All Regions"
        self._fetch_daily_leaderboard_data(force_refresh=True)

    def _refresh_leaderboard(self):
        self.sound_manager.play("menu_select")
        self._fetch_leaderboard_data(force_refresh=True)

    def _refresh_daily_leaderboard(self):
        self.sound_manager.play("menu_select")
        self._fetch_daily_leaderboard_data(force_refresh=True)

    # ================================================================ profile
    def _open_user_edit(self):
        self.sound_manager.play("menu_select")
        self.user_setup_username = self.user_manager.get_username() or ""
        region = self.user_manager.get_region()
        self.user_setup_region_index = REGIONS.index(region) if region in REGIONS else 0
        self.username_error = None
        self._create_user_edit_content()
        self._change_menu(self.user_edit_menu)
        self._focus_input(self.user_edit_menu, "edit_username_input")

    def needs_user_setup(self) -> bool:
        return not self.user_manager.is_setup_completed()

    def show_user_setup(self):
        self.user_setup_active = True
        self.user_setup_username = ""
        self.user_setup_region_index = 0
        self.username_error = None
        self._create_user_setup_content()
        self._change_menu(self.user_setup_menu)
        self._focus_input(self.user_setup_menu, "username_input")

    def _focus_input(self, menu, input_id):
        try:
            menu.select_widget(input_id)
        except Exception as e:
            print(f"Error focusing text input: {e}")

    def _on_username_change(self, value):
        self.user_setup_username = value

    def _on_region_change(self, selected, index):
        self.sound_manager.play("menu_select")
        self.user_setup_region_index = index

    _on_edit_username_change = _on_username_change
    _on_edit_region_change = _on_region_change

    def _confirm_user_setup(self):
        username = self.user_setup_username.strip()
        if not username:
            self.username_error = "Enter a username to continue."
            self._create_user_setup_content()
            self._focus_input(self.user_setup_menu, "username_input")
            return
        if self.supabase_manager and self.supabase_manager.is_configured():
            if self.supabase_manager.is_username_taken(username):
                self.username_error = "That username is taken. Try another one."
                self.sound_manager.play("menu_select")
                self._create_user_setup_content()
                self._focus_input(self.user_setup_menu, "username_input")
                return

        self.username_error = None
        region = REGIONS[self.user_setup_region_index]
        self.user_manager.complete_setup(username, region)
        self.sound_manager.play("menu_apply")
        self.user_setup_active = False

        if self.supabase_manager and self.supabase_manager.is_configured():
            self.supabase_manager.set_user_hash(
                self.user_manager.get_user_id(),
                self.user_manager.user_data.get("created_at", "")
            )
            if self.personal_best_manager:
                self.personal_best_manager.sync_all_to_cloud()

        self.refresh_main_menu_buttons()
        self._build_modes_page(self.difficulty_menu)
        self._change_menu(self.difficulty_menu)

    def _save_user_edit(self):
        username = self.user_setup_username.strip()
        if not username:
            self.username_error = "Enter a username to continue."
            self._create_user_edit_content()
            self._focus_input(self.user_edit_menu, "edit_username_input")
            return
        if self.supabase_manager and self.supabase_manager.is_configured():
            current_user_hash = self.supabase_manager.get_user_hash()
            if self.supabase_manager.is_username_taken(username, exclude_user_hash=current_user_hash):
                self.username_error = "That username is taken. Try another one."
                self.sound_manager.play("menu_select")
                self._create_user_edit_content()
                self._focus_input(self.user_edit_menu, "edit_username_input")
                return

        self.username_error = None
        region = REGIONS[self.user_setup_region_index]
        if self.supabase_manager and self.supabase_manager.is_configured():
            # Keep the same user hash, only rename existing records
            self.supabase_manager.update_user_profile(username, region)
        self.user_manager.update_user(username, region)
        self.sound_manager.play("menu_apply")
        self.refresh_main_menu_buttons()
        self._open_personal_best()

    def _back_from_user_setup(self):
        self.user_setup_active = False
        self._back_to_main()

    # ================================================================ open / close
    def update(self):
        if self.active and self.current_menu and self.current_menu.is_enabled():
            if self._skip_pygame_menu_update_once:
                self._skip_pygame_menu_update_once = False
            else:
                try:
                    self.current_menu.update([])
                except Exception:
                    pass

        if self.leaderboard_ui_refresh_pending and not self.leaderboard_loading:
            if self.statistics_tab == "global_leaderboard":
                self.leaderboard_ui_refresh_pending = False
                self._create_personal_best_content(keep_selection=True)
        if self.daily_leaderboard_ui_refresh_pending and not self.daily_leaderboard_loading:
            if self.statistics_tab == "daily_leaderboard":
                self.daily_leaderboard_ui_refresh_pending = False
                self._create_personal_best_content(keep_selection=True)

        if not self.is_animating:
            return
        progress = min((time.time() - self.animation_start_time) / self.animation_duration, 1.0)
        eased = 1 - (1 - progress) ** 3
        self.current_alpha = eased if self.is_opening else 1.0 - eased
        if progress >= 1.0:
            self.is_animating = False
            self.current_alpha = self.target_alpha
            if not self.is_opening:
                self.active = False

    def get_current_alpha(self):
        if not self.is_animating and not self.active:
            return 0.0
        return self.current_alpha if self.is_animating else 1.0

    def is_fully_visible(self):
        return self.active and (not self.is_animating or self.current_alpha >= 1.0)

    def toggle(self):
        """Fade the menu in or out"""
        self.is_animating = True
        self.animation_start_time = time.time()
        if self.active:
            self.is_opening = False
            self.target_alpha = 0.0
            self.hover_widget = None
        else:
            self.is_opening = True
            self.target_alpha = 1.0
            self.active = True
            self.sound_manager.play("menu_open")
            self.refresh_main_menu_buttons()
            self._change_menu(self.main_menu)

    def is_active(self):
        return self.active

    def set_game_instance(self, game):
        self.game = game
        # Share one settings object with the game so saves never overwrite each other
        self.settings_manager = game.settings
        self._load_display_state()
        self.refresh_main_menu_buttons()

    def notify_game_rendered(self):
        self.game_rendered = True

    def force_background_recapture(self):
        """Kept for compatibility: the menu draws over the live scene now."""

    # ================================================================ input
    def _is_selectable(self, widget):
        sel = getattr(widget, "is_selectable", False)
        sel = sel() if callable(sel) else sel
        return bool(sel) and widget.is_visible()

    def _view_rect(self, menu):
        page = self.pages.get(menu)
        return page["rect"] if page else pygame.Rect(0, 0, self.width, self.height)

    def _widget_at(self, pos):
        menu = self.current_menu
        if not menu or not self._view_rect(menu).collidepoint(pos):
            return None
        for widget in menu.get_widgets():
            try:
                if self._is_selectable(widget) and widget.get_rect(to_real_position=True).collidepoint(pos):
                    return widget
            except Exception:
                continue
        return None

    def _update_hover(self, pos):
        new = self._widget_at(pos)
        if new is not self.hover_widget:
            self.hover_widget = new

    def handle_event(self, event):
        """Handle an event. Returns True if the menu consumed it."""
        if not self.active or (self.is_animating and not self.is_opening):
            return False
        # Sliders click once when the value is released, not on every step while dragging
        if (event.type in (pygame.MOUSEBUTTONUP, pygame.KEYUP)
                and getattr(self, "_slider_dirty", False)):
            self._slider_dirty = False
            self.sound_manager.play("menu_select")
            for slider in self._sliders:
                try:
                    value = slider.get_value()
                    if value != slider.snap_value(value):
                        slider.set_value(slider.snap_value(value))
                except Exception:
                    pass
        menu = self.current_menu
        text_menu = menu in (getattr(self, "user_setup_menu", None), getattr(self, "user_edit_menu", None))

        # Text inputs read KEYDOWN, ignore TEXTINPUT so characters are not doubled
        if text_menu and event.type == pygame.TEXTINPUT:
            return True

        if event.type == pygame.MOUSEMOTION:
            self.keyboard_mode = False
            self._update_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.keyboard_mode = False
            if (self.pages.get(menu, {}).get("kind") == "page" and self.header_back_rect
                    and self.header_back_rect.collidepoint(event.pos)):
                self._go_back()
                return True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._go_back()
                return True
            if event.key in NAV_KEYS:
                if not self.keyboard_mode:
                    # First key press only reveals where the focus is
                    self.keyboard_mode = True
                    return True
                if event.key == pygame.K_TAB:
                    shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
                    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP if shift else pygame.K_DOWN,
                                               mod=0, unicode="", scancode=0)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_SPACE):
                self.keyboard_mode = True
                selected = menu.get_selected_widget()
                if event.key == pygame.K_SPACE and selected is not None and hasattr(selected, "_ui"):
                    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r", scancode=0)

        try:
            menu.update([event])
        except Exception as e:
            if self.debug_mode:
                print(f"Menu event error: {e}")
        self._skip_pygame_menu_update_once = True
        return True

    def update_cursor(self, mouse_pos):
        if not self.active:
            return
        hand = False
        if (self.pages.get(self.current_menu, {}).get("kind") == "page" and self.header_back_rect
                and self.header_back_rect.collidepoint(mouse_pos)):
            hand = True
        else:
            widget = self._widget_at(mouse_pos)
            hand = widget is not None and not getattr(widget, "readonly", False)
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hand else pygame.SYSTEM_CURSOR_ARROW)

    # ================================================================ widget helpers
    def _page(self, title, back, kind="page", width=None, motion_select=True):
        L = self.L
        if kind == "main":
            w, h, x, y = L.panel_w, self.height, 0, 0
            center = True
        elif kind == "dialog":
            w = width + 2 * L.sb_space
            h = self.height - 2 * L.margin
            x, y = (self.width - w) // 2, L.margin
            center = True
        else:
            w = (width or L.content_w) + 2 * L.sb_space
            h = self.height - L.header_h
            x, y = (self.width - w) // 2, L.header_h
            center = False
        menu = pygame_menu.Menu("", w, h, theme=self.theme, position=(x, y, False), center_content=center,
                                mouse_motion_selection=motion_select, screen_dimension=(self.width, self.height))
        # The background is transparent; skip blitting an empty full-size surface every frame
        menu.get_scrollarea()._area_color = None
        # pygame-menu moves the mouse pointer onto a widget it selects itself (for example
        # after a page is rebuilt when switching tabs). Never move the player's pointer.
        menu._disable_widget_update_mousepos_mouseselection = True
        self.pages[menu] = {"title": title, "back": back, "kind": kind, "width": width or L.content_w,
                            "rect": pygame.Rect(x, y, w, h)}
        return menu

    def _size_widget(self, widget, w, h):
        widget.set_padding(0)
        cw, ch = widget.get_width(), widget.get_height()
        dx, dy = max(0, int(w) - cw), max(0, int(h) - ch)
        widget.set_padding((dy // 2, dx - dx // 2, dy - dy // 2, dx // 2))

    def _custom_button(self, menu, label, action, w, h, painter, button_id="", **data):
        widget = menu.add.button(label, action, button_id=button_id, font_size=10, font_name=ui.FONT_BODY,
                                 font_color=(0, 0, 0, 0), background_color=(0, 0, 0, 0))
        self._size_widget(widget, w, h)
        widget._ui = dict(painter=painter, label=label, **data)
        widget._draw = lambda surface, _w=widget: self._paint(_w, surface)
        return widget

    def _paint(self, widget, surface):
        hovered = widget is self.hover_widget or (self.keyboard_mode and widget.is_selected())
        focused = self.keyboard_mode and widget.is_selected()
        disabled = bool(getattr(widget, "readonly", False))
        widget._ui["painter"](surface, widget.get_rect(), widget._ui, hovered and not disabled, focused, disabled)

    def _button(self, menu, label, action, w=None, h=None, variant="secondary", icon_name=None, button_id=""):
        w = w or ui.px(260)
        h = h or ui.px(58)
        return self._custom_button(menu, label, action, w, h, self._paint_button, button_id=button_id,
                                   variant=variant, icon=icon_name)

    def _spacer(self, menu, ref):
        menu.add.vertical_margin(ui.px(ref))

    def _surface(self, menu, surf):
        return menu.add.surface(surf)

    def _text_surface(self, text, fnt, color, width, align="left", line_gap=None):
        lines = ui.wrap(text, fnt, width)
        line_h = fnt.get_linesize() + (line_gap if line_gap is not None else ui.px(2))
        surf = pygame.Surface((width, max(1, line_h * len(lines))), pygame.SRCALPHA)
        for i, line in enumerate(lines):
            r = ui.render(line, fnt, color)
            x = 0 if align == "left" else (width - r.get_width()) // 2
            surf.blit(r, (x, i * line_h))
        return surf

    def _text(self, menu, text, fnt=None, color=ui.MUTED, width=None, align="left"):
        width = width or self.pages[menu]["width"]
        return self._surface(menu, self._text_surface(text, fnt or ui.body_font(), color, width, align))

    def _section(self, menu, title, top=36, width=None):
        width = width or self.pages[menu]["width"]
        self._spacer(menu, top)
        fnt = ui.display_font(ui.SIZE_H3)
        surf = pygame.Surface((width, fnt.get_height()), pygame.SRCALPHA)
        ui.draw_text(surf, title, fnt, ui.MUTED, (0, 0))
        self._surface(menu, surf)
        self._spacer(menu, 12)

    def _hairline(self, menu, width=None):
        width = width or self.pages[menu]["width"]
        surf = pygame.Surface((width, max(1, ui.px(1.5))), pygame.SRCALPHA)
        surf.fill(ui.LINE)
        self._surface(menu, surf)

    def _row(self, menu, label, controls, desc=None, separator=True):
        """A settings row: label on the left, controls packed on the right."""
        width = self.pages[menu]["width"]
        controls_w = sum(c.get_width() for c in controls) + ui.px(16) * (len(controls) - 1)
        fnt = ui.body_font()
        small = ui.body_font(ui.SIZE_SMALL)
        label_w = max(ui.px(120), width - controls_w - ui.px(32))
        lines = [(ui.ellipsize(label, fnt, label_w), fnt, ui.TEXT)]
        if desc:
            for line in ui.wrap(desc, small, label_w)[:2]:
                lines.append((line, small, ui.MUTED))
        text_h = sum(f.get_linesize() for _, f, _ in lines)
        row_h = max(ui.px(72), text_h + ui.px(24), max(c.get_height() for c in controls) + ui.px(16))
        label_surf = pygame.Surface((label_w, text_h), pygame.SRCALPHA)
        y = 0
        for text, f, color in lines:
            label_surf.blit(f.render(text, True, color), (0, y))
            y += f.get_linesize()

        frame = menu.add.frame_h(width, row_h, padding=0)
        frame._pack_margin_warning = False
        frame.pack(menu.add.surface(label_surf), align=ALIGN_LEFT, vertical_position=POSITION_CENTER)
        for i, control in enumerate(controls):
            frame.pack(control, align=ALIGN_RIGHT, vertical_position=POSITION_CENTER,
                       margin=(ui.px(16) if i else 0, 0))
        if separator:
            self._hairline(menu)
        return frame

    def _dropselect(self, menu, items, default, onchange, width, visible=6, title="", widget_id=""):
        d = menu.add.dropselect(
            title, items, default=default, onchange=onchange, dropselect_id=widget_id,
            font_name=ui.FONT_BODY, font_size=ui.fs(ui.SIZE_BODY), font_color=ui.TEXT,
            selection_box_width=width, selection_box_height=visible,
            selection_box_bgcolor=ui.SURFACE_2, selection_box_border_color=ui.LINE,
            selection_box_border_width=max(1, ui.px(1.5)), selection_box_arrow_color=ui.MUTED,
            selection_box_arrow_margin=(ui.px(14), ui.px(14), 0),
            selection_box_text_margin=ui.px(14), selection_box_margin=(ui.px(14) if title else 0, 0),
            selection_box_inflate=(0, ui.px(22)),
            selection_option_font=ui.FONT_BODY, selection_option_font_size=ui.fs(ui.SIZE_SMALL),
            selection_option_font_color=ui.TEXT, selection_option_selected_bgcolor=ui.SURFACE_3,
            selection_option_selected_font_color=ui.ACCENT, selection_option_border_width=0,
            selection_option_padding=(ui.px(10), ui.px(14)),
            scrollbar_color=ui.SURFACE_2, scrollbar_slider_color=ui.SURFACE_3,
            scrollbar_slider_hover_color=ui.MUTED, scrollbar_thick=max(6, ui.px(8)),
            placeholder="Select", placeholder_add_to_selection_box=False)
        return d

    def _toggle(self, menu, default, onchange, widget_id=""):
        return menu.add.toggle_switch(
            "", default, onchange=onchange, single_click=True, toggleswitch_id=widget_id, state_text=("Off", "On"),
            width=ui.px(110), font_size=ui.fs(ui.SIZE_SMALL),
            state_text_font=ui.FONT_BODY_BOLD, state_text_font_size=ui.fs(ui.SIZE_SMALL),
            state_color=(ui.SURFACE_3, ui.ACCENT), state_text_font_color=(ui.MUTED, ui.ON_ACCENT),
            slider_color=ui.TEXT, slider_thickness=0, switch_border_color=ui.LINE,
            switch_border_width=max(1, ui.px(1.5)), switch_height=1.6, switch_margin=(0, 0))

    def _slider(self, menu, default, range_values, increment, onchange, width):
        """Range slider that follows the pointer freely and settles on a multiple of `increment`
        when released. The value passed to `onchange` is always snapped."""
        low, high = range_values

        def snap(value):
            return max(low, min(high, low + round((value - low) / increment) * increment))

        def changed(value):
            onchange(snap(value))

        slider = menu.add.range_slider(
            "", default, range_values, increment=increment, onchange=changed, width=width,
            font_size=ui.fs(ui.SIZE_SMALL), range_margin=(0, 0),
            range_line_color=ui.SURFACE_3, range_line_height=max(2, ui.px(6)),
            range_box_color=ui.ACCENT, range_box_single_slider=True, range_box_height_factor=0.32,
            range_text_value_enabled=False, slider_color=ui.TEXT, slider_selected_color=ui.ACCENT,
            slider_thickness=max(8, ui.px(16)), slider_height_factor=0.9, slider_sel_highlight_enabled=False,
            slider_text_value_enabled=False, value_format=lambda x: "", repeat_keys=True)
        slider.snap_value = snap
        # A generous grab area around the handle (the default is the handle itself)
        grab = ui.px(26)
        raw_rect = slider._get_slider_inflate_rect
        slider._get_slider_inflate_rect = lambda pos, inflate=None, **kw: raw_rect(
            pos, inflate if inflate is not None else ((grab, grab) if kw.get("to_real_position") else None), **kw)
        self._sliders.append(slider)
        return slider

    # ================================================================ painters
    def _paint_button(self, surface, rect, d, hovered, focused, disabled):
        ui.button(surface, rect, d["label"], variant=d.get("variant", "secondary"), hovered=hovered,
                  focused=focused, disabled=disabled, icon_name=d.get("icon"))

    def _paint_main_primary(self, surface, rect, d, hovered, focused, disabled):
        fill = (255, 222, 110) if hovered else ui.ACCENT
        ui.fill_rect(surface, fill, rect, ui.radius(12))
        if focused:
            ui.focus_ring(surface, rect, ui.radius(12), color=ui.TEXT)
        fnt = ui.display_font(ui.SIZE_H3 + 4)
        ui.draw_text(surface, d["label"], fnt, ui.ON_ACCENT, (rect.x + ui.px(24), rect.centery + ui.px(2)), "midleft")
        meta = d.get("meta")
        if meta:
            ui.draw_text(surface, meta, ui.body_font(ui.SIZE_SMALL, bold=True), ui.ON_ACCENT,
                         (rect.right - ui.px(24), rect.centery), "midright")

    def _paint_nav(self, surface, rect, d, hovered, focused, disabled):
        if hovered:
            ui.fill_rect(surface, ui.SURFACE_2, rect, ui.radius(10))
            bar = pygame.Rect(rect.x, rect.y + ui.px(14), max(3, ui.px(4)), rect.height - ui.px(28))
            ui.fill_rect(surface, ui.ACCENT, bar, bar.width // 2)
        if focused:
            ui.focus_ring(surface, rect, ui.radius(10))
        fnt = ui.display_font(ui.SIZE_H3 + 2)
        ui.draw_text(surface, d["label"], fnt, ui.TEXT if hovered else (205, 209, 216),
                     (rect.x + ui.px(24), rect.centery + ui.px(2)), "midleft")
        meta = d.get("meta")
        if meta:
            ui.draw_text(surface, meta, ui.body_font(ui.SIZE_SMALL), ui.MUTED,
                         (rect.right - ui.px(20), rect.centery), "midright")

    def _paint_mode_card(self, surface, rect, d, hovered, focused, disabled):
        mode = d["mode"]
        color = ui.MODE_COLORS.get(mode, ui.ACCENT)
        rad = ui.radius(14)
        ui.fill_rect(surface, ui.SURFACE_2 if hovered else ui.SURFACE, rect, rad)
        ui.fill_rect(surface, color if hovered else ui.LINE, rect, rad, width=max(1, ui.px(2 if hovered else 1.5)))
        if focused:
            ui.focus_ring(surface, rect, rad)

        pad = ui.px(24)
        name_font = ui.display_font(ui.SIZE_H2)
        desc_font = ui.body_font(ui.SIZE_SMALL)
        config = self.game_modes[mode]
        x = rect.x + pad
        # Name line: color marker, name, optional "Current"
        name_cy = rect.centery + ui.px(2) if d.get("wide") else rect.y + pad + name_font.get_height() // 2
        cell = ui.px(32)
        marker = ui.mode_icon(mode, cell)
        if marker:
            surface.blit(marker, (x, name_cy - cell // 2 - ui.px(2)))
        marker_w = cell
        name_r = ui.draw_text(surface, config["name"], name_font, ui.TEXT, (x + marker_w + ui.px(12), name_cy), "midleft")
        if d.get("current"):
            ui.draw_text(surface, "Current", ui.body_font(ui.SIZE_CAPTION, bold=True), ui.MUTED,
                         (rect.right - pad, name_cy - ui.px(2)), "midright")

        if d.get("wide"):
            avail = rect.right - pad - name_r.right - ui.px(32) - (ui.px(90) if d.get("current") else 0)
            if avail > ui.px(160):
                ui.draw_text(surface, ui.ellipsize(config["description"], desc_font, avail), desc_font, ui.MUTED,
                             (name_r.right + ui.px(28), rect.centery), "midleft")
            return

        y = name_r.bottom + ui.px(4)
        width = rect.width - 2 * pad
        lines = ui.wrap(config["description"], desc_font, width)
        max_lines = max(1, (rect.bottom - pad + ui.px(6) - y) // desc_font.get_linesize())
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = ui.ellipsize(lines[-1] + " ...", desc_font, width)
        for line in lines:
            ui.draw_text(surface, line, desc_font, ui.MUTED, (x, y))
            y += desc_font.get_linesize()

    def _paint_tab(self, surface, rect, d, hovered, focused, disabled):
        selected = d.get("selected")
        rad = ui.radius(10)
        if selected:
            ui.fill_rect(surface, ui.SURFACE_3, rect, rad)
        elif hovered:
            ui.fill_rect(surface, ui.SURFACE_2, rect, rad)
        if focused:
            ui.focus_ring(surface, rect, rad)
        fnt = ui.body_font(ui.SIZE_SMALL + 1, bold=True)
        ui.draw_text(surface, d["label"], fnt, ui.TEXT if selected or hovered else ui.MUTED, rect.center, "center")

    # ================================================================ page builders
    def _create_menus(self):
        """Create or recreate every page for the current window size"""
        screen = pygame.display.get_surface()
        if screen:
            self.width, self.height = screen.get_size()
        self.L = _Layout(self.width, self.height)
        self._build_theme()
        self._ach_icon_cache = {}
        previous = getattr(self, "current_menu", None)
        previous_key = None
        for name in ("settings_menu", "controls_menu", "difficulty_menu", "personal_best_menu",
                     "time_selection_menu", "moves_selection_menu", "user_setup_menu", "user_edit_menu",
                     "achievements_menu", "quit_confirmation_menu"):
            if previous is not None and getattr(self, name, None) is previous:
                previous_key = name
        self.pages = {}
        self._sliders = []
        self.hover_widget = None
        self.header_back_rect = None

        L = self.L
        self.difficulty_menu = self._page("Choose a mode", self._back_to_main)
        self._build_modes_page(self.difficulty_menu)

        self.settings_menu = self._page("Settings", self._back_to_main, width=min(L.content_w, ui.px(1000)))
        self._build_settings_page(self.settings_menu)
        self.audio_settings_menu = self.settings_menu

        self.controls_menu = self._page("Controls", self._back_to_main)
        self._build_controls_page(self.controls_menu)

        self.personal_best_menu = self._page("Statistics", self._back_to_main)
        self._create_personal_best_content()

        self.achievements_menu = self._page("Achievements", self._back_to_main, width=min(L.content_w, ui.px(1100)))
        self._create_achievements_content()

        challenge_w = min(L.content_w, ui.px(760))
        self.time_selection_menu = self._page("Limited Time", self._back_to_difficulty, width=challenge_w)
        self._build_limit_page(self.time_selection_menu, "time")
        self.moves_selection_menu = self._page("Limited Moves", self._back_to_difficulty, width=challenge_w)
        self._build_limit_page(self.moves_selection_menu, "moves")

        form_w = min(L.content_w, ui.px(620))
        self.user_setup_menu = self._page("", self._back_from_user_setup, kind="dialog", width=form_w, motion_select=False)
        self._create_user_setup_content()
        self.user_edit_menu = self._page("", self._back_to_statistics, kind="dialog", width=form_w, motion_select=False)
        self._create_user_edit_content()

        self.quit_confirmation_menu = self._page("", self._cancel_quit, kind="dialog", width=min(L.content_w, ui.px(560)))
        self._build_quit_dialog(self.quit_confirmation_menu)

        self.main_menu = None
        self.refresh_main_menu_buttons()

        self.current_menu = getattr(self, previous_key) if previous_key else self.main_menu

    def update_dimensions(self, width, height):
        if (width, height) == (self.width, self.height) and getattr(self, "main_menu", None):
            return
        self.width, self.height = width, height
        self._create_menus()
        self.resolution_changed_flag = False

    def refresh_main_menu_buttons(self):
        """(Re)build the main menu so its buttons match the game state"""
        if not hasattr(self, "L"):
            return
        old = getattr(self, "main_menu", None)
        if old is not None:
            self.pages.pop(old, None)
        menu = self._page("", self._close_from_main, kind="main")
        L = self.L
        inner = L.panel_w - 2 * L.panel_pad
        page = self.pages[menu]
        page["width"] = inner

        # Logo: cube on the left, name on the right, left aligned in the panel
        logo = ui.logo("rubiks_logo_horizontal", inner, ui.px(190))
        if logo is not None:
            row = pygame.Surface((inner, logo.get_height()), pygame.SRCALPHA)
            row.blit(logo, (0, 0))
            self._surface(menu, row)
        self._spacer(menu, 48)

        in_game = self._in_game()
        if in_game:
            mode_name = self.game_modes.get(self.selected_difficulty, {}).get("name", "")
            self._custom_button(menu, "Resume", self._play_current_difficulty, inner, ui.px(72),
                                self._paint_main_primary, button_id="main_primary", meta=mode_name)
        else:
            self._custom_button(menu, "Play", self._open_difficulty_select, inner, ui.px(72),
                                self._paint_main_primary, button_id="main_primary")
        self._spacer(menu, 18)

        unlocked, total = self.achievements_manager.get_unlocked_count()
        items = []
        if in_game:
            items.append(("Change mode", self._open_difficulty_select, None))
        items += [
            ("Statistics", self._open_personal_best, None),
            ("Achievements", self._open_achievements, f"{unlocked} / {total}"),
            ("Settings", self._open_settings, None),
            ("Controls", self._open_controls, None),
            ("Quit", self._show_quit_confirmation, None),
        ]
        for label, action, meta in items:
            self._custom_button(menu, label, action, inner, ui.px(58), self._paint_nav, meta=meta)
            self._spacer(menu, 2)

        self.main_menu = menu
        if old is not None and getattr(self, "current_menu", None) is old:
            self.current_menu = menu

    def _build_modes_page(self, menu):
        menu.clear()
        L = self.L
        cw = self.pages[menu]["width"]
        gap = L.gap
        in_game = self._in_game()
        current = self.selected_difficulty if in_game else None

        def card(mode_key, w, h, action, wide=False):
            return self._custom_button(menu, self.game_modes[mode_key]["name"], action, w, h,
                                       self._paint_mode_card, button_id=f"mode_{mode_key}",
                                       mode=mode_key, wide=wide, current=(mode_key == current))

        self._section(menu, "Practice", top=24)
        card("freeplay", cw, ui.px(96), lambda: self._start_game("freeplay"), wide=True)

        card_w = (cw - 2 * gap) // 3
        card_h = ui.px(172)
        rows = [
            ("Solve", [("easy", lambda: self._start_game("easy")),
                       ("medium", lambda: self._start_game("medium")),
                       ("hard", lambda: self._start_game("hard"))]),
            ("Challenges", [("limited_time", self._open_time_selection),
                            ("limited_moves", self._open_moves_selection),
                            ("daily_cube", lambda: self._start_game("daily_cube"))]),
        ]
        for title, modes in rows:
            self._section(menu, title)
            frame = menu.add.frame_h(cw, card_h, padding=0)
            frame._pack_margin_warning = False
            for i, (mode_key, action) in enumerate(modes):
                if i:
                    frame.pack(menu.add.horizontal_margin(gap))
                frame.pack(card(mode_key, card_w, card_h, action))
        self._spacer(menu, 48)

    def _build_limit_page(self, menu, kind):
        width = self.pages[menu]["width"]
        self._spacer(menu, 24)
        if kind == "time":
            intro = "Pick how long you get to solve a 15 move scramble."
            value = self._format_time_display(self.selected_time_limit).replace(" ", "  ")
            options = self.time_limit_options
            default = options.index(self.selected_time_limit)
            onchange = self._on_time_limit_change_and_update_display
            ends = (self._format_time_display(options[0]), self._format_time_display(options[-1]))
            start = self._start_limited_time_game
        else:
            intro = "Pick your move budget for a 15 move scramble."
            value = f"{self.selected_move_limit}  moves"
            options = self.move_limit_options
            default = options.index(self.selected_move_limit)
            onchange = self._on_move_limit_change_and_update_display
            ends = (f"{options[0]} moves", f"{options[-1]} moves")
            start = self._start_limited_moves_game

        self._text(menu, intro, ui.body_font(), ui.MUTED)
        self._spacer(menu, 40)

        value_panel_h = ui.px(150)
        label = menu.add.label(value, font_name=ui.FONT_DISPLAY, font_size=ui.fs(ui.SIZE_DISPLAY),
                               font_color=ui.TEXT)
        self._size_widget(label, width, value_panel_h)
        if kind == "time":
            self.time_display_label = label
        else:
            self.moves_display_label = label

        self._spacer(menu, 16)
        self._slider(menu, default, (0, len(options) - 1), 1, onchange, width)
        self._spacer(menu, 10)
        small = ui.body_font(ui.SIZE_SMALL)
        ends_surf = pygame.Surface((width, small.get_height()), pygame.SRCALPHA)
        ui.draw_text(ends_surf, ends[0], small, ui.MUTED, (0, 0))
        ui.draw_text(ends_surf, ends[1], small, ui.MUTED, (width, 0), "topright")
        self._surface(menu, ends_surf)
        self._spacer(menu, 48)
        self._button(menu, "Start challenge", start, w=width, h=ui.px(64), variant="primary")
        self._spacer(menu, 48)

    def _build_settings_page(self, menu):
        menu.clear()
        self.resolution_select = None
        self.apply_button = None
        self.volume_labels = {}
        width = self.pages[menu]["width"]
        control_w = min(ui.px(440), int(width * 0.5))

        # Display
        self._section(menu, "Display", top=20)
        mode_index = display_manager.MODES.index(self.pending_mode)
        mode_items = [(display_manager.MODE_LABELS[m], i) for i, m in enumerate(display_manager.MODES)]
        mode_select = self._dropselect(menu, mode_items, mode_index, self._on_display_mode_change, control_w,
                                       visible=3, widget_id="display_mode")
        self._row(menu, "Display mode", [mode_select],
                  desc="Borderless fills the monitor at its native resolution.")

        if display_manager.num_displays() > 1:
            monitor_items = [(display_manager.display_label(i), i) for i in range(display_manager.num_displays())]
            monitor_select = self._dropselect(menu, monitor_items, self.pending_index, self._on_monitor_change,
                                              control_w, visible=4, widget_id="display_monitor")
            self._row(menu, "Monitor", [monitor_select])

        options = self._pending_options()
        if self.pending_size not in options:
            self.pending_size = display_manager.nearest(self.pending_size, options)
        self.resolution_select = self._dropselect(menu, self._resolution_items(), options.index(self.pending_size),
                                                  self._on_resolution_change, control_w, visible=7,
                                                  widget_id="display_resolution")
        self.resolution_select.readonly = self.pending_mode == "borderless"
        self._row(menu, "Resolution", [self.resolution_select],
                  desc="Only sizes your monitor supports are listed.")

        # HDR options exist only on monitors where Windows HDR is on; brightness only while HDR is on
        hdr_available, peak_nits = hdr_output.display_hdr_info(self.pending_index)
        self.paper_white_label = None
        if hdr_available:
            hdr_toggle = self._toggle(menu, self.pending_hdr, self._on_hdr_toggle, "display_hdr")
            peak = f" (peak about {int(round(peak_nits))} nits)" if peak_nits else ""
            self._row(menu, "HDR", [hdr_toggle], desc=f"Use the full HDR range of this monitor{peak}.")
            if self.pending_hdr:
                low, high = hdr_output.PAPER_WHITE_RANGE
                value = max(low, min(high, int(round(self.hdr_paper_white / 5) * 5)))
                slider = self._slider(menu, value, (low, high), 5, self._on_paper_white_change, control_w - ui.px(118))
                self.paper_white_label = menu.add.label(f"{value:>3} nits", font_name=ui.FONT_MONO,
                                                        font_size=ui.fs(ui.SIZE_SMALL), font_color=ui.MUTED)
                self._row(menu, "HDR brightness", [self.paper_white_label, slider],
                          desc="Brightness of white menus and the cube, in steps of 5 nits.")

        self.apply_button = self._button(menu, "Apply", self._apply_settings, w=ui.px(200), h=ui.px(54),
                                         variant="primary", button_id="apply_display")
        self._row(menu, "Apply display changes", [self.apply_button])
        self._update_settings_changed()

        self._row(menu, "Show FPS counter", [self._toggle(menu, self.show_fps, self._on_fps_toggle)],
                  separator=False)

        # Audio
        self._section(menu, "Audio")
        mono = ui.FONT_MONO
        slider_w = control_w - ui.px(86)
        for key, title in (("master_volume", "Master volume"), ("music_volume", "Music"),
                           ("effects_volume", "Sound effects"), ("menu_volume", "Menu sounds")):
            value = getattr(self, key)
            slider = self._slider(menu, value, (0, 100), 5, lambda v, k=key: self._set_volume(k, v), slider_w)
            label = menu.add.label(f"{value:>3}%", font_name=mono, font_size=ui.fs(ui.SIZE_SMALL), font_color=ui.MUTED)
            self.volume_labels[key] = label
            self._row(menu, title, [label, slider], separator=key != "menu_volume")

        # Gameplay
        self._section(menu, "Gameplay")
        self._row(menu, "Show hints", [self._toggle(menu, self.hints_enabled, self._on_hints_toggle)],
                  desc="Offer a hint after 30 seconds without a move on Easy, Medium and Hard.", separator=False)
        self._spacer(menu, 48)

    def _build_controls_page(self, menu):
        width = self.pages[menu]["width"]
        sections = [
            ("General", [
                ("Open or close the menu", [["Esc"]]),
                ("Toggle fullscreen", [["F11"]]),
                ("Undo last move", [["Z"]]),
                ("Scramble (Free Play)", [["X"]]),
                ("Auto rotate camera", [["Space"]]),
                ("Reset camera", [["T"]]),
                ("Debug view", [["Ctrl", "B"]]),
            ]),
            ("Mouse", [
                ("Turn a layer", [["Left drag"]]),
                ("Orbit the camera", [["Right drag"]]),
                ("Orbit with keys", [["Arrow keys"]]),
            ]),
            ("Face turns", [
                ("Right", [["R"], ["Shift", "R"]]),
                ("Left", [["L"], ["Shift", "L"]]),
                ("Up", [["U"], ["Shift", "U"]]),
                ("Down", [["D"], ["Shift", "D"]]),
                ("Front", [["F"], ["Shift", "F"]]),
                ("Back", [["B"], ["Shift", "B"]]),
            ]),
            ("Slice turns", [
                ("Middle", [["M"], ["Shift", "M"]]),
                ("Equator", [["E"], ["Shift", "E"]]),
                ("Standing", [["S"], ["Shift", "S"]]),
            ]),
        ]
        two_cols = width >= ui.px(980)
        gap = ui.px(56)
        col_w = (width - gap) // 2 if two_cols else width
        columns = [[sections[0], sections[1]], [sections[2], sections[3]]] if two_cols else [sections]

        head = ui.display_font(ui.SIZE_H3)
        body = ui.body_font()
        small = ui.body_font(ui.SIZE_SMALL)
        key_font = ui.mono_font(ui.SIZE_SMALL, bold=True)
        row_h = ui.px(52)

        def column_height(col):
            return sum(head.get_height() + ui.px(14) + len(rows) * row_h + ui.px(40) for _, rows in col)

        height = max(column_height(c) for c in columns)
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        for ci, col in enumerate(columns):
            x0 = ci * (col_w + gap)
            y = 0
            for title, rows in col:
                ui.draw_text(surf, title, head, ui.MUTED, (x0, y))
                y += head.get_height() + ui.px(14)
                for desc, combos in rows:
                    pygame.draw.line(surf, ui.LINE, (x0, y), (x0 + col_w, y), max(1, ui.px(1.5)))
                    # Key combos right aligned: draw into a strip, then place it
                    chips = []
                    for ci2, combo in enumerate(combos):
                        if ci2:
                            chips.append(("text", "or"))
                        for ki, key in enumerate(combo):
                            if ki:
                                chips.append(("text", "+"))
                            chips.append(("key", key))
                    strip = pygame.Surface((col_w, row_h), pygame.SRCALPHA)
                    cx = 0
                    for kind, value in chips:
                        if kind == "key":
                            kh = key_font.get_height() + ui.px(10)
                            cx += ui.keycap(strip, cx, (row_h - kh) // 2, value, key_font) + ui.px(6)
                        else:
                            r = ui.draw_text(strip, value, small, ui.MUTED, (cx + ui.px(2), row_h // 2), "midleft")
                            cx = r.right + ui.px(8)
                    surf.blit(strip, (x0 + col_w - cx + ui.px(6), y), (0, 0, cx, row_h))
                    ui.draw_text(surf, ui.ellipsize(desc, body, col_w - cx - ui.px(16)), body, ui.TEXT,
                                 (x0, y + row_h // 2), "midleft")
                    y += row_h
                y += ui.px(40)
        self._spacer(menu, 28)
        self._surface(menu, surf)
        self._spacer(menu, 24)

    def _build_quit_dialog(self, menu):
        width = self.pages[menu]["width"]
        self._surface(menu, self._text_surface("Quit the game?", ui.display_font(ui.SIZE_H1), ui.TEXT, width))
        self._spacer(menu, 8)
        self._text(menu, "Any solve in progress will be lost.", ui.body_font(), ui.MUTED)
        self._spacer(menu, 36)
        gap = ui.px(16)
        bw = (width - gap) // 2
        frame = menu.add.frame_h(width, ui.px(60), padding=0)
        frame._pack_margin_warning = False
        frame.pack(self._button(menu, "Cancel", self._cancel_quit, w=bw, h=ui.px(60), button_id="quit_cancel"))
        frame.pack(menu.add.horizontal_margin(gap))
        frame.pack(self._button(menu, "Quit", self._quit_game, w=bw, h=ui.px(60), variant="danger",
                                button_id="quit_confirm"))

    # ---------------------------------------------------------------- statistics
    def _create_personal_best_content(self, select_id=None, keep_selection=False):
        menu = self.personal_best_menu
        if keep_selection and select_id is None:
            sel = menu.get_selected_widget()
            select_id = sel.get_id() if sel is not None else None
        menu.clear()
        width = self.pages[menu]["width"]

        # Profile strip
        self._spacer(menu, 20)
        username = self.user_manager.get_username() or "Guest"
        region = self.user_manager.get_region() or ""
        edit_btn = self._button(menu, "Edit profile", self._open_user_edit, w=ui.px(220), h=ui.px(54),
                                icon_name="user-edit", button_id="edit_profile")
        name_font = ui.display_font(ui.SIZE_H2)
        small = ui.body_font(ui.SIZE_SMALL)
        strip_w = width - edit_btn.get_width() - ui.px(24)
        strip = pygame.Surface((strip_w, name_font.get_height() + small.get_height()), pygame.SRCALPHA)
        ui.draw_text(strip, ui.ellipsize(username, name_font, strip_w), name_font, ui.TEXT, (0, 0))
        if region:
            ui.draw_text(strip, f"Region: {region}", small, ui.MUTED, (0, name_font.get_height() - ui.px(6)))
        frame = menu.add.frame_h(width, max(strip.get_height(), edit_btn.get_height()), padding=0)
        frame._pack_margin_warning = False
        frame.pack(menu.add.surface(strip), align=ALIGN_LEFT, vertical_position=POSITION_CENTER)
        frame.pack(edit_btn, align=ALIGN_RIGHT, vertical_position=POSITION_CENTER)
        self._spacer(menu, 28)

        # Tabs
        tabs = [("personal_records", "Personal records"), ("global_leaderboard", "Global leaderboard"),
                ("daily_leaderboard", "Daily leaderboard")]
        tab_gap = ui.px(8)
        tab_w = min(ui.px(270), (width - 2 * tab_gap) // 3)
        tab_h = ui.px(52)
        frame = menu.add.frame_h(width, tab_h, padding=0)
        frame._pack_margin_warning = False
        for i, (key, label) in enumerate(tabs):
            if i:
                frame.pack(menu.add.horizontal_margin(tab_gap))
            frame.pack(self._custom_button(menu, label, lambda k=key: self._switch_tab(k), tab_w, tab_h,
                                           self._paint_tab, button_id=f"tab_{key}",
                                           selected=(self.statistics_tab == key)))
        self._spacer(menu, 8)
        self._hairline(menu)
        self._spacer(menu, 24)

        if self.statistics_tab == "personal_records":
            self._create_personal_records_content()
        elif self.statistics_tab == "global_leaderboard":
            self._create_leaderboard_content()
        else:
            self._create_daily_leaderboard_content()
        self._spacer(menu, 48)

        if select_id:
            try:
                menu.select_widget(select_id)
            except Exception:
                pass

    def _stat_tiles(self, menu, tiles):
        width = self.pages[menu]["width"]
        gap = ui.px(16)
        n = len(tiles)
        tile_w = (width - gap * (n - 1)) // n
        label_f = ui.body_font(ui.SIZE_SMALL)
        value_f = ui.mono_font(ui.SIZE_H2, bold=True)
        tile_h = ui.px(22) * 2 + label_f.get_height() + ui.px(6) + value_f.get_height()
        surf = pygame.Surface((width, tile_h), pygame.SRCALPHA)
        for i, (label, value) in enumerate(tiles):
            r = pygame.Rect(i * (tile_w + gap), 0, tile_w, tile_h)
            ui.panel(surf, r, fill=ui.SURFACE, border=ui.LINE)
            ui.draw_text(surf, label, label_f, ui.MUTED, (r.x + ui.px(22), r.y + ui.px(22)))
            ui.draw_text(surf, value, value_f, ui.TEXT, (r.x + ui.px(22), r.y + ui.px(28) + label_f.get_height()))
        self._surface(menu, surf)

    def _table(self, menu, columns, rows):
        """Draw a table as one surface.

        columns: list of (title, weight, align) where align is "left" or "right"
        rows:    list of dicts with "cells" (strings or ("mode", key)), optional "highlight", "rank"
        """
        width = self.pages[menu]["width"]
        head_f = ui.body_font(ui.SIZE_SMALL)
        cell_f = ui.body_font()
        mono_f = ui.mono_font(ui.SIZE_SMALL + 1)
        head_h = ui.px(44)
        row_h = ui.px(58)
        pad = ui.px(18)
        total_w = sum(c[1] for c in columns)
        inner = width - 2 * pad
        xs = []
        x = pad
        for _, weight, _ in columns:
            w = int(inner * weight / total_w)
            xs.append((x, w))
            x += w

        surf = pygame.Surface((width, head_h + row_h * len(rows)), pygame.SRCALPHA)
        for (title, _, align), (cx, cw) in zip(columns, xs):
            if align == "right":
                ui.draw_text(surf, title, head_f, ui.MUTED, (cx + cw, head_h // 2), "midright")
            else:
                ui.draw_text(surf, title, head_f, ui.MUTED, (cx, head_h // 2), "midleft")
        pygame.draw.line(surf, ui.LINE, (0, head_h - 1), (width, head_h - 1), max(1, ui.px(1.5)))

        for ri, row in enumerate(rows):
            y = head_h + ri * row_h
            if row.get("highlight"):
                ui.fill_rect(surf, ui.SURFACE_2, (0, y + ui.px(3), width, row_h - ui.px(6)), ui.radius(8))
                ui.fill_rect(surf, ui.ACCENT, (0, y + ui.px(14), max(3, ui.px(4)), row_h - ui.px(28)), ui.px(2))
            elif ri:
                pygame.draw.line(surf, (32, 37, 45), (pad, y), (width - pad, y), 1)
            cy = y + row_h // 2
            for ci, (cell, (title, _, align), (cx, cw)) in enumerate(zip(row["cells"], columns, xs)):
                color = ui.TEXT
                fnt = cell_f
                if isinstance(cell, tuple) and cell[0] == "mode":
                    key = cell[1]
                    sq = ui.px(22)
                    mark = ui.mode_icon(key, sq)
                    if mark:
                        surf.blit(mark, (cx, cy - sq // 2))
                    name = ui.MODE_NAMES.get(key, str(key).replace("_", " ").title())
                    ui.draw_text(surf, ui.ellipsize(name, fnt, cw - sq - ui.px(14)), fnt, color,
                                 (cx + sq + ui.px(12), cy), "midleft")
                    continue
                text = str(cell)
                if ci == 0 and row.get("rank") is not None:
                    fnt = mono_f
                    color = ui.ACCENT if row["rank"] == 1 else ui.MUTED
                elif align == "right":
                    fnt = mono_f
                if text in ("-", ""):
                    color = ui.DIM
                text = ui.ellipsize(text, fnt, cw - ui.px(12))
                if align == "right":
                    ui.draw_text(surf, text, fnt, color, (cx + cw, cy), "midright")
                else:
                    ui.draw_text(surf, text, fnt, color, (cx, cy), "midleft")
        self._surface(menu, surf)

    def _message(self, menu, title, body=None, title_color=ui.TEXT):
        self._spacer(menu, 24)
        self._text(menu, title, ui.display_font(ui.SIZE_H2), title_color)
        if body:
            self._spacer(menu, 4)
            self._text(menu, body, ui.body_font(), ui.MUTED)

    def _create_personal_records_content(self):
        menu = self.personal_best_menu
        pb = self.personal_best_manager
        unlocked, total = self.achievements_manager.get_unlocked_count()
        wins = pb.get_wins("limited_time") + pb.get_wins("limited_moves")
        self._stat_tiles(menu, [("Total solves", str(pb.get_total_solves())),
                                ("Challenges won", str(wins)),
                                ("Achievements", f"{unlocked} / {total}")])

        if not pb.has_records():
            self._message(menu, "No solves yet",
                          "Finish a cube on Easy, Medium or Hard and your best times show up here.")
            self._spacer(menu, 24)
            cta = self._button(menu, "Choose a mode", self._open_difficulty_select, w=ui.px(260), h=ui.px(56),
                               variant="primary")
            row = menu.add.frame_h(self.pages[menu]["width"], cta.get_height(), padding=0)
            row._pack_margin_warning = False
            row.pack(cta, align=ALIGN_LEFT)
        else:
            self._section(menu, "Best solves")
            rows = []
            for difficulty in ("easy", "medium", "hard"):
                r = pb.get_records(difficulty)
                rows.append({"cells": [
                    ("mode", difficulty),
                    ui.format_clock(r["best_time"], decimals=True) if r.get("best_time") is not None else "-",
                    str(r["best_moves"]) if r.get("best_moves") is not None else "-",
                    f"{r['best_tps']:.2f}" if r.get("best_tps") else "-",
                    str(r.get("total_solves", 0)),
                ]})
            self._table(menu, [("Mode", 3, "left"), ("Best time", 2, "right"), ("Fewest moves", 2, "right"),
                               ("Best TPS", 2, "right"), ("Solves", 1.5, "right")], rows)

        challenge_rows = []
        for mode in ("limited_time", "limited_moves"):
            w, l = pb.get_wins(mode), pb.get_losses(mode)
            if w or l:
                challenge_rows.append({"cells": [("mode", mode), str(w), str(l), f"{pb.get_win_rate(mode):.0f}%"]})
        if challenge_rows:
            self._section(menu, "Challenges")
            self._table(menu, [("Mode", 3, "left"), ("Wins", 2, "right"), ("Losses", 2, "right"),
                               ("Win rate", 2, "right")], challenge_rows)

    def _leaderboard_state(self, loading, error, offline, data, empty_title, empty_body):
        """Shows loading, error, offline and empty states. Returns True if a message was shown."""
        menu = self.personal_best_menu
        if error == "not_configured":
            self._message(menu, "Leaderboard unavailable", "Online records are not set up in this build.")
        elif loading:
            self._message(menu, "Loading", "Fetching the latest times.")
        elif error:
            self._message(menu, "Could not load the leaderboard", "Try refreshing in a moment.", ui.DANGER)
        elif not data and offline:
            self._message(menu, "You are offline", "Leaderboards need an internet connection. "
                                                   "Check your connection and refresh.")
        elif not data:
            self._message(menu, empty_title, empty_body)
        else:
            return False
        return True

    def _filters_row(self, menu, filters, refresh_action):
        """Dropdown filters and a refresh button in one row"""
        width = self.pages[menu]["width"]
        refresh = self._button(menu, "Refresh", refresh_action, w=ui.px(160), h=ui.px(54), button_id="lb_refresh")
        label_f = ui.body_font(ui.SIZE_SMALL, bold=True)
        frame = menu.add.frame_h(width, ui.px(64), padding=0)
        frame._pack_margin_warning = False
        for i, (title, items, default, onchange, wid) in enumerate(filters):
            label = menu.add.surface(ui.render(title, label_f, ui.MUTED))
            frame.pack(label, align=ALIGN_LEFT, vertical_position=POSITION_CENTER, margin=(ui.px(32) if i else 0, 0))
            drop = self._dropselect(menu, items, default, onchange, ui.px(240), visible=6, widget_id=wid)
            frame.pack(drop, align=ALIGN_LEFT, vertical_position=POSITION_CENTER, margin=(ui.px(12), 0))
        frame.pack(refresh, align=ALIGN_RIGHT, vertical_position=POSITION_CENTER)
        self._spacer(menu, 20)

    def _format_lb_time(self, value):
        return ui.format_clock(value, decimals=True) if value is not None else "-"

    def _create_leaderboard_content(self):
        menu = self.personal_best_menu
        if not (self.supabase_manager and self.supabase_manager.is_configured()):
            self._leaderboard_state(False, "not_configured", False, [], "", "")
            return
        mode_items = [(GAME_MODE_DISPLAY.get(m, m), i) for i, m in enumerate(GAME_MODE_OPTIONS)]
        region_items = [(REGION_DISPLAY.get(r, r), i) for i, r in enumerate(REGION_OPTIONS)]
        mode_index = GAME_MODE_OPTIONS.index(self.leaderboard_filter_mode) if self.leaderboard_filter_mode in GAME_MODE_OPTIONS else 0
        region_index = REGION_OPTIONS.index(self.leaderboard_filter_region) if self.leaderboard_filter_region in REGION_OPTIONS else 0
        self._filters_row(menu, [("Mode", mode_items, mode_index, self._on_leaderboard_mode_filter_change, "lb_mode"),
                                 ("Region", region_items, region_index, self._on_leaderboard_region_filter_change, "lb_region")],
                          self._refresh_leaderboard)

        if self._leaderboard_state(self.leaderboard_loading, self.leaderboard_error, self.leaderboard_is_offline,
                                   self.leaderboard_data, "No records yet", "Be the first to post a time."):
            return

        me = self.user_manager.get_username() if self.user_manager else ""
        all_modes = self.leaderboard_filter_mode == "All Modes"
        rows = []
        for rank, entry in enumerate(self.leaderboard_data[:20], 1):
            name = entry.get("username", "Unknown")
            cells = [str(rank), name, entry.get("region", "-")]
            if all_modes:
                cells.append(("mode", entry.get("game_mode", "")))
            cells += [self._format_lb_time(entry.get("best_time")),
                      str(entry.get("best_moves")) if entry.get("best_moves") is not None else "-"]
            if not all_modes:
                cells.append(str(entry.get("total_solves", 0)))
            rows.append({"cells": cells, "rank": rank, "highlight": bool(me) and name == me})
        if all_modes:
            columns = [("#", 0.8, "left"), ("Player", 3.4, "left"), ("Region", 2, "left"), ("Mode", 2.4, "left"),
                       ("Best time", 1.9, "right"), ("Moves", 1.3, "right")]
        else:
            columns = [("#", 0.8, "left"), ("Player", 3.6, "left"), ("Region", 2.2, "left"),
                       ("Best time", 2, "right"), ("Moves", 1.4, "right"), ("Solves", 1.4, "right")]
        self._table(menu, columns, rows)
        if len(self.leaderboard_data) > 20:
            self._spacer(menu, 12)
            self._text(menu, f"Top 20 of {len(self.leaderboard_data)} players", ui.body_font(ui.SIZE_SMALL), ui.MUTED)

    def _create_daily_leaderboard_content(self):
        menu = self.personal_best_menu
        if not (self.supabase_manager and self.supabase_manager.is_configured()):
            self._leaderboard_state(False, "not_configured", False, [], "", "")
            return
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        self._text(menu, f"Today's Daily Cube, {date_str} (UTC). Everyone gets the same scramble.",
                   ui.body_font(), ui.MUTED)
        self._spacer(menu, 16)
        region_items = [(REGION_DISPLAY.get(r, r), i) for i, r in enumerate(REGION_OPTIONS)]
        region_index = REGION_OPTIONS.index(self.daily_leaderboard_filter_region) if self.daily_leaderboard_filter_region in REGION_OPTIONS else 0
        self._filters_row(menu, [("Region", region_items, region_index,
                                  self._on_daily_leaderboard_region_filter_change, "daily_region")],
                          self._refresh_daily_leaderboard)

        if self._leaderboard_state(self.daily_leaderboard_loading, self.daily_leaderboard_error,
                                   self.daily_leaderboard_is_offline, self.daily_leaderboard_data,
                                   "Nobody has solved today's cube yet",
                                   "Play Daily Cube from the mode screen to claim the top spot."):
            return

        me = self.user_manager.get_username() if self.user_manager else ""
        rows = []
        for rank, entry in enumerate(self.daily_leaderboard_data[:20], 1):
            name = entry.get("username", "Unknown")
            tps = entry.get("tps")
            rows.append({"cells": [str(rank), name, entry.get("region", "-"),
                                   self._format_lb_time(entry.get("solve_time")),
                                   str(entry.get("moves")) if entry.get("moves") is not None else "-",
                                   f"{tps:.2f}" if tps is not None else "-"],
                         "rank": rank, "highlight": bool(me) and name == me})
        self._table(menu, [("#", 0.8, "left"), ("Player", 3.6, "left"), ("Region", 2.2, "left"),
                           ("Time", 2, "right"), ("Moves", 1.4, "right"), ("TPS", 1.4, "right")], rows)
        if len(self.daily_leaderboard_data) > 20:
            self._spacer(menu, 12)
            self._text(menu, f"Top 20 of {len(self.daily_leaderboard_data)} players", ui.body_font(ui.SIZE_SMALL), ui.MUTED)

    # ---------------------------------------------------------------- achievements
    def _achievement_icon(self, path, size, unlocked):
        key = (path, size, unlocked)
        if key in self._ach_icon_cache:
            return self._ach_icon_cache[key]
        surf = None
        full = resource_path(path) if path else ""
        if full and os.path.exists(full):
            try:
                img = pygame.image.load(full).convert_alpha()
                surf = pygame.transform.smoothscale(img, (size, size))
                if not unlocked:
                    surf = pygame.transform.grayscale(surf)
                    surf.set_alpha(110)
            except Exception:
                surf = None
        self._ach_icon_cache[key] = surf
        return surf

    def _achievement_card(self, surf, rect, a):
        unlocked = a.get("unlocked", False)
        secret = a.get("secret", False) and not unlocked
        ui.panel(surf, rect, fill=ui.SURFACE, border=(ui.ACCENT if unlocked else ui.LINE))
        pad = ui.px(18)
        icon_size = min(rect.height - 2 * pad, ui.px(84))
        icon_rect = pygame.Rect(rect.x + pad, rect.centery - icon_size // 2, icon_size, icon_size)
        img = None if secret else self._achievement_icon(a.get("icon", ""), icon_size, unlocked)
        if img:
            surf.blit(img, icon_rect)
        else:
            ui.fill_rect(surf, ui.SURFACE_2, icon_rect, ui.radius(10))
            ui.draw_text(surf, "?", ui.display_font(ui.SIZE_H1), ui.DIM, icon_rect.center, "center")

        tx = icon_rect.right + ui.px(20)
        tw = rect.right - pad - tx
        name_f = ui.body_font(ui.SIZE_BODY, bold=True)
        desc_f = ui.body_font(ui.SIZE_SMALL - 1)
        name = "Secret achievement" if secret else a.get("name", "")
        desc = "Keep playing to discover it." if secret else a.get("description", "")
        y = rect.y + pad - ui.px(2)
        ui.draw_text(surf, ui.ellipsize(name, name_f, tw), name_f, ui.TEXT if unlocked else (205, 209, 216), (tx, y))
        y += name_f.get_linesize()
        lines = ui.wrap(desc, desc_f, tw)[:2]
        for line in lines:
            ui.draw_text(surf, line, desc_f, ui.MUTED, (tx, y))
            y += desc_f.get_linesize()

        bottom = rect.bottom - pad
        small = ui.body_font(ui.SIZE_CAPTION, bold=True)
        if unlocked:
            when = ""
            date = a.get("unlock_date")
            if date:
                try:
                    when = "  " + datetime.fromisoformat(str(date)).strftime("%d %b %Y")
                except Exception:
                    when = ""
            ui.draw_text(surf, f"Unlocked{when}", small, ui.ACCENT, (tx, bottom), "bottomleft")
        elif a.get("target", 1) > 1 and not secret:
            label = f"{a.get('progress', 0)} / {a.get('target', 1)}"
            lw = small.size(label)[0]
            bar = pygame.Rect(tx, bottom - ui.px(10), max(ui.px(40), tw - lw - ui.px(16)), max(3, ui.px(6)))
            bar.centery = bottom - small.get_height() // 2
            ui.progress_bar(surf, bar, a.get("progress_percentage", 0), color=ui.MUTED)
            ui.draw_text(surf, label, small, ui.MUTED, (tx + tw, bottom), "bottomright")
        else:
            ui.draw_text(surf, "Locked", small, ui.DIM, (tx, bottom), "bottomleft")

    def _create_achievements_content(self):
        menu = self.achievements_menu
        menu.clear()
        width = self.pages[menu]["width"]
        unlocked, total = self.achievements_manager.get_unlocked_count()
        by_category = self.achievements_manager.get_achievements_by_category()

        # Summary
        self._spacer(menu, 20)
        big = ui.display_font(ui.SIZE_H2)
        summary = pygame.Surface((width, big.get_height() + ui.px(22)), pygame.SRCALPHA)
        ui.draw_text(summary, f"{unlocked} of {total} unlocked", big, ui.TEXT, (0, 0))
        pct = int(round(unlocked / total * 100)) if total else 0
        ui.draw_text(summary, f"{pct}%", ui.mono_font(ui.SIZE_SMALL, bold=True), ui.MUTED,
                     (width, big.get_height() // 2), "midright")
        ui.progress_bar(summary, (0, big.get_height() + ui.px(8), width, max(4, ui.px(8))),
                        unlocked / total if total else 0)
        self._surface(menu, summary)

        names = {"beginner": "Beginner", "progression": "Progression", "speed": "Speed",
                 "challenge": "Challenges", "daily": "Daily", "efficiency": "Efficiency", "secret": "Secret"}
        order = ["beginner", "progression", "speed", "challenge", "daily", "efficiency", "secret"]
        order += [c for c in by_category if c not in order]
        cols = 2 if width >= ui.px(900) else 1
        gap = ui.px(16)
        card_w = (width - gap * (cols - 1)) // cols
        # Height from the real line heights (fonts have a minimum size on small screens)
        card_h = (ui.px(18) * 2 + ui.body_font(ui.SIZE_BODY, bold=True).get_linesize()
                  + 2 * ui.body_font(ui.SIZE_SMALL - 1).get_linesize()
                  + ui.body_font(ui.SIZE_CAPTION, bold=True).get_height() + ui.px(4))
        for category in order:
            items = by_category.get(category)
            if not items:
                continue
            self._section(menu, names.get(category, category.title()))
            n_rows = (len(items) + cols - 1) // cols
            surf = pygame.Surface((width, n_rows * card_h + (n_rows - 1) * gap), pygame.SRCALPHA)
            for i, a in enumerate(items):
                r, c = divmod(i, cols)
                self._achievement_card(surf, pygame.Rect(c * (card_w + gap), r * (card_h + gap), card_w, card_h), a)
            self._surface(menu, surf)
        self._spacer(menu, 48)

    # ---------------------------------------------------------------- profile forms
    def _profile_form(self, menu, title, intro, input_id, onchange, primary, secondary):
        menu.clear()
        width = self.pages[menu]["width"]
        self._surface(menu, self._text_surface(title, ui.display_font(ui.SIZE_H1), ui.TEXT, width))
        self._spacer(menu, 6)
        self._text(menu, intro, ui.body_font(), ui.MUTED)
        self._spacer(menu, 32)

        label_f = ui.body_font(ui.SIZE_SMALL, bold=True)
        self._text(menu, "Username", label_f, ui.TEXT)
        self._spacer(menu, 8)
        field_h = ui.px(60)
        # Text inputs only fit in vertical frames; center it with a top margin
        field = menu.add.frame_v(width, field_h, padding=0, background_color=ui.SURFACE_2,
                                 border_width=max(1, ui.px(1.5)), border_color=ui.LINE)
        field._pack_margin_warning = False
        text_input = menu.add.text_input(
            "", default=self.user_setup_username, maxchar=20, textinput_id=input_id, onchange=onchange,
            font_name=ui.FONT_BODY, font_size=ui.fs(ui.SIZE_BODY), font_color=ui.TEXT,
            input_underline="", copy_paste_enable=True, password=False)
        text_input._ui_ring_frame = field
        field.pack(menu.add.vertical_margin(max(0, (field_h - text_input.get_height()) // 2)))
        field.pack(text_input, align=ALIGN_LEFT, margin=(ui.px(16), 0))
        self._spacer(menu, 8)
        if self.username_error:
            self._text(menu, self.username_error, ui.body_font(ui.SIZE_SMALL), ui.DANGER)
        else:
            self._text(menu, "Up to 20 characters. Shown on leaderboards.", ui.body_font(ui.SIZE_SMALL), ui.MUTED)
        self._spacer(menu, 24)

        self._text(menu, "Region", label_f, ui.TEXT)
        self._spacer(menu, 8)
        region_items = [(region, i) for i, region in enumerate(REGIONS)]
        self._dropselect(menu, region_items, self.user_setup_region_index, self._on_region_change, width,
                         visible=5, widget_id=f"{input_id}_region")
        self._spacer(menu, 40)

        gap = ui.px(16)
        bw = (width - gap) // 2
        frame = menu.add.frame_h(width, ui.px(60), padding=0)
        frame._pack_margin_warning = False
        frame.pack(self._button(menu, secondary[0], secondary[1], w=bw, h=ui.px(60)))
        frame.pack(menu.add.horizontal_margin(gap))
        frame.pack(self._button(menu, primary[0], primary[1], w=bw, h=ui.px(60), variant="primary"))
        return text_input

    def _create_user_setup_content(self):
        self.username_input = self._profile_form(
            self.user_setup_menu, "Create your profile",
            "Pick a name and region for the global leaderboards. You can change them later.",
            "username_input", self._on_username_change,
            ("Continue", self._confirm_user_setup), ("Back", self._back_from_user_setup))

    def _create_user_edit_content(self):
        self.edit_username_input = self._profile_form(
            self.user_edit_menu, "Edit profile", "Your new name also updates the records you already posted.",
            "edit_username_input", self._on_edit_username_change,
            ("Save", self._save_user_edit), ("Cancel", self._back_to_statistics))

    # ================================================================ drawing
    def draw(self, screen):
        alpha = self.get_current_alpha()
        if alpha <= 0.0:
            return
        size = screen.get_size()
        if size != (self.width, self.height):
            self.update_dimensions(*size)

        menu = self.current_menu
        page = self.pages.get(menu, {"kind": "page", "title": ""})
        kind = page["kind"]
        L = self.L

        if kind == "main":
            # Solid side panel; the live cube stays visible on the right
            screen.fill((*ui.BG, 250), pygame.Rect(0, 0, L.panel_w, self.height))
            screen.fill((*ui.LINE, 255), pygame.Rect(L.panel_w - max(1, ui.px(1.5)), 0, max(1, ui.px(1.5)), self.height))
        else:
            screen.fill((*ui.BG, 240))

        if kind == "page":
            self._draw_header(screen, page)
        else:
            self.header_back_rect = None

        if kind == "dialog":
            self._draw_dialog_panel(screen, menu)

        menu.draw(screen)
        self._redraw_open_dropselect(screen, menu)

        if kind == "main":
            self._draw_main_footer(screen)
        self._draw_keyboard_focus(screen, menu)

    def _draw_header(self, screen, page):
        L = self.L
        width = page.get("width", L.content_w)
        x = (self.width - width) // 2
        cy = L.header_h // 2 + ui.px(8)
        size = ui.px(52)
        back = pygame.Rect(x, cy - size // 2, size, size)
        self.header_back_rect = back
        hovered = back.collidepoint(pygame.mouse.get_pos())
        ui.fill_rect(screen, ui.SURFACE_3 if hovered else ui.SURFACE_2, back, ui.radius(12))
        ui.fill_rect(screen, ui.LINE, back, ui.radius(12), width=max(1, ui.px(1.5)))
        ic = ui.icon("back", int(size * 0.5), ui.TEXT)
        if ic:
            screen.blit(ic, ic.get_rect(center=back.center))
        ui.draw_text(screen, page.get("title", ""), ui.display_font(ui.SIZE_H1), ui.TEXT,
                     (back.right + ui.px(22), cy + ui.px(3)), "midleft")
        hint = ui.body_font(ui.SIZE_CAPTION)
        ui.draw_text(screen, "Esc to go back", hint, ui.DIM, (x + width, cy), "midright")
        pygame.draw.line(screen, ui.LINE, (x, L.header_h - 1), (x + width, L.header_h - 1), max(1, ui.px(1.5)))

    def _content_bounds(self, menu):
        rect = None
        for widget in menu.get_widgets():
            try:
                if not widget.is_visible():
                    continue
                r = widget.get_rect(to_real_position=True)
            except Exception:
                continue
            if r.width <= 0 or r.height <= 0:
                continue
            rect = r.copy() if rect is None else rect.union(r)
        return rect

    def _draw_dialog_panel(self, screen, menu):
        bounds = self._content_bounds(menu)
        if bounds is None:
            return
        pad = ui.px(44)
        ui.panel(screen, bounds.inflate(pad * 2, pad * 2), fill=ui.SURFACE, border=ui.LINE, rad=ui.radius(18))

    def _draw_main_footer(self, screen):
        L = self.L
        if not self.user_manager.is_setup_completed():
            return
        small = ui.body_font(ui.SIZE_SMALL)
        name = self.user_manager.get_username() or ""
        region = self.user_manager.get_region() or ""
        text = f"{name}  ·  {region}" if region else name
        y = self.height - L.panel_pad
        ic = ui.icon("user-edit", small.get_height(), ui.MUTED)
        x = L.panel_pad + ui.px(24)
        if ic:
            screen.blit(ic, ic.get_rect(midleft=(x, y - small.get_height() // 2)))
            x += ic.get_width() + ui.px(10)
        ui.draw_text(screen, ui.ellipsize(text, small, L.panel_w - x - L.panel_pad), small, ui.MUTED, (x, y), "bottomleft")

    def _redraw_open_dropselect(self, screen, menu):
        """pygame-menu draws a dropdown list inside its frame, so later rows paint
        over it. Draw the open list again on top of everything."""
        widget = menu.get_selected_widget()
        if (widget is None or widget.__class__.__name__ != "DropSelect" or not widget.active
                or widget.get_frame() is None):
            return
        drop = getattr(widget, "_drop_frame", None)
        world = getattr(menu, "_widgets_surface", None)
        if drop is None or world is None:
            return
        owners = [widget, drop] + list(drop.get_widgets())
        saved = [(o, getattr(o, "last_surface", None)) for o in owners]
        try:
            layer = pygame.Surface(world.get_size(), pygame.SRCALPHA)
            drop.draw(layer)
            real = widget.get_rect(to_real_position=True)
            local = widget.get_rect()
            clip = screen.get_clip()
            screen.set_clip(self._view_rect(menu))
            screen.blit(layer, (real.x - local.x, real.y - local.y))
            screen.set_clip(clip)
        except Exception as e:
            if self.debug_mode:
                print(f"Dropdown redraw error: {e}")
        finally:
            for owner, surf in saved:
                owner.last_surface = surf

    def _draw_keyboard_focus(self, screen, menu):
        """Focus ring for built-in widgets (dropdowns, toggles, sliders, inputs)."""
        if not self.keyboard_mode:
            return
        widget = menu.get_selected_widget()
        if widget is None or hasattr(widget, "_ui"):
            return
        target = getattr(widget, "_ui_ring_frame", None) or widget
        try:
            rect = target.get_rect(to_real_position=True)
        except Exception:
            return
        view = self._view_rect(menu)
        if view.contains(rect):
            ui.focus_ring(screen, rect, ui.radius(10))
