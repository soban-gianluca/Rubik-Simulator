import pygame
from pygame.locals import *
import math

from OpenGL.GL import *
from OpenGL.GLU import *


def load_obj(filename):
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
    
    return vertices, faces

# Load the Rubik's cube model
obj_vertices, obj_faces = load_obj("C:/Users/salma/Desktop/school/test cubo/utils/Rubik's_cube.obj")

# Rubik's cube face colors
cube_colors = {
    'white': (1.0, 1.0, 1.0),
    'yellow': (1.0, 1.0, 0.0),
    'red': (1.0, 0.0, 0.0),
    'orange': (1.0, 0.5, 0.0),
    'blue': (0.0, 0.0, 1.0),
    'green': (0.0, 1.0, 0.0),
    'black': (0.1, 0.1, 0.1)  # For edges/grid lines
}

def get_face_color(face_vertices):
    """Determine face color based on face normal/position"""
    # Calculate face center
    center = [0, 0, 0]
    for vertex_idx in face_vertices:
        vertex = obj_vertices[vertex_idx]
        center[0] += vertex[0]
        center[1] += vertex[1]
        center[2] += vertex[2]
    
    center = [coord / len(face_vertices) for coord in center]
    
    # Determine color based on which face of the cube this is
    # These thresholds may need adjustment based on your OBJ file scale
    threshold = 0.84
    
    if center[1] > threshold:  # Top face
        return cube_colors['white']
    elif center[1] < -threshold:  # Bottom face
        return cube_colors['yellow']
    elif center[0] > threshold:  # Right face
        return cube_colors['red']
    elif center[0] < -threshold:  # Left face
        return cube_colors['orange']
    elif center[2] > threshold:  # Front face
        return cube_colors['blue']
    elif center[2] < -threshold:  # Back face
        return cube_colors['green']
    else:
        return cube_colors['black']  # Internal faces/edges

display_list = None

def create_display_list():
    """Create optimized display list for the cube"""
    global display_list
    display_list = glGenLists(1)
    
    glNewList(display_list, GL_COMPILE)
    
    # Enable smooth shading
    glShadeModel(GL_SMOOTH)
    
    for face in obj_faces:
        color = get_face_color(face)
        glColor3fv(color)
        
        if len(face) == 3:  # Triangle
            glBegin(GL_TRIANGLES)
        elif len(face) == 4:  # Quad
            glBegin(GL_QUADS)
        else:  # Polygon
            glBegin(GL_POLYGON)
        
        for vertex_index in face:
            glVertex3fv(obj_vertices[vertex_index])
        
        glEnd()
    
    glEndList()

def Cube():
    """Render the optimized cube using display list"""
    if display_list:
        glCallList(display_list)

def main():
    pygame.init()
    display = (1280,720)
    pygame.display.set_mode(display, DOUBLEBUF|OPENGL)

    gluPerspective(45, (display[0]/display[1]), 0.1, 50.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    
    # Set up lighting
    glLightfv(GL_LIGHT0, GL_POSITION, [2, 2, 2, 1])
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    glTranslatef(0.0,0.0, -5)
    
    # Create optimized display list
    create_display_list()

    clock = pygame.time.Clock()
    
    # Control variables
    rotation_x = 0
    rotation_y = 0
    auto_rotate = False
    mouse_pressed = False
    last_mouse_pos = (0, 0)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    auto_rotate = not auto_rotate
                elif event.key == pygame.K_r:
                    rotation_x = rotation_y = 0
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    mouse_pressed = True
                    last_mouse_pos = pygame.mouse.get_pos()
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    mouse_pressed = False
            elif event.type == pygame.MOUSEMOTION and mouse_pressed:
                mouse_pos = pygame.mouse.get_pos()
                dx = mouse_pos[0] - last_mouse_pos[0]
                dy = mouse_pos[1] - last_mouse_pos[1]
                rotation_y += dx * 0.5
                rotation_x += dy * 0.5
                last_mouse_pos = mouse_pos

        # Keyboard controls
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            rotation_y -= 2
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            rotation_y += 2
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            rotation_x -= 2
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            rotation_x += 2

        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        
        glPushMatrix()
        
        if auto_rotate:
            glRotatef(1, 3, 1, 1)
        
        glRotatef(rotation_x, 1, 0, 0)
        glRotatef(rotation_y, 0, 1, 0)
        
        Cube()
        
        glPopMatrix()
        
        pygame.display.flip()
        
        fps = clock.tick()
        pygame.display.set_caption(f"FPS: {clock.get_fps():.1f} | Controls: Arrow/WASD, Mouse drag, Space (auto-rotate), R (reset)")


main()