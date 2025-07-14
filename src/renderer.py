import pygame
from pygame.locals import *
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

class Renderer:
    def __init__(self, width=1024, height=768, cube_path="utils/single_cube.obj"):
        # Initialize properties
        self.width = width
        self.height = height
        self.cube_path = cube_path
        
        # OpenGL cube data
        self.obj_vertices = []
        self.obj_faces = []
        self.single_cube_display_list = None
        
        # 3x3x3 cube positions and colors
        self.cube_size = 1.2  # Larger size for better appearance
        self.cube_spacing = 0.52  # Negative spacing to make cubes overlap slightly
        self.cubes = []
        
        # Rubik's cube face colors - define colors before initializing cubes
        self.cube_colors = {
            'white': (1.0, 1.0, 1.0),     # Top
            'yellow': (1.0, 1.0, 0.0),    # Bottom
            'red': (1.0, 0.0, 0.0),       # Right
            'orange': (1.0, 0.5, 0.0),    # Left
            'blue': (0.0, 0.0, 1.0),      # Front
            'green': (0.0, 1.0, 0.0),     # Back
            'black': (0.1, 0.1, 0.1)      # Internal faces
        }
        
        # Now initialize cubes after colors are defined
        self.initialize_cubes()
        
        # Load the single cube model
        self.load_obj(cube_path)
        
        # Initialize OpenGL settings
        self.setup_opengl()
        
        # Create optimized display list for single cube
        self.create_single_cube_display_list()
        
        # Store camera rotation for manual control
        self.rotation_x = 0
        self.rotation_y = 0
    
    def initialize_cubes(self):
        """Initialize the position and colors for each small cube in the 3x3x3 grid"""
        self.cubes = []
        # Create 3x3x3 grid of cubes
        # Scale factor to adjust the overall size of the Rubik's Cube - smaller value brings cubes closer
        scale_factor = 0.85
        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    # Calculate position with proper scaling for a tighter cube
                    position = [
                        x * self.cube_spacing * scale_factor,
                        y * self.cube_spacing * scale_factor,
                        z * self.cube_spacing * scale_factor
                    ]
                    
                    # Create color arrays for each face of this cube
                    # Order: top, bottom, right, left, front, back
                    colors = [
                        self.cube_colors['black'],  # Top (will be replaced if it's visible)
                        self.cube_colors['black'],  # Bottom (will be replaced if it's visible)
                        self.cube_colors['black'],  # Right (will be replaced if it's visible)
                        self.cube_colors['black'],  # Left (will be replaced if it's visible)
                        self.cube_colors['black'],  # Front (will be replaced if it's visible)
                        self.cube_colors['black'],  # Back (will be replaced if it's visible)
                    ]
                    
                    # Assign proper colors based on position
                    if y == 1:  # Top layer
                        colors[0] = self.cube_colors['white']
                    if y == -1:  # Bottom layer
                        colors[1] = self.cube_colors['yellow']
                    if x == 1:  # Right layer
                        colors[2] = self.cube_colors['red']
                    if x == -1:  # Left layer
                        colors[3] = self.cube_colors['orange']
                    if z == 1:  # Front layer
                        colors[4] = self.cube_colors['blue']
                    if z == -1:  # Back layer
                        colors[5] = self.cube_colors['green']
                    
                    self.cubes.append({
                        'position': position,
                        'colors': colors
                    })
        
    def load_obj(self, filename):
        """Load vertices, faces, and normals from OBJ file"""
        vertices = []
        faces = []
        normals = []
        
        with open(filename, 'r') as file:
            for line in file:
                if line.startswith('v '):
                    # Parse vertex coordinates
                    coords = line.strip().split()[1:]
                    vertices.append([float(coord) for coord in coords])
                elif line.startswith('vn '):
                    # Parse normals
                    coords = line.strip().split()[1:]
                    normals.append([float(coord) for coord in coords])
                elif line.startswith('f '):
                    # Parse face indices (convert from 1-based to 0-based)
                    face_data = line.strip().split()[1:]
                    face = []
                    for vertex_data in face_data:
                        # Handle cases like "1/1/1" or "1//1" or just "1"
                        vertex_index = int(vertex_data.split('/')[0]) - 1
                        face.append(vertex_index)
                    faces.append(face)
        
        self.obj_vertices = vertices
        self.obj_faces = faces
        
    def setup_opengl(self):
        """Initialize OpenGL settings"""
        # Reset matrices
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # Set up perspective projection
        gluPerspective(45, (self.width/self.height), 0.1, 50.0)
        # Set the viewport to match window size
        glViewport(0, 0, self.width, self.height)
        
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        
        # Enable multiple light sources
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHT1)
        glEnable(GL_LIGHT2)
        
        # Increase ambient light for all faces to have base illumination
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.4, 0.4, 0.4, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.6, 0.6, 0.6, 1])
        glLightfv(GL_LIGHT0, GL_POSITION, [2, 2, 2, 1])  # Front-top-right
        
        # Add light from opposite direction
        glLightfv(GL_LIGHT1, GL_AMBIENT, [0.2, 0.2, 0.2, 1])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [0.4, 0.4, 0.4, 1])
        glLightfv(GL_LIGHT1, GL_POSITION, [-2, -2, -2, 1])  # Back-bottom-left
        
        # Add a third light for better coverage
        glLightfv(GL_LIGHT2, GL_AMBIENT, [0.2, 0.2, 0.2, 1])
        glLightfv(GL_LIGHT2, GL_DIFFUSE, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT2, GL_POSITION, [-2, 2, -2, 1])  # Back-top-left
        
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

        # Position the camera at a closer distance to see the entire 3x3x3 cube
        glTranslatef(0.0, 0.0, -4.0)

    def create_single_cube_display_list(self):
        """Create optimized display list for the single cube"""
        self.single_cube_display_list = glGenLists(1)
        
        glNewList(self.single_cube_display_list, GL_COMPILE)
        
        # Enable smooth shading
        glShadeModel(GL_SMOOTH)
        
        # Group faces by orientation (assuming cube faces are axis-aligned)
        top_faces = []
        bottom_faces = []
        right_faces = []
        left_faces = []
        front_faces = []
        back_faces = []
        
        # Identify which faces belong to which orientation based on normals
        for i, face in enumerate(self.obj_faces):
            # Calculate face normal by using cross product of two edges
            v0 = self.obj_vertices[face[0]]
            v1 = self.obj_vertices[face[1]]
            v2 = self.obj_vertices[face[2]]
            
            # Calculate two edges
            edge1 = [v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]]
            edge2 = [v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]]
            
            # Cross product to get normal
            normal = [
                edge1[1] * edge2[2] - edge1[2] * edge2[1],
                edge1[2] * edge2[0] - edge1[0] * edge2[2],
                edge1[0] * edge2[1] - edge1[1] * edge2[0]
            ]
            
            # Normalize
            length = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
            if length > 0:
                normal = [n/length for n in normal]
            
            # Identify face orientation by dominant normal component
            abs_normal = [abs(n) for n in normal]
            max_idx = abs_normal.index(max(abs_normal))
            
            if max_idx == 1:  # Y-axis
                if normal[1] > 0:
                    top_faces.append(face)
                else:
                    bottom_faces.append(face)
            elif max_idx == 0:  # X-axis
                if normal[0] > 0:
                    right_faces.append(face)
                else:
                    left_faces.append(face)
            elif max_idx == 2:  # Z-axis
                if normal[2] > 0:
                    front_faces.append(face)
                else:
                    back_faces.append(face)
        
        # Draw each face with appropriate color index (colors will be applied when rendering)
        self.draw_faces(top_faces, 0)      # Top faces - color index 0
        self.draw_faces(bottom_faces, 1)   # Bottom faces - color index 1
        self.draw_faces(right_faces, 2)    # Right faces - color index 2
        self.draw_faces(left_faces, 3)     # Left faces - color index 3
        self.draw_faces(front_faces, 4)    # Front faces - color index 4
        self.draw_faces(back_faces, 5)     # Back faces - color index 5
        
        glEndList()
    
    def draw_faces(self, faces, color_index):
        """Draw a group of faces with a specific color index"""
        # Define colors for each face index
        face_colors = [
            self.cube_colors['white'],   # 0 - Top
            self.cube_colors['yellow'],  # 1 - Bottom
            self.cube_colors['red'],     # 2 - Right
            self.cube_colors['orange'],  # 3 - Left
            self.cube_colors['blue'],    # 4 - Front
            self.cube_colors['green'],   # 5 - Back
        ]
        
        # Set color for this face group
        glColor3fv(face_colors[color_index])
        
        for face in faces:
            if len(face) == 3:  # Triangle
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:  # Quad
                glBegin(GL_QUADS)
            else:  # Polygon
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        
    def rotate_camera(self, azimuth=0, elevation=0):
        """Rotate camera around the cube
        
        Args:
            azimuth: Horizontal rotation angle (around y-axis)
            elevation: Vertical rotation angle (around x-axis)
        """
        self.rotation_y += azimuth
        self.rotation_x += elevation
        
        # Keep rotations within reasonable bounds
        self.rotation_x = max(-90, min(90, self.rotation_x))
        
    def render_cube(self):
        """Render the 3x3x3 Rubik's cube using individual cubes"""
        if not self.single_cube_display_list:
            return
            
        # Render each small cube
        for cube in self.cubes:
            position = cube['position']
            colors = cube['colors']
            
            glPushMatrix()
            
            # Position this cube
            glTranslatef(position[0], position[1], position[2])
            
            # Scale the cube to appropriate size - much larger cubes for better visibility
            glScalef(0.8, 0.8, 0.8)  # Make cubes even bigger to fill the space better
            
            # Draw each face with its proper color
            glCallList(self.single_cube_display_list)
            
            glPopMatrix()
        
    def render_frame(self):
        """Render a frame and return the surface (for compatibility with existing code)"""
        # Check if viewport matches the current dimensions
        viewport = glGetIntegerv(GL_VIEWPORT)
        if viewport[2] != self.width or viewport[3] != self.height:
            # Viewport doesn't match our dimensions, reset it
            glViewport(0, 0, self.width, self.height)
            
            # Also reset projection matrix
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(45, (self.width/self.height), 0.1, 50.0)
            glMatrixMode(GL_MODELVIEW)
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        glPushMatrix()
        
        # Apply rotations
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        # Render the cube
        self.render_cube()
        
        glPopMatrix()
        
        # For compatibility, return None since OpenGL renders directly to screen
        return None
        
    def close(self):
        """Clean up resources"""
        if self.single_cube_display_list:
            glDeleteLists(self.single_cube_display_list, 1)
            self.single_cube_display_list = None