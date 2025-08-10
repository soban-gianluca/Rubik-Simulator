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
        """Complete 3D face detection system - detects ALL visible cube faces accurately"""
        x, y = mouse_pos
        
        try:
            # Get the accurate ray from the mouse position
            ray_origin, ray_dir = self.get_accurate_ray(x, y)
            
            # Get the actual cube geometry from renderer - make bounds more generous
            cube_spacing = 0.52
            scale_factor = 0.85
            actual_spacing = cube_spacing * scale_factor
            
            # The cube is positioned at (0, 0, -4) in world space
            cube_center = [0, 0, -4]
            half_cube_size = actual_spacing
            
            # Make face bounds more generous for better detection
            face_tolerance = actual_spacing * 1.4  # 40% larger detection area
            
            # Define the 6 faces of the actual 3x3x3 cube
            all_faces = [
                ('front', [0, 0, cube_center[2] + half_cube_size], [0, 0, 1]),
                ('back', [0, 0, cube_center[2] - half_cube_size], [0, 0, -1]),
                ('right', [cube_center[0] + half_cube_size, 0, cube_center[2]], [1, 0, 0]),
                ('left', [cube_center[0] - half_cube_size, 0, cube_center[2]], [-1, 0, 0]),
                ('top', [0, cube_center[1] + half_cube_size, cube_center[2]], [0, 1, 0]),
                ('bottom', [0, cube_center[1] - half_cube_size, cube_center[2]], [0, -1, 0])
            ]
            
            # Filter to only visible faces from current camera angle
            visible_faces = []
            for face_name, face_center, face_normal in all_faces:
                if self.is_face_visible_from_camera(face_name):
                    visible_faces.append((face_name, face_center, face_normal))
            
            # Test ray intersection with each visible face
            valid_intersections = []
            
            for face_name, face_center, face_normal in visible_faces:
                intersection = self.ray_plane_intersection(ray_origin, ray_dir, face_center, face_normal)
                
                if intersection:
                    # Use a more sophisticated bounds check that works better with rotated cubes
                    within_bounds = self.is_point_on_cube_face(intersection, face_name, cube_center, face_tolerance)
                    
                    if within_bounds:
                        # Calculate distance from camera
                        distance = math.sqrt(
                            (intersection[0] - ray_origin[0])**2 + 
                            (intersection[1] - ray_origin[1])**2 + 
                            (intersection[2] - ray_origin[2])**2
                        )
                        valid_intersections.append((face_name, distance, intersection))
            
            # Return the closest intersected face
            if valid_intersections:
                valid_intersections.sort(key=lambda x: x[1])  # Sort by distance
                best_face = valid_intersections[0][0]
                print(f"Selected face: {best_face}")  # Clean feedback
                cube_pos = self._get_cube_pos_for_face(best_face)
                return best_face, cube_pos
                
        except Exception as e:
            pass  # Silent fail
        
        return None, None
    
    def is_point_on_cube_face(self, point, face_name, cube_center, tolerance):
        """Improved bounds checking that works better with rotated cubes"""
        # Convert point to cube-relative coordinates
        rel_x = point[0] - cube_center[0]
        rel_y = point[1] - cube_center[1] 
        rel_z = point[2] - cube_center[2]
        
        # Use more generous bounds for better edge detection
        # The actual cube half-size
        half_size = 0.52 * 0.85  # cube_spacing * scale_factor
        
        # Extend the bounds significantly for better selection
        extended_tolerance = tolerance * 1.2  # Even more generous
        
        if face_name == 'front':
            # Front face: Z should be near +half_size, X and Y within bounds
            z_on_face = abs(rel_z - half_size) < 0.1  # Close to front face
            within_xy = abs(rel_x) <= extended_tolerance and abs(rel_y) <= extended_tolerance
            return z_on_face and within_xy
            
        elif face_name == 'back':
            # Back face: Z should be near -half_size, X and Y within bounds  
            z_on_face = abs(rel_z + half_size) < 0.1  # Close to back face
            within_xy = abs(rel_x) <= extended_tolerance and abs(rel_y) <= extended_tolerance
            return z_on_face and within_xy
            
        elif face_name == 'right':
            # Right face: X should be near +half_size, Y and Z within bounds
            x_on_face = abs(rel_x - half_size) < 0.1  # Close to right face
            within_yz = abs(rel_y) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return x_on_face and within_yz
            
        elif face_name == 'left':
            # Left face: X should be near -half_size, Y and Z within bounds
            x_on_face = abs(rel_x + half_size) < 0.1  # Close to left face
            within_yz = abs(rel_y) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return x_on_face and within_yz
            
        elif face_name == 'top':
            # Top face: Y should be near +half_size, X and Z within bounds
            y_on_face = abs(rel_y - half_size) < 0.1  # Close to top face
            within_xz = abs(rel_x) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return y_on_face and within_xz
            
        elif face_name == 'bottom':
            # Bottom face: Y should be near -half_size, X and Z within bounds
            y_on_face = abs(rel_y + half_size) < 0.1  # Close to bottom face
            within_xz = abs(rel_x) <= extended_tolerance and abs(rel_z) <= extended_tolerance
            return y_on_face and within_xz
            
        return False
    
    def is_face_visible_from_camera(self, face_name):
        """Determine if a face is visible from the current camera angle - optimized for responsiveness"""
        # Get current camera rotations
        rx = self.renderer.rotation_x % 360
        ry = self.renderer.rotation_y % 360
        
        # Normalize angles to [-180, 180] range for easier calculation
        if rx > 180:
            rx -= 360
        if ry > 180:
            ry -= 360
        
        # More generous visibility ranges for better user experience
        # A face is visible if the camera is within ~90-100 degrees of facing it
        
        if face_name == 'front':
            # Front face is visible when looking mostly forward
            return -80 < ry < 80
            
        elif face_name == 'back':
            # Back face is visible when looking mostly backward
            return ry > 100 or ry < -100
            
        elif face_name == 'right':
            # Right face is visible when looking mostly right
            return -170 < ry < -10
            
        elif face_name == 'left':
            # Left face is visible when looking mostly left
            return 10 < ry < 170
            
        elif face_name == 'top':
            # Top face is visible when looking from above or at level
            return rx < 30
            
        elif face_name == 'bottom':
            # Bottom face is visible when looking from below or at level
            return rx > -30
            
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
