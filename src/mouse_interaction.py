"""
Dual-Mode Face Interaction System for Rubik's Cube

This advanced system allows 6 different moves when looking at any face:
- 3 Horizontal moves: Top row, middle row, bottom row (moving left/right)
- 3 Vertical moves: Left column, middle column, right column (moving up/down)

Using a 3x3 grid dual-mode system where each zone can perform both horizontal
and vertical moves based on drag direction. This provides balanced access to
all movement types from any position on the face.

Features:
- 3x3 dual-mode grid overlay
- Direction-based move detection
- Visual feedback with dual-direction arrows
- Intuitive drag directions for each zone
- Camera-aware movement interpretation
- Enhanced usability and balance
"""

import math
import pygame
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
        self.move_executed = False
        self.last_move_time = 0
        
        # Hover detection
        self.hovered_face = None
        self.hovered_zone = None
        
        # Visual feedback
        self.highlight_intensity = 0.0
        self.show_grid_overlay = True
        
        # Movement settings
        self.move_sensitivity = 15  # pixels (very responsive for larger zones)
        self.cube_spacing = 1.0
        
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
        
    def _detect_face_from_screen_position(self, mouse_pos):
        """Detect which face is being looked at based on camera rotation"""
        # Get normalized camera rotation
        rx = self.renderer.rotation_x % 360
        ry = self.renderer.rotation_y % 360
        
        # Normalize to [-180, 180] range for easier calculations
        if rx > 180:
            rx -= 360
        if ry > 180:
            ry -= 360
        
        # Debug output (temporary)
        # print(f"🔍 Camera rotation: rx={rx:.1f}°, ry={ry:.1f}°")
        
        # Determine primary face based on rotation
        # Only detect the 4 main faces (front, back, left, right) for cleaner interaction
        if -50 <= ry <= 50:  # Front/back oriented
            return 'front'
        elif ry > 50 and ry <= 130:  # Left side
            return 'left'
        elif ry < -50 and ry >= -130:  # Right side
            return 'right'
        else:  # Back oriented (ry > 130 or ry < -130)
            return 'back'

    def _detect_zone_on_face(self, mouse_pos, face):
        """Detect which 3x3 grid position - ACCURATE cube-matching system"""
        mouse_x, mouse_y = mouse_pos
        
        # Get face center on screen
        center_x = self.renderer.width / 2
        center_y = self.renderer.height / 2
        
        # Calculate relative position within the face
        rel_x = mouse_x - center_x
        rel_y = mouse_y - center_y
        
        # Calculate actual projected cube size on screen based on camera distance and FOV
        camera_distance = 4.0
        cube_world_size = 3 * self.renderer.cube_spacing * 0.85  # Total size of 3x3 cube
        
        # Calculate projected size using perspective projection
        fov_rad = math.radians(self.renderer.fov)
        projected_size = (cube_world_size * self.renderer.height) / (2 * camera_distance * math.tan(fov_rad / 2))
        
        # Each small cube in the 3x3 grid
        small_cube_size = projected_size / 3
        
        # Normalize to grid coordinates [-1.5, -0.5, 0.5, 1.5] for 3x3 grid
        grid_x = rel_x / small_cube_size
        grid_y = rel_y / small_cube_size
        
        # Check if within cube bounds (with small tolerance)
        tolerance = 0.2  # Allow slight overlap between cubes
        if abs(grid_x) > 1.5 + tolerance or abs(grid_y) > 1.5 + tolerance:
            return None
        
        # Map to 3x3 grid indices
        # Convert from continuous space to discrete grid
        if grid_x < -0.5:
            col = 0  # left
        elif grid_x > 0.5:
            col = 2  # right
        else:
            col = 1  # center
            
        if grid_y < -0.5:
            row = 0  # top
        elif grid_y > 0.5:
            row = 2  # bottom
        else:
            row = 1  # middle
        
        # Map grid position to zone names
        zone_map = [
            ['top_left', 'top_center', 'top_right'],
            ['middle_left', 'middle_center', 'middle_right'],
            ['bottom_left', 'bottom_center', 'bottom_right']
        ]
        
        return zone_map[row][col]

    def start_drag(self, mouse_pos):
        """Start drag operation with enhanced face and zone detection"""
        # Detect face
        face = self._detect_face_from_screen_position(mouse_pos)
        if not face:
            return
        
        # Detect zone on face
        zone = self._detect_zone_on_face(mouse_pos, face)
        if not zone:
            return
        
        # Initialize drag
        self.is_dragging = True
        self.drag_start_pos = mouse_pos
        self.drag_current_pos = mouse_pos
        self.detected_face = face
        self.detected_zone = zone
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
        """Generate revolutionary moves based on face, zone, and drag direction - DUAL MODE system"""
        # Calculate drag distances and angles for direction detection
        drag_distance_x = abs(dx)
        drag_distance_y = abs(dy)
        total_distance = math.sqrt(dx*dx + dy*dy)
        
        # Calculate drag angle in degrees (0° = right, 90° = down, 180° = left, 270° = up)
        drag_angle = math.degrees(math.atan2(dy, dx)) % 360
        
        # Determine primary drag direction
        if drag_angle < 45 or drag_angle >= 315:
            primary_direction = 'right'
        elif 45 <= drag_angle < 135:
            primary_direction = 'down'
        elif 135 <= drag_angle < 225:
            primary_direction = 'left'
        else:  # 225 <= drag_angle < 315
            primary_direction = 'up'
        
        # Dual-mode: determine if this should be a horizontal or vertical move
        is_horizontal_move = primary_direction in ['left', 'right']
        is_vertical_move = primary_direction in ['up', 'down']
        
        # Generate move based on direction and zone position
        if is_horizontal_move:
            return self._get_horizontal_move_from_position(zone, primary_direction)
        else:
            return self._get_vertical_move_from_position(zone, primary_direction)
    
    def _get_horizontal_move_from_position(self, zone, direction):
        """Get horizontal move based on 3x3 grid position - SIMPLIFIED FACE-AWARE"""
        # Map 3x3 positions to row moves with simplified face-aware directions
        if zone in ['top_left', 'top_center', 'top_right']:
            # Top row (U moves) - simplified direction logic
            if self.detected_face in ['front']:
                return "U'" if direction == 'right' else 'U'  # Fixed: flipped for front face top row
            elif self.detected_face == 'right':
                return "U'" if direction == 'right' else 'U'  # Fixed: flipped for right face top row
            else:  # back, left - flip direction
                return "U'" if direction == 'right' else 'U'
                
        elif zone in ['middle_left', 'middle_center', 'middle_right']:
            # Middle row (E moves) - simplified direction logic
            if self.detected_face in ['front']:
                return "E'" if direction == 'right' else 'E'  # Fixed: flipped for front face middle row
            elif self.detected_face == 'right':
                return "E'" if direction == 'right' else 'E'  # Fixed: flipped for right face middle row
            else:  # back, left - flip direction
                return "E'" if direction == 'right' else 'E'
                
        else:  # bottom row
            # Bottom row (D moves) - simplified direction logic
            if self.detected_face in ['front', 'left', 'right']:
                return 'D' if direction == 'right' else "D'"
            else:  # back
                return 'D' if direction == 'right' else "D'"
    
    def _get_vertical_move_from_position(self, zone, direction):
        """Get vertical move based on 3x3 grid position - SIMPLIFIED FACE-AWARE"""
        # Map 3x3 positions to column moves with simplified face-aware directions
        if zone in ['top_left', 'middle_left', 'bottom_left']:
            # Left column - different moves depending on viewing face
            if self.detected_face == 'front':
                return 'L' if direction == 'down' else "L'"  # Fixed: flipped for front face left column
            elif self.detected_face == 'back':
                return 'R' if direction == 'down' else "R'"  # Fixed: back face left column should control R (visually reversed)
            elif self.detected_face == 'right':
                return 'F' if direction == 'down' else "F'"  # Fixed: flipped for right face left column
            else:  # left
                return 'B' if direction == 'down' else "B'"  # Left view: left = B slice (flipped)
                
        elif zone in ['top_center', 'middle_center', 'bottom_center']:
            # Middle column - different moves depending on viewing face
            if self.detected_face == 'front':
                return "M'" if direction == 'down' else 'M'  # Fixed: reverted back for front face middle column
            elif self.detected_face == 'back':
                return 'M' if direction == 'down' else "M'"  # Flipped for back view
            elif self.detected_face == 'right':
                return "S'" if direction == 'down' else 'S'  # Right view: center = S slice
            else:  # left
                return 'S' if direction == 'down' else "S'"  # Left view: center = S slice (flipped)
                
        else:  # right column
            # Right column - different moves depending on viewing face
            if self.detected_face == 'front':
                return "R'" if direction == 'down' else 'R'  # Fixed: reverted back for front face right column
            elif self.detected_face == 'back':
                return "L'" if direction == 'down' else 'L'  # Fixed: back face right column should control L' (flipped)
            elif self.detected_face == 'right':
                return "B'" if direction == 'down' else 'B'  # Fixed: flipped for right face right column
            else:  # left
                return "F'" if direction == 'down' else 'F'  # Left view: right = F slice

    def update_hover(self, mouse_pos):
        """Update hover detection for revolutionary zones"""
        if self.is_dragging:
            return
        
        # Detect face and zone
        face = self._detect_face_from_screen_position(mouse_pos)
        zone = None
        if face:
            zone = self._detect_zone_on_face(mouse_pos, face)
        
        # Update hover state
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
        self.move_executed = False

    def get_debug_info(self):
        """Get debug info for troubleshooting"""
        return {
            'is_dragging': self.is_dragging,
            'detected_face': self.detected_face,
            'detected_zone': self.detected_zone,
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
        self.move_executed = False
        self.hovered_face = None
        self.hovered_zone = None
        self.highlight_intensity = 0.0
        self.last_move_time = 0
    
    def update_renderer(self, new_renderer):
        """Update the renderer reference after resolution changes"""
        self.renderer = new_renderer
        # Reset any ongoing interactions since the coordinate system has changed
        self.reset_interaction()
    
    def set_game_reference(self, game):
        """Set reference to game instance for checking move availability"""
        self.game = game