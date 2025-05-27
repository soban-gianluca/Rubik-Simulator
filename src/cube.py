import numpy as np
from enum import Enum

class Color(Enum):
    WHITE = 0
    YELLOW = 1
    BLUE = 2
    GREEN = 3
    RED = 4
    ORANGE = 5

class Face(Enum):
    UP = 0
    DOWN = 1
    FRONT = 2
    BACK = 3
    RIGHT = 4
    LEFT = 5

class RubiksCube:
    def __init__(self):
        # Initialize a solved 3x3 cube
        # Each face is represented by a 3x3 grid of colors
        # We use numpy arrays for efficient manipulation
        self.faces = {}
        self.faces[Face.UP] = np.full((3, 3), Color.WHITE)
        self.faces[Face.DOWN] = np.full((3, 3), Color.YELLOW)
        self.faces[Face.FRONT] = np.full((3, 3), Color.BLUE)
        self.faces[Face.BACK] = np.full((3, 3), Color.GREEN)
        self.faces[Face.RIGHT] = np.full((3, 3), Color.RED)
        self.faces[Face.LEFT] = np.full((3, 3), Color.ORANGE)
    
    def rotate_face_clockwise(self, face):
        """Rotate the given face 90 degrees clockwise"""
        self.faces[face] = np.rot90(self.faces[face], k=3)  # k=3 means 270 degrees counter-clockwise, which is 90 degrees clockwise
    
    def rotate_face_counter_clockwise(self, face):
        """Rotate the given face 90 degrees counter-clockwise"""
        self.faces[face] = np.rot90(self.faces[face], k=1)
    
    def move_right(self, clockwise=True):
        """Perform R move (right face rotation)"""
        # Save affected pieces
        temp = self.faces[Face.UP][:, 2].copy()
        
        if clockwise:
            # Move UP to FRONT
            self.faces[Face.UP][:, 2] = self.faces[Face.BACK][::-1, 0]
            # Move BACK to DOWN
            self.faces[Face.BACK][:, 0] = self.faces[Face.DOWN][::-1, 2]
            # Move DOWN to FRONT
            self.faces[Face.DOWN][:, 2] = self.faces[Face.FRONT][:, 2]
            # Move FRONT to UP
            self.faces[Face.FRONT][:, 2] = temp
            
            # Rotate RIGHT face
            self.rotate_face_clockwise(Face.RIGHT)
        else:
            # Move UP to BACK
            self.faces[Face.UP][:, 2] = self.faces[Face.FRONT][:, 2][::-1]
            # Move BACK to DOWN
            self.faces[Face.BACK][:, 0] = self.faces[Face.UP][:, 2][::-1]
            # Move DOWN to FRONT
            self.faces[Face.DOWN][:, 2] = self.faces[Face.BACK][:, 0][::-1]
            # Move FRONT to UP
            self.faces[Face.FRONT][:, 2] = temp
            
            # Rotate RIGHT face
            self.rotate_face_counter_clockwise(Face.RIGHT)
    
    # Add more moves (U, D, F, B, L) following the same pattern
    
    def is_solved(self):
        """Check if the cube is solved"""
        for face in Face:
            if not np.all(self.faces[face] == self.faces[face][0, 0]):
                return False
        return True
    
    def __str__(self):
        """String representation of the cube for printing"""
        result = []
        
        # Add spacing for UP
        for row in self.faces[Face.UP]:
            result.append("      " + " ".join(str(color.value) for color in row))
        
        # Add LEFT, FRONT, RIGHT, BACK in one row
        for i in range(3):
            row = []
            for face in [Face.LEFT, Face.FRONT, Face.RIGHT, Face.BACK]:
                row.extend(str(color.value) for color in self.faces[face][i])
                row.append(" ")
            result.append(" ".join(row))
        
        # Add spacing for DOWN
        for row in self.faces[Face.DOWN]:
            result.append("      " + " ".join(str(color.value) for color in row))
        
        return "\n".join(result)


if __name__ == "__main__":
    # Example usage
    cube = RubiksCube()
    print("Initial state:")
    print(cube)