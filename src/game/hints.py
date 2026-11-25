import pygame
import time
import threading
from src.ui import ui_style as ui
from utils.path_helper import resource_path
from src import solver
from src.pykociemba.cubiecube import moveCube
from src.pykociemba.facecube import FaceCube


class HintsMixin:
    """Move suggestions: the Kociemba solver, the hint banner and the 3D hint arrow."""

    def _cube_to_facelets(self, cube=None):
        """Convert current `RubiksCube` state to a facelet string for pykociemba.

        CRITICAL FIX: The scramble includes slice moves (M, E, S) which move centers.
        We must map based on WHICH PHYSICAL FACE each sticker is on, not the color value.
        """
        c = cube if cube is not None else self.renderer.rubiks_cube

        # Read the center color of each physical face to determine orientation
        center_top = int(c.faces['top'][1, 1])
        center_right = int(c.faces['right'][1, 1])
        center_front = int(c.faces['front'][1, 1])
        center_bottom = int(c.faces['bottom'][1, 1])
        center_left = int(c.faces['left'][1, 1])
        center_back = int(c.faces['back'][1, 1])
        
        # Create color mapping based on current center positions
        # Map: color_value -> which face letter it represents
        color_to_face = {}
        color_to_face[center_top] = 'U'
        color_to_face[center_right] = 'R'
        color_to_face[center_front] = 'F'
        color_to_face[center_bottom] = 'D'
        color_to_face[center_left] = 'L'
        color_to_face[center_back] = 'B'
        
        result = []
        
        # Read each face in the order expected by pykociemba: U, R, F, D, L, B
        for face_name in ['top', 'right', 'front', 'bottom', 'left', 'back']:
            for row in range(3):
                for col in range(3):
                    color_idx = int(c.faces[face_name][row, col])
                    result.append(color_to_face[color_idx])
        
        facelet_str = ''.join(result)
        return facelet_str

    def suggest_next_move_threaded(self):
        """Wrapper to call suggest_next_move in a background thread safely."""
        try:
            self.solver_is_running = True
            self.suggest_next_move()
        finally:
            self.solver_is_running = False

    def suggest_next_move(self):
        """Compute a full solution using pykociemba and print the next move to terminal.

        This validates the solution using pykociemba's own move semantics to ensure
        the suggestion is correct and will actually solve the cube.
        """
        try:
            # Don't run during animations or scrambles
            if getattr(self.renderer, 'is_animating', False) or getattr(self, 'is_scrambling', False):
                print("Please wait for animations/scramble to finish before requesting a suggestion.")
                return None

            # Build facelet string from current cube state
            facelets = self._cube_to_facelets()

            # Diagnostic: verify it's a solved cube if we think it should be
            if self.renderer.rubiks_cube.is_solved():
                expected_solved = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"
                if facelets != expected_solved:
                    print(f"WARNING: Cube reports as solved but facelet string doesn't match!")
                    print(f"Expected: {expected_solved}")
                    print(f"Got:      {facelets}")

            # Call solver (in its own process, see src/solver.py)
            solution = solver.solve(facelets)

            if solution.startswith('Error'):
                print(f"Solver error: {solution}")
                print(f"Facelet string: {facelets}")
                print(f"Cube is_solved: {self.renderer.rubiks_cube.is_solved()}")
                return None

            solution = solution.strip()
            if not solution:
                print("Cube already solved — no moves needed.")
                return None
            try:
                # Convert current cube state to CubieCube using pykociemba's parser
                test_cubie = FaceCube(facelets).toCubieCube()

                # Apply each move using pykociemba's moveCube table (not RubiksCube.execute_move!)
                # moveCube indices: 0=U, 1=R, 2=F, 3=D, 4=L, 5=B
                move_map = {
                    'U': 0, "U'": 0, 'U2': 0,
                    'R': 1, "R'": 1, 'R2': 1,
                    'F': 2, "F'": 2, 'F2': 2,
                    'D': 3, "D'": 3, 'D2': 3,
                    'L': 4, "L'": 4, 'L2': 4,
                    'B': 5, "B'": 5, 'B2': 5,
                }

                for move_str in solution.split():
                    if move_str not in move_map:
                        print(f"Unknown move in solution: {move_str}")
                        return None

                    move_idx = move_map[move_str]

                    # Apply the move 1, 2, or 3 times depending on notation
                    if move_str.endswith('2'):
                        test_cubie.multiply(moveCube[move_idx])
                        test_cubie.multiply(moveCube[move_idx])
                    elif move_str.endswith("'"):
                        # Prime = 3 times clockwise
                        test_cubie.multiply(moveCube[move_idx])
                        test_cubie.multiply(moveCube[move_idx])
                        test_cubie.multiply(moveCube[move_idx])
                    else:
                        # Normal = 1 time
                        test_cubie.multiply(moveCube[move_idx])

                # Check if solved by converting back to facelet and checking all same
                result_fc = test_cubie.toFaceCube()
                result_str = result_fc.to_String()

                # A solved cube has all U's in positions 0-8, all R's in 9-17, etc.
                is_solved = (
                    all(result_str[i] == 'U' for i in range(9)) and
                    all(result_str[i] == 'R' for i in range(9, 18)) and
                    all(result_str[i] == 'F' for i in range(18, 27)) and
                    all(result_str[i] == 'D' for i in range(27, 36)) and
                    all(result_str[i] == 'L' for i in range(36, 45)) and
                    all(result_str[i] == 'B' for i in range(45, 54))
                )

                if not is_solved:
                    print(f"Solver produced solution that doesn't solve the cube when validated with pykociemba moves. Rejecting.")
                    print(f"Input facelets: {facelets}")
                    print(f"Solution: {solution}")
                    print(f"Result after applying: {result_str}")
                    return None

            except Exception as e:
                print(f"Error validating solution: {e}")
                return None

            # First token (space separated) is the next move
            first_move = solution.split()[0]
            print(f"Suggested next move: {first_move}  (Full solution: {solution})")
            return first_move
        except Exception as e:
            print(f"Error computing suggestion: {e}")
            return None

    def _load_hint_icons(self):
        """Load hint and close button icons"""
        try:
            # Load hint icon
            self.hint_icon = pygame.image.load(resource_path("utils/icons/hint.png"))
            self.hint_icon = pygame.transform.smoothscale(self.hint_icon, (32, 32))
        except Exception as e:
            print(f"Could not load hint icon: {e}")
            self.hint_icon = None
        
        try:
            # Load close icon
            self.close_icon = pygame.image.load(resource_path("utils/icons/close.png"))
            self.close_icon = pygame.transform.smoothscale(self.close_icon, (24, 24))
        except Exception as e:
            print(f"Could not load close icon: {e}")
            self.close_icon = None

    def reset_hint_timer(self, hint_move_matched=False):
        """Reset the hint inactivity timer - called when user makes a move
        
        Args:
            hint_move_matched: True if the move matched the expected hint move
        """
        self.last_move_time = time.time()
        
        # Clear cached solution since cube state changed
        with self._solution_lock:
            self._cached_solution_moves = None
        
        # Hide hint banner if visible
        if self.hint_banner_active and not self.hint_expanded:
            self.hint_banner_active = False
            self.hint_banner_alpha = 0.0
        
        # Update visual hint only if the move matched the hint suggestion
        if self.hint_expanded and len(self.hint_moves_sequence) > 0 and hint_move_matched:
            self.hint_moves_completed += 1
            self.debug_print(f"Hint moves completed: {self.hint_moves_completed}/{len(self.hint_moves_sequence)}")
            
            # Check if all hint moves are completed
            if self.hint_moves_completed >= len(self.hint_moves_sequence):
                self.debug_print("All hint moves completed! Closing popup.")
                self.close_hint_popup()
            else:
                # Update to show next move
                self._enable_visual_hint()

    def update_hint_system(self):
        """Update the hint system - check for inactivity and manage hint display"""
        if not self.hints_enabled:
            return
        
        # Don't show hints in menu, results screen, during scrambling, or when cube is solved
        if (self.menu.is_active() or 
            self.results_window.active or 
            (hasattr(self, 'is_scrambling') and self.is_scrambling) or 
            self.cube_solved or
            self.game_over or
            not self.game_started):
            return
        
        # Don't show hints in freeplay, limited_time, or limited_moves modes
        current_difficulty = self.menu.get_selected_difficulty()
        if current_difficulty in ["freeplay", "limited_time", "limited_moves"]:
            return
        
        current_time = time.time()
        
        # Check for inactivity
        if not self.hint_banner_active and not self.hint_expanded:
            time_since_last_move = current_time - self.last_move_time
            if time_since_last_move >= self.hint_inactivity_threshold:
                # Show hint banner
                self.hint_banner_active = True
                self.hint_banner_start_time = current_time
                self.hint_banner_alpha = 0.0
                self.debug_print("Showing hint banner due to inactivity")
                
                # Play hint sound effect
                self.sound_manager.play("hint")
                
                # Start precomputing solution in background
                self._precompute_solution()
        
        # Update hint banner fade-in animation
        if self.hint_banner_active and not self.hint_expanded:
            elapsed = current_time - self.hint_banner_start_time
            if elapsed < self.hint_banner_fade_in_time:
                self.hint_banner_alpha = elapsed / self.hint_banner_fade_in_time
            else:
                self.hint_banner_alpha = 1.0
        
        # Update expanded hint if solution becomes available
        if self.hint_expanded and self.hint_current_suggestion and "Analyzing the cube" in self.hint_current_suggestion:
            with self._solution_lock:
                if self._cached_solution_moves and not self._solution_computing:
                    # Solution is now available, update the hint
                    solution_moves = self._cached_solution_moves
                    
                    # Expand moves to handle double moves
                    expanded_moves = []
                    for move in solution_moves:
                        if '2' in move:
                            base_move = move.replace('2', '')
                            expanded_moves.append(base_move)
                            expanded_moves.append(base_move)
                        else:
                            expanded_moves.append(move)
                        if len(expanded_moves) >= 3:
                            break
                    
                    self.hint_moves_sequence = expanded_moves[:3]
                    self.hint_moves_completed = 0
                    self.hint_current_suggestion = self._format_hint_suggestion(solution_moves)
                    
                    # Enable visual hint now that we have moves
                    if self.hint_moves_sequence:
                        self._enable_visual_hint()
                    
                    self.debug_print("Hint updated with computed solution")
    
    def _precompute_solution(self):
        """Precompute the solution in a background thread"""
        with self._solution_lock:
            # Don't start multiple computation threads
            if self._solution_computing:
                return
            self._solution_computing = True
        
        def compute():
            try:
                # Compute solution
                solution = self._get_solution_moves()
                with self._solution_lock:
                    self._cached_solution_moves = solution
                    self._solution_computing = False
                self.debug_print("Solution precomputed in background")
            except Exception as e:
                self.debug_print(f"Error precomputing solution: {e}")
                with self._solution_lock:
                    self._solution_computing = False
        
        # Start background thread
        thread = threading.Thread(target=compute, daemon=True)
        thread.start()

    def show_hint_expanded(self):
        """Show the expanded hint popup with algorithm suggestion"""
        self.hint_expanded = True
        self.hint_banner_active = False
        self.hint_used_this_game = True
        
        # Use cached solution (should be ready from background precomputation)
        # If not ready yet, show loading message
        with self._solution_lock:
            solution_moves = self._cached_solution_moves
            is_computing = self._solution_computing
        
        if solution_moves:
            # Determine number of hint moves based on difficulty
            current_difficulty = self.menu.get_selected_difficulty()
            hint_move_counts = {
                "easy": 1,
                "medium": 2,
                "hard": 5
            }
            max_hint_moves = hint_move_counts.get(current_difficulty, 3)  # Default to 3 if not found
            
            # Expand moves to handle double moves (B2 -> B, B)
            expanded_moves = []
            for move in solution_moves:
                if '2' in move:
                    # Double move - add it twice
                    base_move = move.replace('2', '')
                    expanded_moves.append(base_move)
                    expanded_moves.append(base_move)
                else:
                    expanded_moves.append(move)
                
                # Stop after we have enough moves
                if len(expanded_moves) >= max_hint_moves:
                    break
            
            self.hint_moves_sequence = expanded_moves[:max_hint_moves]  # Store hint moves based on difficulty
            self.hint_moves_completed = 0
            
            # Get the hint suggestion with cached solution
            self.hint_current_suggestion = self._format_hint_suggestion(solution_moves)
        elif is_computing:
            # Still computing in background
            self.hint_moves_sequence = []
            self.hint_moves_completed = 0
            self.hint_current_suggestion = "Analyzing the cube\nOne moment while the solver works."
        else:
            # No solution available
            self.hint_moves_sequence = []
            self.hint_moves_completed = 0
            self.hint_current_suggestion = "Try analyzing the cube pattern..."
        
        self.debug_print(f"Showing expanded hint: {self.hint_current_suggestion}")
        
        # Enable visual hint with first move (only if we have moves)
        if self.hint_moves_sequence:
            self._enable_visual_hint()

    def close_hint_popup(self):
        """Close the hint popup and reset the timer"""
        self.hint_expanded = False
        self.hint_banner_active = False
        self.hint_banner_alpha = 0.0
        self.hint_current_suggestion = None
        self.last_move_time = time.time()  # Reset timer so hint doesn't immediately reappear
        
        # Disable visual hint and clear tracking
        self.show_visual_hint = False
        self.visual_hint_face = None
        self.hint_moves_sequence = []
        self.hint_moves_completed = 0
        
        # Clear cached solution since hint is closed
        with self._solution_lock:
            self._cached_solution_moves = None

    def _format_hint_suggestion(self, solution_moves):
        """Format hint suggestion from pre-computed solution moves"""
        import random
        
        # Phrases to make hints more engaging
        hint_phrases = [
            "Have you tried using",
            "Maybe you should try",
            "Consider performing",
            "How about doing",
            "Try executing",
            "You could use",
            "Perhaps attempt"
        ]
        
        # Format the solution moves
        if solution_moves:
            try:
                # Determine number of hint moves based on difficulty
                current_difficulty = self.menu.get_selected_difficulty()
                hint_move_counts = {
                    "easy": 1,
                    "medium": 2,
                    "hard": 5
                }
                max_hint_moves = hint_move_counts.get(current_difficulty, 3)  # Default to 3 if not found
                
                # Get first few moves for display based on difficulty
                display_moves = []
                move_count = 0
                
                for move in solution_moves:
                    display_moves.append(move)
                    # Count actual move steps (B2 counts as 2 steps)
                    if '2' in move:
                        move_count += 2
                    else:
                        move_count += 1
                    
                    # Stop when we have enough moves based on difficulty
                    if move_count >= max_hint_moves:
                        break
                
                # Limit display moves based on difficulty
                display_moves = display_moves[:max_hint_moves]
                moves_str = " ".join(display_moves)
                
                phrase = random.choice(hint_phrases)
                
                # Add explanation about the visual arrow
                first_move = display_moves[0]
                direction = "clockwise" if "'" not in first_move else "counterclockwise"
                face_name = self._get_face_name(first_move[0])
                
                return f"{phrase} these moves:\n{moves_str}\n\nWatch the {face_name} face. The yellow arrow shows a {direction} turn."
            except Exception as e:
                self.debug_print(f"Error formatting hint: {e}")
        
        # Fallback generic hints
        generic_hints = [
            "Try solving the white cross first",
            "Focus on the first layer corners",
            "Work on the middle layer edges",
            "Look for patterns in the last layer",
            "Try the R U R' U' algorithm",
            "Consider rotating the cube to see it from different angles"
        ]
        return random.choice(generic_hints)
    
    def _enable_visual_hint(self):
        """Enable visual hint by parsing the current move from the hint sequence"""
        try:
            # Use stored hint sequence if available
            if len(self.hint_moves_sequence) > 0 and self.hint_moves_completed < len(self.hint_moves_sequence):
                current_move = self.hint_moves_sequence[self.hint_moves_completed]
                
                # Parse the move (e.g., "R", "L'", "U2", etc.)
                face = current_move[0]  # First character is the face
                clockwise = "'" not in current_move  # Prime moves are counterclockwise
                
                # Enable visual hint
                self.show_visual_hint = True
                self.visual_hint_face = face
                self.visual_hint_clockwise = clockwise
                self.visual_hint_pulse_time = time.time()
                
                self.debug_print(f"Visual hint enabled: {current_move} - {face} {'clockwise' if clockwise else 'counterclockwise'}")
            else:
                self.show_visual_hint = False
        except Exception as e:
            self.debug_print(f"Error enabling visual hint: {e}")
            self.show_visual_hint = False
    
    def _get_face_name(self, face_letter):
        """Convert face letter to readable name"""
        face_names = {
            'R': 'Right',
            'L': 'Left',
            'U': 'Top',
            'D': 'Bottom',
            'F': 'Front',
            'B': 'Back',
            'M': 'Middle',
            'E': 'Equatorial',
            'S': 'Standing'
        }
        return face_names.get(face_letter, face_letter)
    
    def _get_solution_moves(self):
        """Get the solution moves from the solver as a list"""
        try:
            # Don't run during animations or scrambles
            if getattr(self.renderer, 'is_animating', False) or getattr(self, 'is_scrambling', False):
                return None

            # Build facelet string from current cube state
            facelets = self._cube_to_facelets()

            # Call solver (in its own process, see src/solver.py)
            solution = solver.solve(facelets)

            if solution.startswith('Error'):
                self.debug_print(f"Solver error: {solution}")
                return None

            solution = solution.strip()
            if not solution:
                return None

            # Return list of moves
            return solution.split()
        except Exception as e:
            self.debug_print(f"Error getting solution: {e}")
            return None

    def handle_hint_click(self, mouse_pos):
        """Handle click on hint banner/popup. Returns True if click was handled."""
        # Check if clicking on expanded popup's close button
        if self.hint_expanded and self.hint_close_rect:
            if self.hint_close_rect.collidepoint(mouse_pos):
                self.close_hint_popup()
                return True
        
        # Check if clicking on small hint banner's close button
        if self.hint_banner_active and not self.hint_expanded and hasattr(self, 'hint_banner_close_rect'):
            if self.hint_banner_close_rect.collidepoint(mouse_pos):
                self.close_hint_popup()
                return True
        
        # Check if clicking on small hint banner (to expand it)
        if self.hint_banner_active and not self.hint_expanded and self.hint_banner_rect:
            if self.hint_banner_rect.collidepoint(mouse_pos):
                self.show_hint_expanded()
                return True
        
        return False

    def _render_hint_system(self):
        """Render hint pill or expanded hint panel"""
        try:
            if self.hint_expanded:
                self._render_expanded_hint()
            elif self.hint_banner_active:
                self._render_small_hint_banner()
        except Exception as e:
            if self.debug_mode:
                print(f"Hint system rendering error: {e}")

    def _close_button(self, surf, rect):
        ui.fill_rect(surf, ui.SURFACE_2, rect, ui.radius(8))
        ic = ui.icon("close", int(rect.width * 0.55), ui.MUTED)
        if ic:
            surf.blit(ic, ic.get_rect(center=rect.center))

    def _render_small_hint_banner(self):
        """Pill asking whether the player wants a hint"""
        a = max(0.0, min(1.0, self.hint_banner_alpha))
        fnt = ui.body_font(ui.SIZE_BODY, bold=True)
        text = fnt.render("Need a hint?", True, ui.TEXT)
        action = ui.body_font(ui.SIZE_SMALL, bold=True).render("Show me", True, ui.ON_ACCENT)
        icon_size = ui.px(28)
        close = ui.px(36)
        pad = ui.px(14)
        pill_h = max(text.get_height(), close) + pad * 2
        action_w = action.get_width() + ui.px(28)
        width = pad + icon_size + ui.px(12) + text.get_width() + ui.px(20) + action_w + ui.px(10) + close + pad
        surf = pygame.Surface((width, pill_h), pygame.SRCALPHA)
        ui.fill_rect(surf, (*ui.SURFACE, 245), surf.get_rect(), ui.radius(14))
        ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(14), width=max(1, ui.px(1.5)))

        x = pad
        ic = ui.icon("hint", icon_size, ui.ACCENT)
        if ic:
            surf.blit(ic, (x, (pill_h - icon_size) // 2))
        x += icon_size + ui.px(12)
        surf.blit(text, (x, (pill_h - text.get_height()) // 2))
        x += text.get_width() + ui.px(20)
        btn = pygame.Rect(x, (pill_h - close) // 2, action_w, close)
        ui.fill_rect(surf, ui.ACCENT, btn, ui.radius(8))
        surf.blit(action, action.get_rect(center=btn.center))
        close_local = pygame.Rect(btn.right + ui.px(10), (pill_h - close) // 2, close, close)
        self._close_button(surf, close_local)

        bx = (self.width - width) // 2
        by = self._hud_margin()
        self.hint_banner_rect = pygame.Rect(bx, by, close_local.x - ui.px(4), pill_h)
        self.hint_banner_close_rect = close_local.move(bx, by)
        self._hint_bottom = by + pill_h
        surf.set_alpha(int(255 * a))
        self._blit_gl(surf, bx, by)

    def _render_expanded_hint(self):
        """Panel with the suggested moves"""
        import re
        hint_text = self.hint_current_suggestion or "Try analyzing the cube pattern"
        lines = hint_text.split('\n')
        width = min(ui.px(600), self.width - ui.px(48))
        pad = ui.px(24)
        inner = width - pad * 2
        title_f = ui.display_font(ui.SIZE_H3)
        body_f = ui.body_font(ui.SIZE_BODY)
        muted_f = ui.body_font(ui.SIZE_SMALL)
        moves_f = ui.mono_font(ui.SIZE_H2, bold=True)
        move_re = re.compile(r"^[RLUDFBMES]['2]?$")

        # Lay out content first to size the panel
        blocks = []
        for i, line in enumerate(lines):
            tokens = line.split()
            if i == 1 and tokens and all(move_re.match(t) for t in tokens):
                blocks.append(("moves", line))
            elif not line.strip():
                blocks.append(("gap", ""))
            else:
                f = body_f if i == 0 else muted_f
                for wrapped in ui.wrap(line, f, inner):
                    blocks.append(("body" if i == 0 else "muted", wrapped))

        close = ui.px(36)
        header_h = max(title_f.get_height(), close)
        height = pad + header_h + ui.px(14)
        for kind, _ in blocks:
            height += {"moves": moves_f.get_height() + ui.px(16), "gap": ui.px(8),
                       "body": body_f.get_linesize(), "muted": muted_f.get_linesize()}[kind]
        if self.hint_moves_sequence:
            height += muted_f.get_linesize() + ui.px(6)
        height += pad

        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        ui.fill_rect(surf, (*ui.SURFACE, 248), surf.get_rect(), ui.radius(16))
        ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(16), width=max(1, ui.px(1.5)))
        ui.fill_rect(surf, ui.ACCENT, (pad, 0, ui.px(64), ui.px(4)), ui.px(2))

        icon_size = ui.px(28)
        ic = ui.icon("hint", icon_size, ui.ACCENT)
        x = pad
        if ic:
            surf.blit(ic, (x, pad + (header_h - icon_size) // 2))
            x += icon_size + ui.px(12)
        ui.draw_text(surf, "Hint", title_f, ui.TEXT, (x, pad + header_h // 2 + ui.px(2)), "midleft")
        close_local = pygame.Rect(width - pad - close, pad + (header_h - close) // 2, close, close)
        self._close_button(surf, close_local)

        y = pad + header_h + ui.px(14)
        for kind, text in blocks:
            if kind == "moves":
                # Highlight the move the player should do next
                done = self.hint_moves_completed
                cx = pad
                for ti, tok in enumerate(text.split()):
                    color = ui.ACCENT if ti == done else (ui.DIM if ti < done else ui.TEXT)
                    r = ui.draw_text(surf, tok, moves_f, color, (cx, y + ui.px(4)))
                    cx = r.right + ui.px(18)
                y += moves_f.get_height() + ui.px(16)
            elif kind == "gap":
                y += ui.px(8)
            elif kind == "body":
                ui.draw_text(surf, text, body_f, ui.TEXT, (pad, y))
                y += body_f.get_linesize()
            else:
                ui.draw_text(surf, text, muted_f, ui.MUTED, (pad, y))
                y += muted_f.get_linesize()
        if self.hint_moves_sequence:
            step = min(self.hint_moves_completed + 1, len(self.hint_moves_sequence))
            ui.draw_text(surf, f"Step {step} of {len(self.hint_moves_sequence)}", muted_f, ui.DIM, (pad, y + ui.px(6)))

        px_, py_ = (self.width - width) // 2, self._hud_margin()
        self.hint_close_rect = close_local.move(px_, py_)
        self._hint_bottom = py_ + height
        self._blit_gl(surf, px_, py_)
