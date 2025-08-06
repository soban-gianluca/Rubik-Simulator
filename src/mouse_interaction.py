"""
Rubik's Cube Mouse Interaction System

HOW IT WORKS:
- The screen is divided into 6 regions (top, bottom, left, right, front, back)
- Each region corresponds to a face of the cube
- Click and drag in any region to rotate that face
- Drag direction determines rotation: horizontal (left/right) or vertical (up/down)
- Visual guide shows color-coded zones and available moves
- Hover over regions to see which face you'll control

CONTROLS:
- Drag horizontally: clockwise/counter-clockwise rotation
- Drag vertically: alternate rotation direction
- Visual feedback shows active regions and move hints
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
        self.move_executed = False
        
        # Simple settings
        self.move_sensitivity = 15
        self.last_move_time = 0
        self.move_cooldown = 0.05  # Very short cooldown
        
        # Visual feedback
        self.highlight_face = None
        self.highlight_intensity = 0.0
        self.fade_speed = 3.0
        
        # Visual guide system
        self.show_guide = True
        self.guide_alpha = 0.8
        self.guide_fade_time = 3.0  # Show guide for 3 seconds after start
        
    def start_drag(self, mouse_pos):
        """Start dragging - detect face immediately"""
        import time
        current_time = time.time()
        if current_time - self.last_move_time < self.move_cooldown:
            return
            
        self.is_dragging = True
        self.drag_start_pos = mouse_pos
        self.drag_current_pos = mouse_pos
        self.move_executed = False
        
        # Simple face detection based on screen regions
        self.detected_face = self._simple_face_detection(mouse_pos)
        if self.detected_face:
            self.highlight_face = self.detected_face
            self.highlight_intensity = 1.0
            
    def _simple_face_detection(self, mouse_pos):
        """ULTRA SIMPLE face detection that actually works"""
        x, y = mouse_pos
        width = self.renderer.width
        height = self.renderer.height
        
        # Convert to percentages
        x_pct = x / width
        y_pct = y / height
        
        # Simple 6-region detection
        if y_pct < 0.25:
            return 'top'
        elif y_pct > 0.75:
            return 'bottom'
        elif x_pct < 0.25:
            return 'left'
        elif x_pct > 0.75:
            return 'right'
        elif x_pct < 0.5:
            return 'front'
        else:
            return 'back'
            
    def update_drag(self, mouse_pos):
        """Update drag and generate moves"""
        if not self.is_dragging or self.move_executed or not self.detected_face:
            return None
            
        self.drag_current_pos = mouse_pos
        
        # Calculate drag distance
        dx = mouse_pos[0] - self.drag_start_pos[0]
        dy = mouse_pos[1] - self.drag_start_pos[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if distance > self.move_sensitivity:
            # Generate move based on drag direction
            move = self._get_move(self.detected_face, dx, dy)
            if move:
                self.move_executed = True
                import time
                self.last_move_time = time.time()
                return move
                
        return None
    
    def _get_move(self, face, dx, dy):
        """Generate move based on face and drag direction"""
        # Use strongest direction
        if abs(dx) > abs(dy):
            # Horizontal drag
            if dx > 0:  # Right
                moves = {'front': 'F', 'back': "B'", 'right': 'R', 'left': "L'", 'top': 'U', 'bottom': "D'"}
            else:  # Left
                moves = {'front': "F'", 'back': 'B', 'right': "R'", 'left': 'L', 'top': "U'", 'bottom': 'D'}
        else:
            # Vertical drag
            if dy > 0:  # Down
                moves = {'front': "F'", 'back': 'B', 'right': "R'", 'left': 'L', 'top': "U'", 'bottom': 'D'}
            else:  # Up
                moves = {'front': 'F', 'back': "B'", 'right': 'R', 'left': "L'", 'top': 'U', 'bottom': "D'"}
        
        return moves.get(face)
    
    def end_drag(self):
        """End drag operation"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.move_executed = False
        self.detected_face = None
        
    def update_visual_feedback(self, dt):
        """Update visual effects"""
        if self.highlight_intensity > 0 and not self.is_dragging:
            self.highlight_intensity = max(0, self.highlight_intensity - self.fade_speed * dt)
            if self.highlight_intensity <= 0:
                self.highlight_face = None
                
        # Fade out guide after some time
        if self.show_guide and self.guide_alpha > 0:
            self.guide_fade_time -= dt
            if self.guide_fade_time <= 0:
                self.guide_alpha = max(0, self.guide_alpha - dt * 0.5)
                if self.guide_alpha <= 0:
                    self.show_guide = False
    
    def render_visual_feedback(self):
        """Render visual feedback AND helpful guide"""
        # Show control guide overlay
        if self.show_guide and self.guide_alpha > 0:
            self._render_control_guide()
            
        # Show current hover/selection
        if self.highlight_face and self.highlight_intensity > 0:
            self._render_highlight()
            
    def _render_control_guide(self):
        """Render helpful control guide overlay"""
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        w, h = self.renderer.width, self.renderer.height
        alpha = self.guide_alpha * 0.2  # Subtle overlay
        
        # Draw guide zones
        zones = [
            ('TOP', (0, 0, w, h*0.25), (1.0, 0.5, 0.0), 'U / U\''),  # Orange
            ('BOTTOM', (0, h*0.75, w, h*0.25), (0.8, 0.0, 1.0), 'D / D\''),  # Purple
            ('LEFT', (0, h*0.25, w*0.25, h*0.5), (0.0, 1.0, 0.0), 'L / L\''),  # Green
            ('RIGHT', (w*0.75, h*0.25, w*0.25, h*0.5), (1.0, 0.0, 0.4), 'R / R\''),  # Red
            ('FRONT', (w*0.25, h*0.25, w*0.25, h*0.5), (0.0, 0.8, 1.0), 'F / F\''),  # Blue
            ('BACK', (w*0.5, h*0.25, w*0.25, h*0.5), (1.0, 0.8, 0.0), 'B / B\'')  # Yellow
        ]
        
        # Set up 2D rendering for text overlays
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.renderer.width, self.renderer.height, 0, -1, 1)
        
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Draw zone backgrounds and borders
        for zone_name, (x, y, width, height), color, moves in zones:
            # Background
            glColor4f(color[0], color[1], color[2], alpha)
            glBegin(GL_QUADS)
            glVertex2f(x, y)
            glVertex2f(x + width, y)
            glVertex2f(x + width, y + height)
            glVertex2f(x, y + height)
            glEnd()
            
            # Border
            glColor4f(1.0, 1.0, 1.0, self.guide_alpha * 0.8)
            glLineWidth(2.0)
            glBegin(GL_LINE_LOOP)
            glVertex2f(x, y)
            glVertex2f(x + width, y)
            glVertex2f(x + width, y + height)
            glVertex2f(x, y + height)
            glEnd()
        
        # Draw grid lines
        glColor4f(1.0, 1.0, 1.0, self.guide_alpha * 0.4)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        # Horizontal lines
        glVertex2f(0, h*0.25)
        glVertex2f(w, h*0.25)
        glVertex2f(0, h*0.75)
        glVertex2f(w, h*0.75)
        # Vertical lines
        glVertex2f(w*0.25, h*0.25)
        glVertex2f(w*0.25, h*0.75)
        glVertex2f(w*0.5, h*0.25)
        glVertex2f(w*0.5, h*0.75)
        glVertex2f(w*0.75, h*0.25)
        glVertex2f(w*0.75, h*0.75)
        glEnd()
        
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
            
    def _render_highlight(self):
        """Render face highlight"""
        # Simple colored overlay based on face
        colors = {
            'front': (0.0, 0.8, 1.0),   # Blue
            'back': (1.0, 0.8, 0.0),    # Yellow
            'right': (1.0, 0.0, 0.4),   # Red
            'left': (0.0, 1.0, 0.0),    # Green
            'top': (1.0, 0.5, 0.0),     # Orange
            'bottom': (0.8, 0.0, 1.0)   # Purple
        }
        
        color = colors.get(self.highlight_face, (1.0, 1.0, 1.0))
        alpha = self.highlight_intensity * 0.3
        
        # Simple screen overlay
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.renderer.width, self.renderer.height, 0, -1, 1)
        
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        glColor4f(color[0], color[1], color[2], alpha)
        
        # Draw region based on detected face
        w, h = self.renderer.width, self.renderer.height
        if self.highlight_face == 'top':
            glBegin(GL_QUADS)
            glVertex2f(0, 0)
            glVertex2f(w, 0)
            glVertex2f(w, h*0.25)
            glVertex2f(0, h*0.25)
            glEnd()
        elif self.highlight_face == 'bottom':
            glBegin(GL_QUADS)
            glVertex2f(0, h*0.75)
            glVertex2f(w, h*0.75)
            glVertex2f(w, h)
            glVertex2f(0, h)
            glEnd()
        elif self.highlight_face == 'left':
            glBegin(GL_QUADS)
            glVertex2f(0, h*0.25)
            glVertex2f(w*0.25, h*0.25)
            glVertex2f(w*0.25, h*0.75)
            glVertex2f(0, h*0.75)
            glEnd()
        elif self.highlight_face == 'right':
            glBegin(GL_QUADS)
            glVertex2f(w*0.75, h*0.25)
            glVertex2f(w, h*0.25)
            glVertex2f(w, h*0.75)
            glVertex2f(w*0.75, h*0.75)
            glEnd()
        elif self.highlight_face == 'front':
            glBegin(GL_QUADS)
            glVertex2f(w*0.25, h*0.25)
            glVertex2f(w*0.5, h*0.25)
            glVertex2f(w*0.5, h*0.75)
            glVertex2f(w*0.25, h*0.75)
            glEnd()
        elif self.highlight_face == 'back':
            glBegin(GL_QUADS)
            glVertex2f(w*0.5, h*0.25)
            glVertex2f(w*0.75, h*0.25)
            glVertex2f(w*0.75, h*0.75)
            glVertex2f(w*0.5, h*0.75)
            glEnd()
        
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        
    def update_hover(self, mouse_pos):
        """Update hover detection and show which region is active"""
        if self.is_dragging:
            return
            
        # Detect face under mouse for hover effect
        face = self._simple_face_detection(mouse_pos)
        if face != self.highlight_face:
            self.highlight_face = face
            self.highlight_intensity = 0.5  # Gentle hover
    
    def toggle_guide(self):
        """Toggle the visual guide on/off"""
        self.show_guide = not self.show_guide
        if self.show_guide:
            self.guide_alpha = 0.8
            self.guide_fade_time = 5.0  # Show for 5 seconds
    
    def get_debug_info(self):
        """Get debug info for compatibility"""
        return {
            'is_dragging': self.is_dragging,
            'detected_face': self.detected_face,
            'highlight_face': self.highlight_face,
            'move_executed': self.move_executed
        }
    
    def reset_interaction(self):
        """Reset everything"""
        self.is_dragging = False
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.detected_face = None
        self.move_executed = False
        self.highlight_face = None
        self.highlight_intensity = 0.0
        self.last_move_time = 0
