"""Cube skins: sticker palettes and procedural sticker patterns, unlocked through achievements.

Each skin gives the six sticker colors (by color index, see RubiksCube), a pattern drawn on
every sticker by the cube shader (src/rendering/renderer.py), an accent color the pattern
uses, and the color of the plastic body. The previews on the customization page draw the
same patterns on the CPU (src/rendering/skin_preview.py).
"""

# Pattern ids, shared with the cube shader (uniform skinPattern)
PATTERNS = {
    "solid": 0, "stripes": 1, "checker": 2, "dots": 3, "glyphs": 4, "neon": 5, "psychedelic": 6,
    "marble": 7, "lava": 8, "eyes": 9, "holo": 10, "static": 11, "pixel": 12, "gems": 13,
}

DEFAULT_SKIN = "classic"
_DARK_BODY = (0.055, 0.058, 0.07)
_STANDARD = {0: (1.0, 0.95, 0.0), 1: (1.0, 1.0, 1.0), 2: (0.9, 0.1, 0.1),
             3: (1.0, 0.35, 0.0), 4: (0.0, 0.2, 0.9), 5: (0.0, 0.8, 0.2)}


def _skin(skin_id, name, description, pattern="solid", colors=None, accent=(1.0, 1.0, 1.0),
          body=_DARK_BODY, gloss=0.0, unlock=None, animated=False):
    return {"id": skin_id, "name": name, "description": description, "pattern": pattern,
            "pattern_id": PATTERNS[pattern], "colors": colors, "accent": accent, "body": body,
            "gloss": gloss, "unlock": unlock, "animated": animated}


# In the order the customization page shows them (roughly from easiest to hardest to unlock)
SKINS = [
    _skin("classic", "Classic", "The colors you know. Follows the color scheme chosen in Settings."),
    _skin("cotton_candy", "Cotton Candy", "Soft pastels on a white body. Sweet enough to hurt.",
          colors={0: (1.0, 0.92, 0.55), 1: (0.78, 0.68, 1.0), 2: (1.0, 0.6, 0.78),
                  3: (1.0, 0.74, 0.52), 4: (0.58, 0.8, 1.0), 5: (0.6, 0.95, 0.76)},
          body=(0.94, 0.93, 0.96), gloss=0.05, unlock="first_solve"),
    _skin("candy_stripes", "Candy Stripes", "Every sticker wrapped like a sweet.", pattern="stripes",
          colors={0: (1.0, 0.82, 0.08), 1: (0.95, 0.35, 0.7), 2: (0.88, 0.08, 0.14),
                  3: (1.0, 0.5, 0.05), 4: (0.15, 0.42, 0.95), 5: (0.18, 0.78, 0.3)},
          accent=(0.98, 0.97, 0.95), unlock="solve_5"),
    _skin("checkmate", "Checkmate", "A chessboard on every sticker.", pattern="checker",
          colors=_STANDARD, accent=(0.06, 0.06, 0.07), body=(0.82, 0.82, 0.84), unlock="first_medium"),
    _skin("polka_party", "Polka Party", "Retro dots on loud colors.", pattern="dots",
          colors={0: (0.0, 0.62, 0.64), 1: (0.85, 0.1, 0.55), 2: (0.95, 0.3, 0.2),
                  3: (0.92, 0.7, 0.1), 4: (0.12, 0.2, 0.58), 5: (0.48, 0.78, 0.15)},
          accent=(0.98, 0.96, 0.9), unlock="solve_10"),
    _skin("eight_bit", "8-Bit", "Chunky pixels from the arcade age.", pattern="pixel",
          colors={0: (0.99, 0.84, 0.22), 1: (0.97, 0.97, 0.97), 2: (0.86, 0.14, 0.1),
                  3: (0.98, 0.55, 0.1), 4: (0.2, 0.34, 0.95), 5: (0.18, 0.74, 0.2)},
          body=(0.02, 0.02, 0.02), unlock="first_hard"),
    _skin("marble_hall", "Marble Hall", "Six polished stones held in brass.", pattern="marble",
          colors={0: (0.96, 0.95, 0.92), 1: (0.17, 0.17, 0.19), 2: (0.03, 0.36, 0.24),
                  3: (0.88, 0.6, 0.62), 4: (0.15, 0.25, 0.65), 5: (0.74, 0.3, 0.07)},
          accent=(0.55, 0.52, 0.5), body=(0.55, 0.43, 0.2), gloss=0.3, unlock="solve_25"),
    _skin("noir", "Vintage Print", "Cream paper, ink and faded dyes, like a well-worn old poster.",
          colors={0: (0.92, 0.66, 0.14), 1: (0.94, 0.91, 0.82), 2: (0.72, 0.07, 0.11),
                  3: (0.1, 0.1, 0.12), 4: (0.2, 0.4, 0.6), 5: (0.12, 0.47, 0.36)},
          body=(0.36, 0.33, 0.3), gloss=0.1, unlock="solve_50"),
    _skin("neon_nights", "Neon Nights", "Glowing tubes buzzing in the dark.", pattern="neon",
          colors={0: (0.1, 0.95, 1.0), 1: (1.0, 0.15, 0.75), 2: (0.6, 1.0, 0.1),
                  3: (0.6, 0.32, 1.0), 4: (1.0, 0.45, 0.05), 5: (0.95, 0.95, 1.0)},
          body=(0.02, 0.02, 0.03), unlock="speed_under_1min", animated=True),
    _skin("treasure_hoard", "Treasure Hoard", "Cut gems set in solid gold.", pattern="gems",
          colors={0: (1.0, 0.76, 0.18), 1: (0.85, 0.94, 1.0), 2: (0.85, 0.05, 0.2),
                  3: (0.95, 0.42, 0.08), 4: (0.1, 0.25, 0.95), 5: (0.05, 0.75, 0.35)},
          body=(0.72, 0.52, 0.14), gloss=0.35, unlock="limited_time_win", animated=True),
    _skin("hieroglyphs", "Hieroglyphs", "One color for the whole cube. Only the symbols tell the sides apart.",
          pattern="glyphs", colors={i: (0.86, 0.74, 0.5) for i in range(6)}, accent=(0.24, 0.14, 0.07),
          body=(0.3, 0.21, 0.11), unlock="limited_moves_win"),
    _skin("hologram", "Hologram", "Shifts through the rainbow as you turn it.", pattern="holo",
          colors={0: (1.0, 0.95, 0.4), 1: (0.95, 0.95, 1.0), 2: (1.0, 0.35, 0.4),
                  3: (1.0, 0.62, 0.3), 4: (0.35, 0.5, 1.0), 5: (0.35, 0.95, 0.55)},
          body=(0.6, 0.62, 0.66), gloss=0.3, unlock="daily_first", animated=True),
    _skin("magma_core", "Magma Core", "Cooling rock with molten cracks.", pattern="lava",
          colors={0: (1.0, 0.85, 0.2), 1: (1.0, 0.98, 0.9), 2: (1.0, 0.12, 0.04),
                  3: (1.0, 0.48, 0.04), 4: (0.2, 0.5, 1.0), 5: (0.3, 1.0, 0.3)},
          accent=(0.09, 0.07, 0.065), body=(0.05, 0.04, 0.04), unlock="hard_10"),
    _skin("bad_signal", "Bad Signal", "Your cube lost reception.", pattern="static",
          colors=_STANDARD, body=(0.08, 0.08, 0.08), unlock="undo_addict", animated=True),
    _skin("fever_dream", "Fever Dream", "Soft swirls of light drifting slowly over dreamy colors.", pattern="psychedelic",
          colors={0: (1.0, 0.84, 0.3), 1: (0.97, 0.95, 1.0), 2: (0.93, 0.25, 0.32),
                  3: (1.0, 0.55, 0.25), 4: (0.3, 0.45, 0.95), 5: (0.25, 0.8, 0.5)},
          body=(0.16, 0.1, 0.26), gloss=0.1, unlock="secret_scrambler", animated=True),
    _skin("the_watchers", "The Watchers", "Fifty four eyes. They follow you. They blink.", pattern="eyes",
          colors={0: (0.95, 0.75, 0.1), 1: (0.62, 0.9, 1.0), 2: (0.85, 0.05, 0.12),
                  3: (0.58, 0.22, 0.88), 4: (0.1, 0.35, 0.95), 5: (0.15, 0.75, 0.25)},
          accent=(0.78, 0.52, 0.48), body=(0.33, 0.1, 0.1), gloss=0.1, unlock="night_owl", animated=True),
]
SKINS_BY_ID = {skin["id"]: skin for skin in SKINS}


def get_skin(skin_id):
    return SKINS_BY_ID.get(skin_id, SKINS_BY_ID[DEFAULT_SKIN])


def is_unlocked(skin, achievements_manager):
    achievement = skin.get("unlock")
    if not achievement:
        return True
    return bool(achievements_manager and achievements_manager.is_unlocked(achievement))


def unlocked_count(achievements_manager):
    return sum(1 for skin in SKINS if is_unlocked(skin, achievements_manager)), len(SKINS)


def skins_unlocked_by(achievement_id):
    return [skin for skin in SKINS if skin.get("unlock") == achievement_id]
