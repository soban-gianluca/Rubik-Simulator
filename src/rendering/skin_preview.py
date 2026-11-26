"""Still previews of cube skins for the customization page.

A small software rasterizer draws an isometric 3x3 cube with numpy, evaluating the same
sticker patterns as the cube shader (Renderer._CUBE_FRAG) at time zero, so a preview looks
like the cube in game without needing the OpenGL context.
"""
import math

import numpy as np
import pygame

from src import cube_skins
from src.rubiks_cube import RubiksCube

# Facelet color indices shown on the preview (top, left, right faces; 9 each): a scrambled
# looking cube that shows every color
_FACELETS = [0, 5, 2, 1, 0, 4, 3, 0, 2,
             4, 4, 1, 5, 4, 0, 2, 3, 4,
             2, 1, 2, 3, 2, 5, 0, 2, 4]
_FACE_LIGHT = (1.0, 0.84, 0.68)   # top, left, right
_STICKER_HALF = 0.42              # sticker half size in cell units
_PATTERN_SCALE = 1.28             # cell units to the shader's plate units

_cache = {}


# ---------------------------------------------------------------- shader helpers (numpy)
def _fract(x):
    return x - np.floor(x)


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _fill(d, aa):
    return 1.0 - _smoothstep(-aa, aa, d)


def _hash21(x, y):
    return _fract(np.sin(x * 127.1 + y * 311.7) * 43758.5453)


def _box2(px, py, bx, by):
    dx, dy = np.abs(px) - bx, np.abs(py) - by
    return np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(dx, dy), 0)


def _rrect(px, py, half, r):
    qx, qy = np.abs(px) - half + r, np.abs(py) - half + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def _hsv2rgb(h, s, v):
    k = np.clip(np.abs(np.mod(h[:, None] * 6.0 + np.array([0.0, 4.0, 2.0]), 6.0) - 3.0) - 1.0, 0.0, 1.0)
    return v * (1.0 + (k - 1.0) * s)


def _wob(px, py, seed):
    return (np.sin(px * 7.1 + seed) * 0.5 + np.sin(py * 9.3 + px * 3.7 + seed * 1.7) * 0.35
            + np.sin((px - py) * 13.0 + seed * 2.3) * 0.2)


def _ell(px, py, cx, cy, rx, ry):
    return (np.hypot((px - cx) / rx, (py - cy) / ry) - 1.0) * min(rx, ry)


def _glyph_raw(ids, px, py):
    """Hieroglyphs (ankh, eye of Horus, scarab, feather, cobra, sun disk), like glyph() in the shader."""
    r = np.hypot
    ankh = np.minimum(np.abs(r(px, py - 0.17) - 0.09) - 0.04,
                      np.minimum(_box2(px, py + 0.1, 0.04, 0.2), _box2(px, py, 0.15, 0.04)))
    a = np.abs(py) - 0.13 * np.maximum(0.0, 1.0 - px * px / 0.09)
    outline = np.maximum(np.abs(a) - 0.027, np.abs(px) - 0.31)
    eye = np.minimum(np.minimum(outline, r(px - 0.03, py) - 0.065),
                     np.minimum(_box2(px, py - 0.22, 0.3, 0.027),
                                np.minimum(_box2(px - 0.12, py + 0.2, 0.027, 0.065),
                                           np.abs(r(px + 0.08, py + 0.24) - 0.045) - 0.022)))
    body = np.maximum(_ell(px, py, 0.0, -0.03, 0.15, 0.19), 0.012 - np.abs(px))
    head = _ell(px, py, 0.0, 0.2, 0.09, 0.05)
    qx = np.abs(px) - 0.2
    legs = np.minimum(_box2(qx, py + 0.1, 0.07, 0.016),
                      np.minimum(_box2(qx, py + 0.01, 0.07, 0.016), _box2(qx, py - 0.08, 0.07, 0.016)))
    scarab = np.minimum(np.minimum(body, head), legs)
    feather = np.minimum(np.abs(_ell(px, py, 0.0, 0.05, 0.13, 0.25)) - 0.022, _box2(px, py + 0.02, 0.02, 0.3))
    hood = np.maximum(_ell(px, py, 0.0, 0.12, 0.14, 0.17), 0.022 - r(px - 0.05, py - 0.2))
    tail = np.maximum(np.abs(px - 0.07 * np.sin(py * 16.0)) - 0.045, np.maximum(py, -py - 0.3))
    cobra = np.minimum(hood, tail)
    sun = np.minimum(np.abs(r(px, py) - 0.26) - 0.038, r(px, py) - 0.075)
    out = sun
    for i, shape in enumerate((ankh, eye, scarab, feather, cobra)):
        out = np.where(ids == i, shape, out)
    return out


def _glyph(ids, px, py):
    return _glyph_raw(ids, px * 0.72, py * 0.72) / 0.72


def _mix(a, b, t):
    return a + (b - a) * t[:, None]


def _pattern(pid, px, py, base, ids, seed, accent, aa):
    """Sticker color and glow, like skinColor() in the cube shader (time 0, viewed head on)."""
    accent = np.asarray(accent, dtype=np.float64)
    emis = np.zeros_like(base)
    diff = base
    if pid == cube_skins.PATTERNS["stripes"]:
        u = (px + py) * 2.5
        diff = _mix(base, accent, _fill((np.abs(_fract(u) - 0.5) - 0.25) / 2.5, aa))
    elif pid == cube_skins.PATTERNS["checker"]:
        tx = np.abs(np.mod(px * 4.0 + 0.5, 2.0) - 1.0) - 0.5
        ty = np.abs(np.mod(py * 4.0 + 0.5, 2.0) - 1.0) - 0.5
        w = max(4.0 * aa, 1e-4)
        diff = _mix(base, accent, 0.5 + 0.5 * np.clip(tx / w, -1.0, 1.0) * np.clip(ty / w, -1.0, 1.0))
    elif pid == cube_skins.PATTERNS["dots"]:
        gx, gy = _fract(px * 3.0 + 0.5) - 0.5, _fract(py * 3.0 + 0.5) - 0.5
        diff = _mix(base, accent, _fill((np.hypot(gx, gy) - 0.28) / 3.0, aa))
    elif pid == cube_skins.PATTERNS["glyphs"]:
        fine = 1.0 - float(_smoothstep(0.4, 1.0, aa * 90.0))
        grain = 0.5 + (_hash21(np.floor(px * 90.0) + seed, np.floor(py * 90.0) + seed) - 0.5) * fine
        coarse = 0.5 + (_hash21(np.floor(px * 38.0) + seed * 1.9, np.floor(py * 38.0) + seed * 1.9) - 0.5) * fine
        stone = base * ((0.86 + 0.16 * grain + 0.14 * coarse) * (0.94 + 0.08 * _wob(px * 1.5, py * 1.5, seed)))[:, None]
        ripple = 1.0 + 0.045 * fine * np.sin((px * 0.45 + py) * 46.0 + _wob(px * 2.0, py * 2.0, seed) * 5.0)
        stone = stone * ripple[:, None]
        pale = np.broadcast_to(np.array([0.85, 0.72, 0.5]), stone.shape)
        stone = _mix(stone, pale, 0.25 * _smoothstep(0.35, 0.8, _wob(px * 2.7 + 5.0, py * 2.7 + 5.0, seed * 1.7) + 0.3))
        glint = np.where(_hash21(np.floor(px * 90.0) + seed * 3.3, np.floor(py * 90.0) + seed * 3.3) > 0.975, fine, 0.0)
        stone = stone + np.array([0.1, 0.09, 0.06]) * glint[:, None]
        pits = np.where(_hash21(np.floor(px * 55.0) + seed * 1.3, np.floor(py * 55.0) + seed * 1.3) > 0.985, 0.25 * fine, 0.0)
        stone = stone * (1.0 - pits)[:, None]
        chip = np.where(_hash21(np.floor(px * 18.0) + seed * 0.4, np.floor(py * 18.0) + seed * 0.4) >= 0.9, 0.03, 0.0)
        d = (_glyph(ids, px, py) + _wob(px * 3.0, py * 3.0, seed + ids) * 0.014 + chip * fine
             + (_hash21(np.floor(px * 45.0) + seed * 0.7, np.floor(py * 45.0) + seed * 0.7) - 0.5) * 0.016 * fine)
        inside = _fill(d, aa)
        edge = 1.0 - _smoothstep(0.0, 0.03, -d)
        wear = (0.5 + 0.5 * _wob(px * 3.4 + ids, py * 3.4 + ids, seed * 1.3)
                + (_hash21(np.floor(px * 40.0) + seed * 2.1, np.floor(py * 40.0) + seed * 2.1) - 0.5) * 0.5 * fine
                + (_hash21(np.floor(px * 90.0) + seed * 4.7, np.floor(py * 90.0) + seed * 4.7) - 0.5) * 0.3 * fine
                + 0.22 * edge)
        speck = np.where(_hash21(np.floor(px * 70.0) + seed * 5.9, np.floor(py * 70.0) + seed * 5.9) >= 0.82, 0.45 * fine, 0.0)
        paint = (1.0 - _smoothstep(0.66, 0.78, wear)) * (1.0 - speck)
        crack = (1.0 - _smoothstep(0.0, 0.09, np.abs(np.sin((px * 0.7 - py) * 35.0 + _wob(px * 4.0, py * 4.0, seed) * 6.0)))) * fine
        teal = np.array([0.09, 0.4, 0.41]) * (0.8 + 0.4 * grain)[:, None]
        teal = _mix(teal, np.broadcast_to(np.array([0.2, 0.5, 0.45]), teal.shape),
                    0.4 * (0.5 + 0.5 * _wob(px * 5.0, py * 5.0, seed * 0.9)))
        teal = teal * (1.0 - 0.45 * crack)[:, None]
        plaster = np.array([0.84, 0.79, 0.67]) * (0.9 + 0.2 * grain)[:, None]
        bare = _mix(stone * 0.6, plaster, 0.7 * edge)
        paint = paint * _fill(d + 0.009, aa)   # paint stays inside the carved edge, with a thin bare rim
        groove = _mix(bare, teal, paint)
        shadow = inside * (1.0 - _fill(_glyph(ids, px - 0.018, py + 0.018), aa))
        lit = inside * (1.0 - _fill(_glyph(ids, px + 0.018, py - 0.018), aa))
        groove = groove * ((1.0 - 0.55 * shadow) * (1.0 + 0.35 * lit))[:, None]
        diff = _mix(stone, groove, inside)
    elif pid == cube_skins.PATTERNS["neon"]:
        line = np.abs(_rrect(px, py, 0.36, 0.12))
        core = _fill(line - 0.025, aa)
        glow = np.exp(-line * 26.0)
        pulse = (0.78 + 0.22 * np.sin(seed))[:, None]
        diff = base * 0.06
        emis = (base * (core * 1.1 + glow * 0.55)[:, None] + (core * 0.35)[:, None]) * pulse
    elif pid == cube_skins.PATTERNS["psychedelic"]:
        wx = px + 0.1 * np.sin(py * 3.0 + seed)
        wy = py + 0.1 * np.cos(px * 3.0 + seed)
        swirl = 0.5 + 0.5 * np.sin((wx + wy) * 4.0 + seed)
        haze = 0.5 + 0.5 * np.sin(np.hypot(wx, wy) * 5.0 + seed * 0.7)
        light = base + (1.0 - base) * 0.4
        diff = base * 0.82 + (light - base * 0.82) * (0.35 * swirl + 0.3 * haze)[:, None]
    elif pid == cube_skins.PATTERNS["marble"]:
        n = _wob(px, py, seed)
        v = np.abs(np.sin((px * 2.0 + py) * 6.0 + n * 3.0))
        vein = 1.0 - _smoothstep(0.0, 0.18, v)
        vein_col = np.array(accent) if base.mean() >= 0.7 else np.array([0.98, 0.97, 0.94])
        diff = _mix(base, vein_col, vein * 0.95) * (0.92 + 0.08 * n)[:, None]
    elif pid == cube_skins.PATTERNS["lava"]:
        n = _wob(px, py, seed)
        crack = np.abs(np.sin(px * 8.0 + n * 4.0 + seed) * np.sin(py * 7.0 - n * 3.0 + seed * 0.7))
        glow = 1.0 - _smoothstep(0.0, 0.22, crack)
        pulse = 0.7 + 0.3 * np.sin(seed + n * 3.0)
        diff = accent * (0.8 + 0.4 * n)[:, None] + base * 0.12
        emis = base * (glow * pulse * 1.3)[:, None] + np.array([1.0, 0.9, 0.6]) * (glow ** 4 * 0.4 * pulse)[:, None]
    elif pid == cube_skins.PATTERNS["feathers"]:
        qx, qy = px * 4.5 + seed * 0.37, py * 4.5 + seed * 0.61
        d1 = np.full(qx.shape, 9.0)
        d2 = np.full(qx.shape, 9.0)
        lx, ly = np.zeros_like(qx), np.zeros_like(qx)
        cx1, cy1 = np.zeros_like(qx), np.zeros_like(qx)
        for j in (-1, 0, 1):
            cy = np.floor(qy) + j
            sh = 0.5 * np.mod(cy, 2.0)
            for i in (-1, 0, 1):
                cx = np.floor(qx - sh) + i + 0.5 + sh
                dx, dy = qx - cx, qy - (cy + 0.5)
                dist = np.hypot(dx, dy * 0.8)
                nearest = dist < d1
                second = ~nearest & (dist < d2)
                d2 = np.where(nearest, d1, np.where(second, dist, d2))
                lx, ly = np.where(nearest, dx, lx), np.where(nearest, dy, ly)
                cx1, cy1 = np.where(nearest, cx, cx1), np.where(nearest, cy + 0.5, cy1)
                d1 = np.where(nearest, dist, d1)
        h = _hash21(cx1, cy1)
        seam = 1.0 - _smoothstep(0.0, 0.14, d2 - d1)
        shaft = (1.0 - _smoothstep(0.02, 0.06, np.abs(lx))) * _smoothstep(-0.35, -0.1, ly)
        bar = 1.0 - _smoothstep(0.03, 0.09, np.abs(ly + np.abs(lx) * 0.7 - 0.12))
        f = base * ((0.7 + 0.35 * h) * (0.85 + 0.35 * (ly + 0.5)))[:, None]
        f = _mix(f, np.broadcast_to(accent, f.shape), 0.35 * bar + 0.45 * shaft)
        diff = f * (1.0 - 0.55 * seam)[:, None]
    elif pid == cube_skins.PATTERNS["holo"]:
        phase = np.array([0.0, 0.33, 0.67]) + ((px - py) * 0.9 + 1.6)[:, None]
        rainbow = 0.5 + 0.5 * np.cos(6.2832 * phase)
        diff = base + (rainbow - base) * 0.2
        s = _hash21(np.floor(px * 28.0) + seed, np.floor(py * 28.0) + seed)
        emis = np.repeat((np.where(s > 0.97, 0.5, 0.0) * 0.5)[:, None], 3, axis=1)
    elif pid == cube_skins.PATTERNS["static"]:
        n = _hash21(np.floor(px * 22.0) + seed, np.floor(py * 22.0) + seed)
        scan = 0.85 + 0.15 * np.sin(py * 90.0)
        diff = base * ((0.45 + 0.75 * n) * scan)[:, None]
        emis = base * (0.15 * n)[:, None]
    elif pid == cube_skins.PATTERNS["pixel"]:
        qx, qy = (px + 0.5) * 6.0, (py + 0.5) * 6.0
        lx, ly = _fract(qx) - 0.5, _fract(qy) - 0.5
        inner = _fill((np.maximum(np.abs(lx), np.abs(ly)) - 0.40) / 6.0, aa)
        bright = 0.78 + 0.3 * _hash21(np.floor(qx) + seed, np.floor(qy) + seed)
        diff = _mix(base * 0.35, base * bright[:, None], inner)
    elif pid == cube_skins.PATTERNS["gems"]:
        a = np.arctan2(py, px)
        sector = np.floor((a + 3.14159) / 0.785398)
        table = _fill(np.abs(px) + np.abs(py) - 0.22, aa)
        fb = 0.55 + 0.6 * _hash21(sector, ids * 3.1)
        fb = fb + (1.25 - fb) * table
        diff = base * fb[:, None]
    return diff, emis


# ---------------------------------------------------------------- rasterizer
_CUBIE_HALF = 0.475    # cubie face half size in cell units (the rest is the seam between cubies)
_CUBIE_RADIUS = 0.2    # rounded cubie corners, in cell units
_BEVEL = 0.12          # width of the darker rounded bevel along each cubie's edge, in cell units
_OUTLINE_RADIUS = 0.1  # rounded corners of the whole cube's outline, in cube edge lengths


def _convex_sdf(x, y, verts):
    """Signed distance (negative inside) to a convex polygon."""
    cx = sum(v[0] for v in verts) / len(verts)
    cy = sum(v[1] for v in verts) / len(verts)
    dist = np.full(x.shape, np.inf)
    inside = np.ones(x.shape, dtype=bool)
    for (ax, ay), (bx, by) in zip(verts, verts[1:] + verts[:1]):
        ex, ey = bx - ax, by - ay
        wx, wy = x - ax, y - ay
        h = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
        dist = np.minimum(dist, np.hypot(wx - ex * h, wy - ey * h))
        side = np.sign(ex * (cy - ay) - ey * (cx - ax))  # which side of this edge is inside
        inside &= (ex * wy - ey * wx) * side >= 0
    return np.where(inside, -dist, dist)


_geometry_cache = {}


def _geometry(n):
    """Everything about the preview that does not depend on the skin, for an n x n image:
    the outline's coverage and, per cube face, its pixels and their cell coordinates."""
    geo = _geometry_cache.get(n)
    if geo is not None:
        return geo
    a = n * 0.45
    cx = cy = n / 2.0
    cos30 = math.cos(math.radians(30))
    dx, dy = a * cos30, a / 2.0
    top, right, left = (cx, cy - a), (cx + dx, cy - dy), (cx - dx, cy - dy)
    mid, bottom, bl = (cx, cy), (cx, cy + a), (cx - dx, cy + dy)

    def vec(p, q):
        return (q[0] - p[0], q[1] - p[1])

    faces = [(left, vec(left, top), vec(left, mid)),
             (left, vec(left, mid), vec(left, bl)),
             (mid, vec(mid, right), vec(mid, bottom))]
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float64) + 0.5
    cell_px = 3.0 / a  # one pixel in cell units

    # Outline: the hexagon around the cube with rounded corners
    r_out = a * _OUTLINE_RADIUS
    radius = a - r_out / cos30  # hexagon shrunk by r_out, then grown back round
    hexagon = [(cx + radius * math.cos(math.radians(ang)), cy + radius * math.sin(math.radians(ang)))
               for ang in (-90, -30, 30, 90, 150, 210)]
    alpha = _fill(_convex_sdf(xs, ys, hexagon) - r_out, 1.0)

    claimed = np.zeros((n, n), dtype=bool)
    pad = 0.05
    parts = []
    for f, (o, u, v) in enumerate(faces):
        det = u[0] * v[1] - u[1] * v[0]
        rx, ry = xs - o[0], ys - o[1]
        s = (rx * v[1] - ry * v[0]) / det
        t = (u[0] * ry - u[1] * rx) / det
        inside = (s >= -pad) & (s <= 1 + pad) & (t >= -pad) & (t <= 1 + pad) & (alpha > 0) & ~claimed
        claimed |= inside
        s, t = s[inside], t[inside]
        i, j = np.clip(np.floor(s * 3), 0, 2), np.clip(np.floor(t * 3), 0, 2)
        lx, ly = s * 3 - i - 0.5, t * 3 - j - 0.5
        d_cubie = _rrect(lx, ly, _CUBIE_HALF, _CUBIE_RADIUS)
        parts.append({
            "mask": inside, "lx": lx, "ly": ly, "k": (f * 9 + j * 3 + i).astype(int),
            "tile": _fill(_rrect(lx, ly, _STICKER_HALF, 0.12), cell_px)[:, None],
            "cubie": _fill(d_cubie, cell_px)[:, None],
            # Rounded cubie: its plastic darkens towards the edge like the bevel of the real one
            "bevel": _smoothstep(-_BEVEL, 0.0, d_cubie)[:, None],
        })
    geo = {"alpha": alpha, "faces": parts, "aa": cell_px * _PATTERN_SCALE}
    _geometry_cache[n] = geo
    return geo


def render(skin, size):
    """Surface (size x size, transparent background) showing the skin on an isometric cube
    built like the real one: rounded cubies with seams between them, stickers on top."""
    key = (skin["id"], int(size), tuple(map(tuple, RubiksCube.color_map.values())) if not skin["colors"] else None)
    surf = _cache.get(key)
    if surf is not None:
        return surf

    n = int(size) * 2  # supersampled
    geo = _geometry(n)
    palette = skin["colors"] or RubiksCube.color_map
    colors = np.array([palette[i] for i in range(6)], dtype=np.float64)
    body = np.asarray(skin["body"], dtype=np.float64)
    facelets = np.array(_FACELETS)

    # Anything inside the outline that no face claims is seam (the dark gaps between cubies)
    rgb = np.empty((n, n, 3))
    rgb[:] = body * 0.25
    for f, part in enumerate(geo["faces"]):
        if not part["k"].size:
            continue
        k = part["k"]
        ids = facelets[k]
        px, py = part["lx"] * _PATTERN_SCALE, part["ly"] * _PATTERN_SCALE
        diff, emis = _pattern(skin["pattern_id"], px, py, colors[ids], ids.astype(np.float64),
                              k * 7.31, skin["accent"], geo["aa"])
        light = _FACE_LIGHT[f]
        sticker = np.clip(diff * light + emis, 0.0, 1.0)
        tile, cubie = part["tile"], part["cubie"]
        plastic = body * light * (1.0 - 0.45 * part["bevel"])
        face_rgb = plastic * (1 - tile) + sticker * tile
        rgb[part["mask"]] = body * light * 0.25 * (1 - cubie) + face_rgb * cubie

    data = np.dstack([np.clip(rgb, 0, 1) * 255.0, geo["alpha"] * 255.0]).astype(np.uint8)
    big = pygame.image.frombuffer(data.tobytes(), (n, n), "RGBA")
    surf = pygame.transform.smoothscale(big, (int(size), int(size)))
    _cache[key] = surf
    return surf
