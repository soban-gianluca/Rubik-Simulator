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
        self.face_colors = [
            [1.0, 1.0, 1.0],  # White (Up)
            [1.0, 1.0, 0.0],  # Yellow (Down)
            [0.0, 0.0, 1.0],  # Blue (Front)
            [0.0, 1.0, 0.0],  # Green (Back)
            [1.0, 0.0, 0.0],  # Red (Right)
            [1.0, 0.5, 0.0],  # Orange (Left)
        ]
        
        # Apply colors and setup display
        self.color_cube()
        self.plotter.set_background('white')
        
    def color_cube(self):
        """Apply colors to different parts of the cube mesh"""
        # Get mesh bounds and points
        bounds = self.mesh.bounds
        points = self.mesh.points
        
        # Create RGB color array
        scalars = np.zeros((self.mesh.n_points, 3))
        
        # Tolerance for face detection
        tol = 0.01
        
        # Apply colors based on position
        for i, (x, y, z) in enumerate(points):
            if abs(z - bounds[5]) < tol:      # Top face (White)
                scalars[i] = self.face_colors[0]
            elif abs(z - bounds[4]) < tol:    # Bottom face (Yellow)
                scalars[i] = self.face_colors[1]
            elif abs(y - bounds[3]) < tol:    # Front face (Blue)
                scalars[i] = self.face_colors[2]
            elif abs(y - bounds[2]) < tol:    # Back face (Green)
                scalars[i] = self.face_colors[3]
            elif abs(x - bounds[1]) < tol:    # Right face (Red)
                scalars[i] = self.face_colors[4]
            elif abs(x - bounds[0]) < tol:    # Left face (Orange)
                scalars[i] = self.face_colors[5]
            else:                             # Interior (black)
                scalars[i] = [0.2, 0.2, 0.2]
        
        self.plotter.add_mesh(self.mesh, scalars=scalars, rgb=True)
        
    def rotate_camera(self, azimuth=0):
        """Rotate camera around the cube"""
        self.plotter.camera.azimuth += azimuth
        
    def render_frame(self):
        """Render a frame and return as pygame surface"""
        image = self.plotter.screenshot(return_img=True)
        img_height, img_width, _ = image.shape
        return pygame.image.frombuffer(image.tobytes(), 
                                      (img_width, img_height), 
                                      "RGB")
    
    def close(self):
        self.plotter.close()