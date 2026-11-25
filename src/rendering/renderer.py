import pygame
from pygame.locals import *
import numpy as np
import math
import time
from OpenGL.GL import *
from OpenGL.GLU import *
from utils.path_helper import resource_path
from src.rendering import backgrounds
from src.ui import ui_style as ui
from src import cube_skins

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

        # Viewport the 3D scene is drawn at (larger than the window with supersampling)
        self.viewport_size = (width, height)

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
        self.skin = cube_skins.get_skin(cube_skins.DEFAULT_SKIN)
        self._time_origin = time.perf_counter()

        # Now initialize cubes after colors are defined
        self.initialize_cubes()

        # Load the single cube model
        self.load_obj(resource_path(self.cube_path))

        # Initialize OpenGL settings
        self.setup_opengl()

        # Procedural background (see src/backgrounds.py)
        self.background = backgrounds.Background()
        self.background_choice = backgrounds.DEFAULT_STYLE
        self.background_mode = "freeplay"
        self.set_background()

        # Create optimized display list for single cube
        self.create_cube_materials()
        self.create_display_list()

        # Store camera rotation for manual control
        self.rotation_x = 0
        self.rotation_y = 0

    def set_background(self, choice=None, stars=None):
        """Pick the background style ("auto" follows the game mode) and the star layer."""
        if choice is not None:
            self.background_choice = choice
        if stars is not None:
            self.background.stars = bool(stars)
        self.background.style = backgrounds.resolve(self.background_choice, self.background_mode)
        self.background.tint = tuple(c / 255.0 for c in ui.MODE_COLORS.get(self.background_mode, ui.ACCENT))

    def set_skin(self, skin_id):
        """Draw the cube with a skin from src/cube_skins.py."""
        self.skin = cube_skins.get_skin(skin_id)
        self.update_cube_colors()

    def _sticker_color(self, index):
        if index < 0:
            return (0.1, 0.1, 0.1)  # inside the cube
        palette = self.skin.get("colors") or self.rubiks_cube.color_map
        return palette[index]

    # Plate axes (T, B) the cube shader uses for each side: top, bottom, right, left, front, back
    _PLATE_AXES = [(0, 2), (0, 2), (1, 2), (1, 2), (0, 1), (0, 1)]
    _NORMALS = [(0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]

    def _sticker_frame(self, face_index, up):
        """The sticker's pattern right and up directions in its side's plate coordinates."""
        if up is None:
            return (1.0, 0.0, 0.0, 1.0)
        right = np.cross(up, self._NORMALS[face_index])
        t, b = self._PLATE_AXES[face_index]
        return (float(right[t]), float(right[b]), float(up[t]), float(up[b]))

    def set_background_mode(self, mode):
        """Game mode changed: used when the style is set to match the game mode."""
        self.background_mode = mode
        self.set_background()

    def render_skybox(self):
        self.background.draw(self.rotation_x, self.rotation_y)

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
                self._carry_grain_orientation()
                # Update cube colors immediately to prevent flicker
                self.update_cube_colors()
            
            self.animating_face = None
            self.animation_cubes = []
            return self.animation_angle_total  # Return final angle
        
        return current_angle
    
    def _carry_grain_orientation(self):
        """A finished turn moves pieces to new slots: hand each piece's grain orientation
        to the slot it landed in, so the surface grain stays put when the slice is
        redrawn unturned with the new colors."""
        ax = np.array(self.animation_axis, dtype=np.float64)
        a = math.radians(self.animation_angle_total)
        k = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        # Rodrigues; quarter turns are exact, so round away float noise
        rot = np.rint(np.identity(3) + math.sin(a) * k + (1 - math.cos(a)) * (k @ k))
        by_slot = {cube['grid_pos']: cube for cube in self.cubes}
        landed = {}
        for cube in self.animation_cubes:
            new_slot = tuple(int(c) for c in rot @ np.array(cube['grid_pos']))
            # Same point on the piece: G_new @ (rot @ v) == G_old @ v
            landed[new_slot] = (cube['grain_orient'] @ rot.T).astype(np.float32)
        for slot, orient in landed.items():
            by_slot[slot]['grain_orient'] = orient

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
                    
                    self.cubes.append({
                        'position': position,
                        'grid_pos': (x, y, z),  # Store grid position for updates
                        # Orientation of the piece in this slot, so its grain turns with it
                        'grain_orient': np.identity(3, dtype=np.float32),
                    })
        self.update_cube_colors()

    def update_cube_colors(self):
        """Update cube colors based on current Rubik's cube state and the skin"""
        for cube in self.cubes:
            x, y, z = cube['grid_pos']
            ids = [self.rubiks_cube.get_color_index(x, y, z, face_index) for face_index in range(6)]
            cube['colors'] = [self._sticker_color(i) for i in ids]
            # Uniform data, ready to upload every frame without conversions
            cube['ids'] = np.array(ids, dtype=np.float32)
            cube['colors_flat'] = np.array(cube['colors'], dtype=np.float32).ravel()
            seeds, frames = [], []
            for face_index in range(6):
                tag, up = self.rubiks_cube.get_sticker(x, y, z, face_index)
                seeds.append(float(max(tag, 0)))
                frames.extend(self._sticker_frame(face_index, up))
            cube['seeds'] = np.array(seeds, dtype=np.float32)
            cube['frames'] = np.array(frames, dtype=np.float32)
    
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
uniform float stickerIds[6]; // color index (0-5) per side, -1 for sides inside the cube
uniform vec4 plate[6];      // flat plate extents per side: amin, amax, bmin, bmax
uniform int skinPattern;    // see src/cube_skins.py PATTERNS
uniform vec3 skinAccent;
uniform vec3 bodyColor;
uniform float bodyGloss;
uniform float uTime;
uniform float stickerSeeds[6]; // physical sticker id per side (stays with the sticker as it moves)
uniform vec4 stickerFrames[6]; // pattern right (xy) and up (zw) per side, in plate coordinates
uniform mat3 grainOrient;      // slot -> piece frame, so the grain stays on the piece as it moves
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

// ---------------------------------------------------------------- skin patterns
// Mirrored on the CPU for the menu previews: src/rendering/skin_preview.py
float hash21(vec2 q) { return fract(sin(dot(q, vec2(127.1, 311.7))) * 43758.5453); }
float box2(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }
vec3 hsv2rgb(float h, float s, float v) {
    vec3 k = clamp(abs(mod(h * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return v * mix(vec3(1.0), k, s);
}
float wob(vec2 p, float seed) {
    return sin(p.x * 7.1 + seed) * 0.5 + sin(p.y * 9.3 + p.x * 3.7 + seed * 1.7) * 0.35
         + sin((p.x - p.y) * 13.0 + seed * 2.3) * 0.2;
}
float glyph(float id, vec2 p) {
    if (id < 0.5) return length(p) - 0.27;                                              // circle
    if (id < 1.5) return min(box2(p, vec2(0.30, 0.08)), box2(p, vec2(0.08, 0.30)));      // plus
    if (id < 2.5) { vec2 t = vec2(p.x, p.y + 0.09);                                      // triangle
                    return max(abs(t.x) * 0.866 + t.y * 0.5, -t.y) - 0.18; }
    if (id < 3.5) return (abs(p.x) + abs(p.y) - 0.34) * 0.7071;                          // diamond
    if (id < 4.5) return abs(length(p) - 0.22) - 0.07;                                   // ring
    vec2 r = vec2(p.x + p.y, p.x - p.y) * 0.7071;                                        // cross
    return min(box2(r, vec2(0.32, 0.075)), box2(r, vec2(0.075, 0.32)));
}

// Sticker color (lit) and glow (unlit) for a point p (-0.5..0.5) on a sticker
void skinColor(int side, vec2 p, vec3 base, vec2 look, float facing, float aa, out vec3 diff, out vec3 emis) {
    float id = stickerIds[side];
    diff = base;
    emis = vec3(0.0);
    if (id < -0.5 || skinPattern == 0) return;
    float seed = stickerSeeds[side] * 7.31;
    if (skinPattern == 1) {            // stripes
        float u = (p.x + p.y) * 2.5;
        diff = mix(base, skinAccent, 1.0 - smoothstep(-aa, aa, (abs(fract(u) - 0.5) - 0.25) / 2.5));
    } else if (skinPattern == 2) {     // checker
        // 4x4 squares with crisp, antialiased edges: a square wave per axis, one pixel wide at the edge
        vec2 t = abs(mod(p * 4.0 + 0.5, 2.0) - 1.0) - 0.5;
        float w = max(4.0 * aa, 1e-4);
        diff = mix(base, skinAccent, 0.5 + 0.5 * clamp(t.x / w, -1.0, 1.0) * clamp(t.y / w, -1.0, 1.0));
    } else if (skinPattern == 3) {     // dots
        vec2 g = fract(p * 3.0 + 0.5) - 0.5;
        diff = mix(base, skinAccent, 1.0 - smoothstep(-aa, aa, (length(g) - 0.28) / 3.0));
    } else if (skinPattern == 4) {     // glyphs
        diff = mix(base, skinAccent, 1.0 - smoothstep(-aa, aa, glyph(id, p)));
    } else if (skinPattern == 5) {     // neon
        float line = abs(rrect(p, 0.36, 0.12));
        float core = 1.0 - smoothstep(-aa, aa, line - 0.025);
        float glow = exp(-line * 26.0);
        float pulse = 0.78 + 0.22 * sin(uTime * 2.2 + seed);
        diff = base * 0.06;
        emis = (base * (core * 1.1 + glow * 0.55) + vec3(core * 0.35)) * pulse;
    } else if (skinPattern == 6) {     // psychedelic
        // Soft drifting swirls of light over the sticker color. Everything is low contrast, low
        // frequency and slow (a full cycle takes over half a minute): nothing flashes or flickers.
        float t = uTime * 0.18;
        vec2 w = p + 0.1 * vec2(sin(p.y * 3.0 + t + seed), cos(p.x * 3.0 - t * 0.8 + seed));
        float swirl = 0.5 + 0.5 * sin((w.x + w.y) * 4.0 + t * 1.5 + seed);
        float haze = 0.5 + 0.5 * sin(length(w) * 5.0 - t + seed * 0.7);
        vec3 light = mix(base, vec3(1.0), 0.4);
        diff = mix(base * 0.82, light, 0.35 * swirl + 0.3 * haze);
    } else if (skinPattern == 7) {     // marble
        float n = wob(p, seed);
        float ph = (p.x * 2.0 + p.y) * 6.0 + n * 3.0;
        float fw = aa * 20.0;                                   // veins per pixel: large at grazing angles
        float v = abs(sin(ph));
        float vein = 1.0 - smoothstep(0.0, 0.18 + min(fw, 1.0) * 0.5, v);
        vein *= 1.0 - smoothstep(0.8, 2.0, fw);                 // fade thin veins out before they alias
        vec3 veinCol = mix(vec3(0.98, 0.97, 0.94), skinAccent, step(0.7, dot(base, vec3(0.333))));
        diff = mix(base, veinCol, vein * 0.95) * (0.92 + 0.08 * n);
    } else if (skinPattern == 8) {     // lava
        float n = wob(p, seed);
        float crack = abs(sin(p.x * 8.0 + n * 4.0 + seed) * sin(p.y * 7.0 - n * 3.0 + seed * 0.7));
        float glow = 1.0 - smoothstep(0.0, 0.22, crack);
        glow = mix(glow, 0.2, smoothstep(0.6, 1.5, aa * 16.0));   // thin cracks average out at grazing angles
        float pulse = 0.7 + 0.3 * sin(uTime * 1.7 + seed + n * 3.0);
        diff = skinAccent * (0.8 + 0.4 * n) + base * 0.12;
        emis = base * glow * pulse * 1.3 + vec3(1.0, 0.9, 0.6) * pow(glow, 4.0) * 0.4 * pulse;
    } else if (skinPattern == 9) {     // eyes: they follow the camera and blink now and then
        float phase = fract(uTime * 0.21 + hash21(vec2(seed, 3.7)));
        float open = 1.0 - smoothstep(0.0, 0.025, phase) * (1.0 - smoothstep(0.035, 0.065, phase));
        float eye_h = 0.40 * open * max(0.0, 1.0 - 3.6 * p.x * p.x);
        float eye = 1.0 - smoothstep(-aa, aa, abs(p.y) - eye_h);
        vec2 c = p - look * 0.13;
        float ir = length(c);
        vec3 e = mix(vec3(0.96, 0.94, 0.9), base * (0.6 + 0.6 * smoothstep(0.0, 0.19, ir)),
                     1.0 - smoothstep(-aa, aa, ir - 0.19));
        e = mix(e, vec3(0.02), 1.0 - smoothstep(-aa, aa, ir - 0.075));
        e = mix(e, vec3(1.0), 1.0 - smoothstep(-aa, aa, length(c - vec2(0.05, 0.05)) - 0.03));
        e *= 1.0 - 0.6 * (1.0 - smoothstep(0.0, 0.05, eye_h - abs(p.y)));
        diff = mix(mix(skinAccent, base, 0.2), e, eye);
    } else if (skinPattern == 10) {    // hologram
        vec3 rainbow = 0.5 + 0.5 * cos(6.2832 * (vec3(0.0, 0.33, 0.67) + (p.x - p.y) * 0.9
                                                 + facing * 1.6 + uTime * 0.05));
        diff = mix(base, rainbow, 0.2);
        float s = hash21(floor(p * 28.0) + seed);
        float fine = 1.0 - smoothstep(0.3, 0.8, aa * 28.0);       // tiny glints vanish instead of flickering
        emis = vec3(step(0.97, s) * (0.5 + 0.5 * sin(uTime * 6.0 + s * 80.0)) * 0.5 * fine);
    } else if (skinPattern == 11) {    // static
        float n = hash21(floor(p * 22.0) + floor(uTime * 18.0) * vec2(1.7, 9.2) + seed);
        n = mix(n, 0.5, smoothstep(0.4, 1.0, aa * 22.0));
        float scan = 0.85 + 0.15 * sin((p.y + uTime * 0.3) * 90.0) * (1.0 - smoothstep(0.25, 0.6, aa * 14.3));
        diff = base * (0.45 + 0.75 * n) * scan;
        emis = base * 0.15 * n;
    } else if (skinPattern == 12) {    // pixel
        vec2 q = (p + 0.5) * 6.0;
        vec2 l = fract(q) - 0.5;
        float inner = 1.0 - smoothstep(-aa, aa, (max(abs(l.x), abs(l.y)) - 0.40) / 6.0);
        diff = mix(base * 0.35, base * (0.78 + 0.3 * hash21(floor(q) + seed)), inner);
    } else if (skinPattern == 13) {    // gems
        float a = atan(p.y, p.x);
        float sector = floor((a + 3.14159) / 0.785398);
        float table = 1.0 - smoothstep(-aa, aa, abs(p.x) + abs(p.y) - 0.22);
        float fb = mix(0.55 + 0.6 * hash21(vec2(sector, id * 3.1)), 1.25, table);
        float tw = pow(max(0.0, sin(uTime * 2.0 + sector * 1.3 + seed)), 16.0) * 0.4;
        diff = base * fb;
        emis = base * tw * 0.5 + vec3(tw * 0.15);
    }
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

    // Very light grain (tileable texture, mipmapped so it never shimmers).
    // Sampled in the piece's own frame so it travels with the piece between slots.
    vec3 gp = grainOrient * vObjP;
    vec3 w = pow(abs(grainOrient * on), vec3(6.0));
    w /= (w.x + w.y + w.z);
    vec2 gx = texture2D(grain, gp.yz * 4.0).rg - 0.5;
    vec2 gy = texture2D(grain, gp.xz * 4.0).rg - 0.5;
    vec2 gz = texture2D(grain, gp.xy * 4.0).rg - 0.5;
    vec3 pert = w.x * (gx.x * vec3(0.0, 1.0, 0.0) + gx.y * vec3(0.0, 0.0, 1.0))
              + w.y * (gy.x * vec3(1.0, 0.0, 0.0) + gy.y * vec3(0.0, 0.0, 1.0))
              + w.z * (gz.x * vec3(1.0, 0.0, 0.0) + gz.y * vec3(0.0, 1.0, 0.0));
    pert = pert * grainOrient;  // back to the slot frame (transpose of a rotation)

    mat3 m = mat3(gl_ModelViewMatrix);

    // Body: plastic in the skin's color
    vec3 nb = normalize(m * normalize(on - pert * 0.25));
    vec3 col = shade(nb, bodyColor, 40.0, 0.22 + bodyGloss, 0.35);

    // Screen derivatives must be taken outside the branch below
    float paa = max(length(fwidth(p)), 1e-4);

    // Sticker: rounded tile that wraps slightly over the bevel
    float d = rrect(p, TILE_HALF, TILE_RADIUS);
    float aa = max(fwidth(d) * 0.7, 1e-4);
    float tile = 1.0 - smoothstep(-aa, aa, d);
    if (tile > 0.0) {
        // Skin pattern, only where there is a sticker. It is drawn in the sticker's own
        // frame so it turns with the sticker; the view direction (object space) lets
        // patterns react to the camera.
        vec3 sdiff = stickers[side];
        vec3 semis = vec3(0.0);
        if (skinPattern != 0) {
            vec3 ve = normalize(-vEyeP);
            vec3 vo = normalize(vec3(dot(m[0], ve), dot(m[1], ve), dot(m[2], ve)));
            vec4 fr = stickerFrames[side];
            vec2 sp = vec2(dot(p, fr.xy), dot(p, fr.zw));
            vec2 look = vec2(dot(vo, T), dot(vo, B));
            look = vec2(dot(look, fr.xy), dot(look, fr.zw));
            skinColor(side, sp, stickers[side], look, abs(dot(vo, on)), paa, sdiff, semis);
        }
        float eps = 0.004;
        vec2 gd = vec2(rrect(p + vec2(eps, 0.0), TILE_HALF, TILE_RADIUS) - d,
                       rrect(p + vec2(0.0, eps), TILE_HALF, TILE_RADIUS) - d) / eps;
        float rim = 1.0 - smoothstep(0.0, 0.03, -d);
        vec3 tilt = (gd.x * T + gd.y * B) * rim * 0.5;
        vec3 nt = normalize(m * normalize(on - pert * 0.6 + tilt));
        vec3 sticker = shade(nt, sdiff, 30.0, 0.20, 0.10) + semis;
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
            self._ids_loc = glGetUniformLocation(program, "stickerIds")
            self._pattern_loc = glGetUniformLocation(program, "skinPattern")
            self._accent_loc = glGetUniformLocation(program, "skinAccent")
            self._body_loc = glGetUniformLocation(program, "bodyColor")
            self._gloss_loc = glGetUniformLocation(program, "bodyGloss")
            self._time_loc = glGetUniformLocation(program, "uTime")
            self._seeds_loc = glGetUniformLocation(program, "stickerSeeds")
            self._frames_loc = glGetUniformLocation(program, "stickerFrames")
            self._grain_orient_loc = glGetUniformLocation(program, "grainOrient")
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
        # The model is slightly off-center. Centered, it is symmetric under quarter
        # turns, so a turned piece lands exactly where its unturned redraw sits and
        # does not jump when a move ends.
        verts -= (verts.min(axis=0) + verts.max(axis=0)) / 2
        center = np.zeros(3)

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
            skin = self.skin
            patterned = skin["pattern_id"] != 0
            glUniform1i(self._pattern_loc, skin["pattern_id"])
            glUniform3fv(self._accent_loc, 1, skin["accent"])
            glUniform3fv(self._body_loc, 1, skin["body"])
            glUniform1f(self._gloss_loc, skin["gloss"])
            # Wrapped so the float stays precise in the shader during long sessions
            glUniform1f(self._time_loc, (time.perf_counter() - self._time_origin) % 3600.0)
        else:
            glEnable(GL_NORMALIZE)
        body_color = self.skin["body"]
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
                glUniform3fv(self._stickers_loc, 6, cube['colors_flat'])
                glUniformMatrix3fv(self._grain_orient_loc, 1, GL_TRUE, cube['grain_orient'])
                if patterned:  # the solid skins never read these
                    glUniform1fv(self._ids_loc, 6, cube['ids'])
                    glUniform1fv(self._seeds_loc, 6, cube['seeds'])
                    glUniform4fv(self._frames_loc, 6, cube['frames'])
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
        if (viewport[2], viewport[3]) != tuple(self.viewport_size):
            # Viewport doesn't match our dimensions, reset it
            glViewport(0, 0, *self.viewport_size)
            
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

        self.background.delete()

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