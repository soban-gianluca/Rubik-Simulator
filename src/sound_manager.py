import os
import pygame
import time
import random

class SoundManager:
    """Manages sound effects for the game"""
    
    def __init__(self):
        """Initialize sound manager and load sound effects"""
        self.sounds = {}
        self.is_enabled = True
        self.last_play_time = {}  # Track last play time for each sound
        self.min_interval = 0.1  # Minimum interval between same sound plays (100ms)
        
        # Volume settings (0.0 to 1.0)
        self.master_volume = 1.0
        self.music_volume = 1.0
        self.effects_volume = 1.0
        self.menu_volume = 1.0
        
        # Check if pygame mixer is initialized
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(44100, -16, 2, 1024)
                print("Pygame mixer initialized")
            except Exception as e:
                print(f"Error initializing pygame mixer: {e}")
                self.is_enabled = False
        
        # Create sound effects directory if it doesn't exist
        sfx_dir = os.path.join("utils", "sfx")
        if not os.path.exists(sfx_dir):
            print("Error: Sound effects directory does not exist.")
        
        # Load sound effects
        try:
            self.sounds["menu_open"] = pygame.mixer.Sound(os.path.join(sfx_dir, "menu", "menu_open.mp3"))
            self.sounds["menu_select"] = pygame.mixer.Sound(os.path.join(sfx_dir, "menu", "menu_select.mp3"))
            self.sounds["menu_apply"] = pygame.mixer.Sound(os.path.join(sfx_dir, "menu", "menu_close.mp3"))
            
            # Load cube movement sound effects
            cube_sfx_dir = os.path.join(sfx_dir, "cube_sfx")
            self.cube_sounds = []
            for i in range(1, 7):  # Load cube_sfx_1.mp3 to cube_sfx_6.mp3
                cube_sound_path = os.path.join(cube_sfx_dir, f"cube_sfx_{i}.mp3")
                if os.path.exists(cube_sound_path):
                    cube_sound = pygame.mixer.Sound(cube_sound_path)
                    cube_sound.set_volume(0.4 * self.effects_volume * self.master_volume)  # Set moderate volume for cube sounds
                    self.cube_sounds.append(cube_sound)
            
            # Set default volumes based on sound type
            self.sounds["menu_open"].set_volume(0.5 * self.menu_volume * self.master_volume)
            self.sounds["menu_select"].set_volume(0.3 * self.menu_volume * self.master_volume)
            self.sounds["menu_apply"].set_volume(0.4 * self.menu_volume * self.master_volume)
            
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
        
    def test_sounds(self):
        """Test if sounds are working"""
        print("Testing sound effects...")
        for sound_name in self.sounds:
            print(f"Playing {sound_name}...")
            self.play(sound_name)
            pygame.time.delay(500)  # Wait half a second between sounds
