import pygame
import math
import time
import threading

""" Puts the application in the taskbar with a custom icon on Windows."""
import ctypes
myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

class LoadingAnimation:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.SysFont('Arial', 55, bold=True)
        self.font_medium = pygame.font.SysFont('Arial', 30)
        
        # Loading state
        self.loading_complete = False
        self.min_display_time = 3.0  # Minimum time to show animation in seconds
        
        # Set caption and icon
        pygame.display.set_caption("Rubik's Cube Simulator")
        
        # Load cube icon for animation
        try:
            self.cube_icon = pygame.image.load("utils/rubiksCube_Icon.ico")
            self.cube_icon = pygame.transform.scale(self.cube_icon, (100, 100))
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
        
    def preload_game_resources(self):
        """Preload game resources in background thread"""
        # Import here to avoid circular imports
        from game import Game
        
        # Simulate resource loading
        for i in range(10):
            self.loading_progress = (i + 1) / 10
            time.sleep(0.5)
        
        time.sleep(0.5)
        self.loading_complete = True
        
    def update(self):
        # Calculate elapsed time
        elapsed = time.time() - self.start_time
        
        # Check if we can exit the animation
        can_exit = (self.loading_complete and elapsed >= self.min_display_time)
        
        # If loading is done but min time hasn't passed, adjust animation to slow down
        if self.loading_complete and not can_exit:
            # Slow down rotation speed in final phase
            self.rotation += 1.0
        else:
            # Normal rotation speed during loading
            self.rotation += 2.0
            
        # Scale effect (breathing animation)
        pulse = (math.sin(elapsed * 2) + 1) / 4 + 0.75  # Range 0.75-1.25
        self.scale_factor = pulse
            
        # Fade in only (no fade out)
        if elapsed < 0.5:
            self.alpha = int(255 * (elapsed / 0.5))  # Fade in during first 0.5 seconds
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
        # Clear screen with black
        self.screen.fill((0, 0, 0))
        
        # Create a surface for the rotating cube
        if self.cube_icon:
            # Get the original dimensions
            orig_width, orig_height = self.cube_icon.get_rect().size
            
            # Calculate new dimensions with scale factor
            new_width = int(orig_width * self.scale_factor)
            new_height = int(orig_height * self.scale_factor)
            
            # Scale the image
            scaled_icon = pygame.transform.scale(self.cube_icon, (new_width, new_height))
            
            # Rotate the image
            rotated_icon = pygame.transform.rotate(scaled_icon, self.rotation)
            
            # Calculate position to center
            icon_rect = rotated_icon.get_rect(center=(self.width // 2, self.height // 2 - 50))
            
            # Create a surface with per-pixel alpha for fade effect
            alpha_surface = pygame.Surface(rotated_icon.get_size(), pygame.SRCALPHA)
            alpha_surface.fill((255, 255, 255, self.alpha))
            rotated_icon.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            # Draw the rotating cube
            self.screen.blit(rotated_icon, icon_rect)
        else:
            # Fallback if icon not available
            # Draw a rotating square
            size = 100 * self.scale_factor
            rect = pygame.Rect(0, 0, size, size)
            rect.center = (self.width // 2, self.height // 2 - 50)
            
            # Calculate rotated points
            center = rect.center
            points = []
            for i in range(4):
                angle = math.radians(45 + i * 90 + self.rotation)
                radius = size / 2 * 1.414  # sqrt(2) to reach the corners
                x = center[0] + radius * math.cos(angle)
                y = center[1] + radius * math.sin(angle)
                points.append((x, y))
            
            # Draw square with alpha
            square_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.polygon(square_surface, (255, 255, 255, self.alpha), points)
            self.screen.blit(square_surface, (0, 0))
        
        # Draw text with fade effect
        title = self.font_large.render("Rubik's Cube Simulator", True, (255, 255, 255))
        title.set_alpha(self.alpha)
        title_rect = title.get_rect(center=(self.width // 2, self.height // 2 + 50))
        self.screen.blit(title, title_rect)
        
        # Draw loading text with progress
        if self.loading_complete:
            loading_text = self.font_medium.render("Ready to start...", True, (200, 200, 200))
        else:
            loading_text = self.font_medium.render(f"Loading... {int(self.loading_progress * 100)}%", True, (200, 200, 200))
        
        loading_text.set_alpha(self.alpha)
        loading_rect = loading_text.get_rect(center=(self.width // 2, self.height // 2 + 100))
        self.screen.blit(loading_text, loading_rect)
        
        # Draw loading bar
        bar_width = 300
        bar_height = 10
        bar_x = (self.width - bar_width) // 2
        bar_y = self.height // 2 + 130
        
        # Background bar (empty)
        pygame.draw.rect(self.screen, (70, 70, 70), (bar_x, bar_y, bar_width, bar_height))
        
        # Filled portion
        filled_width = int(bar_width * self.loading_progress)
        pygame.draw.rect(self.screen, (0, 200, 100), (bar_x, bar_y, filled_width, bar_height))
        
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