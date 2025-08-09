import pygame
import pygame_menu
from pygame_menu import themes
from pygame_menu.locals import *  # Import all constants including alignment
import os
import time
import math
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
        
        # Load audio settings from settings manager
        self.sound_manager.load_volumes_from_settings(self.settings_manager)
        
        # Menu state
        self.active = False
        self.resolution_changed_flag = False
        self.settings_changed = False
        self.selected_difficulty = "freeplay"  # Default difficulty - start in free play mode
        
        # Animation state for smooth transitions
        self.is_animating = False
        self.animation_start_time = 0
        self.animation_duration = 0.3  # 300ms transition
        self.is_opening = False  # True when opening, False when closing
        self.target_alpha = 1.0  # Target alpha value (0.0 to 1.0)
        self.current_alpha = 0.0  # Current alpha value for animation
        
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
        
        self.volume = int(self.settings_manager.settings.get("volume", 50))  # Ensure volume is integer
        self.show_fps = self.settings_manager.settings.get("show_fps", False)
        self.fullscreen = self.settings_manager.settings.get("fullscreen", False)
        
        # Load audio settings
        self.master_volume = self.settings_manager.get_master_volume()
        self.music_volume = self.settings_manager.get_music_volume()
        self.effects_volume = self.settings_manager.get_effects_volume()
        self.menu_volume = self.settings_manager.get_menu_volume()
        
        # Initialize hover tracking
        self.hovered_widgets = set()  # Track which widgets are currently hovered
        
        # Initialize difficulty button animation tracking
        self.difficulty_buttons = {}  # Store difficulty buttons with their metadata
        self.button_animations = {}  # Track animation state for each button
        
        # Create custom fancy theme with improved styling
        self._create_custom_theme()
        
        # Create menus
        self._create_menus()
        
        # Set current menu to main menu
        self.current_menu = self.main_menu
    
    def _create_custom_theme(self):
        """Create a fancy custom theme with better styling"""
        # Start with the blue theme as base
        self.theme = pygame_menu.themes.THEME_BLUE.copy()
        
        # Background styling
        self.theme.background_color = (10, 15, 25, 220)  # Dark blue with transparency
        
        # Title styling
        self.theme.title_font = pygame_menu.font.FONT_FRANCHISE
        self.theme.title_font_size = 65
        self.theme.title_font_color = (255, 255, 255)
        self.theme.title_font_shadow = True
        self.theme.title_font_shadow_color = (0, 0, 0)
        self.theme.title_font_shadow_offset = 3
        self.theme.title_background_color = (10, 15, 25, 0)  # Transparent background
        self.theme.title_bar_style = pygame_menu.widgets.MENUBAR_STYLE_NONE
        # Try different title properties to center it
        self.theme.title_alignment = ALIGN_CENTER
        self.theme.title_position = (50, 50)  # Try positioning the title
        self.theme.title_offset = (0, 0)
        
        # Widget styling
        self.theme.widget_font = pygame_menu.font.FONT_FRANCHISE
        self.theme.widget_font_size = 50
        self.theme.widget_font_color = (255, 255, 255)  # White text
        self.theme.widget_font_shadow = True
        self.theme.widget_font_shadow_color = (0, 0, 0)
        self.theme.widget_font_shadow_offset = 2
        self.theme.widget_margin = (0, 15)
        self.theme.widget_padding = (15, 10)
        
        # Button styling - use NoneSelection for now and handle custom effects manually
        self.theme.widget_selection_effect = pygame_menu.widgets.NoneSelection()
        
        # Button background colors - make them transparent/invisible
        self.theme.widget_background_color = (0, 0, 0, 0)  # Completely transparent
        self.theme.widget_background_color_disabled = (0, 0, 0, 0)  # Completely transparent
        
        # Scrollbar styling (for controls menu)
        self.theme.scrollbar_color = (50, 70, 100)
        self.theme.scrollbar_slider_color = (100, 130, 180)
        self.theme.scrollbar_slider_hover_color = (120, 150, 200)
        
        # Border styling - remove borders
        self.theme.widget_border_color = (0, 0, 0, 0)  # Transparent border
        self.theme.widget_border_width = 0  # No border
        
        # Menu bar styling
        self.theme.menubar_close_button = False
        
        # Custom colors for specific widgets - transparent backgrounds
        self.button_color_normal = (0, 0, 0, 0)  # Transparent
        self.button_color_hover = (30, 50, 80, 100)  # Subtle hover effect
        self.button_color_pressed = (0, 0, 0, 0)  # Transparent
        
        # Text colors
        self.text_color_normal = (255, 255, 255)  # White color for normal text
        self.text_color_hover = (240, 198, 38)   # Hover color
        self.text_color_selected = (255, 18, 18)  # Red color for selected
    
    def _customize_button_appearance(self, button):
        """Apply custom styling to a button widget - remove backgrounds"""
        try:
            # Only set background color to transparent - this is the most important change
            if hasattr(button, 'set_background_color'):
                button.set_background_color((0, 0, 0, 0))
            
        except Exception as e:
            # Silently ignore errors to avoid spam
            pass
    
    def _customize_menu_widgets(self, menu):
        """Apply custom styling to all widgets in a menu - remove backgrounds"""
        try:
            for widget in menu.get_widgets():
                # Get widget type by checking the class name
                widget_class_name = widget.__class__.__name__
                
                if widget_class_name == 'Button':
                    # Check if this is a difficulty button (has background color set)
                    if (hasattr(widget, '_background_color') and 
                        widget._background_color and 
                        widget._background_color != (0, 0, 0, 0)):
                        # This is a difficulty button with custom background, keep it
                        pass
                    else:
                        # This is a regular button, make it transparent
                        self._customize_button_appearance(widget)
                elif widget_class_name in ['DropSelect', 'ToggleSwitch', 'RangeSlider']:
                    # Remove background squares from other interactive widgets
                    if hasattr(widget, 'set_background_color'):
                        widget.set_background_color((0, 0, 0, 0))  # Transparent
                        
        except Exception as e:
            # Silently ignore errors to avoid spam
            pass
    
    def _get_game_modes(self):
        """Get available game modes with their configurations.
        This structure makes it easy to add new difficulties and game modes."""
        return {
            "freeplay": {
                "name": "Free Play",
                "description": "Practice with an unscrambled cube",
                "scramble_moves": 0,  # No scrambling - cube stays solved
                "timer_enabled": False,  # No timer for free play
            },
            "easy": {
                "name": "Easy",
                "description": "Perfect for beginners - 5 moves scramble",
                "scramble_moves": 5,  # Easy scramble
                "timer_enabled": True,  # Future: enable/disable timer
            },
            "medium": {
                "name": "Medium", 
                "description": "Standard difficulty - 10 moves scramble",
                "scramble_moves": 10,
                "timer_enabled": True,
            },
            "hard": {
                "name": "Hard",
                "description": "Complete random scramble",
                "scramble_moves": -1,  # Special value for total random scramble
                "timer_enabled": True,
            }
        }
    
    def get_game_mode_config(self, difficulty):
        """Get the configuration for a specific game mode"""
        game_modes = self._get_game_modes()
        return game_modes.get(difficulty, game_modes["medium"])
    
    def _start_game(self, difficulty="normal"):
        """Start the game (close menu) with specified difficulty"""
        self.sound_manager.play("menu_select")
        # Clear hover effects before starting game
        self._clear_all_hover_effects()
        
        # Store the selected difficulty for future use
        self.selected_difficulty = difficulty
        
        # Change skybox based on difficulty
        if hasattr(self, "game") and self.game:
            skybox_path = self.settings_manager.get_skybox_by_difficulty(difficulty)
            self.game.renderer.reload_skybox_texture(skybox_path)
            if hasattr(self, "debug_mode") and self.debug_mode:
                print(f"Changed skybox to: {skybox_path}")
            
            # Request a new game to be started (this will trigger scrambling)
            self.game.request_new_game()
        
        if hasattr(self, "debug_mode") and self.debug_mode:
            print(f"Starting game with difficulty: {difficulty}")
        
        # Start closing animation instead of immediately setting active to False
        if not self.is_animating:  # Prevent multiple animations
            self.toggle()
    
    def _open_difficulty_select(self):
        """Open difficulty selection submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self.current_menu = self.difficulty_menu
    
    def _open_settings(self):
        """Open settings submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self.current_menu = self.settings_menu
    
    def _open_controls(self):
        """Open controls submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self.current_menu = self.controls_menu
    
    def _open_audio_settings(self):
        """Open audio settings submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self.current_menu = self.audio_settings_menu
    
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
        # Play selection sound with slider-specific debouncing
        self.sound_manager.play_slider_sound("menu_select")
        
        self.volume = int(value)  # Ensure volume is stored as integer
        
        # Update the slider title to show the current volume value
        if hasattr(self, 'volume_slider'):
            self.volume_slider.set_title(f"Volume: {self.volume}%")
        
        # Apply volume immediately if we can
        if pygame.mixer.get_init() and self.game:
            pygame.mixer.music.set_volume(self.volume / 100)
        
        # Save to settings immediately
        self.settings_manager.settings["volume"] = self.volume
        self.settings_manager.save_settings()
        
        # Also update the game's settings manager if available
        if hasattr(self, "game") and self.game and hasattr(self.game, "settings"):
            self.game.settings.settings["volume"] = self.volume
            
        self.settings_changed = True
    
    def _on_master_volume_change(self, value):
        """Handle master volume slider change"""
        self.sound_manager.play_slider_sound("menu_select")
        self.master_volume = int(value)
        
        # Update the slider title
        if hasattr(self, 'master_volume_slider'):
            self.master_volume_slider.set_title(f"Master Volume: {self.master_volume}%")
        
        # Apply volume immediately
        self.sound_manager.set_master_volume(self.master_volume / 100.0)
        
        # Save to settings immediately
        self.settings_manager.set_audio_volume("master_volume", self.master_volume)
        self.settings_manager.save_settings()
        
        # Also update the game's settings manager if available
        if hasattr(self, "game") and self.game and hasattr(self.game, "settings"):
            self.game.settings.set_audio_volume("master_volume", self.master_volume)
        
        self.settings_changed = True
    
    def _on_music_volume_change(self, value):
        """Handle music volume slider change"""
        self.sound_manager.play_slider_sound("menu_select")
        self.music_volume = int(value)
        
        # Update the slider title
        if hasattr(self, 'music_volume_slider'):
            self.music_volume_slider.set_title(f"Music Volume: {self.music_volume}%")
        
        # Apply volume immediately
        self.sound_manager.set_music_volume(self.music_volume / 100.0)
        
        # Save to settings immediately
        self.settings_manager.set_audio_volume("music_volume", self.music_volume)
        self.settings_manager.save_settings()
        
        # Also update the game's settings manager if available
        if hasattr(self, "game") and self.game and hasattr(self.game, "settings"):
            self.game.settings.set_audio_volume("music_volume", self.music_volume)
        
        self.settings_changed = True
    
    def _on_effects_volume_change(self, value):
        """Handle effects volume slider change"""
        self.sound_manager.play_slider_sound("menu_select")
        self.effects_volume = int(value)
        
        # Update the slider title
        if hasattr(self, 'effects_volume_slider'):
            self.effects_volume_slider.set_title(f"Effects Volume: {self.effects_volume}%")
        
        # Apply volume immediately
        self.sound_manager.set_effects_volume(self.effects_volume / 100.0)
        
        # Save to settings immediately
        self.settings_manager.set_audio_volume("effects_volume", self.effects_volume)
        self.settings_manager.save_settings()
        
        # Also update the game's settings manager if available
        if hasattr(self, "game") and self.game and hasattr(self.game, "settings"):
            self.game.settings.set_audio_volume("effects_volume", self.effects_volume)
        
        self.settings_changed = True
    
    def _on_menu_volume_change(self, value):
        """Handle menu volume slider change"""
        self.sound_manager.play_slider_sound("menu_select")
        self.menu_volume = int(value)
        
        # Update the slider title
        if hasattr(self, 'menu_volume_slider'):
            self.menu_volume_slider.set_title(f"Menu Volume: {self.menu_volume}%")
        
        # Apply volume immediately
        self.sound_manager.set_menu_volume(self.menu_volume / 100.0)
        
        # Save to settings immediately
        self.settings_manager.set_audio_volume("menu_volume", self.menu_volume)
        self.settings_manager.save_settings()
        
        # Also update the game's settings manager if available
        if hasattr(self, "game") and self.game and hasattr(self.game, "settings"):
            self.game.settings.set_audio_volume("menu_volume", self.menu_volume)
        
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
                
                # Update audio settings
                self.settings_manager.set_audio_volume("master_volume", self.master_volume)
                self.settings_manager.set_audio_volume("music_volume", self.music_volume)
                self.settings_manager.set_audio_volume("effects_volume", self.effects_volume)
                self.settings_manager.set_audio_volume("menu_volume", self.menu_volume)
                
                self.settings_manager.save_settings()
                
                # Update sound effects volume based on new audio settings
                self.sound_manager.load_volumes_from_settings(self.settings_manager)
                
                self.settings_changed = False
                
            # Return to main menu after applying settings
            self._back_to_main()
            
        except Exception as e:
            print(f"Error applying settings: {e}")
    
    def _back_to_main(self):
        """Return to the main menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self.current_menu = self.main_menu
    
    def _back_to_settings(self):
        """Return to the settings menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self.current_menu = self.settings_menu
    
    def update(self):
        """Update animation state and alpha values"""
        # Always update button animations regardless of menu animation state
        self._update_button_animations()
        
        if not self.is_animating:
            return
            
        current_time = time.time()
        elapsed_time = current_time - self.animation_start_time
        
        # Calculate animation progress (0.0 to 1.0)
        progress = min(elapsed_time / self.animation_duration, 1.0)
        
        # Use smooth easing function for better animation feel
        # Ease-out quadratic function: t * (2 - t)
        eased_progress = progress * (2 - progress)
        
        if self.is_opening:
            # Opening animation: alpha goes from 0 to 1
            self.current_alpha = eased_progress
        else:
            # Closing animation: alpha goes from 1 to 0
            self.current_alpha = 1.0 - eased_progress
        
        # Check if animation is complete
        if progress >= 1.0:
            self.is_animating = False
            self.current_alpha = self.target_alpha
            
            # If we just finished closing, deactivate the menu
            if not self.is_opening:
                self.active = False
    
    def get_current_alpha(self):
        """Get the current alpha value for rendering"""
        if not self.is_animating and not self.active:
            return 0.0
        return self.current_alpha if self.is_animating else 1.0
    
    def is_fully_visible(self):
        """Check if menu is fully visible (not animating or fully open)"""
        return self.active and (not self.is_animating or self.current_alpha >= 1.0)

    def toggle(self):
        """Toggle the menu visibility with smooth animation"""
        # Start animation
        self.is_animating = True
        self.animation_start_time = time.time()
        
        if self.active:
            # Menu is currently active, start closing animation
            self.is_opening = False
            self.target_alpha = 0.0
            # Clear hover effects when starting to close
            self._clear_all_hover_effects()
        else:
            # Menu is currently inactive, start opening animation
            self.is_opening = True
            self.target_alpha = 1.0
            self.active = True  # Set active immediately for opening so events are handled
            # Play sound when opening menu
            self.sound_manager.play("menu_open")
            # Always reset to main menu when opening from in-game
            self.current_menu = self.main_menu
    
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
        elif name == "difficulty":
            return self.selected_difficulty
        return None
    
    def get_selected_difficulty(self):
        """Get the currently selected difficulty"""
        return self.selected_difficulty
    
    def handle_event(self, event):
        """Handle events specific to the menu with enhanced feedback.
        Returns True if the event was handled by the menu."""
        # Only handle events if menu is active and not in closing animation
        if not self.active or (self.is_animating and not self.is_opening):
            return False
            
        # Enhanced mouse motion handling for hover effects
        if event.type == pygame.MOUSEMOTION:
            self.update_cursor(event.pos)
            self._update_hover_effects(event.pos)
        
        # Clear hover effects on mouse button clicks to prevent sticky hover
        if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP]:
            self._clear_all_hover_effects()
        
        # Handle menu navigation
        if self.current_menu and self.current_menu.is_enabled():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.current_menu == self.main_menu:
                        # Start closing animation instead of immediately setting active to False
                        if not self.is_animating:  # Prevent multiple toggle calls during animation
                            self.toggle()
                        return True
                    elif self.current_menu == self.audio_settings_menu:
                        self.sound_manager.play("menu_select")
                        self._clear_all_hover_effects()  # Clear hover effects when changing menu
                        self.current_menu = self.settings_menu
                        return True
                    else:
                        self.sound_manager.play("menu_select")
                        self._clear_all_hover_effects()  # Clear hover effects when changing menu
                        self.current_menu = self.main_menu
                        return True
        
        # Let pygame-menu handle the event
        updated = self.current_menu.update([event])
        
        # Check if we need to go back to main menu (after pygame-menu processes the event)
        return updated or self.active
    
    def _clear_all_hover_effects(self):
        """Clear hover effects from all widgets"""
        for widget in self.hovered_widgets.copy():
            self._apply_hover_effect(widget, False)
        self.hovered_widgets.clear()
    
    def _update_hover_effects(self, mouse_pos):
        """Update hover effects for widgets based on mouse position"""
        if not self.current_menu:
            return
            
        widgets = self.current_menu.get_widgets()
        currently_hovered = set()
        
        for widget in widgets:
            try:
                widget_rect = widget.get_rect()
                widget_class_name = widget.__class__.__name__
                
                # Check if this widget should have hover effects
                if widget_class_name in ['Button', 'DropSelect', 'ToggleSwitch']:
                    if widget_rect.collidepoint(mouse_pos):
                        currently_hovered.add(widget)
                        
                        # If this is a new hover, apply hover effect
                        if widget not in self.hovered_widgets:
                            self._apply_hover_effect(widget, True)
                            
                            # Play subtle hover sound (with debouncing)
                            if hasattr(self, 'sound_manager'):
                                self.sound_manager.play_slider_sound("menu_select")
                    
                    elif widget in self.hovered_widgets:
                        # Mouse left this widget, remove hover effect
                        self._apply_hover_effect(widget, False)
                        
            except:
                # If widget doesn't support get_rect(), skip it
                continue
        
        # Update the tracked hovered widgets
        self.hovered_widgets = currently_hovered
    
    def _apply_hover_effect(self, widget, is_hovered):
        """Apply or remove hover effect from a widget"""
        try:
            widget_class_name = widget.__class__.__name__
            
            if widget_class_name == 'Button':
                # Check if this is a difficulty button
                if widget in self.difficulty_buttons:
                    self._animate_difficulty_button(widget, is_hovered)
                else:
                    # Regular button hover effect (text color change)
                    if hasattr(widget, '_font_color'):
                        if is_hovered:
                            widget._font_color = self.text_color_hover
                        else:
                            widget._font_color = self.text_color_normal
                            
                    # Also try to update the button's style if possible
                    if hasattr(widget, 'update_font'):
                        widget.update_font({
                            'color': self.text_color_hover if is_hovered else self.text_color_normal
                        })
                    
        except Exception as e:
            # Silently handle any errors
            pass
    
    def _animate_difficulty_button(self, button, is_hovered):
        """Apply animated hover effect to difficulty buttons"""
        if button not in self.button_animations:
            return
            
        animation_state = self.button_animations[button]
        current_time = time.time()
        
        if is_hovered:
            if not animation_state['is_hovering']:
                # Start hover animation
                animation_state['is_hovering'] = True
                animation_state['animation_start_time'] = current_time
        else:
            if animation_state['is_hovering']:
                # Start unhover animation
                animation_state['is_hovering'] = False
                animation_state['animation_start_time'] = current_time
    
    def _update_button_animations(self):
        """Update all button animations"""
        current_time = time.time()
        animation_duration = 0.2  # 200ms animation
        
        for button, animation_state in self.button_animations.items():
            if button not in self.difficulty_buttons:
                continue
                
            # Calculate animation progress
            elapsed_time = current_time - animation_state['animation_start_time']
            progress = min(1.0, elapsed_time / animation_duration)
            
            # Smooth easing function (ease out)
            eased_progress = 1 - (1 - progress) ** 3
            
            # Update glow intensity only
            if animation_state['is_hovering']:
                animation_state['glow_intensity'] = eased_progress * 0.3  # Max glow intensity
            else:
                animation_state['glow_intensity'] = (1 - eased_progress) * 0.3
            
            # Apply visual effects to the button
            self._apply_button_visual_effects(button, animation_state)
    
    def _apply_button_visual_effects(self, button, animation_state):
        """Apply visual effects to a difficulty button based on animation state"""
        try:
            if button not in self.difficulty_buttons:
                return
                
            button_info = self.difficulty_buttons[button]
            base_color = button_info['base_color']
            
            # Calculate enhanced color with glow effect
            glow_intensity = animation_state['glow_intensity']
            enhanced_color = (
                min(255, int(base_color[0] + glow_intensity * 60)),  # Add red glow
                min(255, int(base_color[1] + glow_intensity * 60)),  # Add green glow  
                min(255, int(base_color[2] + glow_intensity * 60)),  # Add blue glow
                min(255, int(base_color[3] + glow_intensity * 50))   # Add alpha glow
            )
            
            # Apply the enhanced color to the button
            if hasattr(button, 'set_background_color'):
                button.set_background_color(enhanced_color)
            
            # Also change text color for extra effect
            if hasattr(button, '_font_color'):
                if animation_state['is_hovering']:
                    button._font_color = self.text_color_hover
                else:
                    button._font_color = self.text_color_normal
                    
        except Exception as e:
            # Silently handle any errors
            pass
    
    def update_cursor(self, mouse_pos):
        """Update cursor based on menu interaction with enhanced feedback"""
        if not self.active:
            return
        
        if self.current_menu:
            # Check if mouse is over any interactive widget
            selected_widget = self.current_menu.get_selected_widget()
            
            # Get the widget under mouse position
            widgets = self.current_menu.get_widgets()
            mouse_over_widget = False
            
            for widget in widgets:
                try:
                    widget_rect = widget.get_rect()
                    if widget_rect.collidepoint(mouse_pos):
                        mouse_over_widget = True
                        # Check if it's an interactive widget by class name
                        widget_class_name = widget.__class__.__name__
                        if widget_class_name in ['Button', 'DropSelect', 'ToggleSwitch', 'RangeSlider']:
                            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                            return
                except:
                    # If widget doesn't support get_rect(), skip it
                    continue
            
            # If not over any interactive widget, use arrow cursor
            if not mouse_over_widget:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
    
    def draw(self, screen):
        """Draw the menu on the screen with fancy effects and alpha animation"""
        # Don't draw if completely invisible
        current_alpha = self.get_current_alpha()
        if current_alpha <= 0.0:
            return
        
        # Draw smooth background overlay with alpha
        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        
        # Create a smooth, clean background
        base_alpha = 160  # Fixed alpha for consistent background
        # Apply current animation alpha
        final_alpha = int(base_alpha * current_alpha)
        color = (5, 10, 20, final_alpha)
        overlay.fill(color)
        
        screen.blit(overlay, (0, 0))
        
        # Add subtle particle effects or glow with alpha
        self._draw_background_effects(screen, current_alpha)
        
        # Only check and recreate if there's a significant mismatch
        actual_width, actual_height = screen.get_size()
        if abs(self.width - actual_width) > 10 or abs(self.height - actual_height) > 10:
            # Only print in debug mode
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"Menu dimension mismatch: stored {self.width}x{self.height}, actual {actual_width}x{actual_height}")
            self.width = actual_width
            self.height = actual_height
            self._create_menus()
        
        # Draw the current menu with alpha applied
        if self.current_menu:
            # Create a temporary surface for the menu
            menu_surface = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
            
            # Draw the menu to the temporary surface
            self.current_menu.draw(menu_surface)
            
            # Apply alpha to the entire menu surface
            if current_alpha < 1.0:
                alpha_surface = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
                alpha_surface.fill((255, 255, 255, int(255 * current_alpha)))
                menu_surface.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            # Blit the menu surface to the screen
            screen.blit(menu_surface, (0, 0))
    
    def _draw_background_effects(self, screen, alpha=1.0):
        """Draw subtle background effects like glowing particles with alpha"""
        try:
            # Create a subtle glow effect around the menu area
            center_x = screen.get_width() // 2
            center_y = screen.get_height() // 2
            time_offset = time.time()
            
            # Draw some floating particles
            for i in range(8):
                angle = (time_offset * 30 + i * 45) % 360
                radius = 150 + 50 * math.sin(time_offset * 2 + i)
                
                x = center_x + radius * math.cos(math.radians(angle))
                y = center_y + radius * math.sin(math.radians(angle))
                
                # Ensure particles stay on screen
                if 0 <= x <= screen.get_width() and 0 <= y <= screen.get_height():
                    size = int(3 + 2 * math.sin(time_offset * 3 + i))
                    base_alpha = int(180 + 75 * math.sin(time_offset * 2 + i * 0.5))
                    # Apply current animation alpha
                    final_alpha = int(base_alpha * alpha)
                    
                    # Create a small glowing circle
                    glow_surface = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
                    pygame.draw.circle(glow_surface, (100, 150, 255, final_alpha), (size * 2, size * 2), size * 2)
                    pygame.draw.circle(glow_surface, (150, 200, 255, int(final_alpha * 0.7)), (size * 2, size * 2), size)
                    
                    screen.blit(glow_surface, (x - size * 2, y - size * 2))
        except Exception as e:
            # Silently ignore errors in visual effects
            pass

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
        # Clear existing difficulty button tracking when recreating menus
        self.difficulty_buttons.clear()
        self.button_animations.clear()
        
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
        
        # Create custom fancy theme for main menu (centered title)
        self._create_custom_theme()
        
        # Create theme for other menus (left-aligned titles)
        self.sub_theme = self.theme.copy()
        self.sub_theme.title_alignment = ALIGN_LEFT
        
        # Create main menu with ACTUAL dimensions and no title (we'll add custom centered title)
        self.main_menu = pygame_menu.Menu(
            "",  # Empty title - we'll add a custom centered one
            self.width,
            self.height,
            theme=self.theme,
            columns=1,
            rows=None
        )
        
        # Add custom centered title as a label
        self.main_menu.add.label(
            "Rubik's Cube Simulator",
            font_size=65,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            font_color=(255, 255, 255),
            font_shadow=True,
            font_shadow_color=(0, 0, 0),
            font_shadow_offset=3,
            align=ALIGN_CENTER
        )
        
        # Add some spacing after the title
        self.main_menu.add.vertical_margin(30)
        
        # Try to center the title after menu creation
        try:
            # Method 1: Set title alignment directly on menu
            if hasattr(self.main_menu, 'set_title_alignment'):
                self.main_menu.set_title_alignment(ALIGN_CENTER)
            elif hasattr(self.main_menu, '_theme'):
                self.main_menu._theme.title_alignment = ALIGN_CENTER
            # Method 2: Try setting column alignment
            if hasattr(self.main_menu, 'set_alignment'):
                self.main_menu.set_alignment(ALIGN_CENTER)
        except:
            pass
        
        # Add main menu buttons
        play_btn = self.main_menu.add.button("Play", self._open_difficulty_select)
        settings_btn = self.main_menu.add.button("Settings", self._open_settings)
        controls_btn = self.main_menu.add.button("Controls", self._open_controls)
        quit_btn = self.main_menu.add.button("Quit", pygame_menu.events.EXIT)
        
        # Apply custom styling to main menu
        self._customize_menu_widgets(self.main_menu)
        
        # Create difficulty selection menu with ACTUAL dimensions
        self.difficulty_menu = pygame_menu.Menu(
            "Select Difficulty",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Dynamically add difficulty options from game modes configuration
        game_modes = self._get_game_modes()
        difficulty_icons = {"easy", "medium", "hard"}
        
        # Define background colors for each difficulty
        difficulty_colors = {
            "freeplay": (22, 57, 161, 200),  # Blue (original color)
            "easy": (33, 148, 33, 200),      # Green
            "medium": (199, 106, 26, 200),   # Orange
            "hard": (176, 28, 28, 200)      # Red
        }
        
        for mode_key, mode_config in game_modes.items():
            # Add some spacing before each difficulty
            self.difficulty_menu.add.vertical_margin(20)
            
            # Combine name and description in one button with proper spacing
            button_text = f"{mode_config['name']} | {mode_config['description']}"
            button_action = lambda difficulty=mode_key: self._start_game(difficulty)
            
            # Get the appropriate background color for this difficulty
            bg_color = difficulty_colors.get(mode_key, (40, 60, 90, 200))
            
            difficulty_button = self.difficulty_menu.add.button(
                button_text, 
                button_action,
                font_size=40,
                font_name=pygame_menu.font.FONT_FRANCHISE,
                background_color=bg_color,  # Difficulty-specific colored background box
                padding=(30, 25)  # More padding for a taller box
            )
            
            # Store difficulty button for animation tracking
            self.difficulty_buttons[difficulty_button] = {
                'difficulty': mode_key,
                'original_color': bg_color,
                'base_color': bg_color
            }
            
            # Initialize animation state for this button
            self.button_animations[difficulty_button] = {
                'is_hovering': False,
                'animation_start_time': 0,
                'glow_intensity': 0.0
            }
            
            # Add spacing after each difficulty
            self.difficulty_menu.add.vertical_margin(10)
        
        # Add final spacing and back button
        self.difficulty_menu.add.vertical_margin(20)
        back_btn = self.difficulty_menu.add.button("Back", self._back_to_main)
        
        # Apply custom styling to difficulty menu
        self._customize_menu_widgets(self.difficulty_menu)
        
        # Create settings menu with ACTUAL dimensions
        self.settings_menu = pygame_menu.Menu(
            "Settings",
            self.width,
            self.height,
            theme=self.sub_theme
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
        
        # Audio Settings button
        audio_settings_btn = self.settings_menu.add.button("Audio Settings", self._open_audio_settings)
        
        # Settings menu buttons
        apply_btn = self.settings_menu.add.button("Apply Changes", self._apply_settings)
        back_btn = self.settings_menu.add.button("Back", self._back_to_main)

        # Apply custom styling to settings menu
        self._customize_menu_widgets(self.settings_menu)
        
        # Create audio settings menu with ACTUAL dimensions
        self.audio_settings_menu = pygame_menu.Menu(
            "Audio Settings",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Master Volume slider
        self.master_volume_slider = self.audio_settings_menu.add.range_slider(
            f"Master Volume: {self.master_volume}%",
            default=self.master_volume,
            range_values=(0, 100),
            increment=5,
            value_format=lambda x: "",
            rangeslider_id="master_volume_slider",
            slider_text_value_enabled=False,
            onchange=self._on_master_volume_change
        )
        
        # Music Volume slider
        self.music_volume_slider = self.audio_settings_menu.add.range_slider(
            f"Music Volume: {self.music_volume}%",
            default=self.music_volume,
            range_values=(0, 100),
            increment=5,
            value_format=lambda x: "",
            rangeslider_id="music_volume_slider",
            slider_text_value_enabled=False,
            onchange=self._on_music_volume_change
        )
        
        # Effects Volume slider
        self.effects_volume_slider = self.audio_settings_menu.add.range_slider(
            f"Effects Volume: {self.effects_volume}%",
            default=self.effects_volume,
            range_values=(0, 100),
            increment=5,
            value_format=lambda x: "",
            rangeslider_id="effects_volume_slider",
            slider_text_value_enabled=False,
            onchange=self._on_effects_volume_change
        )
        
        # Menu Volume slider
        self.menu_volume_slider = self.audio_settings_menu.add.range_slider(
            f"Menu Volume: {self.menu_volume}%",
            default=self.menu_volume,
            range_values=(0, 100),
            increment=5,
            value_format=lambda x: "",
            rangeslider_id="menu_volume_slider",
            slider_text_value_enabled=False,
            onchange=self._on_menu_volume_change
        )
        
        # Audio settings menu buttons
        audio_back_btn = self.audio_settings_menu.add.button("Back", self._back_to_settings)
        
        # Apply custom styling to audio settings menu
        self._customize_menu_widgets(self.audio_settings_menu)
        
        # Controls menu with ACTUAL dimensions
        self.controls_menu = pygame_menu.Menu(
            "Controls",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Add controls text with better formatting to match the interface
        controls_sections = [
            ("BASIC CONTROLS", [
                ("Toggle menu", "[ESC]"),
                ("Manual rotation", "[Arrow Keys]"),
                ("Toggle auto-rotation", "[Space]"),
                ("Scramble cube", "[X]"),
                ("Undo last move", "[Z]"),
                ("Reset rotation", "[T]"),
                ("Toggle fullscreen", "[F11]"),
                ("Toggle debug mode", "[Ctrl+B]")

            ]),
            ("MOUSE CONTROLS", [
                ("Rotate camera view", "[Left Click + Drag]"),
                ("Perform cube moves", "[Right click + Drag]"),
                ("Disable auto-rotation", "[Space / Left Click / Right Click]")
            ]),
            ("CUBE MOVES", [
                ("R Move / R' Move", "[R / Shift+R]"),
                ("L Move / L' Move", "[L / Shift+L]"),
                ("U Move / U' Move", "[U / Shift+U]"),
                ("D Move / D' Move", "[D / Shift+D]"),
                ("F Move / F' Move", "[F / Shift+F]"),
                ("B Move / B' Move", "[B / Shift+B]")
            ]),
            ("SLICE MOVES", [
                ("M Move / M' Move", "[M / Shift+M]"),
                ("E Move / E' Move", "[E / Shift+E]"),
                ("S Move / S' Move", "[S / Shift+S]")
            ])
        ]
        
        for section_title, controls in controls_sections:
            # Add section header
            self.controls_menu.add.label(section_title, font_size=50, font_color=(235, 38, 38), font_name=pygame_menu.font.FONT_FRANCHISE)
            self.controls_menu.add.vertical_margin(10)
            
            # Add controls with right-aligned key bindings
            for control_desc, key_binding in controls:
                # Create a formatted string with proper spacing
                formatted_control = f"{control_desc:<30} {key_binding:>15}"
                self.controls_menu.add.label(formatted_control, font_size=30, font_color=(255, 255, 255), font_name=pygame_menu.font.FONT_FRANCHISE)
            
            self.controls_menu.add.vertical_margin(20)
        
        back_btn = self.controls_menu.add.button("Back", self._back_to_main)
        
        # Apply custom styling to controls menu
        self._customize_menu_widgets(self.controls_menu)
        
        # Set current menu (preserve the current menu state)
        if hasattr(self, 'current_menu'):
            if self.current_menu == self.settings_menu:
                self.current_menu = self.settings_menu
            elif self.current_menu == self.audio_settings_menu:
                self.current_menu = self.audio_settings_menu
            elif self.current_menu == self.controls_menu:
                self.current_menu = self.controls_menu
            elif self.current_menu == self.difficulty_menu:
                self.current_menu = self.difficulty_menu
            else:
                self.current_menu = self.main_menu
        else:
            self.current_menu = self.main_menu
