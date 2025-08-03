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
        self.fov = 60 # Field of view for perspective projection
        
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
        
        # Import settings manager to get current skybox
        from settings_manager import SettingsManager
        self.settings_manager = SettingsManager()
        
        # Now initialize cubes after colors are defined
        self.initialize_cubes()
        
        # Load the single cube model
        self.load_obj(cube_path)
        
        # Initialize OpenGL settings
        self.setup_opengl()
        
        # Load skybox texture from settings and create spherical skybox
        # Use medium difficulty as default on initialization
        skybox_path = self.settings_manager.get_skybox_by_difficulty("medium")
        self.load_skybox_texture(skybox_path)
        self.create_spherical_skybox_display_list()  # Using spherical skybox for full panoramic image
        
        # Create optimized display list for single cube
        self.create_display_list()
        
        # Store camera rotation for manual control
        self.rotation_x = 0
        self.rotation_y = 0
        
        # Face visibility and glow effect system
        self.face_visibility_scores = [0.0] * 6  # Visibility scores for each face
        self.most_visible_face = 0  # Index of the most visible face
        self.glow_intensity = 0.0  # Current glow intensity (animated)
        self.glow_target = 1.0  # Target glow intensity
        self.glow_speed = 3.0  # Speed of glow animation
        self.glow_pulse_time = 0.0  # Time for pulsing animation
        self.glow_pulse_speed = 2.0  # Speed of pulse animation
        
        # Face normal vectors in world space (pointing outward from cube center)
        self.face_normals = [
            (0, 1, 0),   # Top face normal
            (0, -1, 0),  # Bottom face normal  
            (1, 0, 0),   # Right face normal
            (-1, 0, 0),  # Left face normal
            (0, 0, 1),   # Front face normal
            (0, 0, -1)   # Back face normal
        ]

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
    
    def reload_skybox_texture(self, new_image_path):
        """Reload skybox texture with a new image file"""
        try:
            # Clean up old texture
            if self.skybox_texture:
                glDeleteTextures([self.skybox_texture])
                self.skybox_texture = None
            
            # Clean up old display list
            if self.skybox_display_list:
                glDeleteLists(self.skybox_display_list, 1)
                self.skybox_display_list = None
            
            # Load new texture
            self.load_skybox_texture(new_image_path)
            
            # Recreate display list with new texture
            self.create_spherical_skybox_display_list()
            
        except Exception as e:
            print(f"Failed to reload skybox texture: {e}")
            # Fallback to default texture
            self.load_skybox_texture("utils/skybox.jpg")
            self.create_spherical_skybox_display_list()

    def create_spherical_skybox_display_list(self):
        """Create a spherical skybox for seamless panoramic image mapping"""
        if not self.skybox_texture:
            return
        
        self.skybox_display_list = glGenLists(1)
        glNewList(self.skybox_display_list, GL_COMPILE)
        
        # Enable texturing
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.skybox_texture)
        glColor3f(1.0, 1.0, 1.0)
        
        # Create a sphere for the skybox
        radius = self.skybox_size
        stacks = 32  # Number of horizontal divisions (latitude)
        slices = 64  # Number of vertical divisions (longitude)
        
        # Generate sphere vertices and texture coordinates
        for i in range(stacks):
            lat0 = math.pi * (-0.5 + float(i) / stacks)
            z0 = radius * math.sin(lat0)
            zr0 = radius * math.cos(lat0)
            
            lat1 = math.pi * (-0.5 + float(i + 1) / stacks)
            z1 = radius * math.sin(lat1)
            zr1 = radius * math.cos(lat1)
            
            glBegin(GL_QUAD_STRIP)
            for j in range(slices + 1):
                lng = 2 * math.pi * float(j) / slices
                x = math.cos(lng)
                y = math.sin(lng)
                
                # Texture coordinates for panoramic mapping
                # u goes from 0 to 1 as we go around horizontally
                # v goes from 0 to 1 as we go from bottom to top
                u = float(j) / slices
                v0 = float(i) / stacks
                v1 = float(i + 1) / stacks
                
                # First vertex (lower latitude)
                glTexCoord2f(u, v0)
                glVertex3f(x * zr0, z0, y * zr0)
                
                # Second vertex (higher latitude)
                glTexCoord2f(u, v1)
                glVertex3f(x * zr1, z1, y * zr1)
            glEnd()
        
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
        
        # Keep all rotations consistent using a simple rule:
        # The same animation angle will be used for all moves
        # We'll handle the logical model differences in rubiks_cube.py
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
            
            # Execute the pending logical move immediately when animation completes
            if hasattr(self, 'pending_move') and self.pending_move:
                self.rubiks_cube.execute_move(self.pending_move)
                self.pending_move = None
                # Update cube colors immediately to prevent flicker
                self.update_cube_colors()
            
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
        gluPerspective(self.fov, (self.width/self.height), 0.1, 50.0)
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

    def calculate_face_visibility(self):
        """Calculate which face is most visible based on camera rotation"""
        import math
        
        # Convert rotation angles to radians
        rx_rad = math.radians(self.rotation_x)
        ry_rad = math.radians(self.rotation_y)
        
        # Calculate camera direction vector (normalized)
        # Camera looks down negative Z axis, then we apply rotations
        # We need to invert the calculation since we want the face pointing towards camera
        cam_x = -math.sin(ry_rad) * math.cos(rx_rad)
        cam_y = math.sin(rx_rad)
        cam_z = math.cos(ry_rad) * math.cos(rx_rad)
        
        # Calculate dot product between camera direction and each face normal
        # Higher dot product means the face is more directly facing the camera
        max_visibility = -1.0
        most_visible = 0
        
        for i, (nx, ny, nz) in enumerate(self.face_normals):
            # Dot product gives us the cosine of the angle between vectors
            visibility = cam_x * nx + cam_y * ny + cam_z * nz
            self.face_visibility_scores[i] = max(0.0, visibility)  # Clamp to positive values
            
            if visibility > max_visibility:
                max_visibility = visibility
                most_visible = i
        
        # Only update most visible face if there's a clear winner
        if max_visibility > 0.3:  # Threshold to prevent rapid switching
            if most_visible != self.most_visible_face:
                self.most_visible_face = most_visible
    
    def update_glow_effect(self, delta_time):
        """Update the glow effect animation"""
        # Update pulse time for breathing effect
        self.glow_pulse_time += delta_time * self.glow_pulse_speed
        
        # Animate glow intensity towards target
        if self.glow_intensity < self.glow_target:
            self.glow_intensity += self.glow_speed * delta_time
            if self.glow_intensity > self.glow_target:
                self.glow_intensity = self.glow_target
        elif self.glow_intensity > self.glow_target:
            self.glow_intensity -= self.glow_speed * delta_time
            if self.glow_intensity < self.glow_target:
                self.glow_intensity = self.glow_target
    
    def render_face_corner_glow(self):
        """Render animated glowing effects at the outer corners of the most visible face"""
        if self.glow_intensity <= 0.01:
            return
        
        import math
        
        # Calculate pulsing effect
        pulse_factor = 0.5 + 0.3 * math.sin(self.glow_pulse_time)
        current_intensity = self.glow_intensity * pulse_factor
        
        # Save current OpenGL state
        depth_test_enabled = glIsEnabled(GL_DEPTH_TEST)
        cull_face_enabled = glIsEnabled(GL_CULL_FACE)
        blend_enabled = glIsEnabled(GL_BLEND)
        
        # Enable blending for glow effect
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        
        # Calculate the spacing between cubes to find face boundaries
        cube_spacing = self.cube_spacing * 0.85  # Same as in initialize_cubes
        
        # Expand outward to create border around the face (not inside)
        border_offset = 0.26  # Distance outside the face
        
        # Define outer corner positions for each face of the entire 3x3x3 cube
        # These positions are outside the actual face to create a border effect
        face_corners = {
            0: [  # Top face corners (expanded outward)
                (-cube_spacing - border_offset, cube_spacing + border_offset, -cube_spacing - border_offset),  # Top-left-back
                (cube_spacing + border_offset, cube_spacing + border_offset, -cube_spacing - border_offset),   # Top-right-back
                (cube_spacing + border_offset, cube_spacing + border_offset, cube_spacing + border_offset),    # Top-right-front
                (-cube_spacing - border_offset, cube_spacing + border_offset, cube_spacing + border_offset)    # Top-left-front
            ],
            1: [  # Bottom face corners (expanded outward)
                (-cube_spacing - border_offset, -cube_spacing - border_offset, cube_spacing + border_offset),  # Bottom-left-front
                (cube_spacing + border_offset, -cube_spacing - border_offset, cube_spacing + border_offset),   # Bottom-right-front
                (cube_spacing + border_offset, -cube_spacing - border_offset, -cube_spacing - border_offset),  # Bottom-right-back
                (-cube_spacing - border_offset, -cube_spacing - border_offset, -cube_spacing - border_offset)  # Bottom-left-back
            ],
            2: [  # Right face corners (expanded outward)
                (cube_spacing + border_offset, -cube_spacing - border_offset, -cube_spacing - border_offset),  # Bottom-right-back
                (cube_spacing + border_offset, cube_spacing + border_offset, -cube_spacing - border_offset),   # Top-right-back
                (cube_spacing + border_offset, cube_spacing + border_offset, cube_spacing + border_offset),    # Top-right-front
                (cube_spacing + border_offset, -cube_spacing - border_offset, cube_spacing + border_offset)    # Bottom-right-front
            ],
            3: [  # Left face corners (expanded outward)
                (-cube_spacing - border_offset, -cube_spacing - border_offset, cube_spacing + border_offset),  # Bottom-left-front
                (-cube_spacing - border_offset, cube_spacing + border_offset, cube_spacing + border_offset),   # Top-left-front
                (-cube_spacing - border_offset, cube_spacing + border_offset, -cube_spacing - border_offset),  # Top-left-back
                (-cube_spacing - border_offset, -cube_spacing - border_offset, -cube_spacing - border_offset)  # Bottom-left-back
            ],
            4: [  # Front face corners (expanded outward)
                (-cube_spacing - border_offset, -cube_spacing - border_offset, cube_spacing + border_offset),  # Bottom-left-front
                (cube_spacing + border_offset, -cube_spacing - border_offset, cube_spacing + border_offset),   # Bottom-right-front
                (cube_spacing + border_offset, cube_spacing + border_offset, cube_spacing + border_offset),    # Top-right-front
                (-cube_spacing - border_offset, cube_spacing + border_offset, cube_spacing + border_offset)    # Top-left-front
            ],
            5: [  # Back face corners (expanded outward)
                (cube_spacing + border_offset, -cube_spacing - border_offset, -cube_spacing - border_offset),  # Bottom-right-back
                (-cube_spacing - border_offset, -cube_spacing - border_offset, -cube_spacing - border_offset), # Bottom-left-back
                (-cube_spacing - border_offset, cube_spacing + border_offset, -cube_spacing - border_offset),  # Top-left-back
                (cube_spacing + border_offset, cube_spacing + border_offset, -cube_spacing - border_offset)    # Top-right-back
            ]
        }
        
        if self.most_visible_face not in face_corners:
            # Restore OpenGL state before returning
            if depth_test_enabled:
                glEnable(GL_DEPTH_TEST)
            if cull_face_enabled:
                glEnable(GL_CULL_FACE)
            if not blend_enabled:
                glDisable(GL_BLEND)
            return
        
        corners = face_corners[self.most_visible_face]
        
        # Set glow colors with animated intensity
        glow_alpha = current_intensity * 0.8
        
        # Render a single thick square border with rounded corners
        glColor4f(1, 1, 1.0, glow_alpha)  # White glow
        
        # Calculate border thickness and corner radius
        border_thickness = 0.02 + current_intensity * 0.01
        corner_radius = 0.05 + current_intensity * 0.02  # Radius for rounded corners
        segments_per_corner = 12  # Number of segments for smooth corners
        
        # Calculate center point
        center_x = sum(corner[0] for corner in corners) / len(corners)
        center_y = sum(corner[1] for corner in corners) / len(corners)
        center_z = sum(corner[2] for corner in corners) / len(corners)
        
        import math
        
        # Generate all vertices for the rounded square border
        all_inner_vertices = []
        all_outer_vertices = []
        
        for i in range(len(corners)):
            current_corner = corners[i]
            next_corner = corners[(i + 1) % len(corners)]
            prev_corner = corners[(i - 1) % len(corners)]
            
            # Calculate vectors to adjacent corners
            to_next = [next_corner[j] - current_corner[j] for j in range(3)]
            to_prev = [prev_corner[j] - current_corner[j] for j in range(3)]
            
            # Normalize vectors
            next_len = math.sqrt(sum(x*x for x in to_next))
            prev_len = math.sqrt(sum(x*x for x in to_prev))
            
            if next_len > 0 and prev_len > 0:
                to_next_norm = [x/next_len for x in to_next]
                to_prev_norm = [x/prev_len for x in to_prev]
                
                # Calculate start and end points for the rounded corner
                corner_start = [current_corner[j] + to_prev_norm[j] * corner_radius for j in range(3)]
                corner_end = [current_corner[j] + to_next_norm[j] * corner_radius for j in range(3)]
                
                # Add the straight edge leading to this corner
                if i == 0:  # Only add the first straight edge to avoid duplicates
                    # Vector from center to start point for thickness calculation
                    to_start = [corner_start[j] - center_j for j, center_j in enumerate([center_x, center_y, center_z])]
                    start_len = math.sqrt(sum(x*x for x in to_start))
                    if start_len > 0:
                        to_start_norm = [x/start_len for x in to_start]
                        
                        inner_start = [center_x + to_start_norm[0] * (start_len - border_thickness),
                                     center_y + to_start_norm[1] * (start_len - border_thickness),
                                     center_z + to_start_norm[2] * (start_len - border_thickness)]
                        outer_start = [center_x + to_start_norm[0] * (start_len + border_thickness),
                                     center_y + to_start_norm[1] * (start_len + border_thickness),
                                     center_z + to_start_norm[2] * (start_len + border_thickness)]
                        
                        all_inner_vertices.append(inner_start)
                        all_outer_vertices.append(outer_start)
                
                # Generate rounded corner vertices
                for seg in range(segments_per_corner + 1):
                    t = seg / segments_per_corner
                    
                    # Linear interpolation between start and end points
                    interp_point = [corner_start[j] + t * (corner_end[j] - corner_start[j]) for j in range(3)]
                    
                    # Calculate outward direction from corner center for rounding
                    to_corner_center = [current_corner[j] - center_j for j, center_j in enumerate([center_x, center_y, center_z])]
                    center_len = math.sqrt(sum(x*x for x in to_corner_center))
                    outward_dir = [x/center_len for x in to_corner_center] if center_len > 0 else [0, 0, 0]
                    
                    # Add outward bulge for rounded effect
                    bulge_factor = math.sin(t * math.pi) * corner_radius * 0.3
                    rounded_point = [interp_point[j] + outward_dir[j] * bulge_factor for j in range(3)]
                    
                    # Calculate inner and outer vertices
                    to_rounded = [rounded_point[j] - center_j for j, center_j in enumerate([center_x, center_y, center_z])]
                    rounded_len = math.sqrt(sum(x*x for x in to_rounded))
                    
                    if rounded_len > 0:
                        to_rounded_norm = [x/rounded_len for x in to_rounded]
                        
                        inner_vertex = [center_x + to_rounded_norm[0] * (rounded_len - border_thickness),
                                      center_y + to_rounded_norm[1] * (rounded_len - border_thickness),
                                      center_z + to_rounded_norm[2] * (rounded_len - border_thickness)]
                        outer_vertex = [center_x + to_rounded_norm[0] * (rounded_len + border_thickness),
                                      center_y + to_rounded_norm[1] * (rounded_len + border_thickness),
                                      center_z + to_rounded_norm[2] * (rounded_len + border_thickness)]
                        
                        all_inner_vertices.append(inner_vertex)
                        all_outer_vertices.append(outer_vertex)
        
        # Draw the rounded border as triangular strips
        glBegin(GL_TRIANGLE_STRIP)
        for i in range(len(all_inner_vertices)):
            # Create triangular strip between inner and outer vertices
            current_i = i
            next_i = (i + 1) % len(all_inner_vertices)
            
            # Add vertices in triangle strip order
            glVertex3f(all_inner_vertices[current_i][0], all_inner_vertices[current_i][1], all_inner_vertices[current_i][2])
            glVertex3f(all_outer_vertices[current_i][0], all_outer_vertices[current_i][1], all_outer_vertices[current_i][2])
        
        # Close the strip by connecting back to the first vertices
        glVertex3f(all_inner_vertices[0][0], all_inner_vertices[0][1], all_inner_vertices[0][2])
        glVertex3f(all_outer_vertices[0][0], all_outer_vertices[0][1], all_outer_vertices[0][2])
        glEnd()
        
        # Restore OpenGL state properly
        if depth_test_enabled:
            glEnable(GL_DEPTH_TEST)
        if cull_face_enabled:
            glEnable(GL_CULL_FACE)
        if not blend_enabled:
            glDisable(GL_BLEND)
        
        glColor3f(1.0, 1.0, 1.0)  # Reset color
        glLineWidth(1.0)  # Reset line width

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
        
        # Calculate which face is most visible
        self.calculate_face_visibility()
        
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
                if self.animation_axis == (1, 0, 0):  # X-axis (R)
                    glRotatef(animation_angle, 1, 0, 0)
                elif self.animation_axis == (-1, 0, 0):  # -X-axis (L)
                    glRotatef(animation_angle, -1, 0, 0)
                elif self.animation_axis == (0, 1, 0):  # Y-axis (U)
                    glRotatef(animation_angle, 0, 1, 0)
                elif self.animation_axis == (0, -1, 0):  # -Y-axis (D)
                    glRotatef(animation_angle, 0, -1, 0)
                elif self.animation_axis == (0, 0, 1):  # Z-axis (F)
                    glRotatef(animation_angle, 0, 0, 1)
                elif self.animation_axis == (0, 0, -1):  # -Z-axis (B)
                    glRotatef(animation_angle, 0, 0, -1)
                
                # Translate back to position
                glTranslatef(position[0], position[1], position[2])
            
            # Scale the cube
            glScalef(0.8, 0.8, 0.8)
            
            # Draw each face with its proper color
            for i in range(6):
                glColor3fv(colors[i])  # Set color using glColor3fv instead of material
                glCallList(self.face_display_lists[i])
            
            glPopMatrix()
        
        # Render the glow effect for the entire most visible face (after all cubes)
        self.render_face_corner_glow()

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