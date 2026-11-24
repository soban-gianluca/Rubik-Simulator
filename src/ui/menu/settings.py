import pygame

from src.rendering import display_manager
from src.rendering import hdr as hdr_output
from src.rendering import graphics
from src.rendering import backgrounds
from src.ui import ui_style as ui
from src.ui.menu.common import _batched, _first_arg


class SettingsMixin:
    """Settings: display, graphics and audio values, and the settings and controls pages."""

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
        self._settings_built_for = None
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
        self._settings_built_for = None
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
        self._settings_built_for = None
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

    # ================================================================ simple settings
    def _on_fps_toggle(self, value):
        self.sound_manager.play("menu_select")
        self.show_fps = value
        self.settings_manager.settings["show_fps"] = value
        self.settings_manager.save_settings()
        if self.game:
            self.game.show_fps = value

    def _graphics_setting(self, key, value):
        self.sound_manager.play("menu_select")
        self.settings_manager.settings[key] = value
        self.settings_manager.save_settings()

    def _on_antialiasing_change(self, selected, mode):
        self._graphics_setting("antialiasing", mode)
        if self.game:
            self.game.scene_target.set_mode(mode)

    def _on_vsync_change(self, selected, mode):
        self._graphics_setting("vsync", mode)
        if self.game:
            graphics.set_vsync(mode)

    def _on_background_change(self, selected, style):
        self._graphics_setting("background_style", style)
        if self.game:
            self.game.renderer.set_background(choice=style)
            if style in (sid for sid, _, _ in backgrounds.STYLES):
                self.game.enqueue_achievement_notifications(self.achievements_manager.record_background(style))

    def _on_stars_toggle(self, value):
        self._graphics_setting("background_stars", bool(value))
        if self.game:
            self.game.renderer.set_background(stars=value)

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

    @_batched(_first_arg)
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
        self._row(menu, "Apply display changes", [self.apply_button], separator=False)
        self._update_settings_changed()

        # Graphics: applied right away, no window change needed
        settings = self.settings_manager.settings
        self._section(menu, "Graphics")
        aa_items = graphics.aa_menu_items()
        aa_ids = [key for _, key in aa_items]
        aa = self.game.scene_target.mode if self.game else settings.get("antialiasing", graphics.DEFAULT_AA)
        aa_select = self._dropselect(menu, aa_items, aa_ids.index(aa) if aa in aa_ids else 0,
                                     self._on_antialiasing_change, control_w, visible=7, widget_id="graphics_aa")
        self._row(menu, "Anti-aliasing", [aa_select],
                  desc="Smooths jagged edges. MSAA stays sharp, SSAA is smoothest but demanding, FXAA is lightest.")

        vsync_items = graphics.vsync_menu_items()
        vsync_ids = [key for _, key in vsync_items]
        vsync = settings.get("vsync", graphics.DEFAULT_VSYNC)
        vsync_select = self._dropselect(menu, vsync_items, vsync_ids.index(vsync) if vsync in vsync_ids else 1,
                                        self._on_vsync_change, control_w, visible=3, widget_id="graphics_vsync")
        vsync_desc = "Matches the frame rate to the monitor to stop tearing."
        if "adaptive" in vsync_ids:
            vsync_desc += " Adaptive only syncs while the game keeps up."
        self._row(menu, "VSync", [vsync_select], desc=vsync_desc)

        self._row(menu, "Show FPS counter", [self._toggle(menu, self.show_fps, self._on_fps_toggle)],
                  separator=False)

        # Background
        self._section(menu, "Background")
        bg_items = backgrounds.menu_items()
        bg_ids = [key for _, key in bg_items]
        bg = settings.get("background_style", backgrounds.DEFAULT_STYLE)
        bg_select = self._dropselect(menu, bg_items, bg_ids.index(bg) if bg in bg_ids else 0,
                                     self._on_background_change, control_w, visible=6, widget_id="background_style")
        self._row(menu, "Style", [bg_select], desc="Match game mode gives every mode its own background; the solid variant uses a gradient in the mode's color.")
        self._row(menu, "Stars", [self._toggle(menu, bool(settings.get("background_stars", True)),
                                               self._on_stars_toggle, "background_stars")],
                  desc="A star field on night and space backgrounds.", separator=False)

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
        # Unapplied display choices exist only in the widgets: such a page is never reused
        self._settings_built_for = None if self.settings_changed else self._settings_state()

    @_batched(_first_arg)
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
