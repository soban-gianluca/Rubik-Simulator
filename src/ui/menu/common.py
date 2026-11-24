"""Constants and helpers shared by the menu modules."""
import functools

import pygame

from src.managers.user_manager import REGIONS
from src.ui import ui_style as ui

# Leaderboard filter options
GAME_MODE_OPTIONS = ["All Modes", "easy", "medium", "hard", "limited_time", "limited_moves"]
GAME_MODE_DISPLAY = {
    "All Modes": "All modes",
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
    "limited_time": "Limited Time",
    "limited_moves": "Limited Moves"
}
REGION_OPTIONS = ["All Regions"] + REGIONS
REGION_DISPLAY = {"All Regions": "All regions"}

NAV_KEYS = (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB)

# Animation timing (seconds)
OPEN_DURATION = 0.26
CLOSE_DURATION = 0.18
PAGE_DURATION = 0.30
ITEM_DELAY = 0.05      # first main menu item starts after the panel begins to slide
ITEM_STAGGER = 0.035   # delay between consecutive main menu items
ITEM_DURATION = 0.32


def _ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _batched(menu_of):
    """Build a page with layout paused, then lay it out once.

    pygame-menu lays out the whole page again after every widget it adds, so a
    page with a few hundred widgets took about a second to build.
    """
    def decorate(build):
        @functools.wraps(build)
        def wrapper(self, *args, **kwargs):
            menu = menu_of(self, *args)
            self._unbuilt.pop(menu, None)
            depth = getattr(menu, "_batch_depth", 0)
            if depth == 0:
                if menu.get_scrollarea().get_world() is None:
                    menu.render()  # dropdowns need a laid out page to exist (cheap while empty)
                menu.disable_render()
            menu._batch_depth = depth + 1
            try:
                return build(self, *args, **kwargs)
            finally:
                menu._batch_depth = depth
                if depth == 0:
                    menu.enable_render()
                    menu.render()
                    # A rebuilt page of the same size reuses the old drawn surface:
                    # without this the previous content stays on screen until a scroll
                    menu.force_surface_cache_update()
        return wrapper
    return decorate


def _first_arg(self, menu, *args):
    return menu


class _Layout:
    """Screen geometry for the current resolution."""

    def __init__(self, width, height):
        ui.set_screen(width, height)
        self.width, self.height = width, height
        self.margin = max(ui.px(32), int(width * 0.035))
        self.header_h = ui.px(124)
        self.sb_space = max(8, ui.px(16))
        self.content_w = min(ui.px(1180), width - 2 * self.margin - 2 * self.sb_space)
        self.content_x = (width - self.content_w) // 2
        self.panel_w = max(min(int(width * 0.33), ui.px(620)), min(ui.px(440), int(width * 0.45)))
        self.panel_pad = ui.px(48)
        self.gap = ui.px(20)
