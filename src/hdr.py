"""HDR output for Windows HDR displays.

When Windows HDR is on, a normal 8-bit window is converted by the compositor,
which often looks washed out. With HDR output enabled the window gets a 16-bit
float framebuffer that Windows reads as scRGB (linear light, 1.0 = 80 nits).
The game still renders exactly as before into an offscreen 8-bit buffer; a
final pass decodes it to linear light and scales it to the chosen brightness.
"""
import ctypes
import os
import sys
import uuid

import pygame
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE, GL_COLOR_ATTACHMENT0, GL_CULL_FACE, GL_DEPTH_ATTACHMENT,
    GL_DEPTH_COMPONENT24, GL_DEPTH_TEST, GL_ENABLE_BIT, GL_FRAMEBUFFER, GL_FRAMEBUFFER_COMPLETE,
    GL_FRAGMENT_SHADER, GL_LIGHTING, GL_BLEND, GL_LINEAR, GL_MODELVIEW, GL_PROJECTION, GL_QUADS, GL_RENDERBUFFER,
    GL_RGBA, GL_RGBA8, GL_TEXTURE0, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_UNSIGNED_BYTE, GL_VERTEX_SHADER, GL_VIEWPORT,
    glActiveTexture, glBegin, glBindFramebuffer, glBindRenderbuffer, glBindTexture, glCheckFramebufferStatus,
    glDeleteFramebuffers, glDeleteProgram, glDeleteRenderbuffers, glDeleteTextures, glDisable, glEnd,
    glFramebufferRenderbuffer, glFramebufferTexture2D, glGenFramebuffers, glGenRenderbuffers, glGenTextures,
    glGetBooleanv, glGetIntegerv, glGetUniformLocation, glLoadIdentity, glMatrixMode, glPopAttrib, glPopMatrix,
    glPushAttrib, glPushMatrix, glRenderbufferStorage, glTexCoord2f, glTexImage2D, glTexParameteri,
    glUniform1f, glUniform1i, glUseProgram, glVertex2f, glViewport,
)
from OpenGL.GL import shaders

GL_RGBA_FLOAT_MODE_ARB = 0x8820
SDL_GL_FLOATBUFFERS = 27  # SDL_GLattr value, not exported by pygame

PAPER_WHITE_DEFAULT = 200
PAPER_WHITE_RANGE = (80, 400)


# ---------------------------------------------------------------- detection
class _GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, text):
        u = uuid.UUID(text)
        return cls(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _OUTPUT_DESC1(ctypes.Structure):
    _fields_ = [("DeviceName", ctypes.c_wchar * 32), ("Desktop", _RECT), ("Attached", ctypes.c_int),
                ("Rotation", ctypes.c_uint), ("Monitor", ctypes.c_void_p), ("BitsPerColor", ctypes.c_uint),
                ("ColorSpace", ctypes.c_uint), ("Primaries", ctypes.c_float * 8),
                ("MinLuminance", ctypes.c_float), ("MaxLuminance", ctypes.c_float),
                ("MaxFullFrameLuminance", ctypes.c_float)]


class _SDL_Rect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("w", ctypes.c_int), ("h", ctypes.c_int)]


_COLOR_SPACE_HDR10 = 12  # DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020


def _vcall(obj, index, *argtypes):
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtbl[index])


def _release(obj):
    if obj:
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2])(obj)


def hdr_outputs():
    """List (desktop rect, HDR active, peak nits) for every monitor, via DXGI."""
    if sys.platform != "win32":
        return []
    result = []
    try:
        dxgi = ctypes.WinDLL("dxgi")
        factory = ctypes.c_void_p()
        if dxgi.CreateDXGIFactory1(ctypes.byref(_GUID.of("770aae78-f26f-4dba-a829-253c83d1b387")),
                                   ctypes.byref(factory)) != 0:
            return []
        iid_output6 = _GUID.of("068346e8-aaec-4b84-add7-137f513f77a1")
        a = 0
        while True:
            adapter = ctypes.c_void_p()
            if _vcall(factory, 12, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(factory, a, ctypes.byref(adapter)) != 0:
                break
            o = 0
            while True:
                output = ctypes.c_void_p()
                if _vcall(adapter, 7, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(adapter, o, ctypes.byref(output)) != 0:
                    break
                output6 = ctypes.c_void_p()
                if _vcall(output, 0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
                        output, ctypes.byref(iid_output6), ctypes.byref(output6)) == 0:
                    desc = _OUTPUT_DESC1()
                    if _vcall(output6, 27, ctypes.POINTER(_OUTPUT_DESC1))(output6, ctypes.byref(desc)) == 0:
                        r = desc.Desktop
                        result.append({
                            "rect": (r.left, r.top, r.right - r.left, r.bottom - r.top),
                            "hdr": desc.ColorSpace == _COLOR_SPACE_HDR10,
                            "peak_nits": float(desc.MaxLuminance),
                        })
                    _release(output6)
                _release(output)
                o += 1
            _release(adapter)
            a += 1
        _release(factory)
    except Exception:
        return result
    return result


def _sdl_display_rect(display_index):
    try:
        sdl = ctypes.CDLL(os.path.join(os.path.dirname(pygame.__file__), "SDL2.dll"))
        rect = _SDL_Rect()
        if sdl.SDL_GetDisplayBounds(int(display_index), ctypes.byref(rect)) == 0:
            return (rect.x, rect.y, rect.w, rect.h)
    except Exception:
        pass
    return None


def display_hdr_info(display_index):
    """(HDR active on that monitor, peak brightness in nits or None)."""
    rect = _sdl_display_rect(display_index)
    outputs = hdr_outputs()
    for out in outputs:
        if rect is not None and out["rect"] == rect:
            return out["hdr"], out["peak_nits"]
    if rect is None and len(outputs) == 1:
        return outputs[0]["hdr"], outputs[0]["peak_nits"]
    return False, None


# ---------------------------------------------------------------- window setup
def request_framebuffer(hdr, msaa=True):
    """Set the OpenGL pixel format for the next window: 16-bit float for HDR.

    Standard windows get 4x multisampling (smooth cube edges). The HDR path renders
    into its own offscreen buffer, so it doesn't use it.
    """
    samples = 4 if (msaa and not hdr) else 0
    pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1 if samples else 0)
    pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, samples)
    bits = 16 if hdr else 8
    pygame.display.gl_set_attribute(pygame.GL_RED_SIZE, bits)
    pygame.display.gl_set_attribute(pygame.GL_GREEN_SIZE, bits)
    pygame.display.gl_set_attribute(pygame.GL_BLUE_SIZE, bits)
    pygame.display.gl_set_attribute(pygame.GL_ALPHA_SIZE, 16 if hdr else 0)
    pygame.display.gl_set_attribute(SDL_GL_FLOATBUFFERS, 1 if hdr else 0)


def framebuffer_is_float():
    try:
        return bool(glGetBooleanv(GL_RGBA_FLOAT_MODE_ARB))
    except Exception:
        return False


# ---------------------------------------------------------------- presenter
_VERTEX = """#version 120
varying vec2 uv;
void main() {
    uv = gl_MultiTexCoord0.xy;
    gl_Position = gl_Vertex;
}
"""

_FRAGMENT = """#version 120
uniform sampler2D scene;
uniform float scale;
varying vec2 uv;
void main() {
    vec3 c = texture2D(scene, uv).rgb;
    // SDR to linear light with a 2.2 gamma (deep blacks, like an SDR monitor),
    // then to scRGB where 1.0 is 80 nits
    gl_FragColor = vec4(pow(c, vec3(2.2)) * scale, 1.0);
}
"""


class HDRPresenter:
    """Renders the frame offscreen, then writes it to the float window as scRGB."""

    def __init__(self, width, height, paper_white=PAPER_WHITE_DEFAULT):
        self.width, self.height = int(width), int(height)
        self.paper_white = float(paper_white)
        self.program = shaders.compileProgram(shaders.compileShader(_VERTEX, GL_VERTEX_SHADER),
                                              shaders.compileShader(_FRAGMENT, GL_FRAGMENT_SHADER))
        self._scale_loc = glGetUniformLocation(self.program, "scale")
        self._scene_loc = glGetUniformLocation(self.program, "scene")

        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, 0)

        self.depth = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, self.width, self.height)
        glBindRenderbuffer(GL_RENDERBUFFER, 0)

        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.texture, 0)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth)
        complete = glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        if not complete:
            self.delete()
            raise RuntimeError("HDR offscreen buffer is not supported")

    def begin(self):
        """Call before drawing a frame: everything renders into the offscreen buffer."""
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

    def end(self):
        """Call before flipping: convert the offscreen frame into the HDR window."""
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        viewport = glGetIntegerv(GL_VIEWPORT)
        glPushAttrib(GL_ENABLE_BIT)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_BLEND)
        glDisable(GL_CULL_FACE)
        glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glUseProgram(self.program)
        glUniform1f(self._scale_loc, self.paper_white / 80.0)
        glUniform1i(self._scene_loc, 0)
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
        glViewport(*[int(v) for v in viewport])

    def delete(self):
        for name, fn in (("fbo", glDeleteFramebuffers), ("depth", glDeleteRenderbuffers),
                         ("texture", glDeleteTextures)):
            obj = getattr(self, name, None)
            if obj:
                try:
                    fn(1, [obj])
                except Exception:
                    pass
                setattr(self, name, None)
        if getattr(self, "program", None):
            try:
                glDeleteProgram(self.program)
            except Exception:
                pass
            self.program = None


def create_presenter(width, height, paper_white):
    """A presenter if the current window really has a float framebuffer, else None."""
    if not framebuffer_is_float():
        return None
    try:
        return HDRPresenter(width, height, paper_white)
    except Exception as e:
        print(f"HDR output unavailable: {e}")
        return None
