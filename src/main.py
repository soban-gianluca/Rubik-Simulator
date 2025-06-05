import pygame
import sys
from pygame.locals import *

from loading_animation import LoadingAnimation
from game import Game

def main():
    print("Initializing the game...")
    
    pygame.init()
    
    # Set up default resolution
    width, height = 1024, 768

    # Create and run the loading animation first (blocking)
    loading_animation = LoadingAnimation(screen_width=width, screen_height=height)
    
    # Run the loading animation synchronously
    if loading_animation.run():
        print("Loading complete, starting game...")
        
        # Close the loading screen
        pygame.quit()
        
        # Reinitialize pygame for the main game
        pygame.init()
        
        # Create and run the game
        game = Game()
        game.run()
    else:
        print("Loading cancelled or failed")
    
    # Clean up
    pygame.quit()
    sys.exit()
    
if __name__ == "__main__":
    main()