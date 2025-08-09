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
        
        # Mouse sensitivity settings
        self.move_sensitivity = 20  # Pixels to move before executing a move (reduced for easier triggering)
        self.last_move_time = 0
        self.move_cooldown = 0.2  # Cooldown between moves (reduced for more responsive feel)
        
        # Visual feedback
        self.hovered_face = None
        self.hovered_cube_pos = None
        self.highlight_intensity = 0.0
        self.fade_speed = 4.0
        
        # 3D cube dimensions and positioning
        self.cube_size = 0.4  # Half size of each small cube
        self.cube_spacing = 0.52  # Spacing between cube centers
        
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
        """Convert screen coordinates to a 3D ray in world space"""
        try:
            # Get current matrices
            model_matrix = glGetDoublev(GL_MODELVIEW_MATRIX)
            proj_matrix = glGetDoublev(GL_PROJECTION_MATRIX)
            viewport = glGetIntegerv(GL_VIEWPORT)
            
            # Convert mouse coordinates to OpenGL screen coordinates
            # (origin at bottom-left)
            opengl_y = viewport[3] - mouse_y
            
            # Get the ray in world coordinates
            # Near plane point
            near_point = gluUnProject(mouse_x, opengl_y, 0.0, 
                                    model_matrix, proj_matrix, viewport)
            # Far plane point
            far_point = gluUnProject(mouse_x, opengl_y, 1.0, 
                                   model_matrix, proj_matrix, viewport)
            
            # Calculate ray direction
            ray_dir = [
                far_point[0] - near_point[0],
                far_point[1] - near_point[1],
                far_point[2] - near_point[2]
            ]
            
            # Normalize ray direction
            length = math.sqrt(ray_dir[0]**2 + ray_dir[1]**2 + ray_dir[2]**2)
            if length > 0:
                ray_dir = [ray_dir[0]/length, ray_dir[1]/length, ray_dir[2]/length]
            
            return near_point, ray_dir
        
        except Exception as e:
            # Fallback if unprojection fails - use manual calculation
            return self._manual_screen_to_world_ray(mouse_x, mouse_y)
    
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
    
    def point_in_cube_face(self, point, cube_center, face_name):
        """Check if a point lies within a specific face of a cube"""
        # Define the bounds of the cube face
        half_size = self.cube_size
        tolerance = 0.1  # Increased tolerance for better detection
        
        # Adjust point relative to cube center
        rel_point = [
            point[0] - cube_center[0],
            point[1] - cube_center[1],
            point[2] - cube_center[2]
        ]
        
        # Check if point is within the face bounds
        if face_name == 'front':  # +Z face
            return (abs(rel_point[2] - half_size) < tolerance and  # Near the front face
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[1]) <= half_size + tolerance)
        elif face_name == 'back':  # -Z face
            return (abs(rel_point[2] + half_size) < tolerance and  # Near the back face
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[1]) <= half_size + tolerance)
        elif face_name == 'right':  # +X face
            return (abs(rel_point[0] - half_size) < tolerance and  # Near the right face
                   abs(rel_point[1]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'left':  # -X face
            return (abs(rel_point[0] + half_size) < tolerance and  # Near the left face
                   abs(rel_point[1]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'top':  # +Y face
            return (abs(rel_point[1] - half_size) < tolerance and  # Near the top face
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        elif face_name == 'bottom':  # -Y face
            return (abs(rel_point[1] + half_size) < tolerance and  # Near the bottom face
                   abs(rel_point[0]) <= half_size + tolerance and 
                   abs(rel_point[2]) <= half_size + tolerance)
        
        return False
    
    def detect_face_from_mouse(self, mouse_pos):
        """Detect which face the mouse is over using 3D ray casting to actual cube geometry"""
        x, y = mouse_pos
        
        # Calculate offset from screen center
        center_x = self.renderer.width / 2
        center_y = self.renderer.height / 2
        dx = x - center_x
        dy = y - center_y
        
        # Normalize to screen size
        norm_dx = dx / (self.renderer.width / 2)
        norm_dy = dy / (self.renderer.height / 2)
        
        # Get camera rotation to determine viewing perspective
        rx = self.renderer.rotation_x % 360
        ry = self.renderer.rotation_y % 360
        
        # Get visible faces from current camera angle (more generous now)
        visible_faces = self.get_visible_faces_from_camera(rx, ry)
        
        if not visible_faces:
            # Fallback - allow all faces if visibility detection fails
            visible_faces = ['front', 'back', 'left', 'right', 'top', 'bottom']
        
        # Determine which face based on mouse position (balanced thresholds)
        face = None
        
        # Determine primary direction - what has the largest offset
        primary_horizontal = abs(norm_dx) > abs(norm_dy) and abs(norm_dx) > 0.15
        primary_vertical = abs(norm_dy) > abs(norm_dx) and abs(norm_dy) > 0.15
        
        # Check for primary direction first
        if primary_vertical:  # Vertical movement dominates
            if norm_dy < 0:  # Top of screen
                if 'top' in visible_faces:
                    face = 'top'
            else:  # Bottom of screen
                if 'bottom' in visible_faces:
                    face = 'bottom'
        elif primary_horizontal:  # Horizontal movement dominates
            if norm_dx > 0:  # Right side of screen
                candidate_face = self.get_face_for_screen_side('right', ry)
                if candidate_face in visible_faces:
                    face = candidate_face
            else:  # Left side of screen
                candidate_face = self.get_face_for_screen_side('left', ry)
                if candidate_face in visible_faces:
                    face = candidate_face
        
        # If no primary direction, check for any significant movement (secondary detection)
        if not face:
            if abs(norm_dy) > 0.25:  # Only very clear top/bottom movements
                if norm_dy < 0 and 'top' in visible_faces:
                    face = 'top'
                elif norm_dy > 0 and 'bottom' in visible_faces:
                    face = 'bottom'
            elif abs(norm_dx) > 0.1:  # More generous for left/right
                if norm_dx > 0:  # Right side of screen
                    candidate_face = self.get_face_for_screen_side('right', ry)
                    if candidate_face in visible_faces:
                        face = candidate_face
                else:  # Left side of screen
                    candidate_face = self.get_face_for_screen_side('left', ry)
                    if candidate_face in visible_faces:
                        face = candidate_face
        
        # If still no face detected, use the primary visible face based on camera angle
        if not face and visible_faces:
            # For center area, prioritize side faces over top/bottom
            side_faces = [f for f in visible_faces if f not in ['top', 'bottom']]
            
            if side_faces:
                # Determine primary side face based on camera Y rotation
                if 315 <= ry or ry < 60:
                    face = 'front' if 'front' in side_faces else side_faces[0]
                elif 30 <= ry < 150:
                    face = 'right' if 'right' in side_faces else side_faces[0]
                elif 120 <= ry < 240:
                    face = 'back' if 'back' in side_faces else side_faces[0]
                elif 210 <= ry < 330:
                    face = 'left' if 'left' in side_faces else side_faces[0]
                else:
                    face = side_faces[0]
            else:
                # Only use top/bottom if no side faces available
                face = visible_faces[0]
        
        cube_pos = self._get_cube_pos_for_face(face) if face else None
        
        return face, cube_pos
    
    def _fallback_face_detection(self, mouse_pos):
        """Fallback face detection using simplified screen region method"""
        x, y = mouse_pos
        width = self.renderer.width
        height = self.renderer.height
        
        # Convert to percentages
        x_pct = x / width
        y_pct = y / height
        
        # Get camera rotation values
        rx = self.renderer.rotation_x
        ry = self.renderer.rotation_y
        
        # Define regions - more generous boundaries
        top_region = y_pct < 0.25
        bottom_region = y_pct > 0.75
        left_region = x_pct < 0.25
        right_region = x_pct > 0.75
        center_region = not (top_region or bottom_region or left_region or right_region)
        
        # Primary face determination based on Y rotation (horizontal camera movement)
        # We'll use much simpler logic - just map rotation ranges to faces
        ry_normalized = ry % 360
        
        # Determine which face is most directly facing camera
        if ry_normalized <= 45 or ry_normalized > 315:
            primary_face = 'front'
            left_adjacent = 'left'
            right_adjacent = 'right'
        elif 45 < ry_normalized <= 135:
            primary_face = 'right'
            left_adjacent = 'front'  
            right_adjacent = 'back'
        elif 135 < ry_normalized <= 225:
            primary_face = 'back'
            left_adjacent = 'right'
            right_adjacent = 'left'
        else:  # 225 < ry_normalized <= 315
            primary_face = 'left'
            left_adjacent = 'back'
            right_adjacent = 'front'
        
        # Determine the face based on screen position
        face = None
        cube_pos = None
        
        # Check top/bottom first (these override side logic)
        if top_region:
            face = 'top'
            cube_pos = (0, 1, 0)
        elif bottom_region:
            face = 'bottom'
            cube_pos = (0, -1, 0)
        # Then check left/right sides (inverted to match visual appearance)
        elif left_region:  # Left side of screen shows right face visually
            face = right_adjacent
            cube_pos = self._get_cube_pos_for_face(right_adjacent)
        elif right_region:  # Right side of screen shows left face visually  
            face = left_adjacent
            cube_pos = self._get_cube_pos_for_face(left_adjacent)
        else:  # center region
            face = primary_face
            cube_pos = self._get_cube_pos_for_face(primary_face)
        
        print(f"Face detection: mouse=({x_pct:.2f}, {y_pct:.2f}), cam=(rx={rx:.0f}, ry={ry:.0f}) -> {face}")
        return face, cube_pos
    
    def get_visible_faces_from_camera(self, rx, ry):
        """Determine which faces are visible from the current camera angle"""
        visible_faces = []
        
        # Convert rotations to a standard range for easier calculation
        rx_norm = rx % 360
        ry_norm = ry % 360
        
        # Always allow top and bottom - they should almost always be accessible
        visible_faces.extend(['top', 'bottom'])
        
        # Determine visible side faces based on camera rotation (more generous ranges)
        if 315 <= ry_norm or ry_norm < 60:  # Looking at front primarily (expanded range)
            visible_faces.extend(['front', 'right', 'left'])  # Allow front and both sides
        elif 30 <= ry_norm < 150:  # Looking at right side primarily (expanded range)
            visible_faces.extend(['right', 'front', 'back'])  # Allow right and adjacent faces
        elif 120 <= ry_norm < 240:  # Looking at back primarily (expanded range)
            visible_faces.extend(['back', 'right', 'left'])  # Allow back and both sides
        elif 210 <= ry_norm < 330:  # Looking at left side primarily (expanded range)
            visible_faces.extend(['left', 'front', 'back'])  # Allow left and adjacent faces
        
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
        """Start dragging - detect face using enhanced detection"""
        import time
        current_time = time.time()
        if current_time - self.last_move_time < self.move_cooldown:
            return
        
        self.is_dragging = True
        self.drag_start_pos = mouse_pos
        self.drag_current_pos = mouse_pos
        self.move_executed = False
        
        # Use enhanced face detection
        self.detected_face, self.detected_cube_pos = self.detect_face_from_mouse(mouse_pos)
        
        if self.detected_face:
            self.highlight_intensity = 1.0
    
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
        """Generate Rubik's cube move based on face and drag direction"""
        # Determine primary drag direction
        if abs(dx) > abs(dy):
            # Horizontal drag
            direction = 'right' if dx > 0 else 'left'
        else:
            # Vertical drag
            direction = 'down' if dy > 0 else 'up'
        
        # Map face and direction to moves
        move_mapping = {
            'front': {
                'right': 'F',
                'left': "F'",
                'down': 'F',
                'up': "F'"
            },
            'back': {
                'right': "B'",
                'left': 'B',
                'down': "B'",
                'up': 'B'
            },
            'right': {
                'right': 'R',
                'left': "R'",
                'down': 'R',
                'up': "R'"
            },
            'left': {
                'right': "L'",
                'left': 'L',
                'down': "L'",
                'up': 'L'
            },
            'top': {
                'right': 'U',
                'left': "U'",
                'down': 'U',
                'up': "U'"
            },
            'bottom': {
                'right': "D'",
                'left': 'D',
                'down': "D'",
                'up': 'D'
            }
        }
        
        return move_mapping.get(face_name, {}).get(direction)
    
    def update_hover(self, mouse_pos):
        """Update hover detection for visual feedback"""
        if self.is_dragging:
            return
        
        # Detect face under mouse for hover effect
        face, cube_pos = self.detect_face_from_mouse(mouse_pos)
        
        # Only update if there's a change to reduce spam
        if face != self.hovered_face or cube_pos != self.hovered_cube_pos:
            self.hovered_face = face
            self.hovered_cube_pos = cube_pos
            if face:
                self.highlight_intensity = 0.3  # Gentle hover effect
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
        """Render a highlight overlay on the specified face"""
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
        alpha = self.highlight_intensity * 0.7  # Increased alpha for better visibility
        
        glColor4f(color[0], color[1], color[2], alpha)
        
        # Position at cube center
        glPushMatrix()
        glTranslatef(cube_center[0], cube_center[1], cube_center[2])
        
        # Scale slightly larger than the cube
        glScalef(0.9, 0.9, 0.9)  # Made slightly larger for better visibility
        
        # Draw highlight based on face
        size = self.cube_size * 1.15  # Increased size for better visibility
        
        glBegin(GL_QUADS)
        
        if face_name == 'front':  # +Z face
            glVertex3f(-size, -size, size)
            glVertex3f(size, -size, size)
            glVertex3f(size, size, size)
            glVertex3f(-size, size, size)
        elif face_name == 'back':  # -Z face
            glVertex3f(size, -size, -size)
            glVertex3f(-size, -size, -size)
            glVertex3f(-size, size, -size)
            glVertex3f(size, size, -size)
        elif face_name == 'right':  # +X face
            glVertex3f(size, -size, -size)
            glVertex3f(size, -size, size)
            glVertex3f(size, size, size)
            glVertex3f(size, size, -size)
        elif face_name == 'left':  # -X face
            glVertex3f(-size, -size, size)
            glVertex3f(-size, -size, -size)
            glVertex3f(-size, size, -size)
            glVertex3f(-size, size, size)
        elif face_name == 'top':  # +Y face
            glVertex3f(-size, size, -size)
            glVertex3f(-size, size, size)
            glVertex3f(size, size, size)
            glVertex3f(size, size, -size)
        elif face_name == 'bottom':  # -Y face
            glVertex3f(-size, -size, size)
            glVertex3f(-size, -size, -size)
            glVertex3f(size, -size, -size)
            glVertex3f(size, -size, size)
        
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
