import pygame
import sys
from OpenGL.GL import *
from OpenGL.GLU import *

def main():
    
    print("Initializing the game...")
    
    from game import Game
    
    pygame.init()
    
    game = Game()
    game.run()
    
if __name__ == "__main__":
    main()