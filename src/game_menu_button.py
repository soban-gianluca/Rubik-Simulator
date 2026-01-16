import pygame
import pygame_menu
from utils.path_helper import resource_path

class GameMenuButton:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
        # Button dimensions and position - make it responsive to screen size
        self.button_size = max(40, min(48, int(width * 0.045)))  # 4.5% of screen width, min 40px, max 48px
        self.button_margin = max(12, int(width * 0.015))  # 1.5% of screen width, min 12px
        
        # Menu button position (top right)
        self.menu_button_rect = pygame.Rect(
            self.width - self.button_size - self.button_margin,
            self.button_margin,
            self.button_size,
            self.button_size
        )
        
        # Load menu icon
        try:
            # Load the original menu icon
            original_menu_icon = pygame.image.load(resource_path("utils/icons/menu_icon.png"))
            
            # Use smoothscale for better quality when scaling down
            # Scale to 2x the button size first, then scale down for anti-aliasing effect
            high_res_size = self.button_size * 2
            high_res_menu_icon = pygame.transform.smoothscale(original_menu_icon, (high_res_size, high_res_size))
            self.menu_icon = pygame.transform.smoothscale(high_res_menu_icon, (self.button_size, self.button_size))
        except:
            # Create a high-quality fallback menu icon if the image fails to load
            self.menu_icon = pygame.Surface((self.button_size, self.button_size), pygame.SRCALPHA)
            
            # Create a hamburger menu icon
            center = self.button_size // 2
            line_width = int(self.button_size * 0.6)
            line_height = max(2, int(self.button_size * 0.08))
            line_spacing = int(self.button_size * 0.2)
            
            # Draw three horizontal lines for hamburger menu
            start_x = (self.button_size - line_width) // 2
            for i in range(3):
                y = center - line_spacing + (i * line_spacing)
                pygame.draw.rect(self.menu_icon, (255, 255, 255, 220), 
                               (start_x, y - line_height//2, line_width, line_height))
        
        # Button state tracking
        self.is_hovering_menu = False
        self.game_callback = None  # Will be set from game instance
        
        # Performance optimization - cache surfaces
        self.menu_button_surface = None
        self.menu_button_surface_hover = None
        self._create_button_surfaces()
        
    def _create_button_surfaces(self):
        """Create the cached button surfaces for menu button"""
        # Normal state button
        self.menu_button_surface = pygame.Surface((self.button_size, self.button_size), pygame.SRCALPHA)
        
        # Normal button background
        button_color = (40, 40, 40, 200)
        pygame.draw.rect(self.menu_button_surface, button_color, 
                        (0, 0, self.button_size, self.button_size), 
                        border_radius=10)
        
        # Normal border (green-ish for menu)
        pygame.draw.rect(self.menu_button_surface, (100, 200, 100, 150), 
                        (0, 0, self.button_size, self.button_size), 
                        width=1, border_radius=10)
        
        # Center the menu icon properly with padding
        icon_padding = 6  # Padding from edges
        icon_size = self.button_size - (icon_padding * 2)
        
        # Use smoothscale for high-quality scaling
        scaled_menu_icon = pygame.transform.smoothscale(self.menu_icon, (icon_size, icon_size))
        
        # Calculate centered position
        icon_x = (self.button_size - icon_size) // 2
        icon_y = (self.button_size - icon_size) // 2
        
        self.menu_button_surface.blit(scaled_menu_icon, (icon_x, icon_y))
        
        # Hover state button
        self.menu_button_surface_hover = pygame.Surface((self.button_size, self.button_size), pygame.SRCALPHA)
        
        # Hover button background (brighter)
        hover_button_color = (60, 60, 70, 230)
        pygame.draw.rect(self.menu_button_surface_hover, hover_button_color, 
                        (0, 0, self.button_size, self.button_size), 
                        border_radius=6)
        
        # Hover border (brighter green and thicker)
        pygame.draw.rect(self.menu_button_surface_hover, (120, 220, 120, 200), 
                        (0, 0, self.button_size, self.button_size), 
                        width=2, border_radius=6)
        
        # Add a subtle glow effect (green-ish)
        glow_surface = pygame.Surface((self.button_size + 4, self.button_size + 4), pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (120, 220, 120, 40), 
                        (0, 0, self.button_size + 4, self.button_size + 4), 
                        border_radius=8)
        self.menu_button_surface_hover.blit(glow_surface, (-2, -2))
        
        # Blit the button content on top
        pygame.draw.rect(self.menu_button_surface_hover, hover_button_color, 
                        (0, 0, self.button_size, self.button_size), 
                        border_radius=6)
        pygame.draw.rect(self.menu_button_surface_hover, (120, 220, 120, 200), 
                        (0, 0, self.button_size, self.button_size), 
                        width=2, border_radius=6)
        
        # Scale and center the menu icon for hover state (slightly brighter)
        scaled_menu_icon_hover = scaled_menu_icon.copy()
        # Add a slight brightness boost to the icon on hover
        bright_overlay = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
        bright_overlay.fill((255, 255, 255, 30))
        scaled_menu_icon_hover.blit(bright_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        
        # Use the same centered position for hover state
        self.menu_button_surface_hover.blit(scaled_menu_icon_hover, (icon_x, icon_y))
        
    def update_hover(self, mouse_pos):
        """Update hover state based on mouse position"""
        was_hovering_menu = self.is_hovering_menu
        self.is_hovering_menu = self.menu_button_rect.collidepoint(mouse_pos)
        
        # Return True if hover state changed
        return was_hovering_menu != self.is_hovering_menu
    
    def handle_click(self, mouse_pos):
        """Handle mouse clicks on the menu button"""
        if self.menu_button_rect.collidepoint(mouse_pos):
            # Handle menu button click
            if self.game_callback:
                self.game_callback('toggle_menu')
            return True
        return False
    
    def draw_menu_button(self, surface):
        """Draw the menu button using cached surface with hover effects"""
        if self.is_hovering_menu:
            surface.blit(self.menu_button_surface_hover, self.menu_button_rect.topleft)
        else:
            surface.blit(self.menu_button_surface, self.menu_button_rect.topleft)
    
    def draw(self, surface):
        """Draw the menu button"""
        self.draw_menu_button(surface)
            
    def update_dimensions(self, width, height):
        """Update dimensions when screen size changes"""
        self.width = width
        self.height = height
        
        self.button_size = max(40, min(60, int(width * 0.045)))  # 4.5% of screen width, min 40px, max 60px
        self.button_margin = max(12, int(width * 0.015))  # 1.5% of screen width, min 12px
        
        # Update menu button position (top right)
        self.menu_button_rect = pygame.Rect(
            self.width - self.button_size - self.button_margin,
            self.button_margin,
            self.button_size,
            self.button_size
        )
        
        # Recreate button surfaces for new dimensions
        self._create_button_surfaces()

    def set_game_callback(self, callback):
        """Set the callback function for game actions"""
        self.game_callback = callback
