import pygame
import sys
import os
from loading_animation import LoadingAnimation

def main():
    print("Initializing the game...")
    
    pygame.init()
    
    # Set up default resolution
    width, height = 1024, 768
    
    # Run loading animation first
    animation = LoadingAnimation(width, height)
    animation_completed = animation.run()
    
    if animation_completed:
        from game import Game
        game = Game()
        game.run()
    else:
        # User closed during animation
        pygame.quit()
        sys.exit()
    
if __name__ == "__main__":
    main()