import pygame
import pygame_menu
from pygame_menu import themes

class Menu:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.screen = pygame.display.get_surface()
        
        # Menu state
        self.active = False
        self.resolution_changed_flag = False
        self.settings_changed = False
        
        # Available resolutions
        self.available_resolutions = [
            (1024, 768),
            (1280, 720),
            (1366, 768),
            (1920, 1080)
        ]
        
        # Current settings
        self.current_resolution_index = 0
        current_res = (screen_width, screen_height)
        if current_res in self.available_resolutions:
            self.current_resolution_index = self.available_resolutions.index(current_res)
        
        self.volume = 50
        self.show_fps = False
        self.fullscreen = False
        
        # Create custom theme
        self.theme = themes.THEME_DARK.copy()
        self.theme.title_font_size = 50
        self.theme.widget_font_size = 30
        self.theme.widget_margin = (0, 10)
        self.theme.background_color = (0, 0, 0, 180)
        
        # Create main menu
        self.main_menu = pygame_menu.Menu(
            'Rubik\'s Cube Simulator',
            self.width,
            self.height,
            theme=self.theme
        )
        
        # Add main menu buttons
        self.main_menu.add.button('Play', self._start_game)
        self.main_menu.add.button('Settings', self._open_settings)
        self.main_menu.add.button('Quit', pygame_menu.events.EXIT)
        
        # Create settings menu
        self.settings_menu = pygame_menu.Menu(
            'Settings',
            self.width,
            self.height,
            theme=self.theme
        )
        
        # Resolution dropdown
        resolution_options = [f"{w}x{h}" for w, h in self.available_resolutions]
        self.settings_menu.add.dropselect(
            title='Resolution: ',
            items=[(res, i) for i, res in enumerate(resolution_options)],
            default=self.current_resolution_index,
            onchange=self._on_resolution_change
        )
        
        # Display mode selector
        self.settings_menu.add.selector(
            'Display Mode: ',
            [('Windowed', False), ('Fullscreen', True)],
            default=0,
            onchange=self._on_fullscreen_change
        )
        
        # Show FPS toggle
        self.settings_menu.add.toggle_switch(
            'Show FPS: ',
            default=self.show_fps,
            onchange=self._on_fps_toggle
        )
        
        # Volume slider
        self.settings_menu.add.range_slider(
            'Volume: ',
            default=self.volume,
            range_values=(0, 100),
            increment=5,
            onchange=self._on_volume_change
        )
        
        # Settings menu buttons
        self.settings_menu.add.button('Apply Changes', self._apply_settings)
        self.settings_menu.add.button('Back', self._back_to_main)
        
        # Help menu
        self.help_menu = pygame_menu.Menu(
            'Controls',
            self.width,
            self.height,
            theme=self.theme
        )
        
        # Add help text
        help_text = [
            "Controls:",
            "",
            "Space: Toggle auto-rotation",
            "Left/Right arrows: Manual rotation",
            "Up/Down arrows: Vertical rotation",
            "Click and drag: Rotate with mouse",
            "D: Toggle debug mode",
            "ESC: Toggle menu",
            "F11: Toggle fullscreen",
            "",
            "Mouse rotation disables auto-rotation"
        ]
        
        for line in help_text:
            if line:
                self.help_menu.add.label(line, font_size=24)
            else:
                self.help_menu.add.vertical_margin(10)
        
        self.help_menu.add.button('Back', self._back_to_main)
        
        # Add help button to main menu
        self.main_menu.add.button('Help', self._open_help)
        
        # Set current menu
        self.current_menu = self.main_menu
    
    def _start_game(self):
        """Start the game (close menu)"""
        self.active = False
    
    def _open_settings(self):
        """Open settings submenu"""
        self.current_menu = self.settings_menu
    
    def _open_help(self):
        """Open help submenu"""
        self.current_menu = self.help_menu
    
    def _on_resolution_change(self, selected_tuple, index):
        """Handle resolution change from dropdown"""
        # The dropselect widget passes: (selected_tuple, index)
        # where selected_tuple is (display_text, value)
        
        print(f"Resolution change - selected: {selected_tuple}, index: {index}")
        
        # Extract the index from the tuple (res, i)
        if isinstance(selected_tuple, tuple) and len(selected_tuple) > 1:
            self.current_resolution_index = selected_tuple[1]  # Get the index value we stored in the tuple
        else:
            # Fallback to using the provided index
            self.current_resolution_index = index
        
        print(f"Set resolution index to: {self.current_resolution_index}")
        self.settings_changed = True
    
    def _on_fullscreen_change(self, *args, **kwargs):
        """Handle fullscreen toggle"""
        # pygame-menu passes: (selected_value, selected_index)
        if len(args) >= 2:
            selected_value, selected_index = args[0], args[1]
            # Get the actual boolean value from our options
            fullscreen_options = [('Windowed', False), ('Fullscreen', True)]
            if selected_index < len(fullscreen_options):
                self.fullscreen = fullscreen_options[selected_index][1]
        elif len(args) >= 1:
            # Fallback
            selected_value = args[0]
            if isinstance(selected_value, tuple):
                self.fullscreen = selected_value[1]
            else:
                self.fullscreen = bool(selected_value)
        self.settings_changed = True
    
    def _on_fps_toggle(self, *args, **kwargs):
        """Handle FPS toggle"""
        if len(args) >= 1:
            self.show_fps = bool(args[0])
        self.settings_changed = True
    
    def _on_volume_change(self, *args, **kwargs):
        """Handle volume change"""
        if len(args) >= 1:
            self.volume = int(args[0])
            # Apply volume change immediately
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(self.volume / 100)
        self.settings_changed = True
    
    def _apply_settings(self):
        """Apply all settings changes"""
        try:
            if self.settings_changed:
                # Set the resolution changed flag to trigger resolution update in game.py
                self.resolution_changed_flag = True
                
                # Get the resolution that will be applied
                new_width, new_height = self.get_current_resolution()
                print(f"Applying settings - Resolution: {new_width}x{new_height}, Fullscreen: {self.fullscreen}")
                
                # Reset settings changed flag
                self.settings_changed = False
            
            # Return to main menu
            self.current_menu = self.main_menu
        except Exception as e:
            print(f"Error applying settings: {str(e)}")
            # Reset settings flags to prevent repeated crashes
            self.settings_changed = False
            self.resolution_changed_flag = False
            # Still return to main menu even if there's an error
            self.current_menu = self.main_menu
    
    def _back_to_main(self):
        """Go back to main menu"""
        self.current_menu = self.main_menu
    
    def toggle(self):
        """Toggle menu visibility"""
        self.active = not self.active
        if self.active:
            self.current_menu = self.main_menu
        return self.active
    
    def is_active(self):
        """Check if menu is visible"""
        return self.active
    
    def get_current_resolution(self):
        """Return the currently selected resolution as (width, height)"""
        return self.available_resolutions[self.current_resolution_index]
    
    def resolution_changed(self):
        """Check if resolution was changed"""
        return self.resolution_changed_flag
    
    def reset_resolution_changed(self):
        """Reset the resolution changed flag"""
        self.resolution_changed_flag = False
    
    def get_setting(self, name):
        """Get a setting value"""
        if name == 'show_fps':
            return self.show_fps
        elif name == 'fullscreen':
            return self.fullscreen
        elif name == 'volume':
            return self.volume
        return None
    
    def handle_event(self, event):
        """Process menu input"""
        if not self.active or event is None:
            return False
        
        # Handle menu navigation
        if self.current_menu and self.current_menu.is_enabled():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.current_menu == self.main_menu:
                        self.active = False
                        return True
                    else:
                        self.current_menu = self.main_menu
                        return True
        
        # Let pygame-menu handle the event
        updated = self.current_menu.update([event])
        
        # Check if we need to go back to main menu (after pygame-menu processes the event)
        if self.current_menu != self.main_menu:
            if updated == pygame_menu.events.BACK:
                self.current_menu = self.main_menu
                return True
        
        return True
    
    def update_cursor(self, mouse_pos):
        """Update cursor (pygame-menu handles this automatically)"""
        pass
    
    def draw(self, screen):
        """Render the menu"""
        if not self.active:
            return
        
        # Draw semi-transparent background
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # Draw the current menu
        if self.current_menu:
            self.current_menu.draw(screen)
    
    def update_dimensions(self, width, height):
        """Update menu dimensions when resolution changes"""
        self.width = width
        self.height = height
        
        # Update menu dimensions instead of recreating the whole menu
        if self.main_menu:
            self.main_menu.resize(width, height)
        
        if self.settings_menu:
            self.settings_menu.resize(width, height)
            
        if self.help_menu:
            self.help_menu.resize(width, height)
        
        # Update the theme if needed
        self.theme.background_color = (0, 0, 0, 180)
        
        # If current_menu is not set, reset to main menu
        if not hasattr(self, 'current_menu') or self.current_menu is None:
            self.current_menu = self.main_menu