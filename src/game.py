import pygame
import sys
import math
from renderer import Renderer

class Game:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rubik's Cube Simulator")
        self.clock = pygame.time.Clock()
        
        icon = pygame.image.load("utils/rubiksCube_Icon.ico")
        pygame.display.set_icon(icon)

        # Initialize renderer
        self.renderer = Renderer(self.width, self.height)
        
        # Game state
        self.running = True
        self.auto_rotate = True  # Auto rotation by default
        
        # Mouse rotation variables
        self.mouse_rotating = False
        self.prev_mouse_x = 0
        self.prev_mouse_y = 0
        self.rotation_sensitivity = 0.5  # Sensitivity for horizontal rotation
        self.vertical_sensitivity = 0.5  # Sensitivity for vertical rotation
        self.debug_mode = True  # Set to False to disable debug prints
        
        # Print instructions
        print("Controls:")
        print("  Space: Toggle auto-rotation")
        print("  Left/Right arrows: Manual rotation")
        print("  Click and drag: Rotate cube with mouse")
        print("  ESC: Quit")

    def debug_print(self, message):
        if self.debug_mode:
            print(message)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                # Quit
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.auto_rotate = not self.auto_rotate
                    self.debug_print(f"Auto-rotate: {'ON' if self.auto_rotate else 'OFF'}")
        
            # Handle mouse events for rotation
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    self.mouse_rotating = True
                    self.prev_mouse_x, self.prev_mouse_y = event.pos
                    # Disable auto-rotation when manually rotating
                    self.auto_rotate = False
                    self.debug_print(f"Mouse rotation started at {event.pos}")
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left mouse button
                    self.mouse_rotating = False
                    self.debug_print("Mouse rotation ended")
                
            elif event.type == pygame.MOUSEMOTION:
                if self.mouse_rotating:
                    # Calculate the mouse movement delta
                    current_x, current_y = event.pos
                    dx = current_x - self.prev_mouse_x
                    dy = current_y - self.prev_mouse_y
                    
                    # Apply horizontal and vertical rotations
                    horizontal_rotation = -dx * self.rotation_sensitivity
                    vertical_rotation = dy * self.vertical_sensitivity
                    
                    # Update the camera
                    self.renderer.rotate_camera(
                        azimuth=horizontal_rotation, 
                        elevation=vertical_rotation
                    )
                    
                    self.debug_print(f"Rotating: dx={dx}, dy={dy}, h={horizontal_rotation}, v={vertical_rotation}")
                    
                    # Update previous position
                    self.prev_mouse_x = current_x
                    self.prev_mouse_y = current_y
    
        # Handle key presses for manual rotation (outside the event loop for smoother response)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.renderer.rotate_camera(azimuth=1)
            self.auto_rotate = False
        if keys[pygame.K_RIGHT]:
            self.renderer.rotate_camera(azimuth=-1)
            self.auto_rotate = False
        if keys[pygame.K_UP]:
            self.renderer.rotate_camera(elevation=-1)
            self.auto_rotate = False
        if keys[pygame.K_DOWN]:
            self.renderer.rotate_camera(elevation=1)
            self.auto_rotate = False

    def update(self):
        # Auto-rotate if enabled
        if self.auto_rotate:
            self.renderer.rotate_camera(azimuth=0.5)
        
    def render(self):
        # Render the cube
        pygame_image = self.renderer.render_frame()
        self.screen.blit(pygame_image, (0, 0))
        
        # Add indicator for mouse rotation state
        if self.mouse_rotating:
            pygame.draw.circle(self.screen, (255, 0, 0), (20, 20), 10)  # Red dot when rotating
            
        pygame.display.flip()
        
    def run(self):
        # Main game loop
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)  # 60 FPS
            
        # Clean up
        self.renderer.close()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Game()
    game.run()