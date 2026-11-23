import pygame
import time
import random
from src import ui_style as ui


class ResultsWindow:
    """Result card shown after a solve or a failed challenge."""

    RATING_LABELS = {
        "LEGENDARY!": "Legendary solve",
        "EXCELLENT!": "Excellent solve",
        "GREAT!": "Great solve",
        "GOOD!": "Good solve",
        "COMPLETED!": "Solved",
    }

    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height

        # Set from the game instance
        self.sound_manager = None
        self.personal_best_manager = None
        self.achievements_manager = None
        self.game_callback = None

        # Window state
        self.active = False
        self.results_data = {}
        self.opened_at = 0.0

        # Buttons: (action, label, variant); rects are computed while drawing
        self.buttons = [("play_again", "Play again", "primary"), ("main_menu", "Main menu", "secondary")]
        self.button_rects = {}
        self.hovered = None
        self.focused = 0
        self.keyboard_focus = False

        # Confetti made of cube facelets
        self.particles = []
        self.celebration_active = False
        self.celebration_start_time = 0

    # ------------------------------------------------------------ showing
    def show_results(self, moves, solve_time, tps=None, difficulty=None):
        """Display the results for a solved cube and start the celebration"""
        new_records = {}
        if self.personal_best_manager and difficulty and difficulty != "freeplay":
            new_records = self.personal_best_manager.update_record(
                difficulty, solve_time, moves, tps or (moves / solve_time if solve_time > 0 else 0)
            )

        newly_unlocked_achievements = []
        if self.achievements_manager and difficulty and difficulty != "freeplay":
            newly_unlocked_achievements = self.achievements_manager.record_solve(difficulty, solve_time, moves)

        self.results_data = {
            'moves': moves,
            'time': solve_time,
            'tps': tps or (moves / solve_time if solve_time > 0 else 0),
            'difficulty': difficulty,
            'new_records': new_records,
            'newly_unlocked_achievements': newly_unlocked_achievements
        }

        self._start_celebration()
        if self.sound_manager:
            self.sound_manager.play_with_music_duck("winning")
        self._open()

    def show_game_over(self, moves, solve_time, reason="time_up", difficulty=None):
        """Display the game over card for failed challenges"""
        if self.personal_best_manager and difficulty and difficulty in ["limited_time", "limited_moves"]:
            self.personal_best_manager.record_loss(difficulty, moves, solve_time)

        self.results_data = {
            'moves': moves,
            'time': solve_time,
            'tps': moves / solve_time if solve_time > 0 else 0,
            'difficulty': difficulty,
            'game_over': True,
            'reason': reason,
            'new_records': {}
        }

        if self.sound_manager:
            self.sound_manager.play_with_music_duck("fail")
        self.celebration_active = False
        self.particles = []
        self._open()

    def _open(self):
        self.active = True
        self.opened_at = time.time()
        self.focused = 0
        self.keyboard_focus = False
        self.hovered = None

    def calculate_performance_rating(self, moves, solve_time):
        """Rate a solve from its move count and time"""
        if moves <= 15:
            if solve_time <= 20:
                return "LEGENDARY!"
            elif solve_time <= 45:
                return "EXCELLENT!"
            return "GREAT!"
        elif moves <= 25:
            if solve_time <= 30:
                return "EXCELLENT!"
            elif solve_time <= 60:
                return "GREAT!"
            return "GOOD!"
        elif moves <= 40:
            if solve_time <= 60:
                return "GREAT!"
            elif solve_time <= 120:
                return "GOOD!"
            return "COMPLETED!"
        elif moves <= 70:
            if solve_time <= 120:
                return "GOOD!"
            return "COMPLETED!"
        return "COMPLETED!"

    # ------------------------------------------------------------ actions
    def _activate(self, action):
        self.close_results()
        if self.game_callback:
            self.game_callback(action)

    def play_again(self):
        self._activate('play_again')

    def to_main_menu(self):
        self._activate('main_menu')

    def close_results(self):
        """Close the results window immediately"""
        self.active = False
        self.celebration_active = False
        self.particles = []
        self.hovered = None

    def toggle(self):
        if self.active:
            self.close_results()
        else:
            self.active = True

    # ------------------------------------------------------------ input
    def handle_events(self, events):
        if not self.active:
            return
        for event in events:
            if event.type == pygame.MOUSEMOTION:
                self.keyboard_focus = False
                self.hovered = self._button_at(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                action = self._button_at(event.pos)
                if action:
                    if self.sound_manager:
                        self.sound_manager.play("menu_select")
                    self._activate(action)
                    return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._activate('main_menu')
                    return
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
                    if self.keyboard_focus:
                        self.focused = (self.focused + 1) % len(self.buttons)
                    self.keyboard_focus = True
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self._activate(self.buttons[self.focused][0])
                    return

    def _button_at(self, pos):
        for action, rect in self.button_rects.items():
            if rect.collidepoint(pos):
                return action
        return None

    def update_cursor(self, mouse_pos):
        if not self.active:
            return
        cursor = pygame.SYSTEM_CURSOR_HAND if self._button_at(mouse_pos) else pygame.SYSTEM_CURSOR_ARROW
        pygame.mouse.set_cursor(cursor)

    # ------------------------------------------------------------ effects
    def _start_celebration(self):
        self.celebration_active = True
        self.celebration_start_time = time.time()
        self.particles = [self._make_particle() for _ in range(70)]

    def _make_particle(self):
        s = ui.scale()
        return {
            'x': self.width / 2 + random.uniform(-0.12, 0.12) * self.width,
            'y': self.height * 0.3,
            'vx': random.uniform(-9, 9) * s,
            'vy': random.uniform(-17, -6) * s,
            'gravity': 0.35 * s,
            'color': random.choice(list(ui.FACE.values())),
            'size': random.uniform(7, 14) * s,
            'rotation': random.uniform(0, 360),
            'spin': random.uniform(-8, 8),
            'life': 1.0,
            'decay': random.uniform(0.006, 0.012),
        }

    def update(self):
        if not self.celebration_active:
            return
        for p in self.particles[:]:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vx'] *= 0.99
            p['vy'] += p['gravity']
            p['rotation'] += p['spin']
            p['life'] -= p['decay']
            if p['life'] <= 0 or p['y'] > self.height + 40:
                self.particles.remove(p)
        if not self.particles:
            self.celebration_active = False

    def _draw_particles(self, surface):
        for p in self.particles:
            size = max(2, int(p['size']))
            piece = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.rect(piece, (*p['color'], int(255 * max(0.0, min(1.0, p['life'] * 1.5)))),
                             piece.get_rect(), border_radius=max(1, size // 4))
            rotated = pygame.transform.rotate(piece, p['rotation'])
            surface.blit(rotated, rotated.get_rect(center=(int(p['x']), int(p['y']))))

    # ------------------------------------------------------------ drawing
    def get_current_alpha(self):
        return 1.0 if self.active else 0.0

    def render_to_surface(self, surface):
        if not self.active:
            return
        data = self.results_data or {}
        w, h = self.width, self.height
        failed = data.get('game_over', False)

        t = min(1.0, (time.time() - self.opened_at) / 0.24)
        ease = 1 - (1 - t) ** 3

        # Scrim over the game, the cube stays visible behind it
        scrim = pygame.Surface((w, h), pygame.SRCALPHA)
        scrim.fill((*ui.BG, int(190 * ease)))
        surface.blit(scrim, (0, 0))

        if self.celebration_active:
            self._draw_particles(surface)

        pad = ui.px(48)
        card_w = min(ui.px(760), w - ui.px(48))
        inner_w = card_w - pad * 2

        f_title = ui.display_font(ui.SIZE_DISPLAY)
        f_sub = ui.body_font(ui.SIZE_BODY)
        f_label = ui.body_font(ui.SIZE_SMALL)
        f_value = ui.mono_font(ui.SIZE_H2, bold=True)
        f_note = ui.body_font(ui.SIZE_SMALL, bold=True)

        # Content
        difficulty = data.get('difficulty') or ""
        mode_name = ui.MODE_NAMES.get(difficulty, difficulty.replace("_", " ").title())
        if failed:
            reason = data.get('reason')
            title = {"time_up": "Out of time", "moves_exceeded": "Out of moves"}.get(reason, "Game over")
            title_color = ui.DANGER
            subtitle = f"{mode_name}  ·  Challenge failed"
            notes = []
        else:
            title = "Solved"
            title_color = ui.TEXT
            rating = self.calculate_performance_rating(data.get('moves', 0), data.get('time', 0))
            subtitle = f"{mode_name}  ·  {self.RATING_LABELS.get(rating, 'Solved')}"
            records = data.get('new_records') or {}
            notes = [label for key, label in (("is_best_time", "New best time"),
                                              ("is_best_moves", "New fewest moves"),
                                              ("is_best_tps", "New best TPS")) if records.get(key)]

        stats = [("Time", ui.format_clock(data.get('time', 0), decimals=True)),
                 ("Moves", str(data.get('moves', 0))),
                 ("TPS", f"{data.get('tps', 0):.2f}")]

        # Measure
        title_h = f_title.get_height()
        stat_h = f_label.get_height() + ui.px(6) + f_value.get_height() + ui.px(36)
        note_h = (f_note.get_height() + ui.px(14)) if notes else 0
        btn_h = ui.px(60)
        card_h = (pad + title_h - ui.px(10) + f_sub.get_height() + ui.px(32) + stat_h + ui.px(24)
                  + note_h + btn_h + pad)

        card = pygame.Rect(0, 0, card_w, card_h)
        card.center = (w // 2, h // 2 + int((1 - ease) * ui.px(28)))

        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        ui.panel(layer, card, fill=ui.SURFACE, border=ui.LINE, rad=ui.radius(16))

        # Mode color edge on top of the card
        mode_color = ui.MODE_COLORS.get(difficulty, ui.ACCENT)
        ui.fill_rect(layer, mode_color, (card.x + pad, card.y, ui.px(72), ui.px(5)), ui.px(2))

        x, y = card.x + pad, card.y + pad
        ui.draw_text(layer, title, f_title, title_color, (x, y - ui.px(6)))
        y += title_h - ui.px(10)
        ui.draw_text(layer, subtitle, f_sub, ui.MUTED, (x, y))
        y += f_sub.get_height() + ui.px(32)

        # Stats in three columns separated by hairlines
        col_w = inner_w // 3
        box = pygame.Rect(x, y, inner_w, stat_h)
        ui.fill_rect(layer, ui.SURFACE_2, box, ui.radius(12))
        for i, (label, value) in enumerate(stats):
            cx = x + col_w * i + ui.px(22)
            ui.draw_text(layer, label, f_label, ui.MUTED, (cx, y + ui.px(18)))
            ui.draw_text(layer, value, f_value, ui.TEXT, (cx, y + ui.px(18) + f_label.get_height() + ui.px(6)))
            if i:
                lx = x + col_w * i
                pygame.draw.line(layer, ui.LINE, (lx, y + ui.px(16)), (lx, y + stat_h - ui.px(16)), max(1, ui.px(1.5)))
        y += stat_h + ui.px(24)

        if notes:
            nx = x
            for note in notes:
                r = ui.draw_text(layer, note, f_note, ui.ACCENT, (nx, y))
                nx = r.right + ui.px(24)
            y += note_h

        # Buttons
        gap = ui.px(16)
        bw = (inner_w - gap) // 2
        self.button_rects = {}
        for i, (action, label, variant) in enumerate(self.buttons):
            rect = pygame.Rect(x + i * (bw + gap), y, bw, btn_h)
            self.button_rects[action] = rect
            ui.button(layer, rect, label, variant=variant,
                      hovered=(self.hovered == action),
                      focused=(self.keyboard_focus and self.focused == i))

        layer.set_alpha(int(255 * ease))
        surface.blit(layer, (0, 0))

    # ------------------------------------------------------------ wiring
    def set_game_callback(self, callback):
        self.game_callback = callback

    def update_dimensions(self, new_width, new_height):
        """Keep the card centered after a resolution change"""
        self.width = new_width
        self.height = new_height
        self.button_rects = {}

    def set_sound_manager(self, sound_manager):
        self.sound_manager = sound_manager

    def set_personal_best_manager(self, personal_best_manager):
        self.personal_best_manager = personal_best_manager

    def set_achievements_manager(self, achievements_manager):
        self.achievements_manager = achievements_manager
