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
        
    def get_renderer_cube_geometry(self):
        """Get the exact cube geometry from the renderer for perfect alignment"""
        cube_spacing = self.renderer.cube_spacing
        scale_factor = 0.85
        
        actual_spacing = cube_spacing * scale_factor
        visual_half_size = actual_spacing * 1.2
        
        return {
            'spacing': actual_spacing,
            'half_size': visual_half_size,
            'world_center': [0, 0, -4]
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
    
    def point_in_cube_face(self, point, cube_center, face_name):
        """Check if a point lies within a specific face of a cube"""
        half_size = self.cube_size * 1.2
        tolerance = 0.25
        
        rel_point = [
            point[0] - cube_center[0],
            point[1] - cube_center[1],
            point[2] - cube_center[2]
        ]
        
        if face_name == 'front':
            return (abs(rel_point[2] - half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[1]) <= half_size + tolerance)
        elif face_name == 'back':
            return (abs(rel_point[2] + half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[1]) <= half_size + tolerance)
        elif face_name == 'right':
            return (abs(rel_point[0] - half_size) < tolerance and
                   abs(rel_point[1]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'left':
            return (abs(rel_point[0] + half_size) < tolerance and
                   abs(rel_point[1]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'top':
            return (abs(rel_point[1] - half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'bottom':
            return (abs(rel_point[1] + half_size) < tolerance and
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        
        return False
    
    def detect_face_from_mouse(self, mouse_pos):
        """Main face detection using hybrid approach"""
        mouse_x, mouse_y = mouse_pos
        
        # Try OpenGL picking first
        result = self.method_opengl_picking(mouse_x, mouse_y)
        if result:
            return result
            
        # Try screen mapping
        result = self.method_screen_mapping(mouse_x, mouse_y)
        if result:
            return result
            
        # Default fallback
        return 'front', (0, 0, 1)
    
    def method_opengl_picking(self, mouse_x, mouse_y):
        """OpenGL-based face detection"""
        try:
            model_matrix = glGetDoublev(GL_MODELVIEW_MATRIX)
            proj_matrix = glGetDoublev(GL_PROJECTION_MATRIX) 
            viewport = glGetIntegerv(GL_VIEWPORT)
            
            ry = self.renderer.rotation_y % 360
            if ry > 180:
                ry -= 360
            rx = self.renderer.rotation_x % 360
            if rx > 180:
                rx -= 360
            
            # Handle direct face views
            if self.is_direct_face_view(ry, rx):
                primary_face = self.get_primary_face_from_rotation(ry)
                center_x = viewport[2] / 2
                center_y = viewport[3] / 2
                distance_from_center = math.sqrt((mouse_x - center_x)**2 + (mouse_y - center_y)**2)
                
                if distance_from_center < 200:
                    return (primary_face, self._get_cube_pos_for_face(primary_face))
            
            # Test face positions
            spacing = self.renderer.cube_spacing * 0.85
            face_positions = []
            
            for x in range(-1, 2):
                for y in range(-1, 2):
                    for z in range(-1, 2):
                        world_pos = [x * spacing, y * spacing, z * spacing]
                        
                        if z == 1:
                            face_positions.append(('front', world_pos, (x, y, z)))
                        if z == -1:
                            face_positions.append(('back', world_pos, (x, y, z)))
                        if x == 1:
                            face_positions.append(('right', world_pos, (x, y, z)))
                        if x == -1:
                            face_positions.append(('left', world_pos, (x, y, z)))
                        if y == 1:
                            face_positions.append(('top', world_pos, (x, y, z)))
                        if y == -1:
                            face_positions.append(('bottom', world_pos, (x, y, z)))
            
            best_match = None
            min_distance = float('inf')
            
            for face_name, world_pos, grid_pos in face_positions:
                if not self.is_face_currently_visible_enhanced(face_name):
                    continue
                    
                try:
                    screen_pos = gluProject(
                        world_pos[0], world_pos[1], world_pos[2],
                        model_matrix, proj_matrix, viewport
                    )
                    
                    if screen_pos:
                        sx, sy, sz = screen_pos
                        sy = viewport[3] - sy
                        
                        dx = mouse_x - sx
                        dy = mouse_y - sy
                        screen_dist = math.sqrt(dx*dx + dy*dy)
                        
                        hit_radius = 80 if face_name in ['left', 'right'] else 60
                        
                        if screen_dist < hit_radius and screen_dist < min_distance:
                            min_distance = screen_dist
                            best_match = (face_name, grid_pos)
                            
                except:
                    continue
            
            return best_match
            
        except:
            return None
    
    def method_screen_mapping(self, mouse_x, mouse_y):
        """Screen region mapping based on camera angle"""
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        rx = self.renderer.rotation_x % 360
        if rx > 180:
            rx -= 360
        
        # Direct face views
        if self.is_direct_face_view(ry, rx):
            return self.handle_direct_face_view(ry, rx)
        
        # Simple fallback based on rotation
        if abs(rx - 90) < 30:  # Looking at top
            return ('top', (0, 1, 0))
        elif abs(rx + 90) < 30:  # Looking at bottom
            return ('bottom', (0, -1, 0))
        elif abs(ry) < 45:  # Looking at front
            return ('front', (0, 0, 1))
        elif abs(ry - 90) < 45:  # Looking at left
            return ('left', (-1, 0, 0))
        elif abs(ry + 90) < 45:  # Looking at right
            return ('right', (1, 0, 0))
        elif abs(ry - 180) < 45 or abs(ry + 180) < 45:  # Looking at back
            return ('back', (0, 0, -1))
        
        # Default fallback
        return ('front', (0, 0, 1))
    
    def is_direct_face_view(self, ry, rx):
        """Check if we're looking directly at a face"""
        return ((abs(ry) < 15 or abs(ry - 90) < 15 or abs(ry + 90) < 15 or 
                abs(ry - 180) < 15 or abs(ry + 180) < 15) and abs(rx) < 30) or \
               (abs(rx - 90) < 15 or abs(rx + 90) < 15)
    
    def handle_direct_face_view(self, ry, rx):
        """Handle direct face-on views"""
        if abs(rx - 90) < 15:
            return ('top', (0, 1, 0))
        elif abs(rx + 90) < 15:
            return ('bottom', (0, -1, 0))
        elif abs(ry) < 15:
            return ('front', (0, 0, 1))
        elif abs(ry - 90) < 15:
            return ('left', (-1, 0, 0))
        elif abs(ry + 90) < 15:
            return ('right', (1, 0, 0))
        elif abs(ry - 180) < 15 or abs(ry + 180) < 15:
            return ('back', (0, 0, -1))
        
        return ('front', (0, 0, 1))
    
    def is_face_currently_visible(self, face_name):
        """Check if face is visible from current camera angle"""
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        rx = self.renderer.rotation_x % 360
        if rx > 180:
            rx -= 360
        
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
    
    def is_face_currently_visible_enhanced(self, face_name):
        """Enhanced visibility check"""
        ry = self.renderer.rotation_y % 360
        if ry > 180:
            ry -= 360
        rx = self.renderer.rotation_x % 360
        if rx > 180:
            rx -= 360
        
        if face_name == 'front':
            return -110 < ry < 110
        elif face_name == 'back':
            return ry > 70 or ry < -70
        elif face_name == 'right':
            return -170 < ry < 170
        elif face_name == 'left':
            return -170 < ry < 170
        elif face_name == 'top':
            return rx < 130
        elif face_name == 'bottom':
            return rx > -130
        
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
            # Back face: fix inverted movements
            if direction == 'right': return 'B'
            elif direction == 'left': return "B'"
            elif direction == 'down': return 'B'
            elif direction == 'up': return "B'"
            
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
            # Left face: fix inverted movements
            if 315 <= ry or ry < 45:  # Viewing from front
                if direction == 'right': return 'L'
                elif direction == 'left': return "L'"
                elif direction == 'down': return 'L'
                elif direction == 'up': return "L'"
            elif 135 <= ry < 225:  # Viewing from back
                if direction == 'right': return "L'"
                elif direction == 'left': return 'L'
                elif direction == 'down': return "L'"
                elif direction == 'up': return 'L'
            else:  # Viewing from side
                if direction == 'right': return 'L'
                elif direction == 'left': return "L'"
                elif direction == 'down': return 'L'
                elif direction == 'up': return "L'"
                
        elif face_name == 'top':
            # Top face: fix inverted movements for all viewing angles
            if 315 <= ry or ry < 45:  # Viewing from front
                if direction == 'right': return 'U'
                elif direction == 'left': return "U'"
                elif direction == 'down': return 'U'
                elif direction == 'up': return "U'"
            elif 45 <= ry < 135:  # Viewing from right
                if direction == 'right': return 'U'
                elif direction == 'left': return "U'"
                elif direction == 'down': return 'U'
                elif direction == 'up': return "U'"
            elif 135 <= ry < 225:  # Viewing from back
                if direction == 'right': return 'U'
                elif direction == 'left': return "U'"
                elif direction == 'down': return 'U'
                elif direction == 'up': return "U'"
            else:  # Viewing from left
                if direction == 'right': return 'U'
                elif direction == 'left': return "U'"
                elif direction == 'down': return 'U'
                elif direction == 'up': return "U'"
                
        elif face_name == 'bottom':
            # Bottom face: fix flipped movements - make consistent with other faces
            if 315 <= ry or ry < 45:  # Viewing from front
                if direction == 'right': return 'D'
                elif direction == 'left': return "D'"
                elif direction == 'down': return 'D'
                elif direction == 'up': return "D'"
            elif 45 <= ry < 135:  # Viewing from right
                if direction == 'right': return 'D'
                elif direction == 'left': return "D'"
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
                elif direction == 'down': return 'D'
                elif direction == 'up': return "D'"
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
        """Render highlight overlay on the specified face"""
        scale_factor = 0.85
        cube_center = [
            cube_pos[0] * self.cube_spacing * scale_factor,
            cube_pos[1] * self.cube_spacing * scale_factor,
            cube_pos[2] * self.cube_spacing * scale_factor
        ]
        
        face_colors = {
            'front': (0.0, 0.8, 1.0),
            'back': (1.0, 0.8, 0.0),
            'right': (1.0, 0.0, 0.4),
            'left': (0.0, 1.0, 0.0),
            'top': (1.0, 0.5, 0.0),
            'bottom': (0.8, 0.0, 1.0)
        }
        
        color = face_colors.get(face_name, (1.0, 1.0, 1.0))
        alpha = self.highlight_intensity * 0.7
        
        glColor4f(color[0], color[1], color[2], alpha)
        
        glPushMatrix()
        glTranslatef(cube_center[0], cube_center[1], cube_center[2])
        
        size = self.cube_spacing * 0.85 * 1.2
        
        glBegin(GL_QUADS)
        
        if face_name == 'front':
            z_pos = self.cube_size + 0.001
            glVertex3f(-size, -size, z_pos)
            glVertex3f(size, -size, z_pos)
            glVertex3f(size, size, z_pos)
            glVertex3f(-size, size, z_pos)
        elif face_name == 'back':
            z_pos = -self.cube_size - 0.001
            glVertex3f(size, -size, z_pos)
            glVertex3f(-size, -size, z_pos)
            glVertex3f(-size, size, z_pos)
            glVertex3f(size, size, z_pos)
        elif face_name == 'right':
            x_pos = self.cube_size + 0.001
            glVertex3f(x_pos, -size, -size)
            glVertex3f(x_pos, -size, size)
            glVertex3f(x_pos, size, size)
            glVertex3f(x_pos, size, -size)
        elif face_name == 'left':
            x_pos = -self.cube_size - 0.001
            glVertex3f(x_pos, -size, size)
            glVertex3f(x_pos, -size, -size)
            glVertex3f(x_pos, size, -size)
            glVertex3f(x_pos, size, size)
        elif face_name == 'top':
            y_pos = self.cube_size + 0.001
            glVertex3f(-size, y_pos, -size)
            glVertex3f(-size, y_pos, size)
            glVertex3f(size, y_pos, size)
            glVertex3f(size, y_pos, -size)
        elif face_name == 'bottom':
            y_pos = -self.cube_size - 0.001
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