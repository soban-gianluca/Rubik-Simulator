import pygame
import numpy as np
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

class FaceOverlay:
    def __init__(self, width=1024, height=768):
        self.width = width
        self.height = height
        self.enabled = True
        self.fade_alpha = 0.8  # How visible the overlays are (0.0 = transparent, 1.0 = opaque)
        
        # Face mapping to keyboard controls and labels
        self.face_controls = {
            'R': {'key': 'R', 'key_inv': 'Shift+R', 'label': 'R', 'label_inv': "R'"},
            'L': {'key': 'L', 'key_inv': 'Shift+L', 'label': 'L', 'label_inv': "L'"},
            'U': {'key': 'U', 'key_inv': 'Shift+U', 'label': 'U', 'label_inv': "U'"},
            'D': {'key': 'D', 'key_inv': 'Shift+D', 'label': 'D', 'label_inv': "D'"},
            'F': {'key': 'F', 'key_inv': 'Shift+F', 'label': 'F', 'label_inv': "F'"},
            'B': {'key': 'B', 'key_inv': 'Shift+B', 'label': 'B', 'label_inv': "B'"}
        }
        
        # Initialize fonts for text rendering
        pygame.font.init()
        self.font_large = pygame.font.SysFont('Arial', 24, bold=True)
        self.font_small = pygame.font.SysFont('Arial', 16, bold=True)
        self.font_arrow = pygame.font.SysFont('Arial', 20, bold=True)  # For arrow symbols
        
        # Colors for different elements
        self.overlay_bg_color = (0, 0, 0, 180)  # Semi-transparent black
        self.text_color = (255, 255, 255, 255)  # White text
        self.highlight_color = (255, 255, 0, 200)  # Yellow highlight
        self.clockwise_color = (0, 255, 100, 255)  # Green for clockwise
        self.counterclockwise_color = (255, 100, 100, 255)  # Red for counter-clockwise
        
        # Current highlighted face (for visual feedback)
        self.highlighted_face = None
        self.highlight_timer = 0
        self.highlight_duration = 0.5  # seconds
        
        # Last move time for fading effect
        self.last_move_time = 0
        
    def toggle(self):
        """Toggle the overlay system on/off"""
        self.enabled = not self.enabled
        return self.enabled
    
    def set_highlight(self, face_name):
        """Highlight a specific face when a move is made"""
        self.highlighted_face = face_name
        self.highlight_timer = self.highlight_duration
        self.last_move_time = pygame.time.get_ticks() / 1000.0
    
    def update(self, delta_time):
        """Update the overlay state"""
        if self.highlight_timer > 0:
            self.highlight_timer -= delta_time
            if self.highlight_timer <= 0:
                self.highlighted_face = None
    
    def get_face_center_2d(self, face_name, rotation_x, rotation_y):
        """Calculate the 2D screen position of a face center"""
        # Define face centers in 3D space relative to cube center
        # Swapped U/D and F/B based on user feedback that they appeared on opposite faces
        face_centers_3d = {
            'R': (0.8, 0, 0),     # Right face - x=1
            'L': (-0.8, 0, 0),    # Left face - x=-1
            'U': (0, -0.8, 0),    # Top face - y=-1
            'D': (0, 0.8, 0),     # Bottom face - y=1
            'F': (0, 0, -0.8),    # Front face - z=-1
            'B': (0, 0, 0.8)      # Back face - z=1
        }
        
        # Define face normals (direction the face is pointing)
        face_normals = {
            'R': (1, 0, 0),       # Right face points in +X direction
            'L': (-1, 0, 0),      # Left face points in -X direction
            'U': (0, -1, 0),      # Top face points in -Y direction
            'D': (0, 1, 0),       # Bottom face points in +Y direction
            'F': (0, 0, -1),      # Front face points in -Z direction
            'B': (0, 0, 1)        # Back face points in +Z direction
        }
        
        if face_name not in face_centers_3d:
            return None
            
        # Get 3D position and normal
        x, y, z = face_centers_3d[face_name]
        nx, ny, nz = face_normals[face_name]
        
        # Apply rotation transformations (same as camera)
        # Convert to radians
        rot_x_rad = math.radians(rotation_x)
        rot_y_rad = math.radians(rotation_y)
        
        # Apply Y rotation first (around Y axis) to position
        cos_y = math.cos(rot_y_rad)
        sin_y = math.sin(rot_y_rad)
        x_rot = x * cos_y - z * sin_y
        z_rot = x * sin_y + z * cos_y
        
        # Apply Y rotation to normal
        nx_rot = nx * cos_y - nz * sin_y
        nz_rot = nx * sin_y + nz * cos_y
        
        # Apply X rotation (around X axis) to position
        cos_x = math.cos(rot_x_rad)
        sin_x = math.sin(rot_x_rad)
        y_rot = y * cos_x - z_rot * sin_x
        z_final = y * sin_x + z_rot * cos_x
        
        # Apply X rotation to normal
        ny_rot = ny * cos_x - nz_rot * sin_x
        nz_final = ny * sin_x + nz_rot * cos_x
        
        # Check if face is facing towards camera
        # Face is visible if its normal has a negative Z component (pointing towards camera)
        if nz_final >= -0.1:  # Face is not facing the camera
            return None
        
        # Apply camera translation (same as in renderer: -4.0 Z offset)
        z_final -= 4.0
        
        # Check if face is behind camera or too close
        if z_final >= -0.1:  # Face is behind camera or too close
            return None
        
        # Project to screen coordinates using perspective projection
        # Using same FOV as renderer (60 degrees)
        fov_rad = math.radians(60)
        aspect_ratio = self.width / self.height
        
        # Perspective projection
        screen_x = (x_rot / (-z_final * math.tan(fov_rad / 2))) * (self.width / 2) + (self.width / 2)
        screen_y = (y_rot / (-z_final * math.tan(fov_rad / 2) / aspect_ratio)) * (self.height / 2) + (self.height / 2)
        
        # Check if coordinates are within screen bounds
        if 0 <= screen_x <= self.width and 0 <= screen_y <= self.height:
            return (int(screen_x), int(screen_y))
        
        return None
    
    def render_face_overlay(self, surface, face_name, screen_pos, is_highlighted=False):
        """Render an overlay for a single face"""
        if not screen_pos:
            return
            
        x, y = screen_pos
        face_info = self.face_controls.get(face_name)
        if not face_info:
            return
        
        # Background circle/rectangle
        overlay_size = 70 if is_highlighted else 60  # Back to original size
        bg_color = self.highlight_color if is_highlighted else self.overlay_bg_color
        
        # Create a surface for the overlay with alpha
        overlay_surf = pygame.Surface((overlay_size, overlay_size), pygame.SRCALPHA)
        
        # Draw background circle
        pygame.draw.circle(overlay_surf, bg_color, (overlay_size//2, overlay_size//2), overlay_size//2)
        
        # Draw both key bindings with simple ASCII directional indicators
        key = face_info['key']
        key_inv = face_info['key_inv']
        center_x = overlay_size // 2
        center_y = overlay_size // 2
        
        # Main key (clockwise) with ASCII rotation indicator
        clockwise_text = f"{key}"  # Just show the key
        clockwise_render = self.font_small.render(clockwise_text, True, self.clockwise_color[:3])
        clockwise_rect = clockwise_render.get_rect(center=(center_x, center_y - 10))
        overlay_surf.blit(clockwise_render, clockwise_rect)
        
        # Inverse key (counter-clockwise) with shortened format
        counter_text = f"S+{key}"  # Shortened "Shift+" to "S+"
        counter_render = self.font_small.render(counter_text, True, self.counterclockwise_color[:3])
        counter_rect = counter_render.get_rect(center=(center_x, center_y + 10))
        overlay_surf.blit(counter_render, counter_rect)
        
        # Apply fade alpha
        overlay_surf.set_alpha(int(255 * self.fade_alpha))
        
        # Blit to main surface
        surface.blit(overlay_surf, (x - overlay_size//2, y - overlay_size//2))
    
    def render_control_hint(self, surface):
        """Render control hints at the bottom of the screen"""
        if not self.enabled:
            return
            
        hint_text = "Face Controls: R/Shift+R | L/Shift+L | U/Shift+U | D/Shift+D | F/Shift+F | B/Shift+B | H=Toggle Overlays"
        text_surf = self.font_small.render(hint_text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=(self.width//2, self.height - 20))
        
        # Semi-transparent background
        bg_rect = pygame.Rect(text_rect.left - 10, text_rect.top - 5, text_rect.width + 20, text_rect.height + 10)
        bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, 150))
        
        surface.blit(bg_surf, bg_rect)
        surface.blit(text_surf, text_rect)
    
    def render(self, surface, rotation_x, rotation_y):
        """Render all face overlays"""
        if not self.enabled:
            return
        
        # Render overlays for each visible face
        for face_name in self.face_controls.keys():
            screen_pos = self.get_face_center_2d(face_name, rotation_x, rotation_y)
            if screen_pos:
                is_highlighted = (face_name == self.highlighted_face and self.highlight_timer > 0)
                self.render_face_overlay(surface, face_name, screen_pos, is_highlighted)