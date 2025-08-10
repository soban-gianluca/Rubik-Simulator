import pygame
import pygame_menu
from pygame_menu import themes
from pygame_menu.locals import *
import time
import math
import random

class ResultsWindow:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.screen = pygame.display.get_surface()
        
        # Results window state
        self.active = False
        self.results_data = {}
        
        # Animation and visual effects
        self.is_animating = False
        self.animation_start_time = 0
        self.animation_duration = 0.8  # Longer animation for dramatic effect
        self.is_opening = False
        self.current_alpha = 0.0
        self.target_alpha = 1.0
        
        # Particle system for celebration
        self.particles = []
        self.stars = []
        self.celebration_active = False
        self.celebration_start_time = 0
        
        # Performance rating colors and effects
        self.rating_colors = {
            "LEGENDARY!": (255, 215, 0),    # Gold
            "EXCELLENT!": (50, 205, 50),    # Lime green
            "GREAT!": (30, 144, 255),       # Dodger blue
            "GOOD!": (255, 140, 0),         # Dark orange
            "COMPLETED!": (169, 169, 169)   # Dark gray
        }
        
        # Create modern custom theme
        self._create_modern_theme()
        
        # Create the results menu
        self.menu = None
        self.create_results_menu()
    
    def _create_modern_theme(self):
        """Create a modern theme matching the main menu style"""
        # Start with the blue theme as base (same as menu)
        self.theme = pygame_menu.themes.THEME_BLUE.copy()
        
        # Background styling - transparent for overlay effect
        self.theme.background_color = (5, 10, 20, 240)  # Very dark with high transparency
        
        # Title styling - minimal since we use custom label
        self.theme.title_font = pygame_menu.font.FONT_FRANCHISE
        self.theme.title_font_size = 1  # Minimal since not used
        self.theme.title_font_color = (255, 215, 0)
        self.theme.title_background_color = (0, 0, 0, 0)  # Transparent
        self.theme.title_bar_style = pygame_menu.widgets.MENUBAR_STYLE_NONE
        self.theme.title_alignment = ALIGN_CENTER
        
        # Widget styling - more compact
        self.theme.widget_font = pygame_menu.font.FONT_FRANCHISE
        self.theme.widget_font_size = 38
        self.theme.widget_font_color = (255, 255, 255)
        self.theme.widget_font_shadow = True
        self.theme.widget_font_shadow_color = (0, 0, 0)
        self.theme.widget_font_shadow_offset = 2
        self.theme.widget_margin = (0, 8)  # Even more compact
        self.theme.widget_padding = (15, 8)  # More compact padding
        
        # Remove widget backgrounds for clean look
        self.theme.widget_background_color = (0, 0, 0, 0)
        self.theme.widget_background_color_disabled = (0, 0, 0, 0)
        self.theme.widget_border_color = (0, 0, 0, 0)
        self.theme.widget_border_width = 0
        
        # Use no selection effect - we'll handle hover manually
        self.theme.widget_selection_effect = pygame_menu.widgets.NoneSelection()
        
        # Menu bar styling
        self.theme.menubar_close_button = False
    
    def create_results_menu(self):
        """Create the modern results display menu"""
        self.menu = pygame_menu.Menu(
            '',  # Empty title since we're using a custom label
            self.width,
            self.height,
            theme=self.theme,
            onclose=pygame_menu.events.NONE,
            overflow=False,  # Disable overflow/scrolling
            columns=1,
            rows=None
        )
        
        # Add some top spacing
        self.menu.add.vertical_margin(30)
        
        # Add celebration emoji/symbols - smaller and more compact
        self.menu.add.label("🎉 CUBE SOLVED! 🎉", font_size=50, font_color=(255, 215, 0))  # Combined title and emoji
        self.menu.add.vertical_margin(15)  # Reduced spacing
        
        # Performance stats with modern styling - more compact layout
        self.moves_widget = self.menu.add.label("", font_size=40, font_color=(255, 255, 255))
        self.time_widget = self.menu.add.label("", font_size=40, font_color=(255, 255, 255))
        self.tps_widget = self.menu.add.label("", font_size=40, font_color=(255, 255, 255))
        
        self.menu.add.vertical_margin(20)  # Reduced spacing
        
        # Performance rating with dynamic color - smaller
        self.rating_widget = self.menu.add.label("", font_size=45, font_color=(255, 215, 0))
        
        self.menu.add.vertical_margin(25)  # Reduced spacing
        
        # Modern styled action buttons - more compact
        self.play_again_btn = self.menu.add.button(
            '▶ Play Again',
            self.play_again,
            font_size=38,  # Reduced from 45
            background_color=(46, 125, 50, 200),  # Green with transparency
            font_color=(255, 255, 255),
            padding=(20, 12)  # Reduced padding
        )
        
        self.main_menu_btn = self.menu.add.button(
            '🏠 Main Menu',
            self.to_main_menu,
            font_size=38,  # Reduced from 45
            background_color=(66, 66, 66, 200),  # Gray with transparency
            font_color=(255, 255, 255),
            padding=(20, 12)  # Reduced padding
        )
        
        # Apply modern styling
        self._customize_button_appearance(self.play_again_btn)
        self._customize_button_appearance(self.main_menu_btn)
    
    def _customize_button_appearance(self, button):
        """Apply modern styling to buttons (simplified without problematic hover callbacks)"""
        try:
            # Just ensure the button has the right styling, hover will be handled manually
            pass
        except:
            pass
    
    def _on_button_hover(self, button, is_hovering):
        """Handle button hover effects"""
        try:
            if is_hovering:
                # Enhance the button color on hover
                if button == self.play_again_btn:
                    button.set_background_color((66, 165, 70, 220))
                elif button == self.main_menu_btn:
                    button.set_background_color((96, 96, 96, 220))
                # Change text color to gold on hover
                if hasattr(button, '_font_color'):
                    button._font_color = (255, 215, 0)
            else:
                # Restore original colors
                if button == self.play_again_btn:
                    button.set_background_color((46, 125, 50, 200))
                elif button == self.main_menu_btn:
                    button.set_background_color((66, 66, 66, 200))
                if hasattr(button, '_font_color'):
                    button._font_color = (255, 255, 255)
        except:
            pass
    
    def show_results(self, moves, solve_time, tps=None):
        """Display the results window with the given data and trigger celebration"""
        self.results_data = {
            'moves': moves,
            'time': solve_time,
            'tps': tps or (moves / solve_time if solve_time > 0 else 0)
        }
        
        # Calculate performance rating and get color
        rating = self.calculate_performance_rating(moves, solve_time)
        rating_color = self.rating_colors.get(rating, (255, 255, 255))
        
        # Update the display widgets with modern formatting
        self.moves_widget.set_title(f"📊 Moves: {moves}")
        self.time_widget.set_title(f"⏱️  Time: {solve_time:.2f}s")
        self.tps_widget.set_title(f"⚡ Speed: {self.results_data['tps']:.2f} TPS")
        
        # Set performance rating with dynamic color
        self.rating_widget.set_title(f"🌟 {rating}")
        self.rating_widget._font_color = rating_color
        
        # Start celebration effects
        self._start_celebration()
        
        # Show window immediately without fade animation
        self.active = True
        self.is_animating = False
        self.current_alpha = 1.0
        self.target_alpha = 1.0
    
    def _start_celebration(self):
        """Start celebration particle effects"""
        self.celebration_active = True
        self.celebration_start_time = time.time()
        self.particles = []
        self.stars = []
        
        # Create initial burst of particles
        for _ in range(50):  # Confetti particles
            self._create_confetti_particle()
        
        for _ in range(20):  # Star particles
            self._create_star_particle()
    
    def _create_confetti_particle(self):
        """Create a confetti particle"""
        colors = [(255, 215, 0), (255, 69, 0), (50, 205, 50), (30, 144, 255), (255, 20, 147)]
        particle = {
            'x': self.width // 2 + random.randint(-100, 100),
            'y': self.height // 4,
            'vx': random.uniform(-8, 8),
            'vy': random.uniform(-15, -5),
            'gravity': 0.3,
            'color': random.choice(colors),
            'size': random.randint(3, 8),
            'rotation': random.uniform(0, 360),
            'rotation_speed': random.uniform(-10, 10),
            'life': 1.0,
            'decay': random.uniform(0.008, 0.015)
        }
        self.particles.append(particle)
    
    def _create_star_particle(self):
        """Create a star particle"""
        star = {
            'x': random.randint(0, self.width),
            'y': random.randint(0, self.height),
            'size': random.randint(2, 6),
            'twinkle_phase': random.uniform(0, 2 * math.pi),
            'twinkle_speed': random.uniform(2, 5),
            'color': (255, 255, 255),
            'life': 1.0,
            'decay': random.uniform(0.005, 0.01)
        }
        self.stars.append(star)
    
    def _update_particles(self):
        """Update particle system"""
        if not self.celebration_active:
            return
        
        # Update confetti
        for particle in self.particles[:]:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['vy'] += particle['gravity']
            particle['rotation'] += particle['rotation_speed']
            particle['life'] -= particle['decay']
            
            if particle['life'] <= 0 or particle['y'] > self.height + 50:
                self.particles.remove(particle)
        
        # Update stars
        for star in self.stars[:]:
            star['life'] -= star['decay']
            if star['life'] <= 0:
                self.stars.remove(star)
        
        # Add new particles occasionally during celebration
        celebration_time = time.time() - self.celebration_start_time
        if celebration_time < 3.0 and random.random() < 0.1:  # 3 seconds of continuous celebration
            if len(self.particles) < 30:
                self._create_confetti_particle()
        
        # Stop celebration after particles die out
        if not self.particles and not self.stars and celebration_time > 2.0:
            self.celebration_active = False
    
    def _draw_particles(self, screen):
        """Draw the particle effects"""
        # Draw confetti
        for particle in self.particles:
            if particle['life'] > 0:
                alpha = int(255 * particle['life'])
                color = (*particle['color'], alpha)
                
                # Create a small surface for the confetti piece
                size = int(particle['size'] * particle['life'])
                if size > 0:
                    # Draw a rotated rectangle for confetti
                    rect_surface = pygame.Surface((size * 2, size), pygame.SRCALPHA)
                    rect_surface.fill(color)
                    
                    # Rotate the confetti
                    rotated = pygame.transform.rotate(rect_surface, particle['rotation'])
                    rect = rotated.get_rect(center=(particle['x'], particle['y']))
                    screen.blit(rotated, rect)
        
        # Draw twinkling stars
        for star in self.stars:
            if star['life'] > 0:
                # Calculate twinkling effect
                twinkle = math.sin(time.time() * star['twinkle_speed'] + star['twinkle_phase']) * 0.5 + 0.5
                alpha = int(255 * star['life'] * twinkle)
                size = int(star['size'] * (0.5 + twinkle * 0.5))
                
                if size > 0:
                    # Draw a simple star shape
                    color = (*star['color'], alpha)
                    pygame.draw.circle(screen, color[:3], 
                                     (int(star['x']), int(star['y'])), size)
                    # Add a plus sign for star effect
                    pygame.draw.line(screen, color[:3], 
                                   (star['x'] - size, star['y']), 
                                   (star['x'] + size, star['y']), 2)
                    pygame.draw.line(screen, color[:3], 
                                   (star['x'], star['y'] - size), 
                                   (star['x'], star['y'] + size), 2)
    
    def calculate_performance_rating(self, moves, solve_time):
        """Calculate a performance rating based on moves and time with more detailed categories"""
        # Enhanced rating system with more nuanced categories
        efficiency_score = moves / max(1, solve_time)  # Moves per second as efficiency metric
        
        if moves <= 15:
            if solve_time <= 20:
                return "LEGENDARY!"
            elif solve_time <= 45:
                return "EXCELLENT!"
            else:
                return "GREAT!"
        elif moves <= 25:
            if solve_time <= 30:
                return "EXCELLENT!"
            elif solve_time <= 60:
                return "GREAT!"
            else:
                return "GOOD!"
        elif moves <= 40:
            if solve_time <= 60:
                return "GREAT!"
            elif solve_time <= 120:
                return "GOOD!"
            else:
                return "COMPLETED!"
        elif moves <= 70:
            if solve_time <= 120:
                return "GOOD!"
            else:
                return "COMPLETED!"
        else:
            return "COMPLETED!"

    def play_again(self):
        """Reset the cube for a new game - immediate action"""
        self.active = False
        self.celebration_active = False  # Stop celebration
        if hasattr(self, 'game_callback'):
            self.game_callback('play_again')
    
    def to_main_menu(self):
        """Return to main menu - immediate action"""
        self.active = False
        self.celebration_active = False  # Stop celebration
        if hasattr(self, 'game_callback'):
            self.game_callback('main_menu')
    
    def _start_closing_animation(self):
        """Start the closing animation - now immediate"""
        self.active = False
        self.is_animating = False
        self.celebration_active = False
    
    def close_results(self):
        """Close the results window immediately"""
        self.active = False
        self.is_animating = False
        self.celebration_active = False
        self.particles = []
        self.stars = []
    
    def update(self):
        """Update animation state and particle effects"""
        # No more fade animation - just update particles
        self._update_particles()
    
    def get_current_alpha(self):
        """Get the current alpha value for rendering"""
        if not self.active:
            return 0.0
        return 1.0  # Always full opacity when active
    
    def handle_events(self, events):
        """Handle pygame events for the results window"""
        if self.active and self.menu:
            # Handle basic events
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.active = False
                        self.celebration_active = False
                        if hasattr(self, 'game_callback'):
                            self.game_callback('main_menu')
                        return
            
            self.menu.update(events)
    
    def _update_button_hover_effects(self, mouse_pos):
        """Update hover effects for buttons based on mouse position - DISABLED for stability"""
        # Temporarily disabled to avoid pygame_menu callback issues
        # The buttons will still work, just without custom hover effects
        pass
    
    def render_to_surface(self, surface):
        """Render the results window with modern effects to a pygame surface"""
        if not self.active:
            return
        
        # Draw modern background with gradient effect (no fade)
        self._draw_modern_background(surface, 1.0)
        
        # Draw particle effects if celebration is active
        if self.celebration_active:
            self._draw_particles(surface)
        
        # Draw the menu
        if self.menu:
            menu_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.menu.draw(menu_surface)
            surface.blit(menu_surface, (0, 0))
    
    def render(self):
        """Legacy render method - now redirects to render_to_surface"""
        # Create a surface and render to it, then blit to screen
        # This method is mainly for backward compatibility
        if self.screen and self.active:
            surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.render_to_surface(surface)
            self.screen.blit(surface, (0, 0))
    
    def _draw_modern_background(self, surface, alpha):
        """Draw a modern gradient background with glassmorphism effect"""
        # Create multi-layered background for depth
        
        # Layer 1: Dark overlay with radial gradient
        center_x, center_y = self.width // 2, self.height // 2
        max_radius = int(math.sqrt(center_x**2 + center_y**2))
        
        for radius in range(0, max_radius, 20):
            alpha_value = max(0, int(200 - (radius / max_radius) * 100))
            final_alpha = int(alpha_value * alpha)
            if final_alpha > 0:
                color = (5, 10, 25, final_alpha)
                pygame.draw.circle(surface, color, (center_x, center_y), radius, 20)
        
        # Layer 2: Subtle animated rings for dynamic effect
        time_offset = time.time()
        for i in range(3):
            ring_radius = 150 + i * 100 + int(30 * math.sin(time_offset + i))
            ring_alpha = int(30 * alpha)
            if ring_alpha > 0:
                pygame.draw.circle(surface, (100, 150, 255, ring_alpha), 
                                 (center_x, center_y), ring_radius, 3)
        
        # Corner spotlight effects removed - no more spheres
    
    def toggle(self):
        """Toggle the results window visibility - immediate"""
        if self.active:
            self.active = False
            self.celebration_active = False
        else:
            self.active = True
    
    def set_game_callback(self, callback):
        """Set the callback function to communicate with the game"""
        self.game_callback = callback
    
    def update_dimensions(self, new_width, new_height):
        """Update the results window dimensions and recreate the menu"""
        if abs(self.width - new_width) < 5 and abs(self.height - new_height) < 5:
            return  # No significant change
        
        self.width = new_width
        self.height = new_height
        
        # Store current results data if any
        current_results = self.results_data.copy() if hasattr(self, 'results_data') and self.results_data else {}
        current_active = self.active
        current_animation_state = self.is_animating
        
        # Recreate the menu with new dimensions
        self.create_results_menu()
        
        # Restore results data if the window was showing results
        if current_results and (current_active or current_animation_state):
            # Re-display results without triggering new celebration
            self._restore_results_display(current_results)
            self.active = current_active
            # Don't restart celebration after resize
    
    def _restore_results_display(self, results_data):
        """Restore results display after dimension update without celebration"""
        moves = results_data['moves']
        solve_time = results_data['time']
        tps = results_data['tps']
        
        # Calculate performance rating and get color
        rating = self.calculate_performance_rating(moves, solve_time)
        rating_color = self.rating_colors.get(rating, (255, 255, 255))
        
        # Update the display widgets with modern formatting
        self.moves_widget.set_title(f"📊 Moves: {moves}")
        self.time_widget.set_title(f"⏱️  Time: {solve_time:.2f}s")
        self.tps_widget.set_title(f"⚡ Speed: {tps:.2f} TPS")
        
        # Set performance rating with dynamic color
        self.rating_widget.set_title(f"🌟 {rating}")
        self.rating_widget._font_color = rating_color
        
        # Store the data
        self.results_data = results_data
