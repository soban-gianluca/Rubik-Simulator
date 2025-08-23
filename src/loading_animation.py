import pygame
import pygame_menu
import math
import time
import threading
from pygame.locals import *
from OpenGL.GL import *
from utils.path_helper import resource_path
import random
from src.settings_manager import SettingsManager

""" Puts the application in the taskbar with a custom icon on Windows."""
import ctypes
myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

class LoadingAnimation:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        
        # Create OpenGL context from the start to match what Game expects
        display_flags = DOUBLEBUF | OPENGL
        self.screen = pygame.display.set_mode((screen_width, screen_height), display_flags)
        
        # Set up OpenGL for 2D rendering
        glViewport(0, 0, screen_width, screen_height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, screen_width, screen_height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Enable alpha blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        
        self.clock = pygame.time.Clock()
        
        # Use the same font as the menu (FONT_FRANCHISE)
        franchise_font_path = pygame_menu.font.FONT_FRANCHISE
        try:
            self.font_large = pygame.font.Font(franchise_font_path, 70)
            self.font_medium = pygame.font.Font(franchise_font_path, 40)
            self.font_small = pygame.font.Font(franchise_font_path, 30)
        except:
            # Fallback to system font if franchise font fails to load
            print("Could not load franchise font, using Arial fallback")
            self.font_large = pygame.font.SysFont('Arial', 70, bold=True)
            self.font_medium = pygame.font.SysFont('Arial', 40)
            self.font_small = pygame.font.SysFont('Arial', 30)
        
        # Loading state
        self.loading_complete = False
        self.min_display_time = 4.0  # Minimum time to show animation in seconds
        
        # Set caption and icon
        pygame.display.set_caption("Rubik's Cube Simulator")
        
        # Load cube icon for animation
        try:
            self.cube_icon = pygame.image.load(resource_path("utils/rubiksCube_Icon.ico"))
            self.cube_icon = pygame.transform.scale(self.cube_icon, (120, 120))
            pygame.display.set_icon(self.cube_icon)
        except:
            print("Icon not found, using placeholder")
            self.cube_icon = None
        
        # Animation parameters
        self.rotation = 0
        self.scale_factor = 1.0
        self.alpha = 0  # For fade in/out
        self.start_time = time.time()
        self.loading_progress = 0.0  # 0.0 to 1.0
        self.current_step = 0
        
        # Loading steps with descriptions
        self.loading_steps = [
            "Initializing OpenGL...",
            "Loading cube model...",
            "Loading textures...",
            "Loading sound effects...",
            "Loading soundtrack...",
            "Setting up renderer...",
            "Preparing game engine...",
            "Finalizing setup...",
            "Ready to play!"
        ]

        # --- Start background music for loading animation ---
        try:
            settings = SettingsManager()
            playlist = [
                resource_path("utils/soundtrack/dark_bar.mp3"),
                resource_path("utils/soundtrack/lounge_layers.mp3"),
                resource_path("utils/soundtrack/midnight_simmetry.mp3"),
                resource_path("utils/soundtrack/the_fifth_color.mp3")
            ]
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            # Only start music if not already playing
            if not pygame.mixer.music.get_busy():
                volume_level = settings.get_music_volume() / 100 * settings.get_master_volume() / 100
                pygame.mixer.music.set_volume(volume_level)
                song = random.choice(playlist)
                pygame.mixer.music.load(song)
                pygame.mixer.music.play(-1)  # Loop during loading
        except Exception as e:
            print(f"Loading screen music error: {e}")
        
    def preload_game_resources(self):
        """Preload game resources in background thread"""
        # Import here to avoid circular imports
        from src.game import Game
        
        # Simulate resource loading with detailed steps
        total_steps = len(self.loading_steps) - 1  # -1 because last step is "Ready to play!"
        
        for i in range(total_steps):
            self.current_step = i
            self.loading_progress = (i + 1) / total_steps
            
            # Simulate different loading times for different steps
            if i == 0:  # OpenGL initialization
                time.sleep(0.7)
            elif i in [1, 2]:  # Model and textures
                time.sleep(0.6)
            elif i in [3, 4]:  # Sound loading
                time.sleep(0.5)
            else:  # Other steps
                time.sleep(0.4)
        
        # Final step
        self.current_step = total_steps
        self.loading_progress = 1.0
        time.sleep(0.8)
        self.loading_complete = True
        
    def update(self):
        # Calculate elapsed time
        elapsed = time.time() - self.start_time
        
        # Check if we can exit the animation
        can_exit = (self.loading_complete and elapsed >= self.min_display_time)
        
        # If loading is done but min time hasn't passed, adjust animation to slow down
        if self.loading_complete and not can_exit:
            # Slow down rotation speed in final phase
            self.rotation += 1.5
        else:
            # Faster rotation speed during loading for more dynamic feel
            self.rotation += 3.0
            
        # Scale effect (gentle breathing animation)
        pulse = (math.sin(elapsed * 1.5) + 1) / 8 + 0.9  # Range 0.9-1.1 for subtle effect
        self.scale_factor = pulse
            
        # Fade in only (no fade out)
        if elapsed < 0.8:
            self.alpha = int(255 * (elapsed / 0.8))  # Fade in during first 0.8 seconds
        else:
            self.alpha = 255  # Fully visible
            
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
                
        return not can_exit  # Continue until loading complete and min time passed
    
    def render(self):
        # Clear OpenGL buffer
        glClear(GL_COLOR_BUFFER_BIT)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        
        # Create a pygame surface for 2D rendering, then convert to OpenGL
        temp_surface = pygame.Surface((self.width, self.height))
        temp_surface.fill((0, 0, 0))
        
        # Draw gradient lines on pygame surface
        for y in range(0, self.height, 4):
            color_value = int(5 + (y / self.height) * 15)
            pygame.draw.line(temp_surface, (color_value, color_value, color_value + 3), (0, y), (self.width, y))
        
        # Draw spinning cube icon on pygame surface
        if self.cube_icon:
            # Get the original dimensions
            orig_width, orig_height = self.cube_icon.get_rect().size
            
            # Calculate new dimensions with scale factor
            new_width = int(orig_width * self.scale_factor)
            new_height = int(orig_height * self.scale_factor)
            
            # Scale and rotate the image
            scaled_icon = pygame.transform.scale(self.cube_icon, (new_width, new_height))
            rotated_icon = pygame.transform.rotate(scaled_icon, self.rotation)
            
            # Apply alpha
            alpha_surface = pygame.Surface(rotated_icon.get_size(), pygame.SRCALPHA)
            alpha_surface.fill((255, 255, 255, self.alpha))
            rotated_icon.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            # Calculate position to center in upper portion
            icon_rect = rotated_icon.get_rect(center=(self.width // 2, self.height // 2 - 80))
            temp_surface.blit(rotated_icon, icon_rect)
        
        # Draw main title on pygame surface
        title = self.font_large.render("Rubik's Cube Simulator", True, (255, 255, 255))
        title.set_alpha(self.alpha)
        title_rect = title.get_rect(center=(self.width // 2, self.height // 2 + 30))
        temp_surface.blit(title, title_rect)
        
        # Draw current loading step on pygame surface
        if self.current_step < len(self.loading_steps):
            step_text = self.loading_steps[self.current_step]
            loading_text = self.font_medium.render(step_text, True, (200, 220, 255))
            loading_text.set_alpha(self.alpha)
            loading_rect = loading_text.get_rect(center=(self.width // 2, self.height // 2 + 80))
            temp_surface.blit(loading_text, loading_rect)
        
        # Draw progress percentage on pygame surface
        progress_percent = f"{int(self.loading_progress * 100)}%"
        percent_text = self.font_small.render(progress_percent, True, (150, 200, 150))
        percent_text.set_alpha(self.alpha)
        percent_rect = percent_text.get_rect(center=(self.width // 2, self.height // 2 + 115))
        temp_surface.blit(percent_text, percent_rect)
        
        # Draw enhanced progress bar on pygame surface
        bar_width = 400
        bar_height = 16
        bar_x = (self.width - bar_width) // 2
        bar_y = self.height // 2 + 135
        
        # Draw progress bar background with border
        border_color = (80, 80, 100)
        bg_color = (40, 40, 50)
        pygame.draw.rect(temp_surface, border_color, (bar_x - 2, bar_y - 2, bar_width + 4, bar_height + 4))
        pygame.draw.rect(temp_surface, bg_color, (bar_x, bar_y, bar_width, bar_height))
        
        # Draw progress fill with gradient effect
        filled_width = int(bar_width * self.loading_progress)
        if filled_width > 0:
            # Create gradient progress bar
            for i in range(filled_width):
                progress_ratio = i / bar_width
                # Color gradient from blue to green
                r = int(50 + progress_ratio * 100)
                g = int(150 + progress_ratio * 50)
                b = int(255 - progress_ratio * 100)
                
                pygame.draw.line(temp_surface, (r, g, b), 
                               (bar_x + i, bar_y), (bar_x + i, bar_y + bar_height))
        
        # Convert pygame surface to OpenGL texture and render
        # Set up 2D orthographic projection
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Disable depth testing for 2D rendering
        glDisable(GL_DEPTH_TEST)
        
        # Convert pygame surface to OpenGL texture
        texture_data = pygame.image.tostring(temp_surface, 'RGBA', True)
        
        # Render the texture
        glRasterPos2f(0, self.height)
        glDrawPixels(self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        
        # Restore OpenGL state
        glEnable(GL_DEPTH_TEST)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        
        # Update display
        pygame.display.flip()
        self.clock.tick(60)
    
    def run(self):
        # Start background loading thread
        loading_thread = threading.Thread(target=self.preload_game_resources)
        loading_thread.daemon = True  # Thread will exit when main program exits
        loading_thread.start()
        
        # Run animation until completion
        while self.update():
            self.render()
        
        # Wait for loading to complete if animation finished first
        while not self.loading_complete:
            # Keep rendering but with "Finishing loading..." message
            self.render()
            
        return True  # Animation completed successfully