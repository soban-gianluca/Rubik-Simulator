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
        
        # Full cube structure (3x3x3)
        self.cube_pieces = []
        self.cube_piece_displays = []

        self.spacing = 1.08
        
        # Load the single cube model
        self.load_obj(cube_path)
        
        # Initialize OpenGL settings
        self.setup_opengl()
        
        # Create the full Rubik's Cube
        self.create_rubiks_cube()
        
        # Store camera rotation for manual control
        self.rotation_x = 20  # Initial tilt to see more faces
        self.rotation_y = 45  # Initial rotation to see more faces
        
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
        gluPerspective(45, (self.width/self.height), 0.1, 50.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        
        # Enable multiple light sources
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHT1)
        glEnable(GL_LIGHT2)
        
        # Increase ambient light for all faces to have base illumination
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.5, 0.5, 0.5, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.7, 0.7, 0.7, 1])
        glLightfv(GL_LIGHT0, GL_POSITION, [2, 2, 2, 1])  # Front-top-right
        
        # Add light from opposite direction
        glLightfv(GL_LIGHT1, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [0.5, 0.5, 0.5, 1])
        glLightfv(GL_LIGHT1, GL_POSITION, [-2, -2, -2, 1])  # Back-bottom-left
        
        # Add a third light for better coverage
        glLightfv(GL_LIGHT2, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT2, GL_DIFFUSE, [0.4, 0.4, 0.4, 1])
        glLightfv(GL_LIGHT2, GL_POSITION, [-2, 2, -2, 1])  # Back-top-left
        
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

        # Move back a bit to see the full cube
        glTranslatef(0.0, 0.0, -6)
    
    def create_rubiks_cube(self):
        """Create a full 3x3x3 Rubik's Cube from the single cube model"""
        # Clear previous displays if any
        if self.cube_piece_displays:
            for display_list in self.cube_piece_displays:
                glDeleteLists(display_list, 1)
            self.cube_piece_displays = []
        
        # Initialize the cube pieces positions
        self.cube_pieces = []
        
        # Create a 3x3x3 grid of cube pieces
        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    # Position of this cube piece
                    position = (
                        x * self.spacing, 
                        y * self.spacing, 
                        z * self.spacing
                    )
                    
                    # Store the piece info
                    self.cube_pieces.append({
                        'position': position,
                        'rotation': (0, 0, 0)  # No initial rotation
                    })
        
        # Create display lists for each cube piece
        for piece in self.cube_pieces:
            display_list = self.create_cube_piece_display(piece['position'])
            self.cube_piece_displays.append(display_list)
    
    def create_cube_piece_display(self, position):
        """Create a display list for a single cube piece at the specified position"""
        display_list = glGenLists(1)
        
        glNewList(display_list, GL_COMPILE)
        
        # Enable smooth shading
        glShadeModel(GL_SMOOTH)
        
        # Save current matrix
        glPushMatrix()
        
        # Position the cube piece
        glTranslatef(position[0], position[1], position[2])
        
        
        scale_factor = 1.9
        glScalef(scale_factor, scale_factor, scale_factor)
        
        # Determine which faces are visible and what colors they should have
        for face in self.obj_faces:
            # Calculate face center
            center = [0, 0, 0]
            for vertex_idx in face:
                vertex = self.obj_vertices[vertex_idx]
                center[0] += vertex[0]
                center[1] += vertex[1]
                center[2] += vertex[2]
            
            center = [coord / len(face) for coord in center]
            
            # Calculate face normal for better color determination
            if len(face) >= 3:
                # Get the first three vertices of the face
                v0 = self.obj_vertices[face[0]]
                v1 = self.obj_vertices[face[1]]
                v2 = self.obj_vertices[face[2]]
                
                # Calculate two edges
                edge1 = [v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]]
                edge2 = [v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]]
                
                # Calculate cross product to get normal
                normal = [
                    edge1[1]*edge2[2] - edge1[2]*edge2[1],
                    edge1[2]*edge2[0] - edge1[0]*edge2[2],
                    edge1[0]*edge2[1] - edge1[1]*edge2[0]
                ]
                
                # Normalize the normal vector
                length = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
                if length > 0:
                    normal = [n/length for n in normal]
            else:
                # Default normal if face doesn't have enough vertices
                normal = [0, 0, 1]
            
            # Transform face center to get global position
            global_x = center[0] + position[0]
            global_y = center[1] + position[1]
            global_z = center[2] + position[2]
            
            # Determine color based on face position and normal
            color = self.get_piece_face_color(global_x, global_y, global_z, position, normal)
            
            # Draw the face
            glColor3fv(color)
            
            if len(face) == 3:  # Triangle
                glBegin(GL_TRIANGLES)
                # Add normal before vertices for better lighting
                glNormal3fv(normal)
                for vertex_index in face:
                    glVertex3fv(self.obj_vertices[vertex_index])
                
            elif len(face) == 4:  # Quad
                glBegin(GL_QUADS)
                # Add normal before vertices for better lighting
                glNormal3fv(normal)
                for vertex_index in face:
                    glVertex3fv(self.obj_vertices[vertex_index])
                
            else:  # Polygon
                glBegin(GL_POLYGON)
                # Add normal before vertices for better lighting
                glNormal3fv(normal)
                for vertex_index in face:
                    glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        
        # Restore matrix
        glPopMatrix()
        
        glEndList()
        return display_list
    
    def get_piece_face_color(self, global_x, global_y, global_z, piece_position, normal):
        """Determine the color of a face based on its global position and orientation"""
        threshold = 0.4  # Reduced threshold for better detection
        piece_x, piece_y, piece_z = piece_position
        
        # Find dominant normal direction
        abs_normal = [abs(n) for n in normal]
        max_idx = abs_normal.index(max(abs_normal))
        
        # Determine if this face is on the outside of the cube
        is_outer_piece = (abs(piece_x) > 0.9 or abs(piece_y) > 0.9 or abs(piece_z) > 0.9)
        
        if not is_outer_piece:
            return self.cube_colors['black']  # Inner piece, always black
            
        # Determine face direction based on the normal
        if max_idx == 1:  # Y-axis dominant
            if normal[1] > 0 and piece_y > 0.9:
                return self.cube_colors['white']  # Top face
            elif normal[1] < 0 and piece_y < -0.9:
                return self.cube_colors['yellow']  # Bottom face
                
        elif max_idx == 0:  # X-axis dominant
            if normal[0] > 0 and piece_x > 0.9:
                return self.cube_colors['red']  # Right face
            elif normal[0] < 0 and piece_x < -0.9:
                return self.cube_colors['orange']  # Left face
                
        elif max_idx == 2:  # Z-axis dominant
            if normal[2] > 0 and piece_z > 0.9:
                return self.cube_colors['blue']  # Front face
            elif normal[2] < 0 and piece_z < -0.9:
                return self.cube_colors['green']  # Back face
        
        # Internal faces or edges
        return self.cube_colors['black']
    
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
    
    def create_display_list(self):
        """Create a display list for the cube (compatibility with game.py)"""
        # This method exists for compatibility with game.py
        # It's called when changing resolution
        self.create_rubiks_cube()
        
    def render_frame(self):
        """Render a frame and return the surface (for compatibility with existing code)"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        glPushMatrix()
        
        # Apply global rotations
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        # Render each cube piece
        for display_list in self.cube_piece_displays:
            glCallList(display_list)
        
        glPopMatrix()
        
        # For compatibility, return None since OpenGL renders directly to screen
        return None
    
    def close(self):
        """Clean up resources"""
        # Clean up display lists
        if self.cube_piece_displays:
            for display_list in self.cube_piece_displays:
                glDeleteLists(display_list, 1)
            self.cube_piece_displays = []