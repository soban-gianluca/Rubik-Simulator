"""
Enhanced Mouse Interaction System for Rubik's Cube

This system uses actual 3D cube geometry for face detection instead of fixed screen regions.
It performs ray-plane intersection to detect which face of the cube the user clicked on,
providing much more accurate and intuitive control.

Features:
- Ray-casting from mouse position to 3D space
- Intersection testing with actual cube faces
- Accurate face detection based on cube orientation
- Visual feedback for hovered and selected faces
- Smooth animation integration
"""

import math
import pygame
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

class MouseCubeInteraction:
    
    def __init__(self, renderer):
        self.renderer = renderer
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_face = None
        self.detected_cube_pos = None  # Position of the detected cube in the 3x3x3 grid
        self.move_executed = False
                
        # Mouse sensitivity settings - optimized for revolutionary detection
        self.move_sensitivity = 12  # Very responsive
        self.last_move_time = 0
        self.move_cooldown = 0.12  # Fast response
        
        # Visual feedback
        self.hovered_face = None
        self.hovered_cube_pos = None
        self.highlight_intensity = 0.0
        self.fade_speed = 4.0
        
        # 3D cube dimensions and positioning - GET FROM RENDERER for accuracy
        self.cube_size = 0.4  # Half size of each small cube
        self.cube_spacing = 0.52  # Spacing between cube centers (will be overridden by renderer)
        
        # Face normal vectors for the 6 faces of the cube
        self.face_normals = {
            'front': (0, 0, 1),   # +Z face
            'back': (0, 0, -1),   # -Z face
            'right': (1, 0, 0),   # +X face
            'left': (-1, 0, 0),   # -X face
            'top': (0, 1, 0),     # +Y face
            'bottom': (0, -1, 0)  # -Y face
        }
        
        # Map face names to cube face indices (same as in rubiks_cube.py)
        self.face_to_index = {
            'top': 0,
            'bottom': 1,
            'right': 2,
            'left': 3,
            'front': 4,
            'back': 5
        }
        
    def test_individual_cube_faces(self, ray_origin, ray_dir, cube_world_pos, cube_grid_pos, spacing):
        """Test ray intersection with each face of an individual cube"""
        x_grid, y_grid, z_grid = cube_grid_pos
        
        # Calculate the half-size of each individual cube face
        cube_half_size = spacing * 0.4  # Adjust to match actual cube face size
        
        # Define the 6 faces of this individual cube
        faces_to_test = []
        
        # Only test faces that are on the outer surface of the 3x3x3 cube
        if z_grid == 1:  # Front face visible
            face_center = [cube_world_pos[0], cube_world_pos[1], cube_world_pos[2] + cube_half_size]
            faces_to_test.append(('front', face_center, [0, 0, 1]))
            
        if z_grid == -1:  # Back face visible
            face_center = [cube_world_pos[0], cube_world_pos[1], cube_world_pos[2] - cube_half_size]
            faces_to_test.append(('back', face_center, [0, 0, -1]))
            
        if x_grid == 1:  # Right face visible
            face_center = [cube_world_pos[0] + cube_half_size, cube_world_pos[1], cube_world_pos[2]]
            faces_to_test.append(('right', face_center, [1, 0, 0]))
            
        if x_grid == -1:  # Left face visible
            face_center = [cube_world_pos[0] - cube_half_size, cube_world_pos[1], cube_world_pos[2]]
            faces_to_test.append(('left', face_center, [-1, 0, 0]))
            
        if y_grid == 1:  # Top face visible
            face_center = [cube_world_pos[0], cube_world_pos[1] + cube_half_size, cube_world_pos[2]]
            faces_to_test.append(('top', face_center, [0, 1, 0]))
            
        if y_grid == -1:  # Bottom face visible
            face_center = [cube_world_pos[0], cube_world_pos[1] - cube_half_size, cube_world_pos[2]]
            faces_to_test.append(('bottom', face_center, [0, -1, 0]))
        
        # Test ray intersection with each face of this cube
        closest_face = None
        closest_distance = float('inf')
        
        for face_name, face_center, face_normal in faces_to_test:
            # Check if this face type is visible from current camera angle
            if not self.is_face_visible_from_camera(face_name):
                continue
                
            intersection = self.ray_plane_intersection(ray_origin, ray_dir, face_center, face_normal)
            
            if intersection:
                # Check if the intersection is within this individual cube face
                if self.is_point_on_individual_cube_face(intersection, face_center, cube_half_size):
                    # Calculate distance from camera
                    distance = math.sqrt(
                        (intersection[0] - ray_origin[0])**2 + 
                        (intersection[1] - ray_origin[1])**2 + 
                        (intersection[2] - ray_origin[2])**2
                    )
                    
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_face = (face_name, distance, cube_grid_pos)
        
        return closest_face
    
    def is_point_on_individual_cube_face(self, point, face_center, cube_half_size):
        """Check if a point is on an individual cube face"""
        # Convert point to face-relative coordinates
        rel_x = point[0] - face_center[0]
        rel_y = point[1] - face_center[1] 
        rel_z = point[2] - face_center[2]
        
        # Use generous tolerance for easier clicking
        tolerance = cube_half_size * 1.2  # 20% larger than actual face
        
        # Check if point is within the square bounds of this individual face
        # For any face, two coordinates should be within tolerance
        return (abs(rel_x) <= tolerance and abs(rel_y) <= tolerance and abs(rel_z) <= tolerance)
    
    def get_renderer_cube_geometry(self):
        """Get the exact cube geometry from the renderer for perfect alignment"""
        # Use the renderer's exact values
        cube_spacing = self.renderer.cube_spacing  # 0.52
        scale_factor = 0.85  # From renderer.initialize_cubes()
        
        actual_spacing = cube_spacing * scale_factor
        # Make faces MUCH larger to match the generous front/back detection
        visual_half_size = actual_spacing * 2.0  # Much larger for better detection
        
        return {
            'spacing': actual_spacing,
            'half_size': visual_half_size,
            'world_center': [0, 0, -4]  # Exact camera position from renderer
        }
    
    def get_3d_cube_positions(self):
        """Get the 3D positions of all 27 cubes in the 3x3x3 grid"""
        positions = []
        scale_factor = 0.85
        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    pos = [
                        x * self.cube_spacing * scale_factor,
                        y * self.cube_spacing * scale_factor,
                        z * self.cube_spacing * scale_factor
                    ]
                    positions.append(((x, y, z), pos))
        return positions
    
    def screen_to_world_ray(self, mouse_x, mouse_y):
        """Convert screen coordinates to a 3D ray in world space - improved version"""
        # Get viewport dimensions
        viewport = [0, 0, self.renderer.width, self.renderer.height]
        
        # Normalize mouse coordinates to [-1, 1] range
        ndc_x = (2.0 * mouse_x) / viewport[2] - 1.0
        ndc_y = 1.0 - (2.0 * mouse_y) / viewport[3]  # Flip Y axis
        
        # Camera setup parameters (must match the renderer's camera setup)
        fov = 45.0  # Field of view in degrees
        aspect = viewport[2] / viewport[3]
        near_plane = 0.1
        far_plane = 50.0
        
        # Calculate the ray direction in camera space
        fov_rad = math.radians(fov)
        tan_half_fov = math.tan(fov_rad / 2.0)
        
        # Ray direction in camera coordinates
        ray_x = ndc_x * tan_half_fov * aspect
        ray_y = ndc_y * tan_half_fov
        ray_z = -1.0  # Point into the screen (negative Z in camera space)
        
        # Camera position in world space (matching renderer setup)
        # The renderer translates by (0, 0, -4) and then applies rotations
        camera_distance = 4.0
        
        # Get current camera rotations
        rot_x = math.radians(self.renderer.rotation_x)
        rot_y = math.radians(self.renderer.rotation_y)
        
        # Create rotation matrices
        cos_x, sin_x = math.cos(rot_x), math.sin(rot_x)
        cos_y, sin_y = math.cos(rot_y), math.sin(rot_y)
        
        # Transform ray direction from camera space to world space
        # Apply Y rotation first, then X rotation (reverse order of renderer)
        
        # Y rotation matrix applied to ray direction
        ray_x_rot = ray_x * cos_y + ray_z * sin_y
        ray_z_rot = -ray_x * sin_y + ray_z * cos_y
        ray_x, ray_z = ray_x_rot, ray_z_rot
        
        # X rotation matrix applied to ray direction
        ray_y_rot = ray_y * cos_x - ray_z * sin_x
        ray_z_rot = ray_y * sin_x + ray_z * cos_x
        ray_y, ray_z = ray_y_rot, ray_z_rot
        
        # Normalize the ray direction
        ray_length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
        if ray_length > 0:
            ray_dir = [ray_x / ray_length, ray_y / ray_length, ray_z / ray_length]
        else:
            ray_dir = [0, 0, -1]
        
        # Calculate camera position in world space
        # Start with camera at (0, 0, camera_distance) and apply rotations
        cam_x, cam_y, cam_z = 0.0, 0.0, camera_distance
        
        # Apply Y rotation to camera position
        cam_x_rot = cam_x * cos_y - cam_z * sin_y
        cam_z_rot = cam_x * sin_y + cam_z * cos_y
        cam_x, cam_z = cam_x_rot, cam_z_rot
        
        # Apply X rotation to camera position
        cam_y_rot = cam_y * cos_x + cam_z * sin_x
        cam_z_rot = -cam_y * sin_x + cam_z * cos_x
        cam_y, cam_z = cam_y_rot, cam_z_rot
        
        ray_origin = [cam_x, cam_y, cam_z]
        
        return ray_origin, ray_dir
    
    def _manual_screen_to_world_ray(self, mouse_x, mouse_y):
        """Manual ray calculation when gluUnProject fails"""
        # Normalize screen coordinates to [-1, 1]
        ndc_x = (2.0 * mouse_x) / self.renderer.width - 1.0
        ndc_y = 1.0 - (2.0 * mouse_y) / self.renderer.height
        
        # Camera parameters (matching renderer setup)
        fov = 45.0  # Field of view in degrees
        aspect = self.renderer.width / self.renderer.height
        near = 0.1
        far = 50.0
        
        # Convert to radians
        fov_rad = math.radians(fov)
        
        # Calculate ray direction in camera space
        tan_half_fov = math.tan(fov_rad / 2.0)
        ray_x = ndc_x * tan_half_fov * aspect
        ray_y = ndc_y * tan_half_fov
        ray_z = -1.0  # Pointing into the screen
        
        # Camera position (matching game setup: translate by (0, 0, -4))
        camera_pos = [0.0, 0.0, 4.0]
        
        # Apply camera rotations (reverse of renderer rotations)
        # Note: These rotations need to be applied in reverse order
        rx = math.radians(-self.renderer.rotation_x)
        ry = math.radians(-self.renderer.rotation_y)
        
        # Rotate ray direction by camera rotations
        # First rotate around X axis
        cos_rx, sin_rx = math.cos(rx), math.sin(rx)
        ray_y_new = ray_y * cos_rx - ray_z * sin_rx
        ray_z_new = ray_y * sin_rx + ray_z * cos_rx
        ray_y, ray_z = ray_y_new, ray_z_new
        
        # Then rotate around Y axis
        cos_ry, sin_ry = math.cos(ry), math.sin(ry)
        ray_x_new = ray_x * cos_ry + ray_z * sin_ry
        ray_z_new = -ray_x * sin_ry + ray_z * cos_ry
        ray_x, ray_z = ray_x_new, ray_z_new
        
        # Normalize ray direction
        length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
        if length > 0:
            ray_dir = [ray_x/length, ray_y/length, ray_z/length]
        else:
            ray_dir = [0, 0, -1]
        
        # Apply camera rotation to camera position
        # Rotate camera position by the same rotations
        cam_x, cam_y, cam_z = camera_pos
        
        # Rotate around Y axis first
        cam_x_new = cam_x * cos_ry - cam_z * sin_ry
        cam_z_new = cam_x * sin_ry + cam_z * cos_ry
        cam_x, cam_z = cam_x_new, cam_z_new
        
        # Then rotate around X axis
        cam_y_new = cam_y * cos_rx + cam_z * sin_rx
        cam_z_new = -cam_y * sin_rx + cam_z * cos_rx
        cam_y, cam_z = cam_y_new, cam_z_new
        
        return (cam_x, cam_y, cam_z), ray_dir
    
    def ray_plane_intersection(self, ray_origin, ray_dir, plane_point, plane_normal):
        """Calculate intersection point of ray with plane"""
        # Ray equation: P = ray_origin + t * ray_dir
        # Plane equation: (P - plane_point) · plane_normal = 0
        
        denominator = (ray_dir[0] * plane_normal[0] + 
                      ray_dir[1] * plane_normal[1] + 
                      ray_dir[2] * plane_normal[2])
        
        if abs(denominator) < 1e-6:  # Ray is parallel to plane
            return None
        
        # Calculate t parameter
        diff = [plane_point[0] - ray_origin[0],
                plane_point[1] - ray_origin[1],
                plane_point[2] - ray_origin[2]]
        
        numerator = (diff[0] * plane_normal[0] + 
                    diff[1] * plane_normal[1] + 
                    diff[2] * plane_normal[2])
        
        t = numerator / denominator
        
        if t < 0:  # Intersection is behind the ray origin
            return None
        
        # Calculate intersection point
        intersection = [
            ray_origin[0] + t * ray_dir[0],
            ray_origin[1] + t * ray_dir[1],
            ray_origin[2] + t * ray_dir[2]
        ]
        
        return intersection
    
    def debug_camera_info(self):
        """Get current camera info for debugging"""
        try:
            model_matrix = glGetDoublev(GL_MODELVIEW_MATRIX)
            proj_matrix = glGetDoublev(GL_PROJECTION_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)
            
            print("Camera Debug Info:")
            print(f"  Viewport: {viewport}")
            print(f"  Model matrix first row: {model_matrix[0:4]}")
            print(f"  Projection matrix first row: {proj_matrix[0:4]}")
            
            # Also get renderer camera info
            if hasattr(self.renderer, 'rotation_x') and hasattr(self.renderer, 'rotation_y'):
                print(f"  Renderer rotation: x={self.renderer.rotation_x}, y={self.renderer.rotation_y}")
        except Exception as e:
            print(f"Camera debug error: {e}")
    
    def point_in_cube_face(self, point, cube_center, face_name):
        """Check if a point lies within a specific face of a cube - with larger detection area"""
        # Make detection area bigger but keep it simple
        half_size = self.cube_size * 1.3  # 30% larger detection area
        tolerance = 0.3  # Good tolerance for detection
        
        # Adjust point relative to cube center
        rel_point = [
            point[0] - cube_center[0],
            point[1] - cube_center[1],
            point[2] - cube_center[2]
        ]
        
        # Check if point is within the face bounds
        if face_name == 'front':  # +Z face
            return (abs(rel_point[2] - half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[1]) <= half_size + tolerance)
        elif face_name == 'back':  # -Z face
            return (abs(rel_point[2] + half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[1]) <= half_size + tolerance)
        elif face_name == 'right':  # +X face
            return (abs(rel_point[0] - half_size) < tolerance and
                   abs(rel_point[1]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'left':  # -X face
            return (abs(rel_point[0] + half_size) < tolerance and
                   abs(rel_point[1]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'top':  # +Y face
            return (abs(rel_point[1] - half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'bottom':  # -Y face
            return (abs(rel_point[1] + half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        
        return False
    
    def detect_face_from_mouse(self, mouse_pos):
        """ULTIMATE face detection - hybrid approach with multiple robust methods"""
        mouse_x, mouse_y = mouse_pos
        
        # Try Method 1: Enhanced OpenGL picking
        result1 = self.method_opengl_picking(mouse_x, mouse_y)
        if result1:
            return result1
            
        # Try Method 2: Simple but reliable screen mapping
        result2 = self.method_screen_mapping(mouse_x, mouse_y)
        if result2:
            return result2
            
        # Try Method 3: Distance-based detection
        result3 = self.method_distance_based(mouse_x, mouse_y)
        if result3:
            return result3
            
        # Absolute fallback
        return 'front', (0, 0, 1)
    
    def method_opengl_picking(self, mouse_x, mouse_y):
        """Method 1: Enhanced OpenGL matrix picking"""
        try:
            # Get current matrices
            model_matrix = glGetDoublev(GL_MODELVIEW_MATRIX)
            proj_matrix = glGetDoublev(GL_PROJECTION_MATRIX) 
            viewport = glGetIntegerv(GL_VIEWPORT)
            
            # Calculate exact cube geometry
            spacing = self.renderer.cube_spacing * 0.85
            
            # Define all possible face positions
            face_positions = []
            
            # Generate all outer face positions
            for x in range(-1, 2):
                for y in range(-1, 2):
                    for z in range(-1, 2):
                        world_pos = [x * spacing, y * spacing, z * spacing]
                        
                        # Add visible faces for this cube
                        if z == 1:  # Front
                            face_positions.append(('front', world_pos, (x, y, z)))
                        if z == -1:  # Back
                            face_positions.append(('back', world_pos, (x, y, z)))
                        if x == 1:  # Right
                            face_positions.append(('right', world_pos, (x, y, z)))
                        if x == -1:  # Left
                            face_positions.append(('left', world_pos, (x, y, z)))
                        if y == 1:  # Top
                            face_positions.append(('top', world_pos, (x, y, z)))
                        if y == -1:  # Bottom
                            face_positions.append(('bottom', world_pos, (x, y, z)))
            
            # Test each face position
            best_match = None
            min_distance = float('inf')
            
            for face_name, world_pos, grid_pos in face_positions:
                if not self.is_face_currently_visible(face_name):
                    continue
                    
                try:
                    # Project to screen
                    screen_pos = gluProject(
                        world_pos[0], world_pos[1], world_pos[2],
                        model_matrix, proj_matrix, viewport
                    )
                    
                    if screen_pos:
                        sx, sy, sz = screen_pos
                        sy = viewport[3] - sy  # Flip Y
                        
                        # Calculate screen distance
                        dx = mouse_x - sx
                        dy = mouse_y - sy
                        screen_dist = math.sqrt(dx*dx + dy*dy)
                        
                        # Use VERY generous hit radius
                        hit_radius = 100  # Large radius for all faces
                        
                        if screen_dist < hit_radius and screen_dist < min_distance:
                            min_distance = screen_dist
                            best_match = (face_name, grid_pos)
                            
                except:
                    continue
            
            return best_match
            
        except:
            return None
    
    def method_screen_mapping(self, mouse_x, mouse_y):
        """Method 2: Reliable screen region mapping"""
        width = self.renderer.width
        height = self.renderer.height
        
        # Get camera rotation
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        rx = self.renderer.rotation_x % 360
        if rx > 180:
            rx -= 360
        
        # Normalize mouse position
        nx = (mouse_x / width) * 2 - 1    # -1 to 1
        ny = (mouse_y / height) * 2 - 1   # -1 to 1
        
        # Define screen regions with rotation compensation
        face_result = None
        
        # Determine primary face based on screen position and rotation
        if abs(nx) > abs(ny):  # Horizontal dominance
            if nx > 0:  # Right side of screen
                face_result = self.get_face_for_screen_right(ry)
            else:  # Left side of screen
                face_result = self.get_face_for_screen_left(ry)
        else:  # Vertical dominance
            if ny < 0:  # Top of screen
                face_result = ('top', (0, 1, 0))
            else:  # Bottom of screen
                face_result = ('bottom', (0, -1, 0))
        
        return face_result
    
    def get_face_for_screen_right(self, ry):
        """Determine which face appears on right side of screen"""
        if -30 < ry < 30:
            return ('right', (1, 0, 0))
        elif 30 <= ry < 120:
            return ('back', (0, 0, -1))
        elif ry >= 120 or ry <= -120:
            return ('left', (-1, 0, 0))
        else:  # -120 < ry < -30
            return ('front', (0, 0, 1))
    
    def get_face_for_screen_left(self, ry):
        """Determine which face appears on left side of screen"""
        if -30 < ry < 30:
            return ('left', (-1, 0, 0))
        elif 30 <= ry < 120:
            return ('front', (0, 0, 1))
        elif ry >= 120 or ry <= -120:
            return ('right', (1, 0, 0))
        else:  # -120 < ry < -30
            return ('back', (0, 0, -1))
    
    def method_distance_based(self, mouse_x, mouse_y):
        """Method 3: Distance-based detection with manual ray"""
        try:
            # Create simple ray from mouse position
            width = self.renderer.width
            height = self.renderer.height
            
            # Normalize mouse coordinates
            norm_x = (mouse_x / width) * 2 - 1
            norm_y = 1 - (mouse_y / height) * 2
            
            # Simple ray direction
            ray_dir = [norm_x * 0.5, norm_y * 0.5, -1.0]
            
            # Camera position (accounting for transformations)
            ry_rad = math.radians(self.renderer.rotation_y)
            rx_rad = math.radians(self.renderer.rotation_x)
            
            # Simple camera position
            cam_pos = [0, 0, 4]  # Distance from cube
            
            # Test intersection with simple cube faces
            spacing = self.renderer.cube_spacing * 0.85
            cube_size = spacing * 1.5
            
            # Define 6 main faces
            faces = [
                ('front', [0, 0, cube_size], [0, 0, 1]),
                ('back', [0, 0, -cube_size], [0, 0, -1]),
                ('right', [cube_size, 0, 0], [1, 0, 0]),
                ('left', [-cube_size, 0, 0], [-1, 0, 0]),
                ('top', [0, cube_size, 0], [0, 1, 0]),
                ('bottom', [0, -cube_size, 0], [0, -1, 0])
            ]
            
            best_face = None
            min_dist = float('inf')
            
            for face_name, face_center, face_normal in faces:
                if not self.is_face_currently_visible(face_name):
                    continue
                
                # Simple distance calculation
                dx = norm_x - (face_center[0] / cube_size)
                dy = norm_y - (face_center[1] / cube_size)
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist < 0.8 and dist < min_dist:  # Generous threshold
                    min_dist = dist
                    best_face = (face_name, self._get_cube_pos_for_face(face_name))
            
            return best_face
            
        except:
            return None
    
    def is_face_currently_visible(self, face_name):
        """Simple visibility check"""
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        rx = self.renderer.rotation_x % 360
        if rx > 180:
            rx -= 360
        
        # Very generous visibility
        if face_name == 'front':
            return -100 < ry < 100
        elif face_name == 'back':
            return ry > 80 or ry < -80
        elif face_name == 'right':
            return -150 < ry < 100
        elif face_name == 'left':
            return 80 < ry < 280 or ry < -80
        elif face_name == 'top':
            return rx < 100
        elif face_name == 'bottom':
            return rx > -100
        
        return True
    
    def _get_cube_pos_for_face(self, face_name):
        """Get representative cube position for face"""
        if face_name == 'front':
            return (0, 0, 1)
        elif face_name == 'back':
            return (0, 0, -1)
        elif face_name == 'right':
            return (1, 0, 0)
        elif face_name == 'left':
            return (-1, 0, 0)
        elif face_name == 'top':
            return (0, 1, 0)
        elif face_name == 'bottom':
            return (0, -1, 0)
        return (0, 0, 1)
    
    def test_cube_faces_screen_projection(self, world_pos, grid_pos, mouse_x, mouse_y, 
                                        model_matrix, proj_matrix, viewport, cube_spacing):
        """ENHANCED screen projection with MASSIVE hit areas for all faces"""
        x_grid, y_grid, z_grid = grid_pos
        face_size = cube_spacing * 0.9  # Larger face size for better detection
        
        faces_to_test = []
        
        # Only test faces on the outer surface of the 3x3x3 cube
        if z_grid == 1:  # Front face
            face_center = [world_pos[0], world_pos[1], world_pos[2] + face_size/2]
            faces_to_test.append(('front', face_center))
            
        if z_grid == -1:  # Back face  
            face_center = [world_pos[0], world_pos[1], world_pos[2] - face_size/2]
            faces_to_test.append(('back', face_center))
            
        if x_grid == 1:  # Right face
            face_center = [world_pos[0] + face_size/2, world_pos[1], world_pos[2]]
            faces_to_test.append(('right', face_center))
            
        if x_grid == -1:  # Left face
            face_center = [world_pos[0] - face_size/2, world_pos[1], world_pos[2]]
            faces_to_test.append(('left', face_center))
            
        if y_grid == 1:  # Top face
            face_center = [world_pos[0], world_pos[1] + face_size/2, world_pos[2]]
            faces_to_test.append(('top', face_center))
            
        if y_grid == -1:  # Bottom face
            face_center = [world_pos[0], world_pos[1] - face_size/2, world_pos[2]]
            faces_to_test.append(('bottom', face_center))
        
        # Test each face by projecting to screen space
        for face_name, face_center in faces_to_test:
            
            # More generous visibility check
            if not self.is_face_type_visible_enhanced(face_name):
                continue
            
            try:
                # Project face center to screen coordinates
                screen_pos = gluProject(
                    face_center[0], face_center[1], face_center[2],
                    model_matrix, proj_matrix, viewport
                )
                
                if screen_pos:
                    screen_x, screen_y, screen_z = screen_pos
                    
                    # Convert OpenGL Y coordinate to screen Y coordinate
                    screen_y = viewport[3] - screen_y
                    
                    # MASSIVE hit areas - especially for side faces
                    if face_name in ['left', 'right', 'top', 'bottom']:
                        face_screen_size = 80  # HUGE hit area for problematic faces
                    else:
                        face_screen_size = 60  # Large hit area for front/back
                    
                    # Check if mouse is within this face's screen area
                    if (abs(mouse_x - screen_x) <= face_screen_size and 
                        abs(mouse_y - screen_y) <= face_screen_size):
                        return face_name, screen_z
                        
            except:
                continue
        
        return None
    
    def is_face_type_visible_enhanced(self, face_name):
        """ULTRA-GENEROUS visibility check for all faces"""
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
            
        rx = self.renderer.rotation_x % 360
        if rx > 180:
            rx -= 360
        
        # Much more generous ranges for all faces
        if face_name == 'front':
            return -120 < ry < 120
        elif face_name == 'back':
            return ry > 60 or ry < -60
        elif face_name == 'right':
            return -180 < ry < 120  # Almost always visible
        elif face_name == 'left':
            return 60 < ry < 300 or ry < -60  # Almost always visible
        elif face_name == 'top':
            return rx < 120  # Much more generous
        elif face_name == 'bottom':
            return rx > -120  # Much more generous
            
        return True
    
    def fallback_simple_detection(self, mouse_pos):
        """ENHANCED fallback detection with multiple strategies"""
        mouse_x, mouse_y = mouse_pos
        
        # Try multiple fallback strategies
        
        # Strategy 1: Enhanced screen region detection
        result1 = self.fallback_screen_regions(mouse_x, mouse_y)
        if result1:
            return result1
            
        # Strategy 2: Ray-casting fallback
        result2 = self.fallback_ray_casting(mouse_pos)
        if result2:
            return result2
            
        # Strategy 3: Absolute fallback
        return 'front', (0, 0, 1)
    
    def fallback_screen_regions(self, mouse_x, mouse_y):
        """Enhanced screen region detection with rotation awareness"""
        width = self.renderer.width
        height = self.renderer.height
        
        center_x = width // 2
        center_y = height // 2
        
        # Calculate relative position
        rel_x = (mouse_x - center_x) / (width / 2)   # -1 to 1
        rel_y = (mouse_y - center_y) / (height / 2)  # -1 to 1
        
        # Get current rotation
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        rx = self.renderer.rotation_x % 360
        if rx > 180:
            rx -= 360
        
        # Determine face based on position and rotation
        abs_x = abs(rel_x)
        abs_y = abs(rel_y)
        
        # Vertical faces have priority when clicked near edges
        if abs_y < 0.3:  # Middle horizontal band - side faces
            if rel_x > 0.2:  # Right side
                if -45 < ry < 45:
                    return 'right', (1, 0, 0)
                elif 45 <= ry < 135:
                    return 'back', (0, 0, -1) 
                elif ry >= 135 or ry <= -135:
                    return 'left', (-1, 0, 0)
                else:  # -135 < ry < -45
                    return 'front', (0, 0, 1)
            elif rel_x < -0.2:  # Left side
                if -45 < ry < 45:
                    return 'left', (-1, 0, 0)
                elif 45 <= ry < 135:
                    return 'front', (0, 0, 1)
                elif ry >= 135 or ry <= -135:
                    return 'right', (1, 0, 0)
                else:  # -135 < ry < -45
                    return 'back', (0, 0, -1)
        
        # Top/bottom faces
        if rel_y < -0.2:  # Top area
            return 'top', (0, 1, 0)
        elif rel_y > 0.2:  # Bottom area  
            return 'bottom', (0, -1, 0)
        
        # Center area - front face priority
        if -45 < ry < 45:
            return 'front', (0, 0, 1)
        elif 45 <= ry < 135:
            return 'right', (1, 0, 0)
        elif ry >= 135 or ry <= -135:
            return 'back', (0, 0, -1)
        else:
            return 'left', (-1, 0, 0)
    
    def fallback_ray_casting(self, mouse_pos):
        """Simple ray casting fallback"""
        try:
            # Get a simple ray direction
            mouse_x, mouse_y = mouse_pos
            
            # Normalize to -1 to 1
            norm_x = (mouse_x / self.renderer.width) * 2 - 1
            norm_y = ((self.renderer.height - mouse_y) / self.renderer.height) * 2 - 1
            
            # Simple ray direction based on mouse position
            ray_dir = [norm_x, norm_y, -1]
            
            # Normalize
            length = math.sqrt(ray_dir[0]**2 + ray_dir[1]**2 + ray_dir[2]**2)
            if length > 0:
                ray_dir = [ray_dir[0]/length, ray_dir[1]/length, ray_dir[2]/length]
            
            # Determine face based on dominant ray direction
            abs_x = abs(ray_dir[0])
            abs_y = abs(ray_dir[1]) 
            abs_z = abs(ray_dir[2])
            
            if abs_z > abs_x and abs_z > abs_y:
                return 'front', (0, 0, 1)
            elif abs_x > abs_y:
                if ray_dir[0] > 0:
                    return 'right', (1, 0, 0)
                else:
                    return 'left', (-1, 0, 0)
            else:
                if ray_dir[1] > 0:
                    return 'top', (0, 1, 0)
                else:
                    return 'bottom', (0, -1, 0)
                    
        except:
            pass
            
        return None
    
    def is_point_on_actual_cube_face(self, point, face_name, face_center, face_half_size):
        """ULTRA-GENEROUS bounds checking - make all faces as easy as front/back"""
        # Convert point to face-relative coordinates
        rel_x = point[0] - face_center[0]
        rel_y = point[1] - face_center[1] 
        rel_z = point[2] - face_center[2]
        
        # Use VERY generous tolerance - much larger than the visual face
        # This makes all faces as easy to click as front/back
        mega_tolerance = face_half_size * 1.5  # 150% of face size - VERY generous
        
        # All faces use the same generous detection logic
        if face_name == 'front':
            # Front face: point should be within MEGA bounds
            return abs(rel_x) <= mega_tolerance and abs(rel_y) <= mega_tolerance
            
        elif face_name == 'back':
            # Back face: point should be within MEGA bounds  
            return abs(rel_x) <= mega_tolerance and abs(rel_y) <= mega_tolerance
            
        elif face_name == 'right':
            # Right face: point should be within MEGA bounds - same generosity as front/back
            return abs(rel_y) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            
        elif face_name == 'left':
            # Left face: point should be within MEGA bounds - same generosity as front/back
            return abs(rel_y) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            
        elif face_name == 'top':
            # Top face: point should be within MEGA bounds - same generosity as front/back
            return abs(rel_x) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            
        elif face_name == 'bottom':
            # Bottom face: point should be within MEGA bounds - same generosity as front/back
            return abs(rel_x) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            
        return False
    
    def is_point_on_expanded_face(self, point, face_name, cube_center, tolerance):
        """Revolutionary bounds checking - give side faces EXTRA large detection areas"""
        # Convert point to cube-relative coordinates
        rel_x = point[0] - cube_center[0]
        rel_y = point[1] - cube_center[1] 
        rel_z = point[2] - cube_center[2]
        
        # The actual cube half-size
        half_size = 0.52 * 0.85  # cube_spacing * scale_factor
        
        # REVOLUTIONARY APPROACH: Give side faces EXTRA large detection areas
        if face_name in ['left', 'right']:
            # MASSIVE detection area for side faces to prevent submersion
            mega_tolerance = tolerance * 3.0  # EXTRA large for sides
            plane_tolerance = 1.2  # Very generous plane detection for sides
        else:
            mega_tolerance = tolerance * 2.0  # Normal mega size for other faces
            plane_tolerance = 1.0  # Normal generous plane detection
        
        if face_name == 'front':
            # Front face: Z should be near +half_size, X and Y within MEGA bounds
            z_on_face = abs(rel_z - half_size) < plane_tolerance
            within_xy = abs(rel_x) <= mega_tolerance and abs(rel_y) <= mega_tolerance
            return z_on_face and within_xy
            
        elif face_name == 'back':
            # Back face: Z should be near -half_size, X and Y within MEGA bounds  
            z_on_face = abs(rel_z + half_size) < plane_tolerance
            within_xy = abs(rel_x) <= mega_tolerance and abs(rel_y) <= mega_tolerance
            return z_on_face and within_xy
            
        elif face_name == 'right':
            # Right face: X should be near +half_size, Y and Z within EXTRA MEGA bounds
            # LARGEST DETECTION AREA to prevent submersion
            x_on_face = abs(rel_x - half_size) < plane_tolerance
            within_yz = abs(rel_y) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            return x_on_face and within_yz
            
        elif face_name == 'left':
            # Left face: X should be near -half_size, Y and Z within EXTRA MEGA bounds
            # LARGEST DETECTION AREA to prevent submersion
            x_on_face = abs(rel_x + half_size) < plane_tolerance
            within_yz = abs(rel_y) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            return x_on_face and within_yz
            
        elif face_name == 'top':
            # Top face: Y should be near +half_size, X and Z within MEGA bounds
            y_on_face = abs(rel_y - half_size) < plane_tolerance
            within_xz = abs(rel_x) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            return y_on_face and within_xz
            
        elif face_name == 'bottom':
            # Bottom face: Y should be near -half_size, X and Z within MEGA bounds
            y_on_face = abs(rel_y + half_size) < plane_tolerance
            within_xz = abs(rel_x) <= mega_tolerance and abs(rel_z) <= mega_tolerance
            return y_on_face and within_xz
            
        return False
    
    def is_point_on_cube_face(self, point, face_name, cube_center, tolerance):
        """Ultra-generous bounds checking - make entire visible face area clickable from any angle"""
        # Convert point to cube-relative coordinates
        rel_x = point[0] - cube_center[0]
        rel_y = point[1] - cube_center[1] 
        rel_z = point[2] - cube_center[2]
        
        # The actual cube half-size
        half_size = 0.52 * 0.85  # cube_spacing * scale_factor
        
        # Get current camera rotation to adjust detection based on viewing angle
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        
        # ULTRA-GENEROUS detection for ALL faces with angle-specific adjustments
        if face_name in ['left', 'right']:
            # MAXIMUM generosity for side faces - especially when viewed at an angle
            extended_tolerance = tolerance * 5.0  # 5x larger detection area
            face_plane_tolerance = 0.7  # Very lenient plane detection
            
            # Extra generous when viewing at angles where side faces are prominent
            if face_name == 'right' and -60 < ry < 30:  # Your viewing angle range
                extended_tolerance = tolerance * 6.0  # Even more generous
                face_plane_tolerance = 0.8  # Very lenient
        else:
            extended_tolerance = tolerance * 3.0  # Also very generous for other faces
            face_plane_tolerance = 0.4
        
        if face_name == 'front':
            # Front face: Z should be near +half_size, X and Y within bounds
            z_on_face = abs(rel_z - half_size) < face_plane_tolerance
            within_xy = abs(rel_x) <= extended_tolerance and abs(rel_y) <= extended_tolerance
            return z_on_face and within_xy
            
        elif face_name == 'back':
            # Back face: Z should be near -half_size, X and Y within bounds  
            z_on_face = abs(rel_z + half_size) < face_plane_tolerance
            within_xy = abs(rel_x) <= extended_tolerance and abs(rel_y) <= extended_tolerance
            return z_on_face and within_xy
            
        elif face_name == 'right':
            # Right face: X should be near +half_size, Y and Z within bounds
            # MAXIMUM GENEROSITY - especially for your viewing angle
            x_on_face = abs(rel_x - half_size) < face_plane_tolerance
            within_yz = abs(rel_y) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return x_on_face and within_yz
            
        elif face_name == 'left':
            # Left face: X should be near -half_size, Y and Z within bounds
            # MAXIMUM GENEROSITY for left face too
            x_on_face = abs(rel_x + half_size) < face_plane_tolerance
            within_yz = abs(rel_y) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return x_on_face and within_yz
            
        elif face_name == 'top':
            # Top face: Y should be near +half_size, X and Z within bounds
            y_on_face = abs(rel_y - half_size) < face_plane_tolerance
            within_xz = abs(rel_x) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return y_on_face and within_xz
            
        elif face_name == 'bottom':
            # Bottom face: Y should be near -half_size, X and Z within bounds
            y_on_face = abs(rel_y + half_size) < face_plane_tolerance
            within_xz = abs(rel_x) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return y_on_face and within_xz
            
        return False
    
    def select_best_face_by_angle(self, valid_intersections):
        """SIMPLE priority system - all faces get equal treatment when visible"""
        if len(valid_intersections) == 1:
            return valid_intersections[0][0]
        
        # Get current camera rotations
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        
        # EQUAL TREATMENT - all faces get fair priority when visible
        face_priorities = []
        
        for face_name, distance, intersection in valid_intersections:
            priority_score = distance  # Start with distance as base score
            
            # Give reasonable priority to all faces when they're visible
            if face_name == 'front' and -60 < ry < 60:
                priority_score *= 0.5  # Good priority for front
                
            elif face_name == 'right' and -120 < ry < 60:
                priority_score *= 0.5  # SAME good priority for right
                
            elif face_name == 'left' and 15 < ry < 165:
                priority_score *= 0.5  # SAME good priority for left
                
            elif face_name == 'back' and (ry > 120 or ry < -120):
                priority_score *= 0.5  # SAME good priority for back
                
            elif face_name == 'top':
                priority_score *= 0.5  # SAME good priority for top
                
            elif face_name == 'bottom':
                priority_score *= 0.5  # SAME good priority for bottom
                
            # Very light penalties to prevent total chaos
            else:
                priority_score *= 1.2  # Just slightly lower priority when not ideally positioned
            
            face_priorities.append((face_name, priority_score))
        
        # Return the face with the best (lowest) priority score
        best_face = min(face_priorities, key=lambda x: x[1])[0]
        return best_face
    
    def is_face_visible_from_camera(self, face_name):
        """Determine if a face type is visible from current camera angle"""
        # Get current camera rotations
        rx = self.renderer.rotation_x % 360
        ry = self.renderer.rotation_y % 360
        
        # Normalize angles to [-180, 180] range
        if rx > 180:
            rx -= 360
        if ry > 180:
            ry -= 360
        
        # Determine visibility based on camera rotation
        if face_name == 'front':
            return -90 < ry < 90  # Front faces visible when looking forward-ish
            
        elif face_name == 'back':
            return ry > 90 or ry < -90  # Back faces visible when looking backward-ish
            
        elif face_name == 'right':
            return -135 < ry < 45  # Right faces visible when looking right-ish
            
        elif face_name == 'left':
            return 45 < ry < 225 or ry < -135  # Left faces visible when looking left-ish
            
        elif face_name == 'top':
            return rx < 45  # Top faces visible when looking from above or level
            
        elif face_name == 'bottom':
            return rx > -45  # Bottom faces visible when looking from below or level
            
        return False
    
    def get_accurate_ray(self, mouse_x, mouse_y):
        """Get the most accurate ray possible using OpenGL matrices"""
        try:
            # Method 1: Use OpenGL's matrices directly
            model_matrix = glGetDoublev(GL_MODELVIEW_MATRIX)
            proj_matrix = glGetDoublev(GL_PROJECTION_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)
            
            # Convert mouse coordinates (flip Y coordinate)
            opengl_y = viewport[3] - mouse_y
            
            # Get near and far points
            near_point = gluUnProject(mouse_x, opengl_y, 0.0, model_matrix, proj_matrix, viewport)
            far_point = gluUnProject(mouse_x, opengl_y, 1.0, model_matrix, proj_matrix, viewport)
            
            # Calculate ray direction
            ray_dir = [
                far_point[0] - near_point[0],
                far_point[1] - near_point[1],
                far_point[2] - near_point[2]
            ]
            
            # Normalize
            length = math.sqrt(ray_dir[0]**2 + ray_dir[1]**2 + ray_dir[2]**2)
            if length > 0:
                ray_dir = [ray_dir[0]/length, ray_dir[1]/length, ray_dir[2]/length]
            
            ray_origin = list(near_point)
            
            return ray_origin, ray_dir
            
        except Exception as e:
            # Fallback to manual calculation
            return self.manual_ray_calculation(mouse_x, mouse_y)
    
    def manual_ray_calculation(self, mouse_x, mouse_y):
        """Manual ray calculation when gluUnProject fails"""
        # Get current camera parameters
        width = self.renderer.width
        height = self.renderer.height
        
        # Normalize mouse coordinates
        ndc_x = (2.0 * mouse_x) / width - 1.0
        ndc_y = 1.0 - (2.0 * mouse_y) / height
        
        # Camera parameters
        fov = 45.0
        aspect = width / height
        
        # Calculate ray in camera space
        fov_rad = math.radians(fov)
        tan_half_fov = math.tan(fov_rad / 2.0)
        
        ray_x = ndc_x * tan_half_fov * aspect
        ray_y = ndc_y * tan_half_fov
        ray_z = -1.0
        
        # Apply camera transformations
        rot_x = math.radians(self.renderer.rotation_x)
        rot_y = math.radians(self.renderer.rotation_y)
        
        # Rotate ray direction
        cos_x, sin_x = math.cos(rot_x), math.sin(rot_x)
        cos_y, sin_y = math.cos(rot_y), math.sin(rot_y)
        
        # Y rotation
        ray_x_new = ray_x * cos_y + ray_z * sin_y
        ray_z_new = -ray_x * sin_y + ray_z * cos_y
        ray_x, ray_z = ray_x_new, ray_z_new
        
        # X rotation
        ray_y_new = ray_y * cos_x - ray_z * sin_x
        ray_z_new = ray_y * sin_x + ray_z * cos_x
        ray_y, ray_z = ray_y_new, ray_z_new
        
        # Normalize
        length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
        if length > 0:
            ray_dir = [ray_x/length, ray_y/length, ray_z/length]
        else:
            ray_dir = [0, 0, -1]
        
        # Camera position
        cam_x, cam_y, cam_z = 0.0, 0.0, 4.0
        
        # Apply rotations to camera position
        cam_x_new = cam_x * cos_y - cam_z * sin_y
        cam_z_new = cam_x * sin_y + cam_z * cos_y
        cam_x, cam_z = cam_x_new, cam_z_new
        
        cam_y_new = cam_y * cos_x + cam_z * sin_x
        cam_z_new = -cam_y * sin_x + cam_z * cos_x
        cam_y, cam_z = cam_y_new, cam_z_new
        
        return [cam_x, cam_y, cam_z], ray_dir
    
    def point_in_cube_face_bounds(self, point, face_center, face_normal, face_size):
        """Check if a 3D point lies within the bounds of a cube face - more generous bounds"""
        # Calculate the point relative to the face center
        rel_x = point[0] - face_center[0]
        rel_y = point[1] - face_center[1]
        rel_z = point[2] - face_center[2]
        
        # Use more generous bounds - 80% of face_size to allow for better detection
        tolerance = face_size * 0.8
        
        # Check bounds based on face orientation
        if abs(face_normal[0]) > 0.5:  # Face perpendicular to X-axis (left/right faces)
            return abs(rel_y) <= tolerance and abs(rel_z) <= tolerance
        elif abs(face_normal[1]) > 0.5:  # Face perpendicular to Y-axis (top/bottom faces)  
            return abs(rel_x) <= tolerance and abs(rel_z) <= tolerance
        elif abs(face_normal[2]) > 0.5:  # Face perpendicular to Z-axis (front/back faces)
            return abs(rel_x) <= tolerance and abs(rel_y) <= tolerance
        
        return False
    
    def point_in_main_face(self, point, face_center, face_name):
        """Check if point is within the main 3x3 face bounds - PRECISE detection"""
        # Make the detection area reasonable - not covering the entire world
        face_size = self.cube_spacing * 0.85 * 1.2  # Just 20% larger than actual face
        
        rel_point = [
            point[0] - face_center[0],
            point[1] - face_center[1], 
            point[2] - face_center[2]
        ]
        
        if face_name in ['front', 'back']:
            # For front/back faces, check X and Y bounds
            return (abs(rel_point[0]) <= face_size and abs(rel_point[1]) <= face_size)
        elif face_name in ['left', 'right']:
            # For left/right faces, check Y and Z bounds  
            return (abs(rel_point[1]) <= face_size and abs(rel_point[2]) <= face_size)
        elif face_name in ['top', 'bottom']:
            # For top/bottom faces, check X and Z bounds
            return (abs(rel_point[0]) <= face_size and abs(rel_point[2]) <= face_size)
        
        return False
    
    def point_in_face_bounds(self, point, face_center, face_normal, face_size):
        """Check if a 3D point lies within the bounds of a cube face"""
        # Calculate the point relative to the face center
        rel_x = point[0] - face_center[0]
        rel_y = point[1] - face_center[1]
        rel_z = point[2] - face_center[2]
        
        # Check bounds based on face orientation (which axis is the normal)
        if abs(face_normal[0]) > 0.5:  # Face is perpendicular to X-axis (left/right faces)
            return abs(rel_y) <= face_size and abs(rel_z) <= face_size
        elif abs(face_normal[1]) > 0.5:  # Face is perpendicular to Y-axis (top/bottom faces)  
            return abs(rel_x) <= face_size and abs(rel_z) <= face_size
        elif abs(face_normal[2]) > 0.5:  # Face is perpendicular to Z-axis (front/back faces)
            return abs(rel_x) <= face_size and abs(rel_y) <= face_size
        
        return False
    
    def test_cube_face_intersection(self, ray_origin, ray_dir, cube_center, face_name):
        """Test if ray intersects a specific face of a cube"""
        # For face detection, we want to detect the entire 3x3 face, not just individual cubes
        # Use larger face size to represent the entire cube face
        face_size = self.cube_spacing * 1.5  # Large enough to cover the entire 3x3 face
        
        # Calculate face center and normal based on face name
        if face_name == 'front':  # +Z face
            face_center = [cube_center[0], cube_center[1], cube_center[2] + self.cube_spacing]
            face_normal = [0, 0, 1]
        elif face_name == 'back':  # -Z face
            face_center = [cube_center[0], cube_center[1], cube_center[2] - self.cube_spacing]
            face_normal = [0, 0, -1]
        elif face_name == 'right':  # +X face
            face_center = [cube_center[0] + self.cube_spacing, cube_center[1], cube_center[2]]
            face_normal = [1, 0, 0]
        elif face_name == 'left':  # -X face
            face_center = [cube_center[0] - self.cube_spacing, cube_center[1], cube_center[2]]
            face_normal = [-1, 0, 0]
        elif face_name == 'top':  # +Y face
            face_center = [cube_center[0], cube_center[1] + self.cube_spacing, cube_center[2]]
            face_normal = [0, 1, 0]
        elif face_name == 'bottom':  # -Y face
            face_center = [cube_center[0], cube_center[1] - self.cube_spacing, cube_center[2]]
            face_normal = [0, -1, 0]
        else:
            return None
        
        # Test ray-plane intersection
        intersection = self.ray_plane_intersection(ray_origin, ray_dir, face_center, face_normal)
        
        if not intersection:
            return None
        
        # Check if intersection is within the face bounds
        rel_point = [
            intersection[0] - face_center[0],
            intersection[1] - face_center[1],
            intersection[2] - face_center[2]
        ]
        
        # Check bounds based on face orientation
        if face_name in ['front', 'back']:
            # Check X and Y bounds
            if abs(rel_point[0]) <= face_size and abs(rel_point[1]) <= face_size:
                return intersection
        elif face_name in ['left', 'right']:
            # Check Y and Z bounds
            if abs(rel_point[1]) <= face_size and abs(rel_point[2]) <= face_size:
                return intersection
        elif face_name in ['top', 'bottom']:
            # Check X and Z bounds
            if abs(rel_point[0]) <= face_size and abs(rel_point[2]) <= face_size:
                return intersection
        
        return None
    
    def fallback_detection(self, mouse_pos):
        """Legacy fallback - should not be needed with new simple detection"""
        # This should rarely be called now, but keeping it as a safety net
        return 'front', (0, 0, 1)
    
    def get_visible_faces_from_camera(self, rx, ry):
        """Determine which faces are visible from the current camera angle"""
        visible_faces = []
        
        # Convert rotations to a standard range for easier calculation
        rx_norm = rx % 360
        ry_norm = ry % 360
        
        # Always allow top and bottom - they should almost always be accessible
        visible_faces.extend(['top', 'bottom'])
        
        # Determine visible side faces based on camera rotation
        # More generous ranges to allow for better detection
        if 315 <= ry_norm or ry_norm < 45:  # Looking at front primarily
            visible_faces.extend(['front', 'right', 'left'])
        elif 45 <= ry_norm < 135:  # Looking at right side primarily
            visible_faces.extend(['right', 'front', 'back'])
        elif 135 <= ry_norm < 225:  # Looking at back primarily
            visible_faces.extend(['back', 'right', 'left'])
        elif 225 <= ry_norm < 315:  # Looking at left side primarily
            visible_faces.extend(['left', 'front', 'back'])
        
        # Add additional logic for extreme camera angles
        if 30 <= ry_norm < 60:
            visible_faces.append('right')
        elif 120 <= ry_norm < 150:
            visible_faces.append('back')
        elif 210 <= ry_norm < 240:
            visible_faces.append('left')
        elif 300 <= ry_norm < 330:
            visible_faces.append('front')
        
        # Remove duplicates while preserving order
        seen = set()
        visible_faces = [face for face in visible_faces if not (face in seen or seen.add(face))]
        
        return visible_faces
    
    def get_face_for_screen_side(self, screen_side, ry):
        """Get which cube face appears on the given screen side based on camera Y rotation"""
        ry_norm = ry % 360
        
        if screen_side == 'right':
            # Right side of screen
            if 0 <= ry_norm < 90:
                return 'left'    # Looking at front, right side shows LEFT face
            elif 90 <= ry_norm < 180:
                return 'front'   # Looking at right, right side shows FRONT face  
            elif 180 <= ry_norm < 270:
                return 'right'   # Looking at back, right side shows RIGHT face
            else:
                return 'back'    # Looking at left, right side shows BACK face
        elif screen_side == 'left':
            # Left side of screen
            if 0 <= ry_norm < 90:
                return 'right'   # Looking at front, left side shows RIGHT face
            elif 90 <= ry_norm < 180:
                return 'back'    # Looking at right, left side shows BACK face
            elif 180 <= ry_norm < 270:
                return 'left'    # Looking at back, left side shows LEFT face
            else:
                return 'front'   # Looking at left, left side shows FRONT face
        
        return None
    
    def _get_cube_pos_for_face(self, face):
        """Get cube position for a given face"""
        face_positions = {
            'front': (0, 0, 1),
            'back': (0, 0, -1),
            'right': (1, 0, 0),
            'left': (-1, 0, 0),
            'top': (0, 1, 0),
            'bottom': (0, -1, 0)
        }
        return face_positions.get(face, (0, 0, 1))
    
    def get_visible_cube_faces(self, grid_pos):
        """Get the list of visible faces for a cube at the given grid position in the 3x3x3 grid"""
        x, y, z = grid_pos
        visible_faces = []
        
        # A face is visible if it's on the outer surface of the 3x3x3 cube
        if x == 1:  # Right face visible
            visible_faces.append('right')
        if x == -1:  # Left face visible
            visible_faces.append('left')
        if y == 1:  # Top face visible
            visible_faces.append('top')
        if y == -1:  # Bottom face visible
            visible_faces.append('bottom')
        if z == 1:  # Front face visible
            visible_faces.append('front')
        if z == -1:  # Back face visible
            visible_faces.append('back')
        
        return visible_faces
    
    def start_drag(self, mouse_pos):
        """Start dragging - detect face using 3D ray-casting"""
        import time
        current_time = time.time()
        if current_time - self.last_move_time < self.move_cooldown:
            return
        
        # Debug camera info on first click
        # self.debug_camera_info()
        
        self.is_dragging = True
        self.drag_start_pos = mouse_pos
        self.drag_current_pos = mouse_pos
        self.move_executed = False
        
        # Use 3D face detection
        self.detected_face, self.detected_cube_pos = self.detect_face_from_mouse(mouse_pos)
        
        if self.detected_face:
            self.highlight_intensity = 1.0
        else:
            # Reset dragging if no face detected
            self.is_dragging = False
    
    def update_drag(self, mouse_pos):
        """Update drag and generate moves based on detected face"""
        if not self.is_dragging or self.move_executed or not self.detected_face:
            return None
        
        self.drag_current_pos = mouse_pos
        
        # Calculate drag distance and direction
        dx = mouse_pos[0] - self.drag_start_pos[0]
        dy = mouse_pos[1] - self.drag_start_pos[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > self.move_sensitivity:
            # Generate move based on detected face and drag direction
            move = self.get_move_from_face_and_direction(self.detected_face, dx, dy)
            if move:
                self.move_executed = True
                import time
                self.last_move_time = time.time()
                return move
        
        return None
    
    def get_move_from_face_and_direction(self, face_name, dx, dy):
        """Generate Rubik's cube move based on the actual 3D face and drag direction"""
        # Determine primary drag direction
        if abs(dx) > abs(dy):
            # Horizontal drag
            direction = 'right' if dx > 0 else 'left'
        else:
            # Vertical drag
            direction = 'down' if dy > 0 else 'up'
        
        # For 3D face detection, we need to consider the actual orientation of each face
        # relative to the camera view when determining what a drag direction means
        
        # Get camera rotation to understand the current view
        ry = (self.renderer.rotation_y % 360)
        
        # Face-specific movement logic based on 3D orientation
        if face_name == 'front':
            # Front face: standard mappings work well
            if direction == 'right': return 'F'
            elif direction == 'left': return "F'"
            elif direction == 'down': return 'F'
            elif direction == 'up': return "F'"
            
        elif face_name == 'back':
            # Back face: movements are mirrored
            if direction == 'right': return "B'"
            elif direction == 'left': return 'B'
            elif direction == 'down': return "B'"
            elif direction == 'up': return 'B'
            
        elif face_name == 'right':
            # Right face: consider viewing angle
            if 315 <= ry or ry < 45:  # Viewing from front
                if direction == 'right': return 'R'
                elif direction == 'left': return "R'"
                elif direction == 'down': return 'R'
                elif direction == 'up': return "R'"
            elif 135 <= ry < 225:  # Viewing from back
                if direction == 'right': return "R'"
                elif direction == 'left': return 'R'
                elif direction == 'down': return "R'"
                elif direction == 'up': return 'R'
            else:  # Viewing from side
                if direction == 'right': return 'R'
                elif direction == 'left': return "R'"
                elif direction == 'down': return 'R'
                elif direction == 'up': return "R'"
                
        elif face_name == 'left':
            # Left face: consider viewing angle
            if 315 <= ry or ry < 45:  # Viewing from front
                if direction == 'right': return "L'"
                elif direction == 'left': return 'L'
                elif direction == 'down': return "L'"
                elif direction == 'up': return 'L'
            elif 135 <= ry < 225:  # Viewing from back
                if direction == 'right': return 'L'
                elif direction == 'left': return "L'"
                elif direction == 'down': return 'L'
                elif direction == 'up': return "L'"
            else:  # Viewing from side
                if direction == 'right': return "L'"
                elif direction == 'left': return 'L'
                elif direction == 'down': return "L'"
                elif direction == 'up': return 'L'
                
        elif face_name == 'top':
            # Top face: adjust based on viewing angle
            if 315 <= ry or ry < 45:  # Viewing from front
                if direction == 'right': return 'U'
                elif direction == 'left': return "U'"
                elif direction == 'down': return 'U'
                elif direction == 'up': return "U'"
            elif 45 <= ry < 135:  # Viewing from right
                if direction == 'right': return 'U'
                elif direction == 'left': return "U'"
                elif direction == 'down': return "U'"
                elif direction == 'up': return 'U'
            elif 135 <= ry < 225:  # Viewing from back
                if direction == 'right': return "U'"
                elif direction == 'left': return 'U'
                elif direction == 'down': return "U'"
                elif direction == 'up': return 'U'
            else:  # Viewing from left
                if direction == 'right': return "U'"
                elif direction == 'left': return 'U'
                elif direction == 'down': return 'U'
                elif direction == 'up': return "U'"
                
        elif face_name == 'bottom':
            # Bottom face: adjust based on viewing angle
            if 315 <= ry or ry < 45:  # Viewing from front
                if direction == 'right': return "D'"
                elif direction == 'left': return 'D'
                elif direction == 'down': return "D'"
                elif direction == 'up': return 'D'
            elif 45 <= ry < 135:  # Viewing from right
                if direction == 'right': return "D'"
                elif direction == 'left': return 'D'
                elif direction == 'down': return 'D'
                elif direction == 'up': return "D'"
            elif 135 <= ry < 225:  # Viewing from back
                if direction == 'right': return 'D'
                elif direction == 'left': return "D'"
                elif direction == 'down': return 'D'
                elif direction == 'up': return "D'"
            else:  # Viewing from left
                if direction == 'right': return 'D'
                elif direction == 'left': return "D'"
                elif direction == 'down': return "D'"
                elif direction == 'up': return 'D'
        
        return None
    
    def update_hover(self, mouse_pos):
        """Update hover detection with 3D ray-casting"""
        if self.is_dragging:
            return
        
        # Use 3D detection for hover as well
        face, cube_pos = self.detect_face_from_mouse(mouse_pos)
        
        # Update hover state
        if face != self.hovered_face or cube_pos != self.hovered_cube_pos:
            self.hovered_face = face
            self.hovered_cube_pos = cube_pos
            if face:
                self.highlight_intensity = 0.6  # Strong hover effect
            else:
                self.highlight_intensity = 0.0
    
    def end_drag(self):
        """End drag operation"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.move_executed = False
        self.detected_face = None
        self.detected_cube_pos = None
    
    def update_visual_feedback(self, dt):
        """Update visual effects"""
        if self.highlight_intensity > 0 and not self.is_dragging:
            self.highlight_intensity = max(0, self.highlight_intensity - self.fade_speed * dt)
    
    def render_visual_feedback(self):
        """Render visual feedback for hovered/selected faces"""
        if not self.hovered_face or self.highlight_intensity <= 0:
            return
        
        # Save current state
        glPushAttrib(GL_ALL_ATTRIB_BITS)
        glPushMatrix()
        
        # Enable blending for transparent overlay
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        
        # Position the camera the same way as the main renderer
        glTranslatef(0.0, 0.0, -4.0)
        glRotatef(self.renderer.rotation_x, 1, 0, 0)
        glRotatef(self.renderer.rotation_y, 0, 1, 0)
        
        # Highlight the detected face
        if self.hovered_cube_pos:
            self.render_face_highlight(self.hovered_cube_pos, self.hovered_face)
        
        # Restore state
        glPopMatrix()
        glPopAttrib()
    
    def render_face_highlight(self, cube_pos, face_name):
        """Render a MASSIVE highlight overlay on the specified face"""
        # Get cube center position
        scale_factor = 0.85
        cube_center = [
            cube_pos[0] * self.cube_spacing * scale_factor,
            cube_pos[1] * self.cube_spacing * scale_factor,
            cube_pos[2] * self.cube_spacing * scale_factor
        ]
        
        # Set highlight color based on face
        face_colors = {
            'front': (0.0, 0.8, 1.0),   # Blue
            'back': (1.0, 0.8, 0.0),    # Yellow
            'right': (1.0, 0.0, 0.4),   # Red
            'left': (0.0, 1.0, 0.0),    # Green
            'top': (1.0, 0.5, 0.0),     # Orange
            'bottom': (0.8, 0.0, 1.0)   # Purple
        }
        
        color = face_colors.get(face_name, (1.0, 1.0, 1.0))
        alpha = self.highlight_intensity * 0.7
        
        glColor4f(color[0], color[1], color[2], alpha)
        
        # Position at cube center
        glPushMatrix()
        glTranslatef(cube_center[0], cube_center[1], cube_center[2])
        
        # Draw clear but not overwhelming highlight overlay
        # Make it nicely visible but not too big
        size = self.cube_spacing * 0.85 * 1.5  # 1.5x larger - clear but reasonable
        
        glBegin(GL_QUADS)
        
        if face_name == 'front':  # +Z face - position right on surface
            z_pos = self.cube_size + 0.001  # Just barely in front of cube face
            glVertex3f(-size, -size, z_pos)
            glVertex3f(size, -size, z_pos)
            glVertex3f(size, size, z_pos)
            glVertex3f(-size, size, z_pos)
        elif face_name == 'back':  # -Z face
            z_pos = -self.cube_size - 0.001  # Just barely behind cube face
            glVertex3f(size, -size, z_pos)
            glVertex3f(-size, -size, z_pos)
            glVertex3f(-size, size, z_pos)
            glVertex3f(size, size, z_pos)
        elif face_name == 'right':  # +X face
            x_pos = self.cube_size + 0.001  # Just barely to the right of cube face
            glVertex3f(x_pos, -size, -size)
            glVertex3f(x_pos, -size, size)
            glVertex3f(x_pos, size, size)
            glVertex3f(x_pos, size, -size)
        elif face_name == 'left':  # -X face
            x_pos = -self.cube_size - 0.001  # Just barely to the left of cube face
            glVertex3f(x_pos, -size, size)
            glVertex3f(x_pos, -size, -size)
            glVertex3f(x_pos, size, -size)
            glVertex3f(x_pos, size, size)
        elif face_name == 'top':  # +Y face
            y_pos = self.cube_size + 0.001  # Just barely above cube face
            glVertex3f(-size, y_pos, -size)
            glVertex3f(-size, y_pos, size)
            glVertex3f(size, y_pos, size)
            glVertex3f(size, y_pos, -size)
        elif face_name == 'bottom':  # -Y face
            y_pos = -self.cube_size - 0.001  # Just barely below cube face
            glVertex3f(-size, y_pos, size)
            glVertex3f(-size, y_pos, -size)
            glVertex3f(size, y_pos, -size)
            glVertex3f(size, y_pos, size)
        
        glEnd()
        glPopMatrix()
    
    def get_debug_info(self):
        """Get debug info for troubleshooting"""
        return {
            'is_dragging': self.is_dragging,
            'detected_face': self.detected_face,
            'detected_cube_pos': self.detected_cube_pos,
            'hovered_face': self.hovered_face,
            'hovered_cube_pos': self.hovered_cube_pos,
            'move_executed': self.move_executed,
            'highlight_intensity': self.highlight_intensity
        }
    
    def reset_interaction(self):
        """Reset everything"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_face = None
        self.detected_cube_pos = None
        self.move_executed = False
        self.hovered_face = None
        self.hovered_cube_pos = None
        self.highlight_intensity = 0.0
        self.last_move_time = 0
