import pygame
import pygame_menu
import time
from OpenGL.GL import *
from utils.path_helper import resource_path

class HelpOverlay:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.active = False
        self.animation_duration = 0.3  # seconds
        self.fade_start_time = 0
        self.is_animating = False
        self.target_alpha = 0.0
        self.current_alpha = 0.0
        
        # Button dimensions and position - make it responsive to screen size
        self.help_button_size = max(40, min(50, int(width * 0.045)))  # 4.5% of screen width, min 40px, max 60px
        self.help_button_margin = max(12, int(width * 0.015))  # 1.5% of screen width, min 12px
        self.button_spacing = 8  # Space between buttons
        
        # Help button position (leftmost)
        self.help_button_rect = pygame.Rect(
            self.width - (self.help_button_size * 2) - self.help_button_margin - self.button_spacing,
            self.help_button_margin,
            self.help_button_size,
            self.help_button_size
        )
        
        # Menu button position (rightmost)
        self.menu_button_rect = pygame.Rect(
            self.width - self.help_button_size - self.help_button_margin,
            self.help_button_margin,
            self.help_button_size,
            self.help_button_size
        )
        
        # Load help icon with high quality scaling
        try:
            # Load the original icon at a higher resolution for better quality
            original_icon = pygame.image.load(resource_path("utils/icons/help_icon.png"))
            
            # Use smoothscale for better quality when scaling down
            # Scale to 2x the button size first, then scale down for anti-aliasing effect
            high_res_size = self.help_button_size * 2
            high_res_icon = pygame.transform.smoothscale(original_icon, (high_res_size, high_res_size))
            self.help_icon = pygame.transform.smoothscale(high_res_icon, (self.help_button_size, self.help_button_size))
        except:
            # Create a high-quality fallback icon if the image fails to load
            self.help_icon = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
            
            # Create a smooth circular background
            center = self.help_button_size // 2
            radius = center - 3
            
            # Draw anti-aliased circle
            pygame.draw.circle(self.help_icon, (255, 255, 255, 220), (center, center), radius)
            pygame.draw.circle(self.help_icon, (200, 200, 200, 150), (center, center), radius, 2)
            
            # Create high-quality question mark
            font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, int(self.help_button_size * 0.6))
            text = font.render("?", True, (60, 60, 60))
            text_rect = text.get_rect(center=(center, center))
            self.help_icon.blit(text, text_rect)
        
        # Load menu icon with high quality scaling
        try:
            # Load the original menu icon at a higher resolution for better quality
            original_menu_icon = pygame.image.load(resource_path("utils/icons/menu_icon.png"))
            
            # Use smoothscale for better quality when scaling down
            # Scale to 2x the button size first, then scale down for anti-aliasing effect
            high_res_size = self.help_button_size * 2
            high_res_menu_icon = pygame.transform.smoothscale(original_menu_icon, (high_res_size, high_res_size))
            self.menu_icon = pygame.transform.smoothscale(high_res_menu_icon, (self.help_button_size, self.help_button_size))
        except:
            # Create a high-quality fallback menu icon if the image fails to load
            self.menu_icon = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
            
            # Create a hamburger menu icon
            center = self.help_button_size // 2
            line_width = int(self.help_button_size * 0.6)
            line_height = max(2, int(self.help_button_size * 0.08))
            line_spacing = int(self.help_button_size * 0.2)
            
            # Draw three horizontal lines for hamburger menu
            start_x = (self.help_button_size - line_width) // 2
            for i in range(3):
                y = center - line_spacing + (i * line_spacing)
                pygame.draw.rect(self.menu_icon, (255, 255, 255, 220), 
                               (start_x, y - line_height//2, line_width, line_height))
        
        # Button state tracking
        self.is_hovering_help = False
        self.is_hovering_menu = False
        self.game_callback = None  # Will be set from game instance
        
        # Help panel properties - bigger to accommodate larger fonts
        self.panel_width = min(650, self.width - 100)
        self.panel_height = min(500, self.height - 100)
        self.panel_x = (self.width - self.panel_width) // 2
        self.panel_y = (self.height - self.panel_height) // 2
        
        # Initialize fonts (same as menu for consistency) - bigger sizes
        pygame.font.init()
        self.title_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 50)
        self.section_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 40)
        self.text_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 35)
        
        # Performance optimization - cache surfaces for both buttons
        self.text_cache = {}
        self.panel_surface = None
        self.panel_dirty = True
        self.help_button_surface = None
        self.help_button_surface_hover = None
        self.menu_button_surface = None
        self.menu_button_surface_hover = None
        self.is_hovering = False  # For backward compatibility (help button)
        self._create_button_surfaces()
        
        # Help content - more compact layout
        self.help_sections = [
            {
                "title": "Cube Moves",
                "items": [
                    "L  ->  Left    | R  ->  Right",
                    "U  ->  Up      | D  ->  Down",
                    "F  ->  Front   | B  ->  Back",
                    "M  ->  Middle",
                    "E  ->  Equator",
                    "S  ->  Slice"
                ]
            },
            {
                "title": "Game Controls",
                "items": [
                    "ESC  ->  Main menu",
                    "T  ->  Reset view",
                    "Z  ->  Undo",
                    "X  ->  Scramble (freeplay)"
                ]
            }
        ]
        
    def toggle(self):
        """Toggle the help overlay visibility with animation"""
        if self.is_animating:
            return  # Ignore toggle requests during animation
            
        self.active = not self.active
        self.target_alpha = 1.0 if self.active else 0.0
        self.fade_start_time = time.time()
        self.is_animating = True
        self.panel_dirty = True  # Mark for re-rendering
        
    def update(self):
        """Update animation state"""
        if not self.is_animating:
            return
            
        elapsed = time.time() - self.fade_start_time
        progress = min(elapsed / self.animation_duration, 1.0)
        
        if self.target_alpha > self.current_alpha:
            # Fading in
            self.current_alpha = progress * self.target_alpha
        else:
            # Fading out
            self.current_alpha = (1.0 - progress) * 1.0
            
        if progress >= 1.0:
            self.is_animating = False
            self.current_alpha = self.target_alpha
            if self.current_alpha == 0.0:
                self.active = False
                
    def get_current_alpha(self):
        """Get current alpha for rendering"""
        return self.current_alpha
        
    def should_render(self):
        """Check if the overlay needs to be rendered (for performance)"""
        return True  # Always render the button at minimum
        
    def handle_click(self, mouse_pos):
        """Handle mouse clicks on both buttons"""
        if self.help_button_rect.collidepoint(mouse_pos):
            self.toggle()
            return True
        elif self.menu_button_rect.collidepoint(mouse_pos):
            # Handle menu button click
            if self.game_callback:
                self.game_callback('toggle_menu')
            return True
        elif self.active and self.current_alpha > 0.5:
            # Click outside help panel to close
            panel_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_width, self.panel_height)
            if not panel_rect.collidepoint(mouse_pos):
                self.toggle()
                return True
        return False
        
    def _create_button_surfaces(self):
        """Create the cached button surfaces for both help and menu buttons"""
        # Create help button surfaces
        self._create_help_button_surface()
        # Create menu button surfaces
        self._create_menu_button_surface()
    
    def _create_help_button_surface(self):
        """Create the cached help button surfaces for normal and hover states"""
        # Normal state button
        self.help_button_surface = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
        
        # Normal button background
        button_color = (40, 40, 40, 200)
        pygame.draw.rect(self.help_button_surface, button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        
        # Normal border
        pygame.draw.rect(self.help_button_surface, (100, 150, 255, 150), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=1, border_radius=6)
        
        # Center the help icon properly with padding
        icon_padding = 6  # Padding from edges
        icon_size = self.help_button_size - (icon_padding * 2)
        
        # Use smoothscale for high-quality scaling
        scaled_icon = pygame.transform.smoothscale(self.help_icon, (icon_size, icon_size))
        
        # Calculate centered position
        icon_x = (self.help_button_size - icon_size) // 2
        icon_y = (self.help_button_size - icon_size) // 2
        
        self.help_button_surface.blit(scaled_icon, (icon_x, icon_y))
        
        # Hover state button
        self.help_button_surface_hover = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
        
        # Hover button background (brighter)
        hover_button_color = (60, 60, 70, 230)
        pygame.draw.rect(self.help_button_surface_hover, hover_button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        
        # Hover border (brighter and thicker)
        pygame.draw.rect(self.help_button_surface_hover, (120, 170, 255, 200), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=2, border_radius=6)
        
        # Add a subtle glow effect
        glow_surface = pygame.Surface((self.help_button_size + 4, self.help_button_size + 4), pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (120, 170, 255, 40), 
                        (0, 0, self.help_button_size + 4, self.help_button_size + 4), 
                        border_radius=8)
        self.help_button_surface_hover.blit(glow_surface, (-2, -2))
        
        # Blit the button content on top
        pygame.draw.rect(self.help_button_surface_hover, hover_button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        pygame.draw.rect(self.help_button_surface_hover, (120, 170, 255, 200), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=2, border_radius=6)
        
        # Scale and center the help icon for hover state (slightly brighter)
        scaled_icon_hover = scaled_icon.copy()
        # Add a slight brightness boost to the icon on hover
        bright_overlay = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
        bright_overlay.fill((255, 255, 255, 30))
        scaled_icon_hover.blit(bright_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        
        # Use the same centered position for hover state
        self.help_button_surface_hover.blit(scaled_icon_hover, (icon_x, icon_y))
    
    def _create_menu_button_surface(self):
        """Create the cached menu button surfaces for normal and hover states"""
        # Normal state button
        self.menu_button_surface = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
        
        # Normal button background (slightly different color for distinction)
        button_color = (40, 40, 40, 200)
        pygame.draw.rect(self.menu_button_surface, button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        
        # Normal border (green-ish for menu)
        pygame.draw.rect(self.menu_button_surface, (100, 200, 100, 150), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=1, border_radius=6)
        
        # Center the menu icon properly with padding
        icon_padding = 6  # Padding from edges
        icon_size = self.help_button_size - (icon_padding * 2)
        
        # Use smoothscale for high-quality scaling
        scaled_menu_icon = pygame.transform.smoothscale(self.menu_icon, (icon_size, icon_size))
        
        # Calculate centered position
        icon_x = (self.help_button_size - icon_size) // 2
        icon_y = (self.help_button_size - icon_size) // 2
        
        self.menu_button_surface.blit(scaled_menu_icon, (icon_x, icon_y))
        
        # Hover state button
        self.menu_button_surface_hover = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
        
        # Hover button background (brighter)
        hover_button_color = (60, 60, 70, 230)
        pygame.draw.rect(self.menu_button_surface_hover, hover_button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        
        # Hover border (brighter green and thicker)
        pygame.draw.rect(self.menu_button_surface_hover, (120, 220, 120, 200), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=2, border_radius=6)
        
        # Add a subtle glow effect (green-ish)
        glow_surface = pygame.Surface((self.help_button_size + 4, self.help_button_size + 4), pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (120, 220, 120, 40), 
                        (0, 0, self.help_button_size + 4, self.help_button_size + 4), 
                        border_radius=8)
        self.menu_button_surface_hover.blit(glow_surface, (-2, -2))
        
        # Blit the button content on top
        pygame.draw.rect(self.menu_button_surface_hover, hover_button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        pygame.draw.rect(self.menu_button_surface_hover, (120, 220, 120, 200), 
                        (0, 0, self.help_button_size, self.help_button_size), 
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
        """Update hover state based on mouse position for both buttons"""
        was_hovering_help = self.is_hovering_help
        was_hovering_menu = self.is_hovering_menu
        
        self.is_hovering_help = self.help_button_rect.collidepoint(mouse_pos)
        self.is_hovering_menu = self.menu_button_rect.collidepoint(mouse_pos)
        
        # For backward compatibility
        self.is_hovering = self.is_hovering_help
        
        # Return True if any hover state changed
        return (was_hovering_help != self.is_hovering_help or 
                was_hovering_menu != self.is_hovering_menu)
        
    def draw_help_button(self, surface):
        """Draw the help button using cached surface with hover effects"""
        if self.is_hovering_help:
            surface.blit(self.help_button_surface_hover, self.help_button_rect.topleft)
        else:
            surface.blit(self.help_button_surface, self.help_button_rect.topleft)
    
    def draw_menu_button(self, surface):
        """Draw the menu button using cached surface with hover effects"""
        if self.is_hovering_menu:
            surface.blit(self.menu_button_surface_hover, self.menu_button_rect.topleft)
        else:
            surface.blit(self.menu_button_surface, self.menu_button_rect.topleft)
        
    def draw_help_panel(self, surface):
        """Draw the help panel with caching for performance"""
        if self.current_alpha <= 0:
            return
            
        # Create cached panel surface if dirty or doesn't exist
        if self.panel_dirty or self.panel_surface is None:
            self._create_panel_surface()
            self.panel_dirty = False
        
        # Apply current alpha to cached surface
        if self.current_alpha < 1.0:
            # Create alpha-modified version
            alpha_surface = self.panel_surface.copy()
            alpha_overlay = pygame.Surface((self.panel_width, self.panel_height), pygame.SRCALPHA)
            alpha_overlay.fill((255, 255, 255, int(255 * self.current_alpha)))
            alpha_surface.blit(alpha_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(alpha_surface, (self.panel_x, self.panel_y))
        else:
            surface.blit(self.panel_surface, (self.panel_x, self.panel_y))
    
    def _create_panel_surface(self):
        """Create the cached panel surface"""
        self.panel_surface = pygame.Surface((self.panel_width, self.panel_height), pygame.SRCALPHA)
        
        # Background with modern look
        bg_color = (25, 25, 35, 235)
        pygame.draw.rect(self.panel_surface, bg_color, (0, 0, self.panel_width, self.panel_height), border_radius=12)
        
        # Accent border
        border_color = (100, 150, 255, 180)
        pygame.draw.rect(self.panel_surface, border_color, (0, 0, self.panel_width, self.panel_height), 
                        width=2, border_radius=12)
        
        # Title
        title_text = self.title_font.render("Quick Help", True, (255, 255, 255))
        title_rect = title_text.get_rect(centerx=self.panel_width//2, y=20)
        self.panel_surface.blit(title_text, title_rect)
        
        # Accent line under title
        line_y = title_rect.bottom + 8
        pygame.draw.line(self.panel_surface, (100, 150, 255, 180), 
                        (40, line_y), (self.panel_width - 40, line_y), 2)
        
        # Content in two columns for compact layout - adjusted spacing for bigger fonts
        y_offset = line_y + 25
        col_width = (self.panel_width - 60) // 2
        
        for i, section in enumerate(self.help_sections):
            # Determine column position
            col_x = 30 if i % 2 == 0 else 30 + col_width + 15
            section_y = y_offset + (i // 2) * 140
            
            # Section title
            section_text = self.section_font.render(section["title"], True, (235, 38, 38))
            self.panel_surface.blit(section_text, (col_x, section_y))
            
            # Section items
            item_y = section_y + 50
            for item in section["items"]:
                item_text = self.text_font.render(f"• {item}", True, (220, 220, 220))
                self.panel_surface.blit(item_text, (col_x + 10, item_y))
                item_y += 40
        
        # Close instruction
        close_text = self.text_font.render("Click outside or press ESC to close", True, (150, 150, 150))
        close_rect = close_text.get_rect(centerx=self.panel_width//2, y=self.panel_height - 45)
        self.panel_surface.blit(close_text, close_rect)
        
    def draw(self, surface):
        """Draw the complete help overlay efficiently"""
        # Always draw both buttons (they're cached)
        self.draw_help_button(surface)
        self.draw_menu_button(surface)
        
        # Only draw help panel if it's actually visible
        if (self.active or self.current_alpha > 0) and self.current_alpha > 0.01:
            self.draw_help_panel(surface)
            
    def update_dimensions(self, width, height):
        """Update dimensions when screen size changes"""
        self.width = width
        self.height = height
        
        # Update responsive button size and margin
        self.help_button_size = max(40, min(60, int(width * 0.045)))  # 4.5% of screen width, min 40px, max 60px
        self.help_button_margin = max(12, int(width * 0.015))  # 1.5% of screen width, min 12px
        self.button_spacing = 8  # Space between buttons
        
        # Update help button position (leftmost)
        self.help_button_rect = pygame.Rect(
            self.width - (self.help_button_size * 2) - self.help_button_margin - self.button_spacing,
            self.help_button_margin,
            self.help_button_size,
            self.help_button_size
        )
        
        # Update menu button position (rightmost)
        self.menu_button_rect = pygame.Rect(
            self.width - self.help_button_size - self.help_button_margin,
            self.help_button_margin,
            self.help_button_size,
            self.help_button_size
        )
        
        # Update panel position and size - bigger for larger fonts
        self.panel_width = min(650, self.width - 100)
        self.panel_height = min(500, self.height - 100)
        self.panel_x = (self.width - self.panel_width) // 2
        self.panel_y = (self.height - self.panel_height) // 2
        self.panel_dirty = True  # Mark for re-rendering
        
        # Recreate button surfaces for new dimensions
        self._create_button_surfaces()

    def set_game_callback(self, callback):
        """Set the callback function for game actions"""
        self.game_callback = callback
