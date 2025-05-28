import pygame

class Menu:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.active = False
        
        # Fonts
        self.font_large = pygame.font.SysFont('Arial', 48, bold=True)
        self.font_medium = pygame.font.SysFont('Arial', 32)
        
        # Button configuration
        self.play_button = {
            'rect': pygame.Rect(screen_width//2 - 100, screen_height//2 + 30, 200, 60),
            'text': 'Play',
            'color': (50, 150, 50)
        }
        
        self.settings_button = {
            'rect': pygame.Rect(screen_width//2 - 100, screen_height//2 + 120, 200, 60),
            'text': 'Settings',
            'color': (50, 150, 50)
        }
    
    def toggle(self):
        """Toggle menu visibility"""
        self.active = not self.active
        return self.active
    
    def is_active(self):
        """Check if menu is visible"""
        return self.active
        
    def handle_event(self, event):
        """Process menu input"""
        if not self.active or event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
            
        # Check if play button was clicked
        if self.play_button['rect'].collidepoint(event.pos):
            self.active = False
            return True
        
        # Check if settings button was clicked
        if self.settings_button['rect'].collidepoint(event.pos):
            self.active = False
            return True
            
        return False
    
    def draw(self, screen):
        """Render the menu"""
        if not self.active:
            return
            
        # Background overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # Title
        title = self.font_large.render("Rubik's Cube Simulator", True, (255, 255, 255))
        screen.blit(title, title.get_rect(center=(self.width//2, self.height//3)))
        
        # Play button
        play_btn = self.play_button
        pygame.draw.rect(screen, play_btn['color'], play_btn['rect'], border_radius=15)
        pygame.draw.rect(screen, (255, 255, 255), play_btn['rect'], 2, border_radius=15)
                
        # Settings button
        settings_btn = self.settings_button
        pygame.draw.rect(screen, settings_btn['color'], settings_btn['rect'], border_radius=15)
        pygame.draw.rect(screen, (255, 255, 255), settings_btn['rect'], 2, border_radius=15)
        
        # Play button text
        text = self.font_medium.render(play_btn['text'], True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=play_btn['rect'].center))
        
        # Settings button text
        text = self.font_medium.render(settings_btn['text'], True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=settings_btn['rect'].center))