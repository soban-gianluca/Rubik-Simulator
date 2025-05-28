import pygame

class Menu:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.active = False
        self.settings_active = False
        
        # Fonts
        self.font_large = pygame.font.SysFont('Arial', 48, bold=True)
        self.font_medium = pygame.font.SysFont('Arial', 32)
        self.font_small = pygame.font.SysFont('Arial', 24)
        
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
        
        # Settings window elements
        self.back_button = {
            'rect': pygame.Rect(screen_width//2 - 100, screen_height - 100, 200, 50),
            'text': 'Back',
            'color': (150, 50, 50)
        }
        
        # Settings options - now with checkboxes instead of sliders
        self.settings_options = {
            'fullscreen': {
                'value': False,
                'text': 'Fullscreen',
                'rect': pygame.Rect(screen_width//2 - 150, screen_height//2 - 100, 25, 25),
                'label_rect': pygame.Rect(screen_width//2 - 110, screen_height//2 - 100, 200, 25)
            },
            'show_fps': {
                'value': False,
                'text': 'Show FPS',
                'rect': pygame.Rect(screen_width//2 - 150, screen_height//2, 25, 25),
                'label_rect': pygame.Rect(screen_width//2 - 110, screen_height//2, 200, 25)
            },
        }
        
        # Track which setting is being adjusted
        self.active_setting = None
        
        # Help button with icon
        try:
            self.help_icon = pygame.image.load("utils/help_icon.png")
            self.help_icon = pygame.transform.scale(self.help_icon, (30, 30))
            self.help_button = {
                'rect': pygame.Rect(screen_width - 50, 20, 30, 30),
                'icon': self.help_icon
            }
        except:
            print("Help icon not found, using text instead")
            self.help_button = {
                'rect': pygame.Rect(screen_width - 80, 20, 60, 30),
                'text': 'Help',
                'color': (100, 100, 150)
            }
    
    def toggle(self):
        """Toggle menu visibility"""
        self.active = not self.active
        if not self.active:
            self.settings_active = False
        return self.active
    
    def is_active(self):
        """Check if menu is visible"""
        return self.active
        
    def handle_event(self, event):
        """Process menu input"""
        if not self.active:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # In settings view
            if self.settings_active:
                # Back button
                if self.back_button['rect'].collidepoint(event.pos):
                    self.settings_active = False
                    return True
                
                # Check checkbox interactions
                for key, option in self.settings_options.items():
                    if option['rect'].collidepoint(event.pos):
                        # Toggle the checkbox value
                        option['value'] = not option['value']
                        print(f"Setting {key} changed to {option['value']}")
                        return True
                
                # Help button
                if hasattr(self, 'help_button') and self.help_button['rect'].collidepoint(event.pos):
                    print("Help button clicked - show controls and instructions")
                    return True
                
            # Main menu view    
            else:
                # Play button
                if self.play_button['rect'].collidepoint(event.pos):
                    self.active = False
                    return True
                
                # Settings button
                if self.settings_button['rect'].collidepoint(event.pos):
                    self.settings_active = True
                    return True
            
        return False
    
    def get_setting(self, name):
        """Get a setting value"""
        if name in self.settings_options:
            return self.settings_options[name]['value']
        return None
    
    def draw(self, screen):
        """Render the menu"""
        if not self.active:
            return
            
        # Background overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        if self.settings_active:
            self._draw_settings(screen)
        else:
            self._draw_main_menu(screen)
    
    def _draw_main_menu(self, screen):
        """Draw the main menu"""
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
    
    def _draw_settings(self, screen):
        """Draw the settings menu"""
        # Title
        title = self.font_large.render("Settings", True, (255, 255, 255))
        screen.blit(title, title.get_rect(center=(self.width//2, self.height//5)))
        
        # Draw checkboxes
        for key, option in self.settings_options.items():
            # Checkbox outline
            pygame.draw.rect(screen, (200, 200, 200), option['rect'], border_radius=3)
            
            # Fill checkbox if selected
            if option['value']:
                inner_rect = pygame.Rect(
                    option['rect'].x + 5, 
                    option['rect'].y + 5, 
                    option['rect'].width - 10, 
                    option['rect'].height - 10
                )
                pygame.draw.rect(screen, (100, 255, 100), inner_rect, border_radius=2)
            
            # Label
            label = self.font_small.render(option['text'], True, (255, 255, 255))
            screen.blit(label, option['label_rect'])
        
        # Back button
        back_btn = self.back_button
        pygame.draw.rect(screen, back_btn['color'], back_btn['rect'], border_radius=10)
        pygame.draw.rect(screen, (255, 255, 255), back_btn['rect'], 2, border_radius=10)
        
        # Back button text
        text = self.font_medium.render(back_btn['text'], True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=back_btn['rect'].center))
        
        # Help button
        if hasattr(self, 'help_icon'):
            screen.blit(self.help_button['icon'], self.help_button['rect'])
        else:
            pygame.draw.rect(screen, self.help_button['color'], self.help_button['rect'], border_radius=5)
            text = self.font_small.render(self.help_button['text'], True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=self.help_button['rect'].center))