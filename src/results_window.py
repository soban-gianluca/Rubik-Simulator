import pygame
import pygame_menu
from pygame_menu import themes
import time

class ResultsWindow:
    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.screen = pygame.display.get_surface()
        
        # Results window state
        self.active = False
        self.results_data = {}
        
        # Create custom theme for results
        self.theme = themes.THEME_DARK.copy()
        self.theme.title_font_size = 60
        self.theme.widget_font_size = 35
        self.theme.widget_margin = (0, 15)
        self.theme.background_color = (0, 50, 0, 200)  # Dark green background
        self.theme.title_background_color = (0, 100, 0, 255)
        self.theme.widget_font_color = (255, 255, 255)
        self.theme.title_font_color = (255, 255, 255)
        
        # Create the results menu
        self.menu = None
        self.create_results_menu()
    
    def create_results_menu(self):
        """Create the results display menu"""
        self.menu = pygame_menu.Menu(
            'CUBE SOLVED!',
            self.width,
            self.height,
            theme=self.theme,
            onclose=pygame_menu.events.NONE  # Disable the close button
        )
        
        # Add results display (will be populated when showing results)
        self.moves_widget = self.menu.add.label("Moves: -", font_size=40)
        self.time_widget = self.menu.add.label("Time: -", font_size=40)
        self.tps_widget = self.menu.add.label("TPS: -", font_size=40)
        
        self.menu.add.vertical_margin(30)
        
        # Performance rating
        self.rating_widget = self.menu.add.label("Performance: -", font_size=35)
        
        self.menu.add.vertical_margin(40)
        
        # Action buttons
        self.menu.add.button(
            'Play Again',
            self.play_again,
            font_size=35,
            background_color=(0, 150, 0),
            font_color=(255, 255, 255)
        )
        
        self.menu.add.button(
            'Main Menu',
            self.to_main_menu,
            font_size=35,
            background_color=(100, 100, 100),
            font_color=(255, 255, 255)
        )
    
    def show_results(self, moves, solve_time, tps=None):
        """Display the results window with the given data"""
        self.results_data = {
            'moves': moves,
            'time': solve_time,
            'tps': tps or (moves / solve_time if solve_time > 0 else 0)
        }
        
        # Update the display widgets
        self.moves_widget.set_title(f"Moves: {moves}")
        self.time_widget.set_title(f"Time: {solve_time:.2f} seconds")
        self.tps_widget.set_title(f"TPS: {self.results_data['tps']:.2f} moves/second")
        
        # Calculate and display performance rating
        rating = self.calculate_performance_rating(moves, solve_time)
        self.rating_widget.set_title(f"Performance: {rating}")
        
        self.active = True
    
    def calculate_performance_rating(self, moves, solve_time):
        """Calculate a performance rating based on moves and time"""
        # Basic rating system - can be improved
        if moves <= 20:
            if solve_time <= 30:
                return "LEGENDARY!"
            elif solve_time <= 60:
                return "EXCELLENT!"
            else:
                return "GREAT!"
        elif moves <= 50:
            if solve_time <= 60:
                return "EXCELLENT!"
            elif solve_time <= 120:
                return "GREAT!"
            else:
                return "GOOD!"
        elif moves <= 100:
            if solve_time <= 120:
                return "GREAT!"
            elif solve_time <= 300:
                return "GOOD!"
            else:
                return "COMPLETED!"
        else:
            return "COMPLETED!"

    def play_again(self):
        """Reset the cube for a new game"""
        self.active = False
        # This will be handled by the game instance
        if hasattr(self, 'game_callback'):
            self.game_callback('play_again')
    
    def to_main_menu(self):
        """Return to main menu"""
        self.active = False
        if hasattr(self, 'game_callback'):
            self.game_callback('main_menu')
    
    def close_results(self):
        """Close the results window"""
        self.active = False
    
    def handle_events(self, events):
        """Handle pygame events for the results window"""
        if self.active and self.menu:
            self.menu.update(events)
    
    def render(self):
        """Render the results window"""
        if self.active and self.menu:
            self.menu.draw(self.screen)
    
    def toggle(self):
        """Toggle the results window visibility"""
        self.active = not self.active
    
    def set_game_callback(self, callback):
        """Set the callback function to communicate with the game"""
        self.game_callback = callback
