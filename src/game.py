import pygame
import sys
from pygame.locals import *

# Initialize pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
BACKGROUND_COLOR = (33, 33, 33)
WHITE = (255, 255, 255)
FPS = 120

# Set up the display
screen = pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | OPENGL)
pygame.display.set_caption("Rubik's Cube Simulator")
clock = pygame.time.Clock()

class Game:
    def __init__(self):
        from renderer import Renderer
        
        # Initialize rotation values
        self.rotation_x = 0
        self.rotation_y = 0
        self.running = True
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    pygame.quit()
                    sys.exit()
    
    def update(self):
        # Auto-rotate the model (comment out if you don't want this)
        self.rotation_y += 1
        
        # Handle arrow key presses for manual rotation
        keys = pygame.key.get_pressed()
        if keys[pygame.K_UP]:
            self.rotation_x += 1
        if keys[pygame.K_DOWN]:
            self.rotation_x -= 1
        if keys[pygame.K_LEFT]:
            self.rotation_y += 1
        if keys[pygame.K_RIGHT]:
            self.rotation_y -= 1
    
    def render(self):
        
        # Render the model
        self.model_renderer.render(self.rotation_x, self.rotation_y)
        
        # Flip the display
        pygame.display.flip()
    
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            clock.tick(FPS)

pygame.display.flip()
clock.tick(FPS)

screen.fill(BACKGROUND_COLOR)