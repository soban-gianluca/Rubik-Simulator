import pygame
from src import ui_style as ui


class GameMenuButton:
    """Square icon button in the top right corner that opens the menu."""

    def __init__(self, width, height):
        self.is_hovering_menu = False
        self.game_callback = None  # Will be set from game instance
        self.update_dimensions(width, height)

    def _recalculate_dimensions(self, width, height):
        """Recalculate button size and position based on screen size"""
        self.width = width
        self.height = height
        self.button_size = ui.px(56)
        self.button_margin = ui.px(24)
        self.menu_button_rect = pygame.Rect(
            self.width - self.button_size - self.button_margin,
            self.button_margin,
            self.button_size,
            self.button_size
        )

    def _create_button_surfaces(self):
        """Create the cached normal and hover surfaces"""
        size = self.button_size
        icon_size = int(size * 0.5)
        self.menu_button_surface = self._make_surface(size, icon_size, ui.SURFACE, ui.MUTED)
        self.menu_button_surface_hover = self._make_surface(size, icon_size, ui.SURFACE_3, ui.TEXT)

    def _make_surface(self, size, icon_size, fill, icon_color):
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        rect = surface.get_rect()
        ui.fill_rect(surface, (*fill, 235), rect, ui.radius(12))
        ui.fill_rect(surface, ui.LINE, rect, ui.radius(12), width=max(1, ui.px(1.5)))
        ic = ui.icon("menu", icon_size, icon_color)
        if ic:
            surface.blit(ic, ic.get_rect(center=rect.center))
        else:
            # Fallback: three lines
            bar_w, bar_h = icon_size, max(2, size // 18)
            for i in (-1, 0, 1):
                pygame.draw.rect(surface, icon_color,
                                 (rect.centerx - bar_w // 2, rect.centery + i * size // 6 - bar_h // 2, bar_w, bar_h))
        return surface

    def update_hover(self, mouse_pos):
        """Update hover state. Returns True if it changed."""
        was_hovering_menu = self.is_hovering_menu
        self.is_hovering_menu = self.menu_button_rect.collidepoint(mouse_pos)
        return was_hovering_menu != self.is_hovering_menu

    def handle_click(self, mouse_pos):
        """Handle mouse clicks on the menu button"""
        if self.menu_button_rect.collidepoint(mouse_pos):
            if self.game_callback:
                self.game_callback('toggle_menu')
            return True
        return False

    def draw(self, surface):
        """Draw the menu button"""
        if self.is_hovering_menu:
            surface.blit(self.menu_button_surface_hover, self.menu_button_rect.topleft)
        else:
            surface.blit(self.menu_button_surface, self.menu_button_rect.topleft)

    def update_dimensions(self, width, height):
        """Update dimensions when screen size changes"""
        self._recalculate_dimensions(width, height)
        self._create_button_surfaces()

    def set_game_callback(self, callback):
        """Set the callback function for game actions"""
        self.game_callback = callback
