import pygame
import time
import os
import numpy as np
from OpenGL.GL import *
from src.ui import ui_style as ui
from src.managers.achievements_manager import ACHIEVEMENTS
from utils.path_helper import resource_path


class HudMixin:
    """In-game 2D overlay: banners, achievement toasts, FPS counter and game stats."""

    def show_banner(self, message):
        """Show a notification banner with fade in/out animation"""
        self.banner_text = message
        self.banner_active = True
        self.banner_start_time = time.time()
        self.banner_alpha = 0.0

    def enqueue_achievement_notifications(self, achievement_ids, delay_seconds=0.0):
        """Queue achievement notifications.

        Notifications are shown one at a time. If `delay_seconds` is provided,
        each item becomes eligible after that delay from the moment it was queued.
        """
        if not achievement_ids:
            return

        now = time.time()
        delay = float(delay_seconds)
        for achievement_id in achievement_ids:
            if not achievement_id:
                continue
            self._achievement_notifications.append({
                'id': achievement_id,
                'ready_at': now + delay,
            })

    def update_achievement_notifications(self):
        """Advance queued achievement notifications (delayed + sequential)."""
        now = time.time()

        if self._achievement_notification_active:
            elapsed = now - self._achievement_notification_start_time
            fade = self._achievement_notification_fade_duration
            total = self._achievement_notification_total_duration

            if elapsed < 0:
                self._achievement_notification_alpha = 0.0
            elif elapsed < fade:
                self._achievement_notification_alpha = elapsed / fade
            elif elapsed < total - fade:
                self._achievement_notification_alpha = 1.0
            elif elapsed < total:
                self._achievement_notification_alpha = 1.0 - ((elapsed - (total - fade)) / fade)
            else:
                self._achievement_notification_active = False
                self._achievement_notification_id = None
                self._achievement_notification_alpha = 0.0

        # Start next notification if none active
        if (not self._achievement_notification_active) and self._achievement_notifications:
            next_item = self._achievement_notifications[0]
            if now >= float(next_item.get('ready_at', 0.0)):
                self._achievement_notifications.pop(0)
                self._achievement_notification_id = next_item.get('id')
                self._achievement_notification_active = True
                self._achievement_notification_start_time = now
                self._achievement_notification_alpha = 0.0

                # Play SFX when the banner actually appears
                if hasattr(self, 'sound_manager') and self.sound_manager:
                    self.sound_manager.play('achievement')

    def _get_achievement_icon(self, achievement_id, size):
        """Load & cache an achievement icon Surface scaled to (size, size)."""
        key = (achievement_id, int(size))
        if key in self._achievement_icon_cache:
            return self._achievement_icon_cache[key]

        achievement = ACHIEVEMENTS.get(achievement_id, {})
        icon_path = achievement.get('icon', '')
        if not icon_path:
            self._achievement_icon_cache[key] = None
            return None

        full_icon_path = resource_path(icon_path)
        if not os.path.exists(full_icon_path):
            self._achievement_icon_cache[key] = None
            return None

        try:
            icon_img = pygame.image.load(full_icon_path).convert_alpha()
            icon_img = pygame.transform.smoothscale(icon_img, (int(size), int(size)))
            self._achievement_icon_cache[key] = icon_img
            return icon_img
        except Exception:
            self._achievement_icon_cache[key] = None
            return None

    def _render_achievement_notification_opengl(self):
        """Achievement toast at the top center"""
        self._achievement_toast_rect = None
        if (not self._achievement_notification_active) or self._achievement_notification_alpha <= 0:
            return
        achievement_id = self._achievement_notification_id
        achievement = ACHIEVEMENTS.get(achievement_id, {}) if achievement_id else {}
        try:
            a = float(self._achievement_notification_alpha)
            pad = ui.px(18)
            icon_size = ui.px(64)
            caption_f = ui.body_font(ui.SIZE_CAPTION, bold=True)
            name_f = ui.body_font(ui.SIZE_BODY, bold=True)
            name = achievement.get('name', 'Unknown achievement')
            text_w = max(caption_f.size("Achievement unlocked")[0], name_f.size(name)[0])
            width = min(self.width - ui.px(48), pad * 2 + icon_size + ui.px(18) + text_w + ui.px(8))
            height = icon_size + pad * 2

            surf = pygame.Surface((width, height), pygame.SRCALPHA)
            ui.fill_rect(surf, (*ui.SURFACE, 248), surf.get_rect(), ui.radius(14))
            ui.fill_rect(surf, ui.ACCENT, surf.get_rect(), ui.radius(14), width=max(1, ui.px(2)))
            icon = self._get_achievement_icon(achievement_id, icon_size)
            if icon is not None:
                surf.blit(icon, (pad, pad))
            else:
                ui.cube_mark(surf, (pad + icon_size // 2, pad + icon_size // 2), icon_size // 2, body=ui.SURFACE)
            tx = pad + icon_size + ui.px(18)
            ui.draw_text(surf, "Achievement unlocked", caption_f, ui.ACCENT, (tx, height // 2 - ui.px(2)), "bottomleft")
            ui.draw_text(surf, ui.ellipsize(name, name_f, width - tx - pad), name_f, ui.TEXT,
                         (tx, height // 2 + ui.px(2)), "topleft")
            surf.set_alpha(int(255 * a))
            y = max(0, self._hud_margin() + int((1.0 - a) * -ui.px(16)))
            self._blit_gl(surf, (self.width - width) // 2, y)
            self._achievement_toast_rect = pygame.Rect((self.width - width) // 2, y, width, height)
        except Exception as e:
            if self.debug_mode:
                print(f"Achievement banner render error: {e}")

    def achievement_toast_at(self, pos):
        rect = getattr(self, '_achievement_toast_rect', None)
        return rect is not None and rect.collidepoint(pos)

    def open_achievements_from_toast(self):
        """Clicking the achievement toast dismisses it and opens the achievements page at its card."""
        achievement_id = self._achievement_notification_id
        self._achievement_notification_active = False
        self._achievement_notification_alpha = 0.0
        self._achievement_toast_rect = None
        if self.results_window.active:
            self.results_window.close_results()
        if not self.menu.is_active() or (self.menu.is_animating and not self.menu.is_opening):
            self.menu.toggle()
        self.menu.show_achievements(achievement_id)

    def update_banner(self):
        """Update banner animation and visibility"""
        if not self.banner_active:
            return

        current_time = time.time()
        elapsed = current_time - self.banner_start_time

        if elapsed < self.banner_fade_duration:
            # Fade in
            self.banner_alpha = elapsed / self.banner_fade_duration
        elif elapsed < self.banner_duration - self.banner_fade_duration:
            # Full visibility
            self.banner_alpha = 1.0
        elif elapsed < self.banner_duration:
            # Fade out
            fade_out_elapsed = elapsed - (self.banner_duration - self.banner_fade_duration)
            self.banner_alpha = 1.0 - (fade_out_elapsed / self.banner_fade_duration)
        else:
            # Banner finished
            self.banner_active = False
            self.banner_alpha = 0.0

    def _blit_gl(self, surface, x, y):
        """Draw a pygame surface on the 2D overlay with its top left at (x, y)."""
        w, h = surface.get_size()
        if w <= 0 or h <= 0:
            return
        x = max(0, min(int(x), self.width - 1))
        y = max(0, int(y))
        texture_data = pygame.image.tostring(surface, 'RGBA', True)
        glRasterPos2f(x, min(self.height, y + h))
        glPixelZoom(1, 1)
        glDrawPixels(w, h, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

    def _get_overlay_surface(self):
        """Full screen transparent surface reused every frame for menus and results."""
        surf = getattr(self, '_overlay_surface', None)
        if surf is None or surf.get_size() != (self.width, self.height):
            surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self._overlay_surface = surf
        surf.fill((0, 0, 0, 0))
        return surf

    def _draw_overlay(self, surface, alpha, offset=(0, 0), texture='_overlay_tex', upload=True):
        """Upload a full screen surface to a texture and draw it as one quad.

        Much faster than tostring + glDrawPixels at high resolutions: the
        surface's BGRA pixels are uploaded without an extra copy. ``offset`` moves
        the quad (menu animations); ``upload=False`` reuses the texture as it is."""
        w, h = surface.get_size()
        if getattr(self, texture, None) is None or getattr(self, texture + '_size', None) != (w, h):
            setattr(self, texture, glGenTextures(1))
            setattr(self, texture + '_size', (w, h))
            upload = True
            glBindTexture(GL_TEXTURE_2D, getattr(self, texture))
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_BGRA, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, getattr(self, texture))
        if upload:
            glPixelStorei(GL_UNPACK_ALIGNMENT, 4)
            glPixelStorei(GL_UNPACK_ROW_LENGTH, surface.get_pitch() // 4)
            view = surface.get_view('1')
            pixels = np.frombuffer(view, dtype=np.uint8)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, pixels)
            del pixels, view  # unlock the surface
            glPixelStorei(GL_UNPACK_ROW_LENGTH, 0)

        x, y = offset
        glEnable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, max(0.0, min(1.0, alpha)))
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x, y)
        glTexCoord2f(1, 0); glVertex2f(x + w, y)
        glTexCoord2f(1, 1); glVertex2f(x + w, y + h)
        glTexCoord2f(0, 1); glVertex2f(x, y + h)
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_TEXTURE_2D)

    def _hud_margin(self):
        return ui.px(24)

    def _render_fps_counter(self, alpha=1.0):
        """FPS pill in the top left corner"""
        try:
            fps = self.clock.get_fps()
            fnt = ui.mono_font(ui.SIZE_SMALL, bold=True)
            label = f"{fps:.0f} FPS" if fps > 0 else "-- FPS"
            text = fnt.render(label, True, ui.MUTED)
            pad_x, pad_y = ui.px(14), ui.px(8)
            surf = pygame.Surface((text.get_width() + pad_x * 2, text.get_height() + pad_y * 2), pygame.SRCALPHA)
            ui.fill_rect(surf, (*ui.SURFACE, 225), surf.get_rect(), ui.radius(10))
            ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(10), width=max(1, ui.px(1.5)))
            surf.blit(text, (pad_x, pad_y))
            if alpha < 1.0:
                surf.set_alpha(int(255 * alpha))
            m = self._hud_margin()
            self._blit_gl(surf, m, m)
        except Exception as e:
            if self.debug_mode:
                print(f"FPS counter rendering error: {e}")

    def _render_game_stats(self, alpha=1.0):
        """Bottom center bar: mode, timer and moves"""
        try:
            current_difficulty = self.menu.get_selected_difficulty()
            game_mode_config = self.menu.get_game_mode_config(current_difficulty)
            timer_enabled = game_mode_config.get("timer_enabled", True)

            segments = []  # (label, value, color, width sample)
            if timer_enabled:
                elapsed = time.time() - self.start_time if self.start_time is not None else 0.0
                if self.time_limit is not None:
                    remaining = max(0.0, self.time_limit - elapsed)
                    color = ui.DANGER if remaining <= 30 else ui.TEXT
                    segments.append(("Time left", ui.format_clock(remaining), color, "00:00"))
                else:
                    segments.append(("Time", ui.format_clock(elapsed), ui.TEXT, "00:00"))
            if self.move_limit is not None:
                remaining_moves = max(0, self.move_limit - self.move_counter)
                color = ui.DANGER if remaining_moves <= 3 else ui.TEXT
                segments.append(("Moves", f"{self.move_counter} / {self.move_limit}", color, f"00 / {self.move_limit}"))
            else:
                segments.append(("Moves", str(self.move_counter), ui.TEXT, "000"))

            label_f = ui.body_font(ui.SIZE_CAPTION)
            value_f = ui.mono_font(ui.SIZE_H3 - 2, bold=True)
            mode_f = ui.display_font(ui.SIZE_H3)
            pad_x = ui.px(26)
            gap = ui.px(26)
            bar_h = label_f.get_height() + value_f.get_height() + ui.px(22)

            mode_name = ui.MODE_NAMES.get(current_difficulty, current_difficulty.replace("_", " ").title())
            mode_surf = ui.render(mode_name, mode_f, ui.TEXT)
            square = ui.px(28)
            mode_w = square + ui.px(12) + mode_surf.get_width()

            # Reserve width for a wide value so the bar does not jitter while the numbers change
            widths = [max(label_f.size(label)[0], value_f.size(sample)[0], value_f.size(value)[0])
                      for label, value, _, sample in segments]
            total_w = pad_x * 2 + mode_w + sum(gap * 2 + w for w in widths)
            surf = pygame.Surface((total_w, bar_h), pygame.SRCALPHA)
            ui.fill_rect(surf, (*ui.SURFACE, 232), surf.get_rect(), ui.radius(14))
            ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(14), width=max(1, ui.px(1.5)))

            x = pad_x
            mark = ui.mode_icon(current_difficulty, square)
            if mark:
                surf.blit(mark, (x, bar_h // 2 - square // 2))
            surf.blit(mode_surf, (x + square + ui.px(12), bar_h // 2 - mode_surf.get_height() // 2 + ui.px(2)))
            x += mode_w
            for (label, value, color, _), width in zip(segments, widths):
                x += gap
                pygame.draw.line(surf, ui.LINE, (x, ui.px(14)), (x, bar_h - ui.px(14)), max(1, ui.px(1.5)))
                x += gap
                ui.draw_text(surf, label, label_f, ui.MUTED, (x, ui.px(10)))
                ui.draw_text(surf, value, value_f, color, (x, ui.px(10) + label_f.get_height()))
                x += width

            if alpha < 1.0:
                surf.set_alpha(int(255 * alpha))
            m = self._hud_margin()
            self._blit_gl(surf, (self.width - total_w) // 2, self.height - bar_h - m)
        except Exception as e:
            if self.debug_mode:
                print(f"Game stats rendering error: {e}")

    def _toast_surface(self, text, alpha):
        fnt = ui.body_font(ui.SIZE_BODY, bold=True)
        t = fnt.render(text, True, ui.TEXT)
        pad_x, pad_y = ui.px(26), ui.px(16)
        surf = pygame.Surface((t.get_width() + pad_x * 2, t.get_height() + pad_y * 2), pygame.SRCALPHA)
        ui.fill_rect(surf, (*ui.SURFACE, 240), surf.get_rect(), ui.radius(12))
        ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(12), width=max(1, ui.px(1.5)))
        surf.blit(t, (pad_x, pad_y))
        surf.set_alpha(int(255 * alpha))
        return surf

    def _render_banner_opengl(self):
        """Short notification toast at the top center"""
        if not self.banner_active or self.banner_alpha <= 0:
            return
        try:
            surf = self._toast_surface(self.banner_text, self.banner_alpha)
            y = self._hud_margin() + int((1.0 - self.banner_alpha) * -ui.px(12))
            if self.hint_banner_active or self.hint_expanded:
                # Stack below the hint so the two never overlap
                y = max(y, getattr(self, '_hint_bottom', 0) + ui.px(12))
            self._blit_gl(surf, (self.width - surf.get_width()) // 2, max(0, y))
        except Exception as e:
            if self.debug_mode:
                print(f"Banner rendering error: {e}")
    
    def _render_game_info(self):
        """Render game information (FPS, moves, time)"""
        try:
            # Import pygame_menu to access the font
            import pygame_menu
            
            # Create font if not exists - use same font as menu
            if not hasattr(self, '_info_font'):
                self._info_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 35)
            
            info_lines = []
            
            # Add FPS if enabled
            if self.show_fps:
                fps = self.clock.get_fps()
                info_lines.append(f"FPS: {fps:.1f}")
            
            # Add move counter and timer
            if self.move_counter > 0:
                info_lines.append(f"Moves: {self.move_counter}")
                
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    info_lines.append(f"Time: {elapsed:.1f}s")
                    
                    if elapsed > 0:
                        tps = self.move_counter / elapsed
                        info_lines.append(f"TPS: {tps:.2f}")
            
            # Render status if solved
            if self.cube_solved:
                info_lines.append("SOLVED!")
            
            # Render each line
            y_offset = 10
            for line in info_lines:
                text_surface = self._info_font.render(line, True, (255, 255, 255))
                text_width, text_height = text_surface.get_size()
                
                # Background
                bg_surface = pygame.Surface((text_width + 20, text_height + 6), pygame.SRCALPHA)
                bg_surface.fill((0, 0, 0, 128))
                bg_surface.blit(text_surface, (10, 3))
                
                # Render to screen
                texture_data = pygame.image.tostring(bg_surface, 'RGBA', True)
                glRasterPos2f(10, y_offset + text_height + 6)
                glPixelZoom(1, 1)
                glDrawPixels(text_width + 20, text_height + 6, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
                
                y_offset += text_height + 12
                
        except Exception as e:
            if self.debug_mode:
                print(f"Game info rendering error: {e}")
