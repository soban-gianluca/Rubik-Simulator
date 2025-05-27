import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from cube import Color, Face, RubiksCube

class CubeRenderer:
    def __init__(self):
        self.color_map = {
            Color.WHITE: '#FFFFFF',
            Color.YELLOW: '#FFFF00',
            Color.BLUE: '#0000FF',
            Color.GREEN: '#00FF00',
            Color.RED: '#FF0000',
            Color.ORANGE: '#FFA500'
        }
        
    def create_square(self, center, normal, size=0.9):
        """Create a square face given center point, normal vector, and size"""
        # Create a unit square in the xy plane
        half_size = size / 2
        corners = np.array([
            [-half_size, -half_size, 0],
            [half_size, -half_size, 0],
            [half_size, half_size, 0],
            [-half_size, half_size, 0]
        ])
        
        # Rotate to align with normal vector
        if np.allclose(normal, [0, 0, 1]):  # UP face
            pass  # Already aligned
        elif np.allclose(normal, [0, 0, -1]):  # DOWN face
            corners = corners @ np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])
        elif np.allclose(normal, [0, 1, 0]):  # FRONT face
            corners = corners @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
        elif np.allclose(normal, [0, -1, 0]):  # BACK face
            corners = corners @ np.array([[1, 0, 0], [0, 0, -1], [0, -1, 0]])
        elif np.allclose(normal, [1, 0, 0]):  # RIGHT face
            corners = corners @ np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]])
        elif np.allclose(normal, [-1, 0, 0]):  # LEFT face
            corners = corners @ np.array([[0, 0, -1], [0, 1, 0], [-1, 0, 0]])
        
        # Translate to center
        corners += center
        return corners
    
    def get_face_centers_and_normals(self):
        """Get center positions and normal vectors for each face"""
        face_data = {
            Face.UP: (np.array([0, 0, 1.5]), np.array([0, 0, 1])),
            Face.DOWN: (np.array([0, 0, -1.5]), np.array([0, 0, -1])),
            Face.FRONT: (np.array([0, 1.5, 0]), np.array([0, 1, 0])),
            Face.BACK: (np.array([0, -1.5, 0]), np.array([0, -1, 0])),
            Face.RIGHT: (np.array([1.5, 0, 0]), np.array([1, 0, 0])),
            Face.LEFT: (np.array([-1.5, 0, 0]), np.array([-1, 0, 0]))
        }
        return face_data
    
    def render_cube(self, cube, title="Rubik's Cube", figsize=(10, 8)):
        """Render the cube in 3D"""
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111, projection='3d')
        
        face_data = self.get_face_centers_and_normals()
        
        for face_enum in Face:
            face_center, face_normal = face_data[face_enum]
            face_colors = cube.faces[face_enum]
            
            # Create 9 small squares for each face
            for i in range(3):
                for j in range(3):
                    # Calculate position for each small square
                    # Offset from face center based on i, j position
                    offset_x = (j - 1) * 0.33  # -0.33, 0, 0.33
                    offset_y = (1 - i) * 0.33  # 0.33, 0, -0.33
                    
                    if face_enum == Face.UP:
                        square_center = face_center + np.array([offset_x, offset_y, 0])
                    elif face_enum == Face.DOWN:
                        square_center = face_center + np.array([offset_x, -offset_y, 0])
                    elif face_enum == Face.FRONT:
                        square_center = face_center + np.array([offset_x, 0, offset_y])
                    elif face_enum == Face.BACK:
                        square_center = face_center + np.array([-offset_x, 0, offset_y])
                    elif face_enum == Face.RIGHT:
                        square_center = face_center + np.array([0, -offset_x, offset_y])
                    elif face_enum == Face.LEFT:
                        square_center = face_center + np.array([0, offset_x, offset_y])
                    
                    # Create and add the square
                    square = self.create_square(square_center, face_normal, size=0.3)
                    color = self.color_map[face_colors[i, j]]
                    
                    poly = Poly3DCollection([square], facecolors=color, 
                                          edgecolors='black', linewidths=1, alpha=0.8)
                    ax.add_3d_collection(poly)
        
        # Set equal aspect ratio and limits
        ax.set_xlim([-2, 2])
        ax.set_ylim([-2, 2])
        ax.set_zlim([-2, 2])
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title(title)
        
        # Remove axes for cleaner look
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        
        plt.tight_layout()
        return fig, ax
    
    def show_cube(self, cube, title="Rubik's Cube"):
        """Display the cube"""
        fig, ax = self.render_cube(cube, title)
        plt.show()
    
    def save_cube(self, cube, filename, title="Rubik's Cube"):
        """Save cube visualization to file"""
        fig, ax = self.render_cube(cube, title)
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()

# Example usage
if __name__ == "__main__":
    cube = RubiksCube()
    renderer = CubeRenderer()
    
    print("Showing solved cube:")
    renderer.show_cube(cube, "Solved Rubik's Cube")
    
    # Perform some moves and show again
    cube.move_right(clockwise=True)
    print("After R move:")
    renderer.show_cube(cube, "After R Move")