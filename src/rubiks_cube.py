import numpy as np
import copy

class RubiksCube:
    def __init__(self):
        # Initialize a solved cube state
        # Each face is represented as a 3x3 array of colors
        # 0=white(top), 1=yellow(bottom), 2=red(right), 3=orange(left), 4=blue(front), 5=green(back)
        self.faces = {
            'top': np.full((3, 3), 0),     # White
            'bottom': np.full((3, 3), 1),  # Yellow
            'right': np.full((3, 3), 2),   # Red
            'left': np.full((3, 3), 3),    # Orange
            'front': np.full((3, 3), 4),   # Blue
            'back': np.full((3, 3), 5)     # Green
        }
        
        # Map colors to RGB values for rendering
        self.color_map = {
            0: (1.0, 1.0, 1.0),    # White
            1: (1.0, 1.0, 0.0),    # Yellow
            2: (1.0, 0.0, 0.0),    # Red
            3: (1.0, 0.5, 0.0),    # Orange
            4: (0.0, 0.0, 1.0),    # Blue
            5: (0.0, 1.0, 0.0),    # Green
        }
        
        # Move history for undo functionality
        self.move_history = []
        
    def get_cube_color(self, x, y, z, face_index):
        """Get the color for a specific cube face at position (x,y,z)"""
        # Convert 3D position to face position
        # x,y,z are in range [-1, 0, 1]
        face_names = ['top', 'bottom', 'right', 'left', 'front', 'back']
        
        # Map 3D coordinates to 2D face coordinates
        # This mapping is critical - it determines how the logical cube maps to visual
        if face_index == 0 and y == 1:  # Top face (white)
            row, col = 1-z, x+1
        elif face_index == 1 and y == -1:  # Bottom face (yellow)
            row, col = z+1, x+1
        elif face_index == 2 and x == 1:  # Right face (red)
            row, col = 1-y, z+1
        elif face_index == 3 and x == -1:  # Left face (orange)
            row, col = 1-y, 1-z  # Correct mapping for left face
        elif face_index == 4 and z == 1:  # Front face (blue)
            row, col = 1-y, x+1
        elif face_index == 5 and z == -1:  # Back face (green)
            row, col = 1-y, 1-x  # Correct mapping for back face
        else:
            return (0.1, 0.1, 0.1)  # Internal face (black)
        
        # Ensure coordinates are valid
        if 0 <= row < 3 and 0 <= col < 3:
            color_index = self.faces[face_names[face_index]][row, col]
            return self.color_map[color_index]
        
        return (0.1, 0.1, 0.1)  # Black for internal faces
    
    def rotate_face_clockwise(self, face_array):
        """Rotate a 3x3 face array 90 degrees clockwise"""
        return np.rot90(face_array, -1)
    
    def rotate_face_counterclockwise(self, face_array):
        """Rotate a 3x3 face array 90 degrees counterclockwise"""
        return np.rot90(face_array, 1)
    
    def move_R(self, clockwise=True):
        """Rotate the right face - Standard Rubik's cube R move"""
        self.move_history.append(('R', clockwise))
        
        if clockwise:
            # Rotate right face clockwise
            self.faces['right'] = self.rotate_face_clockwise(self.faces['right'])
            
            # R move edge cycle: top-right -> back-left -> bottom-right -> front-right -> top-right
            # FIXED: Reverse the cycle to match visual animation direction
            temp = self.faces['top'][:, 2].copy()
            self.faces['top'][:, 2] = self.faces['back'][:, 0][::-1]  # Back face reversal
            self.faces['back'][:, 0] = self.faces['bottom'][:, 2][::-1]  # Back face reversal
            self.faces['bottom'][:, 2] = self.faces['front'][:, 2]
            self.faces['front'][:, 2] = temp
        else:
            # Rotate right face counterclockwise (R' move)
            self.faces['right'] = self.rotate_face_counterclockwise(self.faces['right'])
            
            # Original cycle direction for counterclockwise
            temp = self.faces['top'][:, 2].copy()
            self.faces['top'][:, 2] = self.faces['front'][:, 2]
            self.faces['front'][:, 2] = self.faces['bottom'][:, 2]
            self.faces['bottom'][:, 2] = self.faces['back'][:, 0][::-1]
            self.faces['back'][:, 0] = temp[::-1]
    
    def move_L(self, clockwise=True):
        """Rotate the left face - Standard Rubik's cube L move"""
        self.move_history.append(('L', clockwise))
        
        if clockwise:
            # Rotate left face clockwise
            self.faces['left'] = self.rotate_face_clockwise(self.faces['left'])
            
            # L move edge cycle: FIXED direction to match visual
            temp = self.faces['top'][:, 0].copy()
            self.faces['top'][:, 0] = self.faces['front'][:, 0]
            self.faces['front'][:, 0] = self.faces['bottom'][:, 0]
            self.faces['bottom'][:, 0] = self.faces['back'][:, 2][::-1]  # Back face reversal
            self.faces['back'][:, 2] = temp[::-1]  # Back face reversal
        else:
            # Rotate left face counterclockwise (L' move)
            self.faces['left'] = self.rotate_face_counterclockwise(self.faces['left'])
            
            # Reverse the cycle
            temp = self.faces['top'][:, 0].copy()
            self.faces['top'][:, 0] = self.faces['back'][:, 2][::-1]
            self.faces['back'][:, 2] = self.faces['bottom'][:, 0][::-1]
            self.faces['bottom'][:, 0] = self.faces['front'][:, 0]
            self.faces['front'][:, 0] = temp
    
    def move_U(self, clockwise=True):
        """Rotate the upper (top) face - Standard Rubik's cube U move"""
        self.move_history.append(('U', clockwise))
        
        if clockwise:
            # Rotate top face clockwise
            self.faces['top'] = self.rotate_face_clockwise(self.faces['top'])
            
            # U move edge cycle: FIXED direction to match visual
            temp = self.faces['front'][0, :].copy()
            self.faces['front'][0, :] = self.faces['left'][0, :]
            self.faces['left'][0, :] = self.faces['back'][0, :]
            self.faces['back'][0, :] = self.faces['right'][0, :]
            self.faces['right'][0, :] = temp
        else:
            # Rotate top face counterclockwise (U' move)
            self.faces['top'] = self.rotate_face_counterclockwise(self.faces['top'])
            
            # Reverse the cycle
            temp = self.faces['front'][0, :].copy()
            self.faces['front'][0, :] = self.faces['right'][0, :]
            self.faces['right'][0, :] = self.faces['back'][0, :]
            self.faces['back'][0, :] = self.faces['left'][0, :]
            self.faces['left'][0, :] = temp
    
    def move_D(self, clockwise=True):
        """Rotate the down (bottom) face - Standard Rubik's cube D move"""
        self.move_history.append(('D', clockwise))
        
        if clockwise:
            # Rotate bottom face clockwise
            self.faces['bottom'] = self.rotate_face_clockwise(self.faces['bottom'])
            
            # D move edge cycle: FIXED direction to match visual
            temp = self.faces['front'][2, :].copy()
            self.faces['front'][2, :] = self.faces['right'][2, :]
            self.faces['right'][2, :] = self.faces['back'][2, :]
            self.faces['back'][2, :] = self.faces['left'][2, :]
            self.faces['left'][2, :] = temp
        else:
            # Rotate bottom face counterclockwise (D' move)
            self.faces['bottom'] = self.rotate_face_counterclockwise(self.faces['bottom'])
            
            # Reverse the cycle
            temp = self.faces['front'][2, :].copy()
            self.faces['front'][2, :] = self.faces['left'][2, :]
            self.faces['left'][2, :] = self.faces['back'][2, :]
            self.faces['back'][2, :] = self.faces['right'][2, :]
            self.faces['right'][2, :] = temp
    
    def move_F(self, clockwise=True):
        """Rotate the front face - Standard Rubik's cube F move"""
        self.move_history.append(('F', clockwise))
        
        if clockwise:
            # Rotate front face clockwise
            self.faces['front'] = self.rotate_face_clockwise(self.faces['front'])
            
            # F move edge cycle: FIXED direction to match visual
            temp = self.faces['top'][2, :].copy()
            self.faces['top'][2, :] = self.faces['right'][:, 0]
            self.faces['right'][:, 0] = self.faces['bottom'][0, :][::-1]  # bottom row reversed
            self.faces['bottom'][0, :] = self.faces['left'][:, 2]
            self.faces['left'][:, 2] = temp[::-1]  # temp reversed
        else:
            # Rotate front face counterclockwise (F' move)
            self.faces['front'] = self.rotate_face_counterclockwise(self.faces['front'])
            
            # Reverse the cycle
            temp = self.faces['top'][2, :].copy()
            self.faces['top'][2, :] = self.faces['left'][:, 2][::-1]  # left column reversed
            self.faces['left'][:, 2] = self.faces['bottom'][0, :]
            self.faces['bottom'][0, :] = self.faces['right'][:, 0][::-1]  # right column reversed
            self.faces['right'][:, 0] = temp
    
    def move_B(self, clockwise=True):
        """Rotate the back face - Standard Rubik's cube B move"""
        self.move_history.append(('B', clockwise))
        
        if clockwise:
            # Rotate back face clockwise
            self.faces['back'] = self.rotate_face_clockwise(self.faces['back'])
            
            # B move edge cycle: FIXED direction to match visual
            temp = self.faces['top'][0, :].copy()
            self.faces['top'][0, :] = self.faces['left'][:, 0][::-1]  # left column reversed
            self.faces['left'][:, 0] = self.faces['bottom'][2, :]
            self.faces['bottom'][2, :] = self.faces['right'][:, 2][::-1]  # right column reversed
            self.faces['right'][:, 2] = temp
        else:
            # Rotate back face counterclockwise (B' move)
            self.faces['back'] = self.rotate_face_counterclockwise(self.faces['back'])
            
            # Reverse the cycle
            temp = self.faces['top'][0, :].copy()
            self.faces['top'][0, :] = self.faces['right'][:, 2]
            self.faces['right'][:, 2] = self.faces['bottom'][2, :][::-1]  # bottom row reversed
            self.faces['bottom'][2, :] = self.faces['left'][:, 0]
            self.faces['left'][:, 0] = temp[::-1]  # temp reversed
    
    def execute_move(self, move_notation):
        """Execute a move using standard Rubik's cube notation"""
        move_notation = move_notation.strip().upper()
        
        if move_notation == 'R':
            self.move_R(True)
        elif move_notation == "R'":
            self.move_R(False)
        elif move_notation == 'L':
            self.move_L(True)
        elif move_notation == "L'":
            self.move_L(False)
        elif move_notation == 'U':
            self.move_U(True)
        elif move_notation == "U'":
            self.move_U(False)
        elif move_notation == 'D':
            self.move_D(True)
        elif move_notation == "D'":
            self.move_D(False)
        elif move_notation == 'F':
            self.move_F(True)
        elif move_notation == "F'":
            self.move_F(False)
        elif move_notation == 'B':
            self.move_B(True)
        elif move_notation == "B'":
            self.move_B(False)
        else:
            print(f"Unknown move: {move_notation}")
    
    def undo_last_move(self):
        """Undo the last move"""
        if not self.move_history:
            return False
        
        last_move, was_clockwise = self.move_history.pop()
        
        # Execute the opposite move
        if last_move == 'R':
            self.move_R(not was_clockwise)
        elif last_move == 'L':
            self.move_L(not was_clockwise)
        elif last_move == 'U':
            self.move_U(not was_clockwise)
        elif last_move == 'D':
            self.move_D(not was_clockwise)
        elif last_move == 'F':
            self.move_F(not was_clockwise)
        elif last_move == 'B':
            self.move_B(not was_clockwise)
        
        # Remove the undo move from history
        self.move_history.pop()
        return True
    
    def scramble(self, num_moves=20):
        """Scramble the cube with random moves"""
        import random
        moves = ['R', "R'", 'L', "L'", 'U', "U'", 'D', "D'", 'F', "F'", 'B', "B'"]
        
        # Clear history before scrambling
        self.move_history.clear()
        
        for _ in range(num_moves):
            move = random.choice(moves)
            self.execute_move(move)
        
        # Clear history after scrambling so undo doesn't undo scramble
        self.move_history.clear()
    
    def is_solved(self):
        """Check if the cube is in solved state"""
        for face_name, face_array in self.faces.items():
            if not np.all(face_array == face_array[0, 0]):
                return False
        return True