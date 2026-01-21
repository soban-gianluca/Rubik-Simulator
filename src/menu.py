import pygame
import pygame_menu
from pygame_menu import themes
from pygame_menu.locals import *
import os
import time
import math
import threading
from io import BytesIO
from src.settings_manager import SettingsManager
from src.sound_manager import SoundManager
from src.personal_best_manager import PersonalBestManager
from src.user_manager import UserManager, REGIONS
from src.achievements_manager import AchievementsManager, ACHIEVEMENTS
from utils.path_helper import resource_path

# Leaderboard filter options
GAME_MODE_OPTIONS = ["All Modes", "easy", "medium", "hard", "limited_time", "limited_moves"]
GAME_MODE_DISPLAY = {
    "All Modes": "All Modes",
    "easy": "Easy",
    "medium": "Medium", 
    "hard": "Hard",
    "limited_time": "Limited Time",
    "limited_moves": "Limited Moves"
}
REGION_OPTIONS = ["All Regions"] + REGIONS

class Menu:
    def __init__(self, screen_width, screen_height, game_instance=None):
        self.width = screen_width
        self.height = screen_height
        self.screen = pygame.display.get_surface()
        self.game = game_instance  # Store reference to game instance
        
        # Initialize settings manager directly
        self.settings_manager = SettingsManager()
        
        # Initialize personal best manager
        self.personal_best_manager = PersonalBestManager()
        
        # Initialize user manager
        self.user_manager = UserManager()
        
        # Initialize achievements manager
        self.achievements_manager = AchievementsManager()
        
        # Initialize Supabase manager (will be set by game instance)
        self.supabase_manager = None
        
        # Initialize sound manager for menu sounds
        self.sound_manager = SoundManager()
        
        # Load audio settings from settings manager
        self.sound_manager.load_volumes_from_settings(self.settings_manager)
        
        # Menu state
        self.active = False
        self.resolution_changed_flag = False
        self.settings_changed = False
        self.selected_difficulty = "freeplay"  # Default difficulty - start in free play mode
        self.has_difficulty_changed = False  # Track if difficulty has been changed at least once
        self.difficulty_ever_selected = False  # Track if any difficulty has ever been selected
        
        # User setup state
        self.user_setup_active = False  # Track if user setup dialog is shown
        self.user_setup_username = ""  # Temporary storage for username input
        self.user_setup_region_index = 0  # Temporary storage for region selection
        self.username_error = None  # Error message for username validation
        
        # Statistics tab state
        self.statistics_tab = "personal_records"  # "personal_records", "global_leaderboard", or "daily_leaderboard"
        
        # Leaderboard state
        self.leaderboard_data = []  # Cached leaderboard data
        self.leaderboard_loading = False  # Flag for async loading
        self.leaderboard_error = None  # Error message if fetch failed
        self.leaderboard_is_offline = False  # Flag for offline/network error state
        self.leaderboard_filter_mode = "All Modes"  # Current game mode filter
        self.leaderboard_filter_region = "All Regions"  # Current region filter
        self.leaderboard_last_fetch = 0  # Timestamp of last fetch
        self.leaderboard_ui_refresh_pending = False  # Flag to prevent concurrent UI refreshes
        
        # Daily leaderboard state
        self.daily_leaderboard_data = []  # Cached daily leaderboard data
        self.daily_leaderboard_loading = False  # Flag for async loading
        self.daily_leaderboard_error = None  # Error message if fetch failed
        self.daily_leaderboard_is_offline = False  # Flag for offline/network error state
        self.daily_leaderboard_filter_region = "All Regions"  # Current region filter for daily
        self.daily_leaderboard_last_fetch = 0  # Timestamp of last fetch
        self.daily_leaderboard_ui_refresh_pending = False  # Flag to prevent concurrent UI refreshes
        
        # Limited time mode settings
        self.selected_time_limit = 180  # Default 3 minutes in seconds
        self.time_limit_options = [60, 120, 180, 240, 300, 360, 420, 480, 540, 600, 660, 720, 780, 840, 900]  # 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 minutes

        # Limited moves mode settings
        self.selected_move_limit = 25  # Default 25 moves
        self.move_limit_options = list(range(15, 51))  # 15 to 50 moves

        # Initialize game modes configuration as instance variable
        self.game_modes = self._initialize_game_modes()
        
        # Animation state for smooth transitions
        self.is_animating = False
        self.animation_start_time = 0
        self.animation_duration = 0.3  # 300ms transition
        self.is_opening = False  # True when opening, False when closing
        self.target_alpha = 1.0  # Target alpha value (0.0 to 1.0)
        self.current_alpha = 0.0  # Current alpha value for animation
        
        # Blur effect properties
        self.background_capture = None
        self.blurred_background = None
        self.game_rendered = False  # Track if game has rendered at least once
        self.frames_rendered = 0  # Count frames to ensure proper initialization
        
        # Main menu background image for when difficulty change index is 0
        self.main_menu_background = None
        self._load_main_menu_background()
        
        # Load the logo image for the main menu title
        self.logo_image = None
        self._load_logo_image()
        
        # Load the record icon for the personal best button
        self.record_icon = None
        self._load_record_icon()
        
        # Load the edit icon for user edit button
        self.edit_icon = None
        self._load_edit_icon()
        
        # Load the achievements icon
        self.achievements_icon = None
        self._load_achievements_icon()
        
        # Available resolutions
        self.available_resolutions = [
            (1280, 720),
            (1366, 768),
            (1920, 1080)
        ]
        
        # Load settings from file
        self.current_resolution_index = 0
        current_res = (screen_width, screen_height)
        if current_res in self.available_resolutions:
            self.current_resolution_index = self.available_resolutions.index(current_res)
        
        self.volume = int(self.settings_manager.settings.get("volume", 50))
        self.show_fps = self.settings_manager.settings.get("show_fps", False)
        self.fullscreen = self.settings_manager.settings.get("fullscreen", False)
        
        # Load audio settings
        self.master_volume = self.settings_manager.get_master_volume()
        self.music_volume = self.settings_manager.get_music_volume()
        self.effects_volume = self.settings_manager.get_effects_volume()
        self.menu_volume = self.settings_manager.get_menu_volume()
        
        # Load hints setting
        self.hints_enabled = self.settings_manager.get_hints_enabled()
        
        # Initialize hover tracking
        self.hovered_widgets = set()  # Track which widgets are currently hovered
        
        # Statistics button hover state (renamed from personal_best)
        self.personal_best_button_hovered = False
        self.personal_best_rect = None  # Will be set when drawing the button
        
        # User edit button hover state
        self.user_edit_button_hovered = False
        self.user_edit_rect = None  # Will be set when drawing the button
        
        # Achievements button hover state
        self.achievements_button_hovered = False
        self.achievements_rect = None  # Will be set when drawing the button
        
        # Initialize difficulty button animation tracking
        self.difficulty_buttons = {}  # Store difficulty buttons with their metadata
        self.button_animations = {}  # Track animation state for each button
        
        # Tooltip system for difficulty buttons
        self.tooltip_active = False
        self.tooltip_text = ""
        self.tooltip_start_time = 0
        self.tooltip_delay = 0.5  # 500ms delay before showing tooltip
        self.tooltip_font = None
        self.tooltip_surface = None
        self.tooltip_rect = None
        self.current_tooltip_button = None
        
        # Keyboard navigation state
        self.keyboard_navigation_enabled = False  # Enable on first arrow key press
        self.focused_button_index = -1  # Currently focused button index (-1 = none)
        self.navigable_widgets = []  # List of widgets that can be navigated

        # Prevent double-calling pygame-menu update() in the same frame
        # (event handler already calls update([event]) for interactive input).
        self._skip_pygame_menu_update_once = False

        # Patch pygame-menu scrollbar rendering once so the thumb never drifts off
        # the track (prevents "invisible thumb" and avoids hover flicker).
        self._patch_pygame_menu_scrollbar_render()
        
        # Create custom fancy theme with improved styling
        self._create_custom_theme()
        
        # Create menus
        self._create_menus()
        
        # Set current menu to main menu
        self.current_menu = self.main_menu

    @staticmethod
    def _patch_pygame_menu_scrollbar_render() -> None:
        """Monkeypatch pygame-menu ScrollBar._render to clamp thumb cross-axis.

        The root issue was the thumb rect cross-axis drifting (e.g., x for vertical)
        which makes the thumb render outside the track. Fixing it inside _render()
        ensures every internal render is correct and avoids visible flicker from
        external forced re-renders.
        """
        try:
            from pygame_menu.widgets.widget.scrollbar import ScrollBar
        except Exception:
            return

        if getattr(ScrollBar, '_rubik_sim_render_patched', False):
            return

        original_render = getattr(ScrollBar, '_render', None)
        if original_render is None:
            return

        def _render_patched(self):  # type: ignore[no-redef]
            try:
                r = getattr(self, '_slider_rect', None)
                if r is not None:
                    pad = int(getattr(self, '_slider_pad', 0) or 0)
                    if getattr(self, '_orientation', None) == 1:
                        r.x = pad
                    else:
                        r.y = pad
            except Exception:
                pass
            return original_render(self)

        ScrollBar._render = _render_patched  # type: ignore[assignment]
        ScrollBar._rubik_sim_render_patched = True
    
    def _create_custom_theme(self):
        """Create a fancy custom theme with better styling"""
        # Start with the blue theme as base
        self.theme = pygame_menu.themes.THEME_BLUE.copy()
        
        # Background styling
        self.theme.background_color = (10, 15, 25, 220)  # Dark blue with transparency
        
        # Title styling
        self.theme.title_font = pygame_menu.font.FONT_FRANCHISE
        title_font_size = max(38, min(70, int(self.height * 0.085)))
        self.theme.title_font_size = title_font_size
        self.theme.title_font_color = (255, 255, 255)
        self.theme.title_font_shadow = True
        self.theme.title_font_shadow_color = (0, 0, 0)
        self.theme.title_font_shadow_offset = 3
        self.theme.title_background_color = (5, 10, 20, 240)  # More opaque dark background for better visibility
        self.theme.title_bar_style = pygame_menu.widgets.MENUBAR_STYLE_ADAPTIVE
        # Try different title properties to center it
        self.theme.title_alignment = ALIGN_CENTER
        self.theme.title_position = (50, 50)  # Try positioning the title
        self.theme.title_offset = (0, 0)
        
        # Widget styling
        self.theme.widget_font = pygame_menu.font.FONT_FRANCHISE
        widget_font_size = max(28, min(54, int(self.height * 0.065)))
        self.theme.widget_font_size = widget_font_size
        self.theme.widget_font_color = (255, 255, 255)  # White text
        self.theme.widget_font_shadow = True
        self.theme.widget_font_shadow_color = (0, 0, 0)
        self.theme.widget_font_shadow_offset = 2
        self.theme.widget_margin = (0, max(3, int(self.height * 0.007)))
        self.theme.widget_padding = (max(10, int(self.width * 0.008)), max(6, int(self.height * 0.01)))
        
        # Button styling - use NoneSelection for now and handle custom effects manually
        self.theme.widget_selection_effect = pygame_menu.widgets.NoneSelection()
        
        # Button background colors - make them transparent/invisible
        self.theme.widget_background_color = (0, 0, 0, 0)  # Completely transparent
        self.theme.widget_background_color_disabled = (0, 0, 0, 0)  # Completely transparent
        
        # Scrollbar styling
        self.theme.scrollbar_color = (15, 22, 35)              # Track
        self.theme.scrollbar_slider_color = (240, 198, 38)     # Thumb
        self.theme.scrollbar_slider_hover_color = (255, 255, 255)
        self.theme.scrollbar_slider_pad = 1  # pygame-menu expects int padding
        self.theme.scrollbar_thick = 14
        self.theme.scrollbar_shadow = True  # Add shadow for better visibility
        self.theme.scrollbar_shadow_color = (0, 0, 0)
        self.theme.scrollbar_shadow_offset = 1
        
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
    
    def _load_main_menu_background(self):
        """Load the main menu background image"""
        try:
            # Load the main menu background image
            background_path = resource_path("utils/main_menu_background.png")
            if os.path.exists(background_path):
                self.main_menu_background = pygame.image.load(background_path)
            else:
                print(f"Main menu background not found: {background_path}")
                self.main_menu_background = None
        except Exception as e:
            print(f"Error loading main menu background: {e}")
            self.main_menu_background = None
    
    def _load_logo_image(self):
        """Load the Rubik's Cube logo image"""
        try:
            # Load the logo image
            logo_path = resource_path("utils/rubiks_logo.png")
            if os.path.exists(logo_path):
                self.logo_image = pygame.image.load(logo_path)
                logo_width = int(self.width * 0.08)  # 8% of screen width
                logo_height = int(logo_width * 0.24)  # 24% of logo width (preserve aspect ratio)
                self.logo_image = pygame.transform.scale(self.logo_image, (logo_width, logo_height))
            else:
                print(f"Logo image not found: {logo_path}")
                self.logo_image = None
        except Exception as e:
            print(f"Error loading logo image: {e}")
            self.logo_image = None
    
    def _load_record_icon(self):
        """Load the record icon for the personal best button"""
        try:
            # Load the record icon
            record_icon_path = resource_path("utils/icons/statistics.png")
            if os.path.exists(record_icon_path):
                self._record_icon_original = pygame.image.load(record_icon_path).convert_alpha()
                self._scale_record_icon()
            else:
                print(f"Record icon not found: {record_icon_path}")
                self.record_icon = None
        except Exception as e:
            print(f"Error loading record icon: {e}")
            self.record_icon = None
    
    def _load_edit_icon(self):
        """Load the edit icon for the user edit button"""
        try:
            # Load the edit icon
            edit_icon_path = resource_path("utils/icons/user-edit.png")
            if os.path.exists(edit_icon_path):
                self._edit_icon_original = pygame.image.load(edit_icon_path).convert_alpha()
                self._scale_edit_icon()
            else:
                print(f"Edit icon not found: {edit_icon_path}")
                self.edit_icon = None
        except Exception as e:
            print(f"Error loading edit icon: {e}")
            self.edit_icon = None
    
    def _load_achievements_icon(self):
        """Load the achievements icon for the achievements button"""
        try:
            # Load the achievements icon
            achievements_icon_path = resource_path("utils/icons/achievements.png")
            if os.path.exists(achievements_icon_path):
                self._achievements_icon_original = pygame.image.load(achievements_icon_path).convert_alpha()
                self._scale_achievements_icon()
            else:
                print(f"Achievements icon not found: {achievements_icon_path}")
                self.achievements_icon = None
        except Exception as e:
            print(f"Error loading achievements icon: {e}")
            self.achievements_icon = None

    def _get_stats_button_metrics(self, screen_width=None, screen_height=None):
        """Calculate sizes for the Statistics button based on screen size"""
        if screen_width is None:
            screen_width = self.width
        if screen_height is None:
            screen_height = self.height

        button_height = max(52, min(84, int(screen_height * 0.07)))
        button_width = max(170, min(280, int(screen_width * 0.12)))
        margin = max(14, int(screen_width * 0.018))
        icon_size = max(26, min(48, int(button_height * 0.6)))
        icon_padding = max(10, int(button_height * 0.22))
        font_size = max(20, int(button_height * 0.46))
        hover_font_size = max(font_size + 2, int(button_height * 0.5))

        return {
            "button_width": button_width,
            "button_height": button_height,
            "margin": margin,
            "icon_size": icon_size,
            "icon_padding": icon_padding,
            "font_size": font_size,
            "hover_font_size": hover_font_size
        }

    def _scale_record_icon(self):
        """Scale the record icon based on current resolution"""
        if not hasattr(self, "_record_icon_original") or self._record_icon_original is None:
            self.record_icon = None
            return

        icon_size = self._get_stats_button_metrics()["icon_size"]
        self.record_icon = pygame.transform.smoothscale(self._record_icon_original, (icon_size, icon_size))

    def _scale_edit_icon(self):
        """Scale the edit icon based on current resolution"""
        if not hasattr(self, "_edit_icon_original") or self._edit_icon_original is None:
            self.edit_icon = None
            return

        # Edit icon proportional to edit button size
        edit_icon_size = max(28, min(40, int(self.height * 0.045)))
        self.edit_icon = pygame.transform.smoothscale(self._edit_icon_original, (edit_icon_size, edit_icon_size))
    
    def _scale_achievements_icon(self):
        """Scale the achievements icon based on current resolution"""
        if not hasattr(self, "_achievements_icon_original") or self._achievements_icon_original is None:
            self.achievements_icon = None
            return

        # Achievements icon proportional to button size (same as stats button)
        icon_size = self._get_stats_button_metrics()["icon_size"]
        self.achievements_icon = pygame.transform.smoothscale(self._achievements_icon_original, (icon_size, icon_size))
    
    def _customize_button_appearance(self, button):
        """Apply custom styling to a button widget - remove backgrounds"""
        try:
            # Only set background color to transparent
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
                    # Get button title to check if it's a special button
                    button_title = ""
                    if hasattr(widget, 'get_title'):
                        button_title = widget.get_title()
                    
                    # Check if this is a settings button that should keep its color
                    if button_title in ["Apply Changes", "Back"]:
                        # Skip styling for these buttons - they will be styled separately
                        pass
                    # Also skip if this is the stored apply button reference
                    elif hasattr(self, 'apply_button') and widget == self.apply_button:
                        # Skip styling for apply button - handled separately
                        pass
                    # Check if this is a difficulty button (has background color set)
                    elif (hasattr(widget, '_background_color') and 
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
    
    def _style_settings_buttons(self, apply_btn, back_btn):
        """Apply specific colors and rounded backgrounds to the settings buttons, directly drawing rounded buttons."""
        import pygame
        def draw_rounded_button(widget, surface, *args, **kwargs):
            rect = widget.get_rect(to_real_position=True)
            color = widget._background_color if hasattr(widget, '_background_color') else (80, 80, 80, 150)
            border_radius = 16
            pygame.draw.rect(surface, color, rect, border_radius=border_radius)
            pygame.draw.rect(surface, (120, 120, 120, 180), rect, width=2, border_radius=border_radius)
            if hasattr(widget, 'get_title') and hasattr(widget, '_font'):
                text = widget.get_title()
                font = widget._font
                font_color = widget._font_color if hasattr(widget, '_font_color') else (255, 255, 255)
                text_surf = font.render(text, True, font_color)
                text_rect = text_surf.get_rect(center=rect.center)
                surface.blit(text_surf, text_rect)
        try:
            if hasattr(apply_btn, 'set_background_color'):
                if self.settings_changed:
                    apply_btn.set_background_color((46, 125, 50, 200))  # Green color
                    if hasattr(apply_btn, 'is_enabled'):
                        apply_btn.is_enabled = True
                    if hasattr(apply_btn, '_font_color'):
                        apply_btn._font_color = (255, 255, 255)
                else:
                    apply_btn.set_background_color((80, 80, 80, 150))  # Light gray color
                    if hasattr(apply_btn, 'is_enabled'):
                        apply_btn.is_enabled = False
                    if hasattr(apply_btn, '_font_color'):
                        apply_btn._font_color = (150, 150, 150)
                apply_btn._original_draw = apply_btn.draw
                apply_btn.draw = lambda surface, *a, **k: draw_rounded_button(apply_btn, surface, *a, **k)
            if hasattr(back_btn, 'set_background_color'):
                back_btn.set_background_color((66, 66, 66, 200))
                back_btn._original_draw = back_btn.draw
                back_btn.draw = lambda surface, *a, **k: draw_rounded_button(back_btn, surface, *a, **k)
        except Exception:
            pass

    def _style_difficulty_buttons(self):
        """Apply rounded backgrounds and custom colors to difficulty selection buttons."""
        import pygame
        for button, info in self.difficulty_buttons.items():
            def draw_rounded_difficulty(widget, surface, *args, **kwargs):
                rect = widget.get_rect(to_real_position=True)
                color = widget._background_color if hasattr(widget, '_background_color') else info['base_color']
                border_radius = 18
                pygame.draw.rect(surface, color, rect, border_radius=border_radius)
                pygame.draw.rect(surface, (120, 120, 120, 180), rect, width=2, border_radius=border_radius)
                if hasattr(widget, 'get_title') and hasattr(widget, '_font'):
                    text = widget.get_title()
                    font = widget._font
                    font_color = widget._font_color if hasattr(widget, '_font_color') else (255, 255, 255)
                    text_surf = font.render(text, True, font_color)
                    text_rect = text_surf.get_rect(center=rect.center)
                    surface.blit(text_surf, text_rect)
            button._original_draw = button.draw
            button.draw = lambda surface, *a, btn=button, **k: draw_rounded_difficulty(btn, surface, *a, **k)
    
    def _update_apply_button_state(self):
        """Update the apply button's appearance based on settings_changed state"""
        if hasattr(self, 'apply_button') and self.apply_button:
            try:
                if hasattr(self.apply_button, 'set_background_color'):
                    if self.settings_changed:
                        # Enabled state - green background
                        self.apply_button.set_background_color((46, 125, 50, 200))  # Green color
                        # Set normal text color
                        if hasattr(self.apply_button, '_font_color'):
                            self.apply_button._font_color = (255, 255, 255)  # White text
                    else:
                        # Disabled state - lighter/grayed out background
                        self.apply_button.set_background_color((80, 80, 80, 150))  # Light gray color
                        # Set gray text color
                        if hasattr(self.apply_button, '_font_color'):
                            self.apply_button._font_color = (150, 150, 150)  # Gray text
            except Exception as e:
                # Silently ignore errors
                pass
    
    def _initialize_game_modes(self):
        """Initialize available game modes with their configurations.
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
                "description": "Completely random scramble",
                "scramble_moves": -1,  # Special value for total random scramble
                "timer_enabled": True,
            },
            "limited_time": {
                "name": "Limited Time",
                "description": "Solve the cube before time runs out! - 15 moves scramble",
                "scramble_moves": 15,
                "timer_enabled": True,
                "countdown_mode": True,
            },
            "limited_moves": {
                "name": "Limited Moves",
                "description": "Solve the cube with limited moves! - 15 moves scramble",
                "scramble_moves": 15,
                "timer_enabled": True,
                "countdown_moves": True,
            },
            "daily_cube": {
                "name": "Daily Cube",
                "description": "Same scramble for all players today! Compete globally!",
                "scramble_moves": 20,  # Fixed scramble based on date
                "timer_enabled": True,
                "daily_mode": True,
            }
        }
    
    def get_game_mode_config(self, difficulty):
        """Get the configuration for a specific game mode"""
        # Update limited_time configuration with current selected time limit
        if difficulty == "limited_time":
            self.game_modes["limited_time"]["time_limit"] = self.selected_time_limit
            # Also update the description to reflect current time
            time_display = self._format_time_display(self.selected_time_limit)
            self.game_modes["limited_time"]["description"] = f"Solve the cube before time runs out! ({time_display})"
        
        # Update limited_moves configuration with current selected move limit
        if difficulty == "limited_moves":
            self.game_modes["limited_moves"]["move_limit"] = self.selected_move_limit
            # Also update the description to reflect current move limit
            self.game_modes["limited_moves"]["description"] = f"Solve the cube with limited moves! ({self.selected_move_limit} moves max)"
        
        return self.game_modes.get(difficulty, self.game_modes["medium"])
    
    def _start_game(self, difficulty="normal"):
        """Start the game (close menu) with specified difficulty"""
        self.sound_manager.play("menu_select")
        # Clear hover effects before starting game
        self._clear_all_hover_effects()
        
        # Check if difficulty is different from current selection OR this is the first selection
        difficulty_changed = (difficulty != self.selected_difficulty) or not self.difficulty_ever_selected
        
        # Store the selected difficulty for future use
        self.selected_difficulty = difficulty
        
        # Track that difficulty has been changed at least once
        if difficulty_changed:
            self.has_difficulty_changed = True
            self.difficulty_ever_selected = True
            # Increment difficulty change count in game instance
            if hasattr(self, "game") and self.game:
                self.game.increment_difficulty_change_count()
                # Refresh main menu buttons to reflect the change
                self.refresh_main_menu_buttons()
            
            if hasattr(self, "debug_mode") and self.debug_mode:
                print(f"Difficulty selected: {difficulty} (ESC now enabled)")
        
        # Change background based on difficulty (procedural, no external images)
        if hasattr(self, "game") and self.game:
            self.game.renderer.reload_skybox_texture(difficulty)
            if hasattr(self, "debug_mode") and self.debug_mode:
                print(f"Changed background preset to difficulty: {difficulty}")
            
            # Only request a new game if difficulty changed and we have changed it before
            # or if this is the very first time a difficulty is selected
            if difficulty_changed:
                self.game.request_new_game()
        
        if hasattr(self, "debug_mode") and self.debug_mode:
            print(f"Starting game with difficulty: {difficulty}")
        
        # Start closing animation instead of immediately setting active to False
        if not self.is_animating:  # Prevent multiple animations
            self.toggle()

    def _play_current_difficulty(self):
        """Play with the current difficulty without changing it (just closes menu)"""
        self.sound_manager.play("menu_select")
        # Clear hover effects before starting game
        self._clear_all_hover_effects()
        
        if hasattr(self, "debug_mode") and self.debug_mode:
            print(f"Playing with current difficulty: {self.selected_difficulty}")
        
        # Start closing animation instead of immediately setting active to False
        if not self.is_animating:  # Prevent multiple animations
            self.toggle()
    
    def _open_difficulty_select(self):
        """Open difficulty selection submenu or user setup if needed"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        
        # Check if user setup is needed first
        if not self.user_manager.is_setup_completed():
            self.show_user_setup()
        else:
            self._change_menu(self.difficulty_menu)
    
    def _open_settings(self):
        """Open settings submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self._change_menu(self.settings_menu)
    
    def _open_controls(self):
        """Open controls submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self._change_menu(self.controls_menu)
    
    def _show_quit_confirmation(self):
        """Show confirmation dialog before quitting"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self._change_menu(self.quit_confirmation_menu)
    
    def _cancel_quit(self):
        """Cancel quit and return to main menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()
        self._change_menu(self.main_menu)
    
    def _open_personal_best(self):
        """Open statistics submenu (renamed from personal best)"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        
        # Check if user setup is needed first
        if not self.user_manager.is_setup_completed():
            self.show_user_setup()
        else:
            # Refresh the statistics content before showing
            self._create_personal_best_content()
            self._change_menu(self.personal_best_menu)
    
    def _open_achievements(self):
        """Open achievements submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        
        # Refresh the achievements content before showing
        self._create_achievements_content()
        self._change_menu(self.achievements_menu)
    
    def _switch_to_personal_records_tab(self):
        """Switch to personal records tab in statistics"""
        self.sound_manager.play("menu_select")
        self.statistics_tab = "personal_records"
        self._create_personal_best_content()
    
    def _switch_to_leaderboard_tab(self):
        """Switch to global leaderboard tab in statistics"""
        self.sound_manager.play("menu_select")
        self.statistics_tab = "global_leaderboard"
        # Fetch leaderboard data when switching to the tab
        self._fetch_leaderboard_data()
        self._create_personal_best_content()
    
    def _switch_to_daily_leaderboard_tab(self):
        """Switch to daily leaderboard tab in statistics"""
        self.sound_manager.play("menu_select")
        self.statistics_tab = "daily_leaderboard"
        # Fetch daily leaderboard data when switching to the tab
        self._fetch_daily_leaderboard_data()
        self._create_personal_best_content()
    
    def _fetch_leaderboard_data(self, force_refresh=False):
        """Fetch leaderboard data from Supabase in background thread."""
        # Don't fetch if already loading
        if self.leaderboard_loading:
            return
        
        # Check if we should use cached data (cache for 30 seconds)
        current_time = time.time()
        if not force_refresh and self.leaderboard_data and (current_time - self.leaderboard_last_fetch) < 30:
            return
        
        # Check if Supabase is configured
        if not self.supabase_manager or not self.supabase_manager.is_configured():
            self.leaderboard_error = "Leaderboard not configured"
            self.leaderboard_data = []
            return
        
        self.leaderboard_loading = True
        self.leaderboard_error = None
        self.leaderboard_ui_refresh_pending = True
        
        def fetch_task():
            try:
                # Get filter values
                game_mode = None if self.leaderboard_filter_mode == "All Modes" else self.leaderboard_filter_mode
                region = None if self.leaderboard_filter_region == "All Regions" else self.leaderboard_filter_region
                
                # Fetch data (returns tuple: data, is_offline)
                data, is_offline = self.supabase_manager.get_leaderboard(
                    game_mode=game_mode,
                    region=region,
                    sort_by="best_time",
                    limit=50,
                    ascending=True
                )
                
                self.leaderboard_data = data if data else []
                self.leaderboard_last_fetch = time.time()
                self.leaderboard_is_offline = is_offline
                self.leaderboard_error = None
            except Exception as e:
                print(f"Error fetching leaderboard: {e}")
                self.leaderboard_error = "Failed to load leaderboard"
                self.leaderboard_is_offline = False
                self.leaderboard_data = []
            finally:
                self.leaderboard_loading = False
                # Mark that UI needs refresh - will be handled in main thread
                if self.statistics_tab == "global_leaderboard":
                    self.leaderboard_ui_refresh_pending = True
        
        thread = threading.Thread(target=fetch_task, daemon=True)
        thread.start()
    
    def _fetch_daily_leaderboard_data(self, force_refresh=False):
        """Fetch daily leaderboard data from Supabase in background thread."""
        # Don't fetch if already loading
        if self.daily_leaderboard_loading:
            return
        
        # Check if we should use cached data (cache for 30 seconds)
        current_time = time.time()
        if not force_refresh and self.daily_leaderboard_data and (current_time - self.daily_leaderboard_last_fetch) < 30:
            return
        
        # Check if Supabase is configured
        if not self.supabase_manager or not self.supabase_manager.is_configured():
            self.daily_leaderboard_error = "Leaderboard not configured"
            self.daily_leaderboard_data = []
            return
        
        self.daily_leaderboard_loading = True
        self.daily_leaderboard_error = None
        self.daily_leaderboard_ui_refresh_pending = True
        
        def fetch_task():
            try:
                # Get filter values
                region = None if self.daily_leaderboard_filter_region == "All Regions" else self.daily_leaderboard_filter_region
                
                # Fetch daily leaderboard data (returns tuple: data, is_offline)
                data, is_offline = self.supabase_manager.get_daily_leaderboard(
                    region=region,
                    limit=50
                )
                
                self.daily_leaderboard_data = data if data else []
                self.daily_leaderboard_last_fetch = time.time()
                self.daily_leaderboard_is_offline = is_offline
                self.daily_leaderboard_error = None
            except Exception as e:
                print(f"Error fetching daily leaderboard: {e}")
                self.daily_leaderboard_error = "Failed to load daily leaderboard"
                self.daily_leaderboard_is_offline = False
                self.daily_leaderboard_data = []
            finally:
                self.daily_leaderboard_loading = False
                # Mark that UI needs refresh - will be handled in main thread
                if self.statistics_tab == "daily_leaderboard":
                    self.daily_leaderboard_ui_refresh_pending = True
        
        thread = threading.Thread(target=fetch_task, daemon=True)
        thread.start()
    
    def _on_daily_leaderboard_region_filter_change(self, selected_tuple, index):
        """Handle region filter change in daily leaderboard."""
        self.sound_manager.play("menu_select")
        # Use index to get the actual region value from REGION_OPTIONS
        if 0 <= index < len(REGION_OPTIONS):
            self.daily_leaderboard_filter_region = REGION_OPTIONS[index]
        else:
            self.daily_leaderboard_filter_region = "All Regions"
        # Fetch will auto-refresh UI when data is ready
        self._fetch_daily_leaderboard_data(force_refresh=True)
    
    def _refresh_daily_leaderboard(self):
        """Force refresh the daily leaderboard data."""
        self.sound_manager.play("menu_select")
        self._fetch_daily_leaderboard_data(force_refresh=True)
    
    def _on_leaderboard_mode_filter_change(self, selected_tuple, index):
        """Handle game mode filter change in leaderboard."""
        self.sound_manager.play("menu_select")
        # Use index to get the actual game mode value (lowercase) from GAME_MODE_OPTIONS
        # The selected_tuple contains the display text
        if 0 <= index < len(GAME_MODE_OPTIONS):
            self.leaderboard_filter_mode = GAME_MODE_OPTIONS[index]
        else:
            self.leaderboard_filter_mode = "All Modes"
        # Fetch will auto-refresh UI when data is ready
        self._fetch_leaderboard_data(force_refresh=True)
    
    def _on_leaderboard_region_filter_change(self, selected_tuple, index):
        """Handle region filter change in leaderboard."""
        self.sound_manager.play("menu_select")
        # Use index to get the actual region value from REGION_OPTIONS
        if 0 <= index < len(REGION_OPTIONS):
            self.leaderboard_filter_region = REGION_OPTIONS[index]
        else:
            self.leaderboard_filter_region = "All Regions"
        # Fetch will auto-refresh UI when data is ready
        self._fetch_leaderboard_data(force_refresh=True)
    
    def _refresh_leaderboard(self):
        """Manually refresh the leaderboard data."""
        self.sound_manager.play("menu_select")
        # Fetch will auto-refresh UI when data is ready
        self._fetch_leaderboard_data(force_refresh=True)
    
    def _open_user_edit(self):
        """Open user edit dialog"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()
        # Pre-fill with current user data
        self.user_setup_username = self.user_manager.get_username()
        current_region = self.user_manager.get_region()
        if current_region in REGIONS:
            self.user_setup_region_index = REGIONS.index(current_region)
        else:
            self.user_setup_region_index = 0
        self.username_error = None  # Clear any previous error
        self._create_user_edit_content()
        self._change_menu(self.user_edit_menu)
    
    def _open_audio_settings(self):
        """Open audio settings submenu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self._change_menu(self.audio_settings_menu)
    
    def _open_time_selection(self):
        """Open time selection submenu for limited time mode"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self._change_menu(self.time_selection_menu)
    
    def _on_time_limit_change(self, value):
        """Handle time limit change from slider"""
        # Convert slider value (0-6) to actual time in seconds
        self.selected_time_limit = self.time_limit_options[int(value)]
        self.sound_manager.play("menu_select")
    
    def _on_time_limit_change_and_update_display(self, value):
        """Handle time limit change from slider and update display"""
        self._on_time_limit_change(value)
        # Update the display label
        if hasattr(self, 'time_display_label'):
            self.time_display_label.set_title(f"Time Limit: {self._format_time_display(self.selected_time_limit)}")
    
    def _back_to_difficulty(self):
        """Go back to difficulty selection menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()
        self._change_menu(self.difficulty_menu)
    
    def _format_time_display(self, seconds):
        """Format time in seconds to display string"""
        if seconds < 60:
            return f"{seconds} sec"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} min"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            return f"{hours}h"
    
    def _start_limited_time_game(self):
        """Start the limited time game with selected time limit - always starts fresh"""
        self.sound_manager.play("menu_select")
        # Clear hover effects before starting game
        self._clear_all_hover_effects()
        
        # Always set the difficulty and mark as changed to force new game
        self.selected_difficulty = "limited_time"
        self.has_difficulty_changed = True
        self.difficulty_ever_selected = True
        
        # Update game instance and force new game
        if hasattr(self, "game") and self.game:
            # Increment difficulty change count to ensure menu shows ESC option
            self.game.increment_difficulty_change_count()
            # Refresh main menu buttons to reflect the change
            self.refresh_main_menu_buttons()
            
            # Change background based on difficulty (procedural, no external images)
            self.game.renderer.reload_skybox_texture("limited_time")
            
            # Always request a new game when starting from time selection menu
            self.game.request_new_game()
            
            if hasattr(self, "debug_mode") and self.debug_mode:
                print(f"Starting fresh limited time game with {self.selected_time_limit} seconds")
        
        # Start closing animation instead of immediately setting active to False
        if not self.is_animating:  # Prevent multiple animations
            self.toggle()
    
    def _open_moves_selection(self):
        """Open moves selection submenu for limited moves mode"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self._change_menu(self.moves_selection_menu)
    
    def _on_move_limit_change(self, value):
        """Handle move limit change from slider"""
        # Convert slider value (0-35) to actual move count (15-50)
        self.selected_move_limit = self.move_limit_options[int(value)]
        self.sound_manager.play("menu_select")
    
    def _on_move_limit_change_and_update_display(self, value):
        """Handle move limit change from slider and update display"""
        self._on_move_limit_change(value)
        # Update the display label
        if hasattr(self, 'moves_display_label'):
            self.moves_display_label.set_title(f"Move Limit: {self.selected_move_limit} moves")
    
    def _start_limited_moves_game(self):
        """Start the limited moves game with selected move limit - always starts fresh"""
        self.sound_manager.play("menu_select")
        # Clear hover effects before starting game
        self._clear_all_hover_effects()
        
        # Always set the difficulty and mark as changed to force new game
        self.selected_difficulty = "limited_moves"
        self.has_difficulty_changed = True
        self.difficulty_ever_selected = True
        
        # Update game instance and force new game
        if hasattr(self, "game") and self.game:
            # Increment difficulty change count to ensure menu shows ESC option
            self.game.increment_difficulty_change_count()
            # Refresh main menu buttons to reflect the change
            self.refresh_main_menu_buttons()
            
            # Change background based on difficulty (procedural, no external images)
            self.game.renderer.reload_skybox_texture("limited_moves")
            
            # Always request a new game when starting from moves selection menu
            self.game.request_new_game()
            
            if hasattr(self, "debug_mode") and self.debug_mode:
                print(f"Starting fresh limited moves game with {self.selected_move_limit} moves")
        
        # Start closing animation instead of immediately setting active to False
        if not self.is_animating:  # Prevent multiple animations
            self.toggle()

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
        self._update_apply_button_state()
    
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
        self._update_apply_button_state()
    
    def _on_fps_toggle(self, value):
        """Handle FPS toggle"""
        # Play selection sound
        self.sound_manager.play("menu_select")
        
        self.show_fps = value
        self.settings_changed = True
        self._update_apply_button_state()
    
    def _on_hints_toggle(self, value):
        """Handle hints toggle"""
        # Play selection sound
        self.sound_manager.play("menu_select")
        
        self.hints_enabled = value
        
        # Save to settings immediately
        self.settings_manager.set_hints_enabled(value)
        
        # Also update the game's hints_enabled if available
        if hasattr(self, "game") and self.game:
            self.game.hints_enabled = value
            # Close any active hint banners if hints are disabled
            if not value:
                self.game.hint_banner_active = False
                self.game.hint_expanded = False
                self.game.hint_banner_alpha = 0.0
    
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
            
        # Note: Volume changes are applied immediately, no need to set settings_changed
    
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
        
        # Note: Volume changes are applied immediately, no need to set settings_changed
    
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
        
        # Note: Volume changes are applied immediately, no need to set settings_changed
    
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
        
        # Note: Volume changes are applied immediately, no need to set settings_changed
    
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
        
        # Note: Volume changes are applied immediately, no need to set settings_changed
    
    def _apply_settings(self):
        """Apply all settings changes"""
        try:
            # Don't apply if no changes have been made
            if not self.settings_changed:
                return
            
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
                
                # Note: Audio settings are handled immediately in their change handlers, no need to update here
                
                self.settings_manager.save_settings()
                
                # Update sound effects volume based on new audio settings
                self.sound_manager.load_volumes_from_settings(self.settings_manager)
                
                self.settings_changed = False
                self._update_apply_button_state()
                
            # Return to main menu after applying settings
            self._back_to_main()
            
        except Exception as e:
            print(f"Error applying settings: {e}")
    
    def _back_to_main(self):
        """Return to the main menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        # Refresh main menu buttons in case difficulty change count has changed
        self.refresh_main_menu_buttons()
        self._change_menu(self.main_menu)
    
    def _back_to_settings(self):
        """Return to the settings menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()  # Clear hover effects when changing menu
        self._change_menu(self.settings_menu)
    
    def update(self):
        """Update animation state and alpha values"""
        # Run pygame-menu internal update each frame so scrollbars/scrollareas are computed.
        # Avoid doing it twice in the same frame if handle_event() already updated the menu.
        if self.active and self.current_menu and self.current_menu.is_enabled():
            if self._skip_pygame_menu_update_once:
                self._skip_pygame_menu_update_once = False
            else:
                try:
                    self.current_menu.update([])
                except Exception:
                    pass

        # Check if global leaderboard UI needs refresh (from background thread)
        if self.leaderboard_ui_refresh_pending and not self.leaderboard_loading:
            if self.statistics_tab == "global_leaderboard":
                self.leaderboard_ui_refresh_pending = False
                self._create_personal_best_content()
        
        # Check if daily leaderboard UI needs refresh (from background thread)
        if self.daily_leaderboard_ui_refresh_pending and not self.daily_leaderboard_loading:
            if self.statistics_tab == "daily_leaderboard":
                self.daily_leaderboard_ui_refresh_pending = False
                self._create_personal_best_content()
        
        # Always update button animations regardless of menu animation state
        self._update_button_animations()
        
        # Update tooltip state
        self._update_tooltip()
        
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
            self._change_menu(self.main_menu)
            
            # Capture and blur the background when opening the menu (if game has rendered)
            # Only capture if difficulty change count > 0 (don't blur when using main menu background)
            # Always try to recapture to ensure we have the current resolution
            should_capture_background = (
                self.game_rendered and 
                hasattr(self, "game") and self.game and 
                self.game.get_difficulty_change_count() > 0
            )
            if should_capture_background:
                self._capture_and_blur_background()
    
    def _capture_and_blur_background(self):
        """Capture the current screen and create a blurred version for the background"""
        # Only capture if the game has rendered at least once
        if not self.game_rendered:
            self.background_capture = None
            self.blurred_background = None
            return
            
        try:
            # Get the current framebuffer data
            screen_width = self.width
            screen_height = self.height
            
            # Read the current OpenGL framebuffer
            from OpenGL.GL import glReadPixels, GL_RGB, GL_UNSIGNED_BYTE
            
            # Capture the screen buffer
            glPixels = glReadPixels(0, 0, screen_width, screen_height, GL_RGB, GL_UNSIGNED_BYTE)
            
            # Convert to pygame surface (much simpler approach)
            self.background_capture = pygame.image.fromstring(glPixels, (screen_width, screen_height), 'RGB')
            
            # Flip vertically (OpenGL coordinates are flipped)
            self.background_capture = pygame.transform.flip(self.background_capture, False, True)
            
            # Apply fast blur effect
            self._apply_fast_blur_effect()
            
        except Exception as e:
            print(f"Error capturing background: {e}")
            # Fallback to None - will use solid background
            self.background_capture = None
            self.blurred_background = None
            self.blurred_background = None
    
    def _apply_fast_blur_effect(self):
        """Apply a fast blur effect using pygame's built-in scaling and smoothing"""
        if self.background_capture is None:
            return
            
        try:
            original_size = self.background_capture.get_size()
            
            # Use enhanced scaling method for fast, smooth blur (no scipy dependency)
            blurred_surface = self.background_capture.copy()
            
            # First pass: Scale down more aggressively for stronger blur
            small_size = (original_size[0] // 8, original_size[1] // 8)  # Strong downscaling for blur effect
            
            # Multiple downscale-upscale passes for smoother blur
            for _ in range(3):  # Multiple passes for smoother blur
                # Scale down with smoothing
                small_surface = pygame.transform.smoothscale(blurred_surface, small_size)
                # Scale back up with smoothing
                blurred_surface = pygame.transform.smoothscale(small_surface, original_size)
            
            # Additional blur pass with intermediate scaling for even smoother result
            medium_size = (original_size[0] // 3, original_size[1] // 3)
            medium_surface = pygame.transform.smoothscale(blurred_surface, medium_size)
            blurred_surface = pygame.transform.smoothscale(medium_surface, original_size)
            
            self.blurred_background = blurred_surface
            
            # Add subtle darkening for better contrast with menu text
            dark_overlay = pygame.Surface(original_size, pygame.SRCALPHA)
            dark_overlay.fill((0, 0, 0, 80))  # Darkening for better readability
            self.blurred_background.blit(dark_overlay, (0, 0))
            
        except Exception as e:
            print(f"Error applying blur: {e}")
            # Fallback to original capture
            self.blurred_background = self.background_capture
    
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

        # Ignore TEXTINPUT events and rely on KEYDOWN.
        if (
            self.current_menu in (getattr(self, 'user_setup_menu', None), getattr(self, 'user_edit_menu', None))
            and event.type == pygame.TEXTINPUT
        ):
            return True
        
        # Disable keyboard navigation on mouse movement
        if event.type == pygame.MOUSEMOTION:
            self._disable_keyboard_navigation_on_mouse()
            self.update_cursor(event.pos)
            self._update_hover_effects(event.pos)
        
        # Clear hover effects on mouse button clicks to prevent sticky hover
        if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP]:
            self._disable_keyboard_navigation_on_mouse()
            self._clear_all_hover_effects()
            
            # Check if click is on Statistics button in bottom right (only on main menu)
            if (event.type == pygame.MOUSEBUTTONDOWN and 
                self.current_menu == self.main_menu and 
                hasattr(self, 'personal_best_rect')):
                
                mouse_x, mouse_y = event.pos
                
                # Check if click is within the Statistics button area
                if self.personal_best_rect.collidepoint(mouse_x, mouse_y):
                    self._open_personal_best()
                    return True
            
            # Check if click is on Achievements button in top right (only on main menu)
            if (event.type == pygame.MOUSEBUTTONDOWN and 
                self.current_menu == self.main_menu and 
                hasattr(self, 'achievements_rect') and 
                self.achievements_rect):
                
                mouse_x, mouse_y = event.pos
                
                # Check if click is within the Achievements button area
                if self.achievements_rect.collidepoint(mouse_x, mouse_y):
                    self._open_achievements()
                    return True
            
            # Check if click is on user edit button (only in statistics menu)
            if (event.type == pygame.MOUSEBUTTONDOWN and 
                self.current_menu == self.personal_best_menu and 
                hasattr(self, 'user_edit_rect') and 
                self.user_edit_rect):
                
                mouse_x, mouse_y = event.pos
                
                if self.user_edit_rect.collidepoint(mouse_x, mouse_y):
                    self._open_user_edit()
                    return True
        
        # Handle menu navigation
        if self.current_menu and self.current_menu.is_enabled():
            if event.type == pygame.KEYDOWN:
                # For user setup and edit menus, only handle ESC key here
                # Let all other keys pass through to the text input widget
                if self.current_menu == self.user_setup_menu:
                    if event.key == pygame.K_ESCAPE:
                        # Don't allow escaping from user setup
                        return True
                    # Pass all other keys to pygame-menu for text input
                    updated = self.current_menu.update([event])
                    self._skip_pygame_menu_update_once = True
                    return updated or self.active
                elif self.current_menu == self.user_edit_menu:
                    if event.key == pygame.K_ESCAPE:
                        # Go back to statistics
                        self._back_to_statistics()
                        return True
                    # Pass all other keys to pygame-menu for text input
                    updated = self.current_menu.update([event])
                    self._skip_pygame_menu_update_once = True
                    return updated or self.active
                
                # Handle keyboard navigation (arrow keys, Tab, Enter, Space)
                # But not for text input menus
                if self._handle_keyboard_navigation(event):
                    return True
                
                # Handle ESC key
                if event.key == pygame.K_ESCAPE:
                    if self.current_menu == self.main_menu:
                        # Start closing animation instead of immediately setting active to False
                        if not self.is_animating:  # Prevent multiple toggle calls during animation
                            self.toggle()
                        return True
                    elif self.current_menu == self.quit_confirmation_menu:
                        # Go back to main menu when pressing ESC in quit confirmation
                        self._cancel_quit()
                        return True
                    elif self.current_menu == self.audio_settings_menu:
                        self.sound_manager.play("menu_select")
                        self._clear_all_hover_effects()  # Clear hover effects when changing menu
                        self._change_menu(self.settings_menu)
                        return True
                    else:
                        self.sound_manager.play("menu_select")
                        self._clear_all_hover_effects()  # Clear hover effects when changing menu
                        self._change_menu(self.main_menu)
                        return True
        
        # Let pygame-menu handle the event
        updated = self.current_menu.update([event])
        self._skip_pygame_menu_update_once = True
        
        # Check if we need to go back to main menu (after pygame-menu processes the event)
        return updated or self.active
    
    def _clear_all_hover_effects(self):
        """Clear hover effects from all widgets and hide tooltips"""
        for widget in self.hovered_widgets.copy():
            self._apply_hover_effect(widget, False)
        self.hovered_widgets.clear()
        
        # Hide any active tooltips
        self._hide_tooltip()
    
    def _update_hover_effects(self, mouse_pos):
        """Update hover effects for widgets based on mouse position"""
        if not self.current_menu:
            return
            
        widgets = self.current_menu.get_widgets()
        currently_hovered = set()

        for widget in widgets:
            try:
                # Use to_real_position=True for correct rect in scrollable menus
                widget_rect = widget.get_rect(to_real_position=True)
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

            except Exception:
                # If widget doesn't support get_rect(), skip it
                continue

        # Update the tracked hovered widgets
        self.hovered_widgets = currently_hovered
    
    def _apply_hover_effect(self, widget, is_hovered):
        """Apply or remove hover effect from a widget"""
        try:
            widget_class_name = widget.__class__.__name__
            
            if widget_class_name == 'Button':
                # Check if this is the disabled apply button
                if (hasattr(self, 'apply_button') and widget == self.apply_button and 
                    not self.settings_changed):
                    # Skip hover effects for disabled apply button
                    return
                
                # Check if this is a difficulty button
                if widget in self.difficulty_buttons:
                    self._animate_difficulty_button(widget, is_hovered)
                else:
                    # Check if this is a "Start Game" button with golden background
                    is_golden_start_button = (
                        (hasattr(self, 'time_start_btn') and widget == self.time_start_btn) or
                        (hasattr(self, 'moves_start_btn') and widget == self.moves_start_btn)
                    )
                    
                    # Regular button hover effect (text color change)
                    if hasattr(widget, '_font_color'):
                        if is_hovered:
                            if is_golden_start_button:
                                # Use black text for better visibility on golden background
                                widget._font_color = (0, 0, 0)  # Black
                            else:
                                widget._font_color = self.text_color_hover
                        else:
                            widget._font_color = self.text_color_normal
                            
                    # Also try to update the button's style if possible
                    if hasattr(widget, 'update_font'):
                        hover_color = (0, 0, 0) if is_golden_start_button and is_hovered else (self.text_color_hover if is_hovered else self.text_color_normal)
                        widget.update_font({
                            'color': hover_color
                        })
                    
        except Exception as e:
            # Silently handle any errors
            pass
    
    def _animate_difficulty_button(self, button, is_hovered):
        """Apply animated hover effect to difficulty buttons and handle tooltips"""
        if button not in self.button_animations:
            return
            
        animation_state = self.button_animations[button]
        current_time = time.time()
        
        if is_hovered:
            if not animation_state['is_hovering']:
                # Start hover animation
                animation_state['is_hovering'] = True
                animation_state['animation_start_time'] = current_time
                
                # Start tooltip timer
                self._start_tooltip(button)
        else:
            if animation_state['is_hovering']:
                # Start unhover animation
                animation_state['is_hovering'] = False
                animation_state['animation_start_time'] = current_time
                
                # Hide tooltip
                self._hide_tooltip()
    
    def _start_tooltip(self, button):
        """Start tooltip timer for a difficulty button"""
        if button in self.difficulty_buttons:
            self.current_tooltip_button = button
            self.tooltip_start_time = time.time()
            self.tooltip_text = self.difficulty_buttons[button]['description']
            # Tooltip will become active after delay in update method
    
    def _hide_tooltip(self):
        """Hide the current tooltip"""
        self.tooltip_active = False
        self.current_tooltip_button = None
        self.tooltip_text = ""
        self.tooltip_surface = None
        self.tooltip_rect = None
    
    def _update_tooltip(self):
        """Update tooltip state and create tooltip surface if needed"""
        if not self.current_tooltip_button or not self.tooltip_text:
            return
            
        # Check if enough time has passed to show tooltip
        current_time = time.time()
        if (current_time - self.tooltip_start_time >= self.tooltip_delay and 
            not self.tooltip_active):
            self.tooltip_active = True
            self._create_tooltip_surface()
    
    def _create_tooltip_surface(self):
        """Create the tooltip surface with description text"""
        if not self.tooltip_text:
            return
            
        # Initialize tooltip font if needed
        if not self.tooltip_font:
            try:
                self.tooltip_font = pygame_menu.font.get_font(pygame_menu.font.FONT_FRANCHISE, 28)
            except:
                # Fallback to default font if franchise font fails
                self.tooltip_font = pygame.font.Font(None, 28)
        
        # Create tooltip surface
        padding = 15
        text_color = (255, 255, 255)
        bg_color = (20, 20, 30, 240)  # Dark semi-transparent background
        border_color = (100, 150, 200, 255)  # Light blue border
        
        # Render text
        text_surface = self.tooltip_font.render(self.tooltip_text, True, text_color)
        text_width, text_height = text_surface.get_size()
        
        # Create tooltip background
        tooltip_width = text_width + (padding * 2)
        tooltip_height = text_height + (padding * 2)
        
        self.tooltip_surface = pygame.Surface((tooltip_width, tooltip_height), pygame.SRCALPHA)
        
        # Draw background with rounded corners
        pygame.draw.rect(self.tooltip_surface, bg_color, 
                        (0, 0, tooltip_width, tooltip_height), border_radius=8)
        pygame.draw.rect(self.tooltip_surface, border_color, 
                        (0, 0, tooltip_width, tooltip_height), width=2, border_radius=8)
        
        # Draw text
        self.tooltip_surface.blit(text_surface, (padding, padding))
        
        # Calculate tooltip position (centered below mouse, but keep on screen)
        mouse_pos = pygame.mouse.get_pos()
        tooltip_x = mouse_pos[0] - tooltip_width // 2
        tooltip_y = mouse_pos[1] + 20  # 20px below cursor
        
        # Keep tooltip on screen
        if tooltip_x < 10:
            tooltip_x = 10
        elif tooltip_x + tooltip_width > self.width - 10:
            tooltip_x = self.width - tooltip_width - 10
            
        if tooltip_y + tooltip_height > self.height - 10:
            tooltip_y = mouse_pos[1] - tooltip_height - 10  # Show above cursor instead
        
        self.tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
    
    def _draw_tooltip(self, screen):
        """Draw the tooltip if active"""
        if (self.tooltip_active and self.tooltip_surface and self.tooltip_rect and 
            self.current_menu == self.difficulty_menu):  # Only show in difficulty menu
            
            # Apply menu alpha to tooltip
            current_alpha = self.get_current_alpha()
            if current_alpha > 0.0:
                if current_alpha < 1.0:
                    tooltip_surface = self.tooltip_surface.copy()
                    tooltip_surface.set_alpha(int(255 * current_alpha))
                    screen.blit(tooltip_surface, self.tooltip_rect.topleft)
                else:
                    screen.blit(self.tooltip_surface, self.tooltip_rect.topleft)
    
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
                    # Check if this is a button with yellow/golden background
                    if button_info['difficulty'] in ['limited_time', 'limited_moves']:
                        # Use black text for better visibility on yellow background
                        button._font_color = (0, 0, 0)  # Black
                    else:
                        button._font_color = self.text_color_hover
                else:
                    button._font_color = self.text_color_normal
                    
        except Exception as e:
            # Silently handle any errors
            pass
    
    def _update_navigable_widgets(self):
        """Update the list of navigable widgets for keyboard navigation"""
        self.navigable_widgets = []
        if not self.current_menu:
            return
            
        widgets = self.current_menu.get_widgets()
        for widget in widgets:
            widget_class_name = widget.__class__.__name__
            # Only include buttons, dropdowns, and toggle switches
            if widget_class_name in ['Button', 'DropSelect', 'ToggleSwitch']:
                # Skip disabled widgets - check both as property and method
                try:
                    if hasattr(widget, 'is_selectable'):
                        is_selectable = widget.is_selectable() if callable(widget.is_selectable) else widget.is_selectable
                        if not is_selectable:
                            continue
                except:
                    pass
                self.navigable_widgets.append(widget)
    
    def _handle_keyboard_navigation(self, event):
        """Handle keyboard navigation (arrow keys, Enter, Space)"""
        if event.type != pygame.KEYDOWN:
            return False
            
        # Arrow keys or Tab - enable keyboard navigation and move focus
        if event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB]:
            # Enable keyboard navigation on first arrow key press
            if not self.keyboard_navigation_enabled:
                self.keyboard_navigation_enabled = True
                self._update_navigable_widgets()
                
                # Start with first widget focused
                if self.navigable_widgets:
                    self.focused_button_index = 0
                    self._apply_keyboard_focus(self.navigable_widgets[0], True)
                    return True
            
            # Navigate between widgets
            if not self.navigable_widgets:
                self._update_navigable_widgets()
                
            if self.navigable_widgets:
                # Clear current focus
                if 0 <= self.focused_button_index < len(self.navigable_widgets):
                    self._apply_keyboard_focus(self.navigable_widgets[self.focused_button_index], False)
                
                # Move focus
                if event.key in [pygame.K_DOWN, pygame.K_RIGHT] or (event.key == pygame.K_TAB and not (pygame.key.get_mods() & pygame.KMOD_SHIFT)):
                    self.focused_button_index = (self.focused_button_index + 1) % len(self.navigable_widgets)
                elif event.key in [pygame.K_UP, pygame.K_LEFT] or (event.key == pygame.K_TAB and (pygame.key.get_mods() & pygame.KMOD_SHIFT)):
                    self.focused_button_index = (self.focused_button_index - 1) % len(self.navigable_widgets)
                
                # Apply new focus
                self._apply_keyboard_focus(self.navigable_widgets[self.focused_button_index], True)
                
                # Play navigation sound
                if hasattr(self, 'sound_manager'):
                    self.sound_manager.play_slider_sound("menu_select")
                
                return True
                
        # Enter or Space - activate focused widget
        elif event.key in [pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE]:
            if self.keyboard_navigation_enabled and 0 <= self.focused_button_index < len(self.navigable_widgets):
                focused_widget = self.navigable_widgets[self.focused_button_index]
                
                # Simulate click on the focused widget
                if focused_widget.__class__.__name__ == 'Button':
                    # Play click sound
                    if hasattr(self, 'sound_manager'):
                        self.sound_manager.play("menu_select")
                    
                    # Trigger button action
                    focused_widget.apply()
                    return True
                elif focused_widget.__class__.__name__ == 'ToggleSwitch':
                    # Toggle the switch
                    focused_widget.change()
                    return True
                elif focused_widget.__class__.__name__ == 'DropSelect':
                    # Open dropdown (let pygame-menu handle this)
                    return False
        
        return False
    
    def _apply_keyboard_focus(self, widget, is_focused):
        """Apply or remove keyboard focus visual effect from a widget"""
        try:
            if is_focused:
                # Apply focus effect similar to hover
                self._apply_hover_effect(widget, True)
                
                # Add additional visual indicator (border or background change)
                if hasattr(widget, 'set_border'):
                    widget.set_border(2, (255, 255, 255))
                    
            else:
                # Remove focus effect
                self._apply_hover_effect(widget, False)
                
                # Remove border
                if hasattr(widget, 'set_border'):
                    widget.set_border(0, (0, 0, 0, 0))
                    
        except Exception:
            pass
    
    def _disable_keyboard_navigation_on_mouse(self):
        """Disable keyboard navigation when mouse is used"""
        if self.keyboard_navigation_enabled:
            # Clear current focus
            if 0 <= self.focused_button_index < len(self.navigable_widgets):
                self._apply_keyboard_focus(self.navigable_widgets[self.focused_button_index], False)
            
            self.keyboard_navigation_enabled = False
            self.focused_button_index = -1
    
    def _reset_keyboard_navigation(self):
        """Reset keyboard navigation state (called when changing menus)"""
        # Clear current focus if active
        if self.keyboard_navigation_enabled and 0 <= self.focused_button_index < len(self.navigable_widgets):
            self._apply_keyboard_focus(self.navigable_widgets[self.focused_button_index], False)
        
        # Reset state
        self.keyboard_navigation_enabled = False
        self.focused_button_index = -1
        self.navigable_widgets = []
    
    def _change_menu(self, new_menu):
        """Change to a new menu and reset keyboard navigation"""
        self._reset_keyboard_navigation()
        self.current_menu = new_menu
    
    def update_cursor(self, mouse_pos):
        """Update cursor based on menu interaction with enhanced feedback"""
        if not self.active:
            return
        
        # Check if mouse is over Statistics button (only on main menu)
        if (self.current_menu == self.main_menu and 
            hasattr(self, 'personal_best_rect') and 
            self.personal_best_rect):
            
            if self.personal_best_rect.collidepoint(mouse_pos):
                self.personal_best_button_hovered = True
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                return
            else:
                self.personal_best_button_hovered = False
        else:
            self.personal_best_button_hovered = False
        
        # Check if mouse is over Achievements button (only on main menu)
        if (self.current_menu == self.main_menu and 
            hasattr(self, 'achievements_rect') and 
            self.achievements_rect):
            
            if self.achievements_rect.collidepoint(mouse_pos):
                self.achievements_button_hovered = True
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                return
            else:
                self.achievements_button_hovered = False
        else:
            self.achievements_button_hovered = False
        
        # Check if mouse is over user edit button (only in statistics menu)
        if (self.current_menu == self.personal_best_menu and 
            hasattr(self, 'user_edit_rect') and 
            self.user_edit_rect):
            
            if self.user_edit_rect.collidepoint(mouse_pos):
                self.user_edit_button_hovered = True
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                return
            else:
                self.user_edit_button_hovered = False
        else:
            self.user_edit_button_hovered = False
        
        if self.current_menu:
            # Check if mouse is over any interactive widget
            selected_widget = self.current_menu.get_selected_widget()

            # Get the widget under mouse position
            widgets = self.current_menu.get_widgets()
            mouse_over_widget = False

            for widget in widgets:
                try:
                    # Use to_real_position=True for correct rect in scrollable menus
                    widget_rect = widget.get_rect(to_real_position=True)
                    if widget_rect.collidepoint(mouse_pos):
                        mouse_over_widget = True
                        # Check if it's an interactive widget by class name
                        widget_class_name = widget.__class__.__name__
                        if widget_class_name in ['Button', 'DropSelect', 'ToggleSwitch', 'RangeSlider']:
                            # Check if this is the disabled apply button
                            if (hasattr(self, 'apply_button') and widget == self.apply_button and 
                                not self.settings_changed):
                                # Show regular arrow cursor for disabled button
                                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                            else:
                                # Show hand cursor for enabled interactive widgets
                                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                            return
                except:
                    # If widget doesn't support get_rect(), skip it
                    continue

            # If not over any interactive widget, use arrow cursor
            if not mouse_over_widget:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
    
    def draw(self, screen):
        """Draw the menu on the screen with blur effect and alpha animation"""
        # Don't draw if completely invisible
        current_alpha = self.get_current_alpha()
        if current_alpha <= 0.0:
            return
        
        # Check if we should use the main menu background (when difficulty change count is 0)
        should_use_main_background = (
            hasattr(self, "game") and self.game and 
            self.game.get_difficulty_change_count() == 0 and 
            self.main_menu_background is not None
        )
        
        # Use main menu background for difficulty change count = 0
        if should_use_main_background:
            # Tile the main menu background 4 times (2x2 grid) to avoid zooming
            screen_size = (screen.get_width(), screen.get_height())
            bg_size = self.main_menu_background.get_size()
            
            # Calculate tile size (each tile is 1/4 of the screen)
            tile_width = screen_size[0] // 2
            tile_height = screen_size[1] // 2
            
            # Scale the background to fit each tile
            scaled_background = pygame.transform.scale(self.main_menu_background, (tile_width, tile_height))
            
            # Apply brightness enhancement to make the background more visible
            # Create a copy for brightness adjustment
            brightened_background = scaled_background.copy()
            
            # Create a bright overlay to enhance visibility
            brightness_overlay = pygame.Surface((tile_width, tile_height), pygame.SRCALPHA)
            brightness_overlay.fill((80, 80, 80, 120))  # Light gray overlay with transparency
            
            # Blend the brightness overlay with the background
            brightened_background.blit(brightness_overlay, (0, 0), special_flags=pygame.BLEND_ADD)
            
            # Apply alpha if needed
            if current_alpha < 1.0:
                brightened_background.set_alpha(int(255 * current_alpha))
            
            # Draw the brightened background in a 2x2 grid pattern
            for row in range(2):
                for col in range(2):
                    x = col * tile_width
                    y = row * tile_height
                    screen.blit(brightened_background, (x, y))
        else:
            # Use blurred background if available, otherwise fallback to solid overlay
            if self.blurred_background is not None:
                # Check if blurred background size matches current screen size
                bg_size = self.blurred_background.get_size()
                screen_size = (screen.get_width(), screen.get_height())
                
                if bg_size != screen_size:
                    # Size mismatch - scale the background or clear it
                    if hasattr(self, 'debug_mode') and self.debug_mode:
                        print(f"Background size mismatch: {bg_size} vs {screen_size}, clearing background")
                    self.blurred_background = None
                    self.background_capture = None
                    # Try to recapture with correct size if game has rendered
                    # Only capture if difficulty change count > 0 (don't blur when using main menu background)
                    should_capture_background = (
                        self.game_rendered and 
                        hasattr(self, "game") and self.game and 
                        self.game.get_difficulty_change_count() > 0
                    )
                    if should_capture_background:
                        self._capture_and_blur_background()
                
                # Draw blurred background with alpha if still available
                if self.blurred_background is not None:
                    if current_alpha < 1.0:
                        # Create a copy for alpha blending
                        background_surface = self.blurred_background.copy()
                        background_surface.set_alpha(int(255 * current_alpha))
                        screen.blit(background_surface, (0, 0))
                    else:
                        screen.blit(self.blurred_background, (0, 0))
            
            # Fallback to modern solid background if no blur available
            if self.blurred_background is None:
                # Fallback to modern solid background with gradient effect
                overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
                base_alpha = 200  # Slightly more opaque for better readability
                final_alpha = int(base_alpha * current_alpha)
                
                # Create a subtle gradient effect
                for y in range(screen.get_height()):
                    alpha_variation = final_alpha + int(20 * math.sin(y * 0.01))
                    alpha_variation = max(0, min(255, alpha_variation))
                    color = (8, 12, 28, alpha_variation)  # Dark blue-grey
                    pygame.draw.line(overlay, color, (0, y), (screen.get_width(), y))
                
                screen.blit(overlay, (0, 0))
        
        # Add subtle particle effects with reduced intensity for performance (only when not using main background)
        if current_alpha > 0.5 and not should_use_main_background:  # Only draw particles when menu is mostly visible and not using main background
            self._draw_background_effects(screen, current_alpha)
        
        # Handle dimension mismatch
        actual_width, actual_height = screen.get_size()
        if abs(self.width - actual_width) > 10 or abs(self.height - actual_height) > 10:
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"Menu dimension mismatch: stored {self.width}x{self.height}, actual {actual_width}x{actual_height}")
            self.width = actual_width
            self.height = actual_height
            self._create_menus()
        
        # Draw the current menu
        if self.current_menu:
            # Important: avoid calling set_alpha() on an SRCALPHA surface.
            # pygame-menu draws the scrollbar thumb using per-pixel alpha, and
            # combining that with per-surface alpha can make the thumb appear to
            # disappear on some systems.
            if current_alpha < 1.0:
                colorkey = (1, 2, 3)
                menu_surface = pygame.Surface((screen.get_width(), screen.get_height())).convert()
                menu_surface.fill(colorkey)
                menu_surface.set_colorkey(colorkey)
                self.current_menu.draw(menu_surface)
                menu_surface.set_alpha(int(255 * current_alpha))
                screen.blit(menu_surface, (0, 0))
            else:
                self.current_menu.draw(screen)
            
            # Draw Statistics button in bottom right corner (only on main menu)
            if (self.current_menu == self.main_menu and 
                hasattr(self, 'record_icon')):  # Only need to check if we have the icon loaded
                
                # Position the Statistics button in bottom right
                metrics = self._get_stats_button_metrics(screen.get_width(), screen.get_height())
                button_width = metrics["button_width"]
                button_height = metrics["button_height"]
                margin = metrics["margin"]
                icon_size = metrics["icon_size"]
                icon_padding = metrics["icon_padding"]
                
                button_x = screen.get_width() - button_width - margin
                button_y = screen.get_height() - button_height - margin
                
                # Create button background with hover effects
                button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
                
                if self.personal_best_button_hovered:
                    # Hover state - brighter background and border
                    pygame.draw.rect(screen, (80, 80, 80, 200), button_rect, border_radius=10)  # Brighter background
                    pygame.draw.rect(screen, (150, 150, 150), button_rect, 3, border_radius=10)  # Thicker, brighter border
                    
                    # Add subtle glow effect
                    glow_rect = pygame.Rect(button_x - 2, button_y - 2, button_width + 4, button_height + 4)
                    pygame.draw.rect(screen, (120, 120, 120, 100), glow_rect, 1, border_radius=10)
                else:
                    # Normal state
                    pygame.draw.rect(screen, (50, 50, 50, 180), button_rect, border_radius=10)  # Dark semi-transparent background
                    pygame.draw.rect(screen, (100, 100, 100), button_rect, 2, border_radius=10)  # Border
                
                # Draw the record icon if available
                if self.record_icon:
                    if (hasattr(self, "_record_icon_original") and self._record_icon_original and
                        (self.record_icon.get_width() != icon_size or self.record_icon.get_height() != icon_size)):
                        self.record_icon = pygame.transform.smoothscale(self._record_icon_original, (icon_size, icon_size))
                    icon_x = button_x + icon_padding
                    icon_y = button_y + (button_height - icon_size) // 2
                    screen.blit(self.record_icon, (icon_x, icon_y))
                    text_x = icon_x + icon_size + max(8, icon_padding // 2)
                else:
                    text_x = button_x + icon_padding
                
                # Draw the text using the menu's font with hover effects
                try:
                    # Use the same font as the menu widgets
                    font_size = metrics["hover_font_size"] if self.personal_best_button_hovered else metrics["font_size"]
                    menu_font = pygame_menu.font.get_font(pygame_menu.font.FONT_FRANCHISE, font_size)
                    
                    # Text color changes on hover
                    text_color = (255, 255, 255) if not self.personal_best_button_hovered else (255, 255, 180)
                    text_surface = menu_font.render("Statistics", True, text_color)
                    text_y = button_y + (button_height - text_surface.get_height()) // 2
                    
                    # Add shadow effect like the menu
                    shadow_surface = menu_font.render("Statistics", True, (0, 0, 0))
                    shadow_offset = 2 if self.personal_best_button_hovered else 1
                    screen.blit(shadow_surface, (text_x + shadow_offset, text_y + shadow_offset))
                    screen.blit(text_surface, (text_x, text_y))
                except:
                    # Fallback to basic font if menu font fails
                    font = pygame.font.Font(None, 24)
                    text_surface = font.render("Statistics", True, (255, 255, 255))
                    text_y = button_y + (button_height - text_surface.get_height()) // 2
                    screen.blit(text_surface, (text_x, text_y))
                
                # Store button rectangle for click detection
                self.personal_best_rect = button_rect
                
                # Draw Achievements button in top right corner (only on main menu)
                ach_metrics = self._get_stats_button_metrics(screen.get_width(), screen.get_height())
                ach_button_width = ach_metrics["button_width"]
                ach_button_height = ach_metrics["button_height"]
                ach_margin = ach_metrics["margin"]
                ach_icon_size = ach_metrics["icon_size"]
                ach_icon_padding = ach_metrics["icon_padding"]
                
                # Position in top right
                ach_button_x = screen.get_width() - ach_button_width - ach_margin
                ach_button_y = ach_margin
                
                # Create button background with hover effects
                ach_button_rect = pygame.Rect(ach_button_x, ach_button_y, ach_button_width, ach_button_height)
                
                if self.achievements_button_hovered:
                    # Hover state - golden glow for achievements
                    pygame.draw.rect(screen, (90, 75, 40, 200), ach_button_rect, border_radius=10)
                    pygame.draw.rect(screen, (240, 198, 38), ach_button_rect, 3, border_radius=10)
                    
                    # Add golden glow effect
                    glow_rect = pygame.Rect(ach_button_x - 2, ach_button_y - 2, ach_button_width + 4, ach_button_height + 4)
                    pygame.draw.rect(screen, (240, 198, 38, 100), glow_rect, 1, border_radius=10)
                else:
                    # Normal state
                    pygame.draw.rect(screen, (50, 50, 50, 180), ach_button_rect, border_radius=10)
                    pygame.draw.rect(screen, (100, 100, 100), ach_button_rect, 2, border_radius=10)
                
                # Draw the achievements icon if available
                if hasattr(self, 'achievements_icon') and self.achievements_icon:
                    if (hasattr(self, "_achievements_icon_original") and self._achievements_icon_original and
                        (self.achievements_icon.get_width() != ach_icon_size or self.achievements_icon.get_height() != ach_icon_size)):
                        self.achievements_icon = pygame.transform.smoothscale(self._achievements_icon_original, (ach_icon_size, ach_icon_size))
                    ach_icon_x = ach_button_x + ach_icon_padding
                    ach_icon_y = ach_button_y + (ach_button_height - ach_icon_size) // 2
                    screen.blit(self.achievements_icon, (ach_icon_x, ach_icon_y))
                    ach_text_x = ach_icon_x + ach_icon_size + max(8, ach_icon_padding // 2)
                else:
                    ach_text_x = ach_button_x + ach_icon_padding
                
                # Draw the text using the menu's font with hover effects
                try:
                    ach_font_size = ach_metrics["hover_font_size"] if self.achievements_button_hovered else ach_metrics["font_size"]
                    ach_menu_font = pygame_menu.font.get_font(pygame_menu.font.FONT_FRANCHISE, ach_font_size)
                    
                    # Text color - golden on hover
                    ach_text_color = (240, 198, 38) if self.achievements_button_hovered else (255, 255, 255)
                    ach_text_surface = ach_menu_font.render("Achievements", True, ach_text_color)
                    ach_text_y = ach_button_y + (ach_button_height - ach_text_surface.get_height()) // 2
                    
                    # Add shadow effect
                    ach_shadow_surface = ach_menu_font.render("Achievements", True, (0, 0, 0))
                    ach_shadow_offset = 2 if self.achievements_button_hovered else 1
                    screen.blit(ach_shadow_surface, (ach_text_x + ach_shadow_offset, ach_text_y + ach_shadow_offset))
                    screen.blit(ach_text_surface, (ach_text_x, ach_text_y))
                    
                    # Draw unlocked count badge
                    unlocked, total = self.achievements_manager.get_unlocked_count()
                    badge_text = f"{unlocked}/{total}"
                    badge_font = pygame_menu.font.get_font(pygame_menu.font.FONT_FRANCHISE, max(14, ach_font_size - 8))
                    badge_surface = badge_font.render(badge_text, True, (255, 255, 255))
                    badge_x = ach_button_x + ach_button_width - badge_surface.get_width() - 8
                    badge_y = ach_button_y + ach_button_height - badge_surface.get_height() - 4
                    
                    # Draw badge background
                    badge_rect = pygame.Rect(badge_x - 4, badge_y - 2, badge_surface.get_width() + 8, badge_surface.get_height() + 4)
                    badge_color = (240, 198, 38) if unlocked > 0 else (80, 80, 80)
                    pygame.draw.rect(screen, badge_color, badge_rect, border_radius=6)
                    screen.blit(badge_surface, (badge_x, badge_y))
                except:
                    pass
                
                # Store button rectangle for click detection
                self.achievements_rect = ach_button_rect
            
            # Draw user edit button in Statistics menu (top right corner)
            if (self.current_menu == self.personal_best_menu and 
                self.user_manager.is_setup_completed()):
                
                # Position the edit button in top right of content area
                edit_btn_size = 60
                edit_margin = 80
                edit_x = screen.get_width() - edit_btn_size - edit_margin
                edit_y = 80  # Below the title bar
                
                edit_rect = pygame.Rect(edit_x, edit_y, edit_btn_size, edit_btn_size)
                
                if self.user_edit_button_hovered:
                    pygame.draw.rect(screen, (80, 80, 80, 200), edit_rect, border_radius=8)
                    pygame.draw.rect(screen, (150, 150, 150), edit_rect, 2, border_radius=8)
                else:
                    pygame.draw.rect(screen, (50, 50, 50, 180), edit_rect, border_radius=8)
                    pygame.draw.rect(screen, (100, 100, 100), edit_rect, 1, border_radius=8)
                
                # Draw edit icon or fallback pencil symbol
                if self.edit_icon:
                    icon_x = edit_x + (edit_btn_size - 36) // 2
                    icon_y = edit_y + (edit_btn_size - 36) // 2
                    screen.blit(self.edit_icon, (icon_x, icon_y))
                else:
                    # Fallback: draw a simple pencil shape
                    try:
                        edit_font = pygame_menu.font.get_font(pygame_menu.font.FONT_FRANCHISE, 24)
                        edit_text = edit_font.render("✎", True, (255, 255, 255))
                        text_x = edit_x + (edit_btn_size - edit_text.get_width()) // 2
                        text_y = edit_y + (edit_btn_size - edit_text.get_height()) // 2
                        screen.blit(edit_text, (text_x, text_y))
                    except:
                        pass
                
                self.user_edit_rect = edit_rect
        
        # Draw tooltip if active (must be last to appear on top)
        self._draw_tooltip(screen)
    
    def _draw_background_effects(self, screen, alpha=1.0):
        """Draw simplified background effects for better performance"""
        try:
            # Create a subtle glow effect around the menu area (reduced particles)
            center_x = screen.get_width() // 2
            center_y = screen.get_height() // 2
            time_offset = time.time()
            
            # Reduced number of particles for better performance
            for i in range(4):  # Reduced from 8 to 4 particles
                angle = (time_offset * 20 + i * 90) % 360  # Slower animation
                radius = 120 + 30 * math.sin(time_offset + i)  # Smaller radius
                
                x = center_x + radius * math.cos(math.radians(angle))
                y = center_y + radius * math.sin(math.radians(angle))
                
                # Ensure particles stay on screen
                if 0 <= x <= screen.get_width() and 0 <= y <= screen.get_height():
                    size = int(2 + math.sin(time_offset * 2 + i))  # Smaller particles
                    base_alpha = int(120 + 60 * math.sin(time_offset + i * 0.5))  # Lower alpha
                    final_alpha = int(base_alpha * alpha)
                    
                    # Simple circle instead of complex glow
                    pygame.draw.circle(screen, (100, 150, 255, min(255, final_alpha)), 
                                     (int(x), int(y)), max(1, size))
                    
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
        
        # Reload logo image with new screen dimensions
        self._load_logo_image()

        # Rescale resolution-dependent icons
        self._scale_record_icon()
        self._scale_edit_icon()
        self._scale_achievements_icon()
        
        # Clear cached background images since resolution changed
        self.background_capture = None
        self.blurred_background = None
        
        # Force recreate menus with new dimensions
        self._create_menus()
        
        # Reset the resolution changed flag
        self.resolution_changed_flag = False
    
    def set_game_instance(self, game):
        """Set the game instance reference"""
        self.game = game
    
    def notify_game_rendered(self):
        """Notify the menu that the game has rendered at least one frame"""
        self.frames_rendered += 1
        if self.frames_rendered >= 3:  # Wait for a few frames to ensure proper initialization
            self.game_rendered = True
    
    def force_background_recapture(self):
        """Force recapture of the background (useful after resolution changes)"""
        # Only capture if difficulty change count > 0 (don't blur when using main menu background)
        should_capture_background = (
            self.game_rendered and 
            hasattr(self, "game") and self.game and 
            self.game.get_difficulty_change_count() > 0
        )
        if should_capture_background:
            self._capture_and_blur_background()

    def refresh_main_menu_buttons(self):
        """Refresh the main menu buttons based on current difficulty change count"""
        if hasattr(self, 'main_menu'):
            # Clear existing widgets (keeping only the title/logo)
            widgets = self.main_menu.get_widgets()
            widgets_to_remove = []
            
            # Remove all buttons and vertical margins, but keep the logo/title (first widget)
            for i, widget in enumerate(widgets):
                if i > 0:  # Keep only the first widget (logo/title)
                    # Check if it's a button or vertical margin that we want to remove
                    widget_type = type(widget).__name__
                    if 'Button' in widget_type or 'VMargin' in widget_type or 'VerticalMargin' in widget_type:
                        widgets_to_remove.append(widget)
            
            for widget in widgets_to_remove:
                self.main_menu.remove_widget(widget)
            
            # Re-add buttons with correct behavior
            if hasattr(self, "game") and self.game and self.game.get_difficulty_change_count() >= 1:
                # Once difficulty has been changed, "Play" just closes menu and "Change Mode" opens difficulty menu
                play_btn = self.main_menu.add.button("Play", self._play_current_difficulty)
                change_difficulty_btn = self.main_menu.add.button("Change Mode", self._open_difficulty_select)
            else:
                # Initially, "Play" opens difficulty selection menu
                play_btn = self.main_menu.add.button("Play", self._open_difficulty_select)
            
            settings_btn = self.main_menu.add.button("Settings", self._open_settings)
            controls_btn = self.main_menu.add.button("Controls", self._open_controls)
            quit_btn = self.main_menu.add.button("Quit", self._show_quit_confirmation)
            
            # Apply custom styling to main menu
            self._customize_menu_widgets(self.main_menu)
            
            # Personal Best button will be drawn manually in draw() method
    
    def _create_menus(self):
        """Create or recreate menus with current dimensions"""
        # Refresh resolution-dependent assets
        self._scale_record_icon()
        self._scale_edit_icon()
        self._scale_achievements_icon()

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
        
        # Create a separate theme for main menu without title bar
        self.main_theme = self.theme.copy()
        self.main_theme.title_bar_style = pygame_menu.widgets.MENUBAR_STYLE_NONE
        self.main_theme.title_background_color = (0, 0, 0, 0)  # Transparent background for main menu
        
        # Create theme for other menus (left-aligned titles with margin)
        self.sub_theme = self.theme.copy()
        self.sub_theme.title_alignment = ALIGN_LEFT
        # Add left margin to titles to prevent them from being at the window border
        self.sub_theme.title_offset = (10, 0)  # 10 pixels left margin
        # Ensure sub-theme also has a solid background for title visibility
        self.sub_theme.title_background_color = (0, 8, 18, 250)  # More opaque dark background for better visibility
        self.sub_theme.title_bar_style = pygame_menu.widgets.MENUBAR_STYLE_ADAPTIVE
        
        # Apply scrollbar settings to sub_theme for visibility in all sub-menus
        self.sub_theme.scrollbar_color = (15, 22, 35)
        self.sub_theme.scrollbar_slider_color = (240, 198, 38)
        self.sub_theme.scrollbar_slider_hover_color = (255, 255, 255)
        self.sub_theme.scrollbar_slider_pad = 1  # pygame-menu expects int padding
        self.sub_theme.scrollbar_thick = 14
        self.sub_theme.scrollbar_shadow = True
        self.sub_theme.scrollbar_shadow_color = (0, 0, 0)
        self.sub_theme.scrollbar_shadow_offset = 1

        # Create main menu with ACTUAL dimensions and no title (we'll add custom centered title)
        self.main_menu = pygame_menu.Menu(
            "",  # Empty title - we'll add a custom centered one
            self.width,
            self.height,
            theme=self.main_theme,  # Use the main_theme without title bar
            columns=1,
            rows=None
        )
        
        # Add custom logo image as title if available, otherwise use text
        logo_path = resource_path("utils/rubiks_logo.png")
        if os.path.exists(logo_path):
            logo_scale_width = self.width * 0.12 / 400  # 12% of width, slightly larger
            logo_scale_height = logo_scale_width
            self.main_menu.add.image(
                logo_path,
                angle=0,
                scale=(logo_scale_width, logo_scale_height),
                align=ALIGN_CENTER,
                margin=(0, 2)
            )
        else:
            # Fallback to text title if logo fails to load
            self.main_menu.add.label(
                "Rubik's Cube Simulator",
                font_size=65,
                font_name=pygame_menu.font.FONT_FRANCHISE,
                font_color=(255, 255, 255),
                font_shadow=True,
                font_shadow_color=(0, 0, 0),
                font_shadow_offset=3,
                align=ALIGN_CENTER,
                margin=(0, 2)
            )
        
        
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
        
        # Add main menu buttons - behavior changes based on difficulty change count
        if hasattr(self, "game") and self.game and self.game.get_difficulty_change_count() >= 1:
            play_btn = self.main_menu.add.button("Play", self._play_current_difficulty)
            change_difficulty_btn = self.main_menu.add.button("Change Mode", self._open_difficulty_select)
        else:
            play_btn = self.main_menu.add.button("Play", self._open_difficulty_select)
        settings_btn = self.main_menu.add.button("Settings", self._open_settings)
        controls_btn = self.main_menu.add.button("Controls", self._open_controls)
        quit_btn = self.main_menu.add.button("Quit", self._show_quit_confirmation)
        for widget in self.main_menu.get_widgets():
            if hasattr(widget, 'set_margin'):
                widget.set_margin(0, 2)
        self.main_menu.add.vertical_margin(self.height // 10)
        # Apply custom styling to main menu
        self._customize_menu_widgets(self.main_menu)
        
        # Create quit confirmation menu
        self.quit_confirmation_menu = pygame_menu.Menu(
            "Quit Game",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        self.quit_confirmation_menu.add.label("")
        self.quit_confirmation_menu.add.label("Are you sure you want to quit?")
        self.quit_confirmation_menu.add.label("")
        yes_btn = self.quit_confirmation_menu.add.button("Yes", pygame_menu.events.EXIT)
        no_btn = self.quit_confirmation_menu.add.button("No", self._cancel_quit)
        for widget in self.quit_confirmation_menu.get_widgets():
            if hasattr(widget, 'set_margin'):
                widget.set_margin(0, 2)
        self._customize_menu_widgets(self.quit_confirmation_menu)
        
        # Create difficulty selection menu with ACTUAL dimensions
        self.difficulty_menu = pygame_menu.Menu(
            "Select Mode",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Dynamically add difficulty options from game modes configuration
        game_modes = self.game_modes
        difficulty_icons = {"easy", "medium", "hard"}
        
        # Define background colors for each difficulty
        difficulty_colors = {
            "freeplay": (22, 57, 161, 200),  # Blue (original color)
            "easy": (33, 148, 33, 200),      # Green
            "medium": (199, 106, 26, 200),   # Orange
            "hard": (176, 28, 28, 200),      # Red
            "limited_time": (240, 198, 38, 200),   # Gold
            "limited_moves": (240, 198, 38, 200),  # Gold
            "daily_cube": (138, 43, 226, 200),     # Purple/Violet
        }
        
        # First, add Free Play button separately at the top
        self.difficulty_menu.add.vertical_margin(20)
        
        if "freeplay" in game_modes:
            mode_config = game_modes["freeplay"]
            button_text = mode_config['name']
            button_action = lambda difficulty="freeplay": self._start_game(difficulty)
            bg_color = difficulty_colors.get("freeplay", (40, 60, 90, 200))
            
            freeplay_button = self.difficulty_menu.add.button(
                button_text, 
                button_action,
                font_size=40,
                font_name=pygame_menu.font.FONT_FRANCHISE,
                background_color=bg_color,
                padding=(20, 370)  # (wide buttons)
            )
            
            # Store difficulty button for animation tracking and tooltip
            self.difficulty_buttons[freeplay_button] = {
                'difficulty': "freeplay",
                'original_color': bg_color,
                'base_color': bg_color,
                'description': mode_config['description']
            }
            
            # Initialize animation state for this button
            self.button_animations[freeplay_button] = {
                'is_hovering': False,
                'animation_start_time': 0,
                'glow_intensity': 0.0
            }
        
        # Add spacing before the horizontal row
        self.difficulty_menu.add.vertical_margin(30)
        
        # Create horizontal layout for Easy, Medium, Hard using frame
        horizontal_frame = self.difficulty_menu.add.frame_h(
            width=1000,  # Further increased width to accommodate buttons
            height=130,
            align=ALIGN_CENTER,
            margin=(0, 0)
        )
        
        # Add Easy, Medium, Hard buttons horizontally
        horizontal_difficulties = ["easy", "medium", "hard"]
        for i, mode_key in enumerate(horizontal_difficulties):
            if mode_key in game_modes:
                mode_config = game_modes[mode_key]
                button_text = mode_config['name']
                button_action = lambda difficulty=mode_key: self._start_game(difficulty)
                bg_color = difficulty_colors.get(mode_key, (40, 60, 90, 200))
                
                difficulty_button = horizontal_frame.pack(
                    self.difficulty_menu.add.button(
                        button_text, 
                        button_action,
                        font_size=40,
                        font_name=pygame_menu.font.FONT_FRANCHISE,
                        background_color=bg_color,
                        padding=(20, 100),  # Increased padding for wider buttons  
                        button_id=f'difficulty_{mode_key}',
                        margin=(0, 0)  # No margin on individual buttons when packed
                    ),
                    align=ALIGN_CENTER,
                    margin=(10, 0)  # Margin between buttons
                )
                
                # Store difficulty button for animation tracking and tooltip
                self.difficulty_buttons[difficulty_button] = {
                    'difficulty': mode_key,
                    'original_color': bg_color,
                    'base_color': bg_color,
                    'description': mode_config['description']
                }
                
                # Initialize animation state for this button
                self.button_animations[difficulty_button] = {
                    'is_hovering': False,
                    'animation_start_time': 0,
                    'glow_intensity': 0.0
                }
        
        # Create second horizontal layout for Limited Time, Limited Moves, and Daily Cube
        challenge_frame = self.difficulty_menu.add.frame_h(
            width=1200,  # Increased width to accommodate three buttons
            height=130,
            align=ALIGN_CENTER,
            margin=(0, 0)
        )
        
        # Add Limited Time, Limited Moves, and Daily Cube buttons horizontally
        challenge_modes = ["limited_time", "limited_moves", "daily_cube"]
        for mode_key in challenge_modes:
            if mode_key in game_modes:
                mode_config = game_modes[mode_key]
                # Add globe emoji for daily cube
                button_text = "🌍 " + mode_config['name'] if mode_key == "daily_cube" else mode_config['name']
                
                # Special handling for limited_time mode - open time selection instead of starting game directly
                if mode_key == "limited_time":
                    button_action = self._open_time_selection
                # Special handling for limited_moves mode - open moves selection instead of starting game directly
                elif mode_key == "limited_moves":
                    button_action = self._open_moves_selection
                else:
                    button_action = lambda difficulty=mode_key: self._start_game(difficulty)
                
                # Special color for daily cube
                if mode_key == "daily_cube":
                    bg_color = (138, 43, 226, 200)  # Purple/Violet
                else:
                    bg_color = difficulty_colors.get(mode_key, (40, 60, 90, 200))
                
                challenge_button = challenge_frame.pack(
                    self.difficulty_menu.add.button(
                        button_text, 
                        button_action,
                        font_size=40,
                        font_name=pygame_menu.font.FONT_FRANCHISE,
                        background_color=bg_color,
                        padding=(20, 80),  # Increased padding for wider buttons
                        button_id=f'difficulty_{mode_key}',
                        margin=(0, 0)  # No margin on individual buttons when packed
                    ),
                    align=ALIGN_CENTER,
                    margin=(10, 0)  # Reduced margin between challenge buttons
                )
                
                # Store difficulty button for animation tracking and tooltip
                self.difficulty_buttons[challenge_button] = {
                    'difficulty': mode_key,
                    'original_color': bg_color,
                    'base_color': bg_color,
                    'description': mode_config['description']
                }
                
                # Initialize animation state for this button
                self.button_animations[challenge_button] = {
                    'is_hovering': False,
                    'animation_start_time': 0,
                    'glow_intensity': 0.0
                }
        
        # Add final spacing and back button
        self.difficulty_menu.add.vertical_margin(20)
        back_btn = self.difficulty_menu.add.button("Back", self._back_to_main)
        
        # Apply custom styling to difficulty menu
        self._customize_menu_widgets(self.difficulty_menu)

        # Apply rounded styling to difficulty buttons
        self._style_difficulty_buttons()
        
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
        
        # Hints toggle
        self.settings_menu.add.toggle_switch(
            "Show Hints: ",
            default=self.hints_enabled,
            onchange=self._on_hints_toggle
        )
        
        # Audio Settings button
        audio_settings_btn = self.settings_menu.add.button("Audio Settings", self._open_audio_settings)
        
        # Settings menu buttons
        apply_btn = self.settings_menu.add.button("Apply Changes", self._apply_settings)
        back_btn = self.settings_menu.add.button("Back", self._back_to_main)

        # Store reference to apply button for dynamic updates
        self.apply_button = apply_btn

        # Apply custom styling to settings menu
        self._customize_menu_widgets(self.settings_menu)
        
        # Apply specific colors to the settings buttons
        self._style_settings_buttons(apply_btn, back_btn)
        
        # Ensure apply button starts in correct state
        self._update_apply_button_state()
        
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
                ("Rotate camera view", "[Right Click + Drag]"),
                ("Perform cube moves", "[Left Click + Drag]"),
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
        # Ensure the Back button gets hover/cursor styling
        self._apply_hover_effect(back_btn, False)
        
        # Create statistics menu (renamed from personal best) with ACTUAL dimensions
        self.personal_best_menu = pygame_menu.Menu(
            "Statistics",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Create statistics menu content
        self._create_personal_best_content()
        
        # Create achievements menu
        self.achievements_menu = pygame_menu.Menu(
            "Achievements",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Create achievements menu content
        self._create_achievements_content()
        
        # Create user setup menu for first-time setup
        self.user_setup_menu = pygame_menu.Menu(
            "Welcome!",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        self._create_user_setup_content()
        
        # Create user edit menu for editing user info
        self.user_edit_menu = pygame_menu.Menu(
            "Edit Profile",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Create time selection menu for limited time mode
        self.time_selection_menu = pygame_menu.Menu(
            "Select Time Limit",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Add description
        self.time_selection_menu.add.vertical_margin(20)
        self.time_selection_menu.add.label(
            "Choose your time limit for the challenge:",
            font_size=45,
            font_color=(255, 255, 255),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        self.time_selection_menu.add.vertical_margin(30)
        
        # Create time display label
        self.time_display_label = self.time_selection_menu.add.label(
            f"Time Limit: {self._format_time_display(self.selected_time_limit)}",
            font_size=45,
            font_color=(240, 198, 38),  # Golden color
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.time_selection_menu.add.vertical_margin(20)
        
        # Add time slider with labels
        time_labels = [self._format_time_display(time) for time in self.time_limit_options]
        current_index = self.time_limit_options.index(self.selected_time_limit)
        
        self.time_slider = self.time_selection_menu.add.range_slider(
            "",
            default=current_index,
            range_values=(0, len(self.time_limit_options) - 1),
            increment=1,
            value_format=lambda x: "",
            rangeslider_id="time_limit_slider",
            slider_text_value_enabled=False,
            onchange=self._on_time_limit_change_and_update_display
        )
        
        # Customize slider appearance
        self.time_slider.set_background_color((60, 60, 60, 200))
        
        self.time_selection_menu.add.vertical_margin(30)
        
        # Add time option labels below slider in a simple vertical layout
        time_labels = [self._format_time_display(time) for time in self.time_limit_options]
        current_index = self.time_limit_options.index(self.selected_time_limit)
                
        self.time_selection_menu.add.vertical_margin(40)
        
        # Add action buttons without frame to avoid sizing issues
        start_btn = self.time_selection_menu.add.button(
            "Start Game",
            self._start_limited_time_game,
            font_size=45,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            background_color=(240, 198, 38, 200),  # Gold
            padding=(15, 30)
        )
        
        # Store reference to time start button for special hover handling
        self.time_start_btn = start_btn
        
        # Make the Start Game button rounded (like difficulty buttons)
        def draw_rounded_time(widget, surface, *args, **kwargs):
            rect = widget.get_rect(to_real_position=True)
            color = widget._background_color if hasattr(widget, '_background_color') else (138, 43, 226, 200)
            border_radius = 18
            pygame.draw.rect(surface, color, rect, border_radius=border_radius)
            pygame.draw.rect(surface, (120, 120, 120, 180), rect, width=2, border_radius=border_radius)
            if hasattr(widget, 'get_title') and hasattr(widget, '_font'):
                text = widget.get_title()
                font = widget._font
                font_color = widget._font_color if hasattr(widget, '_font_color') else (255, 255, 255)
                text_surf = font.render(text, True, font_color)
                text_rect = text_surf.get_rect(center=rect.center)
                surface.blit(text_surf, text_rect)
        start_btn._original_draw = start_btn.draw
        start_btn.draw = lambda surface, *a, btn=start_btn, **k: draw_rounded_time(btn, surface, *a, **k)
        
        self.time_selection_menu.add.vertical_margin(10)
        
        back_btn = self.time_selection_menu.add.button(
            "Back",
            self._back_to_difficulty,
            font_size=45,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            padding=(15, 30)
        )
        
        # Apply custom styling to time selection menu
        self._customize_menu_widgets(self.time_selection_menu)
        
        # Apply hover effects to buttons
        self._apply_hover_effect(start_btn, False)
        self._apply_hover_effect(back_btn, False)
        
        # Create moves selection menu for limited moves mode
        self.moves_selection_menu = pygame_menu.Menu(
            "Select Move Limit",
            self.width,
            self.height,
            theme=self.sub_theme
        )
        
        # Add description
        self.moves_selection_menu.add.vertical_margin(20)
        self.moves_selection_menu.add.label(
            "Choose your move limit for the challenge:",
            font_size=45,
            font_color=(255, 255, 255),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        self.moves_selection_menu.add.vertical_margin(30)
        
        # Create moves display label
        self.moves_display_label = self.moves_selection_menu.add.label(
            f"Move Limit: {self.selected_move_limit} moves",
            font_size=45,
            font_color=(240, 198, 38),  # Golden color
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.moves_selection_menu.add.vertical_margin(20)
        
        # Add moves slider
        current_move_index = self.move_limit_options.index(self.selected_move_limit)
        
        self.moves_slider = self.moves_selection_menu.add.range_slider(
            "",
            default=current_move_index,
            range_values=(0, len(self.move_limit_options) - 1),
            increment=1,
            value_format=lambda x: "",
            rangeslider_id="move_limit_slider",
            slider_text_value_enabled=False,
            onchange=self._on_move_limit_change_and_update_display
        )
        
        # Customize slider appearance
        self.moves_slider.set_background_color((60, 60, 60, 200))
        
        self.moves_selection_menu.add.vertical_margin(40)
                
        self.moves_selection_menu.add.vertical_margin(40)
        
        # Add action buttons
        moves_start_btn = self.moves_selection_menu.add.button(
            "Start Game",
            self._start_limited_moves_game,
            font_size=45,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            background_color=(240, 198, 38, 200),  # Gold (matching limited moves theme)
            padding=(15, 30)
        )
        
        # Store reference to moves start button for special hover handling
        self.moves_start_btn = moves_start_btn
        
        # Make the Start Game button rounded (like difficulty buttons)
        def draw_rounded_moves(widget, surface, *args, **kwargs):
            rect = widget.get_rect(to_real_position=True)
            color = widget._background_color if hasattr(widget, '_background_color') else (255, 20, 147, 200)
            border_radius = 18
            pygame.draw.rect(surface, color, rect, border_radius=border_radius)
            pygame.draw.rect(surface, (120, 120, 120, 180), rect, width=2, border_radius=border_radius)
            if hasattr(widget, 'get_title') and hasattr(widget, '_font'):
                text = widget.get_title()
                font = widget._font
                font_color = widget._font_color if hasattr(widget, '_font_color') else (255, 255, 255)
                text_surf = font.render(text, True, font_color)
                text_rect = text_surf.get_rect(center=rect.center)
                surface.blit(text_surf, text_rect)
        moves_start_btn._original_draw = moves_start_btn.draw
        moves_start_btn.draw = lambda surface, *a, btn=moves_start_btn, **k: draw_rounded_moves(btn, surface, *a, **k)
        
        self.moves_selection_menu.add.vertical_margin(10)
        
        moves_back_btn = self.moves_selection_menu.add.button(
            "Back",
            self._back_to_difficulty,
            font_size=45,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            padding=(20, 40)
        )
        
        # Apply custom styling to moves selection menu
        self._customize_menu_widgets(self.moves_selection_menu)
        
        # Apply hover effects to buttons
        self._apply_hover_effect(moves_start_btn, False)
        self._apply_hover_effect(moves_back_btn, False)
        
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
            elif self.current_menu == self.personal_best_menu:
                self.current_menu = self.personal_best_menu
            elif self.current_menu == self.time_selection_menu:
                self.current_menu = self.time_selection_menu
            elif self.current_menu == self.moves_selection_menu:
                self.current_menu = self.moves_selection_menu
            elif self.current_menu == self.user_setup_menu:
                self.current_menu = self.user_setup_menu
            elif self.current_menu == self.user_edit_menu:
                self.current_menu = self.user_edit_menu
            elif self.current_menu == self.achievements_menu:
                self.current_menu = self.achievements_menu
            else:
                self.current_menu = self.main_menu
        else:
            self.current_menu = self.main_menu
    
    def _create_achievements_content(self):
        """Create or refresh achievements menu content with progress bars"""
        # Clear existing content except title
        widgets = self.achievements_menu.get_widgets()
        widgets_to_remove = []
        
        # Remove all widgets except the title (first widget)
        for i, widget in enumerate(widgets):
            if i > 0:  # Keep only the first widget (title)
                widgets_to_remove.append(widget)
        
        for widget in widgets_to_remove:
            self.achievements_menu.remove_widget(widget)
        
        # Get achievement data
        unlocked_count, total_count = self.achievements_manager.get_unlocked_count()
        achievements_by_category = self.achievements_manager.get_achievements_by_category()
        
        # Add header with overall progress
        self.achievements_menu.add.vertical_margin(15)
        
        # Overall progress display
        progress_pct = (unlocked_count / total_count * 100) if total_count > 0 else 0
        header_text = f"{unlocked_count} / {total_count} Achievements Unlocked ({progress_pct:.0f}%)"
        self.achievements_menu.add.label(
            header_text,
            font_size=36,
            font_color=(240, 198, 38),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.achievements_menu.add.vertical_margin(10)
        
        # Draw overall progress bar
        self._add_achievements_progress_bar(progress_pct / 100.0)
        
        self.achievements_menu.add.vertical_margin(25)
        
        # Category display order and names
        category_order = ["beginner", "progression", "speed", "challenge", "daily", "efficiency", "secret"]
        category_names = {
            "beginner": "Beginner",
            "progression": "Progression",
            "speed": "Speed",
            "challenge": "Challenges",
            "daily": "Daily",
            "efficiency": "Efficiency",
            "secret": "Secret"
        }
        
        # Display achievements by category
        for category in category_order:
            if category not in achievements_by_category:
                continue
            
            achievements = achievements_by_category[category]
            category_name = category_names.get(category, category.title())
            
            # Category header
            self.achievements_menu.add.label(
                category_name,
                font_size=55,
                font_color=(255, 180, 0),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            self.achievements_menu.add.vertical_margin(8)
            
            # Display each achievement in this category
            for achievement in achievements:
                self._add_achievement_widget(achievement)
            
            self.achievements_menu.add.vertical_margin(15)
        
        # Back button
        self.achievements_menu.add.vertical_margin(20)
        back_btn = self.achievements_menu.add.button("Back", self._back_to_main)
        
        # Apply custom styling
        self._customize_menu_widgets(self.achievements_menu)
    
    def _add_achievements_progress_bar(self, progress):
        """Add a visual progress bar to the achievements menu"""
        # Create a frame for the progress bar
        bar_width = 600
        bar_height = 25
        
        # We'll draw the progress bar as a label with special formatting
        filled_width = int(bar_width * progress)
        empty_width = bar_width - filled_width
        
        # Create visual representation using block characters
        filled_blocks = int(progress * 30)  # 30 blocks total
        empty_blocks = 30 - filled_blocks
        
        bar_text = "█" * filled_blocks + "░" * empty_blocks
        
        self.achievements_menu.add.label(
            bar_text,
            font_size=20,
            font_color=(240, 198, 38),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
    
    def _create_achievement_surface(self, achievement, width=750, height=110):
        """Create a surface with the achievement details in a box"""
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # Colors
        bg_color = (20, 30, 45, 180)  # Dark background
        border_color = (60, 70, 90)
        
        is_unlocked = achievement.get("unlocked", False)
        is_secret = achievement.get("secret", False)
        progress = achievement.get("progress", 0)
        target = achievement.get("target", 1)
        progress_pct = achievement.get("progress_percentage", 0)
        
        if is_unlocked:
            border_color = (240, 198, 38) # Gold border
            bg_color = (30, 40, 60, 220)
            
        # Draw box
        pygame.draw.rect(surface, bg_color, (0, 0, width, height), border_radius=8)
        pygame.draw.rect(surface, border_color, (0, 0, width, height), 2, border_radius=8)
        
        # Font Helper - Optimized with lazy loading
        if not hasattr(self, '_achievement_title_font'):
             try:
                self._achievement_title_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 42)
             except:
                self._achievement_title_font = pygame.font.SysFont("arial", 42)
        
        if not hasattr(self, '_achievement_desc_font'):
             try:
                self._achievement_desc_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 28)
             except:
                self._achievement_desc_font = pygame.font.SysFont("arial", 28)

        if not hasattr(self, '_achievement_status_font'):
             try:
                self._achievement_status_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 22)
             except:
                self._achievement_status_font = pygame.font.SysFont("arial", 22)

        # Content Logic
        icon_path = achievement.get("icon", "")
        name = achievement.get("name", "Unknown")
        description = achievement.get("description", "")
        
        if is_secret and not is_unlocked:
            name = "???"
            description = "This is a secret achievement"
            icon_path = ""
            
        name_color = (240, 198, 38) if is_unlocked else (180, 180, 180)
        desc_color = (200, 200, 200) if is_unlocked else (120, 120, 120)
        
        # Draw Icon (Left side, square based on height)
        padding = 10
        icon_size = height - (padding * 2)
        icon_rect = pygame.Rect(padding, padding, icon_size, icon_size)
        
        # Icon background/placeholder
        pygame.draw.rect(surface, (10, 10, 10, 100), icon_rect, border_radius=5)
        
        if icon_path:
            full_icon_path = resource_path(icon_path)
            if os.path.exists(full_icon_path):
                try:
                    icon_img = pygame.image.load(full_icon_path).convert_alpha()
                    icon_img = pygame.transform.smoothscale(icon_img, (icon_size, icon_size))
                    surface.blit(icon_img, icon_rect)
                except Exception as e:
                    print(f"Error loading icon: {e}")
        
        # Text Area (Right of icon)
        text_x = padding + icon_size + 20
        text_width = width - text_x - padding
        
        # Name
        name_surf = self._achievement_title_font.render(name, True, name_color)
        surface.blit(name_surf, (text_x, 10))
        
        # Description
        desc_surf = self._achievement_desc_font.render(description, True, desc_color)
        surface.blit(desc_surf, (text_x, 52))
        
        # Progress Bar or Unlocked Text
        bottom_y = height - 30
        
        if not is_unlocked and target > 1:
            # Draw progress bar
            bar_w = 250
            bar_h = 10
            
            # Background
            pygame.draw.rect(surface, (50, 50, 50), (text_x, bottom_y + 6, bar_w, bar_h), border_radius=5)
            # Fill
            fill_w = int(bar_w * progress_pct)
            if fill_w > 0:
                pygame.draw.rect(surface, (100, 180, 255), (text_x, bottom_y + 6, fill_w, bar_h), border_radius=5)
            
            # Text
            status_text = f"{progress}/{target}"
            status_surf = self._achievement_status_font.render(status_text, True, (150, 150, 150))
            surface.blit(status_surf, (text_x + bar_w + 12, bottom_y))
            
        elif is_unlocked:
             status_text = "UNLOCKED"
             status_surf = self._achievement_status_font.render(status_text, True, (100, 255, 100))
             surface.blit(status_surf, (text_x, bottom_y))

        return surface

    def _add_achievement_widget(self, achievement):
        """Add a single achievement widget with progress bar if applicable"""
        # Create custom surface for the achievement
        surf = self._create_achievement_surface(achievement)

        # Convert surface to BytesIO for pygame-menu
        image_bytes = BytesIO()
        pygame.image.save(surf, image_bytes, "PNG")
        image_bytes.seek(0)  # Reset pointer to start
        
        # Add surface to menu
        self.achievements_menu.add.image(
            image_bytes,
            align=ALIGN_CENTER,
            margin=(0, 5)
        )
        # Vertical margin already handled by margin(0,5) but maybe add explicit spacer
        # self.achievements_menu.add.vertical_margin(2)
    
    def _create_personal_best_content(self):
        """Create or refresh statistics menu content with tabs"""
        # Clear existing content except title
        widgets = self.personal_best_menu.get_widgets()
        widgets_to_remove = []
        
        # Remove all widgets except the title (first widget)
        for i, widget in enumerate(widgets):
            if i > 0:  # Keep only the first widget (title)
                widgets_to_remove.append(widget)
        
        for widget in widgets_to_remove:
            self.personal_best_menu.remove_widget(widget)
        
        # Add user info display at the top
        username = self.user_manager.get_username()
        region = self.user_manager.get_region()
        if username:
            self.personal_best_menu.add.vertical_margin(10)
            user_info_text = f"Player: {username}"
            if region:
                user_info_text += f"  |  Region: {region}"
            # Tab navigation buttons (side-by-side)
            self.personal_best_menu.add.vertical_margin(15)

            tab_frame = self.personal_best_menu.add.frame_h(
                width=1100,
                height=90,
                align=ALIGN_CENTER,
                margin=(0, 0)
            )
            # Suppress pack margin warnings (pygame-menu internal warning)
            tab_frame._pack_margin_warning = False

            pr_color = (240, 198, 38, 200) if self.statistics_tab == "personal_records" else (60, 60, 60, 180)
            pr_text_color = (255, 255, 255) if self.statistics_tab == "personal_records" else (160, 160, 160)
            personal_records_btn = tab_frame.pack(
                self.personal_best_menu.add.button(
                    "Personal Records",
                    self._switch_to_personal_records_tab,
                    font_size=26,
                    font_name=pygame_menu.font.FONT_FRANCHISE,
                    background_color=pr_color,
                    font_color=pr_text_color,
                    padding=(8, 20),
                    margin=(0, 0)
                ),
                align=ALIGN_CENTER,
                margin=(10, 0)
            )

            gl_color = (240, 198, 38, 200) if self.statistics_tab == "global_leaderboard" else (60, 60, 60, 180)
            gl_text_color = (255, 255, 255) if self.statistics_tab == "global_leaderboard" else (160, 160, 160)
            leaderboard_btn = tab_frame.pack(
                self.personal_best_menu.add.button(
                    "Global Leaderboard",
                    self._switch_to_leaderboard_tab,
                    font_size=26,
                    font_name=pygame_menu.font.FONT_FRANCHISE,
                    background_color=gl_color,
                    font_color=gl_text_color,
                    padding=(8, 20),
                    margin=(0, 0)
                ),
                align=ALIGN_CENTER,
                margin=(10, 0)
            )

            dl_color = (240, 198, 38, 200) if self.statistics_tab == "daily_leaderboard" else (60, 60, 60, 180)
            dl_text_color = (255, 255, 255) if self.statistics_tab == "daily_leaderboard" else (160, 160, 160)
            daily_leaderboard_btn = tab_frame.pack(
                self.personal_best_menu.add.button(
                    "Daily Leaderboard",
                    self._switch_to_daily_leaderboard_tab,
                    font_size=26,
                    font_name=pygame_menu.font.FONT_FRANCHISE,
                    background_color=dl_color,
                    font_color=dl_text_color,
                    padding=(8, 20),
                    margin=(0, 0)
                ),
                align=ALIGN_CENTER,
                margin=(10, 0)
            )

        self.personal_best_menu.add.vertical_margin(20)
        
        # Show content based on selected tab
        if self.statistics_tab == "personal_records":
            self._create_personal_records_content()
        elif self.statistics_tab == "global_leaderboard":
            self._create_leaderboard_content()
        else:  # daily_leaderboard
            self._create_daily_leaderboard_content()
        
        # Add spacing and back button
        self.personal_best_menu.add.vertical_margin(40)
        back_btn = self.personal_best_menu.add.button("Back", self._back_to_main)
        
        # Apply custom styling to statistics menu
        self._customize_menu_widgets(self.personal_best_menu)
        # Ensure the Back button gets hover/cursor styling
        self._apply_hover_effect(back_btn, False)
    
    def _create_personal_records_content(self):
        """Create personal records tab content"""
        # Check if there are any records
        has_any_records = self.personal_best_manager.has_records()
        
        if not has_any_records:
            # No records message
            self.personal_best_menu.add.vertical_margin(30)
            self.personal_best_menu.add.label(
                "No records yet!",
                font_size=45,
                font_color=(255, 215, 0),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            self.personal_best_menu.add.vertical_margin(20)
            self.personal_best_menu.add.label(
                "Complete a cube solve in any difficulty",
                font_size=32,
                font_color=(200, 200, 200),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            self.personal_best_menu.add.label(
                "to start tracking your personal bests!",
                font_size=32,
                font_color=(200, 200, 200),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
        else:
            # Display records in table format
            self.personal_best_menu.add.vertical_margin(10)
                        
            # Table column headers with separators
            header_row = "DIFFICULTY           │           BEST TIME           │          LEAST MOVES          │     SOLVES"
            self.personal_best_menu.add.label(
                header_row,
                font_size=45,
                font_color=(255, 255, 255),  # Brighter white for headers
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            
            # Separator line
            separator = "=" * 95  # Adjusted for even wider spacing
            self.personal_best_menu.add.label(
                separator,
                font_size=30,  # Increased font size for better visibility
                font_color=(200, 200, 200),  # Brighter color for better visibility
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            self.personal_best_menu.add.vertical_margin(5)
            
            # Table data rows
            difficulties = ["easy", "medium", "hard"]
            difficulty_names = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
            difficulty_colors = {
                "easy": (33, 148, 33),      # Green
                "medium": (199, 106, 26),   # Orange  
                "hard": (176, 28, 28)       # Red
            }
            
            for difficulty in difficulties:
                records = self.personal_best_manager.get_records(difficulty)
                
                # Format the data for each column
                diff_name = difficulty_names[difficulty]
                
                if records["best_time"] is not None:
                    best_time = f"{records['best_time']:.3f}s"
                else:
                    best_time = "---"
                
                if records["best_moves"] is not None:
                    best_moves = f"{records['best_moves']}"
                else:
                    best_moves = "---"
                
                total_solves = records["total_solves"]
                
                # Create aligned row with even wider spacing to match headers
                data_row = f"{diff_name:<21}│{best_time:^36}│{best_moves:^40}│{total_solves:^35}"
                
                # Add row with difficulty color
                self.personal_best_menu.add.label(
                    data_row,
                    font_size=45,
                    font_color=difficulty_colors[difficulty] if records["total_solves"] > 0 else (100, 100, 100),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
            
            # Challenge Modes Win/Loss Table
            self.personal_best_menu.add.vertical_margin(30)
            
            # Check if there are any challenge mode records
            has_challenge_records = (
                self.personal_best_manager.get_wins("limited_time") > 0 or 
                self.personal_best_manager.get_losses("limited_time") > 0 or
                self.personal_best_manager.get_wins("limited_moves") > 0 or 
                self.personal_best_manager.get_losses("limited_moves") > 0
            )
            
            if has_challenge_records:
                # Challenge modes title
                self.personal_best_menu.add.label(
                    "CHALLENGE MODES STATISTICS",
                    font_size=50,
                    font_color=(255, 215, 0),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                
                self.personal_best_menu.add.vertical_margin(20)
                
                # Challenge table headers
                challenge_header = "MODE                    │        WINS       │       LOSSES      │      WIN RATE"
                self.personal_best_menu.add.label(
                    challenge_header,
                    font_size=40,
                    font_color=(255, 255, 255),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                
                # Challenge separator line
                challenge_separator = "=" * 85
                self.personal_best_menu.add.label(
                    challenge_separator,
                    font_size=25,
                    font_color=(200, 200, 200),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                
                self.personal_best_menu.add.vertical_margin(5)
                
                # Challenge modes data
                challenge_modes = ["limited_time", "limited_moves"]
                challenge_names = {"limited_time": "Limited Time", "limited_moves": "Limited Moves"}
                challenge_colors = {
                    "limited_time": (255, 255, 255),   # White
                    "limited_moves": (255, 255, 255)   # White
                }
                
                for mode in challenge_modes:
                    wins = self.personal_best_manager.get_wins(mode)
                    losses = self.personal_best_manager.get_losses(mode)
                    win_rate = self.personal_best_manager.get_win_rate(mode)
                    
                    # Only show modes that have been played
                    if wins > 0 or losses > 0:
                        mode_name = challenge_names[mode]
                        win_rate_str = f"{win_rate:.1f}%" if win_rate > 0 else "0.0%"
                        
                        # Create aligned row
                        challenge_row = f"{mode_name:<24}│{wins:^19}│{losses:^19}│{win_rate_str:^19}"
                        
                        # Add row with mode color
                        self.personal_best_menu.add.label(
                            challenge_row,
                            font_size=40,
                            font_color=challenge_colors[mode],
                            font_name=pygame_menu.font.FONT_FRANCHISE
                        )
        
            # Overall statistics
            self.personal_best_menu.add.vertical_margin(20)
            total_solves = self.personal_best_manager.get_total_solves()
            if total_solves > 0:
                self.personal_best_menu.add.label(
                    f"Total Solves: {total_solves}",
                    font_size=40,
                    font_color=(255, 215, 0),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
    
    def _create_leaderboard_content(self):
        """Create global leaderboard tab content with filters and data display."""
        
        # Check if Supabase is configured
        if not self.supabase_manager or not self.supabase_manager.is_configured():
            self.personal_best_menu.add.vertical_margin(50)
            self.personal_best_menu.add.label(
                "Global Leaderboard",
                font_size=50,
                font_color=(255, 215, 0),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            self.personal_best_menu.add.vertical_margin(30)
            self.personal_best_menu.add.label(
                "Leaderboard Not Configured",
                font_size=40,
                font_color=(200, 200, 200),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            self.personal_best_menu.add.vertical_margin(20)
            self.personal_best_menu.add.label(
                "Please configure Supabase credentials in supabase_manager.py",
                font_size=24,
                font_color=(150, 150, 150),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Filter section - using simple vertical layout with labels
        self.personal_best_menu.add.vertical_margin(5)
        
        # Filter label
        self.personal_best_menu.add.label(
            "FILTERS",
            font_size=28,
            font_color=(200, 200, 200),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.personal_best_menu.add.vertical_margin(5)
        
        # Game mode filter dropdown
        mode_items = [(GAME_MODE_DISPLAY.get(mode, mode), i) for i, mode in enumerate(GAME_MODE_OPTIONS)]
        current_mode_index = GAME_MODE_OPTIONS.index(self.leaderboard_filter_mode) if self.leaderboard_filter_mode in GAME_MODE_OPTIONS else 0
        
        self.personal_best_menu.add.dropselect(
            "Game Mode:  ",
            mode_items,
            default=current_mode_index,
            font_size=26,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            onchange=self._on_leaderboard_mode_filter_change,
            selection_box_height=6,
            selection_box_width=200,
            margin=(0, 5)
        )
        
        # Region filter dropdown
        region_items = [(region, i) for i, region in enumerate(REGION_OPTIONS)]
        current_region_index = REGION_OPTIONS.index(self.leaderboard_filter_region) if self.leaderboard_filter_region in REGION_OPTIONS else 0
        
        self.personal_best_menu.add.dropselect(
            "Region:  ",
            region_items,
            default=current_region_index,
            font_size=26,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            onchange=self._on_leaderboard_region_filter_change,
            selection_box_height=6,
            selection_box_width=180,
            margin=(0, 5)
        )
        
        # Refresh button
        self.personal_best_menu.add.vertical_margin(5)
        refresh_btn = self.personal_best_menu.add.button(
            "⟳ Refresh Leaderboard",
            self._refresh_leaderboard,
            font_size=26,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            background_color=(60, 80, 100, 180),
            padding=(8, 20),
            margin=(0, 5)
        )
        self._apply_hover_effect(refresh_btn, False)
        
        self.personal_best_menu.add.vertical_margin(10)
        
        # Separator
        self.personal_best_menu.add.label(
            "─" * 60,
            font_size=20,
            font_color=(100, 100, 100),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.personal_best_menu.add.vertical_margin(5)
        
        # Loading state
        if self.leaderboard_loading:
            self.personal_best_menu.add.vertical_margin(30)
            self.personal_best_menu.add.label(
                "Loading leaderboard...",
                font_size=35,
                font_color=(200, 200, 200),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Error state
        if self.leaderboard_error:
            self.personal_best_menu.add.vertical_margin(30)
            self.personal_best_menu.add.label(
                self.leaderboard_error,
                font_size=35,
                font_color=(255, 100, 100),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Empty state - distinguish between offline and no records
        if not self.leaderboard_data:
            self.personal_best_menu.add.vertical_margin(30)
            
            if self.leaderboard_is_offline:
                # Offline state - no internet connection
                self.personal_best_menu.add.label(
                    "⚠ No Internet Connection",
                    font_size=40,
                    font_color=(255, 165, 0),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                self.personal_best_menu.add.vertical_margin(15)
                self.personal_best_menu.add.label(
                    "Online features are unavailable",
                    font_size=28,
                    font_color=(200, 150, 100),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                self.personal_best_menu.add.vertical_margin(10)
                self.personal_best_menu.add.label(
                    "Please check your internet connection and try again",
                    font_size=24,
                    font_color=(150, 150, 150),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
            else:
                # Actually no records found
                self.personal_best_menu.add.label(
                    "No records found",
                    font_size=40,
                    font_color=(200, 200, 200),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                self.personal_best_menu.add.vertical_margin(15)
                self.personal_best_menu.add.label(
                    "Be the first to set a record!",
                    font_size=28,
                    font_color=(150, 150, 150),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Table header
        if self.leaderboard_filter_mode == "All Modes":
            header_row = "RANK │      PLAYER      │   REGION   │    MODE    │   BEST TIME   │  MOVES"
        else:
            header_row = "RANK │        PLAYER        │     REGION     │   BEST TIME   │  MOVES  │  SOLVES"
        
        self.personal_best_menu.add.label(
            header_row,
            font_size=28,
            font_color=(255, 255, 255),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        # Separator line
        separator = "=" * 85
        self.personal_best_menu.add.label(
            separator,
            font_size=20,
            font_color=(200, 200, 200),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        # Display leaderboard entries
        current_username = self.user_manager.get_username() if self.user_manager else ""
        
        for rank, entry in enumerate(self.leaderboard_data[:20], 1):  # Limit to 20 entries
            username = entry.get("username", "Unknown")[:12]  # Truncate long names
            region = entry.get("region", "N/A")[:10]
            game_mode = entry.get("game_mode", "N/A")
            best_time = entry.get("best_time")
            best_moves = entry.get("best_moves")
            total_solves = entry.get("total_solves", 0)
            
            # Format time
            if best_time is not None:
                if best_time < 60:
                    time_str = f"{best_time:.2f}s"
                else:
                    mins = int(best_time // 60)
                    secs = best_time % 60
                    time_str = f"{mins}:{secs:05.2f}"
            else:
                time_str = "---"
            
            # Format moves
            moves_str = str(best_moves) if best_moves is not None else "---"
            
            # Get display mode name
            mode_display = GAME_MODE_DISPLAY.get(game_mode, game_mode)[:10]
            
            # Create row based on filter
            if self.leaderboard_filter_mode == "All Modes":
                row = f"{rank:^5}│{username:^18}│{region:^12}│{mode_display:^12}│{time_str:^15}│{moves_str:^8}"
            else:
                row = f"{rank:^5}│{username:^22}│{region:^16}│{time_str:^15}│{moves_str:^9}│{total_solves:^9}"
            
            # Determine row color
            if username == current_username:
                # Highlight current user's entries
                row_color = (240, 198, 38)  # Gold
            elif rank == 1:
                row_color = (255, 215, 0)  # Gold for #1
            elif rank == 2:
                row_color = (192, 192, 192)  # Silver for #2
            elif rank == 3:
                row_color = (205, 127, 50)  # Bronze for #3
            else:
                row_color = (200, 200, 200)  # Default gray
            
            self.personal_best_menu.add.label(
                row,
                font_size=26,
                font_color=row_color,
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
        
        # Show total entries count if there are more
        if len(self.leaderboard_data) > 20:
            self.personal_best_menu.add.vertical_margin(10)
            self.personal_best_menu.add.label(
                f"Showing top 20 of {len(self.leaderboard_data)} entries",
                font_size=22,
                font_color=(150, 150, 150),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
    
    def _create_daily_leaderboard_content(self):
        """Create daily leaderboard tab content with today's date and rankings."""
        from datetime import datetime, timezone
        
        # Check if Supabase is configured
        if not self.supabase_manager or not self.supabase_manager.is_configured():
            self.personal_best_menu.add.vertical_margin(50)
            self.personal_best_menu.add.label(
                "Daily Leaderboard",
                font_size=50,
                font_color=(255, 215, 0),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            self.personal_best_menu.add.vertical_margin(30)
            self.personal_best_menu.add.label(
                "Leaderboard Not Configured",
                font_size=40,
                font_color=(200, 200, 200),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Display today's date
        utc_now = datetime.now(timezone.utc)
        date_str = utc_now.strftime("%B %d, %Y")  # e.g., "January 19, 2026"
        
        self.personal_best_menu.add.vertical_margin(5)
        self.personal_best_menu.add.label(
            f"📅 Today's Daily Cube - {date_str} (UTC)",
            font_size=32,
            font_color=(255, 215, 0),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.personal_best_menu.add.vertical_margin(10)
        
        # Filter section - region only for daily leaderboard
        self.personal_best_menu.add.label(
            "FILTER",
            font_size=24,
            font_color=(200, 200, 200),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.personal_best_menu.add.vertical_margin(5)
        
        # Region filter dropdown
        region_items = [(region, i) for i, region in enumerate(REGION_OPTIONS)]
        current_region_index = REGION_OPTIONS.index(self.daily_leaderboard_filter_region) if self.daily_leaderboard_filter_region in REGION_OPTIONS else 0
        
        self.personal_best_menu.add.dropselect(
            "Region:  ",
            region_items,
            default=current_region_index,
            font_size=24,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            onchange=self._on_daily_leaderboard_region_filter_change,
            selection_box_height=6,
            selection_box_width=180,
            margin=(0, 5)
        )
        
        # Refresh button
        self.personal_best_menu.add.vertical_margin(5)
        refresh_btn = self.personal_best_menu.add.button(
            "⟳ Refresh",
            self._refresh_daily_leaderboard,
            font_size=24,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            background_color=(60, 80, 100, 180),
            padding=(6, 15),
            margin=(0, 5)
        )
        self._apply_hover_effect(refresh_btn, False)
        
        self.personal_best_menu.add.vertical_margin(10)
        
        # Separator
        self.personal_best_menu.add.label(
            "─" * 60,
            font_size=18,
            font_color=(100, 100, 100),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.personal_best_menu.add.vertical_margin(5)
        
        # Loading state
        if self.daily_leaderboard_loading:
            self.personal_best_menu.add.vertical_margin(30)
            self.personal_best_menu.add.label(
                "Loading daily leaderboard...",
                font_size=32,
                font_color=(200, 200, 200),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Error state
        if self.daily_leaderboard_error:
            self.personal_best_menu.add.vertical_margin(30)
            self.personal_best_menu.add.label(
                self.daily_leaderboard_error,
                font_size=32,
                font_color=(255, 100, 100),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Empty state - distinguish between offline and no records
        if not self.daily_leaderboard_data:
            self.personal_best_menu.add.vertical_margin(30)
            
            if self.daily_leaderboard_is_offline:
                # Offline state - no internet connection
                self.personal_best_menu.add.label(
                    "⚠ No Internet Connection",
                    font_size=40,
                    font_color=(255, 165, 0),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                self.personal_best_menu.add.vertical_margin(15)
                self.personal_best_menu.add.label(
                    "Online features are unavailable",
                    font_size=28,
                    font_color=(200, 150, 100),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                self.personal_best_menu.add.vertical_margin(10)
                self.personal_best_menu.add.label(
                    "Please check your internet connection and try again",
                    font_size=24,
                    font_color=(150, 150, 150),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
            else:
                # Actually no records found
                self.personal_best_menu.add.label(
                    "No one has completed today's Daily Cube yet!",
                    font_size=36,
                    font_color=(200, 200, 200),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                self.personal_best_menu.add.vertical_margin(15)
                self.personal_best_menu.add.label(
                    "Be the first to set a record!",
                    font_size=26,
                    font_color=(150, 150, 150),
                    font_name=pygame_menu.font.FONT_FRANCHISE
                )
                self.personal_best_menu.add.vertical_margin(10)
                self.personal_best_menu.add.label(
                    "Play 'Daily Cube' mode to compete!",
                    font_size=24,
                    font_color=(240, 198, 38),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
            return
        
        # Table header
        header_row = "RANK │        PLAYER        │     REGION     │   SOLVE TIME   │  MOVES  │   TPS"
        
        self.personal_best_menu.add.label(
            header_row,
            font_size=26,
            font_color=(255, 255, 255),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        # Separator line
        separator = "=" * 85
        self.personal_best_menu.add.label(
            separator,
            font_size=18,
            font_color=(200, 200, 200),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        # Display daily leaderboard entries
        current_username = self.user_manager.get_username() if self.user_manager else ""
        
        for rank, entry in enumerate(self.daily_leaderboard_data[:20], 1):  # Limit to 20 entries
            username = entry.get("username", "Unknown")[:12]  # Truncate long names
            region = entry.get("region", "N/A")[:10]
            solve_time = entry.get("solve_time")
            moves = entry.get("moves")
            tps = entry.get("tps")
            
            # Format time
            if solve_time is not None:
                if solve_time < 60:
                    time_str = f"{solve_time:.2f}s"
                else:
                    mins = int(solve_time // 60)
                    secs = solve_time % 60
                    time_str = f"{mins}:{secs:05.2f}"
            else:
                time_str = "---"
            
            # Format moves
            moves_str = str(moves) if moves is not None else "---"
            
            # Format TPS
            tps_str = f"{tps:.2f}" if tps is not None else "---"
            
            # Create row
            row = f"{rank:^5}│{username:^22}│{region:^16}│{time_str:^16}│{moves_str:^9}│{tps_str:^8}"
            
            # Determine row color
            if username == current_username:
                # Highlight current user's entries
                row_color = (240, 198, 38)  # Gold
            elif rank == 1:
                row_color = (255, 215, 0)  # Gold for #1
            elif rank == 2:
                row_color = (192, 192, 192)  # Silver for #2
            elif rank == 3:
                row_color = (205, 127, 50)  # Bronze for #3
            else:
                row_color = (200, 200, 200)  # Default gray
            
            self.personal_best_menu.add.label(
                row,
                font_size=24,
                font_color=row_color,
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
        
        # Show total entries count if there are more
        if len(self.daily_leaderboard_data) > 20:
            self.personal_best_menu.add.vertical_margin(10)
            self.personal_best_menu.add.label(
                f"Showing top 20 of {len(self.daily_leaderboard_data)} entries",
                font_size=20,
                font_color=(150, 150, 150),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
    
    def _create_user_setup_content(self):
        """Create user setup dialog content for first-time users"""
        # Clear existing content except title
        widgets = self.user_setup_menu.get_widgets()
        widgets_to_remove = []
        for i, widget in enumerate(widgets):
            if i > 0:
                widgets_to_remove.append(widget)
        for widget in widgets_to_remove:
            self.user_setup_menu.remove_widget(widget)
        
        self.user_setup_menu.add.vertical_margin(30)
        self.user_setup_menu.add.label(
            "Please set up your profile",
            font_size=45,
            font_color=(255, 255, 255),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.user_setup_menu.add.vertical_margin(30)
        
        # Username input - clickable text field for keyboard input
        self.username_input = self.user_setup_menu.add.text_input(
            "Enter Username: ",
            default=self.user_setup_username,
            maxchar=20,
            font_size=32,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            input_underline="_",
            onchange=self._on_username_change,
            textinput_id="username_input",
            password=False,
            copy_paste_enable=True
        )
        # Make text input more visible
        self.username_input.set_background_color((40, 40, 60, 200))
        
        # Show username error if any
        if self.username_error:
            self.user_setup_menu.add.vertical_margin(10)
            self.user_setup_menu.add.label(
                self.username_error,
                font_size=28,
                font_color=(255, 100, 100),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
        
        self.user_setup_menu.add.vertical_margin(30)
        
        # Region selection
        self.user_setup_menu.add.label(
            "Region:",
            font_size=35,
            font_color=(200, 200, 200),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        region_items = [(region, i) for i, region in enumerate(REGIONS)]
        self.region_selector = self.user_setup_menu.add.dropselect(
            "",
            region_items,
            default=self.user_setup_region_index,
            font_size=35,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            onchange=self._on_region_change,
            selection_box_height=5
        )
        
        self.user_setup_menu.add.vertical_margin(50)
        
        # Confirm button
        confirm_btn = self.user_setup_menu.add.button(
            "Confirm",
            self._confirm_user_setup,
            font_size=45,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            background_color=(46, 125, 50, 200),
            padding=(15, 40)
        )
        
        self.user_setup_menu.add.vertical_margin(20)
        
        # Back button
        back_btn = self.user_setup_menu.add.button(
            "Back",
            self._back_from_user_setup,
            font_size=45,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            background_color=(211, 47, 47, 200),
            padding=(15, 40)
        )
        
        # Apply custom styling
        self._customize_menu_widgets(self.user_setup_menu)
        self._apply_hover_effect(confirm_btn, False)
        self._apply_hover_effect(back_btn, False)
        
        # Set the text input as selected and focused to enable keyboard input
        try:
            self.user_setup_menu.enable()
            self.user_setup_menu.select_widget(self.username_input)
            # Force focus the text input
            if hasattr(self.username_input, 'set_selected'):
                self.username_input.set_selected(True)
        except Exception as e:
            print(f"Error focusing text input: {e}")
    
    def _create_user_edit_content(self):
        """Create user edit dialog content"""
        # Clear existing content except title
        widgets = self.user_edit_menu.get_widgets()
        widgets_to_remove = []
        for i, widget in enumerate(widgets):
            if i > 0:
                widgets_to_remove.append(widget)
        for widget in widgets_to_remove:
            self.user_edit_menu.remove_widget(widget)
        
        self.user_edit_menu.add.vertical_margin(30)
        self.user_edit_menu.add.label(
            "Edit your profile",
            font_size=45,
            font_color=(255, 255, 255),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        self.user_edit_menu.add.vertical_margin(30)
        
        # Username input - clickable text field for keyboard input
        self.edit_username_input = self.user_edit_menu.add.text_input(
            "Enter Username: ",
            default=self.user_setup_username,
            maxchar=20,
            font_size=32,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            input_underline="_",
            onchange=self._on_edit_username_change,
            textinput_id="edit_username_input",
            password=False,
            copy_paste_enable=True
        )
        # Make text input more visible
        self.edit_username_input.set_background_color((40, 40, 60, 200))
        
        # Show username error if any
        if self.username_error:
            self.user_edit_menu.add.vertical_margin(10)
            self.user_edit_menu.add.label(
                self.username_error,
                font_size=28,
                font_color=(255, 100, 100),
                font_name=pygame_menu.font.FONT_FRANCHISE
            )
        
        self.user_edit_menu.add.vertical_margin(30)
        
        # Region selection
        self.user_edit_menu.add.label(
            "Region:",
            font_size=35,
            font_color=(200, 200, 200),
            font_name=pygame_menu.font.FONT_FRANCHISE
        )
        
        region_items = [(region, i) for i, region in enumerate(REGIONS)]
        self.edit_region_selector = self.user_edit_menu.add.dropselect(
            "",
            region_items,
            default=self.user_setup_region_index,
            font_size=35,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            onchange=self._on_edit_region_change,
            selection_box_height=5
        )
        
        self.user_edit_menu.add.vertical_margin(50)
        
        # Save button
        save_btn = self.user_edit_menu.add.button(
            "Save Changes",
            self._save_user_edit,
            font_size=45,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            background_color=(46, 125, 50, 200),
            padding=(15, 40)
        )
        
        self.user_edit_menu.add.vertical_margin(15)
        
        # Back button
        back_btn = self.user_edit_menu.add.button(
            "Cancel",
            self._back_to_statistics,
            font_size=40,
            font_name=pygame_menu.font.FONT_FRANCHISE,
            padding=(10, 30)
        )
        
        # Apply custom styling
        self._customize_menu_widgets(self.user_edit_menu)
        self._apply_hover_effect(save_btn, False)
        self._apply_hover_effect(back_btn, False)
        
        # Set the text input as selected and focused to enable keyboard input
        try:
            self.user_edit_menu.enable()
            self.user_edit_menu.select_widget(self.edit_username_input)
            # Force focus the text input
            if hasattr(self.edit_username_input, 'set_selected'):
                self.edit_username_input.set_selected(True)
        except Exception as e:
            print(f"Error focusing edit text input: {e}")
    
    def _on_username_change(self, value):
        """Handle username input change"""
        self.user_setup_username = value
    
    def _on_region_change(self, selected_tuple, index):
        """Handle region selection change"""
        self.sound_manager.play("menu_select")
        if isinstance(selected_tuple, tuple) and len(selected_tuple) > 1:
            self.user_setup_region_index = selected_tuple[1]
        else:
            self.user_setup_region_index = index
    
    def _on_edit_username_change(self, value):
        """Handle username input change in edit mode"""
        self.user_setup_username = value
    
    def _on_edit_region_change(self, selected_tuple, index):
        """Handle region selection change in edit mode"""
        self.sound_manager.play("menu_select")
        if isinstance(selected_tuple, tuple) and len(selected_tuple) > 1:
            self.user_setup_region_index = selected_tuple[1]
        else:
            self.user_setup_region_index = index
    
    def _confirm_user_setup(self):
        """Confirm user setup and save data"""
        username = self.user_setup_username.strip()
        if not username:
            # Show error - username required
            self.username_error = "Username is required"
            self._create_user_setup_content()
            return
        
        # Check if username is already taken
        if self.supabase_manager and self.supabase_manager.is_configured():
            if self.supabase_manager.is_username_taken(username):
                self.username_error = "Username is already in use. Please choose a different one."
                self.sound_manager.play("menu_select")  # Play feedback sound
                self._create_user_setup_content()
                return
        
        self.username_error = None
        region = REGIONS[self.user_setup_region_index]
        self.user_manager.complete_setup(username, region)
        self.sound_manager.play("menu_apply")
        self.user_setup_active = False
        
        # Initialize Supabase user hash for cloud sync (uses stable user_id)
        if self.supabase_manager and self.supabase_manager.is_configured():
            self.supabase_manager.set_user_hash(
                self.user_manager.get_user_id(),
                self.user_manager.user_data.get("created_at", "")
            )
            # Sync any existing records to cloud
            if self.personal_best_manager:
                self.personal_best_manager.sync_all_to_cloud()
        
        # After setup, go directly to difficulty selection
        self.current_menu = self.difficulty_menu
    
    def _save_user_edit(self):
        """Save user edit changes"""
        username = self.user_setup_username.strip()
        if not username:
            self.username_error = "Username is required"
            self._create_user_edit_content()
            return
        
        # Check if username is already taken by another user
        if self.supabase_manager and self.supabase_manager.is_configured():
            # Exclude current user's hash when checking
            current_user_hash = self.supabase_manager.get_user_hash()
            if self.supabase_manager.is_username_taken(username, exclude_user_hash=current_user_hash):
                self.username_error = "Username is already in use. Please choose a different one."
                self.sound_manager.play("menu_select")  # Play feedback sound
                self._create_user_edit_content()
                return
        
        self.username_error = None
        region = REGIONS[self.user_setup_region_index]
        
        # Update existing records in Supabase BEFORE changing local data
        # This ensures the records keep the same user_hash but get the new username/region
        if self.supabase_manager and self.supabase_manager.is_configured():
            # Update all existing records with new username and region
            self.supabase_manager.update_user_profile(username, region)
        
        # Now update local user data
        self.user_manager.update_user(username, region)
        self.sound_manager.play("menu_apply")
        
        # Note: We do NOT change the user_hash when editing profile
        # The user_hash remains the same so existing records stay linked to this user
        # We also don't need to re-sync since we already updated the records above
        
        self._open_personal_best()  # Go back to statistics
    
    def _back_to_statistics(self):
        """Go back to statistics menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()
        self._create_personal_best_content()
        self._change_menu(self.personal_best_menu)
    
    def needs_user_setup(self) -> bool:
        """Check if user setup is needed"""
        return not self.user_manager.is_setup_completed()
    
    def show_user_setup(self):
        """Show the user setup dialog"""
        self.user_setup_active = True
        self.user_setup_username = ""
        self.user_setup_region_index = 0
        self.username_error = None  # Clear any previous error
        self._create_user_setup_content()
        self._change_menu(self.user_setup_menu)
        
        # Ensure the text input is selected and focused for keyboard input
        try:
            # Force the menu to become active first
            self.user_setup_menu.enable()
            # Then select the text input widget
            self.user_setup_menu.select_widget(self.username_input)
            # Also clear any existing text and set cursor position
            if hasattr(self.username_input, 'clear'):
                self.username_input.clear()
        except Exception as e:
            print(f"Error selecting text input: {e}")    
    def _back_from_user_setup(self):
        """Go back from user setup screen to main menu"""
        self.sound_manager.play("menu_select")
        self._clear_all_hover_effects()
        self.user_setup_active = False
        self._change_menu(self.main_menu)