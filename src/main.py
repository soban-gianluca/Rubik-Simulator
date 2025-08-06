import pygame
import sys
from pygame.locals import *
from loading_animation import LoadingAnimation
from game import Game

def main():
    print("Initializing the game...")
    
    pygame.init()
    
    # Load game settings to use the same resolution
    from settings_manager import SettingsManager
    settings = SettingsManager()
    width = settings.settings["resolution"]["width"]
    height = settings.settings["resolution"]["height"]

    # Create and run the loading animation with game resolution
    loading_animation = LoadingAnimation(screen_width=width, screen_height=height)
    
    # Run the loading animation synchronously
    if loading_animation.run():
        print("Loading complete, starting game...")
        
        # Get the screen from loading animation for seamless transition
        screen = loading_animation.screen
        
        # Create and run the game with the existing screen
        game = Game(existing_screen=screen)
        game.run()
    else:
        print("Loading cancelled or failed")
    
    # Clean up
    pygame.quit()
    sys.exit()
    
if __name__ == "__main__":
    main()