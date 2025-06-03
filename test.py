import pygame
from pygame.locals import *

from OpenGL.GL import *
from OpenGL.GLU import *

verticies = (
    (1, -1, -1),
    (1, 1, -1),
    (-1, 1, -1),
    (-1, -1, -1),
    (1, -1, 1),
    (1, 1, 1),
    (-1, -1, 1),
    (-1, 1, 1)
    )

edges = (
    (0,1),
    (0,3),
    (0,4),
    (2,1),
    (2,3),
    (2,7),
    (6,3),
    (6,4),
    (6,7),
    (5,1),
    (5,4),
    (5,7)
    )

faces = (
    (0,1,2,3),  # front face
    (3,2,7,6),  # left face
    (6,7,5,4),  # back face
    (4,5,1,0),  # right face
    (1,5,7,2),  # top face
    (4,0,3,6)   # bottom face
)

colors = (
    (1,0,0),    # red
    (0,1,0),    # green
    (0,0,1),    # blue
    (1,1,0),    # yellow
    (1,0,1),    # magenta
    (0,1,1)     # cyan
)


def Cube():
    glBegin(GL_QUADS)
    for i, face in enumerate(faces):
        glColor3fv(colors[i])
        for vertex in face:
            glVertex3fv(verticies[vertex])
    glEnd()


def main():
    pygame.init()
    display = (1280,720)
    pygame.display.set_mode(display, DOUBLEBUF|OPENGL)

    gluPerspective(45, (display[0]/display[1]), 0.1, 50.0)
    glEnable(GL_DEPTH_TEST)

    glTranslatef(0.0,0.0, -5)

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
        
        fps = clock.tick(60)
        pygame.display.set_caption(f"FPS: {clock.get_fps():.1f} | Controls: Arrow/WASD, Mouse drag, Space (auto-rotate), R (reset)")


main()