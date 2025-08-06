import math
import pygame
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

""" How it works:
Screen divided into 3 vertical columns (left, center, right)
Each column + direction = ONE specific move (NO cycling, NO repetition)
12 total moves available across the 3 areas
Direct mapping:
Left area:

⬆️ Up drag = U
⬇️ Down drag = D
⬅️ Left drag = L
➡️ Right drag = R
Center area:

⬆️ Up drag = U'
⬇️ Down drag = D'
⬅️ Left drag = L'
➡️ Right drag = R'
Right area:

⬆️ Up drag = F
⬇️ Down drag = B
⬅️ Left drag = F'
➡️ Right drag = B' """

class MouseCubeInteraction:
    """ULTRA RELIABLE mouse interaction - direct screen mapping to specific moves"""
    
    def __init__(self, renderer):
        self.renderer = renderer
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_area = None
        self.move_executed = False
        
        # Sensitivity settings
        self.move_sensitivity = 25
        
        # Visual feedback
        self.highlight_area = None
        self.highlight_intensity = 0.0
        self.fade_speed = 4.0
        
        # Movement tracking
        self.last_move_time = 0
        self.move_cooldown = 0.2
        
        # DIRECT SCREEN-TO-MOVE MAPPING - NO CYCLING, NO CONFUSION
        # Screen divided into 3 columns, each column has 4 directional moves
        self.screen_moves = {
            # Left column - Basic moves
            'left_up': 'U',
            'left_down': 'D', 
            'left_left': 'L',
            'left_right': 'R',
            
            # Center column - Prime moves
            'center_up': "U'",
            'center_down': "D'",
            'center_left': "L'",
            'center_right': "R'",
            
            # Right column - Front/Back moves  
            'right_up': 'F',
            'right_down': 'B',
            'right_left': "F'",
            'right_right': "B'"
        }
        
    def start_drag(self, mouse_pos):
        """Start a drag operation with area detection"""
        # Check cooldown to prevent rapid moves
        import time
        current_time = time.time()
        if current_time - self.last_move_time < self.move_cooldown:
            return
            
        self.is_dragging = True
        self.drag_start_pos = mouse_pos
        self.drag_current_pos = mouse_pos
        self.move_executed = False
        
        # Detect which screen area the mouse is in
        self.detected_area = self._detect_screen_area(mouse_pos)
        
        if self.detected_area:
            self.highlight_area = self.detected_area
            self.highlight_intensity = 1.0
            
    def _detect_screen_area(self, mouse_pos):
        """Detect which area of the screen the mouse is in (3x1 grid)"""
        x, y = mouse_pos
        width = self.renderer.width
        height = self.renderer.height
        
        # Divide screen into 3 columns
        col_width = width // 3
        
        # Determine column (left, center, right)
        if x < col_width:
            return 'left'
        elif x < 2 * col_width:
            return 'center'
        else:
            return 'right'
            
    def update_drag(self, mouse_pos):
        """Update drag with direct move detection - NO CYCLING"""
        if not self.is_dragging or self.move_executed:
            return None
            
        self.drag_current_pos = mouse_pos
        
        # Calculate drag vector
        drag_vector = (
            mouse_pos[0] - self.drag_start_pos[0],
            mouse_pos[1] - self.drag_start_pos[1]
        )
        
        drag_distance = math.sqrt(drag_vector[0]**2 + drag_vector[1]**2)
        
        # Check if we've dragged far enough
        if drag_distance > self.move_sensitivity and self.detected_area:
            move = self._get_move_for_drag(drag_vector)
            if move:
                self.move_executed = True
                import time
                self.last_move_time = time.time()
                return move
                
        return None
    
    def _get_move_for_drag(self, drag_vector):
        """Get move based on area and direction - DIRECT MAPPING"""
        if not self.detected_area:
            return None
            
        dx, dy = drag_vector
        area = self.detected_area
        
        # Simple direction detection
        abs_dx = abs(dx)
        abs_dy = abs(dy)
        
        # Determine direction
        if abs_dx > abs_dy:
            # Horizontal movement
            direction = 'right' if dx > 0 else 'left'
        else:
            # Vertical movement  
            direction = 'up' if dy < 0 else 'down'  # Screen Y is inverted
        
        # Create lookup key
        lookup_key = f"{area}_{direction}"
        
        # Return the specific move for this area + direction
        return self.screen_moves.get(lookup_key)
    
    def end_drag(self):
        """End drag operation with proper cleanup"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.move_executed = False
        
    def update_visual_feedback(self, dt):
        """Update visual feedback animations"""
        if self.highlight_intensity > 0 and not self.is_dragging:
            self.highlight_intensity = max(0, self.highlight_intensity - self.fade_speed * dt)
            if self.highlight_intensity <= 0:
                self.highlight_area = None
    
    def reset_interaction(self):
        """Reset the interaction state"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_area = None
        self.move_executed = False
        self.highlight_area = None
        self.highlight_intensity = 0.0
        self.last_move_time = 0
    
    def get_debug_info(self):
        """Get debug information about current interaction state"""
        return {
            'is_dragging': self.is_dragging,
            'detected_area': self.detected_area,
            'highlight_area': self.highlight_area,
            'move_executed': self.move_executed,
            'last_move_time': self.last_move_time,
            'drag_start': self.drag_start_pos,
            'drag_current': self.drag_current_pos
        }
    
    def render_visual_feedback(self):
        """Render visual feedback for mouse interaction"""
        if not self.highlight_area or self.highlight_intensity <= 0:
            return
        
        # Enable blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Render area highlight
        self._render_area_highlight()
        
        # Render drag indicator if dragging
        if self.is_dragging and self.drag_start_pos and self.drag_current_pos:
            self._render_drag_indicator()
    
    def _render_area_highlight(self):
        """Render highlight for the detected area"""
        alpha = self.highlight_intensity * 0.3
        
        # Set highlight color based on area
        area_colors = {
            'left': (1.0, 0.0, 0.0, alpha),      # Red
            'center': (0.0, 1.0, 0.0, alpha),   # Green  
            'right': (0.0, 0.0, 1.0, alpha),    # Blue
        }
        
        color = area_colors.get(self.highlight_area, (1.0, 1.0, 1.0, alpha))
        glColor4f(*color)
        
        # Render a simple screen overlay for area indication
        glBegin(GL_QUADS)
        screen_area = self._get_area_screen_coordinates(self.highlight_area)
        if screen_area:
            for vertex in screen_area:
                glVertex2f(*vertex)
        glEnd()
    
    def _get_area_screen_coordinates(self, area):
        """Get screen coordinates for the area"""
        width = self.renderer.width
        height = self.renderer.height
        
        col_width = width // 3
        
        # Map areas to screen coordinates
        if area == 'left':
            return [(0, 0), (col_width, 0), (col_width, height), (0, height)]
        elif area == 'center':
            return [(col_width, 0), (2 * col_width, 0), (2 * col_width, height), (col_width, height)]
        elif area == 'right':
            return [(2 * col_width, 0), (width, 0), (width, height), (2 * col_width, height)]
        
        return None
    
    def _render_drag_indicator(self):
        """Render line showing drag direction"""
        glColor4f(1.0, 1.0, 1.0, 0.8)
        glLineWidth(3.0)
        
        glBegin(GL_LINES)
        glVertex2f(*self.drag_start_pos)
        glVertex2f(*self.drag_current_pos)
        glEnd()
        
        # Draw arrow head
        dx = self.drag_current_pos[0] - self.drag_start_pos[0]
        dy = self.drag_current_pos[1] - self.drag_start_pos[1]
        
        if dx != 0 or dy != 0:
            length = math.sqrt(dx**2 + dy**2)
            if length > 10:
                # Normalize
                dx /= length
                dy /= length
                
                # Arrow head points
                arrow_size = 10
                angle = 0.5  # radians
                
                # Calculate arrow head points
                x1 = self.drag_current_pos[0] - arrow_size * (dx * math.cos(angle) - dy * math.sin(angle))
                y1 = self.drag_current_pos[1] - arrow_size * (dx * math.sin(angle) + dy * math.cos(angle))
                
                x2 = self.drag_current_pos[0] - arrow_size * (dx * math.cos(-angle) - dy * math.sin(-angle))
                y2 = self.drag_current_pos[1] - arrow_size * (dx * math.sin(-angle) + dy * math.cos(-angle))
                
                glBegin(GL_LINES)
                glVertex2f(*self.drag_current_pos)
                glVertex2f(x1, y1)
                glVertex2f(*self.drag_current_pos)
                glVertex2f(x2, y2)
                glEnd()
        
        glLineWidth(1.0)
