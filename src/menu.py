import pygame
import pygame_menu
from pygame_menu import themes
from settings_manager import SettingsManager
from sound_manager import SoundManager

class Menu:
    def __init__(self, screen_width, screen_height, game_instance=None):
        self.width = screen_width
        self.height = screen_height
        self.screen = pygame.display.get_surface()
        self.game = game_instance  # Store reference to game instance
        
        # Initialize settings manager directly
        self.settings_manager = SettingsManager()
        
        # Initialize sound manager for menu sounds
        self.sound_manager = SoundManager()
        
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
        
        # Load settings from file
        self.current_resolution_index = 0
        current_res = (screen_width, screen_height)
        if current_res in self.available_resolutions:
            self.current_resolution_index = self.available_resolutions.index(current_res)
        
        self.volume = self.settings_manager.settings.get("volume", 50)
        self.show_fps = self.settings_manager.settings.get("show_fps", False)
        self.fullscreen = self.settings_manager.settings.get("fullscreen", False)
        
        # Create custom theme
        self.theme = themes.THEME_DARK.copy()
        self.theme.title_font_size = 50
        self.theme.widget_font_size = 30
        self.theme.widget_margin = (0, 10)
        self.theme.background_color = (0, 0, 0, 180)
        
        # Create main menu
        self.main_menu = pygame_menu.Menu(
            "Rubik's Cube Simulator",
            self.width,
            self.height,
            theme=self.theme
        )
        
        # Add main menu buttons
        self.main_menu.add.button("Play", self._start_game)
        self.main_menu.add.button("Settings", self._open_settings)
        self.main_menu.add.button("Quit", pygame_menu.events.EXIT)
        
        # Create settings menu
        self.settings_menu = pygame_menu.Menu(
            "Settings",
            self.width,
            self.height,
            theme=self.theme
        )
        
        # Resolution dropdown
        resolution_options = [f"{w}x{h}" for w, h in self.available_resolutions]
        self.settings_menu.add.dropselect(
            title="Resolution: ",
            items=[(res, i) for i, res in enumerate(resolution_options)],
            default=self.current_resolution_index,
            onchange=self._on_resolution_change
        )
        
        # Replace the display mode selector with a dropdown
        self.settings_menu.add.dropselect(
            title="Display Mode: ",
            items=[("Windowed", False), ("Fullscreen", True)],
            default=int(self.fullscreen),
            onchange=self._on_fullscreen_change
        )
        
        # Show FPS toggle
        self.settings_menu.add.toggle_switch(
            "Show FPS: ",
            default=self.show_fps,
            onchange=self._on_fps_toggle
        )
        
        # Volume slider
        self.settings_menu.add.range_slider(
            "Volume: ",
            default=self.volume,
            range_values=(0, 100),
            increment=5,
            onchange=self._on_volume_change
        )
        
        # Settings menu buttons
        self.settings_menu.add.button("Apply Changes", self._apply_settings)
        self.settings_menu.add.button("Back", self._back_to_main)
        
        # Help menu
        self.help_menu = pygame_menu.Menu(
            "Controls",
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
            self.help_menu.add.label(line)
        
        self.help_menu.add.button("Back", self._back_to_main)
        
        # Add help button to main menu
        self.main_menu.add.button("Help", self._open_help)
        
        # Set current menu
        self.current_menu = self.main_menu
    
    def _start_game(self):
        """Start the game (close menu)"""
        self.sound_manager.play("menu_select")
        self.active = False
    
    def _open_settings(self):
        """Open settings submenu"""
        self.sound_manager.play("menu_select")
        self.current_menu = self.settings_menu
    
    def _open_help(self):
        """Open help submenu"""
        self.sound_manager.play("menu_select")
        self.current_menu = self.help_menu
    
    def _on_resolution_change(self, selected_tuple, index):
        """Handle resolution change from dropdown"""
        # Play selection sound
        self.sound_manager.play("menu_select")
        
        # The dropselect widget passes: (selected_tuple, index)
        # where selected_tuple is (display_text, value)
        
        if hasattr(self, "debug_mode") and self.debug_mode:
            print(f"Resolution change: {selected_tuple}, {index}")
        
        # Extract the index from the tuple (res, i)
        if isinstance(selected_tuple, tuple) and len(selected_tuple) > 1:
            self.current_resolution_index = selected_tuple[1]  # Use the value part of the tuple
        else:
            self.current_resolution_index = index
        
        if hasattr(self, "debug_mode") and self.debug_mode:
            print(f"New resolution index: {self.current_resolution_index}")
        
        self.settings_changed = True
    
    def _on_fullscreen_change(self, selected_tuple, index):
        """Handle fullscreen toggle from dropdown"""
        # Play selection sound
        self.sound_manager.play("menu_select")
        
        # Extract the boolean value from the selected tuple
        if isinstance(selected_tuple, tuple) and len(selected_tuple) > 1:
            self.fullscreen = selected_tuple[1]  # Extract boolean value
        else:
            self.fullscreen = bool(index)  # Convert index to boolean
        
        self.settings_changed = True
    
    def _on_fps_toggle(self, value):
        """Handle FPS toggle"""
        # Play selection sound
        self.sound_manager.play("menu_select")
        
        self.show_fps = value
        self.settings_changed = True
    
    def _on_volume_change(self, value):
        """Handle volume slider change"""
        # Play selection sound
        self.sound_manager.play("menu_select")
        
        self.volume = value
        
        # Apply volume immediately if we can
        if pygame.mixer.get_init() and self.game:
            pygame.mixer.music.set_volume(self.volume / 100)
            
        self.settings_changed = True
    
    def _apply_settings(self):
        """Apply all settings changes"""
        try:
            # Play apply settings sound
            self.sound_manager.play("menu_apply")
            
            if self.settings_changed:
                # Set the resolution changed flag to trigger resolution update in game.py
                self.resolution_changed_flag = True
                
                # Get the resolution that will be applied
                new_width, new_height = self.get_current_resolution()
                if hasattr(self, "debug_mode") and self.debug_mode:
                    print(f"Applying settings - Resolution: {new_width}x{new_height}, Fullscreen: {self.fullscreen}")
                
                # Update settings object directly
                self.settings_manager.settings["resolution"]["width"] = new_width
                self.settings_manager.settings["resolution"]["height"] = new_height
                self.settings_manager.settings["fullscreen"] = self.fullscreen
                self.settings_manager.settings["show_fps"] = self.show_fps
                self.settings_manager.settings["volume"] = self.volume
                self.settings_manager.save_settings()
                
                # Update sound effects volume based on game volume setting
                self.sound_manager.set_volume(self.volume / 100)
                
                self.settings_changed = False
                
            # Return to main menu after applying settings
            self._back_to_main()
            
        except Exception as e:
            print(f"Error applying settings: {e}")
    
    def _back_to_main(self):
        """Return to the main menu"""
        self.sound_manager.play("menu_select")
        self.current_menu = self.main_menu
    
    def toggle(self):
        """Toggle the menu visibility"""
        self.active = not self.active
        
        # Play sound when opening menu
        if self.active:
            self.sound_manager.play("menu_open")
    
    def is_active(self):
        """Check if menu is active"""
        return self.active
    
    def get_current_resolution(self):
        """Get the currently selected resolution"""
        index = min(self.current_resolution_index, len(self.available_resolutions) - 1)
        return self.available_resolutions[index]
    
    def resolution_changed(self):
        """Check if resolution was changed"""
        return self.resolution_changed_flag
    
    def reset_resolution_changed(self):
        """Reset the resolution changed flag"""
        self.resolution_changed_flag = False
    
    def get_setting(self, name):
        """Get a setting value"""
        if name == "show_fps":
            return self.show_fps
        elif name == "fullscreen":
            return self.fullscreen
        elif name == "volume":
            return self.volume
        return None
    
    def handle_event(self, event):
        """Handle events specific to the menu.
        Returns True if the event was handled by the menu."""
        if not self.active or not self.current_menu:
            return False
            
        # Update mouse cursor for menu
        if event.type == pygame.MOUSEMOTION:
            self.update_cursor(event.pos)
        
        # Play sound on certain menu interactions
        if event.type == pygame.KEYDOWN:
            # Play navigation sound for arrow keys, enter, etc.
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN):
                self.sound_manager.play("menu_select")
        
        # Handle menu navigation
        if self.current_menu and self.current_menu.is_enabled():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.current_menu == self.main_menu:
                        self.active = False
                        return True
                    else:
                        self.sound_manager.play("menu_select")
                        self.current_menu = self.main_menu
                        return True
        
        # Handle mouse click sound
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left mouse button
            # Check if we clicked on a menu item
            if self.current_menu:
                # Play selection sound on mouse click
                self.sound_manager.play("menu_select")
        
        # Let pygame-menu handle the event
        updated = self.current_menu.update([event])
        
        # Check if we need to go back to main menu (after pygame-menu processes the event)
        return updated or self.active
    
    def update_cursor(self, mouse_pos):
        """Update cursor based on menu interaction"""
        if not self.active:
            return
        
        if self.current_menu:
            # If mouse is over a widget, use pointer cursor
            if self.current_menu.get_selected_widget():
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            else:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
    
    def draw(self, screen):
        """Draw the menu on the screen"""
        if not self.active:
            return
        
        # Draw semi-transparent background for the full screen
        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # Only check and recreate if there's a significant mismatch
        actual_width, actual_height = screen.get_size()
        if abs(self.width - actual_width) > 10 or abs(self.height - actual_height) > 10:
            # Only print in debug mode
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"Menu dimension mismatch: stored {self.width}x{self.height}, actual {actual_width}x{actual_height}")
            self.width = actual_width
            self.height = actual_height
            self._create_menus()
        
        # Draw the current menu
        if self.current_menu:
            self.current_menu.draw(screen)

    def update_dimensions(self, width, height):
        """Update menu dimensions when resolution changes"""
        # Check if dimensions have actually changed
        if abs(self.width - width) < 5 and abs(self.height - height) < 5:
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"Menu dimensions already match: {width}x{height}, skipping update")
            return
        
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"Updating menu dimensions to: {width}x{height}")
        
        # Update dimensions
        self.width = width
        self.height = height
        
        # Force recreate menus with new dimensions
        self._create_menus()
        
        # Reset the resolution changed flag
        self.resolution_changed_flag = False
    
    def set_game_instance(self, game):
        """Set the game instance reference"""
        self.game = game
    
    def _create_menus(self):
        """Create or recreate menus with current dimensions"""
        # Store current settings before recreating
        current_resolution_index = self.current_resolution_index
        current_volume = self.volume
        current_show_fps = self.show_fps
        current_fullscreen = self.fullscreen
        
        # Get actual screen dimensions
        screen = pygame.display.get_surface()
        if screen:
            actual_width, actual_height = screen.get_size()
            # Update our stored dimensions to match actual screen
            if abs(self.width - actual_width) > 5 or abs(self.height - actual_height) > 5:
                if hasattr(self, 'debug_mode') and self.debug_mode:
                    print(f"Updating menu dimensions from {self.width}x{self.height} to {actual_width}x{actual_height}")
                self.width = actual_width
                self.height = actual_height
        elif hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"No screen surface available, using stored dimensions: {self.width}x{self.height}")
        
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"Creating menus with dimensions: {self.width}x{self.height}")
        
        # Create custom theme
        self.theme = pygame_menu.themes.THEME_DARK.copy()
        self.theme.title_font_size = 50
        self.theme.widget_font_size = 30
        self.theme.widget_margin = (0, 10)
        self.theme.background_color = (0, 0, 0, 180)
        
        # Create main menu with ACTUAL dimensions
        self.main_menu = pygame_menu.Menu(
            "Rubik's Cube Simulator",
            self.width,
            self.height,
            theme=self.theme
        )
        
        # Add main menu buttons
        self.main_menu.add.button("Play", self._start_game)
        self.main_menu.add.button("Settings", self._open_settings)
        self.main_menu.add.button("Help", self._open_help)
        self.main_menu.add.button("Quit", pygame_menu.events.EXIT)
        
        # Create settings menu with ACTUAL dimensions
        self.settings_menu = pygame_menu.Menu(
            "Settings",
            self.width,
            self.height,
            theme=self.theme
        )
        
        # Resolution dropdown
        resolution_options = [f"{w}x{h}" for w, h in self.available_resolutions]
        self.settings_menu.add.dropselect(
            title="Resolution: ",
            items=[(res, i) for i, res in enumerate(resolution_options)],
            default=current_resolution_index,
            onchange=self._on_resolution_change
        )
        
        # Display mode dropdown
        self.settings_menu.add.dropselect(
            title="Display Mode: ",
            items=[("Windowed", False), ("Fullscreen", True)],
            default=int(current_fullscreen),
            onchange=self._on_fullscreen_change
        )
        
        # Show FPS toggle
        self.settings_menu.add.toggle_switch(
            "Show FPS: ",
            default=current_show_fps,
            onchange=self._on_fps_toggle
        )
        
        # Volume slider
        self.settings_menu.add.range_slider(
            "Volume: ",
            default=current_volume,
            range_values=(0, 100),
            increment=5,
            onchange=self._on_volume_change
        )
        
        # Settings menu buttons
        self.settings_menu.add.button("Apply Changes", self._apply_settings)
        self.settings_menu.add.button("Back", self._back_to_main)
        
        # Help menu with ACTUAL dimensions
        self.help_menu = pygame_menu.Menu(
            "Controls",
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
            self.help_menu.add.label(line)
        
        self.help_menu.add.button("Back", self._back_to_main)
        
        # Set current menu (preserve the current menu state)
        if hasattr(self, 'current_menu'):
            if self.current_menu == self.settings_menu:
                self.current_menu = self.settings_menu
            elif self.current_menu == self.help_menu:
                self.current_menu = self.help_menu
            else:
                self.current_menu = self.main_menu
        else:
            self.current_menu = self.main_menu
