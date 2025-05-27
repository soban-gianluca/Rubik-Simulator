import pyvista as pv
import pygame

# Initialize PyGame
pygame.init()
width, height = 800, 600
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Rubik's Cube Visualizer")

# Read the mesh
mesh = pv.read("utils/Rubik's Cube.obj")

# Create a PyVista plotter with off-screen rendering
plotter = pv.Plotter(off_screen=True, window_size=(width, height))
plotter.add_mesh(mesh, show_edges=True)
plotter.set_background('white')

# Main loop
running = True
rotation_speed = 0.01
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    # Rotate camera
    plotter.camera.azimuth += rotation_speed * 100
    
    # Render frame
    image = plotter.screenshot(transparent_background=False, return_img=True)
    
    # Convert to pygame surface
    img_height, img_width, _ = image.shape
    pygame_image = pygame.image.frombuffer(image.tobytes(), 
                                          (img_width, img_height), 
                                          "RGB")
    
    # Draw to screen
    screen.blit(pygame_image, (0, 0))
    pygame.display.flip()
    
    # Control the frame rate
    pygame.time.wait(10)

# Clean up
plotter.close()
pygame.quit()