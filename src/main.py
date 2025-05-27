import pygame
import sys
import os

def main():
    
    print("Initializing the game...")
    
    pygame.init()
    
    # Set the window icon
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "rubicksCube_Icon.ico")
    if os.path.exists(icon_path):
        icon = pygame.image.load(icon_path)
        pygame.display.set_icon(icon)
    else:
        print(f"Warning: Icon file not found at {icon_path}")
    
    from game import Game
    
    game = Game()
    game.run()
    
if __name__ == "__main__":
    main()