import pygame
from pygame.locals import *
import numpy as np
import math
import time
from OpenGL.GL import *
from OpenGL.GLU import *

class Renderer:
    def __init__(self, width=1024, height=768, cube_path="utils/cube.obj"):
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
        
        # Animation system
        self.is_animating = False
        self.animation_start_time = 0
        self.animation_duration = 0.3  # 300ms animation
        self.animating_face = None
        self.animation_axis = None
        self.animation_angle_total = 0
        self.animation_clockwise = True
        self.animation_cubes = []  # Cubes that are part of the rotating face
        self.pending_move = None  # Move to execute when animation completes
        
        # Skybox properties
        self.skybox_texture = None
        self.skybox_display_list = None
        self.skybox_size = 20.0  # Large size to encompass the scene
        
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
        
        # Import and initialize the Rubik's cube logic
        from rubiks_cube import RubiksCube
        self.rubiks_cube = RubiksCube()
        
        # Now initialize cubes after colors are defined
        self.initialize_cubes()
        
        # Load the single cube model
        self.load_obj(cube_path)
        
        # Initialize OpenGL settings
        self.setup_opengl()
        
        # Load skybox texture and create cylindrical skybox
        self.load_skybox_texture("utils/skybox.jpg")
        self.create_cylindrical_skybox_display_list()  # Changed from spherical to cylindrical
        
        # Create optimized display list for single cube
        self.create_display_list()
        
        # Store camera rotation for manual control
        self.rotation_x = 0
        self.rotation_y = 0

    def load_skybox_texture(self, image_path):
        """Load skybox texture from image file"""
        try:
            # Load image using pygame
            skybox_image = pygame.image.load(image_path)
            skybox_image = pygame.transform.flip(skybox_image, False, True)  # Flip vertically for OpenGL
            
            # Get image data
            image_data = pygame.image.tostring(skybox_image, 'RGB')
            image_width, image_height = skybox_image.get_size()
            
            # Generate and bind texture
            self.skybox_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.skybox_texture)
            
            # CRITICAL: Set texture parameters for seamless panoramic wrapping
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)      # Horizontal repeat for 360°
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)  # Vertical clamp to prevent artifacts
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            
            # Upload texture data
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image_width, image_height, 0, GL_RGB, GL_UNSIGNED_BYTE, image_data)
            
            print(f"Skybox texture loaded successfully: {image_width}x{image_height}")
            
        except Exception as e:
            print(f"Failed to load skybox texture: {e}")
            # Create a simple gradient texture as fallback
            self.create_fallback_skybox_texture()

    def create_fallback_skybox_texture(self):
        """Create a simple gradient texture if image loading fails"""
        # Create a simple 64x64 gradient texture
        size = 64
        texture_data = []
        
        for y in range(size):
            for x in range(size):
                # Create a blue to white gradient from bottom to top
                intensity = y / size
                r = int(135 + (255 - 135) * intensity)  # Sky blue to white
                g = int(206 + (255 - 206) * intensity)
                b = int(235 + (255 - 235) * intensity)
                texture_data.extend([r, g, b])
        
        # Generate and bind texture
        self.skybox_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.skybox_texture)
        
        # Set texture parameters
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        
        # Upload texture data
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size, 0, GL_RGB, GL_UNSIGNED_BYTE, bytes(texture_data))
        
        print("Using fallback gradient skybox texture")

    def create_cylindrical_skybox_display_list(self):
        """Create a cylindrical skybox for seamless panoramic image mapping"""
        if not self.skybox_texture:
            return
        
        self.skybox_display_list = glGenLists(1)
        glNewList(self.skybox_display_list, GL_COMPILE)
        
        # Enable texturing
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.skybox_texture)
        glColor3f(1.0, 1.0, 1.0)
        
        # Create a cylinder for the skybox
        radius = self.skybox_size
        height = self.skybox_size * 2  # Make cylinder tall enough
        slices = 64  # Number of vertical slices around the cylinder
        
        # FIXED: Adjust texture coordinate scaling to reduce horizontal stretching
        # Instead of mapping full texture across 360°, use a smaller portion
        texture_scale = 2.0  # Increase this value to reduce stretching (try 1.5, 2.0, 2.5)
        
        # CRITICAL FIX: Draw the curved side with proper texture wrapping
        glBegin(GL_QUAD_STRIP)
        for i in range(slices + 1):  # +1 to complete the circle
            angle = 2 * math.pi * i / slices
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            
            # FIXED: Scale texture coordinates to reduce horizontal stretching
            if i == slices:
                u = texture_scale  # Explicitly set for the seam
            else:
                u = (float(i) / slices) * texture_scale
        
            # Bottom vertex
            glTexCoord2f(u, 0.0)
            glVertex3f(x, -height/2, z)
            
            # Top vertex  
            glTexCoord2f(u, 1.0)
            glVertex3f(x, height/2, z)
        
        glEnd()
        
        # Optional: Remove caps entirely to avoid texture stretching issues
        # If you want to keep caps, use a solid color instead of texture
        
        glDisable(GL_TEXTURE_2D)
        glEndList()

    def render_skybox(self):
        """Render the spherical skybox"""
        if not self.skybox_display_list:
            return
        
        # Save current matrix
        glPushMatrix()
        
        # Disable depth testing and lighting for skybox
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        
        # Move skybox with camera (no translation, only rotation)
        # The skybox should always be centered on the camera
        glLoadIdentity()
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        # Render the skybox
        glCallList(self.skybox_display_list)
        
        # Re-enable depth testing and lighting
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        
        # Restore matrix
        glPopMatrix()

    def start_face_animation(self, face_name, clockwise=True):
        """Start animation for a face rotation"""
        if self.is_animating:
            return False  # Already animating
        
        # Define which cubes belong to each face and rotation axis
        face_definitions = {
            'R': {'axis': (1, 0, 0), 'cubes': [(1, y, z) for y in [-1, 0, 1] for z in [-1, 0, 1]]},
            'L': {'axis': (-1, 0, 0), 'cubes': [(-1, y, z) for y in [-1, 0, 1] for z in [-1, 0, 1]]},
            'U': {'axis': (0, 1, 0), 'cubes': [(x, 1, z) for x in [-1, 0, 1] for z in [-1, 0, 1]]},
            'D': {'axis': (0, -1, 0), 'cubes': [(x, -1, z) for x in [-1, 0, 1] for z in [-1, 0, 1]]},
            'F': {'axis': (0, 0, 1), 'cubes': [(x, y, 1) for x in [-1, 0, 1] for y in [-1, 0, 1]]},
            'B': {'axis': (0, 0, -1), 'cubes': [(x, y, -1) for x in [-1, 0, 1] for y in [-1, 0, 1]]}
        }
        
        if face_name not in face_definitions:
            return False
        
        # Set up animation
        self.is_animating = True
        self.animation_start_time = time.time()
        self.animating_face = face_name
        self.animation_axis = face_definitions[face_name]['axis']
        
        # This is the key part: Make sure the animation angle matches the logical model
        # direction we set in rubiks_cube.py
        self.animation_angle_total = 90 if clockwise else -90
        self.animation_clockwise = clockwise
        
        # Find cubes that are part of this face
        face_cube_positions = face_definitions[face_name]['cubes']
        self.animation_cubes = []
        
        for cube in self.cubes:
            if cube['grid_pos'] in face_cube_positions:
                self.animation_cubes.append(cube)
        
        return True
    
    def update_animation(self):
        """Update animation state and return current rotation angle"""
        if not self.is_animating:
            return 0
        
        current_time = time.time()
        elapsed = current_time - self.animation_start_time
        progress = min(elapsed / self.animation_duration, 1.0)
        
        # Use easing function for smooth animation
        # Ease-out cubic: 1 - (1-t)^3
        eased_progress = 1 - (1 - progress) ** 3
        
        current_angle = self.animation_angle_total * eased_progress
        
        # Check if animation is complete
        if progress >= 1.0:
            self.is_animating = False
            self.animating_face = None
            self.animation_cubes = []
            return self.animation_angle_total  # Return final angle
        
        return current_angle
    
    def initialize_cubes(self):
        """Initialize the position and colors for each small cube in the 3x3x3 grid"""
        self.cubes = []
        # Create 3x3x3 grid of cubes
        scale_factor = 0.85
        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    # Calculate position
                    position = [
                        x * self.cube_spacing * scale_factor,
                        y * self.cube_spacing * scale_factor,
                        z * self.cube_spacing * scale_factor
                    ]
                    
                    # Get colors from the Rubik's cube state
                    colors = []
                    for face_index in range(6):
                        color = self.rubiks_cube.get_cube_color(x, y, z, face_index)
                        colors.append(color)
                    
                    self.cubes.append({
                        'position': position,
                        'colors': colors,
                        'grid_pos': (x, y, z)  # Store grid position for updates
                    })
    
    def update_cube_colors(self):
        """Update cube colors based on current Rubik's cube state"""
        for cube in self.cubes:
            x, y, z = cube['grid_pos']
            colors = []
            for face_index in range(6):
                color = self.rubiks_cube.get_cube_color(x, y, z, face_index)
                colors.append(color)
            cube['colors'] = colors
    
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

    def create_display_list(self):
        """Create optimized display lists for the Rubik's cube"""
        self.create_single_cube_display_list()

    def create_single_cube_display_list(self):
        """Create optimized display lists for each face of a single cube"""
        # Create 6 display lists, one for each face
        self.face_display_lists = [glGenLists(1) for _ in range(6)]
        
        # Group faces by orientation
        top_faces = []
        bottom_faces = []
        right_faces = []
        left_faces = []
        front_faces = []
        back_faces = []
        
        # Identify which faces belong to which orientation based on normals
        for face in self.obj_faces:
            # Calculate face normal
            v0 = self.obj_vertices[face[0]]
            v1 = self.obj_vertices[face[1]]
            v2 = self.obj_vertices[face[2]]
            
            edge1 = [v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]]
            edge2 = [v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]]
            
            normal = [
                edge1[1] * edge2[2] - edge1[2] * edge2[1],
                edge1[2] * edge2[0] - edge1[0] * edge2[2],
                edge1[0] * edge2[1] - edge1[1] * edge2[0]
            ]
            
            # Normalize
            length = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
            if length > 0:
                normal = [n/length for n in normal]
            
            # Identify face orientation
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
        
        # Create display list for top faces (index 0)
        glNewList(self.face_display_lists[0], GL_COMPILE)
        for face in top_faces:
            if len(face) == 3:
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:
                glBegin(GL_QUADS)
            else:
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        glEndList()
        
        # Create display list for bottom faces (index 1)
        glNewList(self.face_display_lists[1], GL_COMPILE)
        for face in bottom_faces:
            if len(face) == 3:
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:
                glBegin(GL_QUADS)
            else:
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        glEndList()
        
        # Create display list for right faces (index 2)
        glNewList(self.face_display_lists[2], GL_COMPILE)
        for face in right_faces:
            if len(face) == 3:
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:
                glBegin(GL_QUADS)
            else:
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        glEndList()
        
        # Create display list for left faces (index 3)
        glNewList(self.face_display_lists[3], GL_COMPILE)
        for face in left_faces:
            if len(face) == 3:
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:
                glBegin(GL_QUADS)
            else:
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        glEndList()
        
        # Create display list for front faces (index 4)
        glNewList(self.face_display_lists[4], GL_COMPILE)
        for face in front_faces:
            if len(face) == 3:
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:
                glBegin(GL_QUADS)
            else:
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        glEndList()
        
        # Create display list for back faces (index 5)
        glNewList(self.face_display_lists[5], GL_COMPILE)
        for face in back_faces:
            if len(face) == 3:
                glBegin(GL_TRIANGLES)
            elif len(face) == 4:
                glBegin(GL_QUADS)
            else:
                glBegin(GL_POLYGON)
            
            for vertex_index in face:
                glVertex3fv(self.obj_vertices[vertex_index])
            
            glEnd()
        glEndList()
        
        # Keep single_cube_display_list for backward compatibility
        self.single_cube_display_list = self.face_display_lists[0]

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
        """Render the 3x3x3 Rubik's cube using individual cubes with animation"""
        if not hasattr(self, 'face_display_lists'):
            return
        
        # Get current animation angle
        animation_angle = self.update_animation()
        
        # Render each small cube
        for cube in self.cubes:
            position = cube['position']
            colors = cube['colors']
            is_animating_cube = cube in self.animation_cubes
            
            glPushMatrix()
            
            # Position this cube
            glTranslatef(position[0], position[1], position[2])
            
            # Apply animation rotation if this cube is part of the animating face
            if is_animating_cube and self.is_animating:
                # Translate to origin for rotation
                glTranslatef(-position[0], -position[1], -position[2])
                
                # Apply rotation around the face axis
                if self.animation_axis == (1, 0, 0):  # X-axis
                    glRotatef(animation_angle, 1, 0, 0)
                elif self.animation_axis == (-1, 0, 0):  # -X-axis
                    glRotatef(animation_angle, -1, 0, 0)  # Use negative axis instead of negative angle
                elif self.animation_axis == (0, 1, 0):  # Y-axis
                    glRotatef(animation_angle, 0, 1, 0)
                elif self.animation_axis == (0, -1, 0):  # -Y-axis
                    glRotatef(animation_angle, 0, -1, 0)  # Use negative axis instead of negative angle
                elif self.animation_axis == (0, 0, 1):  # Z-axis
                    glRotatef(animation_angle, 0, 0, 1)
                elif self.animation_axis == (0, 0, -1):  # -Z-axis
                    glRotatef(animation_angle, 0, 0, -1)  # Use negative axis instead of negative angle
                
                # Translate back to position
                glTranslatef(position[0], position[1], position[2])
            
            # Scale the cube
            glScalef(0.8, 0.8, 0.8)
            
            # Draw each face with its proper color
            for i in range(6):
                glColor3fv(colors[i])  # Set color using glColor3fv instead of material
                glCallList(self.face_display_lists[i])
            
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
        
        # Render skybox first (before any transformations)
        self.render_skybox()
        
        glPushMatrix()
        
        # Position the camera
        glTranslatef(0.0, 0.0, -4.0)
        
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
        if hasattr(self, 'face_display_lists'):
            for display_list in self.face_display_lists:
                glDeleteLists(display_list, 1)
            self.face_display_lists = None
            self.single_cube_display_list = None
        
        # Clean up skybox resources
        if self.skybox_texture:
            glDeleteTextures([self.skybox_texture])
            self.skybox_texture = None
        
        if self.skybox_display_list:
            glDeleteLists(self.skybox_display_list, 1)
            self.skybox_display_list = None