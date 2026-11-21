#!/usr/bin/env python3
"""Entry for make.fun competition the-passport-page-of-a-countr-2-20261121-0318.

Writes one image, an invented passport spread, to /output/entry.png.

Pure Python 3 stdlib only (zlib for the PNG encoder): no network, no clock,
no randomness, no third-party packages, so the program runs byte-identically
in the grader's sandbox. Two runs produce the identical file.

The spread: the Republic of Meridia, an island nation that does not exist.
Left page -- data page: portrait, holder's details, machine-readable zone
with ICAO check digits. Right page -- visas and stamps: a Dravnian visa,
entry/exit stamps from three neighbouring countries, and an endorsement
stamp that reveals the place (re-entry by ferry only: Meridia has no
airport). Every date is consistent: the passport was issued 02 JUN 2023 and
expires 02 JUN 2033; every stamp falls between those dates, and the
Dravnian stay (12-28 SEP 2024) fits its 30-day visa.
"""

import math
import os
import struct
import zlib
from pathlib import Path

# ---------------------------------------------------------------- canvas

W, H = 1024, 640

PAPER_L = (243, 237, 218)   # left page paper
PAPER_R = (246, 240, 223)   # right page paper
INK = (31, 42, 68)          # document ink, dark navy
INK_SOFT = (74, 84, 110)    # secondary ink
RULE = (31, 42, 68)
FAINT = (196, 188, 164)     # faint background pattern
GOLD = (176, 132, 40)
SKIN = (217, 169, 134)
HAIR = (58, 46, 38)
JACKET = (51, 71, 94)
PHOTO_BG = (178, 190, 199)
STAMP_RED = (163, 59, 50)
STAMP_BLUE = (47, 93, 138)
STAMP_PURPLE = (107, 74, 138)


class Canvas:
    """An RGB raster; pixels are a bytearray, rows are W*3 bytes."""

    def __init__(self, w, h, fill=(255, 255, 255)):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(fill) * (w * h))

    def _off(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = self._off(x, y)
            self.px[o], self.px[o + 1], self.px[o + 2] = c

    def blend(self, x, y, c, a):
        """Blend colour c over the pixel with alpha a (0..255)."""
        if 0 <= x < self.w and 0 <= y < self.h and a:
            o = self._off(x, y)
            if a >= 255:
                self.px[o], self.px[o + 1], self.px[o + 2] = c
            else:
                ia = 255 - a
                self.px[o] = (c[0] * a + self.px[o] * ia) // 255
                self.px[o + 1] = (c[1] * a + self.px[o + 1] * ia) // 255
                self.px[o + 2] = (c[2] * a + self.px[o + 2] * ia) // 255

    def fill_rect(self, x0, y0, x1, y1, c):
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w, x1)
        y1 = min(self.h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for y in range(y0, y1):
            o = self._off(x0, y)
            self.px[o:o + len(row)] = row

    def hline(self, x0, x1, y, c, t=1):
        for yy in range(y, y + t):
            self.fill_rect(x0, yy, x1, yy + 1, c)

    def vline(self, x, y0, y1, c, t=1):
        for xx in range(x, x + t):
            self.fill_rect(xx, y0, xx + 1, y1, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.fill_rect(x, y, x + t, y + t, c)
            if x == x1 and y == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def rect(self, x0, y0, x1, y1, c, t=1):
        self.hline(x0, x1, y0, c, t)
        self.hline(x0, x1, y1 - t, c, t)
        self.vline(x0, y0, y1, c, t)
        self.vline(x1 - t, y0, y1, c, t)

    def _ellipse_rows(self, cx, cy, rx, ry):
        for dy in range(-ry, ry + 1):
            if ry == 0:
                continue
            v = 1.0 - (dy * dy) / float(ry * ry)
            if v < 0:
                continue
            dx = int(rx * math.sqrt(v))
            yield cy + dy, cx - dx, cx + dx

    def fill_ellipse(self, cx, cy, rx, ry, c):
        for y, x0, x1 in self._ellipse_rows(cx, cy, rx, ry):
            self.fill_rect(x0, y, x1 + 1, y + 1, c)

    def ellipse(self, cx, cy, rx, ry, c, t=1):
        for yy, x0, x1 in self._ellipse_rows(cx, cy, rx, ry):
            self.fill_rect(x0, yy, x0 + t, yy + 1, c)
            self.fill_rect(x1 - t + 1, yy, x1 + 1, yy + 1, c)

    def fill_circle(self, cx, cy, r, c):
        self.fill_ellipse(cx, cy, r, r, c)

    def circle(self, cx, cy, r, c, t=1):
        self.ellipse(cx, cy, r, r, c, t)

    def fill_polygon(self, pts, c):
        """Scanline polygon fill; pts is a list of (x, y)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.fill_rect(int(math.ceil(xs[i])), y,
                               int(math.floor(xs[i + 1])) + 1, y + 1, c)

    def polyline(self, pts, c, t=1):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], c, t)


# ------------------------------------------------------------------- font
# A 5x7 bitmap font, drawn from a table written for this entry.

def _g(*rows):
    return tuple(int(ch) for r in rows for ch in r)


FONT = {
    'A': _g("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': _g("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': _g("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': _g("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': _g("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': _g("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': _g("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': _g("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': _g("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': _g("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': _g("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': _g("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': _g("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': _g("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': _g("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': _g("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': _g("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': _g("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': _g("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': _g("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': _g("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': _g("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': _g("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': _g("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': _g("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': _g("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': _g("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': _g("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': _g("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': _g("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': _g("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': _g("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': _g("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': _g("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': _g("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': _g("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': _g("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': _g("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': _g("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    '-': _g("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '/': _g("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    '(': _g("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': _g("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    ':': _g("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "'": _g("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '&': _g("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    '<': _g("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    '>': _g("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    '+': _g("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    '!': _g("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': _g("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    '=': _g("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '%': _g("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '*': _g("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
    ';': _g("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    '"': _g("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
}


def text_width(s, scale, spacing=1):
    return len(s) * (5 * scale + spacing) - spacing


def draw_text(cv, x, y, s, scale, color, spacing=1, alpha=255):
    """Draw text on a Canvas (or Layer) at (x, y); y is the top row."""
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT[' '])
        for row in range(7):
            for col in range(5):
                if g[row * 5 + col]:
                    if scale == 1:
                        if alpha >= 255:
                            cv.set(cx + col, y + row, color)
                        else:
                            cv.blend(cx + col, y + row, color, alpha)
                    else:
                        for dy in range(scale):
                            for dx in range(scale):
                                if alpha >= 255:
                                    cv.set(cx + col * scale + dx,
                                           y + row * scale + dy, color)
                                else:
                                    cv.blend(cx + col * scale + dx,
                                             y + row * scale + dy, color, alpha)
        cx += 5 * scale + spacing
    return cx


def draw_text_center(cv, cx, y, s, scale, color, spacing=1, alpha=255):
    w = text_width(s, scale, spacing)
    draw_text(cv, cx - w // 2, y, s, scale, color, spacing, alpha)

# ------------------------------------------------------------------ layers
# Stamps are drawn on small RGBA layers, then pasted rotated onto the page,
# which is how a real rubber stamp lands: slightly tilted, ink uneven.

class Layer(Canvas):
    """A small canvas with a per-pixel alpha channel."""

    def __init__(self, w, h):
        super().__init__(w, h, fill=(0, 0, 0))
        self.alpha = bytearray(w * h)

    def set(self, x, y, c):
        """Canvas.set, but the pixel also becomes fully opaque."""
        self.set_a(x, y, c, 255)

    def blend(self, x, y, c, a):
        """Canvas.blend, but the pixel's alpha grows too."""
        self.blend_a(x, y, c, a)

    def set_a(self, x, y, c, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = self._off(x, y)
            self.px[o], self.px[o + 1], self.px[o + 2] = c
            self.alpha[y * self.w + x] = a

    def blend_a(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h and a:
            o = self._off(x, y)
            ia = 255 - a
            self.px[o] = (c[0] * a + self.px[o] * ia) // 255
            self.px[o + 1] = (c[1] * a + self.px[o + 1] * ia) // 255
            self.px[o + 2] = (c[2] * a + self.px[o + 2] * ia) // 255
            old = self.alpha[y * self.w + x]
            self.alpha[y * self.w + x] = min(255, old + a)

    def fill_rect_a(self, x0, y0, x1, y1, c, a=255):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.set_a(x, y, c, a)

    def ellipse_a(self, cx, cy, rx, ry, c, a=255, t=1):
        for yy, x0, x1 in self._ellipse_rows(cx, cy, rx, ry):
            for xx in range(x0, x0 + t):
                self.set_a(xx, yy, c, a)
            for xx in range(x1 - t + 1, x1 + 1):
                self.set_a(xx, yy, c, a)

    def fill_ellipse_a(self, cx, cy, rx, ry, c, a=255):
        for y, x0, x1 in self._ellipse_rows(cx, cy, rx, ry):
            for x in range(x0, x1 + 1):
                self.set_a(x, y, c, a)

    def line_a(self, x0, y0, x1, y1, c, a=255, t=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            for yy in range(y, y + t):
                for xx in range(x, x + t):
                    self.set_a(xx, yy, c, a)
            if x == x1 and y == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy


def paste_rotated(dst, layer, cx, cy, angle_deg, ink_alpha=200):
    """Paste a layer centred at (cx, cy), rotated by angle_deg, with ink
    alpha scaled by ink_alpha (stamps are never full-strength)."""
    th = math.radians(angle_deg)
    cos_t, sin_t = math.cos(th), math.sin(th)
    hw, hh = layer.w / 2.0, layer.h / 2.0
    # bounding box of the rotated layer
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    rx = [c[0] * cos_t - c[1] * sin_t for c in corners]
    ry = [c[0] * sin_t + c[1] * cos_t for c in corners]
    x0 = int(cx + min(rx)) - 1
    x1 = int(cx + max(rx)) + 1
    y0 = int(cy + min(ry)) - 1
    y1 = int(cy + max(ry)) + 1
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            dx, dy = x - cx, y - cy
            sx = dx * cos_t + dy * sin_t + hw
            sy = -dx * sin_t + dy * cos_t + hh
            ix, iy = int(sx), int(sy)
            if 0 <= ix < layer.w and 0 <= iy < layer.h:
                a = layer.alpha[iy * layer.w + ix]
                if a:
                    o = layer._off(ix, iy)
                    dst.blend(x, y, (layer.px[o], layer.px[o + 1], layer.px[o + 2]),
                              a * ink_alpha // 255)


def star_points(cx, cy, r_out, r_in, points=5, rot=-90.0):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180.0 / points)
        pts.append((int(cx + r * math.cos(a)), int(cy + r * math.sin(a))))
    return pts


# ------------------------------------------------------------------- MRZ
# ICAO 9303 check digits: weights 7, 3, 1; A-Z = 10-35, '<' = 0.

def mrz_check(s):
    total = 0
    for i, ch in enumerate(s):
        if ch == '<':
            v = 0
        elif ch.isdigit():
            v = int(ch)
        else:
            v = ord(ch) - ord('A') + 10
        total += v * (7, 3, 1)[i % 3]
    return str(total % 10)


def mrz_lines():
    line1 = "P<MER" + "VOSS<<ELENA<MARIS"
    line1 = line1 + "<" * (44 - len(line1))
    doc = "MD4829137"
    dob = "910314"      # 14 MAR 1991
    exp = "330602"      # 02 JUN 2033
    personal = "PORTANSELM<<<<"
    line2 = (doc + mrz_check(doc) + "MER" + dob + mrz_check(dob) + "F"
             + exp + mrz_check(exp) + personal + mrz_check(personal))
    line2 = line2 + mrz_check(line2)
    return line1, line2


# ------------------------------------------------------------- coat of arms
def draw_arms(cv, x, y, s):
    """Small shield with a star over three sea waves."""
    # shield outline: top edge straight, sides down, point at the bottom
    pts = [(x, y), (x + s, y), (x + s, y + int(s * 0.62)),
           (x + s // 2, y + s), (x, y + int(s * 0.62))]
    cv.fill_polygon(pts, (247, 243, 230))
    cv.polyline(pts + [pts[0]], INK, 2)
    cx, cy = x + s // 2, y + int(s * 0.30)
    cv.fill_polygon(star_points(cx, cy, s // 4, s // 10), GOLD)
    # three waves
    for k in range(3):
        wy = y + int(s * 0.62) + k * 5
        wave = []
        for xx in range(x + 4, x + s - 3, 4):
            wave.append((xx, wy + (3 if (xx // 4) % 2 == 0 else -1)))
        cv.polyline(wave, INK_SOFT, 1)


# ---------------------------------------------------------------- portrait
def draw_portrait(cv, x0, y0, x1, y1):
    """A stylised passport photograph: flat bands, head, hair, shoulders."""
    # background bands
    cv.fill_rect(x0, y0, x1, y0 + (y1 - y0) // 3, (188, 198, 206))
    cv.fill_rect(x0, y0 + (y1 - y0) // 3, x1, y0 + 2 * (y1 - y0) // 3,
                 (172, 184, 193))
    cv.fill_rect(x0, y0 + 2 * (y1 - y0) // 3, x1, y1, (158, 171, 181))
    cx = (x0 + x1) // 2
    # hair mass behind the head
    cv.fill_ellipse(cx, y0 + 78, 46, 58, HAIR)
    cv.fill_rect(cx - 46, y0 + 78, cx + 47, y0 + 148, HAIR)
    # shoulders / jacket
    cv.fill_polygon([(x0 + 6, y1), (x0 + 6, y0 + 148), (cx - 26, y0 + 132),
                     (cx + 26, y0 + 132), (x1 - 6, y0 + 148), (x1 - 6, y1)],
                    JACKET)
    # shirt V and collar
    cv.fill_polygon([(cx - 16, y0 + 136), (cx + 16, y0 + 136),
                     (cx, y0 + 168)], (238, 234, 222))
    # neck
    cv.fill_rect(cx - 11, y0 + 112, cx + 12, y0 + 138, SKIN)
    # head
    cv.fill_ellipse(cx, y0 + 82, 33, 41, SKIN)
    # hair fringe over the forehead
    cv.fill_polygon([(cx - 33, y0 + 78), (cx - 30, y0 + 46), (cx - 12, y0 + 38),
                     (cx + 10, y0 + 40), (cx + 28, y0 + 50), (cx + 33, y0 + 78),
                     (cx + 24, y0 + 62), (cx, y0 + 56), (cx - 24, y0 + 62)],
                    HAIR)
    # ears
    cv.fill_ellipse(x0 + 38, y0 + 84, 5, 8, SKIN)
    cv.fill_ellipse(x1 - 38, y0 + 84, 5, 8, SKIN)
    # brows, eyes, nose, mouth
    cv.line(cx - 20, y0 + 74, cx - 8, y0 + 72, HAIR, 2)
    cv.line(cx + 8, y0 + 72, cx + 20, y0 + 74, HAIR, 2)
    cv.fill_ellipse(cx - 14, y0 + 80, 4, 3, (38, 32, 28))
    cv.fill_ellipse(cx + 14, y0 + 80, 4, 3, (38, 32, 28))
    cv.line(cx, y0 + 82, cx - 2, y0 + 96, (178, 128, 96), 2)
    cv.line(cx - 8, y0 + 106, cx + 8, y0 + 106, (138, 74, 58), 2)
    # faint print grain, like a photograph's texture
    for yy in range(y0 + 4, y1 - 4, 6):
        for xx in range(x0 + 2, x1 - 2):
            cv.blend(xx, yy, (255, 255, 255), 14)
    cv.rect(x0, y0, x1, y1, INK, 2)

# ------------------------------------------------------------------ stamps

def oval_stamp(lines, color, w=210, h=120):
    """A border-control stamp: double oval border, centred lines."""
    ly = Layer(w, h)
    ly.ellipse_a(w // 2, h // 2, w // 2 - 3, h // 2 - 3, color, 255, 3)
    ly.ellipse_a(w // 2, h // 2, w // 2 - 9, h // 2 - 9, color, 255, 1)
    y = 14
    for i, (txt, sc) in enumerate(lines):
        draw_text_center(ly, w // 2, y, txt, sc, color, spacing=1)
        y += 7 * sc + 6
        if i == 0:
            ly.line_a(14, y - 2, w - 14, y - 2, color, 255, 1)
            y += 4
    return ly


def rect_stamp(lines, color, w=300, h=64):
    """A rectangular endorsement stamp."""
    ly = Layer(w, h)
    for t in (0, 1):
        x0, y0, x1, y1 = 3 + t * 4, 3 + t * 4, w - 3 - t * 4, h - 3 - t * 4
        for xx in range(x0, x1):
            ly.set_a(xx, y0, color)
            ly.set_a(xx, y1 - 1, color)
        for yy in range(y0, y1):
            ly.set_a(x0, yy, color)
            ly.set_a(x1 - 1, yy, color)
    y = 10
    for txt, sc in lines:
        draw_text_center(ly, w // 2, y, txt, sc, color, spacing=1)
        y += 7 * sc + 5
    return ly


# ------------------------------------------------------------------- pages

def guilloche(cv, cx, cy):
    """Faint concentric arcs behind the page, like security printing."""
    for r in (120, 180, 240, 300):
        for deg in range(0, 360, 2):
            a = math.radians(deg)
            x = int(cx + r * math.cos(a))
            y = int(cy + r * math.sin(a))
            cv.blend(x, y, FAINT, 60)


def field(cv, x, y, label, value, vscale=2, width=260):
    draw_text(cv, x, y, label, 1, INK_SOFT, spacing=1)
    draw_text(cv, x, y + 11, value, vscale, INK, spacing=1)


def draw_left_page(cv):
    x0, x1 = 16, 496
    cv.fill_rect(x0, 16, x1, 624, PAPER_L)
    guilloche(cv, 256, 320)
    # header: arms + country name
    draw_arms(cv, 40, 34, 44)
    draw_text(cv, 100, 40, "REPUBLIC OF MERIDIA", 3, INK, spacing=2)
    draw_text(cv, 100, 66, "PASSPORT", 2, INK, spacing=6)
    draw_text(cv, 330, 66, "TYPE P   CODE MER", 1, INK_SOFT, spacing=1)
    cv.hline(40, 472, 96, RULE, 2)
    cv.hline(40, 472, 100, RULE, 1)
    # photo
    draw_portrait(cv, 44, 118, 194, 308)
    # signature under the photo
    cv.polyline([(56, 330), (72, 322), (86, 332), (100, 320), (118, 330),
                 (132, 322), (150, 330), (168, 324), (182, 330)], INK, 2)
    cv.hline(48, 190, 340, RULE, 1)
    draw_text(cv, 48, 346, "SIGNATURE OF BEARER", 1, INK_SOFT, spacing=1)
    # holder's fields, right of the photo
    fx = 214
    field(cv, fx, 118, "SURNAME", "VOSS")
    field(cv, fx, 162, "GIVEN NAMES", "ELENA MARIS")
    field(cv, fx, 206, "NATIONALITY", "MERIDIAN")
    field(cv, fx, 250, "DATE OF BIRTH", "14 MAR 1991")
    field(cv, fx, 294, "PLACE OF BIRTH", "PORT ANSELM")
    field(cv, fx, 338, "SEX", "F")
    # issue block, two rows of two columns across the page
    cv.hline(40, 472, 372, RULE, 1)
    field(cv, 40, 384, "DATE OF ISSUE", "02 JUN 2023")
    field(cv, 260, 384, "DATE OF EXPIRY", "02 JUN 2033")
    field(cv, 40, 424, "AUTHORITY", "PORT ANSELM")
    field(cv, 260, 424, "PASSPORT NO.", "MD 4829137")
    # machine-readable zone
    cv.hline(40, 472, 458, RULE, 1)
    line1, line2 = mrz_lines()
    draw_text(cv, 36, 470, line1, 2, INK, spacing=0)
    draw_text(cv, 36, 488, line2, 2, INK, spacing=0)
    # footer
    draw_text(cv, 40, 560, "THIS PASSPORT REMAINS THE PROPERTY OF", 1,
              INK_SOFT, spacing=1)
    draw_text(cv, 40, 574, "THE REPUBLIC OF MERIDIA.", 1, INK_SOFT, spacing=1)
    draw_text(cv, 448, 592, "1", 2, INK_SOFT, spacing=1)


def draw_right_page(cv):
    x0, x1 = 528, 1008
    cv.fill_rect(x0, 16, x1, 624, PAPER_R)
    guilloche(cv, 768, 320)
    # diagonal watermark
    wm = Layer(420, 90)
    draw_text(wm, 0, 20, "MERIDIA", 6, (196, 188, 164), spacing=4)
    paste_rotated(cv, wm, 768, 320, -28, ink_alpha=70)
    # header
    draw_text(cv, 560, 40, "VISAS", 3, INK, spacing=4)
    draw_text(cv, 800, 48, "PAGES 2 - 3", 1, INK_SOFT, spacing=1)
    cv.hline(560, 976, 96, RULE, 2)
    cv.hline(560, 976, 100, RULE, 1)
    # Dravnian visa sticker
    vx0, vy0, vx1, vy1 = 560, 118, 792, 236
    cv.fill_rect(vx0, vy0, vx1, vy1, (226, 232, 238))
    cv.rect(vx0, vy0, vx1, vy1, STAMP_BLUE, 2)
    cv.rect(vx0 + 5, vy0 + 5, vx1 - 5, vy1 - 5, STAMP_BLUE, 1)
    draw_text_center(cv, (vx0 + vx1) // 2, vy0 + 12, "KINGDOM OF DRAVNIA", 2,
                     STAMP_BLUE, spacing=1)
    draw_text_center(cv, (vx0 + vx1) // 2, vy0 + 32, "VISA", 3, STAMP_BLUE,
                     spacing=8)
    cv.hline(vx0 + 14, vx1 - 14, vy0 + 60, STAMP_BLUE, 1)
    draw_text(cv, vx0 + 16, vy0 + 68, "SINGLE ENTRY - 30 DAYS", 1, INK, spacing=1)
    draw_text(cv, vx0 + 16, vy0 + 82, "FEE 40 DRV PAID", 1, INK, spacing=1)
    draw_text(cv, vx0 + 16, vy0 + 96, "ISSUED 28 AUG 2024", 1, INK, spacing=1)
    # stamps: Dravnia in/out, Kessaly in, Tarnovia in
    paste_rotated(cv, oval_stamp([
        ("DRAVNIA", 2), ("ENTRY", 2), ("12 SEP 2024", 1),
        ("PORT ANSELM FERRY", 1)], STAMP_PURPLE), 660, 320, -10)
    paste_rotated(cv, oval_stamp([
        ("DRAVNIA", 2), ("EXIT", 2), ("28 SEP 2024", 1),
        ("PORT ANSELM FERRY", 1)], STAMP_PURPLE), 880, 330, 8)
    paste_rotated(cv, oval_stamp([
        ("KESSALY", 2), ("ENTRY", 2), ("03 MAR 2025", 1),
        ("HARBOUR GATE 2", 1)], STAMP_BLUE), 660, 470, -6)
    paste_rotated(cv, oval_stamp([
        ("TARNOVIA", 2), ("ENTRY", 2), ("17 JUN 2025", 1),
        ("NORTH QUAY", 1)], STAMP_RED), 880, 480, 12)
    # endorsement: the telling detail -- re-entry by ferry only
    paste_rotated(cv, rect_stamp([
        ("ENDORSEMENT", 2),
        ("RE-ENTRY TO MERIDIA BY FERRY ONLY", 1)], STAMP_RED), 768, 566, -3)
    # small island map, top right
    mx, my = 820, 128
    cv.fill_polygon([(mx, my + 44), (mx + 26, my + 8), (mx + 58, my + 2),
                     (mx + 88, my + 18), (mx + 96, my + 44), (mx + 70, my + 62),
                     (mx + 34, my + 60)], (214, 226, 220))
    cv.polyline([(mx, my + 44), (mx + 26, my + 8), (mx + 58, my + 2),
                 (mx + 88, my + 18), (mx + 96, my + 44), (mx + 70, my + 62),
                 (mx + 34, my + 60), (mx, my + 44)], INK_SOFT, 1)
    cv.fill_polygon(star_points(mx + 52, my + 34, 7, 3), GOLD)
    draw_text(cv, mx + 66, my + 28, "PORT ANSELM", 1, INK, spacing=1)
    draw_text(cv, mx, my + 70, "MERIDIA  12 14 S  44 02 E", 1, INK_SOFT,
              spacing=1)
    # footer
    draw_text(cv, 560, 612,
              "IF FOUND PLEASE RETURN TO THE NEAREST MERIDIAN CONSULATE.",
              1, INK_SOFT, spacing=1)
    draw_text(cv, 958, 606, "2", 2, INK_SOFT, spacing=1)


# -------------------------------------------------------------------- PNG

def write_png(path, cv):
    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))
    Path(path).write_bytes(data)
    return len(data)


def build():
    cv = Canvas(W, H, fill=(226, 220, 200))
    # outer frame and spine
    cv.fill_rect(8, 8, 1016, 632, (58, 52, 44))
    draw_left_page(cv)
    draw_right_page(cv)
    cv.fill_rect(508, 16, 516, 624, (120, 110, 92))
    cv.vline(508, 16, 624, (58, 52, 44), 1)
    cv.vline(515, 16, 624, (58, 52, 44), 1)
    cv.rect(8, 8, 1016, 632, INK, 2)
    return cv


def main():
    out_dir = Path(os.environ.get("OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    cv = build()
    path = out_dir / "entry.png"
    size = write_png(path, cv)
    print(f"wrote {path} {cv.w}x{cv.h} {size} bytes")


if __name__ == "__main__":
    main()
