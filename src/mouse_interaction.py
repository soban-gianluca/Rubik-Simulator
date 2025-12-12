import math
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
import time

class MouseInteraction:
    
    def __init__(self, renderer):
        self.renderer = renderer
        self.game = None  # Reference to game instance for checking move availability
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_face = None
        self.detected_zone = None
        self.detected_grid_pos = None  # Store the actual grid position (row, col) on the face
        self.move_executed = False
        self.last_move_time = 0
        
        # Hover detection
        self.hovered_face = None
        self.hovered_zone = None
        
        # Visual feedback
        self.highlight_intensity = 0.0
        self.show_grid_overlay = True
        
        # Movement settings
        self.move_sensitivity = 15  # pixels
        self.cube_spacing = 1.0
        
        # Calculate cube_half_size from renderer settings
        self._update_cube_half_size()
        
        # Define the 3x3 dual-mode zones - each zone can do both horizontal and vertical moves
        self.zone_types = {
            'top_left': 'dual', 'top_center': 'dual', 'top_right': 'dual',
            'middle_left': 'dual', 'middle_center': 'dual', 'middle_right': 'dual',
            'bottom_left': 'dual', 'bottom_center': 'dual', 'bottom_right': 'dual'
        }
        
        # Unified colors for dual-mode zones (yellow-ish)
        self.zone_colors = {
            'top_left': (1.0, 0.9, 0.3, 0.4), 'top_center': (1.0, 0.9, 0.3, 0.4), 'top_right': (1.0, 0.9, 0.3, 0.4),
            'middle_left': (1.0, 0.9, 0.3, 0.4), 'middle_center': (1.0, 0.9, 0.3, 0.4), 'middle_right': (1.0, 0.9, 0.4),
            'bottom_left': (1.0, 0.9, 0.3, 0.4), 'bottom_center': (1.0, 0.9, 0.3, 0.4), 'bottom_right': (1.0, 0.9, 0.3, 0.4)
        }
        
        # Cube face definitions for 3D ray casting
        # Calculate the actual half-size based on renderer settings:
        # - cube_spacing = 0.52
        # - scale_factor = 0.85
        # - small cube scale = 0.8
        # - positions at -1, 0, 1
        # Outer edge = 1 * 0.52 * 0.85 + (0.8 * small_cube_half_size)
        # The OBJ cube appears to be roughly 0.5 units in half-size
        # So: 0.442 + 0.8 * 0.25 ≈ 0.642
        # But looking at the visual, let's use a value that matches the actual rendered cube
        self.cube_half_size = 0.66  # Corrected half-size to match actual cube dimensions
    
    def _update_cube_half_size(self):
        """Calculate the cube half size from renderer settings"""
        if self.renderer:
            # Get values from renderer
            cube_spacing = getattr(self.renderer, 'cube_spacing', 0.52)
            scale_factor = 0.85  # This is hardcoded in renderer's initialize_cubes
            small_cube_scale = 0.8  # This is hardcoded in render_cube
            
            # The outer small cube center is at position 1 * cube_spacing * scale_factor
            outer_pos = 1.0 * cube_spacing * scale_factor
            
            # Add the half-size of the small cube (scaled)
            # The OBJ cube model is approximately 0.5 units in half-size
            small_cube_half = 0.25 * small_cube_scale
            
            self.cube_half_size = outer_pos + small_cube_half
        else:
            self.cube_half_size = 0.66  # Fallback value
        
    def _get_ray_from_screen(self, mouse_pos):
        """Convert screen coordinates to a 3D ray in world space using camera parameters"""
        mouse_x, mouse_y = mouse_pos
        
        # Get screen dimensions and camera parameters from renderer
        width = self.renderer.width
        height = self.renderer.height
        fov = getattr(self.renderer, 'fov', 45)  # Default FOV
        camera_distance = 4.0  # Camera is at z=-4 looking at origin
        
        # Get camera rotation from renderer (in degrees)
        rot_x = math.radians(self.renderer.rotation_x)
        rot_y = math.radians(self.renderer.rotation_y)
        
        # Convert screen coordinates to normalized device coordinates (-1 to 1)
        ndc_x = (2.0 * mouse_x / width) - 1.0
        ndc_y = 1.0 - (2.0 * mouse_y / height)  # Flip Y
        
        # Calculate ray direction in camera space
        aspect = width / height
        fov_rad = math.radians(fov)
        tan_fov = math.tan(fov_rad / 2.0)
        
        # Ray direction in camera space (camera looks down -Z)
        ray_cam_x = ndc_x * aspect * tan_fov
        ray_cam_y = ndc_y * tan_fov
        ray_cam_z = -1.0
        
        # Normalize
        ray_cam = np.array([ray_cam_x, ray_cam_y, ray_cam_z])
        ray_cam = ray_cam / np.linalg.norm(ray_cam)
        
        # Camera position in camera space (before any rotation)
        cam_pos_cam = np.array([0, 0, camera_distance])
        
        # The renderer applies rotations as:
        # glRotatef(rotation_x, 1, 0, 0)  - rotate around X axis
        # glRotatef(rotation_y, 0, 1, 0)  - rotate around Y axis
        # This rotates the WORLD, so to get ray in world space we apply INVERSE rotations
        # in REVERSE order: first -rot_y around Y, then -rot_x around X
        
        cos_x, sin_x = math.cos(rot_x), math.sin(rot_x)
        cos_y, sin_y = math.cos(rot_y), math.sin(rot_y)
        
        # Inverse rotation matrix around Y axis (rotate by -rot_y)
        inv_rot_y = np.array([
            [cos_y, 0, -sin_y],
            [0, 1, 0],
            [sin_y, 0, cos_y]
        ])
        
        # Inverse rotation matrix around X axis (rotate by -rot_x)
        inv_rot_x = np.array([
            [1, 0, 0],
            [0, cos_x, sin_x],
            [0, -sin_x, cos_x]
        ])
        
        # Apply inverse rotations in reverse order: first Y inverse, then X inverse
        ray_dir = inv_rot_y @ (inv_rot_x @ ray_cam)
        ray_origin = inv_rot_y @ (inv_rot_x @ cam_pos_cam)
        
        return ray_origin, ray_dir
        
        return ray_origin, ray_dir
    
    def _ray_plane_intersection(self, ray_origin, ray_dir, plane_point, plane_normal):
        """Calculate intersection of ray with a plane. Returns (t, intersection_point) or (None, None)"""
        denom = np.dot(ray_dir, plane_normal)
        if abs(denom) < 1e-6:
            return None, None  # Ray is parallel to plane
        
        t = np.dot(plane_point - ray_origin, plane_normal) / denom
        if t < 0:
            return None, None  # Intersection is behind the ray origin
        
        intersection = ray_origin + t * ray_dir
        return t, intersection
    
    def _detect_face_with_raycast(self, mouse_pos):
        """
        Detect which cube face is clicked using 3D ray casting.
        Returns (face_name, grid_row, grid_col) or (None, None, None)
        """
        ray_origin, ray_dir = self._get_ray_from_screen(mouse_pos)
        if ray_origin is None:
            return None, None, None
        
        # Define the 6 faces of the cube
        # Each face: (name, plane_point, plane_normal, u_axis, v_axis)
        # u_axis and v_axis define the local coordinate system on the face for grid detection
        h = self.cube_half_size
        
        faces = [
            ('front',  np.array([0, 0, h]),  np.array([0, 0, 1]),  np.array([1, 0, 0]),  np.array([0, 1, 0])),
            ('back',   np.array([0, 0, -h]), np.array([0, 0, -1]), np.array([-1, 0, 0]), np.array([0, 1, 0])),
            ('right',  np.array([h, 0, 0]),  np.array([1, 0, 0]),  np.array([0, 0, -1]), np.array([0, 1, 0])),
            ('left',   np.array([-h, 0, 0]), np.array([-1, 0, 0]), np.array([0, 0, 1]),  np.array([0, 1, 0])),
            ('top',    np.array([0, h, 0]),  np.array([0, 1, 0]),  np.array([1, 0, 0]),  np.array([0, 0, -1])),
            ('bottom', np.array([0, -h, 0]), np.array([0, -1, 0]), np.array([1, 0, 0]),  np.array([0, 0, 1])),
        ]
        
        closest_face = None
        closest_t = float('inf')
        closest_grid = (None, None)
        
        for face_name, plane_point, plane_normal, u_axis, v_axis in faces:
            # Only consider faces that are facing the camera (backface culling)
            # A face is visible if the ray direction has a negative dot product with the face normal
            if np.dot(ray_dir, plane_normal) >= 0:
                continue  # Face is facing away from camera
            
            t, intersection = self._ray_plane_intersection(ray_origin, ray_dir, plane_point, plane_normal)
            
            if t is None or t >= closest_t:
                continue
            
            # Check if intersection is within the face bounds
            # Convert intersection to local face coordinates
            local_pos = intersection - plane_point
            u = np.dot(local_pos, u_axis)
            v = np.dot(local_pos, v_axis)
            
            # Check bounds (face is 2*h x 2*h)
            if abs(u) <= h and abs(v) <= h:
                closest_face = face_name
                closest_t = t
                
                # Convert to grid coordinates (0, 1, 2 for each axis)
                # u and v are in range [-h, h], map to [0, 3]
                grid_u = int((u + h) / (2 * h) * 3)
                grid_v = int((v + h) / (2 * h) * 3)
                
                # Clamp to valid range
                grid_u = max(0, min(2, grid_u))
                grid_v = max(0, min(2, grid_v))
                
                # Convert to row, col (v is vertical, u is horizontal)
                # Invert v because screen Y increases downward but 3D Y increases upward
                grid_row = 2 - grid_v
                grid_col = grid_u
                
                closest_grid = (grid_row, grid_col)
        
        return closest_face, closest_grid[0], closest_grid[1]
    
    def _grid_to_zone(self, row, col):
        """Convert grid position (row, col) to zone name"""
        if row is None or col is None:
            return None
        
        zone_map = [
            ['top_left', 'top_center', 'top_right'],
            ['middle_left', 'middle_center', 'middle_right'],
            ['bottom_left', 'bottom_center', 'bottom_right']
        ]
        
        if 0 <= row <= 2 and 0 <= col <= 2:
            return zone_map[row][col]
        return None
    
    def _detect_face_from_screen_position(self, mouse_pos):
        """Detect which face is being clicked using 3D ray casting"""
        face, row, col = self._detect_face_with_raycast(mouse_pos)
        return face

    def _detect_zone_on_face(self, mouse_pos, face):
        """Detect which 3x3 grid position using 3D ray casting"""
        detected_face, row, col = self._detect_face_with_raycast(mouse_pos)
        
        if detected_face != face or row is None or col is None:
            return None
        
        # Store grid position for move generation
        self.detected_grid_pos = (row, col)
        
        return self._grid_to_zone(row, col)

    def start_drag(self, mouse_pos):
        """Start drag operation with 3D ray casting face and zone detection"""
        # Use 3D ray casting to detect face and grid position
        face, row, col = self._detect_face_with_raycast(mouse_pos)
        if not face:
            return
        
        zone = self._grid_to_zone(row, col)
        if not zone:
            return
        
        # Initialize drag
        self.is_dragging = True
        self.drag_start_pos = mouse_pos
        self.drag_current_pos = mouse_pos
        self.detected_face = face
        self.detected_zone = zone
        self.detected_grid_pos = (row, col)
        self.move_executed = False

    def update_drag(self, mouse_pos):
        """Update drag and detect moves - ENHANCED with dual-mode detection"""
        if not self.is_dragging or self.move_executed:
            return None
        
        # Check if moves are allowed in the current game state
        if self.game and not self.game.can_make_move():
            return None
        
        self.drag_current_pos = mouse_pos
        
        # Calculate drag vector
        dx = mouse_pos[0] - self.drag_start_pos[0]
        dy = mouse_pos[1] - self.drag_start_pos[1]
        
        # Check if drag is large enough
        drag_distance = math.sqrt(dx*dx + dy*dy)
        if drag_distance < self.move_sensitivity:
            return None
        
        # Prevent multiple moves in one drag
        current_time = time.time()
        if current_time - self.last_move_time < 0.3:  # 300ms cooldown
            return None
        
        # Generate move
        if self.detected_face and self.detected_zone:
            move = self._get_revolutionary_move(self.detected_face, self.detected_zone, dx, dy)
            if move:
                self.move_executed = True
                self.last_move_time = current_time
                return move
        
        return None

    def _get_revolutionary_move(self, face, zone, dx, dy):
        """Generate moves based on face, grid position, and drag direction using 3D-aware logic"""
        # Get the grid position (row, col) on the face
        if not hasattr(self, 'detected_grid_pos') or self.detected_grid_pos is None:
            return None
        
        row, col = self.detected_grid_pos
        
        # Calculate drag angle in degrees (0° = right, 90° = down, 180° = left, 270° = up)
        drag_angle = math.degrees(math.atan2(dy, dx)) % 360
        
        # Determine primary drag direction on screen
        if drag_angle < 45 or drag_angle >= 315:
            screen_dir = 'right'
        elif 45 <= drag_angle < 135:
            screen_dir = 'down'
        elif 135 <= drag_angle < 225:
            screen_dir = 'left'
        else:  # 225 <= drag_angle < 315
            screen_dir = 'up'
        
        # Determine if this is a horizontal or vertical drag
        is_horizontal = screen_dir in ['left', 'right']
        
        # For top/bottom faces, we need to transform the screen direction based on camera Y rotation
        if face in ['top', 'bottom']:
            screen_dir, is_horizontal, row, col = self._transform_top_bottom_input(
                face, screen_dir, is_horizontal, row, col
            )
        
        # Generate move based on face and drag direction
        # Each face has its own mapping of drag directions to moves
        return self._get_move_for_face(face, row, col, screen_dir, is_horizontal)
    
    def _transform_top_bottom_input(self, face, screen_dir, is_horizontal, row, col):
        """
        Transform screen drag direction into world-relative direction for top/bottom faces.
        
        The grid row/col are already in world coordinates (from ray casting) - they don't need transformation.
        We only need to transform the SCREEN drag direction to match the world coordinate frame
        based on camera Y rotation.
        
        For TOP face (u_axis = [1,0,0], v_axis = [0,0,-1]):
        - Grid col increases with world +X
        - Grid row increases with world +Z (towards back, since v_axis is [0,0,-1] and we invert)
        - At rot_y=0: screen right = +X, screen down = -Z (towards front)
        
        For BOTTOM face (u_axis = [1,0,0], v_axis = [0,0,1]):
        - Grid col increases with world +X  
        - Grid row increases with world -Z (towards front, since v_axis is [0,0,1] and we invert)
        - At rot_y=0: screen right = +X, screen down = +Z (towards back)
        
        The key difference: on bottom face, screen "down" maps to +Z (back), not -Z (front) like on top.
        """
        # Get camera Y rotation and normalize to 0-360
        rot_y = self.renderer.rotation_y % 360
        if rot_y < 0:
            rot_y += 360
        
        # Determine which quadrant we're in
        if rot_y < 45 or rot_y >= 315:
            quadrant = 0  # Front-facing (default orientation)
        elif 45 <= rot_y < 135:
            quadrant = 1  # Left-facing (camera rotated ~90° right)
        elif 135 <= rot_y < 225:
            quadrant = 2  # Back-facing (camera rotated ~180°)
        else:  # 225 <= rot_y < 315
            quadrant = 3  # Right-facing (camera rotated ~270° right)
        
        # Grid coordinates are in world space - don't transform them
        # Only transform the screen direction to world direction
        
        if face == 'top':
            # TOP FACE transformations
            if quadrant == 0:
                # No transformation needed - screen coords match expected world coords
                return screen_dir, is_horizontal, row, col
            
            elif quadrant == 1:
                # Camera looking at left side (rot_y ~90°)
                # Screen right -> world -Z, which in our system should act like "down" (towards front row)
                # Screen down -> world -X, which should act like "left"
                dir_map = {'right': 'down', 'down': 'left', 'left': 'up', 'up': 'right'}
                new_dir = dir_map[screen_dir]
                new_is_horizontal = not is_horizontal
                return new_dir, new_is_horizontal, row, col
            
            elif quadrant == 2:
                # Camera looking at back (rot_y ~180°)
                # Screen right -> world -X, should act like "left"
                # Screen down -> world +Z, should act like "up" (towards back row)
                dir_map = {'right': 'left', 'down': 'up', 'left': 'right', 'up': 'down'}
                new_dir = dir_map[screen_dir]
                return new_dir, is_horizontal, row, col
            
            else:  # quadrant == 3
                # Camera looking at right side (rot_y ~270°)
                # Screen right -> world +Z, should act like "up"
                # Screen down -> world +X, should act like "right"
                dir_map = {'right': 'up', 'down': 'right', 'left': 'down', 'up': 'left'}
                new_dir = dir_map[screen_dir]
                new_is_horizontal = not is_horizontal
                return new_dir, new_is_horizontal, row, col
        
        else:  # face == 'bottom'
            # BOTTOM FACE transformations
            # The bottom face has v_axis = [0,0,1] instead of [0,0,-1]
            # At quadrants 0 and 2, bottom face behaves same as top face
            # At quadrants 1 and 3, we need to invert both row and column directions
            
            if quadrant == 0:
                # No transformation needed - same as top face
                return screen_dir, is_horizontal, row, col
            
            elif quadrant == 1:
                # Camera looking at left side (rot_y ~90°)
                # For bottom face: invert both horizontal (right/left) and vertical (up/down) outputs
                # compared to top face mapping {'right': 'down', 'down': 'left', 'left': 'up', 'up': 'right'}
                dir_map = {'right': 'up', 'down': 'right', 'left': 'down', 'up': 'left'}
                new_dir = dir_map[screen_dir]
                new_is_horizontal = not is_horizontal
                return new_dir, new_is_horizontal, row, col
            
            elif quadrant == 2:
                # Camera looking at back (rot_y ~180°)
                # Same transformation as top face
                dir_map = {'right': 'left', 'down': 'up', 'left': 'right', 'up': 'down'}
                new_dir = dir_map[screen_dir]
                return new_dir, is_horizontal, row, col
            
            else:  # quadrant == 3
                # Camera looking at right side (rot_y ~270°)
                # For bottom face: invert both horizontal and vertical outputs
                # compared to top face mapping {'right': 'up', 'down': 'right', 'left': 'down', 'up': 'left'}
                dir_map = {'right': 'down', 'down': 'left', 'left': 'up', 'up': 'right'}
                new_dir = dir_map[screen_dir]
                new_is_horizontal = not is_horizontal
                return new_dir, new_is_horizontal, row, col
    
    def _get_move_for_face(self, face, row, col, screen_dir, is_horizontal):
        """
        Get the correct move based on which face was clicked, position on the face, and drag direction.
        This handles all 6 faces of the cube properly.
        """
        if face == 'front':
            return self._get_front_face_move(row, col, screen_dir, is_horizontal)
        elif face == 'back':
            return self._get_back_face_move(row, col, screen_dir, is_horizontal)
        elif face == 'right':
            return self._get_right_face_move(row, col, screen_dir, is_horizontal)
        elif face == 'left':
            return self._get_left_face_move(row, col, screen_dir, is_horizontal)
        elif face == 'top':
            return self._get_top_face_move(row, col, screen_dir, is_horizontal)
        elif face == 'bottom':
            return self._get_bottom_face_move(row, col, screen_dir, is_horizontal)
        
        return None
    
    def _get_front_face_move(self, row, col, screen_dir, is_horizontal):
        """Get move for front face interaction - this is the reference face"""
        if is_horizontal:
            # Horizontal drag on front face -> move U, E, or D layers
            if row == 0:
                return "U'" if screen_dir == 'right' else 'U'
            elif row == 1:
                return "E'" if screen_dir == 'right' else 'E'
            else:  # row == 2
                return 'D' if screen_dir == 'right' else "D'"
        else:
            # Vertical drag on front face -> move L, M, or R layers
            if col == 0:
                return 'L' if screen_dir == 'down' else "L'"
            elif col == 1:
                return "M'" if screen_dir == 'down' else 'M'
            else:  # col == 2
                return "R'" if screen_dir == 'down' else 'R'
    
    def _get_back_face_move(self, row, col, screen_dir, is_horizontal):
        """Get move for back face interaction - opposite to front"""
        if is_horizontal:
            # Horizontal drag on back face -> U, E, D layers (same pattern as front, visually inverted)
            if row == 0:
                return "U'" if screen_dir == 'right' else 'U'
            elif row == 1:
                return "E'" if screen_dir == 'right' else 'E'
            else:  # row == 2
                return 'D' if screen_dir == 'right' else "D'"
        else:
            # Vertical drag on back face -> columns are mirrored (col 0 on back = R side of cube)
            if col == 0:
                return 'R' if screen_dir == 'down' else "R'"
            elif col == 1:
                return 'M' if screen_dir == 'down' else "M'"
            else:  # col == 2
                return "L'" if screen_dir == 'down' else 'L'
    
    def _get_right_face_move(self, row, col, screen_dir, is_horizontal):
        """Get move for right face interaction"""
        if is_horizontal:
            # Horizontal drag on right face -> U, E, D layers (same as front for horizontal)
            if row == 0:
                return "U'" if screen_dir == 'right' else 'U'
            elif row == 1:
                return "E'" if screen_dir == 'right' else 'E'
            else:  # row == 2
                return 'D' if screen_dir == 'right' else "D'"
        else:
            # Vertical drag on right face -> F, S, B layers
            # col 0 on right face = front side, col 2 = back side
            if col == 0:
                return 'F' if screen_dir == 'down' else "F'"
            elif col == 1:
                return "S'" if screen_dir == 'down' else 'S'
            else:  # col == 2
                return "B'" if screen_dir == 'down' else 'B'
    
    def _get_left_face_move(self, row, col, screen_dir, is_horizontal):
        """Get move for left face interaction - opposite to right"""
        if is_horizontal:
            # Horizontal drag on left face -> U, E, D layers (same pattern as front)
            if row == 0:
                return "U'" if screen_dir == 'right' else 'U'
            elif row == 1:
                return "E'" if screen_dir == 'right' else 'E'
            else:  # row == 2
                return 'D' if screen_dir == 'right' else "D'"
        else:
            # Vertical drag on left face -> B, S, F layers
            # col 0 on left face = back side, col 2 = front side
            if col == 0:
                return 'B' if screen_dir == 'down' else "B'"
            elif col == 1:
                return 'S' if screen_dir == 'down' else "S'"
            else:  # col == 2
                return "F'" if screen_dir == 'down' else 'F'
    
    def _get_top_face_move(self, row, col, screen_dir, is_horizontal):
        """Get move for top face interaction"""
        if is_horizontal:
            # Horizontal drag on top face -> B, S, F layers
            # row 0 = back side, row 2 = front side
            if row == 0:
                return "B'" if screen_dir == 'right' else 'B'
            elif row == 1:
                return "S'" if screen_dir == 'right' else 'S'
            else:  # row == 2
                return 'F' if screen_dir == 'right' else "F'"
        else:
            # Vertical drag on top face -> L, M, R layers
            if col == 0:
                return 'L' if screen_dir == 'down' else "L'"
            elif col == 1:
                return "M'" if screen_dir == 'down' else 'M'
            else:  # col == 2
                return "R'" if screen_dir == 'down' else 'R'
    
    def _get_bottom_face_move(self, row, col, screen_dir, is_horizontal):
        """Get move for bottom face interaction - opposite to top"""
        if is_horizontal:
            # Horizontal drag on bottom face -> F, S, B layers
            # row 0 = front side, row 2 = back side
            if row == 0:
                return "F'" if screen_dir == 'right' else 'F'
            elif row == 1:
                return 'S' if screen_dir == 'right' else "S'"
            else:  # row == 2
                return "B" if screen_dir == 'right' else "B'"
        else:
            # Vertical drag on bottom face -> L, M, R layers
            if col == 0:
                return 'L' if screen_dir == 'down' else "L'"
            elif col == 1:
                return "M'" if screen_dir == 'down' else 'M'
            else:  # col == 2
                return "R'" if screen_dir == 'down' else 'R'

    def update_hover(self, mouse_pos):
        """Update hover detection using 3D ray casting"""
        if self.is_dragging:
            return
        
        # Detect face and zone using ray casting
        face, row, col = self._detect_face_with_raycast(mouse_pos)
        zone = self._grid_to_zone(row, col) if face else None
        
        # Update hover state - only set if actually hovering on a face
        self.hovered_face = face
        self.hovered_zone = zone
        
        # Update highlight intensity
        if face and zone:
            self.highlight_intensity = min(1.0, self.highlight_intensity + 0.05)
        else:
            self.highlight_intensity = max(0.0, self.highlight_intensity - 0.05)

    def end_drag(self):
        """End drag operation"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_face = None
        self.detected_zone = None
        self.detected_grid_pos = None
        self.move_executed = False

    def get_debug_info(self):
        """Get debug info for troubleshooting"""
        return {
            'is_dragging': self.is_dragging,
            'detected_face': self.detected_face,
            'detected_zone': self.detected_zone,
            'detected_grid_pos': self.detected_grid_pos,
            'hovered_face': self.hovered_face,
            'hovered_zone': self.hovered_zone,
            'move_executed': self.move_executed,
            'highlight_intensity': self.highlight_intensity,
            'zone_type': self.zone_types.get(self.detected_zone, 'none') if self.detected_zone else 'none'
        }
    
    def reset_interaction(self):
        """Reset everything"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_face = None
        self.detected_zone = None
        self.detected_grid_pos = None
        self.move_executed = False
        self.hovered_face = None
        self.hovered_zone = None
        self.highlight_intensity = 0.0
        self.last_move_time = 0
    
    def update_renderer(self, new_renderer):
        """Update the renderer reference after resolution changes"""
        self.renderer = new_renderer
        # Recalculate cube size from new renderer
        self._update_cube_half_size()
        # Reset any ongoing interactions since the coordinate system has changed
        self.reset_interaction()
    
    def set_game_reference(self, game):
        """Set reference to game instance for checking move availability"""
        self.game = game
    
    def render_debug_faces(self):
        """
        Render the virtual detection faces as colored transparent planes for debugging.
        Call this method after rendering the cube but before glPopMatrix.
        """
        h = self.cube_half_size
        
        # Define face colors (RGBA) - distinct colors for each face
        face_colors = {
            'front':  (1.0, 0.0, 0.0, 0.3),   # Red
            'back':   (0.0, 1.0, 0.0, 0.3),   # Green
            'right':  (0.0, 0.0, 1.0, 0.3),   # Blue
            'left':   (1.0, 1.0, 0.0, 0.3),   # Yellow
            'top':    (1.0, 0.0, 1.0, 0.3),   # Magenta
            'bottom': (0.0, 1.0, 1.0, 0.3),   # Cyan
        }
        
        # Define face vertices (4 corners for each face)
        # Each face is a square of size 2*h centered on the face plane
        faces = {
            'front': [
                (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)
            ],
            'back': [
                (h, -h, -h), (-h, -h, -h), (-h, h, -h), (h, h, -h)
            ],
            'right': [
                (h, -h, h), (h, -h, -h), (h, h, -h), (h, h, h)
            ],
            'left': [
                (-h, -h, -h), (-h, -h, h), (-h, h, h), (-h, h, -h)
            ],
            'top': [
                (-h, h, h), (h, h, h), (h, h, -h), (-h, h, -h)
            ],
            'bottom': [
                (-h, -h, -h), (h, -h, -h), (h, -h, h), (-h, -h, h)
            ],
        }
        
        # Save OpenGL state
        glPushAttrib(GL_ALL_ATTRIB_BITS)
        
        # Enable blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Disable lighting so colors show properly
        glDisable(GL_LIGHTING)
        
        # Disable depth writing but keep depth testing (so faces render behind cube parts)
        glDepthMask(GL_FALSE)
        
        # Draw each face
        for face_name, vertices in faces.items():
            color = face_colors[face_name]
            
            # Highlight the currently hovered face
            if face_name == self.hovered_face:
                color = (color[0], color[1], color[2], 0.6)  # More opaque when hovered
            
            glColor4f(*color)
            
            glBegin(GL_QUADS)
            for vertex in vertices:
                glVertex3f(*vertex)
            glEnd()
            
            # Draw grid lines on each face to show the 3x3 zones
            glColor4f(1.0, 1.0, 1.0, 0.8)  # White grid lines
            glLineWidth(2.0)
            
            # Calculate grid line positions
            self._draw_grid_on_face(face_name, vertices, h)
        
        # Restore OpenGL state
        glDepthMask(GL_TRUE)
        glPopAttrib()
    
    def _draw_grid_on_face(self, face_name, vertices, h):
        """Draw 3x3 grid lines on a face"""
        # Grid divisions at -h/3, 0, h/3
        divisions = [-h/3, h/3]
        
        if face_name in ['front', 'back']:
            # Grid on XY plane
            z = h if face_name == 'front' else -h
            for div in divisions:
                # Vertical lines
                glBegin(GL_LINES)
                glVertex3f(div, -h, z)
                glVertex3f(div, h, z)
                glEnd()
                # Horizontal lines
                glBegin(GL_LINES)
                glVertex3f(-h, div, z)
                glVertex3f(h, div, z)
                glEnd()
                
        elif face_name in ['left', 'right']:
            # Grid on YZ plane
            x = h if face_name == 'right' else -h
            for div in divisions:
                # Vertical lines (along Y)
                glBegin(GL_LINES)
                glVertex3f(x, -h, div)
                glVertex3f(x, h, div)
                glEnd()
                # Horizontal lines (along Z)
                glBegin(GL_LINES)
                glVertex3f(x, div, -h)
                glVertex3f(x, div, h)
                glEnd()
                
        elif face_name in ['top', 'bottom']:
            # Grid on XZ plane
            y = h if face_name == 'top' else -h
            for div in divisions:
                # Lines along X
                glBegin(GL_LINES)
                glVertex3f(-h, y, div)
                glVertex3f(h, y, div)
                glEnd()
                # Lines along Z
                glBegin(GL_LINES)
                glVertex3f(div, y, -h)
                glVertex3f(div, y, h)
                glEnd()