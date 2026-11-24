"""Anti-aliasing and vertical sync.

Anti-aliasing works on an offscreen scene buffer, so it can change at any time
without recreating the window, and it also works with HDR output:
- MSAA: the 3D scene is drawn into a multisampled buffer, then resolved.
- SSAA: the scene is drawn at twice the width and height, then averaged down.
- FXAA: an edge smoothing pass over the finished scene.
Menus and the HUD are drawn afterwards at native resolution, so text stays crisp.
"""
import ctypes
import os

import pygame
from OpenGL.GL import (
    GL_BLEND, GL_CLAMP_TO_EDGE, GL_COLOR_ATTACHMENT0, GL_COLOR_BUFFER_BIT, GL_CULL_FACE, GL_DEPTH24_STENCIL8,
    GL_DEPTH_STENCIL_ATTACHMENT, GL_DEPTH_TEST, GL_DRAW_FRAMEBUFFER, GL_DRAW_FRAMEBUFFER_BINDING,
    GL_ENABLE_BIT, GL_FRAGMENT_SHADER, GL_FRAMEBUFFER, GL_FRAMEBUFFER_COMPLETE, GL_LIGHTING, GL_LINEAR,
    GL_MAX_SAMPLES, GL_MODELVIEW, GL_NEAREST, GL_PROJECTION, GL_QUADS, GL_READ_FRAMEBUFFER, GL_RENDERBUFFER,
    GL_RGBA, GL_RGBA8, GL_TEXTURE0, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_UNSIGNED_BYTE, GL_VERTEX_SHADER,
    glActiveTexture, glBegin, glBindFramebuffer, glBindRenderbuffer, glBindTexture, glBlitFramebuffer,
    glCheckFramebufferStatus, glDeleteFramebuffers, glDeleteProgram, glDeleteRenderbuffers, glDeleteTextures,
    glDisable, glEnd, glFramebufferRenderbuffer, glFramebufferTexture2D, glGenFramebuffers, glGenRenderbuffers,
    glGenTextures, glGetIntegerv, glGetUniformLocation, glLoadIdentity, glMatrixMode, glPopAttrib, glPopMatrix,
    glPushAttrib, glPushMatrix, glRenderbufferStorage, glRenderbufferStorageMultisample, glTexCoord2f,
    glTexImage2D, glTexParameteri, glUniform1i, glUniform2f, glUseProgram, glVertex2f, glViewport,
)
from OpenGL.GL import shaders

# ---------------------------------------------------------------- anti-aliasing
# id -> (label, MSAA samples, supersampling scale, FXAA pass)
AA_MODES = {
    "off": ("Off", 0, 1, False),
    "fxaa": ("FXAA", 0, 1, True),
    "msaa2": ("MSAA 2x", 2, 1, False),
    "msaa4": ("MSAA 4x", 4, 1, False),
    "msaa8": ("MSAA 8x", 8, 1, False),
    "ssaa4": ("SSAA 4x", 0, 2, False),
}
DEFAULT_AA = "msaa4"


def max_samples():
    try:
        return int(glGetIntegerv(GL_MAX_SAMPLES))
    except Exception:
        return 0


def aa_menu_items():
    """(label, id) for every mode this GPU supports."""
    limit = max_samples()
    return [(label, key) for key, (label, samples, _, _) in AA_MODES.items() if samples <= limit]


_VERTEX = """#version 120
varying vec2 uv;
void main() {
    uv = gl_MultiTexCoord0.xy;
    gl_Position = gl_Vertex;
}
"""

# FXAA after Timothy Lottes (the compact PC variant)
_FRAGMENT = """#version 120
uniform sampler2D scene;
uniform vec2 texel;
uniform int fxaa;
varying vec2 uv;

void main() {
    vec3 m = texture2D(scene, uv).rgb;
    if (fxaa == 0) { gl_FragColor = vec4(m, 1.0); return; }
    vec3 nw = texture2D(scene, uv + vec2(-1.0, -1.0) * texel).rgb;
    vec3 ne = texture2D(scene, uv + vec2( 1.0, -1.0) * texel).rgb;
    vec3 sw = texture2D(scene, uv + vec2(-1.0,  1.0) * texel).rgb;
    vec3 se = texture2D(scene, uv + vec2( 1.0,  1.0) * texel).rgb;
    vec3 L = vec3(0.299, 0.587, 0.114);
    float lnw = dot(nw, L), lne = dot(ne, L), lsw = dot(sw, L), lse = dot(se, L), lm = dot(m, L);
    float lmin = min(lm, min(min(lnw, lne), min(lsw, lse)));
    float lmax = max(lm, max(max(lnw, lne), max(lsw, lse)));
    vec2 dir = vec2(-((lnw + lne) - (lsw + lse)), ((lnw + lsw) - (lne + lse)));
    float reduce = max((lnw + lne + lsw + lse) * 0.25 * (1.0 / 8.0), 1.0 / 128.0);
    float rcp = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
    dir = clamp(dir * rcp, vec2(-8.0), vec2(8.0)) * texel;
    vec3 a = 0.5 * (texture2D(scene, uv + dir * (1.0 / 3.0 - 0.5)).rgb
                  + texture2D(scene, uv + dir * (2.0 / 3.0 - 0.5)).rgb);
    vec3 b = a * 0.5 + 0.25 * (texture2D(scene, uv - dir * 0.5).rgb + texture2D(scene, uv + dir * 0.5).rgb);
    float lb = dot(b, L);
    gl_FragColor = vec4((lb < lmin || lb > lmax) ? a : b, 1.0);
}
"""


def _texture(w, h):
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tex


def _renderbuffer(fmt, w, h, samples):
    rb = glGenRenderbuffers(1)
    glBindRenderbuffer(GL_RENDERBUFFER, rb)
    if samples:
        glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples, fmt, w, h)
    else:
        glRenderbufferStorage(GL_RENDERBUFFER, fmt, w, h)
    glBindRenderbuffer(GL_RENDERBUFFER, 0)
    return rb


class SceneTarget:
    """Offscreen buffer the 3D scene is drawn into, according to the anti-aliasing mode.

    Usage per frame:  if target.begin(w, h): draw scene; target.end(dest_fbo)
    begin() returns False for "off": the scene then draws straight to the screen.
    """

    def __init__(self, mode=DEFAULT_AA):
        self.mode = mode if mode in AA_MODES else DEFAULT_AA
        self.size = None
        self.scene_size = None
        self._fbos, self._rbs, self._texs = [], [], []
        self.program = None
        self.active = False

    # ---------------------------------------------------------------- setup
    def set_mode(self, mode):
        if mode not in AA_MODES:
            mode = DEFAULT_AA
        if mode != self.mode:
            self._release()
            self.mode = mode

    def _release(self):
        for fn, objs in ((glDeleteFramebuffers, self._fbos), (glDeleteRenderbuffers, self._rbs),
                         (glDeleteTextures, self._texs)):
            for obj in objs:
                try:
                    fn(1, [obj])
                except Exception:
                    pass
            objs.clear()
        self.size = None
        self.scene_size = None

    def _build(self, w, h):
        _, samples, scale, _ = AA_MODES[self.mode]
        samples = min(samples, max_samples())
        sw, sh = w * scale, h * scale
        if self.program is None:
            self.program = shaders.compileProgram(shaders.compileShader(_VERTEX, GL_VERTEX_SHADER),
                                                  shaders.compileShader(_FRAGMENT, GL_FRAGMENT_SHADER),
                                                  validate=False)
            self._scene_loc = glGetUniformLocation(self.program, "scene")
            self._texel_loc = glGetUniformLocation(self.program, "texel")
            self._fxaa_loc = glGetUniformLocation(self.program, "fxaa")

        # The texture the final pass reads (the scene itself, or the MSAA resolve)
        self.texture = _texture(sw, sh)
        self._texs.append(self.texture)
        self.resolve_fbo = glGenFramebuffers(1)
        self._fbos.append(self.resolve_fbo)
        glBindFramebuffer(GL_FRAMEBUFFER, self.resolve_fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.texture, 0)
        if samples:
            ok = glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE
            self.scene_fbo = glGenFramebuffers(1)
            self._fbos.append(self.scene_fbo)
            glBindFramebuffer(GL_FRAMEBUFFER, self.scene_fbo)
            color = _renderbuffer(GL_RGBA8, sw, sh, samples)
            self._rbs.append(color)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, color)
        else:
            ok = True
            self.scene_fbo = self.resolve_fbo
        depth = _renderbuffer(GL_DEPTH24_STENCIL8, sw, sh, samples)
        self._rbs.append(depth)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, depth)
        ok = ok and glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        if not ok:
            self._release()
            raise RuntimeError(f"{AA_MODES[self.mode][0]} buffer is not supported")
        self.samples = samples
        self.size = (w, h)
        self.scene_size = (sw, sh)

    # ---------------------------------------------------------------- per frame
    def begin(self, w, h):
        """Bind the scene buffer (rebuilt when the window size changed)."""
        self.active = False
        if self.mode == "off":
            return False
        if self.size != (w, h):
            self._release()
            try:
                self._build(w, h)
            except Exception as e:
                print(f"Anti-aliasing unavailable, turning it off: {e}")
                self._release()
                self.mode = "off"
                return False
        self._dest = int(glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING))
        glBindFramebuffer(GL_FRAMEBUFFER, self.scene_fbo)
        glViewport(0, 0, *self.scene_size)
        self.active = True
        return True

    def end(self):
        """Resolve the scene and draw it into the buffer that was bound before begin()."""
        if not self.active:
            return
        self.active = False
        sw, sh = self.scene_size
        if self.samples:
            glBindFramebuffer(GL_READ_FRAMEBUFFER, self.scene_fbo)
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, self.resolve_fbo)
            glBlitFramebuffer(0, 0, sw, sh, 0, 0, sw, sh, GL_COLOR_BUFFER_BIT, GL_NEAREST)
        glBindFramebuffer(GL_FRAMEBUFFER, self._dest)
        w, h = self.size
        glViewport(0, 0, w, h)

        glPushAttrib(GL_ENABLE_BIT)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_BLEND)
        glDisable(GL_CULL_FACE)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glUseProgram(self.program)
        glUniform1i(self._scene_loc, 0)
        glUniform1i(self._fxaa_loc, 1 if AA_MODES[self.mode][3] else 0)
        glUniform2f(self._texel_loc, 1.0 / sw, 1.0 / sh)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(-1, -1)
        glTexCoord2f(1, 0); glVertex2f(1, -1)
        glTexCoord2f(1, 1); glVertex2f(1, 1)
        glTexCoord2f(0, 1); glVertex2f(-1, 1)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopAttrib()

    def delete(self):
        self._release()
        if self.program:
            try:
                glDeleteProgram(self.program)
            except Exception:
                pass
            self.program = None


# ---------------------------------------------------------------- vertical sync
# id -> (label, swap interval). Adaptive syncs when the game keeps up with the
# monitor and tears instead of stuttering when it falls behind.
VSYNC_MODES = {
    "off": ("Off", 0),
    "on": ("On", 1),
    "adaptive": ("Adaptive", -1),
}
DEFAULT_VSYNC = "on"

_sdl = None


def _sdl_lib():
    global _sdl
    if _sdl is None:
        try:
            _sdl = ctypes.CDLL(os.path.join(os.path.dirname(pygame.__file__), "SDL2.dll"))
        except OSError:
            _sdl = ctypes.CDLL("SDL2")
    return _sdl


def swap_interval():
    try:
        return int(_sdl_lib().SDL_GL_GetSwapInterval())
    except Exception:
        return None


def set_vsync(mode):
    """Apply a VSync mode to the current window. Returns the mode that is really active."""
    if mode not in VSYNC_MODES:
        mode = DEFAULT_VSYNC
    try:
        sdl = _sdl_lib()
        if sdl.SDL_GL_SetSwapInterval(VSYNC_MODES[mode][1]) != 0:
            if mode == "adaptive" and sdl.SDL_GL_SetSwapInterval(1) == 0:
                return "on"
            return None
    except Exception as e:
        print(f"Could not change vertical sync: {e}")
        return None
    return mode


_adaptive_supported = None


def adaptive_supported():
    """Whether the driver offers adaptive sync (checked once, current interval kept)."""
    global _adaptive_supported
    if _adaptive_supported is None:
        try:
            sdl = _sdl_lib()
            current = sdl.SDL_GL_GetSwapInterval()
            _adaptive_supported = sdl.SDL_GL_SetSwapInterval(-1) == 0
            sdl.SDL_GL_SetSwapInterval(current)
        except Exception:
            _adaptive_supported = False
    return _adaptive_supported


def vsync_menu_items():
    return [(label, key) for key, (label, _) in VSYNC_MODES.items()
            if key != "adaptive" or adaptive_supported()]
