import pygame
import sys
import os
from loading_animation import LoadingAnimation
from game import Game
import threading

def main():
    print("Initializing the game...")
    
    pygame.init()
    
    # Set up default resolution
    width, height = 1024, 768

    # Create the loading animation instance with required screen dimensions
    loading_animation = LoadingAnimation(screen_width=width, screen_height=height)
    
    # Run the loading animation in a separate thread
    t1 = threading.Thread(target=loading_animation.run)
    t1.start()
    
    # Create and run the game in the main thread
    game = Game()
    game.run()
    
    # Clean up
    pygame.quit()
    sys.exit()
    
if __name__ == "__main__":
    main()