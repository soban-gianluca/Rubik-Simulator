"""Monitor detection, resolution lists and window creation.

Display modes:
- windowed:   a regular window at a chosen resolution that fits the monitor
- borderless: a frameless window covering the whole monitor at its native resolution
- fullscreen: exclusive fullscreen at any resolution the monitor reports
"""
import os
import sys

import pygame
from pygame.locals import DOUBLEBUF, OPENGL, FULLSCREEN, NOFRAME

MODES = ("windowed", "borderless", "fullscreen")
MODE_LABELS = {"windowed": "Windowed", "borderless": "Borderless", "fullscreen": "Fullscreen"}

MIN_SIZE = (1024, 600)

# Common window sizes, offered in windowed mode in addition to the monitor's own modes
COMMON_SIZES = [
    (1024, 576), (1024, 640), (1024, 768), (1152, 648), (1280, 720), (1280, 800), (1280, 1024),
    (1366, 768), (1440, 900), (1536, 864), (1600, 900), (1600, 1000), (1680, 1050),
    (1920, 1080), (1920, 1200), (2048, 1152), (2560, 1080), (2560, 1440), (2560, 1600),
    (2880, 1620), (3200, 1800), (3440, 1440), (3840, 2160),
]

# Space a window needs for its title bar and the taskbar
WINDOW_CHROME = (16, 88)


def enable_dpi_awareness():
    """Ask Windows for real pixel sizes, so 125%/150% display scaling does not
    blur the window or hide resolutions. Must run before the first window."""
    if sys.platform != "win32":
        return
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def num_displays():
    try:
        return max(1, pygame.display.get_num_displays())
    except pygame.error:
        return 1


def desktop_size(display_index=0):
    try:
        sizes = pygame.display.get_desktop_sizes()
        if 0 <= display_index < len(sizes):
            return tuple(sizes[display_index])
    except pygame.error:
        pass
    info = pygame.display.Info()
    return (info.current_w, info.current_h)


def _fits(size, minimum=MIN_SIZE):
    return size[0] >= minimum[0] and size[1] >= minimum[1]


def _sorted(sizes):
    return sorted(set(sizes), key=lambda s: (s[0], s[1]), reverse=True)


def fullscreen_resolutions(display_index=0):
    try:
        modes = pygame.display.list_modes(0, FULLSCREEN, display_index)
    except (pygame.error, TypeError):
        modes = pygame.display.list_modes()
    if not isinstance(modes, list):  # -1 means "any size"
        modes = []
    sizes = [tuple(m) for m in modes if _fits(m)]
    native = desktop_size(display_index)
    sizes.append(native)
    return _sorted(sizes)


def windowed_resolutions(display_index=0):
    dw, dh = desktop_size(display_index)
    max_w, max_h = dw - WINDOW_CHROME[0], dh - WINDOW_CHROME[1]
    candidates = set(COMMON_SIZES) | set(fullscreen_resolutions(display_index))
    sizes = [s for s in candidates if _fits(s) and s[0] <= max_w and s[1] <= max_h]
    if not sizes:
        # Tiny monitor: offer the largest window that still fits
        sizes = [(max(640, max_w), max(480, max_h))]
    return _sorted(sizes)


def resolutions_for(mode, display_index=0):
    if mode == "borderless":
        return [desktop_size(display_index)]
    if mode == "fullscreen":
        return fullscreen_resolutions(display_index)
    return windowed_resolutions(display_index)


def default_window_size(display_index=0):
    """Largest window with the monitor's aspect ratio that uses about 75% of its width."""
    dw, dh = desktop_size(display_index)
    options = windowed_resolutions(display_index)
    target_ratio = dw / dh
    good = [s for s in options if s[0] <= dw * 0.78 and abs(s[0] / s[1] - target_ratio) < 0.04]
    if good:
        return good[0]
    good = [s for s in options if s[0] <= dw * 0.78]
    return good[0] if good else options[-1]


def nearest(size, options):
    """Pick the option closest to ``size`` (prefers same aspect ratio)."""
    if size in options:
        return size
    ratio = size[0] / max(1, size[1])

    def cost(o):
        return abs(o[0] - size[0]) + abs(o[1] - size[1]) + abs(o[0] / o[1] - ratio) * 4000
    return min(options, key=cost)


def resolve(settings):
    """Turn saved settings into a valid (mode, display_index, size) for this machine."""
    mode = settings.get("display_mode")
    if mode not in MODES:
        mode = "fullscreen" if settings.get("fullscreen") else "windowed"
    index = int(settings.get("display_index", 0) or 0)
    if not 0 <= index < num_displays():
        index = 0

    res = settings.get("resolution") or {}
    size = (int(res.get("width", 0) or 0), int(res.get("height", 0) or 0))

    if mode == "borderless":
        return mode, index, desktop_size(index)

    options = resolutions_for(mode, index)
    if size[0] <= 0 or size[1] <= 0:
        size = default_window_size(index) if mode == "windowed" else desktop_size(index)
    elif size not in options:
        dw, dh = desktop_size(index)
        fits_monitor = size[0] <= dw - WINDOW_CHROME[0] and size[1] <= dh - WINDOW_CHROME[1]
        if mode == "windowed" and fits_monitor and _fits(size):
            pass  # any window that fits the monitor is fine
        else:
            size = nearest(size, options)
    return mode, index, size


def open_window(mode, display_index, size, hdr=False):
    """Create (or recreate) the OpenGL window. Returns the display surface.

    ``hdr`` requests a 16-bit float framebuffer (see src/hdr.py); if the driver
    refuses it, a normal window is created instead.
    """
    from src import hdr as hdr_output

    flags = DOUBLEBUF | OPENGL
    os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
    os.environ["SDL_VIDEO_CENTERED"] = "1"
    if mode == "fullscreen":
        flags |= FULLSCREEN
    elif mode == "borderless":
        flags |= NOFRAME
        w, h = desktop_size(display_index)
        # A frameless window that exactly covers the monitor is promoted to exclusive
        # fullscreen by the graphics driver (black flash, HDR switches off). One extra
        # pixel row, off the bottom of the screen, keeps it a normal desktop window.
        size = (w, h + 1)

    def create(with_hdr):
        hdr_output.request_framebuffer(with_hdr)
        try:
            return pygame.display.set_mode(size, flags, display=display_index)
        except TypeError:
            return pygame.display.set_mode(size, flags)

    if hdr:
        try:
            return create(True)
        except pygame.error as e:
            print(f"HDR window not available, using a standard window: {e}")
    return create(False)


def display_label(index):
    w, h = desktop_size(index)
    return f"Monitor {index + 1}  ({w} x {h})"
