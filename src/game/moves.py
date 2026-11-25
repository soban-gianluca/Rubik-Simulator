import time
from src.rubiks_cube import RubiksCube


class MovesMixin:
    """Cube moves, undo and scrambling."""

    def can_make_move(self):
        """Check if the player is allowed to make a move (considering move limits)"""
        # Don't allow new moves while animating or if game is over
        if self.renderer.is_animating or self.game_over:
            return False
        
        # Allow moves during scrambling
        if hasattr(self, 'is_scrambling') and self.is_scrambling:
            return True
        
        # Check if cube is already solved
        if self.cube_solved:
            return False
        
        # Check move limit
        if self.move_limit is not None and self.move_counter >= self.move_limit:
            return False
        
        return True
    
    def execute_cube_move(self, move_notation):
        """Execute a Rubik's cube move with animation"""
        # Check if move is allowed before executing
        if not self.can_make_move():
            return
        
        # Check if this move matches the expected hint move
        hint_move_matches = False
        if self.hint_expanded and len(self.hint_moves_sequence) > 0:
            if self.hint_moves_completed < len(self.hint_moves_sequence):
                expected_move = self.hint_moves_sequence[self.hint_moves_completed]
                if move_notation == expected_move:
                    hint_move_matches = True
                    self.debug_print(f"Hint move matched! {move_notation}")
                else:
                    self.debug_print(f"Move {move_notation} doesn't match expected hint move {expected_move}")
        
        # Reset hint timer when making a move (pass whether it matched)
        self.reset_hint_timer(hint_move_matches)
        
        # Only start timer if not scrambling
        if not hasattr(self, 'is_scrambling') or not self.is_scrambling:
            if self.start_time is None:
                self.start_time = time.time()
        
        # Start animation first
        face_name = move_notation.replace("'", "") # FIX AND REMOVE THIS LINES
        clockwise = "'" not in move_notation
        
        if self.renderer.start_face_animation(face_name, clockwise):
            # Play random cube movement sound
            self.sound_manager.play_random_cube_sound()
            
            # Store the move to execute when animation completes
            self.renderer.pending_move = move_notation
            
            # Only increment move counter if not scrambling
            if not hasattr(self, 'is_scrambling') or not self.is_scrambling:
                self.move_counter += 1
                self.debug_print(f"Move {self.move_counter}: {move_notation} (animating)")
                
                # Check if we've reached the move limit after incrementing
                if (self.move_limit is not None and 
                    self.move_counter >= self.move_limit and 
                    not self.cube_solved):
                    # Show warning when reaching move limit
                    self.show_banner(f"Move limit reached ({self.move_counter} of {self.move_limit})")
            else:
                self.debug_print(f"Scramble move: {move_notation} (animating)")
    
    def undo_move(self):
        """Undo the last move"""
        # Don't allow undo if animating
        if self.renderer.is_animating:
            return
        
        # Allow undo in limited moves mode even when limit is reached (gives player a chance to recover)
        # But don't allow undo if game is over for other reasons (time limit, etc.)
        if self.game_over and hasattr(self, 'game_over_reason') and self.game_over_reason != "moves_exceeded":
            self.debug_print("Cannot undo: Game is over")
            return
        
        if self.renderer.rubiks_cube.undo_last_move():
            # Play random cube movement sound for undo
            self.sound_manager.play_random_cube_sound()
            if self.move_limit is not None and self.move_counter >= self.move_limit:
                self.undo_at_limit = True
            self.enqueue_achievement_notifications(self.achievements_manager.record_undo())

            self.renderer.update_cube_colors()
            self.move_counter = max(0, self.move_counter - 1)
            self.debug_print(f"Move undone. Move count: {self.move_counter}")
            
            # If we were in game over state due to move limit, reset it since we now have moves available
            if (self.game_over and hasattr(self, 'game_over_reason') and 
                self.game_over_reason == "moves_exceeded" and 
                self.move_limit is not None and self.move_counter < self.move_limit):
                self.game_over = False
                self.game_over_reason = None
                # Close results window if it's open
                if self.results_window.active:
                    self.results_window.close_results()
                self.show_banner(f"Undo gave you a move back ({self.move_counter} of {self.move_limit})")
        else:
            self.debug_print("No moves to undo")
    
    def scramble_cube(self):
        """Scramble the cube"""
        # Play a cube sound for scrambling
        self.sound_manager.play_random_cube_sound()
        
        self.renderer.rubiks_cube.scramble(25)
        self.renderer.update_cube_colors()
        self.move_counter = 0
        self.start_time = None
        self.cube_solved = False
        self.debug_print("Cube scrambled!")
        
        # Record scramble for achievements and show notifications if any unlocked
        newly_unlocked = self.achievements_manager.record_scramble()
        if newly_unlocked:
            self.enqueue_achievement_notifications(newly_unlocked, delay_seconds=0.0)
    
    def animated_scramble_cube(self, num_moves):
        """Scramble the cube with animated moves for visual effect"""
        import random
        
        # Available moves for scrambling
        moves = ['R', "R'", 'L', "L'", 'U', "U'", 'D', "D'", 'F', "F'", 'B', "B'", 'M', "M'", 'E', "E'", 'S', "S'"]
        
        # Generate the scramble sequence. Consecutive moves never share an axis, so they
        # cannot cancel each other out (R R', R L R' L') and leave the cube solved.
        axis = {'R': 'x', 'L': 'x', 'M': 'x', 'U': 'y', 'D': 'y', 'E': 'y', 'F': 'z', 'B': 'z', 'S': 'z'}
        scramble_sequence = []
        for _ in range(num_moves):
            last_axis = axis[scramble_sequence[-1][0]] if scramble_sequence else None
            move = random.choice([m for m in moves if axis[m[0]] != last_axis])
            scramble_sequence.append(move)

        # Store original animation duration (unless a scramble is already running) and scramble faster
        if not hasattr(self, 'original_animation_duration'):
            self.original_animation_duration = self.renderer.animation_duration
        self.renderer.animation_duration = 0.1  # Faster animation (100ms instead of 300ms)
        
        # Store the scramble sequence for animated execution
        self.scramble_queue = scramble_sequence.copy()
        self.is_scrambling = True
        self.scramble_start_time = time.time()
        
        self.debug_print(f"Starting fast animated scramble with {num_moves} moves: {' '.join(scramble_sequence)}")
    
    def animated_daily_scramble_cube(self, num_moves=20):
        """Scramble the cube with the daily deterministic scramble (animated).
        All players get the same scramble for the current UTC date."""
        
        # Get the daily scramble sequence from the cube
        scramble_sequence = self.renderer.rubiks_cube.get_daily_scramble_sequence(num_moves)
        
        # Store original animation duration (unless a scramble is already running) and scramble faster
        if not hasattr(self, 'original_animation_duration'):
            self.original_animation_duration = self.renderer.animation_duration
        self.renderer.animation_duration = 0.1  # Faster animation (100ms instead of 300ms)

        # Store the scramble sequence for animated execution
        self.scramble_queue = scramble_sequence.copy()
        self.is_scrambling = True
        self.scramble_start_time = time.time()

        self.debug_print(f"Starting daily scramble with {num_moves} moves: {' '.join(scramble_sequence)}")
    
    def update_animated_scramble(self):
        """Update the animated scrambling process"""
        if not hasattr(self, 'is_scrambling') or not self.is_scrambling:
            return
        
        # Don't execute next move if animation is still running
        if self.renderer.is_animating:
            return
        
        # Check if we have more moves to execute
        if hasattr(self, 'scramble_queue') and self.scramble_queue:
            # Execute the next move
            next_move = self.scramble_queue.pop(0)
            self.execute_cube_move(next_move)
            self.debug_print(f"Scramble move: {next_move} ({len(self.scramble_queue)} moves remaining)")
        else:
            # Scrambling complete
            self.is_scrambling = False
            self.move_counter = 0  # Reset move counter after scrambling
            self.start_time = None  # Reset timer
            
            # Restore original animation duration
            if hasattr(self, 'original_animation_duration'):
                self.renderer.animation_duration = self.original_animation_duration
                delattr(self, 'original_animation_duration')
            
            self.debug_print("Fast animated scrambling complete!")
            
            # Clear move history to prevent undoing scramble moves
            if hasattr(self.renderer.rubiks_cube, 'move_history'):
                self.renderer.rubiks_cube.move_history.clear()
    
    # Idle shuffle shown behind the main menu before the first mode is picked
    MENU_SHUFFLE_TURN_DURATION = 0.7  # seconds per face turn
    MENU_SHUFFLE_PAUSE = 0.6  # seconds between turns

    def update_menu_idle_shuffle(self):
        """Slowly mix the solved cube with random turns while the main menu waits for a mode."""
        if self.renderer.is_animating:
            return
        now = time.time()
        if not getattr(self, '_menu_shuffle_active', False):
            # First call: the cube is still solved, give a moment before the first turn
            self._menu_shuffle_active = True
            self._menu_shuffle_saved_duration = self.renderer.animation_duration
            self._menu_shuffle_last_axis = None
            self._menu_shuffle_next_time = now + 1.5
            return
        if now < self._menu_shuffle_next_time:
            return

        import random
        axis = {'R': 'x', 'L': 'x', 'M': 'x', 'U': 'y', 'D': 'y', 'E': 'y', 'F': 'z', 'B': 'z', 'S': 'z'}
        faces = [f for f in axis if axis[f] != self._menu_shuffle_last_axis]
        face = random.choice(faces)
        clockwise = random.random() < 0.5
        self._menu_shuffle_last_axis = axis[face]

        self.renderer.animation_duration = self.MENU_SHUFFLE_TURN_DURATION
        if self.renderer.start_face_animation(face, clockwise):
            self.renderer.pending_move = face if clockwise else face + "'"
        self._menu_shuffle_next_time = now + self.MENU_SHUFFLE_TURN_DURATION + self.MENU_SHUFFLE_PAUSE

    def stop_menu_idle_shuffle(self):
        """End the menu shuffle and restore the normal turn speed."""
        if not getattr(self, '_menu_shuffle_active', False):
            return
        self._menu_shuffle_active = False
        self.renderer.animation_duration = self._menu_shuffle_saved_duration

    def scramble_cube_by_difficulty(self, difficulty):
        """Scramble the cube based on difficulty level"""
        # Play a cube sound for scrambling
        self.sound_manager.play_random_cube_sound()
        
        # Get difficulty configuration from menu
        game_mode_config = self.menu.get_game_mode_config(difficulty)
        
        # Drop any move still animating from the previous game, so it is not applied to the new cube
        self.renderer.is_animating = False
        self.renderer.pending_move = None
        self.renderer.animating_face = None
        self.renderer.animation_cubes = []
        self.scramble_queue = []

        # ALWAYS reset the cube to solved state first before applying any difficulty-specific scrambling
        self.renderer.rubiks_cube = RubiksCube()
        self.debug_print("Cube reset to solved state")
        
        # A new game: no hint opened and no undo at the move limit yet
        self.hint_used_this_game = False
        self.undo_at_limit = False

        # Reset challenge mode variables
        self.time_limit = None
        self.move_limit = None
        self.game_over = False
        self.game_over_reason = None
        
        # Reset hint system
        self.hint_banner_active = False
        self.hint_expanded = False
        self.hint_banner_alpha = 0.0
        self.hint_current_suggestion = None
        self.last_move_time = time.time()
        
        # Reset visual hint (3D arrow) state
        self.show_visual_hint = False
        self.visual_hint_face = None
        self.hint_moves_sequence = []
        self.hint_moves_completed = 0
        with self._solution_lock:
            self._cached_solution_moves = None
        
        # Set up challenge limits based on game mode
        if "time_limit" in game_mode_config:
            self.time_limit = game_mode_config["time_limit"]
            self.debug_print(f"Time limit set to {self.time_limit} seconds")
        
        if "move_limit" in game_mode_config:
            self.move_limit = game_mode_config["move_limit"]
            self.debug_print(f"Move limit set to {self.move_limit} moves")
        
        if difficulty == "freeplay":
            # Free play: Keep cube solved (no scrambling)
            self.debug_print("Free play mode: Cube ready for practice!")
        elif difficulty == "easy":
            # Easy: 5 moves scramble
            self.animated_scramble_cube(5)
            self.debug_print("Easy mode: Scramble with 5 moves!")
        elif difficulty == "medium":
            # Medium: 10 moves scramble
            self.animated_scramble_cube(10)
            self.debug_print("Medium mode: Scramble with 10 moves!")
        elif difficulty == "hard":
            # Hard: Random scramble with >30 moves
            import random
            scramble_moves = random.randint(30, 70)  # Generate random number between 30-70
            self.animated_scramble_cube(scramble_moves)
            self.debug_print(f"Hard mode: Completely random scramble!")
        elif difficulty == "limited_time":
            # Limited Time: Medium scramble with time pressure
            self.animated_scramble_cube(15)
            self.debug_print(f"Limited Time mode: Scramble with 15 moves!")
        elif difficulty == "limited_moves":
            # Limited Moves: Medium scramble with move restriction
            self.animated_scramble_cube(15)
            self.debug_print(f"Limited Moves mode: Scramble with 15 moves!")
        elif difficulty == "daily_cube":
            # Daily Cube: Same scramble for all players today
            self.animated_daily_scramble_cube(20)
            self.debug_print(f"Daily Cube mode: Using today's daily scramble!")
        else:
            # Default case (fallback)
            self.animated_scramble_cube(20)
            self.debug_print(f"Unknown difficulty '{difficulty}', using default animated scramble!")
        
        # Update cube colors and reset game state
        self.renderer.update_cube_colors()
        self.move_counter = 0
        self.start_time = None
        self.cube_solved = False
