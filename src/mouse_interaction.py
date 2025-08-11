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
            'middle_left': (1.0, 0.9, 0.3, 0.4), 'middle_center': (1.0, 0.9, 0.3, 0.4), 'middle_right': (1.0, 0.9, 0.3, 0.4),
            'bottom_left': (1.0, 0.9, 0.3, 0.4), 'bottom_center': (1.0, 0.9, 0.3, 0.4), 'bottom_right': (1.0, 0.9, 0.3, 0.4)
        }
        
        print("🚀 Dual-Mode Mouse Interaction System initialized!")
        print("   ✨ 3x3 grid with dual-mode zones")
        print("   🎯 Direction-based move detection")
        print("   📱 Enhanced visual feedback")
        
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
        
        # Determine primary face based on rotation
        # We use wider ranges for more forgiving detection
        if -45 <= ry <= 45:
            if -45 <= rx <= 45:
                return 'front'
            elif rx > 45:
                return 'bottom'
            else:  # rx < -45
                return 'top'
        elif ry > 45 and ry <= 135:
            return 'right'
        elif ry < -45 and ry >= -135:
            return 'left'
        else:  # ry > 135 or ry < -135
            if -45 <= rx <= 45:
                return 'back'
            elif rx > 45:
                return 'bottom'
            else:  # rx < -45
                return 'top'

    def _detect_zone_on_face(self, mouse_pos, face):
        """Detect which 3x3 grid position - IMPROVED dual-mode system"""
        mouse_x, mouse_y = mouse_pos
        
        # Get face center on screen
        center_x = self.renderer.width / 2
        center_y = self.renderer.height / 2
        
        # Calculate relative position within the face
        rel_x = mouse_x - center_x
        rel_y = mouse_y - center_y
        
        # Face size on screen - increased to match cube size
        face_size = 200  # pixels (increased to match actual cube size)
        
        # Normalize to [-1, 1] range
        norm_x = rel_x / (face_size / 2)
        norm_y = rel_y / (face_size / 2)
        
        # Extended boundaries for much better targeting (covers entire cube face)
        if abs(norm_x) > 2.0 or abs(norm_y) > 2.0:
            return None
        
        # Divide face into 3x3 grid with expanded boundaries to match cube size
        if norm_x < -0.15:      # Left third (expanded boundaries)
            if norm_y < -0.15:      # Top third
                return 'top_left'
            elif norm_y > 0.15:     # Bottom third
                return 'bottom_left'
            else:                   # Middle third
                return 'middle_left'
                
        elif norm_x > 0.15:     # Right third (expanded boundaries)
            if norm_y < -0.15:      # Top third
                return 'top_right'
            elif norm_y > 0.15:     # Bottom third
                return 'bottom_right'
            else:                   # Middle third
                return 'middle_right'
                
        else:                   # Center third
            if norm_y < -0.15:      # Top third
                return 'top_center'
            elif norm_y > 0.15:     # Bottom third
                return 'bottom_center'
            else:                   # Middle third
                return 'middle_center'  # Most versatile position

    def start_drag(self, mouse_pos):
        """Start drag operation with enhanced face and zone detection"""
        print(f"\\n🎯 Starting drag at {mouse_pos}")
        
        # Detect face
        face = self._detect_face_from_screen_position(mouse_pos)
        if not face:
            print("❌ No face detected")
            return
        
        # Detect zone on face
        zone = self._detect_zone_on_face(mouse_pos, face)
        if not zone:
            print(f"❌ No zone detected on face {face}")
            return
        
        # Initialize drag
        self.is_dragging = True
        self.drag_start_pos = mouse_pos
        self.drag_current_pos = mouse_pos
        self.detected_face = face
        self.detected_zone = zone
        self.move_executed = False
        
        print(f"✅ Drag started: face={face}, zone={zone} ({self.zone_types[zone]})")

    def update_drag(self, mouse_pos):
        """Update drag and detect moves - ENHANCED with dual-mode detection"""
        if not self.is_dragging or self.move_executed:
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
                print(f"🎮 Move executed: {move}")
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
        
        print(f"🎯 Dual-mode drag analysis:")
        print(f"   dx={dx:.1f}, dy={dy:.1f}, angle={drag_angle:.1f}°")
        print(f"   zone={zone}, direction={primary_direction}")
        print(f"   horizontal_move={is_horizontal_move}, vertical_move={is_vertical_move}")
        print(f"   distance={total_distance:.1f}")
        
        # Generate move based on direction and zone position
        if is_horizontal_move:
            return self._get_horizontal_move_from_position(zone, primary_direction)
        else:
            return self._get_vertical_move_from_position(zone, primary_direction)
    
    def _get_horizontal_move_from_position(self, zone, direction):
        """Get horizontal move based on 3x3 grid position - INTUITIVE DIRECTIONS"""
        # Map 3x3 positions to row moves with intuitive directions based on visual perspective
        if zone in ['top_left', 'top_center', 'top_right']:
            # Top row (U moves) - always follows visual left/right drag direction
            return 'U' if direction == 'right' else "U'"
                
        elif zone in ['middle_left', 'middle_center', 'middle_right']:
            # Middle row (E moves) - always follows visual left/right drag direction
            return 'E' if direction == 'right' else "E'"
                
        else:  # bottom row
            # Bottom row (D moves) - always follows visual left/right drag direction
            return 'D' if direction == 'right' else "D'"
    
    def _get_vertical_move_from_position(self, zone, direction):
        """Get vertical move based on 3x3 grid position - INTUITIVE DIRECTIONS"""
        # Map 3x3 positions to column moves with intuitive directions based on visual perspective
        if zone in ['top_left', 'middle_left', 'bottom_left']:
            # Left column (L moves) - always follows visual up/down drag direction
            return "L'" if direction == 'down' else 'L'
                
        elif zone in ['top_center', 'middle_center', 'bottom_center']:
            # Middle column (M moves) - always follows visual up/down drag direction  
            return "M'" if direction == 'down' else 'M'
                
        else:  # right column
            # Right column (R moves) - always follows visual up/down drag direction
            return "R'" if direction == 'down' else 'R'

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
        if self.is_dragging:
            print("🏁 Drag ended")
        
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_face = None
        self.detected_zone = None
        self.move_executed = False

    def update_visual_feedback(self, dt):
        """Update visual feedback animations"""
        pass

    def render_visual_feedback(self):
        """Render revolutionary visual feedback with zone grid"""
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
        
        # Render revolutionary zone highlights
        self._render_revolutionary_grid()
        
        # Restore state
        glPopMatrix()
        glPopAttrib()
    
    def _render_revolutionary_grid(self):
        """Render a minimal grid overlay on the hovered face only"""
        if not self.hovered_face:
            return
            
        # Don't draw any large face overlays - just draw a small grid on the actual cube face
        # The positioning should be much more precise and smaller
        
        # Large overlay size - matches cube face size
        size = 0.35  # Larger overlay to match cube face dimensions
        
        # Only draw if hovering and highlight is strong enough
        if self.highlight_intensity < 0.3:
            return
            
        # Position directly on the cube face center (no offset)
        face_center = [0, 0, 0]
        
        # Minimal positioning - much closer to the actual cube
        if self.hovered_face == 'front':
            face_center[2] = 0.51  # Just in front of cube face
        elif self.hovered_face == 'back':
            face_center[2] = -0.51
        elif self.hovered_face == 'right':
            face_center[0] = 0.51
        elif self.hovered_face == 'left':
            face_center[0] = -0.51
        elif self.hovered_face == 'top':
            face_center[1] = 0.51
        elif self.hovered_face == 'bottom':
            face_center[1] = -0.51
        
        glPushMatrix()
        glTranslatef(face_center[0], face_center[1], face_center[2])
        
        # Draw minimal grid lines only
        self._draw_minimal_grid(size)
        
        glPopMatrix()
    
    def _draw_minimal_grid(self, size):
        """Draw a minimal 3x3 grid overlay - no large colored blocks"""
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glLineWidth(1.5)
        
        # Very subtle grid lines only
        third = size * 2 / 3
        glColor4f(1.0, 1.0, 1.0, 0.4 * self.highlight_intensity)
        
        # Draw minimal grid lines
        glBegin(GL_LINES)
        
        # Horizontal lines
        for i in range(4):
            y = size - (i * third)
            glVertex3f(-size, y, 0.001)
            glVertex3f(size, y, 0.001)
        
        # Vertical lines  
        for i in range(4):
            x = -size + (i * third)
            glVertex3f(x, -size, 0.001)
            glVertex3f(x, size, 0.001)
            
        glEnd()
        
        # Optional: show a subtle highlight for the current zone
        if self.hovered_zone:
            self._draw_minimal_zone_highlight(size, third)
        
        glLineWidth(1.0)
    
    def _draw_minimal_zone_highlight(self, size, third):
        """Draw a very subtle highlight for the hovered zone"""
        zone_positions = {
            'top_left': (0, 0), 'top_center': (1, 0), 'top_right': (2, 0),
            'middle_left': (0, 1), 'middle_center': (1, 1), 'middle_right': (2, 1),
            'bottom_left': (0, 2), 'bottom_center': (1, 2), 'bottom_right': (2, 2)
        }
        
        if self.hovered_zone not in zone_positions:
            return
            
        col, row = zone_positions[self.hovered_zone]
        
        # Calculate zone bounds
        x1 = -size + col * third
        x2 = -size + (col + 1) * third
        y1 = size - row * third
        y2 = size - (row + 1) * third
        
        # Very subtle highlight
        glColor4f(1.0, 1.0, 0.0, 0.2 * self.highlight_intensity)
        glBegin(GL_QUADS)
        glVertex3f(x1, y1, 0.002)
        glVertex3f(x2, y1, 0.002)
        glVertex3f(x2, y2, 0.002)
        glVertex3f(x1, y2, 0.002)
        glEnd()
        
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