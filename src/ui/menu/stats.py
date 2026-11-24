import os
import time
import threading
from datetime import datetime, timezone

import pygame
from pygame_menu.locals import ALIGN_LEFT, ALIGN_RIGHT, POSITION_CENTER

from src.ui import ui_style as ui
from utils.path_helper import resource_path
from src.ui.menu.common import GAME_MODE_OPTIONS, GAME_MODE_DISPLAY, REGION_OPTIONS, REGION_DISPLAY, _batched


class StatsMixin:
    """Statistics: personal records, global and daily leaderboards, achievements."""

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
                data, failure = self.supabase_manager.get_leaderboard(
                    game_mode=game_mode, region=region, sort_by="best_time", limit=50, ascending=True)
                self.leaderboard_data = data if data else []
                self.leaderboard_last_fetch = time.time()
                self.leaderboard_error = failure
            except Exception as e:
                print(f"Error fetching leaderboard: {e}")
                self.leaderboard_error = "failed"
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
                data, failure = self.supabase_manager.get_daily_leaderboard(region=region, limit=50)
                self.daily_leaderboard_data = data if data else []
                self.daily_leaderboard_last_fetch = time.time()
                self.daily_leaderboard_error = failure
            except Exception as e:
                print(f"Error fetching daily leaderboard: {e}")
                self.daily_leaderboard_error = "failed"
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

    # ---------------------------------------------------------------- statistics
    @_batched(lambda self, *args: self.personal_best_menu)
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

    def _error_banner(self, menu, icon_name, title, body, color):
        """A bordered banner with an icon tile, a title and a wrapped explanation."""
        width = self.pages[menu]["width"]
        pad = ui.px(24)
        tile = ui.px(56)
        title_f = ui.display_font(ui.SIZE_H3)
        text_x = pad + tile + ui.px(20)
        body_surf = self._text_surface(body, ui.body_font(), ui.MUTED, width - text_x - pad)
        text_h = title_f.get_height() + ui.px(6) + body_surf.get_height()
        height = max(tile, text_h) + 2 * pad
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        ui.panel(surf, surf.get_rect(), fill=ui.SURFACE, border=(*color, 140))
        tile_rect = pygame.Rect(pad, (height - tile) // 2, tile, tile)
        ui.fill_rect(surf, (*color, 36), tile_rect, ui.radius(10))
        mark = ui.icon(icon_name, ui.px(28), color)
        if mark:
            surf.blit(mark, mark.get_rect(center=tile_rect.center))
        y = (height - text_h) // 2
        ui.draw_text(surf, title, title_f, ui.TEXT, (text_x, y))
        surf.blit(body_surf, (text_x, y + title_f.get_height() + ui.px(6)))
        self._spacer(menu, 8)
        self._surface(menu, surf)

    def _leaderboard_state(self, loading, error, data, empty_title, empty_body):
        """Shows loading, error, offline and empty states. Returns True if a message was shown."""
        menu = self.personal_best_menu
        if error == "not_configured":
            self._message(menu, "Leaderboard unavailable", "Online records are not set up in this build.")
        elif loading:
            self._message(menu, "Loading", "Fetching the latest times.")
        elif error == "offline":
            self._error_banner(menu, "wifi-off", "You are offline",
                               "Online features require an internet connection. "
                               "Check your connection, then press Refresh.", ui.FACE["orange"])
        elif error == "server_down":
            self._error_banner(menu, "server-off", "Game servers are not available",
                               "The leaderboards cannot be reached right now. "
                               "Please try again later.", ui.DANGER)
        elif error:
            self._message(menu, "Could not load the leaderboard", "Try refreshing in a moment.", ui.DANGER)
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
            self._leaderboard_state(False, "not_configured", [], "", "")
            return
        mode_items = [(GAME_MODE_DISPLAY.get(m, m), i) for i, m in enumerate(GAME_MODE_OPTIONS)]
        region_items = [(REGION_DISPLAY.get(r, r), i) for i, r in enumerate(REGION_OPTIONS)]
        mode_index = GAME_MODE_OPTIONS.index(self.leaderboard_filter_mode) if self.leaderboard_filter_mode in GAME_MODE_OPTIONS else 0
        region_index = REGION_OPTIONS.index(self.leaderboard_filter_region) if self.leaderboard_filter_region in REGION_OPTIONS else 0
        self._filters_row(menu, [("Mode", mode_items, mode_index, self._on_leaderboard_mode_filter_change, "lb_mode"),
                                 ("Region", region_items, region_index, self._on_leaderboard_region_filter_change, "lb_region")],
                          self._refresh_leaderboard)

        if self._leaderboard_state(self.leaderboard_loading, self.leaderboard_error, self.leaderboard_data,
                                   "No records yet", "Be the first to post a time."):
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
            self._leaderboard_state(False, "not_configured", [], "", "")
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
                                   self.daily_leaderboard_data,
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

    @_batched(lambda self, *args: self.achievements_menu)
    def _create_achievements_content(self):
        menu = self.achievements_menu
        menu.clear()
        width = self.pages[menu]["width"]
        unlocked, total = self.achievements_manager.get_unlocked_count()
        by_category = self.achievements_manager.get_achievements_by_category()
        self._ach_seen = (self.achievements_manager, unlocked)  # this page is current (see _refresh_achievement_views)
        self._ach_cards = {}  # achievement id: (widget of its section, card rect inside it)

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
                 "challenge": "Challenges", "daily": "Daily", "efficiency": "Efficiency", "mastery": "Mastery",
                 "secret": "Secret"}
        order = ["beginner", "progression", "speed", "challenge", "daily", "efficiency", "mastery", "secret"]
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
            rects = {}
            for i, a in enumerate(items):
                r, c = divmod(i, cols)
                rects[a["id"]] = pygame.Rect(c * (card_w + gap), r * (card_h + gap), card_w, card_h)
                self._achievement_card(surf, rects[a["id"]], a)
            widget = self._surface(menu, surf)
            for aid, rect in rects.items():
                self._ach_cards[aid] = (widget, rect)
        self._spacer(menu, 48)
