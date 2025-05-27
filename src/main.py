import pygame
import sys

def main():
    
    print("Initializing the game...")
    
    from game import Game
    
    pygame.init()
    
    game = Game()
    game.run()
    
if __name__ == "__main__":
    main()