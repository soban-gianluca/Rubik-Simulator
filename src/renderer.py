import pygame
from pygame.locals import *
import numpy as np
import math
import time
import random
from OpenGL.GL import *
from OpenGL.GLU import *
from utils.path_helper import resource_path

class Renderer:
    def __init__(self, width=1280, height=720, cube_path="utils/cube.obj"):
        # Initialize properties
        self.width = width
        self.height = height
        self.cube_path = cube_path
        self.fov = 60 # Field of view for perspective projection

        # OpenGL cube data
        self.obj_vertices = []
        self.obj_faces = []
        self.single_cube_display_list = None

        # 3x3x3 cube positions and colors
        self.cube_size = 1.2  # Larger size for better appearance
        self.cube_spacing = 0.52  # Negative spacing to make cubes overlap slightly
        self.cubes = []

        # Animation system
        self.is_animating = False
        self.animation_start_time = 0
        self.animation_duration = 0.3  # 300ms animation
        self.animating_face = None
        self.animation_axis = None
        self.animation_angle_total = 0
        self.animation_clockwise = True
        self.animation_cubes = []  # Cubes that are part of the rotating face
        self.pending_move = None  # Move to execute when animation completes

        # Skybox properties
        self.skybox_texture = None
        self.skybox_display_list = None
        self.skybox_size = 20.0

        # Rubik's cube face colors - define colors before initializing cubes
        self.cube_colors = {
            'white': (1.0, 1.0, 1.0),     # Top
            'yellow': (1.0, 1.0, 0.0),    # Bottom
            'red': (1.0, 0.0, 0.0),       # Right
            'orange': (1.0, 0.5, 0.0),    # Left
            'blue': (0.0, 0.0, 1.0),      # Front
            'green': (0.0, 1.0, 0.0),     # Back
            'black': (0.1, 0.1, 0.1)      # Internal faces
        }

        # Import and initialize the Rubik's cube logic
        from src.rubiks_cube import RubiksCube
        self.rubiks_cube = RubiksCube()

        # Import settings manager to get current skybox
        from src.settings_manager import SettingsManager
        self.settings_manager = SettingsManager()

        # Now initialize cubes after colors are defined
        self.initialize_cubes()

        # Load the single cube model
        self.load_obj(resource_path(self.cube_path))

        # Initialize OpenGL settings
        self.setup_opengl()

        # Load a procedural skybox texture (no external images)
        # Use freeplay difficulty as default on initialization
        self.reload_skybox_texture("freeplay")
        self.create_spherical_skybox_display_list()  # Using spherical skybox for full panoramic image

        # Create optimized display list for single cube
        self.create_cube_materials()
        self.create_display_list()

        # Store camera rotation for manual control
        self.rotation_x = 0
        self.rotation_y = 0

    def create_procedural_skybox_texture(self, preset="calm"):
        """Create a lightweight procedural skybox texture (no external images)."""
        # Use a higher 2:1 texture for better quality (generated once, cached on GPU)
        width = 2048
        height = 1024

        palettes = {
            "calm": ((42, 61, 115), (118, 160, 210), (118, 160, 210)),
            "green": ((26, 79, 53), (54, 133, 67), (170, 220, 190)),
            "orange": ((40, 20, 10), (170, 90, 40), (255, 200, 140)),
            "red": ((35, 12, 18), (150, 50, 60), (240, 160, 170)),
            "purple": ((36, 20, 70), (90, 60, 150), (175, 120, 230)),
        }

        # Preset names must match difficulty names
        difficulty_palette = {
            "freeplay": "calm",
            "easy": "green",
            "medium": "orange",
            "hard": "red",
            "limited_time": "calm",
            "limited_moves": "calm",
            "daily_cube": "purple"
        }

        palette_key = difficulty_palette.get(preset, "calm")
        top, mid, bottom = palettes.get(palette_key, palettes["calm"])

        # Create base gradient with subtle horizon glow and dithering
        texture_data = bytearray(width * height * 3)
        for y in range(height):
            t = y / (height - 1)
            # Blend top->mid->bottom
            if t < 0.55:
                tt = t / 0.55
                r = int(top[0] + (mid[0] - top[0]) * tt)
                g = int(top[1] + (mid[1] - top[1]) * tt)
                b = int(top[2] + (mid[2] - top[2]) * tt)
            else:
                tt = (t - 0.55) / 0.45
                bottom_bright = (min(255, bottom[0] * 1.4), min(255, bottom[1] * 1.4), min(255, bottom[2] * 1.4))
                r = int(mid[0] + (bottom_bright[0] - mid[0]) * tt)
                g = int(mid[1] + (bottom_bright[1] - mid[1]) * tt)
                b = int(mid[2] + (bottom_bright[2] - mid[2]) * tt)

            # Soft horizon glow near the middle
            glow = max(0.0, 1.0 - abs(t - 0.55) * 6.0)
            r = min(255, int(r + 15 * glow))
            g = min(255, int(g + 12 * glow))
            b = min(255, int(b + 6 * glow))

            # Subtle vignette to reduce flatness
            v = 1.0 - abs(t - 0.5) * 0.18
            r = int(r * v)
            g = int(g * v)
            b = int(b * v)

            row_index = y * width * 3
            for x in range(width):
                # Tiny deterministic dithering to reduce banding
                noise = ((x * 73856093) ^ (y * 19349663)) & 0xFF
                d = (noise - 128) * 0.015
                idx = row_index + x * 3
                texture_data[idx] = min(255, max(0, int(r + d)))
                texture_data[idx + 1] = min(255, max(0, int(g + d)))
                texture_data[idx + 2] = min(255, max(0, int(b + d)))

        # Add sparse star field (very cheap, static)
        rng = random.Random(1337 + hash(preset) % 1000)
        star_count = 320 if palette_key == "calm" else 420
        for _ in range(star_count):
            x = rng.randrange(0, width)
            y = rng.randrange(0, int(height * 0.65))  # upper region
            brightness = rng.randint(180, 255)
            idx = (y * width + x) * 3
            texture_data[idx] = min(255, texture_data[idx] + brightness)
            texture_data[idx + 1] = min(255, texture_data[idx + 1] + brightness)
            texture_data[idx + 2] = min(255, texture_data[idx + 2] + brightness)

        # Add a soft haze band near horizon (no stripes)
        haze_center = int(height * 0.58)
        haze_radius = int(height * 0.18)
        for y in range(max(0, haze_center - haze_radius), min(height, haze_center + haze_radius)):
            falloff = 1.0 - abs(y - haze_center) / haze_radius
            tint = int(18 * falloff)
            row_index = y * width * 3
            for x in range(width):
                idx = row_index + x * 3
                texture_data[idx] = min(255, texture_data[idx] + tint)
                texture_data[idx + 1] = min(255, texture_data[idx + 1] + int(tint * 0.7))
                texture_data[idx + 2] = min(255, texture_data[idx + 2] + int(tint * 0.9))

        # Generate and bind texture
        self.skybox_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.skybox_texture)

        # Texture parameters for seamless panoramic wrapping
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        # Upload texture data
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGB,
            width,
            height,
            0,
            GL_RGB,
            GL_UNSIGNED_BYTE,
            bytes(texture_data),
        )

    def create_fallback_skybox_texture(self):
        """Deprecated: kept for compatibility (procedural texture is used)."""
        self.create_procedural_skybox_texture("calm")
    
    def reload_skybox_texture(self, new_image_path):
        """Reload skybox texture with a new procedural style."""
        try:
            # Clean up old texture
            if self.skybox_texture:
                glDeleteTextures([self.skybox_texture])
                self.skybox_texture = None

            # Clean up old display list
            if self.skybox_display_list:
                glDeleteLists(self.skybox_display_list, 1)
                self.skybox_display_list = None

            # Map incoming difficulty skybox path to a procedural preset
            lowered = (new_image_path or "").lower()
            if "daily_cube" in lowered:
                preset = "daily_cube"
            elif "freeplay" in lowered:
                preset = "freeplay"
            elif "easy" in lowered:
                preset = "easy"
            elif "medium" in lowered:
                preset = "medium"
            elif "hard" in lowered:
                preset = "hard"
            elif "limited_time" in lowered:
                preset = "limited_time"
            elif "limited_moves" in lowered:
                preset = "limited_moves"
            elif "daily" in lowered:
                preset = "daily"
            else:
                preset = "freeplay"

            # Create new procedural texture
            self.create_procedural_skybox_texture(preset)

            # Recreate display list with new texture
            self.create_spherical_skybox_display_list()

        except Exception as e:
            print(f"Failed to reload skybox texture: {e}")
            self.create_procedural_skybox_texture("calm")
            self.create_spherical_skybox_display_list()

    def create_spherical_skybox_display_list(self):
        """Create a spherical skybox for seamless panoramic image mapping"""
        if not self.skybox_texture:
            return
        
        self.skybox_display_list = glGenLists(1)
        glNewList(self.skybox_display_list, GL_COMPILE)
        
        # Enable texturing
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.skybox_texture)
        glColor3f(1.0, 1.0, 1.0)
        
        # Create a sphere for the skybox
        radius = self.skybox_size
        stacks = 64  # Number of horizontal divisions (latitude)
        slices = 128  # Number of vertical divisions (longitude)
        
        # Generate sphere vertices and texture coordinates
        for i in range(stacks):
            lat0 = math.pi * (-0.5 + float(i) / stacks)
            z0 = radius * math.sin(lat0)
            zr0 = radius * math.cos(lat0)
            
            lat1 = math.pi * (-0.5 + float(i + 1) / stacks)
            z1 = radius * math.sin(lat1)
            zr1 = radius * math.cos(lat1)
            
            glBegin(GL_QUAD_STRIP)
            for j in range(slices + 1):
                lng = 2 * math.pi * float(j) / slices
                x = math.cos(lng)
                y = math.sin(lng)
                
                # Texture coordinates for panoramic mapping
                # u goes from 0 to 1 as we go around horizontally
                # v goes from 0 to 1 as we go from bottom to top
                u = float(j) / slices
                v0 = float(i) / stacks
                v1 = float(i + 1) / stacks
                
                # First vertex (lower latitude)
                glTexCoord2f(u, v0)
                glVertex3f(x * zr0, z0, y * zr0)
                
                # Second vertex (higher latitude)
                glTexCoord2f(u, v1)
                glVertex3f(x * zr1, z1, y * zr1)
            glEnd()
        
        glDisable(GL_TEXTURE_2D)
        glEndList()

    def render_skybox(self):
        """Render the spherical skybox"""
        if not self.skybox_display_list:
            return
        
        # Save current matrix
        glPushMatrix()
        
        # Disable depth testing and lighting for skybox
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        
        # Move skybox with camera (no translation, only rotation)
        # The skybox should always be centered on the camera
        glLoadIdentity()
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        # Render the skybox
        glCallList(self.skybox_display_list)
        
        # Re-enable depth testing and lighting
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        
        # Restore matrix
        glPopMatrix()

    def start_face_animation(self, face_name, clockwise=True):
        """Start animation for a face rotation"""
        if self.is_animating:
            return False  # Already animating
        
        # Define which cubes belong to each face and rotation axis
        face_definitions = {
            'R': {'axis': (1, 0, 0), 'cubes': [(1, y, z) for y in [-1, 0, 1] for z in [-1, 0, 1]]},
            'L': {'axis': (-1, 0, 0), 'cubes': [(-1, y, z) for y in [-1, 0, 1] for z in [-1, 0, 1]]},
            'U': {'axis': (0, 1, 0), 'cubes': [(x, 1, z) for x in [-1, 0, 1] for z in [-1, 0, 1]]},
            'D': {'axis': (0, -1, 0), 'cubes': [(x, -1, z) for x in [-1, 0, 1] for z in [-1, 0, 1]]},
            'F': {'axis': (0, 0, 1), 'cubes': [(x, y, 1) for x in [-1, 0, 1] for y in [-1, 0, 1]]},
            'B': {'axis': (0, 0, -1), 'cubes': [(x, y, -1) for x in [-1, 0, 1] for y in [-1, 0, 1]]},
            # Slice moves
            'M': {'axis': (-1, 0, 0), 'cubes': [(0, y, z) for y in [-1, 0, 1] for z in [-1, 0, 1]]},  # Middle slice (same direction as L)
            'E': {'axis': (0, -1, 0), 'cubes': [(x, 0, z) for x in [-1, 0, 1] for z in [-1, 0, 1]]},  # Equatorial slice (same direction as D)
            'S': {'axis': (0, 0, 1), 'cubes': [(x, y, 0) for x in [-1, 0, 1] for y in [-1, 0, 1]]}   # Standing slice (same direction as F)
        }
        
        if face_name not in face_definitions:
            return False
        
        # Set up animation
        self.is_animating = True
        self.animation_start_time = time.time()
        self.animating_face = face_name
        self.animation_axis = face_definitions[face_name]['axis']
        
        # Handle animation direction: face moves vs slice moves need different logic
        if face_name in ['M', 'E', 'S']:
            # Slice moves: keep original direction (they weren't flipped in the logic)
            self.animation_angle_total = 90 if clockwise else -90
        else:
            # Face moves: use flipped direction to match the corrected logic
            self.animation_angle_total = -90 if clockwise else 90
        self.animation_clockwise = clockwise
        
        # Find cubes that are part of this face
        face_cube_positions = face_definitions[face_name]['cubes']
        self.animation_cubes = []
        
        for cube in self.cubes:
            if cube['grid_pos'] in face_cube_positions:
                self.animation_cubes.append(cube)
        
        return True
    
    def update_animation(self):
        """Update animation state and return current rotation angle"""
        if not self.is_animating:
            return 0
        
        current_time = time.time()
        elapsed = current_time - self.animation_start_time
        progress = min(elapsed / self.animation_duration, 1.0)
        
        # Use easing function for smooth animation
        # Ease-out cubic: 1 - (1-t)^3
        eased_progress = 1 - (1 - progress) ** 3
        
        current_angle = self.animation_angle_total * eased_progress
        
        # Check if animation is complete
        if progress >= 1.0:
            self.is_animating = False
            
            # Execute the pending logical move immediately when animation completes
            if hasattr(self, 'pending_move') and self.pending_move:
                self.rubiks_cube.execute_move(self.pending_move)
                self.pending_move = None
                # Update cube colors immediately to prevent flicker
                self.update_cube_colors()
            
            self.animating_face = None
            self.animation_cubes = []
            return self.animation_angle_total  # Return final angle
        
        return current_angle
    
    def initialize_cubes(self):
        """Initialize the position and colors for each small cube in the 3x3x3 grid"""
        self.cubes = []
        # Create 3x3x3 grid of cubes
        scale_factor = 0.85
        for x in range(-1, 2):
            for y in range(-1, 2):
                for z in range(-1, 2):
                    # Calculate position
                    position = [
                        x * self.cube_spacing * scale_factor,
                        y * self.cube_spacing * scale_factor,
                        z * self.cube_spacing * scale_factor
                    ]
                    
                    # Get colors from the Rubik's cube state
                    colors = []
                    for face_index in range(6):
                        color = self.rubiks_cube.get_cube_color(x, y, z, face_index)
                        colors.append(color)
                    
                    self.cubes.append({
                        'position': position,
                        'colors': colors,
                        'grid_pos': (x, y, z)  # Store grid position for updates
                    })
    
    def update_cube_colors(self):
        """Update cube colors based on current Rubik's cube state"""
        for cube in self.cubes:
            x, y, z = cube['grid_pos']
            colors = []
            for face_index in range(6):
                color = self.rubiks_cube.get_cube_color(x, y, z, face_index)
                colors.append(color)
            cube['colors'] = colors
    
    def load_obj(self, filename):
        """Load vertices, faces, and normals from OBJ file"""
        vertices = []
        faces = []
        normals = []

        with open(filename, 'r') as file:
            for line in file:
                if line.startswith('v '):
                    # Parse vertex coordinates
                    coords = line.strip().split()[1:]
                    vertices.append([float(coord) for coord in coords])
                elif line.startswith('vn '):
                    # Parse normals
                    coords = line.strip().split()[1:]
                    normals.append([float(coord) for coord in coords])
                elif line.startswith('f '):
                    # Parse face indices (convert from 1-based to 0-based)
                    face_data = line.strip().split()[1:]
                    face = []
                    for vertex_data in face_data:
                        # Handle cases like "1/1/1" or "1//1" or just "1"
                        vertex_index = int(vertex_data.split('/')[0]) - 1
                        face.append(vertex_index)
                    faces.append(face)

        self.obj_vertices = vertices
        self.obj_faces = faces
        
    def setup_opengl(self):
        """Initialize OpenGL settings"""
        # Reset matrices
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # Set up perspective projection
        gluPerspective(self.fov, (self.width/self.height), 0.1, 50.0)
        # Set the viewport to match window size
        glViewport(0, 0, self.width, self.height)
        
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        
        # Enable multiple light sources
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHT1)
        glEnable(GL_LIGHT2)
        
        # Increase ambient light for all faces to have base illumination
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.4, 0.4, 0.4, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.6, 0.6, 0.6, 1])
        glLightfv(GL_LIGHT0, GL_POSITION, [2, 2, 2, 1])  # Front-top-right
        
        # Add light from opposite direction
        glLightfv(GL_LIGHT1, GL_AMBIENT, [0.2, 0.2, 0.2, 1])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [0.4, 0.4, 0.4, 1])
        glLightfv(GL_LIGHT1, GL_POSITION, [-2, -2, -2, 1])  # Back-bottom-left
        
        # Add a third light for better coverage
        glLightfv(GL_LIGHT2, GL_AMBIENT, [0.2, 0.2, 0.2, 1])
        glLightfv(GL_LIGHT2, GL_DIFFUSE, [0.3, 0.3, 0.3, 1])
        glLightfv(GL_LIGHT2, GL_POSITION, [-2, 2, -2, 1])  # Back-top-left
        
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    def create_display_list(self):
        """Create optimized display lists for the Rubik's cube"""
        self.create_single_cube_display_list()

    # ------------------------------------------------------------------
    # Cube materials: procedural grain texture + one small GLSL program
    # ------------------------------------------------------------------
    _CUBE_VERT = """
#version 120
varying vec3 vObjP;
varying vec3 vObjN;
varying vec3 vEyeP;
void main() {
    vec4 e = gl_ModelViewMatrix * gl_Vertex;
    vEyeP = e.xyz;
    vObjP = gl_Vertex.xyz;
    vObjN = gl_Normal;
    gl_Position = gl_ProjectionMatrix * e;
}
"""

    _CUBE_FRAG = """
#version 120
uniform sampler2D grain;
uniform vec3 stickers[6];   // sticker color per side: top, bottom, right, left, front, back
uniform vec4 plate[6];      // flat plate extents per side: amin, amax, bmin, bmax
varying vec3 vObjP;
varying vec3 vObjN;
varying vec3 vEyeP;

const vec3 KEY  = vec3(0.45, 0.70, 0.55);
const vec3 FILL = vec3(-0.75, 0.10, 0.45);
const float TILE_HALF = 0.54;    // sticker half size in plate units (0.5 = plate edge)
const float TILE_RADIUS = 0.15;

float rrect(vec2 p, float half_size, float r) {
    vec2 q = abs(p) - half_size + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// Soft, slightly toon-like light: smooth wrap diffuse plus a clean glossy dab
vec3 shade(vec3 n, vec3 base, float shin, float spec_k, float rim_k) {
    vec3 v = normalize(-vEyeP);
    vec3 l0 = normalize(KEY);
    vec3 l1 = normalize(FILL);
    float d = 0.60 + 0.40 * smoothstep(-0.25, 0.85, dot(n, l0))
                   + 0.12 * smoothstep(0.0, 0.8, dot(n, l1));
    float s = smoothstep(0.35, 0.55, pow(max(dot(n, normalize(l0 + v)), 0.0), shin)) * spec_k;
    float rim = smoothstep(0.55, 0.9, 1.0 - max(dot(n, v), 0.0)) * rim_k;
    return base * d + vec3(s) + vec3(0.55, 0.65, 0.85) * rim;
}

void main() {
    vec3 on = normalize(vObjN);
    vec3 a = abs(on);

    // Which side this point belongs to, and its coordinates on that side's plate
    int side;
    vec2 q;
    vec3 T;
    vec3 B;
    if (a.y >= a.x && a.y >= a.z) {
        side = on.y > 0.0 ? 0 : 1; q = vObjP.xz; T = vec3(1.0, 0.0, 0.0); B = vec3(0.0, 0.0, 1.0);
    } else if (a.x >= a.z) {
        side = on.x > 0.0 ? 2 : 3; q = vObjP.yz; T = vec3(0.0, 1.0, 0.0); B = vec3(0.0, 0.0, 1.0);
    } else {
        side = on.z > 0.0 ? 4 : 5; q = vObjP.xy; T = vec3(1.0, 0.0, 0.0); B = vec3(0.0, 1.0, 0.0);
    }
    vec4 pr = plate[side];
    vec2 p = (q - pr.xz) / (pr.yw - pr.xz) - 0.5;

    // Very light grain (tileable texture, mipmapped so it never shimmers)
    vec3 w = pow(a, vec3(6.0));
    w /= (w.x + w.y + w.z);
    vec2 gx = texture2D(grain, vObjP.yz * 4.0).rg - 0.5;
    vec2 gy = texture2D(grain, vObjP.xz * 4.0).rg - 0.5;
    vec2 gz = texture2D(grain, vObjP.xy * 4.0).rg - 0.5;
    vec3 pert = w.x * (gx.x * vec3(0.0, 1.0, 0.0) + gx.y * vec3(0.0, 0.0, 1.0))
              + w.y * (gy.x * vec3(1.0, 0.0, 0.0) + gy.y * vec3(0.0, 0.0, 1.0))
              + w.z * (gz.x * vec3(1.0, 0.0, 0.0) + gz.y * vec3(0.0, 1.0, 0.0));

    mat3 m = mat3(gl_ModelViewMatrix);

    // Body: dark glossy plastic
    vec3 nb = normalize(m * normalize(on - pert * 0.25));
    vec3 col = shade(nb, vec3(0.055, 0.058, 0.07), 40.0, 0.22, 0.35);

    // Sticker: rounded tile that wraps slightly over the bevel
    float d = rrect(p, TILE_HALF, TILE_RADIUS);
    float aa = max(fwidth(d) * 0.7, 1e-4);
    float tile = 1.0 - smoothstep(-aa, aa, d);
    if (tile > 0.0) {
        float eps = 0.004;
        vec2 gd = vec2(rrect(p + vec2(eps, 0.0), TILE_HALF, TILE_RADIUS) - d,
                       rrect(p + vec2(0.0, eps), TILE_HALF, TILE_RADIUS) - d) / eps;
        float rim = 1.0 - smoothstep(0.0, 0.03, -d);
        vec3 tilt = (gd.x * T + gd.y * B) * rim * 0.5;
        vec3 nt = normalize(m * normalize(on - pert * 0.6 + tilt));
        vec3 sticker = shade(nt, stickers[side], 30.0, 0.20, 0.10);
        col = mix(col, sticker, tile);
    }
    gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
"""

    def create_cube_materials(self):
        """Build the grain texture and shader used to draw the cube.

        Everything stays tiny on purpose: one 256x256 RGB texture (about 260 KB with
        mipmaps) shared by every cubie, with the sticker/bezel look done procedurally
        in the shader. If the shader can't be built the cube falls back to the plain
        fixed-function look (flat stickers on dark plastic).
        """
        self.cube_program = None
        self.grain_texture = None
        try:
            from OpenGL.GL import shaders
            program = shaders.compileProgram(
                shaders.compileShader(self._CUBE_VERT, GL_VERTEX_SHADER),
                shaders.compileShader(self._CUBE_FRAG, GL_FRAGMENT_SHADER),
                validate=False,
            )
            self._grain_loc = glGetUniformLocation(program, "grain")
            self._stickers_loc = glGetUniformLocation(program, "stickers")
            self._plate_loc = glGetUniformLocation(program, "plate")
        except Exception as e:
            print(f"Cube shader unavailable, using basic shading: {e}")
            return

        # Tileable band-limited noise -> height, stored as (d/dx, d/dy, height)
        size = 256
        rng = np.random.default_rng(7)
        spectrum = np.fft.fft2(rng.standard_normal((size, size)))
        fy = np.fft.fftfreq(size)[:, None]
        fx = np.fft.fftfreq(size)[None, :]
        r = np.sqrt(fx * fx + fy * fy)
        r[0, 0] = 1.0
        shape = np.exp(-(r / 0.22) ** 2) / (r + 0.02)
        shape[0, 0] = 0.0
        h = np.fft.ifft2(spectrum * shape).real
        h = (h - h.mean()) / h.std()
        dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
        dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
        scale = 0.5 / 3.0 / max(dx.std(), dy.std())
        data = np.empty((size, size, 3), dtype=np.uint8)
        data[..., 0] = np.clip(0.5 + dx * scale * 0.5, 0, 1) * 255
        data[..., 1] = np.clip(0.5 + dy * scale * 0.5, 0, 1) * 255
        data[..., 2] = np.clip(0.5 + h / 6.0, 0, 1) * 255

        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        try:
            max_aniso = glGetFloatv(0x84FF)  # GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT
            glTexParameterf(GL_TEXTURE_2D, 0x84FE, min(8.0, float(max_aniso)))
        except Exception:
            pass
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB8, size, size, 0, GL_RGB, GL_UNSIGNED_BYTE, data.tobytes())
        glGenerateMipmap(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, 0)

        self.cube_program = program
        self.grain_texture = tex

    def create_single_cube_display_list(self):
        """Compile the cubie mesh into display lists.

        The cubie model is a closed rounded cube with one flat plate per side. The
        six plates become the stickers (one list per side, so each can be drawn in
        its own color); everything else (the rounded bevels) is the black plastic
        body, drawn with one list. Vertex normals are smoothed across the bevels.
        """
        verts = np.array(self.obj_vertices, dtype=np.float64)
        faces = self.obj_faces
        center = (verts.min(axis=0) + verts.max(axis=0)) / 2

        # Smooth vertex normals (area weighted face normals), oriented outward
        vnormals = np.zeros_like(verts)
        for f in faces:
            fn = np.cross(verts[f[1]] - verts[f[0]], verts[f[2]] - verts[f[0]])
            fn += np.cross(verts[f[2]] - verts[f[0]], verts[f[3]] - verts[f[0]]) if len(f) > 3 else 0
            if np.dot(fn, verts[f[0]] - center) < 0:
                fn = -fn
            for i in f:
                vnormals[i] += fn
        lengths = np.linalg.norm(vnormals, axis=1, keepdims=True)
        vnormals = vnormals / np.where(lengths > 0, lengths, 1)

        # Sticker plates: faces lying entirely on a bounding box side.
        # (axis, sign) per color index: top, bottom, right, left, front, back.
        sides = [(1, 1), (1, -1), (0, 1), (0, -1), (2, 1), (2, -1)]
        tangent_axes = {0: (1, 2), 1: (0, 2), 2: (0, 1)}
        extreme = {s: (verts[:, s[0]].max() if s[1] > 0 else verts[:, s[0]].min()) for s in sides}
        plates = [[] for _ in sides]
        body = []
        for f in faces:
            for index, side in enumerate(sides):
                axis = side[0]
                if all(abs(verts[i][axis] - extreme[side]) < 1e-4 for i in f):
                    plates[index].append(f)
                    break
            else:
                body.append(f)

        def emit(face, axis_normal=None):
            glBegin(GL_QUADS if len(face) == 4 else GL_TRIANGLES)
            for i in face:
                glNormal3fv(axis_normal if axis_normal is not None else vnormals[i])
                glVertex3fv(verts[i])
            glEnd()

        # Fallback lists (fixed pipeline): one per sticker plate, one for the body
        self.face_display_lists = [glGenLists(1) for _ in range(6)]
        plate_ranges = []
        plate_normals = []
        for index, (axis, sign) in enumerate(sides):
            normal = [0.0, 0.0, 0.0]
            normal[axis] = float(sign)
            plate_normals.append(normal)
            a, b = tangent_axes[axis]
            idx = sorted({i for f in plates[index] for i in f})
            plate_ranges.append([verts[idx, a].min(), verts[idx, a].max(),
                                 verts[idx, b].min(), verts[idx, b].max()])
            glNewList(self.face_display_lists[index], GL_COMPILE)
            for f in plates[index]:
                emit(f, normal)
            glEndList()

        self.body_display_list = glGenLists(1)
        glNewList(self.body_display_list, GL_COMPILE)
        for f in body:
            emit(f)
        glEndList()

        # Shader path: the whole cubie in one list, the sticker colors come as a uniform
        self.full_display_list = glGenLists(1)
        glNewList(self.full_display_list, GL_COMPILE)
        for f in body:
            emit(f)
        for index in range(6):
            for f in plates[index]:
                emit(f, plate_normals[index])
        glEndList()

        if self.cube_program:
            glUseProgram(self.cube_program)
            glUniform4fv(self._plate_loc, 6, np.array(plate_ranges, dtype=np.float32))
            glUseProgram(0)

        # Keep single_cube_display_list for backward compatibility
        self.single_cube_display_list = self.face_display_lists[0]

    def rotate_camera(self, azimuth=0, elevation=0):
        """Rotate camera around the cube

        Args:
            azimuth: Horizontal rotation angle (around y-axis)
            elevation: Vertical rotation angle (around x-axis)
        """
        # Pitch (rotation_x) is never clamped, so the camera can loop past vertical
        # and end up upside down. Once that happens, a rightward mouse drag needs to
        # keep turning the view the way the (now inverted) viewer expects, so flip the
        # azimuth input while upside down rather than applying it raw.
        if self.is_upside_down():
            azimuth = -azimuth
        self.rotation_y += azimuth
        self.rotation_x += elevation
        # Vertical limit removed to allow unrestricted look-around

    def is_upside_down(self):
        """
        Whether pitch (rotation_x) has looped past vertical, flipping the view top-to-bottom.

        Pitch always rotates around the screen-fixed horizontal axis, so it never rolls
        the view - it only flips "up" into "down" once it passes 90deg/270deg. That flip
        happens exactly where cos(rotation_x) changes sign, independent of yaw.
        """
        return math.cos(math.radians(self.rotation_x)) < 0
        
    def render_cube(self):
        """Render the 3x3x3 Rubik's cube using individual cubes with animation"""
        if not hasattr(self, 'face_display_lists'):
            return
        
        # Get current animation angle
        animation_angle = self.update_animation()
        
        textured = self.cube_program is not None
        if textured:
            glUseProgram(self.cube_program)
            glUniform1i(self._grain_loc, 0)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.grain_texture)
        else:
            glEnable(GL_NORMALIZE)
        body_color = (0.04, 0.04, 0.045)
        glEnable(GL_CULL_FACE)  # the cubie mesh is closed and wound outward

        # Render each small cube
        for cube in self.cubes:
            position = cube['position']
            colors = cube['colors']
            is_animating_cube = cube in self.animation_cubes
            
            glPushMatrix()
            
            # Position this cube
            glTranslatef(position[0], position[1], position[2])
            
            # Apply animation rotation if this cube is part of the animating face
            if is_animating_cube and self.is_animating:
                # Translate to origin for rotation
                glTranslatef(-position[0], -position[1], -position[2])
                
                # Apply rotation around the face axis
                if self.animation_axis == (1, 0, 0):  # X-axis (R)
                    glRotatef(animation_angle, 1, 0, 0)
                elif self.animation_axis == (-1, 0, 0):  # -X-axis (L)
                    glRotatef(animation_angle, -1, 0, 0)
                elif self.animation_axis == (0, 1, 0):  # Y-axis (U)
                    glRotatef(animation_angle, 0, 1, 0)
                elif self.animation_axis == (0, -1, 0):  # -Y-axis (D)
                    glRotatef(animation_angle, 0, -1, 0)
                elif self.animation_axis == (0, 0, 1):  # Z-axis (F)
                    glRotatef(animation_angle, 0, 0, 1)
                elif self.animation_axis == (0, 0, -1):  # -Z-axis (B)
                    glRotatef(animation_angle, 0, 0, -1)
                
                # Translate back to position
                glTranslatef(position[0], position[1], position[2])
            
            # Scale the cube
            glScalef(0.8, 0.8, 0.8)
            
            if textured:
                glUniform3fv(self._stickers_loc, 6, [c for color in colors for c in color])
                glCallList(self.full_display_list)
            else:
                # Black plastic body, then each sticker plate in its color
                glColor3fv(body_color)
                glCallList(self.body_display_list)
                for i in range(6):
                    glColor3fv(colors[i])
                    glCallList(self.face_display_lists[i])

            glPopMatrix()

        glDisable(GL_CULL_FACE)
        if textured:
            glUseProgram(0)
            glBindTexture(GL_TEXTURE_2D, 0)
        else:
            glDisable(GL_NORMALIZE)

    def render_frame(self, debug_callback=None):
        """Render a frame and return the surface (for compatibility with existing code)
        
        Args:
            debug_callback: Optional callback function to render debug visualizations
                           after the cube but before exiting the 3D transformation context.
        """
        # Check if viewport matches the current dimensions
        viewport = glGetIntegerv(GL_VIEWPORT)
        if viewport[2] != self.width or viewport[3] != self.height:
            # Viewport doesn't match our dimensions, reset it
            glViewport(0, 0, self.width, self.height)
            
            # Also reset projection matrix
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(45, (self.width/self.height), 0.1, 50.0)
            glMatrixMode(GL_MODELVIEW)
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Render skybox first (before any transformations)
        self.render_skybox()
        
        glPushMatrix()
        
        # Position the camera
        glTranslatef(0.0, 0.0, -4.0)
        
        # Apply rotations
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        
        # Render the cube
        self.render_cube()
        
        # Call debug callback if provided (renders in 3D space with cube transformations)
        if debug_callback:
            debug_callback()
        
        glPopMatrix()
        
        # For compatibility, return None since OpenGL renders directly to screen
        return None
        
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'face_display_lists'):
            for display_list in self.face_display_lists:
                glDeleteLists(display_list, 1)
            self.face_display_lists = None
            self.single_cube_display_list = None
            glDeleteLists(self.body_display_list, 1)
            glDeleteLists(self.full_display_list, 1)

        if self.grain_texture:
            glDeleteTextures([self.grain_texture])
            self.grain_texture = None
        if self.cube_program:
            glDeleteProgram(self.cube_program)
            self.cube_program = None

        # Clean up skybox resources
        if self.skybox_texture:
            glDeleteTextures([self.skybox_texture])
            self.skybox_texture = None
        
        if self.skybox_display_list:
            glDeleteLists(self.skybox_display_list, 1)
            self.skybox_display_list = None
    
    def render_visual_hint(self, face, clockwise, pulse_time):
        """Render a visual hint arrow showing which face to rotate and in which direction
        
        Args:
            face: Face letter (R, L, U, D, F, B)
            clockwise: True for clockwise rotation, False for counterclockwise
            pulse_time: Start time for pulsing animation
        """
        # Calculate pulse effect (0.5 to 1.0)
        pulse = 0.5 + 0.5 * abs(math.sin((time.time() - pulse_time) * 3))
        
        # Map face to position and normal - right on the cube face
        face_positions = {
            'R': (1.0, 0, 0, (1, 0, 0)),     # Right face
            'L': (-1.0, 0, 0, (-1, 0, 0)),   # Left face
            'U': (0, 1.0, 0, (0, 1, 0)),     # Up/Top face
            'D': (0, -1.0, 0, (0, -1, 0)),   # Down/Bottom face
            'F': (0, 0, 1.0, (0, 0, 1)),     # Front face
            'B': (0, 0, -1.0, (0, 0, -1))    # Back face
        }
        
        if face not in face_positions:
            return
        
        pos_x, pos_y, pos_z, normal = face_positions[face]
        
        glPushMatrix()
        
        # Move to face position
        glTranslatef(pos_x, pos_y, pos_z)
        
        # Orient the arrow to face outward from the cube
        if face == 'R':
            glRotatef(90, 0, 1, 0)
        elif face == 'L':
            glRotatef(-90, 0, 1, 0)
        elif face == 'U':
            glRotatef(-90, 1, 0, 0)
        elif face == 'D':
            glRotatef(90, 1, 0, 0)
        elif face == 'B':
            glRotatef(180, 0, 1, 0)
        # F face doesn't need rotation
        
        # Disable lighting for bright arrows
        glDisable(GL_LIGHTING)
        
        # Set arrow color (bright yellow/gold with pulse)
        glColor4f(1.0 * pulse, 1.0 * pulse, 0.2, 0.9)
        
        # Draw circular arrow indicating rotation direction
        # Invert direction because we're looking at the face from outside
        self._draw_circular_arrow(not clockwise, pulse)
        
        # Re-enable lighting
        glEnable(GL_LIGHTING)
        
        glPopMatrix()
    
    def _draw_circular_arrow(self, clockwise, pulse):
        """Draw a circular arrow with arrowhead to indicate rotation direction"""
        radius = 0.8
        thickness = 0.08 * pulse
        segments = 32
        arc_angle = 270  # 3/4 circle
        
        # Draw the arc
        glBegin(GL_QUAD_STRIP)
        for i in range(segments + 1):
            angle = (i / segments) * arc_angle
            if not clockwise:
                angle = -angle
            
            rad = math.radians(angle)
            
            # Outer point
            x_outer = (radius + thickness) * math.cos(rad)
            y_outer = (radius + thickness) * math.sin(rad)
            
            # Inner point
            x_inner = (radius - thickness) * math.cos(rad)
            y_inner = (radius - thickness) * math.sin(rad)
            
            glVertex3f(x_inner, y_inner, 0.01)
            glVertex3f(x_outer, y_outer, 0.01)
        glEnd()
        
        # Draw arrowhead at the end of the arc
        arrow_angle = arc_angle if clockwise else -arc_angle
        arrow_rad = math.radians(arrow_angle)
        
        # Position of arrowhead
        arrow_x = radius * math.cos(arrow_rad)
        arrow_y = radius * math.sin(arrow_rad)
        
        # Direction perpendicular to the arc (tangent)
        if clockwise:
            tangent_x = -math.sin(arrow_rad)
            tangent_y = math.cos(arrow_rad)
        else:
            tangent_x = math.sin(arrow_rad)
            tangent_y = -math.cos(arrow_rad)
        
        # Arrowhead size
        arrow_size = 0.25 * pulse
        
        # Draw triangular arrowhead
        glBegin(GL_TRIANGLES)
        # Tip of arrow
        glVertex3f(arrow_x + tangent_x * arrow_size, 
                   arrow_y + tangent_y * arrow_size, 0.01)
        # Base corners
        glVertex3f(arrow_x - tangent_x * arrow_size * 0.3 + tangent_y * arrow_size * 0.5,
                   arrow_y - tangent_y * arrow_size * 0.3 - tangent_x * arrow_size * 0.5, 0.01)
        glVertex3f(arrow_x - tangent_x * arrow_size * 0.3 - tangent_y * arrow_size * 0.5,
                   arrow_y - tangent_y * arrow_size * 0.3 + tangent_x * arrow_size * 0.5, 0.01)
        glEnd()