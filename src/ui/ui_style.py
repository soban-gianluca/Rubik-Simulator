"""Design tokens and drawing primitives shared by every 2D screen.

All sizes are authored for a 1920x1080 reference screen and scaled with
``px()`` / ``fs()`` so the UI keeps its proportions at any resolution and
aspect ratio (16:9, 16:10, 4:3, ultrawide).
"""
import math

import pygame
import pygame_menu

from utils.path_helper import resource_path

# ---------------------------------------------------------------- colors
BG = (13, 16, 20)
SURFACE = (22, 26, 32)
SURFACE_2 = (30, 35, 43)
SURFACE_3 = (41, 47, 57)
LINE = (46, 53, 64)
TEXT = (236, 238, 241)
MUTED = (150, 158, 170)
DIM = (98, 106, 118)
ACCENT = (255, 210, 63)
ON_ACCENT = (24, 20, 8)

FACE = {
    "white": (238, 238, 232),
    "yellow": (255, 210, 63),
    "red": (229, 72, 77),
    "orange": (242, 140, 40),
    "blue": (59, 130, 246),
    "green": (47, 179, 106),
}
SUCCESS = FACE["green"]
DANGER = FACE["red"]

MODE_COLORS = {
    "freeplay": FACE["white"],
    "easy": FACE["green"],
    "medium": FACE["orange"],
    "hard": FACE["red"],
    "limited_time": FACE["yellow"],
    "limited_moves": FACE["blue"],
    "daily_cube": FACE["yellow"],
}

MODE_NAMES = {
    "freeplay": "Free Play",
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
    "limited_time": "Limited Time",
    "limited_moves": "Limited Moves",
    "daily_cube": "Daily Cube",
}

# Lucide icon per mode (utils/icons/modes): growth to peak to fire for the difficulty ladder
MODE_ICONS = {
    "freeplay": "infinity",
    "easy": "circle-check-big",
    "medium": "mountain",
    "hard": "flame",
    "limited_time": "timer",
    "limited_moves": "arrow-right-left",
    "daily_cube": "calendar-days",
}

# ---------------------------------------------------------------- fonts
FONT_DISPLAY = pygame_menu.font.FONT_BEBAS
FONT_BODY = pygame_menu.font.FONT_OPEN_SANS
FONT_BODY_BOLD = pygame_menu.font.FONT_OPEN_SANS_BOLD
FONT_MONO = pygame_menu.font.FONT_FIRACODE
FONT_MONO_BOLD = pygame_menu.font.FONT_FIRACODE_BOLD

# Type scale in reference pixels (1080p)
SIZE_DISPLAY = 112
SIZE_H1 = 64
SIZE_H2 = 44
SIZE_H3 = 32
SIZE_BODY = 24
SIZE_SMALL = 20
SIZE_CAPTION = 17

MIN_FONT_PX = 13

# ---------------------------------------------------------------- scaling
REFERENCE_SIZE = (1920, 1080)
_scale = 1.0
_screen = REFERENCE_SIZE


def set_screen(width, height):
    """Recompute the global UI scale for a new window size."""
    global _scale, _screen
    _screen = (int(width), int(height))
    _scale = max(0.45, min(width / REFERENCE_SIZE[0], height / REFERENCE_SIZE[1]))


def scale():
    return _scale


def screen_size():
    return _screen


def px(value):
    """Scale a reference-pixel length to the current screen."""
    return max(1, int(round(value * _scale)))


def fs(value):
    """Scale a font size, with a floor that keeps text readable."""
    return max(MIN_FONT_PX, int(round(value * _scale)))


_font_cache = {}


def font(path, size):
    key = (path, size)
    f = _font_cache.get(key)
    if f is None:
        try:
            f = pygame.font.Font(path, size)
        except Exception:
            f = pygame.font.SysFont("arial", size)
        _font_cache[key] = f
    return f


_display_font_ids = set()


def display_font(ref_size):
    f = font(FONT_DISPLAY, fs(ref_size))
    _display_font_ids.add(id(f))
    return f


def body_font(ref_size=SIZE_BODY, bold=False):
    return font(FONT_BODY_BOLD if bold else FONT_BODY, fs(ref_size))


def mono_font(ref_size=SIZE_BODY, bold=False):
    return font(FONT_MONO_BOLD if bold else FONT_MONO, fs(ref_size))


# ---------------------------------------------------------------- icons
_icon_cache = {}


def icon(name, size, color=TEXT):
    """Load a white line icon from utils/icons and tint it."""
    key = (name, size, tuple(color))
    surf = _icon_cache.get(key)
    if surf is not None:
        return surf
    try:
        base = pygame.image.load(resource_path(f"utils/icons/{name}.png"))
        try:
            base = base.convert_alpha()
        except pygame.error:
            pass
        surf = pygame.transform.smoothscale(base, (size, size))
        tint = pygame.Surface((size, size), pygame.SRCALPHA)
        tint.fill((*color[:3], 255))
        surf.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    except Exception:
        surf = None
    _icon_cache[key] = surf
    return surf


def mode_icon(mode, size, color=None):
    """Lucide icon of a game mode, tinted with the mode color by default."""
    return icon("modes/" + MODE_ICONS.get(mode, "infinity"), size, color or MODE_COLORS.get(mode, ACCENT))


def clear_caches():
    _icon_cache.clear()
    _logo_cache.clear()


# ---------------------------------------------------------------- text
def _render_display(text, fnt, color):
    """Bebas has a hairline word space and a loose apostrophe: space words
    properly and pull the apostrophe in."""
    h = fnt.get_height()
    word_gap = int(h * 0.2)
    kern = -int(h * 0.06)
    pieces = []  # (surface, x offset before it)
    for wi, word in enumerate(text.split(" ")):
        parts = word.split("'")
        for pi, part in enumerate(parts):
            if pi:
                pieces.append((fnt.render("'", True, color), kern))
            if part:
                pieces.append((fnt.render(part, True, color), kern if pi else (word_gap if wi and pi == 0 else 0)))
            elif pi == 0 and wi:
                pieces.append((None, word_gap))
    width = max(1, sum(max(0, (s.get_width() if s else 0) + off) for s, off in pieces))
    surf = pygame.Surface((width, h), pygame.SRCALPHA)
    x = 0
    for s, off in pieces:
        x += off
        if s:
            surf.blit(s, (x, 0))
            x += s.get_width()
    return surf


def render(text, fnt, color):
    text = str(text)
    if id(fnt) in _display_font_ids and (" " in text or "'" in text):
        return _render_display(text, fnt, color)
    return fnt.render(text, True, color)


def text_width(text, fnt):
    return render(text, fnt, TEXT).get_width() if id(fnt) in _display_font_ids else fnt.size(str(text))[0]


def draw_text(surface, text, fnt, color, pos, anchor="topleft", alpha=255):
    surf = render(text, fnt, color)
    if alpha < 255:
        surf.set_alpha(alpha)
    rect = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(surf, rect)
    return rect


def ellipsize(text, fnt, max_width):
    text = str(text)
    if fnt.size(text)[0] <= max_width:
        return text
    while text and fnt.size(text + "...")[0] > max_width:
        text = text[:-1]
    return text.rstrip() + "..."


def wrap(text, fnt, max_width):
    """Greedy word wrap. Returns a list of lines."""
    lines = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split(" ")
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if text_width(candidate, fnt) <= max_width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


# ---------------------------------------------------------------- shapes
def radius(ref=10):
    return max(2, px(ref))


def fill_rect(surface, color, rect, rad=0, width=0):
    """Draw a (rounded) rect. Colors with alpha are blended, not copied."""
    rect = pygame.Rect(rect)
    if rect.width <= 0 or rect.height <= 0:
        return
    if len(color) == 4 and color[3] < 255:
        tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(tmp, color, tmp.get_rect(), width, border_radius=rad)
        surface.blit(tmp, rect.topleft)
    else:
        pygame.draw.rect(surface, color[:3], rect, width, border_radius=rad)


def panel(surface, rect, fill=SURFACE, border=LINE, rad=None):
    rad = radius(12) if rad is None else rad
    fill_rect(surface, fill, rect, rad)
    if border:
        fill_rect(surface, border, rect, rad, width=max(1, px(1.5)))


def focus_ring(surface, rect, rad=None, color=ACCENT):
    rad = radius(12) if rad is None else rad
    gap = max(2, px(3))
    ring = pygame.Rect(rect).inflate(gap * 2, gap * 2)
    fill_rect(surface, color, ring, rad + gap, width=max(2, px(2)))


def progress_bar(surface, rect, value, color=ACCENT, track=SURFACE_3):
    rect = pygame.Rect(rect)
    rad = rect.height // 2
    fill_rect(surface, track, rect, rad)
    value = max(0.0, min(1.0, float(value)))
    if value > 0:
        w = max(rect.height, int(rect.width * value))
        fill_rect(surface, color, (rect.x, rect.y, w, rect.height), rad)


def button(surface, rect, label, variant="secondary", hovered=False, focused=False,
           disabled=False, icon_name=None, ref_font=SIZE_BODY, align="center"):
    """Draw a button. Variants: primary, secondary, ghost, danger."""
    rect = pygame.Rect(rect)
    rad = radius(10)
    if disabled:
        fill, border, fg = SURFACE_2, None, DIM
    elif variant == "primary":
        fill = (255, 222, 110) if hovered else ACCENT
        border, fg = None, ON_ACCENT
    elif variant == "danger":
        fill = (240, 96, 100) if hovered else DANGER
        border, fg = None, (255, 255, 255)
    elif variant == "ghost":
        fill = SURFACE_2 if hovered else None
        border, fg = None, TEXT
    else:
        fill = SURFACE_3 if hovered else SURFACE_2
        border, fg = LINE, TEXT
    if fill:
        fill_rect(surface, fill, rect, rad)
    if border:
        fill_rect(surface, border, rect, rad, width=max(1, px(1.5)))
    if focused and not disabled:
        focus_ring(surface, rect, rad)

    fnt = body_font(ref_font, bold=True)
    text = render(label, fnt, fg)
    ic = icon(icon_name, fs(ref_font) + px(2), fg) if icon_name else None
    gap = px(10)
    content_w = text.get_width() + (ic.get_width() + gap if ic else 0)
    if align == "left":
        x = rect.x + px(20)
    else:
        x = rect.centerx - content_w // 2
    if ic:
        surface.blit(ic, (x, rect.centery - ic.get_height() // 2))
        x += ic.get_width() + gap
    surface.blit(text, (x, rect.centery - text.get_height() // 2))


def keycap(surface, x, y, label, fnt=None):
    """Draw a keyboard key chip. Returns its width."""
    fnt = fnt or mono_font(SIZE_SMALL, bold=True)
    t = render(label, fnt, TEXT)
    pad_x, pad_y = px(10), px(5)
    rect = pygame.Rect(x, y, max(t.get_width() + pad_x * 2, t.get_height() + pad_y * 2),
                       t.get_height() + pad_y * 2)
    fill_rect(surface, SURFACE_3, rect, radius(6))
    fill_rect(surface, LINE, rect, radius(6), width=max(1, px(1.5)))
    surface.blit(t, t.get_rect(center=rect.center))
    return rect.width


# ---------------------------------------------------------------- signature: cube mark
_COS30 = math.cos(math.radians(30))


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _face_cell(o, u, v, i, j, n, inset):
    """Quad for cell (i, j) of a parallelogram face with origin o and edges u, v."""
    def p(a, b):
        return (o[0] + u[0] * a + v[0] * b, o[1] + u[1] * a + v[1] * b)
    a0, a1 = (i + inset) / n, (i + 1 - inset) / n
    b0, b1 = (j + inset) / n, (j + 1 - inset) / n
    return [p(a0, b0), p(a1, b0), p(a1, b1), p(a0, b1)]


def cube_mark(surface, center, size, colors=None, lit=27, body=BG):
    """Isometric 3x3 cube. ``lit`` facelets (0-27) are colored, the rest dim.

    ``size`` is the length of one cube edge in pixels.
    """
    cx, cy = center
    a = size
    dx, dy = a * _COS30, a / 2
    top = (cx, cy - a)
    right = (cx + dx, cy - dy)
    left = (cx - dx, cy - dy)
    mid = (cx, cy)
    bottom = (cx, cy + a)
    bl = (cx - dx, cy + dy)
    br = (cx + dx, cy + dy)

    outline = [top, right, br, bottom, bl, left]
    pad = max(1.5, a * 0.05)
    grown = []
    for x, y in outline:
        vx, vy = x - cx, y - cy
        d = math.hypot(vx, vy) or 1
        grown.append((x + vx / d * pad, y + vy / d * pad))
    pygame.draw.polygon(surface, body, grown)

    colors = colors or (FACE["white"], FACE["green"], FACE["red"])
    faces = [
        (left, (top[0] - left[0], top[1] - left[1]), (mid[0] - left[0], mid[1] - left[1]), colors[0]),
        (left, (mid[0] - left[0], mid[1] - left[1]), (bl[0] - left[0], bl[1] - left[1]), colors[1]),
        (mid, (right[0] - mid[0], right[1] - mid[1]), (bottom[0] - mid[0], bottom[1] - mid[1]), colors[2]),
    ]
    k = 0
    inset = 0.09
    for o, u, v, col in faces:
        for j in range(3):
            for i in range(3):
                quad = _face_cell(o, u, v, i, j, 3, inset)
                c = col if k < lit else SURFACE_3
                pygame.draw.polygon(surface, c, quad)
                k += 1


_logo_cache = {}


def logo(name, max_width, max_height):
    """Load a logo from utils/ and scale it to fit the box, keeping its aspect ratio."""
    key = (name, int(max_width), int(max_height))
    surf = _logo_cache.get(key)
    if surf is None:
        try:
            base = pygame.image.load(resource_path(f"utils/{name}.png"))
            try:
                base = base.convert_alpha()
            except pygame.error:
                pass
            k = min(max_width / base.get_width(), max_height / base.get_height())
            size = (max(1, int(base.get_width() * k)), max(1, int(base.get_height() * k)))
            surf = pygame.transform.smoothscale(base, size)
        except Exception as e:
            print(f"Logo {name} not found: {e}")
            surf = None
        _logo_cache[key] = surf
    return surf


def format_clock(seconds, decimals=False):
    seconds = max(0.0, float(seconds))
    m = int(seconds // 60)
    s = seconds - m * 60
    if decimals:
        return f"{m}:{s:05.2f}" if m else f"{s:.2f}"
    return f"{m:02d}:{int(s):02d}"


def aspect_label(w, h):
    r = w / h
    for name, value in (("16:9", 16 / 9), ("16:10", 16 / 10), ("4:3", 4 / 3), ("5:4", 5 / 4),
                        ("21:9", 21 / 9), ("32:9", 32 / 9), ("3:2", 3 / 2), ("5:3", 5 / 3)):
        if abs(r - value) < 0.03:
            return name
    if 2.3 < r < 2.45:
        return "21:9"
    return f"{r:.2f}:1"
