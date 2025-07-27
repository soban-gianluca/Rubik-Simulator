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
                    cube_sound.set_volume(0.4)  # Set moderate volume for cube sounds
                    self.cube_sounds.append(cube_sound)
            
            # Set default volumes
            self.sounds["menu_open"].set_volume(0.5)
            self.sounds["menu_select"].set_volume(0.3)
            self.sounds["menu_apply"].set_volume(0.4)
            
            print(f"Sound effects loaded successfully ({len(self.cube_sounds)} cube sounds)")
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
        """Set volume for all sound effects (0.0 to 1.0)"""
        if self.is_enabled:
            for sound in self.sounds.values():
                sound.set_volume(volume)
            # Also set volume for cube sounds
            if hasattr(self, 'cube_sounds') and self.cube_sounds:
                for cube_sound in self.cube_sounds:
                    cube_sound.set_volume(volume * 0.4)  # Keep cube sounds slightly quieter
    
    def enable(self, enabled=True):
        """Enable or disable sound effects"""
        self.is_enabled = enabled
        
    def test_sounds(self):
        """Test if sounds are working"""
        print("Testing sound effects...")
        for sound_name in self.sounds:
            print(f"Playing {sound_name}...")
            self.play(sound_name)
            pygame.time.delay(500)  # Wait half a second between sounds
