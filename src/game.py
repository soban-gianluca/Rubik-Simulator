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

class Game:
    pass

pygame.display.flip()
clock.tick(FPS)

screen.fill(BACKGROUND_COLOR)