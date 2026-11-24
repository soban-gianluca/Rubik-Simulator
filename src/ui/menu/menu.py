import time

import pygame
import pygame_menu
from pygame_menu.locals import ALIGN_CENTER, POSITION_EAST

from src.managers.settings_manager import SettingsManager
from src.managers.sound_manager import SoundManager
from src.managers.personal_best_manager import PersonalBestManager
from src.managers.user_manager import UserManager
from src.managers.achievements_manager import AchievementsManager
from src.ui import ui_style as ui
from src.ui.menu.common import NAV_KEYS, OPEN_DURATION, CLOSE_DURATION, _ease_out, _Layout
from src.ui.menu.widgets import WidgetsMixin
from src.ui.menu.settings import SettingsMixin
from src.ui.menu.navigation import NavigationMixin
from src.ui.menu.stats import StatsMixin
from src.ui.menu.profile import ProfileMixin
from src.ui.menu.drawing import DrawingMixin


class Menu(WidgetsMixin, SettingsMixin, NavigationMixin, StatsMixin, ProfileMixin, DrawingMixin):
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
        self.animation_duration = OPEN_DURATION
        self.is_opening = False
        self.target_alpha = 1.0
        self.current_alpha = 0.0
        # Page change: a still image of the old page slides out while the new one slides in
        self._transition = None
        self._snapshot = None
        self._panel_layer = None

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

    def get_selected_difficulty(self):
        return self.selected_difficulty

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
        eased = _ease_out(progress)
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
        """Animate the menu in or out. Toggling mid-animation turns it around from where it is."""
        alpha = self.get_current_alpha()
        closing = self.is_animating and not self.is_opening
        self.is_animating = True
        if self.active and not closing:
            self.is_opening = False
            self.target_alpha = 0.0
            self.animation_duration = CLOSE_DURATION
            # Start the eased curve at the current alpha (1 - ease_out(p) == alpha)
            p = 1 - alpha ** (1 / 3)
            self.animation_start_time = time.time() - p * CLOSE_DURATION
            self.hover_widget = None
        else:
            self.is_opening = True
            self.target_alpha = 1.0
            self.animation_duration = OPEN_DURATION
            p = 1 - (1 - alpha) ** (1 / 3)  # ease_out(p) == alpha
            self.animation_start_time = time.time() - p * OPEN_DURATION
            self.active = True
            self.sound_manager.play("menu_open")
            self.refresh_main_menu_buttons()
            self._change_menu(self.main_menu)
            self._transition = None  # opening has its own animation

    def is_active(self):
        return self.active

    def set_game_instance(self, game):
        self.game = game
        # Share one settings object with the game so saves never overwrite each other
        self.settings_manager = game.settings
        self._load_display_state()
        self.refresh_main_menu_buttons()
        # Build every page now, during the game's startup, so no page is slow the first time
        for menu in list(self._unbuilt):
            self._ensure_built(menu)

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
        # Pages that are rebuilt every time they open are built on first use
        self._unbuilt = {}
        self.difficulty_menu = self._page("Choose a mode", self._back_to_main)
        self._unbuilt[self.difficulty_menu] = lambda: self._build_modes_page(self.difficulty_menu)

        self.settings_menu = self._page("Settings", self._back_to_main, width=min(L.content_w, ui.px(1000)))
        self._unbuilt[self.settings_menu] = lambda: self._build_settings_page(self.settings_menu)
        self._settings_built_for = None
        self.audio_settings_menu = self.settings_menu

        self.controls_menu = self._page("Controls", self._back_to_main)
        self._build_controls_page(self.controls_menu)

        self.personal_best_menu = self._page("Statistics", self._back_to_main)
        self._unbuilt[self.personal_best_menu] = self._create_personal_best_content

        self.achievements_menu = self._page("Achievements", self._back_to_main, width=min(L.content_w, ui.px(1100)))
        self._unbuilt[self.achievements_menu] = self._create_achievements_content

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
        self._ensure_built(self.current_menu)

    def _ensure_built(self, menu):
        build = self._unbuilt.pop(menu, None)
        if build:
            build()

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
        menu.render()
        menu.disable_render()  # lay out once at the end (see _batched)
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
        menu.enable_render()
        menu.render()

        self.main_menu = menu
        if old is not None and getattr(self, "current_menu", None) is old:
            self.current_menu = menu
