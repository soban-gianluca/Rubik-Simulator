import pygame
import pygame_menu
from pygame_menu.locals import ALIGN_LEFT, ALIGN_RIGHT, POSITION_CENTER

from src.ui import ui_style as ui


class WidgetsMixin:
    """Widget helpers and the painters of the custom drawn buttons."""

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
