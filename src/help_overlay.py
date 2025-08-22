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
        
        # Button dimensions and position
        self.help_button_size = 50
        self.help_button_margin = 20
        self.help_button_rect = pygame.Rect(
            self.width - self.help_button_size - self.help_button_margin,
            self.help_button_margin,
            self.help_button_size,
            self.help_button_size
        )
        
        # Load help icon
        try:
            self.help_icon = pygame.image.load(resource_path("utils/icons/help_icon.png"))
            self.help_icon = pygame.transform.scale(self.help_icon, (self.help_button_size, self.help_button_size))
        except:
            # Create a fallback icon if the image fails to load
            self.help_icon = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
            pygame.draw.circle(self.help_icon, (255, 255, 255, 200), 
                             (self.help_button_size//2, self.help_button_size//2), 
                             self.help_button_size//2 - 2, 2)
            font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 28)
            text = font.render("?", True, (255, 255, 255))
            text_rect = text.get_rect(center=(self.help_button_size//2, self.help_button_size//2))
            self.help_icon.blit(text, text_rect)
        
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
        
        # Performance optimization - cache surfaces
        self.text_cache = {}
        self.panel_surface = None
        self.panel_dirty = True
        self.button_surface = None
        self.button_surface_hover = None
        self.is_hovering = False
        self._create_button_surface()
        
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
        """Handle mouse clicks on the help button"""
        if self.help_button_rect.collidepoint(mouse_pos):
            self.toggle()
            return True
        elif self.active and self.current_alpha > 0.5:
            # Click outside help panel to close
            panel_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_width, self.panel_height)
            if not panel_rect.collidepoint(mouse_pos):
                self.toggle()
                return True
        return False
        
    def _create_button_surface(self):
        """Create the cached button surfaces for normal and hover states"""
        # Normal state button
        self.button_surface = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
        
        # Normal button background
        button_color = (40, 40, 40, 200)
        pygame.draw.rect(self.button_surface, button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        
        # Normal border
        pygame.draw.rect(self.button_surface, (100, 150, 255, 150), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=1, border_radius=6)
        
        # Scale and blit the help icon
        icon_size = self.help_button_size - 8  # Add some padding
        scaled_icon = pygame.transform.scale(self.help_icon, (icon_size, icon_size))
        self.button_surface.blit(scaled_icon, (4, 4))
        
        # Hover state button
        self.button_surface_hover = pygame.Surface((self.help_button_size, self.help_button_size), pygame.SRCALPHA)
        
        # Hover button background (brighter)
        hover_button_color = (60, 60, 70, 230)
        pygame.draw.rect(self.button_surface_hover, hover_button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        
        # Hover border (brighter and thicker)
        pygame.draw.rect(self.button_surface_hover, (120, 170, 255, 200), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=2, border_radius=6)
        
        # Add a subtle glow effect
        glow_surface = pygame.Surface((self.help_button_size + 4, self.help_button_size + 4), pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (120, 170, 255, 40), 
                        (0, 0, self.help_button_size + 4, self.help_button_size + 4), 
                        border_radius=8)
        self.button_surface_hover.blit(glow_surface, (-2, -2))
        
        # Blit the button content on top
        pygame.draw.rect(self.button_surface_hover, hover_button_color, 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        border_radius=6)
        pygame.draw.rect(self.button_surface_hover, (120, 170, 255, 200), 
                        (0, 0, self.help_button_size, self.help_button_size), 
                        width=2, border_radius=6)
        
        # Scale and blit the help icon (slightly brighter for hover)
        scaled_icon_hover = scaled_icon.copy()
        # Add a slight brightness boost to the icon on hover
        bright_overlay = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
        bright_overlay.fill((255, 255, 255, 30))
        scaled_icon_hover.blit(bright_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        self.button_surface_hover.blit(scaled_icon_hover, (4, 4))
        
    def update_hover(self, mouse_pos):
        """Update hover state based on mouse position"""
        was_hovering = self.is_hovering
        self.is_hovering = self.help_button_rect.collidepoint(mouse_pos)
        return was_hovering != self.is_hovering  # Return True if hover state changed
        
    def draw_help_button(self, surface):
        """Draw the help button using cached surface with hover effects"""
        if self.is_hovering:
            surface.blit(self.button_surface_hover, self.help_button_rect.topleft)
        else:
            surface.blit(self.button_surface, self.help_button_rect.topleft)
        
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
        # Always draw the help button (it's cached)
        self.draw_help_button(surface)
        
        # Only draw help panel if it's actually visible
        if (self.active or self.current_alpha > 0) and self.current_alpha > 0.01:
            self.draw_help_panel(surface)
            
    def update_dimensions(self, width, height):
        """Update dimensions when screen size changes"""
        self.width = width
        self.height = height
        
        # Update help button position
        self.help_button_rect = pygame.Rect(
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
        self._create_button_surface()
