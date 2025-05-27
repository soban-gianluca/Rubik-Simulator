import pygame
import sys
from renderer import Renderer

class Game:
    def __init__(self):
        # Initialize pygame
        pygame.init()
        self.width, self.height = 800, 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Rubik's Cube Simulator")
        self.clock = pygame.time.Clock()
        
        # Initialize renderer
        self.renderer = Renderer(self.width, self.height)
        
        # Game state
        self.running = True
        self.auto_rotate = True  # Auto rotation by default
        
        # Print instructions
        print("Controls:")
        print("  Space: Toggle auto-rotation")
        print("  Left/Right arrows: Manual rotation")
        print("  ESC: Quit")

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                # Quit
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.auto_rotate = not self.auto_rotate
                    
            # Handle key presses for manual rotation
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                self.renderer.rotate_camera(1)
            if keys[pygame.K_RIGHT]:
                self.renderer.rotate_camera(-1)
    
    def update(self):
        # Auto-rotate if enabled
        if self.auto_rotate:
            self.renderer.rotate_camera(0.5)
        
    def render(self):
        # Render the cube
        pygame_image = self.renderer.render_frame()
        self.screen.blit(pygame_image, (0, 0))
        pygame.display.flip()
        
    def run(self):
        # Main game loop
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)  # 60 FPS
            
        # Clean up
        self.renderer.close()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Game()
    game.run()