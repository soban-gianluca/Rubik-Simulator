import pygame
import sys

# Initialize pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
BACKGROUND_COLOR = (30, 30, 30)
WHITE = (255, 255, 255)
FPS = 60

# Set up the displayGTYHYHYHYHYHYHYHYHYHYHYHYHYHYH
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rubik's Cube Simulator")
clock = pygame.time.Clock()

class Button:
    def __init__(self, x, y, width, height, text, color, hover_color):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.hover_color = hover_color
        self.text = text
        self.font = pygame.font.SysFont('Arial', 20)
        self.is_hovered = False
    
    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=5)
        
        text_surface = self.font.render(self.text, True, WHITE)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)
    
    def update(self):
        mouse_pos = pygame.mouse.get_pos()
        self.is_hovered = self.rect.collidepoint(mouse_pos)
    
    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.is_hovered
        return False

def main():
    # Create some buttons
    scramble_button = Button(50, 500, 150, 40, "Scramble", (0, 100, 200), (0, 150, 255))
    solve_button = Button(220, 500, 150, 40, "Solve", (0, 150, 0), (0, 200, 0))
    reset_button = Button(390, 500, 150, 40, "Reset", (150, 0, 0), (200, 0, 0))
    quit_button = Button(560, 500, 150, 40, "Quit", (100, 100, 100), (150, 150, 150))
    
    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if scramble_button.is_clicked(event):
                print("Scramble button clicked!")
            
            if solve_button.is_clicked(event):
                print("Solve button clicked!")
            
            if reset_button.is_clicked(event):
                print("Reset button clicked!")
            
            if quit_button.is_clicked(event):
                running = False
        
        # Update
        scramble_button.update()
        solve_button.update()
        reset_button.update()
        quit_button.update()
        
        # Render
        screen.fill(BACKGROUND_COLOR)
        
        # Draw title
        title_font = pygame.font.SysFont('Arial', 36, bold=True)
        title_text = title_font.render("Rubik's Cube Simulator", True, WHITE)
        title_rect = title_text.get_rect(center=(WIDTH // 2, 50))
        screen.blit(title_text, title_rect)
        
        # Draw a placeholder for the cube (just a rectangle for now)
        cube_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 100, 200, 200)
        pygame.draw.rect(screen, (0, 120, 215), cube_rect)
        
        # Draw buttons
        scramble_button.draw(screen)
        solve_button.draw(screen)
        reset_button.draw(screen)
        quit_button.draw(screen)
        
        # Update display
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()