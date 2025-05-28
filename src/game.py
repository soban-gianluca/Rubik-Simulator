import pygame
import sys
from menu import Menu
from renderer import Renderer

class Game:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rubik's Cube Simulator")
        self.clock = pygame.time.Clock()
        
        # Load playback music
        """ pygame.mixer.music.load("utils/rubiksCube_Playback.mp3")
        pygame.mixer.music.set_volume(1)
        pygame.mixer.music.play(-1) """
        
        # Load icon
        icon = pygame.image.load("utils/rubiksCube_Icon.ico")
        pygame.display.set_icon(icon)

        # Initialize renderer
        self.renderer = Renderer(self.width, self.height)
        
        # Initialize menu (enabled by default)
        self.menu = Menu(self.width, self.height)
        self.menu.toggle()  # Start with menu active
        
        # Game state
        self.running = True
        self.auto_rotate = False
        self.auto_rotate = True  # Auto rotation by default
        
        # Mouse rotation variables
        self.mouse_rotating = False
        self.prev_mouse_x = 0
        self.prev_mouse_y = 0
        self.rotation_sensitivity = 0.5
        self.vertical_sensitivity = 0.5
        self.debug_mode = False
        
        # Print instructions
        print("Controls:")
        print("  Space: Toggle auto-rotation")
        print("  Left/Right arrows: Manual rotation")
        print("  Click and drag: Rotate cube with mouse")
        print("  D: Toggle debug mode")
        print("  ESC: Toggle menu")

    def debug_print(self, message):
        if self.debug_mode:
            print(message)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            # Handle ESC key to toggle menu
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.menu.toggle()
                    self.debug_print(f"Menu: {'ON' if self.menu.is_active() else 'OFF'}")
                elif not self.menu.is_active() and event.key == pygame.K_SPACE:
                    self.auto_rotate = not self.auto_rotate
                    self.debug_print(f"Auto-rotate: {'ON' if self.auto_rotate else 'OFF'}")
                elif not self.menu.is_active() and event.key == pygame.K_d:
                    self.debug_mode = not self.debug_mode
            
            # Pass event to menu first
            elif self.menu.handle_event(event):
                continue  # Event was handled by menu
                
            # Handle mouse events for rotation (only when not in menu)
            elif not self.menu.is_active() and event.type == pygame.MOUSEBUTTONDOWN:
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
                
            elif not self.menu.is_active() and event.type == pygame.MOUSEMOTION:
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
        if not self.menu.is_active():
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
        # Auto-rotate if enabled and not in menu
        if not self.menu.is_active() and self.auto_rotate:
            self.renderer.rotate_camera(azimuth=0.5)
    
    def render(self):
        # Render the cube
        pygame_image = self.renderer.render_frame()
        self.screen.blit(pygame_image, (0, 0))
        
        # Add indicator for mouse rotation state
        if self.mouse_rotating:
            pygame.draw.circle(self.screen, (255, 0, 0), (20, 20), 10)  # Red dot when rotating
        
        # Draw menu if active
        self.menu.draw(self.screen)
            
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