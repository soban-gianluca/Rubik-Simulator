import time

import pygame

from src.ui import ui_style as ui
from src.ui.menu.common import PAGE_DURATION, ITEM_DELAY, ITEM_STAGGER, ITEM_DURATION, _ease_out


class DrawingMixin:
    """Page transitions and drawing of the menu layers."""

    # ================================================================ animation
    def _depth(self, menu):
        """How deep a page is: going deeper slides in from the right, going back from the left."""
        if menu is self.main_menu:
            return 0
        if menu in (self.time_selection_menu, self.moves_selection_menu, self.user_edit_menu):
            return 2
        return 1

    def _start_transition(self, old, new):
        surf = self._snapshot
        if surf is None or surf.get_size() != (self.width, self.height):
            surf = self._snapshot = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        self._draw_page(surf, old, settled=True)
        kinds = (self.pages.get(old, {}).get("kind"), self.pages.get(new, {}).get("kind"))
        self._transition = {
            "start": time.time(),
            "dir": 1 if self._depth(new) >= self._depth(old) else -1,
            "vertical": "dialog" in kinds,
            "uploaded": False,
        }

    def layers(self, screen):
        """The menu as layers for the game to composite on the GPU.

        Returns [(surface, alpha, (dx, dy), changed)], back to front. ``screen`` is a
        cleared full screen surface the current page is drawn into; during a page
        change the old page comes first as a still snapshot (``changed`` only once).
        """
        alpha = self.get_current_alpha()
        if alpha <= 0.0:
            return []
        if screen.get_size() != (self.width, self.height):
            self.update_dimensions(*screen.get_size())
            self._transition = None
        self._draw_page(screen, self.current_menu)

        # Opening and closing: the side panel slides with the fade, pages drift down a little
        hidden = 1.0 - alpha
        if self.pages.get(self.current_menu, {}).get("kind") == "main":
            base = (-round(hidden * ui.px(56)), 0)
        else:
            base = (0, round(hidden * ui.px(20)))

        t = self._transition
        progress = (time.time() - t["start"]) / PAGE_DURATION if t else 1.0
        if progress >= 1.0:
            self._transition = None
            return [(screen, alpha, base, True)]

        incoming = _ease_out(progress)
        outgoing = _ease_out(progress * 1.6)  # the old page clears out faster
        d = t["dir"]
        if t["vertical"]:
            in_off, out_off = (0, round((1 - incoming) * ui.px(28))), (0, 0)
        else:
            in_off = (round((1 - incoming) * ui.px(56) * d), 0)
            out_off = (round(-outgoing * ui.px(36) * d), 0)
        changed = not t["uploaded"]
        t["uploaded"] = True
        return [
            (self._snapshot, alpha * (1 - outgoing), (base[0] + out_off[0], base[1] + out_off[1]), changed),
            (screen, alpha * incoming, (base[0] + in_off[0], base[1] + in_off[1]), True),
        ]

    # ================================================================ drawing
    def draw(self, screen):
        """Draw the current page without animation offsets (see layers())."""
        if self.get_current_alpha() <= 0.0:
            return
        if screen.get_size() != (self.width, self.height):
            self.update_dimensions(*screen.get_size())
        self._draw_page(screen, self.current_menu)

    def _draw_page(self, screen, menu, settled=False):
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

        # pygame-menu redraws a page's widgets only when one of them reports a change. The custom
        # painted buttons also depend on our hover and keyboard focus state: redraw when it changes.
        paint_state = (menu, self.hover_widget, self.keyboard_mode, menu.get_selected_widget())
        if paint_state != self._paint_state:
            self._paint_state = paint_state
            menu.force_surface_cache_update()

        elapsed = time.time() - self.animation_start_time
        cascade_end =ITEM_DELAY + ITEM_STAGGER * len(menu.get_widgets()) + ITEM_DURATION
        if kind == "main" and not settled and self.is_opening and elapsed < cascade_end:
            self._draw_main_cascade(screen, menu, elapsed)
        else:
            menu.draw(screen)
        self._redraw_open_dropselect(screen, menu)

        if kind == "main":
            self._draw_main_footer(screen)
            self._draw_update_banner(screen)
        else:
            self.update_rect = None
        self._draw_keyboard_focus(screen, menu)

    def _draw_main_cascade(self, screen, menu, elapsed):
        """Main menu items slide in one after another when the menu opens."""
        L = self.L
        layer = self._panel_layer
        if layer is None or layer.get_size() != (L.panel_w, self.height):
            layer = self._panel_layer = pygame.Surface((L.panel_w, self.height), pygame.SRCALPHA)
        layer.fill((0, 0, 0, 0))
        menu.draw(layer)
        rects = []
        for widget in menu.get_widgets():
            try:
                r = widget.get_rect(to_real_position=True).clip(layer.get_rect())
            except Exception:
                continue
            if r.width > 1 and r.height > 1:
                rects.append(r)
        rects.sort(key=lambda r: r.y)
        for i, r in enumerate(rects):
            e = _ease_out((elapsed - ITEM_DELAY - i * ITEM_STAGGER) / ITEM_DURATION)
            if e <= 0.0:
                continue
            # (each blit sets its own alpha; set_alpha(None) would stop the layer from blending)
            layer.set_alpha(int(255 * e))
            screen.blit(layer, (r.x - round((1 - e) * ui.px(40)), r.y), area=r)

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
        # Center the capital letters on the button: the font's line box has extra room below them
        title_font = ui.display_font(ui.SIZE_H1)
        caps = title_font.render("H", True, ui.TEXT).get_bounding_rect()
        ui.draw_text(screen, page.get("title", ""), title_font, ui.TEXT,
                     (back.right + ui.px(22), cy - caps.centery), "topleft")
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
        small = ui.body_font(ui.SIZE_SMALL)
        y = self.height - L.panel_pad

        # Round credits button, bottom right of the panel, centered on the profile line
        size = ui.px(52)
        credits = pygame.Rect(0, 0, size, size)
        credits.center = (L.panel_w - L.panel_pad - size // 2, y - small.get_height() // 2)
        self.credits_rect = credits
        hovered = credits.collidepoint(pygame.mouse.get_pos())
        ui.fill_rect(screen, ui.SURFACE_3 if hovered else ui.SURFACE_2, credits, size // 2)
        ui.fill_rect(screen, ui.LINE, credits, size // 2, width=max(1, ui.px(1.5)))
        ic = ui.icon("info", int(size * 0.5), ui.TEXT if hovered else ui.MUTED)
        if ic:
            screen.blit(ic, ic.get_rect(center=credits.center))

        if not self.user_manager.is_setup_completed():
            return
        name = self.user_manager.get_username() or ""
        region = self.user_manager.get_region() or ""
        text = f"{name}  ·  {region}" if region else name
        ic = ui.icon("user-edit", small.get_height(), ui.MUTED)
        x = L.panel_pad + ui.px(24)
        if ic:
            screen.blit(ic, ic.get_rect(midleft=(x, y - small.get_height() // 2)))
            x += ic.get_width() + ui.px(10)
        max_w = credits.left - ui.px(16) - x
        ui.draw_text(screen, ui.ellipsize(text, small, max_w), small, ui.MUTED, (x, y), "bottomleft")

    def _draw_update_banner(self, screen):
        """Top right of the main menu, shown only when GitHub has a newer release."""
        checker = self.update_checker
        if not checker.update_available:
            self.update_rect = None
            return
        font = ui.body_font(ui.SIZE_SMALL)
        label = f"Version {checker.latest_tag} is out"
        btn_label = "Download"
        pad = ui.px(14)
        btn_w = ui.text_width(btn_label, ui.body_font(ui.SIZE_SMALL, bold=True)) + ui.px(40)
        btn_h = ui.px(40)
        w = pad + ui.text_width(label, font) + ui.px(20) + btn_w + pad // 2
        h = btn_h + pad
        panel = pygame.Rect(self.width - self.L.margin - w, self.L.margin, w, h)
        ui.panel(screen, panel, fill=ui.SURFACE, border=ui.LINE, rad=ui.radius(12))
        ui.draw_text(screen, label, font, ui.TEXT, (panel.x + pad, panel.centery), "midleft")
        btn = pygame.Rect(panel.right - pad // 2 - btn_w, panel.y + pad // 2, btn_w, btn_h)
        self.update_rect = panel
        ui.button(screen, btn, btn_label, "primary", hovered=panel.collidepoint(pygame.mouse.get_pos()),
                  ref_font=ui.SIZE_SMALL)

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
