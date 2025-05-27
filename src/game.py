import pygame
import sys

# Initialize pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
BACKGROUND_COLOR = (33, 33, 33)
WHITE = (255, 255, 255)
FPS = 120

# Set up the display
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rubik's Cube Simulator")
clock = pygame.time.Clock()



def main():
    # Create some buttons
    scramble_button = Button("Scramble")
    reset_button = Button("Reset")
    quit_button = Button("Quit")
    
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
        reset_button.draw(screen)
        quit_button.draw(screen)
        
        # Update display
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()