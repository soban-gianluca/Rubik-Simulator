import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

class ModelRenderer:
    def __init__(self, obj_file_path):
        self.vertices = []
        self.faces = []
        self.load_obj(obj_file_path)
    
    def load_obj(self, file_path):
        """Load a simple OBJ file, only considering vertices and faces."""
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if line.startswith('v '):  # Vertex
                        parts = line.strip().split()
                        if len(parts) >= 4:  # Ensure we have x, y, z coordinates
                            vertex = [float(parts[1]), float(parts[2]), float(parts[3])]
                            self.vertices.append(vertex)
                    elif line.startswith('f '):  # Face
                        parts = line.strip().split()
                        face = []
                        for i in range(1, len(parts)):
                            # Extract just the vertex index (ignore texture/normal indices)
                            vertex_idx = int(parts[i].split('/')[0]) - 1
                            face.append(vertex_idx)
                        self.faces.append(face)
            print(f"Loaded {len(self.vertices)} vertices and {len(self.faces)} faces")
        except Exception as e:
            print(f"Error loading model: {e}")
    
    def setup_gl(self, width, height):
        """Basic OpenGL setup."""
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (width / height), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_DEPTH_TEST)
    
    def render(self, rotation_x=0, rotation_y=0):
        """Render the model with simple white color."""
        # Clear the screen
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Reset the view
        glLoadIdentity()
        
        # Move back a bit to see the model
        glTranslatef(0, 0, -5)
        
        # Apply rotations
        glRotatef(rotation_x, 1, 0, 0)
        glRotatef(rotation_y, 0, 1, 0)
        
        # Draw the model faces as simple white polygons
        glColor3f(1, 1, 1)  # White color
        for face in self.faces:
            # Draw each face
            glBegin(GL_POLYGON)
            for vertex_idx in face:
                # Make sure we don't go out of bounds
                if 0 <= vertex_idx < len(self.vertices):
                    glVertex3fv(self.vertices[vertex_idx])
            glEnd()
        
        # Draw the model edges for better visibility
        glColor3f(0, 0, 0)  # Black color for edges
        for face in self.faces:
            glBegin(GL_LINE_LOOP)
            for vertex_idx in face:
                if 0 <= vertex_idx < len(self.vertices):
                    glVertex3fv(self.vertices[vertex_idx])
            glEnd()
