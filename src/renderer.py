import pygame
from pygame.locals import *
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

class Renderer:
    def __init__(self, width=1024, height=768, cube_path="utils/Rubik's_cube2.obj"):
        # Initialize properties
        self.width = width
        self.height = height
        self.cube_path = cube_path
        
        # OpenGL cube data
        self.obj_vertices = []
        self.obj_faces = []
        self.display_list = None
        
        # Rubik's cube face colors
        self.cube_colors = {
            'white': (1.0, 1.0, 1.0),
            'yellow': (1.0, 1.0, 0.0),
            'red': (1.0, 0.0, 0.0),
            'orange': (1.0, 0.5, 0.0),
            'blue': (0.0, 0.0, 1.0),
            'green': (0.0, 1.0, 0.0),
            'black': (0.1, 0.1, 0.1)  # For edges/grid lines
        }
        
        # Load the cube model
        self.load_obj(cube_path)
        
        # Initialize OpenGL settings
        self.setup_opengl()
        
        # Create optimized display list
        self.create_display_list()
        
        # Store camera rotation for manual control
        self.rotation_x = 0
        self.rotation_y = 0
        
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

        glTranslatef(0.0, 0.0, -5)
        
    def get_face_color(self, face_vertices):
        """Determine face color based on face normal/position"""
        # Calculate face center
        center = [0, 0, 0]
        for vertex_idx in face_vertices:
            vertex = self.obj_vertices[vertex_idx]
            center[0] += vertex[0]
            center[1] += vertex[1]
            center[2] += vertex[2]
        
        center = [coord / len(face_vertices) for coord in center]
        
        # Determine color based on which face of the cube this is
        # These thresholds may need adjustment based on your OBJ file scale
        threshold = 0.84
        
        if center[1] > threshold:  # Top face
            return self.cube_colors['white']
        elif center[1] < -threshold:  # Bottom face
            return self.cube_colors['yellow']
        elif center[0] > threshold:  # Right face
            return self.cube_colors['red']
        elif center[0] < -threshold:  # Left face
            return self.cube_colors['orange']
        elif center[2] > threshold:  # Front face
            return self.cube_colors['blue']
        elif center[2] < -threshold:  # Back face
            return self.cube_colors['green']
        else:
            return self.cube_colors['black']  # Internal faces/edges

    def create_display_list(self):
        """Create optimized display list for the cube"""
        self.display_list = glGenLists(1)
        
        glNewList(self.display_list, GL_COMPILE)
        
        # Enable smooth shading
        glShadeModel(GL_SMOOTH)
        
        for face in self.obj_faces:
            color = self.get_face_color(face)
            glColor3fv(color)
            
            if len(face) == 3:  # Triangle
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:  # Quad
                glBegin(GL_QUADS)
            else:  # Polygon
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        
        glEndList()
        
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
        """Render the optimized cube using display list"""
        if self.display_list:
            glCallList(self.display_list)
        
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
        if self.display_list:
            glDeleteLists(self.display_list, 1)
            self.display_list = None