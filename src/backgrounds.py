"""Procedural backgrounds.

Each style is computed by a shader for every direction around the camera. That is
done once, into a cube map, when the style is chosen; every frame then only reads
the cube map, adds the stars (computed live, one pixel sharp, twinkling) and a tiny
dither against 8-bit banding. The aurora's moving curtains live in a second, small
cube map that is refreshed one side per frame. Nothing is loaded from disk.
"""
import time

from OpenGL.GL import (
    GL_BLEND, GL_CLAMP_TO_EDGE, GL_COLOR_ATTACHMENT0, GL_COLOR_BUFFER_BIT, GL_CULL_FACE, GL_DEPTH_TEST,
    GL_DRAW_FRAMEBUFFER_BINDING, GL_FRAGMENT_SHADER, GL_FRAMEBUFFER, GL_FRAMEBUFFER_COMPLETE, GL_LIGHTING,
    GL_LINEAR, GL_QUADS, GL_READ_FRAMEBUFFER_BINDING, GL_DRAW_FRAMEBUFFER, GL_READ_FRAMEBUFFER, GL_RGBA,
    GL_RGBA8, GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE_CUBE_MAP, GL_TEXTURE_CUBE_MAP_POSITIVE_X,
    GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_WRAP_R, GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE, GL_VERTEX_SHADER, GL_VIEWPORT,
    glActiveTexture, glBegin, glBindFramebuffer, glBindTexture, glCheckFramebufferStatus, glClear,
    glClearColor, glDeleteFramebuffers, glDeleteProgram, glDeleteTextures, glDisable, glEnable, glEnd,
    glFramebufferTexture2D, glGenFramebuffers, glGenTextures, glGetIntegerv, glGetUniformLocation,
    glLoadIdentity, glPopMatrix, glPushMatrix, glRotatef, glTexImage2D, glTexParameteri, glUniform1f,
    glUniform1i, glUniform3f, glUseProgram, glVertex2f, glViewport,
)
from OpenGL.GL import shaders

GL_TEXTURE_CUBE_MAP_SEAMLESS = 0x884F

# Cube map side length relative to the height of the 3D view: about one texel per
# pixel (the view's 60 degree field covers a 90 degree cube face), capped for memory
BAKE_SCALE = 1.4
BAKE_MAX = 2048
LIGHT_SIZE = 256  # the aurora's soft curtains need little resolution

# (major axis, s axis, t axis) of each cube map face, in OpenGL's face order
_FACES = [
    ((1, 0, 0), (0, 0, -1), (0, -1, 0)),
    ((-1, 0, 0), (0, 0, 1), (0, -1, 0)),
    ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
    ((0, -1, 0), (1, 0, 0), (0, 0, -1)),
    ((0, 0, 1), (1, 0, 0), (0, -1, 0)),
    ((0, 0, -1), (-1, 0, 0), (0, -1, 0)),
]

# (id, label, category). The order of the real styles matches the shader's style index.
STYLES = [
    ("midnight", "Midnight", "Gradient"),
    ("dusk", "Dusk", "Gradient"),
    ("studio", "Studio", "Gradient"),
    ("nebula", "Nebula", "Semi-realistic"),
    ("aurora", "Aurora", "Semi-realistic"),
    ("daydream", "Daydream", "Cartoon"),
    ("planet", "Ringed planet", "Cartoon"),
    ("hills", "Sunset hills", "Cartoon"),
]
STYLE_IDS = [s[0] for s in STYLES]
AUTO = "auto"
DEFAULT_STYLE = AUTO

# Background per game mode when the style is "Match game mode"
MODE_STYLES = {
    "freeplay": "midnight",
    "easy": "aurora",
    "medium": "dusk",
    "hard": "nebula",
    "limited_time": "hills",
    "limited_moves": "daydream",
    "daily_cube": "planet",
}


def menu_items():
    """(label, id) pairs for the settings dropdown."""
    items = [("Match game mode", AUTO)]
    items += [(f"{label}  ({category.lower()})", sid) for sid, label, category in STYLES]
    return items


def resolve(choice, mode):
    if choice in STYLE_IDS:
        return choice
    return MODE_STYLES.get(mode, "midnight")


_QUAD_VERTEX = """#version 120
void main() {
    gl_Position = vec4(gl_Vertex.xy, 0.0, 1.0);
}
"""

# Bakes one cube map face: the style (layer 0) or the aurora's curtains (layer 1)
_BAKE_FRAGMENT = """#version 120
uniform int style;
uniform int layer;
uniform float time;
uniform float size;
uniform vec3 major;
uniform vec3 axisS;
uniform vec3 axisT;

// ---------------------------------------------------------------- noise
float hash13(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.zyx + 31.32);
    return fract((p.x + p.y) * p.z);
}
vec3 hash33(vec3 p) {
    p = fract(p * vec3(0.1031, 0.1030, 0.0973));
    p += dot(p, p.yxz + 33.33);
    return fract((p.xxy + p.yxx) * p.zyx);
}
float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), f.x),
                  mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), f.x), f.y);
    float b = mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), f.x),
                  mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), f.x), f.y);
    return mix(a, b, f.z);
}
float fbm(vec3 p, int octaves, float gain) {
    float s = 0.0;
    float a = 0.5;
    float norm = 0.0;
    for (int i = 0; i < 6; i++) {
        if (i >= octaves) break;
        s += a * noise(p);
        norm += a;
        p = p * 2.03 + vec3(1.7, 9.2, 3.1);
        a *= gain;
    }
    return s / norm;
}

// Anti-aliased step: 1 where x < edge, smooth over about one pixel
float fill(float x, float edge) {
    float w = max(fwidth(x), 1e-5);
    return 1.0 - smoothstep(edge - w, edge + w, x);
}

vec3 grad3(float t, vec3 a, vec3 b, vec3 c, float m) {
    // Smooth three stop gradient with no visible stop line
    vec3 lo = mix(a, b, smoothstep(0.0, m, t));
    return mix(lo, c, smoothstep(m * 0.5, 1.0, t));
}

// Silhouette height of a hill range around the horizon, seamless in every direction
float ridge(vec3 d, float base, float amp, float freq, float seed) {
    vec3 a = vec3(normalize(d.xz + 1e-5), 0.0).xzy * freq + seed;
    return base + amp * smoothstep(0.25, 0.75, fbm(a, 4, 0.5));
}

// ---------------------------------------------------------------- styles
// Each style returns the color and how visible stars are there (0 on the ground).
vec4 midnight(vec3 d) {
    float y = d.y;
    vec3 zen = vec3(0.012, 0.018, 0.055);
    vec3 hor = vec3(0.075, 0.105, 0.235);
    vec3 low = vec3(0.020, 0.026, 0.060);
    vec3 col = y > 0.0 ? mix(hor, zen, pow(smoothstep(0.0, 1.0, y), 0.55))
                       : mix(hor, low, pow(smoothstep(0.0, 1.0, -y), 0.45));
    col += vec3(0.05, 0.06, 0.12) * exp(-abs(y) * 9.0);           // horizon glow
    col *= 0.9 + 0.2 * fbm(d * 1.6, 3, 0.5);                       // large soft variation
    return vec4(col, 1.0);
}

vec4 dusk(vec3 d) {
    vec3 sun = normalize(vec3(0.0, 0.03, -1.0));
    float y = d.y;
    vec3 col;
    vec3 horizon = vec3(1.00, 0.62, 0.36);
    vec3 sky = grad3(pow(max(y, 0.0), 0.6), horizon, vec3(0.62, 0.30, 0.42), vec3(0.09, 0.08, 0.22), 0.55);
    // Hazy lowland: from the horizon color into a deep plum, blended in over a wide band
    vec3 low = grad3(pow(smoothstep(0.0, 0.9, -y), 0.6), horizon, vec3(0.38, 0.17, 0.27),
                     vec3(0.07, 0.04, 0.09), 0.5);
    col = mix(low, sky, smoothstep(-0.12, 0.06, y));
    float s = max(dot(d, sun), 0.0);
    col += vec3(1.0, 0.55, 0.25) * (pow(s, 6.0) * 0.30 + pow(s, 60.0) * 0.35) * smoothstep(-0.2, 0.05, y);
    return vec4(col, smoothstep(0.0, 0.2, y));
}

vec4 studio(vec3 d) {
    float y = d.y;
    // Cyclorama: a soft lit wall that curves into a darker floor, lit from above
    float wall = smoothstep(-0.55, 0.12, y);
    vec3 col = mix(vec3(0.030, 0.032, 0.038), vec3(0.150, 0.158, 0.175), wall);
    col = mix(col, vec3(0.060, 0.063, 0.072), smoothstep(0.1, 1.0, y));
    float spot = exp(-pow(length(d - normalize(vec3(0.0, 0.25, -1.0))) * 1.4, 2.0));
    col += vec3(0.08, 0.08, 0.085) * spot;
    float pool = smoothstep(-0.15, -0.95, y);
    col += vec3(0.075, 0.077, 0.085) * pool * pool;
    return vec4(col, 0.0);
}

vec4 nebula(vec3 d) {
    vec3 col = vec3(0.006, 0.008, 0.020);
    vec3 p = d * 2.2;
    float warp = fbm(p * 0.9 + 4.0, 3, 0.5);
    float n = fbm(p + warp * 1.4, 5, 0.52);
    float band = exp(-pow(dot(d, normalize(vec3(0.35, 1.0, 0.25))) / 0.55, 2.0));
    float dens = smoothstep(0.38, 0.85, n) * (0.35 + 0.65 * band);
    float hue = fbm(p * 0.6 + 11.0, 3, 0.5);
    vec3 c1 = vec3(0.55, 0.12, 0.42);
    vec3 c2 = vec3(0.10, 0.30, 0.62);
    vec3 c3 = vec3(0.95, 0.45, 0.35);
    vec3 neb = mix(c1, c2, smoothstep(0.35, 0.65, hue));
    neb = mix(neb, c3, smoothstep(0.72, 0.95, n) * 0.6);
    float dust = smoothstep(0.5, 0.75, fbm(p * 2.3 + 7.0, 4, 0.5));
    col += neb * dens * 0.75 * (1.0 - 0.6 * dust);
    col += vec3(0.05, 0.04, 0.09) * band;
    return vec4(col, 1.0 - 0.6 * dens);
}

// The aurora's curtains are the only moving part of any style: they are kept out of the
// baked sky and baked separately into a small cube map that refreshes all the time.
vec4 auroraLight(vec3 d) {
    float y = d.y;
    vec3 ring = vec3(normalize(d.xz + 1e-5), 0.0).xzy;
    // Curtains: a wavy base line, vertical rays, a bright lower edge fading upward
    float sway = fbm(ring * 1.3 + vec3(0.0, time * 0.02, 0.0), 3, 0.5);
    float base = 0.10 + 0.22 * sway;
    float h = y - base;
    float rays = fbm(ring * 7.0 + vec3(sway * 2.0, time * 0.05, 0.0), 3, 0.55);
    rays = smoothstep(0.35, 0.8, rays);
    float curtain = smoothstep(-0.015, 0.03, h) * exp(-max(h, 0.0) * 5.0);
    float region = smoothstep(0.25, 0.6, fbm(ring * 0.8 + 3.0, 2, 0.5));
    float a = curtain * (0.25 + 0.75 * rays) * region;
    vec3 green = vec3(0.10, 0.95, 0.55);
    vec3 violet = vec3(0.45, 0.20, 0.80);
    return vec4(mix(green, violet, smoothstep(0.0, 0.35, h)) * a * 0.65, a);
}

// Alpha: how open the sky is (0 behind mountains); the curtains and stars are scaled by it
vec4 auroraSky(vec3 d) {
    float y = d.y;
    vec3 col = mix(vec3(0.025, 0.060, 0.080), vec3(0.006, 0.012, 0.030), pow(smoothstep(-0.05, 1.0, y), 0.6));
    vec3 ring = vec3(normalize(d.xz + 1e-5), 0.0).xzy;
    float region = smoothstep(0.25, 0.6, fbm(ring * 0.8 + 3.0, 2, 0.5));
    col += vec3(0.02, 0.10, 0.08) * region * exp(-abs(y - 0.05) * 12.0);  // airglow
    // Mountains rising from the shore
    float land = fill(y, ridge(d, 0.0, 0.16, 2.4, 5.0));
    col = mix(col, vec3(0.012, 0.020, 0.028), land);
    return vec4(col, 1.0 - land);
}

vec4 aurora(vec3 d) {
    if (d.y >= 0.0) return auroraSky(d);
    // A still lake: the mirrored sky, darker toward your feet, with faint ripples
    vec3 m = vec3(d.x, -d.y, d.z);
    float ripple = (noise(vec3(d.xz / max(-d.y, 0.05) * 6.0, time * 0.15)) - 0.5) * 0.02;
    vec4 r = auroraSky(normalize(m + vec3(0.0, ripple, 0.0)));
    float fade = mix(0.55, 0.22, smoothstep(0.0, 0.8, -d.y));
    vec3 col = r.rgb * fade + vec3(0.004, 0.008, 0.012);
    return vec4(col, r.a * fade);
}

vec4 daydream(vec3 d) {
    float y = d.y;
    vec3 col = mix(vec3(0.66, 0.86, 1.00), vec3(0.20, 0.50, 0.92), pow(smoothstep(0.0, 1.0, y), 0.7));
    vec3 sunDir = normalize(vec3(-0.55, 0.45, -0.7));
    float sd = length(d - sunDir);
    col = mix(col, vec3(1.0, 0.97, 0.80), 0.35 * fill(sd, 0.22));
    col = mix(col, vec3(1.0, 0.93, 0.55), fill(sd, 0.11));
    // Puffy cartoon clouds: thresholded noise with a white top and a soft blue belly
    vec3 p = d * vec3(2.4, 5.5, 2.4) + vec3(time * 0.004, 0.0, 0.0);
    float band = smoothstep(0.02, 0.12, y) * smoothstep(0.75, 0.3, y);
    float c = fbm(p, 4, 0.45) * band;
    float top = fbm(p + vec3(0.0, 0.22, 0.0), 4, 0.45) * band;
    float cloud = 1.0 - fill(c, 0.50);
    float lit = fill(top, 0.50);
    vec3 cc = mix(vec3(0.80, 0.87, 0.97), vec3(1.0), lit);
    col = mix(col, cc, cloud);
    // Two rows of rounded hills, both standing on the horizon
    float far = ridge(d, 0.0, 0.13, 1.6, 2.0);
    float near = ridge(d, 0.0, 0.07, 2.6, 9.0);
    col = mix(col, vec3(0.42, 0.70, 0.52), fill(y, far));
    col = mix(col, vec3(0.30, 0.62, 0.30), fill(y, near));
    // Meadow: lighter in the distance, soft patches of darker grass up close
    if (y < 0.0) {
        vec3 grass = mix(vec3(0.36, 0.67, 0.34), vec3(0.24, 0.52, 0.22), smoothstep(0.0, 0.9, -y));
        float patches = 1.0 - smoothstep(0.38, 0.5, fbm(d * vec3(7.0, 12.0, 7.0) + 4.0, 3, 0.5));
        col = mix(grass, grass * 0.94, patches * smoothstep(0.0, 0.15, -y));
    }
    return vec4(col, 0.0);
}

vec4 planet(vec3 d) {
    float y = d.y;
    vec3 col = mix(vec3(0.20, 0.10, 0.34), vec3(0.07, 0.04, 0.15), pow(smoothstep(-1.0, 1.0, y), 0.8));
    float vis = 1.0;
    // Ringed planet, cel shaded with a dark outline
    vec3 P = normalize(vec3(-0.30, -0.28, -0.92));
    vec3 T = normalize(cross(P, vec3(0.0, 1.0, 0.0)));
    vec3 B = cross(T, P);
    float R = 0.17;
    if (dot(d, P) > 0.0) {
        vec2 q = vec2(dot(d, T), dot(d, B)) / R;
        float tilt = 0.35;
        vec2 qr = vec2(q.x * cos(tilt) - q.y * sin(tilt), q.x * sin(tilt) + q.y * cos(tilt));
        float rr = length(vec2(qr.x, qr.y / 0.26));
        float ring = fill(rr, 2.1) * (1.0 - fill(rr, 1.45)) * (1.0 - fill(abs(rr - 1.75), 0.04));
        vec3 ringCol = mix(vec3(0.98, 0.78, 0.55), vec3(0.85, 0.55, 0.45), step(1.75, rr));
        float r2 = dot(q, q);
        // Ring behind the planet
        col = mix(col, ringCol * 0.8, ring * step(0.0, qr.y));
        if (r2 < 1.15) {
            float disk = fill(sqrt(r2), 1.0);
            vec3 n = vec3(q, sqrt(max(1.0 - r2, 0.0)));
            float l = dot(n, normalize(vec3(-0.55, 0.45, 0.70)));
            float stripes = sin((q.y + 0.08 * sin(q.x * 4.0)) * 11.0);
            vec3 base = mix(vec3(0.95, 0.55, 0.40), vec3(0.85, 0.38, 0.45), fill(stripes, 0.0));
            vec3 shade = base * mix(0.55, 1.0, 1.0 - fill(l, 0.05));
            shade = mix(shade, vec3(1.0, 0.85, 0.70), 1.0 - fill(l, 0.72));
            float outline = fill(sqrt(r2), 1.0) * (1.0 - fill(sqrt(r2), 0.955));
            shade = mix(shade, vec3(0.10, 0.05, 0.16), outline);
            col = mix(col, shade, disk);
            vis *= 1.0 - disk;
        }
        // Ring in front of the planet
        col = mix(col, ringCol, ring * (1.0 - step(0.0, qr.y)));
        vis *= 1.0 - ring;
    }
    // Small moon
    vec3 M = normalize(vec3(-0.92, -0.10, -0.25));
    float md = length(d - M);
    if (md < 0.12) {
        vec3 MT = normalize(cross(M, vec3(0.0, 1.0, 0.0)));
        vec2 mq = vec2(dot(d - M, MT), dot(d - M, cross(MT, M))) / 0.06;
        float shadow = fill(length(mq - vec2(0.45, -0.3)), 1.0);
        vec3 moon = mix(vec3(0.92, 0.90, 1.0), vec3(0.52, 0.50, 0.72), shadow);
        float mdisk = fill(md, 0.06);
        col = mix(col, moon, mdisk);
        vis *= 1.0 - mdisk;
    }
    return vec4(col, vis);
}

vec4 hills(vec3 d) {
    float y = d.y;
    vec3 sunDir = normalize(vec3(0.15, 0.05, -1.0));
    vec3 col;
    if (y > -0.05) {
        float t = pow(clamp(y + 0.05, 0.0, 1.0), 0.65);
        col = grad3(t, vec3(1.00, 0.74, 0.42), vec3(0.93, 0.42, 0.45), vec3(0.24, 0.14, 0.40), 0.5);
    } else {
        col = vec3(1.00, 0.74, 0.42);
    }
    float sd = length(d - sunDir);
    col = mix(col, vec3(1.0, 0.88, 0.60), 0.25 * fill(sd, 0.30));
    col = mix(col, vec3(1.0, 0.92, 0.66), fill(sd, 0.16));
    float h1 = ridge(d, 0.0, 0.15, 1.5, 1.0);
    float h2 = ridge(d, 0.0, 0.10, 2.3, 6.0);
    float h3 = ridge(d, 0.0, 0.05, 3.1, 12.0);
    col = mix(col, vec3(0.62, 0.32, 0.46), fill(y, h1));
    col = mix(col, vec3(0.42, 0.20, 0.38), fill(y, h2));
    col = mix(col, vec3(0.22, 0.10, 0.25), fill(y, h3));
    if (y < 0.0) {
        vec3 ground = mix(vec3(0.22, 0.10, 0.25), vec3(0.10, 0.04, 0.12), smoothstep(0.0, 0.9, -y));
        float patches = 1.0 - smoothstep(0.38, 0.5, fbm(d * vec3(7.0, 12.0, 7.0) + 9.0, 3, 0.5));
        col = mix(ground, ground * 1.07, patches * smoothstep(0.0, 0.15, -y));
    }
    float sky = 1.0 - fill(y, h1);
    return vec4(col, sky * smoothstep(0.25, 0.6, y));
}

void main() {
    vec2 st = gl_FragCoord.xy / size * 2.0 - 1.0;
    vec3 d = normalize(major + axisS * st.x + axisT * st.y);
    vec4 s;
    if (layer == 1) s = auroraLight(d);
    else if (style == 0) s = midnight(d);
    else if (style == 1) s = dusk(d);
    else if (style == 2) s = studio(d);
    else if (style == 3) s = nebula(d);
    else if (style == 4) s = aurora(d);
    else if (style == 5) s = daydream(d);
    else if (style == 6) s = planet(d);
    else s = hills(d);
    // Stored in 8 bits: dither so slow gradients do not band
    vec2 fc = gl_FragCoord.xy + major.xy * 1931.0 + major.z * 977.0;
    float n = hash13(vec3(fc, 3.0)) + hash13(vec3(fc, 11.0)) - 1.0;
    gl_FragColor = vec4(clamp(s.rgb, 0.0, 1.0) + n / 255.0, clamp(s.a, 0.0, 1.0));
}
"""

_VERTEX = """#version 120
varying vec3 vDir;
void main() {
    // Unproject the far plane: with a rotation only modelview this is the world view direction
    vec4 w = gl_ModelViewProjectionMatrixInverse * vec4(gl_Vertex.xy, 1.0, 1.0);
    vDir = w.xyz / w.w;
    gl_Position = vec4(gl_Vertex.xy, 0.0, 1.0);
}
"""

_FRAGMENT = """#version 120
uniform samplerCube sky;
uniform samplerCube light;
uniform int aurora;
uniform float stars;
uniform float time;
varying vec3 vDir;

// ---------------------------------------------------------------- noise
float hash13(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.zyx + 31.32);
    return fract((p.x + p.y) * p.z);
}
vec3 hash33(vec3 p) {
    p = fract(p * vec3(0.1031, 0.1030, 0.0973));
    p += dot(p, p.yxz + 33.33);
    return fract((p.xxy + p.yxx) * p.zyx);
}
float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), f.x),
                  mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), f.x), f.y);
    float b = mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), f.x),
                  mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), f.x), f.y);
    return mix(a, b, f.z);
}
float fbm(vec3 p, int octaves, float gain) {
    float s = 0.0;
    float a = 0.5;
    float norm = 0.0;
    for (int i = 0; i < 6; i++) {
        if (i >= octaves) break;
        s += a * noise(p);
        norm += a;
        p = p * 2.03 + vec3(1.7, 9.2, 3.1);
        a *= gain;
    }
    return s / norm;
}

// Anti-aliased step: 1 where x < edge, smooth over about one pixel
float fill(float x, float edge) {
    float w = max(fwidth(x), 1e-5);
    return 1.0 - smoothstep(edge - w, edge + w, x);
}

vec3 grad3(float t, vec3 a, vec3 b, vec3 c, float m) {
    // Smooth three stop gradient with no visible stop line
    vec3 lo = mix(a, b, smoothstep(0.0, m, t));
    return mix(lo, c, smoothstep(m * 0.5, 1.0, t));
}

// Silhouette height of a hill range around the horizon, seamless in every direction
float ridge(vec3 d, float base, float amp, float freq, float seed) {
    vec3 a = vec3(normalize(d.xz + 1e-5), 0.0).xzy * freq + seed;
    return base + amp * smoothstep(0.25, 0.75, fbm(a, 4, 0.5));
}

// ---------------------------------------------------------------- stars
// Stars live on the faces of a cube map grid: one candidate per cell, kept away from
// the cell borders so none is ever cut. Their size follows the pixel footprint.
float starLayer(vec3 d, float pixel, float scale, float density, float bright) {
    vec3 a = abs(d);
    vec2 uv;
    float face;
    float major;
    if (a.x >= a.y && a.x >= a.z) { major = a.x; uv = d.yz / a.x; face = d.x > 0.0 ? 1.0 : 2.0; }
    else if (a.y >= a.z) { major = a.y; uv = d.xz / a.y; face = d.y > 0.0 ? 3.0 : 4.0; }
    else { major = a.z; uv = d.xy / a.z; face = d.z > 0.0 ? 5.0 : 6.0; }
    vec2 p = uv * scale;
    vec2 cell = floor(p);
    vec3 h = hash33(vec3(cell, face * 17.0 + scale));
    if (h.z > density) return 0.0;
    vec2 center = cell + 0.15 + 0.7 * h.xy;
    float px = max(pixel * scale / major, 1e-4);     // one pixel, in cell units
    float r = length(p - center) / px;               // distance in pixels
    float core = exp(-r * r * 1.1);
    float k = fract(h.z * 91.7 + h.x * 13.1);
    float twinkle = 0.85 + 0.15 * sin(time * (1.0 + 2.0 * k) + k * 40.0);
    return core * bright * (0.25 + 0.75 * k * k * k) * twinkle;
}

float starField(vec3 d) {
    // Pixel footprint from the direction itself: continuous across the cube map faces
    float pixel = length(fwidth(d));
    return starLayer(d, pixel, 55.0, 0.10, 0.75)
         + starLayer(d, pixel, 22.0, 0.10, 1.4)
         + starLayer(d, pixel, 8.0, 0.08, 2.2);
}

void main() {
    vec3 d = normalize(vDir);
    vec4 s = textureCube(sky, d);
    vec3 col = s.rgb;
    float vis = s.a;
    if (aurora == 1) {
        // Curtains, mirrored and rippling in the lake; masked by the mountains (sky alpha)
        vec3 ld = d;
        if (d.y < 0.0) {
            float ripple = (noise(vec3(d.xz / max(-d.y, 0.05) * 6.0, time * 0.15)) - 0.5) * 0.02;
            ld = normalize(vec3(d.x, -d.y, d.z) + vec3(0.0, ripple, 0.0));
        }
        vec4 l = textureCube(light, ld);
        col += l.rgb * s.a;
        vis = s.a * (1.0 - min(l.a * 1.5, 1.0));
    }

    if (stars > 0.5) {
        float lum = dot(col, vec3(0.299, 0.587, 0.114));
        col += vec3(0.92, 0.95, 1.0) * starField(d) * vis * (1.0 - smoothstep(0.12, 0.40, lum));
    }

    // Triangular dither of one 8-bit step: removes banding in slow gradients
    vec2 fc = gl_FragCoord.xy;
    float n = hash13(vec3(fc, 1.0)) + hash13(vec3(fc, 7.0)) - 1.0;
    gl_FragColor = vec4(clamp(col, 0.0, 1.0) + n / 255.0, 1.0);
}
"""


def _cube_map(size):
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_CUBE_MAP, tex)
    for i in range(6):
        glTexImage2D(GL_TEXTURE_CUBE_MAP_POSITIVE_X + i, 0, GL_RGBA8, size, size, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
    glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    for wrap in (GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_TEXTURE_WRAP_R):
        glTexParameteri(GL_TEXTURE_CUBE_MAP, wrap, GL_CLAMP_TO_EDGE)
    glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
    return tex


def _quad():
    glBegin(GL_QUADS)
    glVertex2f(-1, -1)
    glVertex2f(1, -1)
    glVertex2f(1, 1)
    glVertex2f(-1, 1)
    glEnd()


class Background:
    """Owns the background shaders and cube maps. Needs a current OpenGL context."""

    def __init__(self):
        self.style = "midnight"
        self.stars = True
        self._start = time.perf_counter()
        self.program = None
        self.bake_program = None
        self._sky = None           # (texture, size, style) of the baked sky
        self._light = None         # texture of the aurora's curtains
        self._light_face = 0
        self._fbo = None
        try:
            self.program = shaders.compileProgram(shaders.compileShader(_VERTEX, GL_VERTEX_SHADER),
                                                  shaders.compileShader(_FRAGMENT, GL_FRAGMENT_SHADER),
                                                  validate=False)
            self.bake_program = shaders.compileProgram(shaders.compileShader(_QUAD_VERTEX, GL_VERTEX_SHADER),
                                                       shaders.compileShader(_BAKE_FRAGMENT, GL_FRAGMENT_SHADER),
                                                       validate=False)
            self._loc = {n: glGetUniformLocation(self.program, n)
                         for n in ("sky", "light", "aurora", "stars", "time")}
            self._bake_loc = {n: glGetUniformLocation(self.bake_program, n)
                              for n in ("style", "layer", "time", "size", "major", "axisS", "axisT")}
            self._fbo = glGenFramebuffers(1)
            try:
                glEnable(GL_TEXTURE_CUBE_MAP_SEAMLESS)  # filter across face edges
            except Exception:
                pass
        except Exception as e:
            print(f"Background shader unavailable, using a plain color: {e}")
            self.program = None

    def _time(self):
        # Wrapped so float precision stays fine in long sessions
        return (time.perf_counter() - self._start) % 10000.0

    def _bake(self, texture, size, faces, layer):
        """Render the given faces of a cube map, keeping the caller's framebuffer and viewport."""
        draw_fbo = glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING)
        read_fbo = glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING)
        viewport = [int(v) for v in glGetIntegerv(GL_VIEWPORT)]
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)
        glViewport(0, 0, size, size)
        glUseProgram(self.bake_program)
        loc = self._bake_loc
        glUniform1i(loc["style"], STYLE_IDS.index(self.style))
        glUniform1i(loc["layer"], layer)
        glUniform1f(loc["time"], self._time() if layer == 1 else 0.0)
        glUniform1f(loc["size"], float(size))
        ok = True
        for i in faces:
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_CUBE_MAP_POSITIVE_X + i,
                                   texture, 0)
            if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
                ok = False
                break
            major, axis_s, axis_t = _FACES[i]
            glUniform3f(loc["major"], *major)
            glUniform3f(loc["axisS"], *axis_s)
            glUniform3f(loc["axisT"], *axis_t)
            _quad()
        glUseProgram(0)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, int(draw_fbo))
        glBindFramebuffer(GL_READ_FRAMEBUFFER, int(read_fbo))
        glViewport(*viewport)
        return ok

    def _prepare(self):
        """Bake the sky when the style or the view size changed; keep the curtains moving."""
        height = int(glGetIntegerv(GL_VIEWPORT)[3])
        size = max(256, min(BAKE_MAX, int(height * BAKE_SCALE)))
        if self._sky is None or self._sky[1:] != (size, self.style):
            if self._sky is not None:
                glDeleteTextures([self._sky[0]])
            texture = _cube_map(size)
            self._sky = (texture, size, self.style)
            if not self._bake(texture, size, range(6), 0):
                raise RuntimeError("cube map faces are not renderable")
        if self.style == "aurora":
            if self._light is None:
                self._light = _cube_map(LIGHT_SIZE)
                self._bake(self._light, LIGHT_SIZE, range(6), 1)
            else:
                self._bake(self._light, LIGHT_SIZE, [self._light_face], 1)
                self._light_face = (self._light_face + 1) % 6

    def draw(self, rotation_x, rotation_y):
        """Fill the screen with the sky as seen with the camera's rotation."""
        if self.program is not None:
            try:
                self._prepare()
            except Exception as e:
                print(f"Background bake failed, using a plain color: {e}")
                self.delete()
        if self.program is None:
            glClearColor(0.05, 0.06, 0.12, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)
            return
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_BLEND)
        glDisable(GL_CULL_FACE)
        glPushMatrix()
        glLoadIdentity()
        # Same rotation as the cube: the horizon is the cube's own horizontal plane
        glRotatef(rotation_x, 1, 0, 0)
        glRotatef(rotation_y, 0, 1, 0)
        glUseProgram(self.program)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_CUBE_MAP, self._sky[0])
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_CUBE_MAP, self._light or 0)
        glUniform1i(self._loc["sky"], 0)
        glUniform1i(self._loc["light"], 1)
        glUniform1i(self._loc["aurora"], 1 if self.style == "aurora" else 0)
        glUniform1f(self._loc["stars"], 1.0 if self.stars else 0.0)
        glUniform1f(self._loc["time"], self._time())
        _quad()
        glUseProgram(0)
        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        glPopMatrix()
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def delete(self):
        for tex in (self._sky[0] if self._sky else None, self._light):
            if tex:
                try:
                    glDeleteTextures([tex])
                except Exception:
                    pass
        self._sky = self._light = None
        if self._fbo:
            try:
                glDeleteFramebuffers(1, [self._fbo])
            except Exception:
                pass
            self._fbo = None
        for name in ("program", "bake_program"):
            prog = getattr(self, name)
            if prog:
                try:
                    glDeleteProgram(prog)
                except Exception:
                    pass
                setattr(self, name, None)
