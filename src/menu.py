import pygame

class Menu:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.active = False
        self.settings_active = False
        
        # Available resolutions
        self.available_resolutions = [
            (1024, 768),
            (1280, 720),
            (1366, 768),
            (1920, 1080)
        ]
        
        # Find the current resolution index based on actual screen size
        self.current_resolution_index = 0
        current_res = (screen_width, screen_height)
        if current_res in self.available_resolutions:
            self.current_resolution_index = self.available_resolutions.index(current_res)
        else:
            # If current resolution isn't in the list, find the closest match
            closest_match = 0
            min_diff = float('inf')
            for i, res in enumerate(self.available_resolutions):
                # Calculate difference (prioritize matching aspect ratio)
                diff = abs(res[0] - screen_width) + abs(res[1] - screen_height)
                if diff < min_diff:
                    min_diff = diff
                    closest_match = i
            self.current_resolution_index = closest_match
        
        # Dropdown state
        self.dropdown_open = False
        
        # Fonts
        self.font_large = pygame.font.SysFont('Arial', 55, bold=True)
        self.font_medium = pygame.font.SysFont('Arial', 40)
        self.font_small = pygame.font.SysFont('Lexinton', 30)
        self.font_section = pygame.font.SysFont('Arial', 36, bold=True)
        
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
        
        # Calculate positions for settings
        settings_start_y = screen_height // 6 + 70  # Position after the title
        settings_spacing = 35  # Space between settings items
        section_spacing = 60   # Space between sections
        settings_width = 300   # Width of settings controls
        
        # Section titles
        self.display_section = {
            'text': 'Display Settings',
            'rect': pygame.Rect(screen_width//2 - 150, settings_start_y, 300, 40)
        }
        
        # Display settings positions - after section title
        display_y = settings_start_y + 50
        
        # Resolution settings
        self.resolution_label_rect = pygame.Rect(screen_width//2 - 150, display_y, 200, 25)
        
        # Dropdown menu for resolution
        self.dropdown_button = {
            'rect': pygame.Rect(screen_width//2 - 150, display_y + 30, settings_width, 30),
            'color': (50, 50, 50),
            'hover_color': (70, 70, 70),
            'arrow_color': (200, 200, 200)
        }
        
        # Display mode settings
        display_mode_y = display_y + settings_spacing + 40
        self.display_mode_label_rect = pygame.Rect(screen_width//2 - 150, display_mode_y, 200, 25)

        # Dropdown for display mode
        self.display_mode_button = {
            'rect': pygame.Rect(screen_width//2 - 150, display_mode_y + 30, settings_width, 30),
            'color': (50, 50, 50),
            'hover_color': (70, 70, 70),
            'arrow_color': (200, 200, 200)
        }

        # Available display modes
        self.display_modes = ["Windowed", "Fullscreen"]
        self.current_display_mode = 0  # Default to windowed

        # Dropdown state for display mode
        self.display_mode_dropdown_open = False

        # Show FPS option
        fps_y = display_mode_y + settings_spacing + 40
        self.settings_options = {
            'show_fps': {
                'value': False,
                'text': 'Show FPS',
                'rect': pygame.Rect(screen_width//2 - 150, fps_y, 25, 25),
                'label_rect': pygame.Rect(screen_width//2 - 110, fps_y + 5, 200, 25)
            }
        }
        
        # Audio section - starts after display section + spacing
        audio_section_y = fps_y + section_spacing
        self.audio_section = {
            'text': 'Audio Settings',
            'rect': pygame.Rect(screen_width//2 - 150, audio_section_y, 300, 40)
        }
        
        # Volume slider
        volume_y = audio_section_y + 50
        self.volume_label_rect = pygame.Rect(screen_width//2 - 150, volume_y, 200, 25)
        
        # Default volume (50%)
        self.volume = 50
        
        # Volume slider bar
        self.volume_bar = {
            'rect': pygame.Rect(screen_width//2 - 150, volume_y + 30, settings_width, 20),
            'color': (50, 50, 50),
            'fill_color': (50, 150, 50),
            'border_color': (200, 200, 200)
        }
        
        # Volume slider handle
        handle_x = screen_width//2 - 150 + (settings_width * self.volume // 100) - 10
        self.volume_handle = {
            'rect': pygame.Rect(handle_x, volume_y + 25, 20, 30),
            'color': (200, 200, 200),
            'hover_color': (255, 255, 255),
            'dragging': False
        }
        
        # Create dropdown option rectangles
        self.dropdown_options = []
        for i in range(len(self.available_resolutions)):
            self.dropdown_options.append(
                pygame.Rect(
                    screen_width//2 - 150, 
                    display_y + 30 + (i+1)*30, 
                    settings_width, 
                    30
                )
            )
        
        # Create display mode dropdown option rectangles
        self.display_mode_options = []
        for i in range(len(self.display_modes)):
            self.display_mode_options.append(
                pygame.Rect(
                    screen_width//2 - 150, 
                    display_mode_y + 30 + (i+1)*30, 
                    settings_width, 
                    30
                )
            )
        
        # Control buttons at the bottom of the screen
        buttons_y = screen_height - 100
        
        # Back button (Cancel)
        self.back_button = {
            'rect': pygame.Rect(screen_width//2 - 220, buttons_y, 200, 50),
            'text': 'Cancel',
            'color': (150, 50, 50)
        }
        
        # Confirm button
        self.confirm_button = {
            'rect': pygame.Rect(screen_width//2 + 20, buttons_y, 200, 50),
            'text': 'Confirm',
            'color': (50, 150, 50)
        }
        
        # Resolution change flag
        self.resolution_changed_flag = False
        self.settings_changed = False
        
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
        
        # Track cursor state
        self.cursor_default = pygame.SYSTEM_CURSOR_ARROW
        self.cursor_pointer = pygame.SYSTEM_CURSOR_HAND
        self.current_cursor = self.cursor_default
    
    def toggle(self):
        """Toggle menu visibility"""
        self.active = not self.active
        if not self.active:
            self.settings_active = False
            self.dropdown_open = False
        return self.active
    
    def is_active(self):
        """Check if menu is visible"""
        return self.active
    
    def get_current_resolution(self):
        """Return the currently selected resolution"""
        return self.available_resolutions[self.current_resolution_index]
    
    def resolution_changed(self):
        """Check if resolution was changed"""
        return self.resolution_changed_flag
    
    def reset_resolution_changed(self):
        """Reset the resolution changed flag"""
        self.resolution_changed_flag = False
        
    def handle_event(self, event):
        """Process menu input"""
        if not self.active:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Close dropdown if clicking outside
            if self.dropdown_open:
                inside_dropdown = False
                for i, rect in enumerate(self.dropdown_options):
                    if rect.collidepoint(event.pos):
                        # Selected a resolution from dropdown
                        self.current_resolution_index = i
                        self.dropdown_open = False
                        self.settings_changed = True
                        return True
                
                if not self.dropdown_button['rect'].collidepoint(event.pos):
                    # Clicked outside dropdown, close it
                    self.dropdown_open = False
                    return True
            
            # In settings view
            if self.settings_active:
                # Back button (Cancel)
                if self.back_button['rect'].collidepoint(event.pos):
                    self.settings_active = False
                    self.dropdown_open = False
                    # Reset any changes
                    self.settings_changed = False
                    return True
                
                # Confirm button
                if self.confirm_button['rect'].collidepoint(event.pos):
                    self.settings_active = False
                    self.dropdown_open = False
                    if self.settings_changed:
                        self.resolution_changed_flag = True
                        self.settings_changed = False
                    return True
                
                # Resolution dropdown toggle
                if self.dropdown_button['rect'].collidepoint(event.pos):
                    self.dropdown_open = not self.dropdown_open
                    return True
                
                # Handle display mode dropdown
                if self.display_mode_dropdown_open:
                    for i, rect in enumerate(self.display_mode_options):
                        if rect.collidepoint(event.pos):
                            # Selected a display mode
                            old_mode = self.current_display_mode
                            self.current_display_mode = i
                            self.display_mode_dropdown_open = False
                            if old_mode != self.current_display_mode:
                                self.settings_changed = True
                            return True
                    
                    # Close dropdown if clicked outside
                    if not self.display_mode_button['rect'].collidepoint(event.pos):
                        self.display_mode_dropdown_open = False
                        return True
                
                # Toggle display mode dropdown
                if self.display_mode_button['rect'].collidepoint(event.pos):
                    self.display_mode_dropdown_open = not self.display_mode_dropdown_open
                    # Close resolution dropdown if open
                    if self.dropdown_open:
                        self.dropdown_open = False
                    return True
                
                # Check checkbox interactions
                for key, option in self.settings_options.items():
                    if option['rect'].collidepoint(event.pos):
                        # Toggle the checkbox value
                        option['value'] = not option['value']
                        self.settings_changed = True
                        if self.get_setting('debug_mode'):
                            print(f"Setting {key} changed to {option['value']}")
                        return True
                
                # Volume slider handle dragging
                if self.volume_handle['rect'].collidepoint(event.pos):
                    self.volume_handle['dragging'] = True
                    return True
                
                # Volume bar click (jump to position)
                if self.volume_bar['rect'].collidepoint(event.pos):
                    # Calculate new volume position
                    rel_x = event.pos[0] - self.volume_bar['rect'].x
                    self.volume = max(0, min(100, int(rel_x / self.volume_bar['rect'].width * 100)))
                    # Update handle position
                    self._update_volume_handle()
                    self.settings_changed = True
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
        
        # Mouse button up - stop dragging volume handle
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.volume_handle['dragging']:
                self.volume_handle['dragging'] = False
                return True
        
        # Mouse motion - handle volume slider dragging
        elif event.type == pygame.MOUSEMOTION:
            if self.settings_active and self.volume_handle['dragging']:
                # Calculate new volume based on horizontal mouse position
                rel_x = event.pos[0] - self.volume_bar['rect'].x
                self.volume = max(0, min(100, int(rel_x / self.volume_bar['rect'].width * 100)))
                # Update handle position
                self._update_volume_handle()
                self.settings_changed = True
                # Update actual volume
                pygame.mixer.music.set_volume(self.volume / 100)
                return True
            
        return False
    
    def _update_volume_handle(self):
        """Update volume slider handle position based on current volume"""
        handle_x = self.volume_bar['rect'].x + (self.volume_bar['rect'].width * self.volume // 100) - 10
        self.volume_handle['rect'].x = handle_x
    
    def get_setting(self, name):
        """Get a setting value"""
        if name in self.settings_options:
            return self.settings_options[name]['value']
        elif name == 'fullscreen':
            # Return True if Fullscreen is selected (index 1)
            return self.current_display_mode == 1
        elif name == 'volume':
            return self.volume
        return None
    
    def update_cursor(self, mouse_pos):
        """Update cursor based on what it's hovering over"""
        if not self.active:
            if self.current_cursor != self.cursor_default:
                pygame.mouse.set_cursor(self.cursor_default)
                self.current_cursor = self.cursor_default
            return
        
        # Default to arrow cursor
        new_cursor = self.cursor_default
        
        if self.settings_active:
            # Check if hovering over buttons in settings
            hover_elements = [
                self.back_button['rect'],
                self.confirm_button['rect'],
                self.dropdown_button['rect'],
                self.display_mode_button['rect'],
                self.help_button['rect'],
                self.volume_handle['rect']
            ]
            
            # Add checkboxes to hover elements
            for option in self.settings_options.values():
                hover_elements.append(option['rect'])
            
            # Add dropdown options if open
            if self.dropdown_open:
                hover_elements.extend(self.dropdown_options)
            if self.display_mode_dropdown_open:
                hover_elements.extend(self.display_mode_options)
                
            # Check if mouse is over any interactive element
            for element in hover_elements:
                if element.collidepoint(mouse_pos):
                    new_cursor = self.cursor_pointer
                    break
            
            # Also consider the volume bar as a hover element
            if self.volume_bar['rect'].collidepoint(mouse_pos):
                new_cursor = self.cursor_pointer
        else:
            # Check if hovering over buttons in main menu
            if (self.play_button['rect'].collidepoint(mouse_pos) or 
                self.settings_button['rect'].collidepoint(mouse_pos)):
                new_cursor = self.cursor_pointer
        
        # Update cursor if needed
        if new_cursor != self.current_cursor:
            pygame.mouse.set_cursor(new_cursor)
            self.current_cursor = new_cursor
    
    def draw(self, screen):
        """Render the menu"""
        if not self.active:
            return
        
        # Update cursor on each draw
        self.update_cursor(pygame.mouse.get_pos())
            
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
        screen.blit(title, title.get_rect(center=(self.width//2, self.height//6)))
        
        mouse_pos = pygame.mouse.get_pos()
        
        # Display Settings Section Title
        section_title = self.font_section.render(self.display_section['text'], True, (220, 220, 220))
        screen.blit(section_title, self.display_section['rect'])
        # Draw light underline for section
        pygame.draw.line(screen, (150, 150, 150), 
                         (self.display_section['rect'].left, self.display_section['rect'].bottom + 5),
                         (self.display_section['rect'].right, self.display_section['rect'].bottom + 5), 2)
        
        # Resolution label
        resolution_label = self.font_small.render("Resolution:", True, (255, 255, 255))
        screen.blit(resolution_label, self.resolution_label_rect)
        
        # Draw dropdown button
        button_color = self.dropdown_button['hover_color'] if self.dropdown_button['rect'].collidepoint(mouse_pos) else self.dropdown_button['color']
        pygame.draw.rect(screen, button_color, self.dropdown_button['rect'], border_radius=5)
        pygame.draw.rect(screen, (200, 200, 200), self.dropdown_button['rect'], 1, border_radius=5)
        
        # Display current resolution text on dropdown button
        current_res = self.available_resolutions[self.current_resolution_index]
        res_text = self.font_small.render(f"{current_res[0]}x{current_res[1]}", True, (255, 255, 255))
        screen.blit(res_text, (self.dropdown_button['rect'].x + 10, self.dropdown_button['rect'].y + 5))
        
        # Draw dropdown arrow
        arrow_x = self.dropdown_button['rect'].right - 25
        arrow_y = self.dropdown_button['rect'].centery
        arrow_points = [
            (arrow_x - 8, arrow_y - 4),
            (arrow_x, arrow_y + 4),
            (arrow_x + 8, arrow_y - 4)
        ]
        pygame.draw.polygon(screen, self.dropdown_button['arrow_color'], arrow_points)
        
        # Display mode label
        display_mode_label = self.font_small.render("Display Mode:", True, (255, 255, 255))
        screen.blit(display_mode_label, self.display_mode_label_rect)
        
        # Draw display mode dropdown button
        button_color = self.display_mode_button['hover_color'] if self.display_mode_button['rect'].collidepoint(mouse_pos) else self.display_mode_button['color']
        pygame.draw.rect(screen, button_color, self.display_mode_button['rect'], border_radius=5)
        pygame.draw.rect(screen, (200, 200, 200), self.display_mode_button['rect'], 1, border_radius=5)
        
        # Display current mode text on dropdown button
        current_mode = self.display_modes[self.current_display_mode]
        mode_text = self.font_small.render(current_mode, True, (255, 255, 255))
        screen.blit(mode_text, (self.display_mode_button['rect'].x + 10, self.display_mode_button['rect'].y + 5))
        
        # Draw dropdown arrow
        arrow_x = self.display_mode_button['rect'].right - 25
        arrow_y = self.display_mode_button['rect'].centery
        arrow_points = [
            (arrow_x - 8, arrow_y - 4),
            (arrow_x, arrow_y + 4),
            (arrow_x + 8, arrow_y - 4)
        ]
        pygame.draw.polygon(screen, self.display_mode_button['arrow_color'], arrow_points)

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
        
        # Audio Settings Section Title
        section_title = self.font_section.render(self.audio_section['text'], True, (220, 220, 220))
        screen.blit(section_title, self.audio_section['rect'])
        # Draw light underline for section
        pygame.draw.line(screen, (150, 150, 150), 
                         (self.audio_section['rect'].left, self.audio_section['rect'].bottom + 5),
                         (self.audio_section['rect'].right, self.audio_section['rect'].bottom + 5), 2)
        
        # Volume label
        volume_label = self.font_small.render("Volume:", True, (255, 255, 255))
        screen.blit(volume_label, self.volume_label_rect)
        
        # Volume percentage text
        volume_text = self.font_small.render(f"{self.volume}%", True, (255, 255, 255))
        volume_text_rect = volume_text.get_rect()
        volume_text_rect.right = self.volume_bar['rect'].right
        volume_text_rect.y = self.volume_label_rect.y
        screen.blit(volume_text, volume_text_rect)
        
        # Draw volume bar background
        pygame.draw.rect(screen, self.volume_bar['color'], self.volume_bar['rect'], border_radius=5)
        
        # Draw filled portion of volume bar
        filled_width = int(self.volume_bar['rect'].width * self.volume / 100)
        filled_rect = pygame.Rect(
            self.volume_bar['rect'].x,
            self.volume_bar['rect'].y,
            filled_width,
            self.volume_bar['rect'].height
        )
        pygame.draw.rect(screen, self.volume_bar['fill_color'], filled_rect, border_radius=5)
        
        # Draw volume bar border
        pygame.draw.rect(screen, self.volume_bar['border_color'], self.volume_bar['rect'], 1, border_radius=5)
        
        # Draw volume handle with hover effect
        handle_color = self.volume_handle['hover_color'] if self.volume_handle['rect'].collidepoint(mouse_pos) or self.volume_handle['dragging'] else self.volume_handle['color']
        pygame.draw.rect(screen, handle_color, self.volume_handle['rect'], border_radius=4)
        pygame.draw.rect(screen, (100, 100, 100), self.volume_handle['rect'], 1, border_radius=4)

        # Back (Cancel) button
        back_btn = self.back_button
        pygame.draw.rect(screen, back_btn['color'], back_btn['rect'], border_radius=10)
        pygame.draw.rect(screen, (255, 255, 255), back_btn['rect'], 2, border_radius=10)
        
        # Back button text
        text = self.font_medium.render(back_btn['text'], True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=back_btn['rect'].center))
        
        # Confirm button
        confirm_btn = self.confirm_button
        pygame.draw.rect(screen, confirm_btn['color'], confirm_btn['rect'], border_radius=10)
        pygame.draw.rect(screen, (255, 255, 255), confirm_btn['rect'], 2, border_radius=10)
        
        # Confirm button text
        text = self.font_medium.render(confirm_btn['text'], True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=confirm_btn['rect'].center))
        
        # Help button
        if hasattr(self, 'help_icon'):
            screen.blit(self.help_button['icon'], self.help_button['rect'])
        else:
            pygame.draw.rect(screen, self.help_button['color'], self.help_button['rect'], border_radius=5)
            text = self.font_small.render(self.help_button['text'], True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=self.help_button['rect'].center))
        
        # Draw dropdown options if open - DRAW THESE LAST to ensure they appear on top
        if self.dropdown_open:            
            for i, rect in enumerate(self.dropdown_options):
                # Check if mouse is hovering over this option
                is_hovering = rect.collidepoint(mouse_pos)
                option_color = (70, 70, 70) if is_hovering else (40, 40, 40)
                
                pygame.draw.rect(screen, option_color, rect)
                pygame.draw.rect(screen, (100, 100, 100), rect, 1)
                
                # Resolution text
                res = self.available_resolutions[i]
                option_text = self.font_small.render(f"{res[0]}x{res[1]}", True, (255, 255, 255))
                screen.blit(option_text, (rect.x + 10, rect.y + 5))
        
        # Draw display mode dropdown options if open - DRAW THESE LAST too
        if self.display_mode_dropdown_open:           
            for i, rect in enumerate(self.display_mode_options):
                # Check if mouse is hovering over this option
                is_hovering = rect.collidepoint(mouse_pos)
                option_color = (70, 70, 70) if is_hovering else (40, 40, 40)
                
                pygame.draw.rect(screen, option_color, rect)
                pygame.draw.rect(screen, (100, 100, 100), rect, 1)
                
                # Mode text
                mode = self.display_modes[i]
                option_text = self.font_small.render(mode, True, (255, 255, 255))
                screen.blit(option_text, (rect.x + 10, rect.y + 5))
    
    def change_resolution(self, width, height):
        # Update the actual screen
        self.width = width
        self.height = height
    
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((width, height))
            
        # Update menu dimensions
        self.menu = Menu(width, height)
        
        # Make sure menu's current resolution index is correct
        current_res = (width, height)
        if current_res in self.menu.available_resolutions:
            self.menu.current_resolution_index = self.menu.available_resolutions.index(current_res)
    
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        current_res = (self.width, self.height)
        
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode(current_res, pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(current_res)