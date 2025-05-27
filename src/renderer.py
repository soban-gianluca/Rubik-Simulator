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
        
        # Define colors for each face (RGB format)
        # White, Yellow, Blue, Green, Red, Orange
        self.face_colors = [
            [1.0, 1.0, 1.0],  # White (Up)
            [1.0, 1.0, 0.0],  # Yellow (Down)
            [0.0, 0.0, 1.0],  # Blue (Front)
            [0.0, 1.0, 0.0],  # Green (Back)
            [1.0, 0.0, 0.0],  # Red (Right)
            [1.0, 0.5, 0.0],  # Orange (Left)
        ]
        
        # Apply colors to the mesh
        self.color_cube()
        
        # Set display properties
        self.plotter.set_background('white')
        
    def color_cube(self):
        """Apply colors to different parts of the cube mesh"""
        # Get mesh bounds to determine face positions
        bounds = self.mesh.bounds
        x_min, x_max = bounds[0], bounds[1]
        y_min, y_max = bounds[2], bounds[3]
        z_min, z_max = bounds[4], bounds[5]
        
        # Create scalars array for coloring
        n_points = self.mesh.n_points
        scalars = np.zeros((n_points, 3))  # RGB array
        
        # Get point coordinates
        points = self.mesh.points
        
        # Tolerance for face detection
        tol = 0.01
        
        # Apply colors based on position
        for i, point in enumerate(points):
            x, y, z = point
            
            # Top face (White)
            if abs(z - z_max) < tol:
                scalars[i] = self.face_colors[0]
            # Bottom face (Yellow)
            elif abs(z - z_min) < tol:
                scalars[i] = self.face_colors[1]
            # Front face (Blue)
            elif abs(y - y_max) < tol:
                scalars[i] = self.face_colors[2]
            # Back face (Green)
            elif abs(y - y_min) < tol:
                scalars[i] = self.face_colors[3]
            # Right face (Red)
            elif abs(x - x_max) < tol:
                scalars[i] = self.face_colors[4]
            # Left face (Orange)
            elif abs(x - x_min) < tol:
                scalars[i] = self.face_colors[5]
            # Interior points (black)
            else:
                scalars[i] = [0.2, 0.2, 0.2]
        
        # Add the colored mesh to the plotter
        self.plotter.add_mesh(self.mesh, scalars=scalars, rgb=True, show_edges=True)
        
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