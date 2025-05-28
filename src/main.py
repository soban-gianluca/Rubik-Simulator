import pygame

def main():
    
    print("Initializing the game...")
    
    pygame.init()
    
    from game import Game
    
    game = Game()
    game.run()
    
if __name__ == "__main__":
    main()