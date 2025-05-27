import pygame

def main():
    
    print("Starting the game...")
    
    from game import Game
    pygame.init()
    
    # Initialize the game window
    game = Game()
    game.run()
    
if __name__ == "__main__":
    main()