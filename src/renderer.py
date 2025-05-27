import pyvista as pv
import pygame
import numpy as np

class Renderer:
    def __init__(self, width=800, height=600, cube_path="utils/Rubik's Cube.obj"):
        # Initialize properties
        self.width = width
        self.height = height
        
        # Initialize mesh and plotter
        self.mesh = pv.read(cube_path)
        self.plotter = pv.Plotter(off_screen=True, window_size=(width, height))
        self.plotter.add_mesh(self.mesh, show_edges=True)
        self.plotter.set_background('white')
        
    def rotate_camera(self, azimuth=0):
        """Simple camera rotation around the cube"""
        self.plotter.camera.azimuth += azimuth
        
    def render_frame(self):
        """Render a single frame and return as pygame surface"""
        # Render to image
        image = self.plotter.screenshot(transparent_background=False, return_img=True)
        
        # Convert to pygame surface
        img_height, img_width, _ = image.shape
        pygame_image = pygame.image.frombuffer(image.tobytes(), 
                                            (img_width, img_height), 
                                            "RGB")
        return pygame_image
    
    def close(self):
        """Close the renderer"""
        self.plotter.close()

# If run as a standalone script, demonstrate basic functionality
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Rubik's Cube Visualizer")
    
    renderer = Renderer()
    clock = pygame.time.Clock()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        # Auto-rotate for demo
        renderer.rotate_camera(azimuth=1)
        
        # Render and display
        pygame_image = renderer.render_frame()
        screen.blit(pygame_image, (0, 0))
        pygame.display.flip()
        
        # Control frame rate
        clock.tick(30)
    
    renderer.close()
    pygame.quit()