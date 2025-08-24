import os
import pygame
import time
import random
from utils.path_helper import resource_path

class SoundManager:
    """Manages sound effects for the game"""
    
    def __init__(self):
        """Initialize sound manager and load sound effects"""
        self.sounds = {}
        self.is_enabled = True
        self.last_play_time = {}  # Track last play time for each sound
        self.min_interval = 0.1
        
        # Volume settings (0.0 to 1.0)
        self.master_volume = 1.0
        self.music_volume = 1.0
        self.effects_volume = 1.0
        self.menu_volume = 1.0
        
        # Music ducking settings
        self.original_music_volume = None
        self.is_music_ducked = False
        self.duck_volume_ratio = 0.3  # Reduce music to 30% when ducking
        self.duck_fade_duration = 200  # 200ms fade time
        
        # Music fade-in settings
        self.is_fading_in = False
        self.fade_start_time = None
        self.fade_in_duration = 2.0  # 2 seconds fade-in duration
        self.fade_target_volume = None
        
        # Check if pygame mixer is initialized
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(44100, -16, 2, 1024)
                print("Pygame mixer initialized")
            except Exception as e:
                print(f"Error initializing pygame mixer: {e}")
                self.is_enabled = False
        
        # Create sound effects directory if it doesn't exist
        sfx_dir = resource_path("utils/sfx")
        if not os.path.exists(sfx_dir):
            print("Error: Sound effects directory does not exist.")
        
        # Load sound effects
        try:
            self.sounds["menu_open"] = pygame.mixer.Sound(resource_path("utils/sfx/menu/menu_open.mp3"))
            self.sounds["menu_select"] = pygame.mixer.Sound(resource_path("utils/sfx/menu/menu_select.mp3"))
            self.sounds["menu_apply"] = pygame.mixer.Sound(resource_path("utils/sfx/menu/menu_close.mp3"))
            
            # Load winning sound effect
            self.sounds["winning"] = pygame.mixer.Sound(resource_path("utils/sfx/winning_screen/winningSFX.mp3"))

            # Load cube movement sound effects
            cube_sfx_dir = resource_path("utils/sfx/cube_sfx")
            self.cube_sounds = []
            for i in range(1, 7):  # Load cube_sfx_1.mp3 to cube_sfx_6.mp3
                cube_sound_path = resource_path(f"utils/sfx/cube_sfx/cube_sfx_{i}.mp3")
                if os.path.exists(cube_sound_path):
                    cube_sound = pygame.mixer.Sound(cube_sound_path)
                    cube_sound.set_volume(0.4 * self.effects_volume * self.master_volume)  # Set moderate volume for cube sounds
                    self.cube_sounds.append(cube_sound)

            # Set default volumes based on sound type
            self.sounds["menu_open"].set_volume(0.5 * self.menu_volume * self.master_volume)
            self.sounds["menu_select"].set_volume(0.3 * self.menu_volume * self.master_volume)
            self.sounds["menu_apply"].set_volume(0.4 * self.menu_volume * self.master_volume)
            self.sounds["winning"].set_volume(1 * self.effects_volume * self.master_volume)

        except Exception as e:
            print(f"Error loading sound effects: {e}")
            self.is_enabled = False
    
    def play(self, sound_name):
        """Play a sound effect by name if enabled and not played too recently"""
        if not self.is_enabled or sound_name not in self.sounds:
            return False
            
        # Check if enough time has passed since last play
        current_time = time.time()
        if sound_name in self.last_play_time:
            time_since_last = current_time - self.last_play_time[sound_name]
            if time_since_last < self.min_interval:
                return False  # Too soon, don't play
        
        try:
            self.sounds[sound_name].play()
            self.last_play_time[sound_name] = current_time
            return True
        except Exception as e:
            print(f"Error playing sound {sound_name}: {e}")
            return False
    
    def play_slider_sound(self, sound_name):
        """Play a sound effect for sliders with longer debounce (500ms)"""
        if not self.is_enabled or sound_name not in self.sounds:
            return False
            
        # Check if enough time has passed since last play (longer interval for sliders)
        current_time = time.time()
        slider_interval = 0.5  # 500ms for sliders
        if sound_name in self.last_play_time:
            time_since_last = current_time - self.last_play_time[sound_name]
            if time_since_last < slider_interval:
                return False  # Too soon, don't play
        
        try:
            self.sounds[sound_name].play()
            self.last_play_time[sound_name] = current_time
            return True
        except Exception as e:
            print(f"Error playing slider sound {sound_name}: {e}")
            return False
    
    def play_random_cube_sound(self):
        """Play a random cube movement sound effect"""
        if not self.is_enabled or not hasattr(self, 'cube_sounds') or not self.cube_sounds:
            return False
            
        # Check if enough time has passed since last cube sound (shorter interval for cube sounds)
        current_time = time.time()
        cube_interval = 0.05  # 50ms minimum interval between cube sounds
        if 'cube_sound' in self.last_play_time:
            time_since_last = current_time - self.last_play_time['cube_sound']
            if time_since_last < cube_interval:
                return False  # Too soon, don't play
        
        try:
            # Select and play a random cube sound
            random_sound = random.choice(self.cube_sounds)
            random_sound.play()
            self.last_play_time['cube_sound'] = current_time
            return True
        except Exception as e:
            print(f"Error playing random cube sound: {e}")
            return False
    
    def set_volume(self, volume):
        """Set volume for all sound effects (0.0 to 1.0) - for backward compatibility"""
        self.set_master_volume(volume)
    
    def set_master_volume(self, volume):
        """Set master volume for all sounds (0.0 to 1.0)"""
        self.master_volume = max(0.0, min(1.0, volume))
        self._update_all_volumes()
    
    def set_music_volume(self, volume):
        """Set music volume (0.0 to 1.0)"""
        self.music_volume = max(0.0, min(1.0, volume))
        # Apply to pygame music
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
    
    def set_effects_volume(self, volume):
        """Set effects volume (0.0 to 1.0)"""
        self.effects_volume = max(0.0, min(1.0, volume))
        self._update_cube_volumes()
    
    def set_menu_volume(self, volume):
        """Set menu volume (0.0 to 1.0)"""
        self.menu_volume = max(0.0, min(1.0, volume))
        self._update_menu_volumes()
    
    def _update_all_volumes(self):
        """Update all sound volumes based on current settings"""
        self._update_menu_volumes()
        self._update_cube_volumes()
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.music_volume * self.master_volume)
    
    def _update_menu_volumes(self):
        """Update menu sound volumes"""
        if self.is_enabled and hasattr(self, 'sounds'):
            menu_sounds = {
                "menu_open": 0.5,
                "menu_select": 0.3,
                "menu_apply": 0.4
            }
            for sound_name, base_volume in menu_sounds.items():
                if sound_name in self.sounds:
                    self.sounds[sound_name].set_volume(base_volume * self.menu_volume * self.master_volume)
    
    def _update_cube_volumes(self):
        """Update cube sound effects volumes"""
        if self.is_enabled and hasattr(self, 'cube_sounds') and self.cube_sounds:
            for cube_sound in self.cube_sounds:
                cube_sound.set_volume(0.4 * self.effects_volume * self.master_volume)
        
        # Update winning sound volume
        if self.is_enabled and hasattr(self, 'sounds') and "winning" in self.sounds:
            self.sounds["winning"].set_volume(0.7 * self.effects_volume * self.master_volume)
    
    def enable(self, enabled=True):
        """Enable or disable sound effects"""
        self.is_enabled = enabled
    
    def load_volumes_from_settings(self, settings_manager):
        """Load volume settings from settings manager"""
        self.master_volume = settings_manager.get_master_volume() / 100.0
        self.music_volume = settings_manager.get_music_volume() / 100.0
        self.effects_volume = settings_manager.get_effects_volume() / 100.0
        self.menu_volume = settings_manager.get_menu_volume() / 100.0
        self._update_all_volumes()
    
    def duck_music(self):
        """Temporarily lower the music volume for important sound effects"""
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy() and not self.is_music_ducked:
            self.original_music_volume = pygame.mixer.music.get_volume()
            target_volume = self.original_music_volume * self.duck_volume_ratio
            pygame.mixer.music.set_volume(target_volume)
            self.is_music_ducked = True
    
    def restore_music_volume(self):
        """Start fading the music volume back to original level after ducking"""
        if pygame.mixer.get_init() and self.is_music_ducked and self.original_music_volume is not None:
            # Start fade-in process instead of instant restore
            self.fade_target_volume = self.original_music_volume
            self.fade_start_time = time.time()
            self.is_fading_in = True
            # Set initial volume to ducked level
            current_ducked_volume = self.original_music_volume * self.duck_volume_ratio
            pygame.mixer.music.set_volume(current_ducked_volume)
            
            # Reset ducking state but keep fade state active
            self.is_music_ducked = False
    
    def update_music_fade(self):
        """Update the music fade-in process - should be called regularly in game loop"""
        if not self.is_fading_in or self.fade_start_time is None:
            return
        
        current_time = time.time()
        elapsed_time = current_time - self.fade_start_time
        
        if elapsed_time >= self.fade_in_duration:
            # Fade complete - set final volume and clean up
            if pygame.mixer.get_init() and self.fade_target_volume is not None:
                pygame.mixer.music.set_volume(self.fade_target_volume)
            self._finish_fade_in()
        else:
            # Calculate current fade volume using smooth easing
            fade_progress = elapsed_time / self.fade_in_duration
            # Apply easing function for smoother fade (ease-out curve)
            eased_progress = 1 - (1 - fade_progress) ** 2
            
            if pygame.mixer.get_init() and self.fade_target_volume is not None:
                # Calculate volume between ducked level and target
                ducked_volume = self.fade_target_volume * self.duck_volume_ratio
                current_volume = ducked_volume + (self.fade_target_volume - ducked_volume) * eased_progress
                pygame.mixer.music.set_volume(current_volume)
    
    def _finish_fade_in(self):
        """Clean up after fade-in is complete"""
        self.is_fading_in = False
        self.fade_start_time = None
        self.fade_target_volume = None
        self.original_music_volume = None
    
    def play_with_music_duck(self, sound_name, duck_duration=None):
        """Play a sound effect with music ducking and automatic restore"""
        if not self.is_enabled or sound_name not in self.sounds:
            return False
        
        # Check if enough time has passed since last play
        current_time = time.time()
        if sound_name in self.last_play_time:
            time_since_last = current_time - self.last_play_time[sound_name]
            if time_since_last < self.min_interval:
                return False  # Too soon, don't play
        
        try:
            # Duck the music first
            self.duck_music()
            
            # Play the sound
            sound_channel = self.sounds[sound_name].play()
            self.last_play_time[sound_name] = current_time
            
            # Calculate restore time based on sound duration or provided duration
            if duck_duration is None and sound_channel:
                # Get the sound duration and add a small buffer
                sound_length = self.sounds[sound_name].get_length()
                duck_duration = sound_length + 0.5  # Add 500ms buffer
            elif duck_duration is None:
                duck_duration = 3.0  # Default 3 seconds if we can't get sound length
            
            # Schedule music volume restore using pygame's timer
            # Use USEREVENT + 10 which should match MUSIC_RESTORE_EVENT in game.py
            pygame.time.set_timer(pygame.USEREVENT + 10, int(duck_duration * 1000))
            return True
            
        except Exception as e:
            print(f"Error playing sound with music duck {sound_name}: {e}")
            # Make sure to restore music even if sound fails
            self.restore_music_volume()
            return False
        
    def test_sounds(self):
        """Test if sounds are working"""
        print("Testing sound effects...")
        for sound_name in self.sounds:
            print(f"Playing {sound_name}...")
            self.play(sound_name)
            pygame.time.delay(500)  # Wait half a second between sounds
