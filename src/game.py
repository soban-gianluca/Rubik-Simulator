import pygame
import sys
import time
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from menu import Menu
from renderer import Renderer
from settings_manager import SettingsManager

class Game:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        
        # Load settings
        self.settings = SettingsManager()
        self.width = self.settings.settings["resolution"]["width"]
        self.height = self.settings.settings["resolution"]["height"]
        self.is_fullscreen = self.settings.settings["fullscreen"]
        self.show_fps = self.settings.settings["show_fps"]
        
        # Set initial display mode with OpenGL
        display_flags = DOUBLEBUF | OPENGL
        if self.is_fullscreen:
            display_flags |= FULLSCREEN
        self.screen = pygame.display.set_mode((self.width, self.height), display_flags)
        pygame.display.set_caption("Rubik's Cube Simulator")
        self.clock = pygame.time.Clock()
        
        # Initialize music
        self.playlist = [
            "utils/soundtrack/lounge_layers.mp3",
            "utils/soundtrack/midnight_simmetry.mp3",
            "utils/soundtrack/the_fifth_color.mp3"
        ]
        self.current_song = 1
        self.MUSIC_END_EVENT = pygame.USEREVENT + 1
        
        try:
            pygame.mixer.init()
            volume_level = self.settings.settings["volume"] / 100
            pygame.mixer.music.set_volume(volume_level)
            pygame.mixer.music.load(self.playlist[self.current_song])
            pygame.mixer.music.play()
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)
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
        self.menu.set_game_instance(self)
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
        
        # Movement system variables
        self.move_counter = 0
        self.start_time = None
        self.cube_solved = False
        
        print("Controls:")
        print("  Space: Toggle auto-rotation")
        print("  Arrow keys/WASD: Manual rotation")
        print("  Mouse drag: Rotate cube")
        print("  D: Toggle debug mode")
        print("  ESC: Toggle menu")
        print("  R: Reset rotation")
        
        print("Movement Controls:")
        print("  1: R move    2: R' move")
        print("  3: L move    4: L' move") 
        print("  5: U move    6: U' move")
        print("  7: D move    8: D' move")
        print("  9: F move    0: F' move")
        print("  Q: B move    W: B' move")
        print("  Z: Undo last move")
        print("  X: Scramble cube")
        print("  C: Check if solved")

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
        self.debug_print(f"Changing resolution to {width}x{height}")
        
        try:
            # Store current fullscreen state
            fullscreen = self.menu.fullscreen if hasattr(self, 'menu') else self.is_fullscreen
            
            # First completely recreate the pygame display without OpenGL
            pygame.display.quit()
            pygame.display.init()
            
            # Set display flags
            display_flags = DOUBLEBUF | OPENGL
            if fullscreen:
                display_flags |= FULLSCREEN
                self.is_fullscreen = True
            else:
                self.is_fullscreen = False
            
            # Update internal dimensions
            self.width = width
            self.height = height
            
            # Set the new display mode with a fresh pygame instance
            self.screen = pygame.display.set_mode((width, height), display_flags)
            pygame.display.set_caption("Rubik's Cube Simulator")
            
            # Verify the actual dimensions
            actual_width, actual_height = pygame.display.get_surface().get_size()
            self.debug_print(f"Actual screen size: {actual_width}x{actual_height}")
            
            # If actual size differs significantly from requested size, update dimensions
            if abs(actual_width - width) > 5 or abs(actual_height - height) > 5:
                self.width = actual_width
                self.height = actual_height
    
            # Now recreate the OpenGL context with correct dimensions
            self.renderer = Renderer(self.width, self.height)
    
            # Update menu with the actual dimensions
            if hasattr(self, 'menu'):
                self.menu.width = self.width
                self.menu.height = self.height
                if hasattr(self, 'debug_mode'):
                    self.menu.debug_mode = self.debug_mode
                self.menu._create_menus()
    
            # Try to restore icon
            try:
                icon = pygame.image.load("utils/rubiksCube_Icon.ico")
                pygame.display.set_icon(icon)
            except Exception:
                pass
    
            # Save settings
            self.settings.settings["resolution"]["width"] = self.width
            self.settings.settings["resolution"]["height"] = self.height
            self.settings.settings["fullscreen"] = self.is_fullscreen
            self.settings.save_settings()
    
            self.debug_print(f"Resolution change complete: {self.width}x{self.height}")
            return True
    
        except Exception as e:
            print(f"Resolution change error: {e}")
            self._fallback_resolution()
            return False
    
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
                
                # Add movement controls
                elif not self.menu.is_active():
                    if event.key == pygame.K_1:
                        self.execute_cube_move('R')
                    elif event.key == pygame.K_2:
                        self.execute_cube_move("R'")
                    elif event.key == pygame.K_3:
                        self.execute_cube_move('L')
                    elif event.key == pygame.K_4:
                        self.execute_cube_move("L'")
                    elif event.key == pygame.K_5:
                        self.execute_cube_move('U')
                    elif event.key == pygame.K_6:
                        self.execute_cube_move("U'")
                    elif event.key == pygame.K_7:
                        self.execute_cube_move('D')
                    elif event.key == pygame.K_8:
                        self.execute_cube_move("D'")
                    elif event.key == pygame.K_9:
                        self.execute_cube_move('F')
                    elif event.key == pygame.K_0:
                        self.execute_cube_move("F'")
                    elif event.key == pygame.K_q:
                        self.execute_cube_move('B')
                    elif event.key == pygame.K_w:
                        self.execute_cube_move("B'")
                    elif event.key == pygame.K_z:
                        self.undo_move()
                    elif event.key == pygame.K_x:
                        self.scramble_cube()
                    elif event.key == pygame.K_c:
                        self.check_solved()
        
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
            try:
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
                
                # Reset the flag after successfully applying settings
                self.menu.reset_resolution_changed()
            except Exception as e:
                self.debug_print(f"Error during resolution change: {e}")
                # Reset the flag even on error to prevent continuous attempts
                self.menu.reset_resolution_changed()

        if not self.menu.is_active() and self.auto_rotate:
            self.renderer.rotate_camera(azimuth=self.auto_rotation_speed, elevation=0)
    
    def render(self):
        # Render 3D cube
        self.renderer.render_frame()
        
        # Render 2D overlays (menu and FPS)
        # Switch to 2D orthographic projection
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
        
        # Render FPS counter if enabled
        if self.show_fps:
            self._render_fps_counter()
        
        # Render menu overlay if active
        if self.menu.is_active():
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
        
        # Update window caption (remove FPS from title since it's now on screen)
        pygame.display.set_caption("Rubik's Cube Simulator")
        
        pygame.display.flip()

    def _render_fps_counter(self):
        """Render FPS counter in the top-left corner"""
        try:
            # Get current FPS
            fps = self.clock.get_fps()
            
            # Create font if not exists
            if not hasattr(self, '_fps_font'):
                self._fps_font = pygame.font.SysFont('Arial', 24, bold=True)
            
            # Create FPS text surface
            fps_text = f"FPS: {fps:.1f}"
            text_surface = self._fps_font.render(fps_text, True, (255, 255, 255))
            
            # Add a semi-transparent background for better readability
            text_width, text_height = text_surface.get_size()
            bg_surface = pygame.Surface((text_width + 20, text_height + 10), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 128))  # Semi-transparent black background
            
            # Blit text onto background
            bg_surface.blit(text_surface, (10, 5))
            
            # Convert to OpenGL texture and render
            texture_data = pygame.image.tostring(bg_surface, 'RGBA', True)
            
            # Position in top-left corner (10 pixels from edges)
            glRasterPos2f(10, text_height + 15)
            glPixelZoom(1, 1)
            glDrawPixels(text_width + 20, text_height + 10, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            
        except Exception as e:
            # Fallback: if there's an error, just print to console
            if self.debug_mode:
                print(f"FPS counter rendering error: {e}")

    def execute_cube_move(self, move_notation):
        """Execute a Rubik's cube move"""
        if self.start_time is None:
            self.start_time = time.time()
        
        self.renderer.rubiks_cube.execute_move(move_notation)
        self.renderer.update_cube_colors()
        self.move_counter += 1
        
        self.debug_print(f"Move {self.move_counter}: {move_notation}")
        
        # Check if solved after move
        if self.renderer.rubiks_cube.is_solved():
            self.cube_solved = True
            solve_time = time.time() - self.start_time
            print(f"🎉 CUBE SOLVED! 🎉")
            print(f"Moves: {self.move_counter}")
            print(f"Time: {solve_time:.2f} seconds")
            print(f"TPS: {self.move_counter/solve_time:.2f} moves/second")
    
    def undo_move(self):
        """Undo the last move"""
        if self.renderer.rubiks_cube.undo_last_move():
            self.renderer.update_cube_colors()
            self.move_counter = max(0, self.move_counter - 1)
            self.debug_print(f"Move undone. Move count: {self.move_counter}")
        else:
            self.debug_print("No moves to undo")
    
    def scramble_cube(self):
        """Scramble the cube"""
        self.renderer.rubiks_cube.scramble(25)
        self.renderer.update_cube_colors()
        self.move_counter = 0
        self.start_time = None
        self.cube_solved = False
        self.debug_print("Cube scrambled!")
    
    def check_solved(self):
        """Check if the cube is solved"""
        if self.renderer.rubiks_cube.is_solved():
            print("✅ Cube is SOLVED!")
        else:
            print("❌ Cube is not solved yet")
    
    def _render_game_info(self):
        """Render game information (FPS, moves, time)"""
        try:
            # Create font if not exists
            if not hasattr(self, '_info_font'):
                self._info_font = pygame.font.SysFont('Arial', 20, bold=True)
            
            info_lines = []
            
            # Add FPS if enabled
            if self.show_fps:
                fps = self.clock.get_fps()
                info_lines.append(f"FPS: {fps:.1f}")
            
            # Add move counter and timer
            if self.move_counter > 0:
                info_lines.append(f"Moves: {self.move_counter}")
                
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    info_lines.append(f"Time: {elapsed:.1f}s")
                    
                    if elapsed > 0:
                        tps = self.move_counter / elapsed
                        info_lines.append(f"TPS: {tps:.2f}")
            
            # Render status if solved
            if self.cube_solved:
                info_lines.append("🎉 SOLVED! 🎉")
            
            # Render each line
            y_offset = 10
            for line in info_lines:
                text_surface = self._info_font.render(line, True, (255, 255, 255))
                text_width, text_height = text_surface.get_size()
                
                # Background
                bg_surface = pygame.Surface((text_width + 20, text_height + 6), pygame.SRCALPHA)
                bg_surface.fill((0, 0, 0, 128))
                bg_surface.blit(text_surface, (10, 3))
                
                # Render to screen
                texture_data = pygame.image.tostring(bg_surface, 'RGBA', True)
                glRasterPos2f(10, y_offset + text_height + 6)
                glPixelZoom(1, 1)
                glDrawPixels(text_width + 20, text_height + 6, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
                
                y_offset += text_height + 12
                
        except Exception as e:
            if self.debug_mode:
                print(f"Game info rendering error: {e}")

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick()
            
        # Before exiting, save settings
        self.settings.settings["resolution"]["width"] = self.width
        self.settings.settings["resolution"]["height"] = self.height
        self.settings.settings["fullscreen"] = self.is_fullscreen
        self.settings.settings["show_fps"] = self.show_fps
        self.settings.settings["volume"] = int(pygame.mixer.music.get_volume() * 100)
        self.settings.save_settings()
        
        self.renderer.close()
        pygame.quit()
        sys.exit()

    def _fallback_resolution(self):
        """Fallback to a safe resolution if change fails"""
        try:
            print("Attempting fallback to safe resolution")
            
            # First completely recreate the pygame display
            pygame.display.quit()
            pygame.display.init()
            
            # Try a standard resolution that should work
            fallback_width, fallback_height = 1024, 768
            self.width = fallback_width
            self.height = fallback_height
            
            # Reset to windowed mode for safety
            self.is_fullscreen = False
            
            # Set the display mode with safe settings
            self.screen = pygame.display.set_mode((fallback_width, fallback_height), DOUBLEBUF | OPENGL)
            
            # Recreate the renderer from scratch
            self.renderer = Renderer(fallback_width, fallback_height)
            
            # Update menu dimensions if it exists
            if hasattr(self, 'menu'):
                self.menu.width = fallback_width
                self.menu.height = fallback_height
                self.menu._create_menus()
            
            print(f"Successfully restored to fallback resolution: {fallback_width}x{fallback_height}")
        except Exception as e:
            print(f"Critical error in fallback resolution: {e}")
            # Nothing more we can do at this point
            self.running = False