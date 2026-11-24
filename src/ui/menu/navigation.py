import pygame
from pygame_menu.locals import ORIENTATION_VERTICAL

from src.rendering import display_manager
from src.rendering import hdr as hdr_output
from src.ui import ui_style as ui
from src.ui.menu.common import _batched, _first_arg


class NavigationMixin:
    """Page navigation, starting games, challenge limits and the mode and limit pages."""

    # ================================================================ navigation actions
    def _in_game(self):
        return bool(self.game and getattr(self.game, "difficulty_change_count", 0) >= 1)

    def _change_menu(self, new_menu):
        self._ensure_built(new_menu)
        old = getattr(self, "current_menu", None)
        if old is not None and old is not new_menu and self.active and self.get_current_alpha() > 0.0:
            self._start_transition(old, new_menu)
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
            self.game.renderer.set_background_mode(difficulty)
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
            self.game.renderer.set_background_mode(difficulty)
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

    def _settings_state(self):
        """Everything the settings page shows; it is rebuilt only when this changes."""
        s = self.settings_manager.settings
        return (self.display_mode, self.display_index, self.width, self.height, self.hdr_enabled,
                self.hdr_paper_white, display_manager.num_displays(), hdr_output.display_hdr_info(self.display_index),
                self.show_fps, self.hints_enabled, self.master_volume, self.music_volume, self.effects_volume,
                self.menu_volume, self.game.scene_target.mode if self.game else s.get("antialiasing"),
                s.get("vsync"), s.get("background_style"), s.get("background_stars"))

    def _open_settings(self):
        self._load_display_state()
        if self._settings_built_for != self._settings_state():
            self._build_settings_page(self.settings_menu)
        self._go(self.settings_menu)

    def _open_audio_settings(self):
        self._open_settings()

    def _open_controls(self):
        self._go(self.controls_menu)

    def _open_credits(self):
        self._go(self.credits_menu)

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

    def show_achievements(self, achievement_id=None):
        """Open the achievements page (used by the game's achievement toast),
        scrolled so the card of ``achievement_id`` is in view."""
        self._open_achievements()
        card = getattr(self, "_ach_cards", {}).get(achievement_id)
        sbar = self._menu_scrollbar(self.achievements_menu)
        if card is None or sbar is None:
            return
        widget, rect = card
        lo, hi = sbar.get_minmax()
        view_h = self.achievements_menu.get_scrollarea().get_view_rect().height
        # Center the card in the visible part of the page
        target = widget.get_rect().y + rect.centery - view_h // 2
        sbar.set_value(min(max(target, lo), hi))

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

    @_batched(_first_arg)
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

    @_batched(_first_arg)
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

    @_batched(_first_arg)
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
