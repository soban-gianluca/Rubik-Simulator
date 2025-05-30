import pygame
import sys
from menu import Menu
from renderer import Renderer

class Game:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        self.width, self.height = 1024, 768     # Default resolution    (precedente: 800, 600)    
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rubik's Cube Simulator")
        self.clock = pygame.time.Clock()
        
        # Load playback music
        pygame.mixer.music.load("utils/rubiksCube_Playback.mp3")
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)
        
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
        self.auto_rotate = True  # Auto rotation by default
        
        # Mouse rotation variables
        self.mouse_rotating = False
        self.prev_mouse_x = 0
        self.prev_mouse_y = 0
        self.rotation_sensitivity = 0.5
        self.vertical_sensitivity = 0.5
        self.debug_mode = False
        
        # Display settings
        self.is_fullscreen = False
        self.show_fps = False

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

    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode with proper resolution handling"""
        if self.is_fullscreen:
            # Switch back to windowed mode with original resolution
            self.screen = pygame.display.set_mode((self.width, self.height))
            
            # Update the renderer for windowed mode
            if hasattr(self, 'renderer'):
                self.renderer.close()
                self.renderer = Renderer(self.width, self.height)
        else:
            # Get the current display info to use native resolution
            display_info = pygame.display.Info()
            fullscreen_width = display_info.current_w
            fullscreen_height = display_info.current_h
            
            # Switch to fullscreen with native resolution
            self.screen = pygame.display.set_mode((fullscreen_width, fullscreen_height), pygame.FULLSCREEN)
            
            # Update the renderer for fullscreen
            if hasattr(self, 'renderer'):
                self.renderer.close()
                self.renderer = Renderer(fullscreen_width, fullscreen_height)
                
            self.debug_print(f"Switched to fullscreen: {fullscreen_width}x{fullscreen_height}")
        
        self.is_fullscreen = not self.is_fullscreen
        
        # Force a redraw
        self.renderer.render_frame()
    
    def change_resolution(self, width, height):
        """Actually change the screen resolution"""
        # Store current settings
        current_volume = self.menu.volume if hasattr(self, 'menu') else 50
        current_settings = {}
        if hasattr(self, 'menu'):
            for key in self.menu.settings_options.keys():
                current_settings[key] = self.menu.get_setting(key)
            current_display_mode = self.menu.current_display_mode

        # Update dimensions
        self.width = width
        self.height = height

        # Update display mode based on fullscreen setting
        is_fullscreen = False
        if hasattr(self, 'menu'):
            is_fullscreen = self.menu.get_setting('fullscreen')

        if is_fullscreen:
            self.screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
            self.is_fullscreen = True
        else:
            self.screen = pygame.display.set_mode((width, height))
            self.is_fullscreen = False

        # Update the renderer with the new resolution
        if hasattr(self, 'renderer'):
            # Close the old renderer to release resources
            self.renderer.close()
            # Create a new renderer with updated dimensions
            self.renderer = Renderer(width, height)

        # Recreate menu with new dimensions and restore settings
        if hasattr(self, 'menu'):
            # Create new menu with correct dimensions
            self.menu = Menu(width, height)
    
            # Restore settings
            self.menu.volume = current_volume
            self.menu._update_volume_handle()
    
            if 'current_display_mode' in locals():
                self.menu.current_display_mode = current_display_mode
    
            for key, value in current_settings.items():
                if key in self.menu.settings_options:
                    self.menu.settings_options[key]['value'] = value

        # Only print if debug mode is active
        self.debug_print(f"Resolution changed to {width}x{height}")

        return True
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            # Handle ESC key to toggle menu
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    menu_was_active = self.menu.is_active()
                    self.menu.toggle()
                    # Reset cursor to default if exiting menu
                    if menu_was_active:
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                    self.debug_print(f"Menu: {'ON' if self.menu.is_active() else 'OFF'}")
                elif not self.menu.is_active() and event.key == pygame.K_SPACE:
                    self.auto_rotate = not self.auto_rotate
                    self.debug_print(f"Auto-rotate: {'ON' if self.auto_rotate else 'OFF'}")
                elif not self.menu.is_active() and event.key == pygame.K_d:
                    self.debug_mode = not self.debug_mode
                    self.debug_print(f"Debug mode: {'ON' if self.debug_mode else 'OFF'}")
                elif event.key == pygame.K_F11:  # Add F11 as alternate fullscreen toggle
                    self.toggle_fullscreen()
            
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
                if event.button == 1 and not self.menu.is_active():  # Left mouse button
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
        """Update game state"""
        # Check and apply settings from menu when resolution changed flag is true
        if hasattr(self, 'menu') and self.menu.resolution_changed():
            # Get selected resolution
            new_width, new_height = self.menu.get_current_resolution()
            current_width, current_height = self.width, self.height
            
            # Check if resolution has actually changed
            if (new_width, new_height) != (current_width, current_height):
                self.debug_print(f"Changing resolution from {current_width}x{current_height} to {new_width}x{new_height}")
                self.change_resolution(new_width, new_height)
            
            # Apply fullscreen setting
            fullscreen = self.menu.get_setting('fullscreen')
            if fullscreen != self.is_fullscreen:
                self.toggle_fullscreen()
            
            # Apply other settings
            show_fps = self.menu.get_setting('show_fps')
            if show_fps is not None:
                self.show_fps = show_fps
            
            # Apply volume setting
            volume = self.menu.get_setting('volume')
            if volume is not None and hasattr(pygame.mixer, 'music') and pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(volume / 100)
            
            # Reset the resolution changed flag
            self.menu.reset_resolution_changed()

        # Auto-rotate if enabled and not in menu
        if not self.menu.is_active() and self.auto_rotate:
            self.renderer.rotate_camera(azimuth=0.5 * self.rotation_sensitivity)
    
    def render(self):
        # Render the cube
        pygame_image = self.renderer.render_frame()
        self.screen.blit(pygame_image, (0, 0))
        
        # Add indicator for mouse rotation state
        if self.mouse_rotating:
            pygame.draw.circle(self.screen, (255, 0, 0), (20, 20), 10)  # Red dot when rotating
        
        # Show FPS counter if in fullscreen
        if self.show_fps and self.is_fullscreen:
            fps = self.clock.get_fps()
            fps_text = pygame.font.SysFont('Arial', 20, 'bolder').render(f"FPS: {fps:.1f}", True, (0, 161, 27))
            self.screen.blit(fps_text, (10, 10))
        
        # Draw menu if active and update cursor
        if self.menu.is_active():
            self.menu.update_cursor(pygame.mouse.get_pos())
        self.menu.draw(self.screen)
            
        pygame.display.flip()
        
    def run(self):
        # Main game loop
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)  # 60 FPS
            
            # Only update caption if show_fps is disabled (otherwise it's shown in-game)
            if not self.show_fps:
                pygame.display.set_caption("Rubik's Cube Simulator")
            else:
                fps = self.clock.get_fps()
                pygame.display.set_caption(f"Rubik's Cube Simulator - FPS: {fps:.1f}")
            
        # Clean up
        self.renderer.close()
        pygame.quit()
        sys.exit()