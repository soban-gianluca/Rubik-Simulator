import pygame
import sys
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from menu import Menu
from renderer import Renderer

class Game:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        self.width, self.height = 1024, 768
        
        # Display settings
        self.is_fullscreen = False
        self.show_fps = False
        
        # Set initial display mode with OpenGL
        self.screen = pygame.display.set_mode((self.width, self.height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Rubik's Cube Simulator")
        self.clock = pygame.time.Clock()
        
        # Load resources
        # Initialize music
        self.playlist = [
            "utils/soundtrack/lounge_layers.mp3",
            "utils/soundtrack/midnight_simmetry.mp3",
            "utils/soundtrack/the_fifth_color.mp3"
        ]
        self.current_song = 1
        self.fade_time = 2000
        
        # Initialize music
        try:
            pygame.mixer.init()
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.load(self.playlist[self.current_song])
            pygame.mixer.music.play()
            
            # Set up music end event
            MUSIC_END_EVENT = pygame.USEREVENT + 1
            pygame.mixer.music.set_endevent(MUSIC_END_EVENT)
            self.MUSIC_END_EVENT = MUSIC_END_EVENT
        except Exception as e:
            print(f"Background music error: {e}")
        
        try:
            icon = pygame.image.load("utils/rubiksCube_Icon.ico")
            pygame.display.set_icon(icon)
        except:
            print("Icon not found")

        # Initialize renderer
        self.renderer = Renderer(self.width, self.height)
        
        # Initialize menu
        self.menu = Menu(self.width, self.height)
        self.menu.toggle()  # Start with menu active
        
        # Game state
        self.running = True
        self.auto_rotate = True
        
        # Control variables
        self.mouse_rotating = False
        self.prev_mouse_x = 0
        self.prev_mouse_y = 0
        self.rotation_sensitivity = 0.5
        self.vertical_sensitivity = 0.5
        self.debug_mode = False
        self.auto_rotation_speed = 0.2  # Reduced from 1.0 to 0.3 for slower rotation
        
        print("Controls:")
        print("  Space: Toggle auto-rotation")
        print("  Arrow keys/WASD: Manual rotation")
        print("  Mouse drag: Rotate cube")
        print("  D: Toggle debug mode")
        print("  ESC: Toggle menu")
        print("  R: Reset rotation")

    def debug_print(self, message):
        if self.debug_mode:
            print(message)

    # ...existing code... (keeping all the existing methods the same)
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode with proper resolution handling"""
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode((self.width, self.height), DOUBLEBUF | OPENGL)
            self.renderer.setup_opengl()
            self.renderer.create_display_list()
        else:
            display_info = pygame.display.Info()
            fullscreen_width = display_info.current_w
            fullscreen_height = display_info.current_h
            
            self.screen = pygame.display.set_mode((fullscreen_width, fullscreen_height), DOUBLEBUF | OPENGL | FULLSCREEN)
            self.renderer.setup_opengl()
            self.renderer.create_display_list()
            self.debug_print(f"Switched to fullscreen: {fullscreen_width}x{fullscreen_height}")
        
        self.is_fullscreen = not self.is_fullscreen
    
    def change_resolution(self, width, height):
        """Change screen resolution"""
        current_volume = self.menu.volume if hasattr(self, 'menu') else 50
        current_show_fps = self.menu.show_fps if hasattr(self, 'menu') else False
        current_fullscreen = self.menu.fullscreen if hasattr(self, 'menu') else False

        self.width = width
        self.height = height

        if current_fullscreen:
            self.screen = pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL | FULLSCREEN)
            self.is_fullscreen = True
        else:
            self.screen = pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
            self.is_fullscreen = False

        if hasattr(self, 'renderer'):
            self.renderer.width = width
            self.renderer.height = height
            self.renderer.setup_opengl()
            self.renderer.create_display_list()

        if hasattr(self, 'menu'):
            self.menu.update_dimensions(width, height)
            self.menu.volume = current_volume
            self.menu.show_fps = current_show_fps
            self.menu.fullscreen = current_fullscreen

        self.debug_print(f"Resolution changed to {width}x{height}")
        return True
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == self.MUSIC_END_EVENT:
                # Move to the next song (looping back to the first)
                self.current_song = (self.current_song + 1) % len(self.playlist)
                self.debug_print(f"Playing next song: {self.playlist[self.current_song]}")
                
                # Load and play the next song
                try:
                    pygame.mixer.music.load(self.playlist[self.current_song])
                    pygame.mixer.music.play()
                except Exception as e:
                    self.debug_print(f"Music error: {e}")
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    menu_was_active = self.menu.is_active()
                    self.menu.toggle()
                    if menu_was_active:
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                    self.debug_print(f"Menu: {'ON' if self.menu.is_active() else 'OFF'}")
                elif not self.menu.is_active() and event.key == pygame.K_SPACE:
                    self.auto_rotate = not self.auto_rotate
                    self.debug_print(f"Auto-rotate: {'ON' if self.auto_rotate else 'OFF'}")
                elif not self.menu.is_active() and event.key == pygame.K_d:
                    self.debug_mode = not self.debug_mode
                    self.debug_print(f"Debug mode: {'ON' if self.debug_mode else 'OFF'}")
                elif not self.menu.is_active() and event.key == pygame.K_r:
                    self.renderer.rotation_x = 0
                    self.renderer.rotation_y = 0
                    self.debug_print("Rotation reset")
                elif event.key == pygame.K_F11:
                    self.toggle_fullscreen()
            
            elif self.menu.handle_event(event):
                continue
                
            elif not self.menu.is_active() and event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.mouse_rotating = True
                    self.prev_mouse_x, self.prev_mouse_y = event.pos
                    self.auto_rotate = False
                    self.debug_print(f"Mouse rotation started at {event.pos}")
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and not self.menu.is_active():
                    self.mouse_rotating = False
                    self.debug_print("Mouse rotation ended")
                
            elif not self.menu.is_active() and event.type == pygame.MOUSEMOTION:
                if self.mouse_rotating:
                    current_x, current_y = event.pos
                    dx = current_x - self.prev_mouse_x
                    dy = current_y - self.prev_mouse_y
                    
                    horizontal_rotation = dx * self.rotation_sensitivity
                    vertical_rotation = dy * self.vertical_sensitivity
                    
                    self.renderer.rotate_camera(
                        azimuth=horizontal_rotation, 
                        elevation=vertical_rotation
                    )
                    
                    self.debug_print(f"Rotating: dx={dx}, dy={dy}")
                    
                    self.prev_mouse_x = current_x
                    self.prev_mouse_y = current_y
    
        # Keyboard controls for rotation
        if not self.menu.is_active():
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.renderer.rotate_camera(azimuth=-2)
                self.auto_rotate = False
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.renderer.rotate_camera(azimuth=2)
                self.auto_rotate = False
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.renderer.rotate_camera(elevation=-2)
                self.auto_rotate = False
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.renderer.rotate_camera(elevation=2)
                self.auto_rotate = False

    def update(self):
        """Update game state"""        
        if hasattr(self, 'menu') and self.menu.resolution_changed():
            new_width, new_height = self.menu.get_current_resolution()
            fullscreen = self.menu.get_setting('fullscreen')
            
            if (new_width, new_height) != (self.width, self.height) or fullscreen != self.is_fullscreen:
                self.change_resolution(new_width, new_height)
            
            show_fps = self.menu.get_setting('show_fps')
            if show_fps is not None:
                self.show_fps = show_fps
            
            volume = self.menu.get_setting('volume')
            if volume is not None and pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(volume / 100)
            
            self.menu.reset_resolution_changed()

        if not self.menu.is_active() and self.auto_rotate:
            self.renderer.rotate_camera(azimuth=self.auto_rotation_speed)
    
    def render(self):
        # Render 3D cube
        self.renderer.render_frame()
        
        # Render 2D menu overlay if active
        if self.menu.is_active():
            # Switch to 2D orthographic projection for menu
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glOrtho(0, self.width, self.height, 0, -1, 1)
            
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            
            # Disable depth testing for 2D rendering
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_LIGHTING)
            
            # Enable blending for transparency
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Create menu surface and render to it
            menu_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.menu.draw(menu_surface)
            
            # Convert pygame surface to OpenGL texture
            texture_data = pygame.image.tostring(menu_surface, 'RGBA', True)
            
            glRasterPos2f(0, self.height)
            glPixelZoom(1, 1)  # Flip vertically
            glDrawPixels(self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            
            # Restore 3D state
            glDisable(GL_BLEND)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            
            glPopMatrix()
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
        
        # Update window caption
        if self.show_fps:
            fps = self.clock.get_fps()
            pygame.display.set_caption(f"Rubik's Cube Simulator - FPS: {fps:.1f}")
        else:
            pygame.display.set_caption("Rubik's Cube Simulator")
            
        pygame.display.flip()
        
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick()
            
        self.renderer.close()
        pygame.quit()
        sys.exit()