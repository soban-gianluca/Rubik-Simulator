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
        
        # Map colors to RGB values for rendering - Improved for better color distinction
        self.color_map = {
            0: (1.0, 0.95, 0.0),   # White - Pure white
            1: (1.0, 1.0, 1.0),    # Yellow - Pure yellow
            2: (0.9, 0.1, 0.1),    # Red - Deep red with slight darkness for better realism
            3: (1.0, 0.35, 0.0),   # Orange - More distinct orange, less green component
            4: (0.0, 0.2, 0.9),    # Blue - Brighter blue with slight lightness
            5: (0.0, 0.8, 0.2),    # Green - Forest green for better distinction from other colors
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
            row, col = z+1, x+1  
        elif face_index == 1 and y == -1:  # Bottom face (yellow)
            row, col = 1-z, x+1  
        elif face_index == 2 and x == 1:  # Right face (red)
            row, col = 1-y, 1-z  # Fixed: prevent conflict with front face
        elif face_index == 3 and x == -1:  # Left face (orange)
            row, col = 1-y, z+1  # Fixed: prevent conflict with front face
        elif face_index == 4 and z == 1:  # Front face (blue)
            row, col = 1-y, x+1
        elif face_index == 5 and z == -1:  # Back face (green)
            row, col = 1-y, 1-x
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
            # Rotate right face clockwise (fixed)
            self.faces['right'] = self.rotate_face_clockwise(self.faces['right'])
            
            # Correct R move (clockwise): front → bottom → back → top → front
            temp = self.faces['front'][:, 2].copy()
            self.faces['front'][:, 2] = self.faces['bottom'][:, 2].copy()
            self.faces['bottom'][:, 2] = self.faces['back'][:, 0][::-1].copy()  
            self.faces['back'][:, 0] = self.faces['top'][:, 2][::-1].copy()  
            self.faces['top'][:, 2] = temp.copy()
        else:
            # Rotate right face counterclockwise (fixed)
            self.faces['right'] = self.rotate_face_counterclockwise(self.faces['right'])
            
            # Correct R' move (counter-clockwise): front → top → back → bottom → front
            temp = self.faces['front'][:, 2].copy()
            self.faces['front'][:, 2] = self.faces['top'][:, 2].copy()
            self.faces['top'][:, 2] = self.faces['back'][:, 0][::-1].copy()  
            self.faces['back'][:, 0] = self.faces['bottom'][:, 2][::-1].copy()  
            self.faces['bottom'][:, 2] = temp.copy()
    
    def move_L(self, clockwise=True):
        """Rotate the left face - Standard Rubik's cube L move"""
        self.move_history.append(('L', clockwise))
        
        if clockwise:
            # Rotate left face clockwise (fixed)
            self.faces['left'] = self.rotate_face_clockwise(self.faces['left'])
            
            # Correct L move (clockwise): front → top → back → bottom → front
            temp = self.faces['front'][:, 0].copy()
            self.faces['front'][:, 0] = self.faces['top'][:, 0].copy()
            self.faces['top'][:, 0] = self.faces['back'][:, 2][::-1].copy()  
            self.faces['back'][:, 2] = self.faces['bottom'][:, 0][::-1].copy()  
            self.faces['bottom'][:, 0] = temp.copy()
        else:
            # Rotate left face counterclockwise (fixed)
            self.faces['left'] = self.rotate_face_counterclockwise(self.faces['left'])
            
            # Correct L' move (counter-clockwise): front → bottom → back → top → front
            temp = self.faces['front'][:, 0].copy()
            self.faces['front'][:, 0] = self.faces['bottom'][:, 0].copy()
            self.faces['bottom'][:, 0] = self.faces['back'][:, 2][::-1].copy()  
            self.faces['back'][:, 2] = self.faces['top'][:, 0][::-1].copy()  
            self.faces['top'][:, 0] = temp.copy()
    
    def move_U(self, clockwise=True):
        """Rotate the upper (top) face - Standard Rubik's cube U move"""
        self.move_history.append(('U', clockwise))
        
        if clockwise:
            # Rotate top face clockwise (fixed)
            self.faces['top'] = self.rotate_face_clockwise(self.faces['top'])
            
            # U move (clockwise): front → right → back → left → front
            temp = self.faces['front'][0, :].copy()
            self.faces['front'][0, :] = self.faces['right'][0, :].copy()
            self.faces['right'][0, :] = self.faces['back'][0, :].copy()
            self.faces['back'][0, :] = self.faces['left'][0, :].copy()
            self.faces['left'][0, :] = temp.copy()
        else:
            # Rotate top face counterclockwise (fixed)
            self.faces['top'] = self.rotate_face_counterclockwise(self.faces['top'])
            
            # U' move (counter-clockwise): front → left → back → right → front
            temp = self.faces['front'][0, :].copy()
            self.faces['front'][0, :] = self.faces['left'][0, :].copy()
            self.faces['left'][0, :] = self.faces['back'][0, :].copy()
            self.faces['back'][0, :] = self.faces['right'][0, :].copy()
            self.faces['right'][0, :] = temp.copy()
    
    def move_D(self, clockwise=True):
        """Rotate the down (bottom) face - Standard Rubik's cube D move"""
        self.move_history.append(('D', clockwise))
        
        if clockwise:
            # Rotate bottom face clockwise (fixed)
            self.faces['bottom'] = self.rotate_face_clockwise(self.faces['bottom'])
            
            # D move (clockwise): front → left → back → right → front
            temp = self.faces['front'][2, :].copy()
            self.faces['front'][2, :] = self.faces['left'][2, :].copy()
            self.faces['left'][2, :] = self.faces['back'][2, :].copy()
            self.faces['back'][2, :] = self.faces['right'][2, :].copy()
            self.faces['right'][2, :] = temp.copy()
        else:
            # Rotate bottom face counterclockwise (fixed)
            self.faces['bottom'] = self.rotate_face_counterclockwise(self.faces['bottom'])
            
            # D' move (counter-clockwise): front → right → back → left → front
            temp = self.faces['front'][2, :].copy()
            self.faces['front'][2, :] = self.faces['right'][2, :].copy()
            self.faces['right'][2, :] = self.faces['back'][2, :].copy()
            self.faces['back'][2, :] = self.faces['left'][2, :].copy()
            self.faces['left'][2, :] = temp.copy()
    
    def move_F(self, clockwise=True):
        """Rotate the front face - Standard Rubik's cube F move"""
        self.move_history.append(('F', clockwise))
        
        if clockwise:
            # Rotate front face clockwise (fixed)
            self.faces['front'] = self.rotate_face_clockwise(self.faces['front'])
            
            # F move (clockwise): top → left → bottom → right → top
            temp = self.faces['top'][2, :].copy()
            self.faces['top'][2, :] = self.faces['left'][:, 2][::-1].copy()
            self.faces['left'][:, 2] = self.faces['bottom'][0, :].copy()
            self.faces['bottom'][0, :] = self.faces['right'][:, 0][::-1].copy()
            self.faces['right'][:, 0] = temp.copy()
        else:
            # Rotate front face counterclockwise (fixed)
            self.faces['front'] = self.rotate_face_counterclockwise(self.faces['front'])
            
            # F' move (counter-clockwise): top → right → bottom → left → top
            temp = self.faces['top'][2, :].copy()
            self.faces['top'][2, :] = self.faces['right'][:, 0].copy()
            self.faces['right'][:, 0] = self.faces['bottom'][0, :][::-1].copy()
            self.faces['bottom'][0, :] = self.faces['left'][:, 2].copy()
            self.faces['left'][:, 2] = temp[::-1].copy()
    
    def move_B(self, clockwise=True):
        """Rotate the back face - Standard Rubik's cube B move"""
        self.move_history.append(('B', clockwise))
        
        if clockwise:
            # Rotate back face clockwise (fixed)
            self.faces['back'] = self.rotate_face_clockwise(self.faces['back'])
            
            # B move (clockwise): top → right → bottom → left → top
            temp = self.faces['top'][0, :].copy()
            self.faces['top'][0, :] = self.faces['right'][:, 2].copy()
            self.faces['right'][:, 2] = self.faces['bottom'][2, :][::-1].copy()
            self.faces['bottom'][2, :] = self.faces['left'][:, 0].copy()
            self.faces['left'][:, 0] = temp[::-1].copy()
        else:
            # Rotate back face counterclockwise (fixed)
            self.faces['back'] = self.rotate_face_counterclockwise(self.faces['back'])
            
            # B' move (counter-clockwise): top → left → bottom → right → top
            temp = self.faces['top'][0, :].copy()
            self.faces['top'][0, :] = self.faces['left'][:, 0][::-1].copy()
            self.faces['left'][:, 0] = self.faces['bottom'][2, :].copy()
            self.faces['bottom'][2, :] = self.faces['right'][:, 2][::-1].copy()
            self.faces['right'][:, 2] = temp.copy()

    def move_M(self, clockwise=True):
        """Rotate the middle slice (M move) - between L and R faces"""
        self.move_history.append(('M', clockwise))
        
        if clockwise:
            # M move (clockwise when looking from R face): front → top → back → bottom → front
            # This affects the middle column (index 1) of front, top, back, bottom faces
            temp = self.faces['front'][:, 1].copy()
            self.faces['front'][:, 1] = self.faces['bottom'][:, 1].copy()
            self.faces['bottom'][:, 1] = self.faces['back'][:, 1][::-1].copy()
            self.faces['back'][:, 1] = self.faces['top'][:, 1][::-1].copy()
            self.faces['top'][:, 1] = temp.copy()
        else:
            # M' move (counter-clockwise): front → bottom → back → top → front
            temp = self.faces['front'][:, 1].copy()
            self.faces['front'][:, 1] = self.faces['top'][:, 1].copy()
            self.faces['top'][:, 1] = self.faces['back'][:, 1][::-1].copy()
            self.faces['back'][:, 1] = self.faces['bottom'][:, 1][::-1].copy()
            self.faces['bottom'][:, 1] = temp.copy()

    def move_E(self, clockwise=True):
        """Rotate the equatorial slice (E move) - between U and D faces"""
        self.move_history.append(('E', clockwise))
        
        if clockwise:
            # E move (clockwise when looking from D face): front → right → back → left → front
            # This affects the middle row (index 1) of front, left, back, right faces
            temp = self.faces['front'][1, :].copy()
            self.faces['front'][1, :] = self.faces['right'][1, :].copy()
            self.faces['right'][1, :] = self.faces['back'][1, :].copy()
            self.faces['back'][1, :] = self.faces['left'][1, :].copy()
            self.faces['left'][1, :] = temp.copy()
        else:
            # E' move (counter-clockwise): front → left → back → right → front
            temp = self.faces['front'][1, :].copy()
            self.faces['front'][1, :] = self.faces['left'][1, :].copy()
            self.faces['left'][1, :] = self.faces['back'][1, :].copy()
            self.faces['back'][1, :] = self.faces['right'][1, :].copy()
            self.faces['right'][1, :] = temp.copy()

    def move_S(self, clockwise=True):
        """Rotate the standing slice (S move) - between F and B faces"""
        self.move_history.append(('S', clockwise))
        
        if clockwise:
            # S move (clockwise when looking from F face): top → right → bottom → left → top
            # This affects the middle slice (index 1) of top, right, bottom, left faces
            temp = self.faces['top'][1, :].copy()
            self.faces['top'][1, :] = self.faces['right'][:, 1].copy()
            self.faces['right'][:, 1] = self.faces['bottom'][1, :][::-1].copy()
            self.faces['bottom'][1, :] = self.faces['left'][:, 1].copy()
            self.faces['left'][:, 1] = temp[::-1].copy()
        else:
            # S' move (counter-clockwise): top → left → bottom → right → top
            temp = self.faces['top'][1, :].copy()
            self.faces['top'][1, :] = self.faces['left'][:, 1][::-1].copy()
            self.faces['left'][:, 1] = self.faces['bottom'][1, :].copy()
            self.faces['bottom'][1, :] = self.faces['right'][:, 1][::-1].copy()
            self.faces['right'][:, 1] = temp.copy()
    
    def execute_move(self, move_notation):
        """Execute a move using standard Rubik's cube notation"""
        move_notation = move_notation.strip().upper()
        
        # Handle double moves (2)
        if move_notation.endswith('2'):
            base_move = move_notation[:-1]
            self.execute_move(base_move)
            self.execute_move(base_move)
            return
            
        # Handle wide moves (w)
        if move_notation.endswith('W') or move_notation.endswith("W'"):
            if move_notation.endswith("W'"):
                base_face = move_notation[:-2]
                clockwise = False
            else:
                base_face = move_notation[:-1]
                clockwise = True
            self._execute_wide_move(base_face, clockwise)
            return
        
        # Standard moves
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
        elif move_notation == 'M':
            self.move_M(True)
        elif move_notation == "M'":
            self.move_M(False)
        elif move_notation == 'E':
            self.move_E(True)
        elif move_notation == "E'":
            self.move_E(False)
        elif move_notation == 'S':
            self.move_S(True)
        elif move_notation == "S'":
            self.move_S(False)
        else:
            print(f"Unknown move: {move_notation}")
    
    def _execute_wide_move(self, face, clockwise=True):
        """Execute a wide move (face + middle slice)"""
        if face == 'R':
            self.move_R(clockwise)
            self.move_M(not clockwise)  # M moves opposite to R
        elif face == 'L':
            self.move_L(clockwise)
            self.move_M(clockwise)  # M moves same as L
        elif face == 'U':
            self.move_U(clockwise)
            self.move_E(not clockwise)  # E moves opposite to U
        elif face == 'D':
            self.move_D(clockwise)
            self.move_E(clockwise)  # E moves same as D
        elif face == 'F':
            self.move_F(clockwise)
            self.move_S(clockwise)  # S moves same as F
        elif face == 'B':
            self.move_B(clockwise)
            self.move_S(not clockwise)  # S moves opposite to B
    
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
        elif last_move == 'M':
            self.move_M(not was_clockwise)
        elif last_move == 'E':
            self.move_E(not was_clockwise)
        elif last_move == 'S':
            self.move_S(not was_clockwise)
        
        # Remove the undo move from history
        self.move_history.pop()
        return True
    
    def scramble(self, num_moves=20):
        """Scramble the cube with random moves"""
        import random
        moves = ['R', "R'", 'L', "L'", 'U', "U'", 'D', "D'", 'F', "F'", 'B', "B'", 'M', "M'", 'E', "E'", 'S', "S'"]
        
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