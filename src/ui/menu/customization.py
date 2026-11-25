import pygame

from src import cube_skins
from src.managers.achievements_manager import ACHIEVEMENTS
from src.rendering import skin_preview
from src.ui import ui_style as ui
from src.ui.menu.common import _batched


class CustomizationMixin:
    """Customization page: pick a cube skin. Skins unlock with achievements."""

    def _equipped_skin_id(self):
        if self.game and hasattr(self.game, "equipped_skin_id"):
            return self.game.equipped_skin_id()
        return self.settings_manager.settings.get("cube_skin", cube_skins.DEFAULT_SKIN)

    def _open_customization(self):
        self.sound_manager.play("menu_select")
        self._create_customization_content()
        self._change_menu(self.customization_menu)

    def _equip_skin(self, skin_id):
        skin = cube_skins.get_skin(skin_id)
        if not cube_skins.is_unlocked(skin, self.achievements_manager):
            return
        self.sound_manager.play("menu_apply")
        self.settings_manager.settings["cube_skin"] = skin_id
        self.settings_manager.save_settings()
        if self.game:
            self.game.renderer.set_skin(skin_id)
        # The cards read the equipped skin when painted: redraw them
        self.customization_menu.force_surface_cache_update()

    @staticmethod
    def _skin_requirement(skin):
        achievement = ACHIEVEMENTS.get(skin.get("unlock") or "")
        if not achievement:
            return ""
        if achievement.get("secret"):
            return "Unlocked by a secret achievement."
        return f"Unlock “{achievement['name']}”: {achievement['description']}."

    @_batched(lambda self, *args: self.customization_menu)
    def _create_customization_content(self):
        menu = self.customization_menu
        menu.clear()
        width = self.pages[menu]["width"]
        manager = self.achievements_manager
        unlocked, total = cube_skins.unlocked_count(manager)

        # Summary
        self._spacer(menu, 20)
        big = ui.display_font(ui.SIZE_H2)
        summary = pygame.Surface((width, big.get_height() + ui.px(22)), pygame.SRCALPHA)
        ui.draw_text(summary, f"{unlocked} of {total} skins unlocked", big, ui.TEXT, (0, 0))
        ui.progress_bar(summary, (0, big.get_height() + ui.px(8), width, max(4, ui.px(8))),
                        unlocked / total if total else 0)
        self._surface(menu, summary)
        self._spacer(menu, 14)
        self._text(menu, "Earn achievements to unlock new skins. The Classic skin uses the color scheme "
                         "chosen in Settings.", ui.body_font(ui.SIZE_SMALL), ui.MUTED)
        self._section(menu, "Cube skins", top=28)

        # As many columns as fit while every skin name still shows in full
        gap = ui.px(16)
        pad = ui.px(16)
        name_f = ui.body_font(ui.SIZE_BODY, bold=True)
        longest = max(name_f.size(skin["name"])[0] for skin in cube_skins.SKINS)
        cols = 4
        while cols > 2 and (width - gap * (cols - 1)) // cols - 2 * pad < longest:
            cols -= 1
        card_w = (width - gap * (cols - 1)) // cols
        preview = min(card_w - 2 * pad, ui.px(168))
        card_h = (2 * pad + preview + ui.px(12) + ui.body_font(ui.SIZE_BODY, bold=True).get_linesize()
                  + 3 * ui.body_font(ui.SIZE_CAPTION).get_linesize()
                  + ui.body_font(ui.SIZE_CAPTION, bold=True).get_height() + ui.px(10))

        skins = cube_skins.SKINS
        for row in range(0, len(skins), cols):
            frame = menu.add.frame_h(width, card_h, padding=0)
            frame._pack_margin_warning = False
            for col, skin in enumerate(skins[row:row + cols]):
                if col:
                    frame.pack(menu.add.horizontal_margin(gap))
                widget = self._custom_button(menu, skin["name"], lambda s=skin["id"]: self._equip_skin(s),
                                             card_w, card_h, self._paint_skin_card,
                                             button_id=f"skin_{skin['id']}", skin=skin, preview=preview)
                widget.readonly = not cube_skins.is_unlocked(skin, manager)
                frame.pack(widget)
            if row + cols < len(skins):
                self._spacer(menu, 16)
        self._spacer(menu, 48)

    def _paint_skin_card(self, surface, rect, d, hovered, focused, locked):
        skin = d["skin"]
        equipped = not locked and skin["id"] == self._equipped_skin_id()
        rad = ui.radius(14)
        ui.fill_rect(surface, ui.SURFACE_2 if hovered else ui.SURFACE, rect, rad)
        border = ui.ACCENT if equipped else (ui.MUTED if hovered else ui.LINE)
        ui.fill_rect(surface, border, rect, rad, width=max(1, ui.px(2 if equipped or hovered else 1.5)))
        if focused:
            ui.focus_ring(surface, rect, rad)

        pad = ui.px(16)
        size = d["preview"]
        img = skin_preview.render(skin, size)
        img_rect = img.get_rect(midtop=(rect.centerx, rect.y + pad))
        if locked:
            img = img.copy()
            img.fill((255, 255, 255, 70), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(img, img_rect)
            self._draw_lock(surface, img_rect.center, max(ui.px(26), size // 5))
        else:
            surface.blit(img, img_rect)

        x = rect.x + pad
        tw = rect.width - 2 * pad
        y = img_rect.bottom + ui.px(12)
        name_f = ui.body_font(ui.SIZE_BODY, bold=True)
        small = ui.body_font(ui.SIZE_CAPTION)
        tag_f = ui.body_font(ui.SIZE_CAPTION, bold=True)
        ui.draw_text(surface, ui.ellipsize(skin["name"], name_f, tw), name_f,
                     ui.TEXT if not locked else (205, 209, 216), (x, y))
        y += name_f.get_linesize()

        text = self._skin_requirement(skin) if locked else skin["description"]
        lines = ui.wrap(text, small, tw)
        if len(lines) > 3:
            lines = lines[:3]
            lines[-1] = ui.ellipsize(lines[-1] + " ...", small, tw)
        for line in lines:
            ui.draw_text(surface, line, small, ui.MUTED, (x, y))
            y += small.get_linesize()

        bottom = rect.bottom - pad
        if equipped:
            status, color = "Equipped", ui.ACCENT
        elif locked:
            status, color = "Locked", ui.DIM
        else:
            status, color = "Select", ui.TEXT if hovered else ui.MUTED
        ui.draw_text(surface, status, tag_f, color, (x, bottom), "bottomleft")
        # The animated tag sits on the status line so the name keeps the full width
        if skin.get("animated"):
            ui.draw_text(surface, "Animated", tag_f, ui.DAILY if not locked else ui.DIM,
                         (rect.right - pad, bottom), "bottomright")

    @staticmethod
    def _draw_lock(surface, center, size):
        """A padlock: rounded body and a shackle."""
        cx, cy = center
        body = pygame.Rect(0, 0, size, int(size * 0.78))
        body.midtop = (cx, cy - size // 8)
        thick = max(2, size // 7)
        shackle = pygame.Rect(0, 0, int(size * 0.64), int(size * 0.8))
        shackle.midbottom = (cx, body.y + thick)
        ui.fill_rect(surface, ui.BG, body.inflate(thick * 2, thick * 2), ui.radius(8))
        pygame.draw.ellipse(surface, ui.BG, shackle.inflate(thick * 2, thick * 2), thick * 3)
        pygame.draw.ellipse(surface, ui.TEXT, shackle, thick)
        ui.fill_rect(surface, ui.BG, body, ui.radius(6))
        ui.fill_rect(surface, ui.TEXT, body, ui.radius(6))
        hole = pygame.Rect(0, 0, max(2, thick), body.height // 3)
        hole.center = body.center
        ui.fill_rect(surface, ui.BG, hole, hole.width // 2)
