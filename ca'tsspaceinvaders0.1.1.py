#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cats's space invaders 0.1
A.C Holdings / Team Flames - single-file, pygame-ce, 60 FPS fixed timestep.

Engine ("famicom-style"):
  * PPU-ish  : 224x256 native framebuffer (arcade portrait res), NES 2C02 palette,
               cellophane colour-overlay bands multiplied over a 1-bit scene,
               integer scaling + optional CRT scanlines.
  * APU-ish  : runtime-synthesised pulse (12.5/25/50% duty, 4-bit volume steps),
               32-step triangle, 15-bit LFSR noise using the NTSC noise period
               table. Every sound is generated at boot - no asset files.
  * Physics  : fixed 60 Hz step, per-pixel sprite masks, per-pixel destructible
               shields + ground line, shot-vs-shot collisions.
  * Rules    : one invader moves per frame (natural speed-up + ragged rack),
               4-note march with count-based tempo, 3 alien shot types
               (rolling = aimed, plunger/squiggly = column tables), score-based
               reload rate, UFO every 1536 frames with shot-count score table
               (23rd shot = 300), extra life at 1500, lowering wave starts.

Controls: LEFT/RIGHT or A/D move, SPACE/Z/X fire, ENTER/1 start,
          P pause, M mute, C CRT scanlines, F11 fullscreen, ESC quit.
          Gamepad: d-pad/stick move, button 0/1 fire, start/7/9 start.
Run:      python Program.py            (python Program.py --autotest = headless bot)
"""
import os
import sys
import math
import array
import random

try:
    import pygame
except ImportError:  # tkinter fallback just to tell the user what's missing
    try:
        import tkinter as tk
        from tkinter import messagebox
        _r = tk.Tk(); _r.withdraw()
        messagebox.showerror("cats's space invaders 0.1",
                             "pygame-ce is required.\n\npip install pygame-ce")
    except Exception:
        pass
    print("pygame-ce is required:  pip install pygame-ce")
    sys.exit(1)

TITLE = "cats's space invaders 0.1"
W, H = 224, 256
SCALE = 3
FPS = 60

# ---------------------------------------------------------------- palette ---
# NES 2C02 palette entries (recalled from the common nesdev "2C02" palette)
NES_PAL = {
    0x0F: (0x00, 0x00, 0x00),  # black
    0x30: (0xFF, 0xFE, 0xFF),  # white
    0x16: (0xB5, 0x31, 0x20),  # red
    0x2A: (0x5C, 0xE4, 0x30),  # green
    0x27: (0xEA, 0x9E, 0x22),  # orange
    0x21: (0x64, 0xB0, 0xFF),  # sky blue
}
BLACK = NES_PAL[0x0F]
WHITE = NES_PAL[0x30]

# --------------------------------------------------------------- layout -----
PLAYER_Y = 216
PLAYER_MIN_X, PLAYER_MAX_X = 16, W - 16 - 13
PLAYER_START_X = 16
SHIELD_Y = 192
GROUND_Y = 239
UFO_Y = 40
TOP_LIMIT = 32
RACK_LEFT, RACK_RIGHT = 8, W - 8
RACK_START_X = 24
WAVE_BOTTOM_Y = 128
WAVE_DROP = (0, 16, 24, 32, 32, 32, 40, 40, 40)

# Alien fire column table (1-based columns). Recalled from the Space Invaders
# disassembly (computerarcheology "ColFireTable") - plunger reads [0..15],
# squiggly reads [6..20]. Not byte-verified against a ROM dump.
COL_TABLE = (1, 7, 1, 1, 1, 4, 11, 1, 6, 3, 1, 1, 11, 9, 2, 8,
             2, 11, 4, 7, 10)
# Reload frames by score threshold (recalled: thresholds 200/1000/2000/3000).
RELOAD = ((200, 48), (1000, 16), (2000, 11), (3000, 8), (10 ** 9, 7))
# March note delay by invaders remaining (recalled SoundDelayKey/Value tables).
MARCH_KEYS = (50, 43, 36, 28, 22, 17, 13, 10, 8, 7, 6, 5, 4, 3, 2, 1)
MARCH_VALS = (52, 46, 39, 34, 28, 24, 21, 19, 16, 14, 13, 12, 11, 9, 7, 5)
# UFO score table, indexed by shots fired % 15 (gives 300 on the 23rd shot).
UFO_TABLE = (100, 50, 50, 100, 150, 100, 100, 50, 300, 100, 100, 100, 50, 150, 100)
UFO_PERIOD = 1536
EXTRA_LIFE = 1500
POINTS = (30, 20, 10)

# --------------------------------------------------------------- sprites ----
# Original cat-themed designs for this game (not the arcade bitmaps).
KITTEN = (
    ["#......#", "##....##", "########", "#.####.#",
     "########", ".#.##.#.", "#......#", ".#....#."],
    ["#......#", "##....##", "########", "#.####.#",
     "########", "..#..#..", ".#.##.#.", "#......#"],
)
CAT = (
    ["#.........#", "##.......##", "###########", "##..###..##",
     "###########", "###.###.###", ".#.#...#.#.", "#.........#"],
    ["#.........#", "##.......##", "###########", "##..###..##",
     "###########", "####...####", "..#.....#..", ".#.......#."],
)
BIGCAT = (
    [".#........#.", "###......###", "############", "###..##..###",
     "############", "#.########.#", "#.#......#.#", "...##..##..."],
    [".#........#.", "###......###", "############", "###..##..###",
     "############", "..########..", ".##.#..#.##.", "##........##"],
)
PLAYER = ["......#......", ".....###.....", "..#..###..#..", ".###########.",
          "#############", "##.#######.##", "#############", ".#.#.#.#.#.#."]
PLAYER_BOOM = (
    [".....#..........", "..#.....#..#....", "......#.#.......", "..#..##.....#...",
     "....#####..#....", ".#.#######.#....", "..#########..#..", "################"],
    ["..#.........#...", "........#.......", "#..#..#....#...#", "......##..#.....",
     "...######.......", "..#########..#..", ".###########.#..", "################"],
)
ALIEN_BOOM = ["....#...#....", ".#...#.#...#.", "..#.......#..", "...#.....#...",
              "##.........##", "...#.....#...", "..#..#.#..#..", ".#..#...#..#."]
UFO = ["......####......", "...##########...", "..############..",
       ".##.##.##.##.##.", "################", "..###..##..###..", "...#........#..."]
UFO_BOOM = ["#..#....#..#..#.", "..#..#.#..#.#...", ".#..#######..#..", "...###########..",
            "#.###.#.#.###..#", "..###########...", ".#..#######..#..", "#..#...#...#..#."]
SHOT_BLAST = ["#..#..#.", ".#...#..", "..####.#", "#.#####.",
              ".######.", "#.####.#", ".#..#..#", "#..#..#."]
TOP_BLAST = ["#...#..#", "..#...#.", ".######.", "########",
             ".######.", "..#..#..", "#..#...#", "........"]
ASHOTS = (
    (  # rolling (aimed)
        [".#.", ".#.", ".##", ".#.", "##.", ".#.", ".#."],
        [".#.", ".##", ".#.", ".#.", ".#.", "##.", ".#."],
        [".#.", ".#.", "##.", ".#.", ".##", ".#.", ".#."],
        [".#.", "##.", ".#.", ".#.", ".#.", ".##", ".#."],
    ),
    (  # plunger
        ["###", ".#.", ".#.", ".#.", ".#.", ".#.", ".#."],
        [".#.", ".#.", "###", ".#.", ".#.", ".#.", ".#."],
        [".#.", ".#.", ".#.", ".#.", "###", ".#.", ".#."],
        [".#.", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    ),
    (  # squiggly
        [".#.", "#..", ".#.", "..#", ".#.", "#..", ".#."],
        ["#..", ".#.", "..#", ".#.", "#..", ".#.", "..#"],
        [".#.", "..#", ".#.", "#..", ".#.", "..#", ".#."],
        ["..#", ".#.", "#..", ".#.", "..#", ".#.", "#.."],
    ),
)

# 5x7 font, 7 rows per glyph, 5-bit rows as hex pairs (MSB = leftmost pixel)
FONT_HEX = {
    "0": "0E11131519110E", "1": "040C040404040E", "2": "0E11010204081F",
    "3": "1F02040201110E",
    "4": "02060A121F0202", "5": "1F101E0101110E", "6": "0608101E11110E",
    "7": "1F010204080808", "8": "0E11110E11110E", "9": "0E11110F01020C",
    "A": "0E1111111F1111", "B": "1E11111E11111E", "C": "0E11101010110E",
    "D": "1C12111111121C",
    "E": "1F10101E10101F", "F": "1F10101E101010", "G": "0E11101711110F",
    "H": "1111111F111111", "I": "0E04040404040E", "J": "0702020202120C",
    "K": "11121418141211", "L": "1010101010101F", "M": "111B1515111111",
    "N": "11111915131111", "O": "0E11111111110E", "P": "1E11111E101010",
    "Q": "0E11111115120D", "R": "1E11111E141211", "S": "0F10100E01011E",
    "T": "1F040404040404", "U": "1111111111110E", "V": "11111111110A04",
    "W": "1111111515150A", "X": "11110A040A1111", "Y": "1111110A040404",
    "Z": "1F01020408101F", " ": "00000000000000", "-": "0000001F000000",
    "<": "02040810080402", ">": "08040201020408", "=": "00001F001F0000",
    "?": "0E110102040004", ".": "00000000000C0C", "*": "0004150E150400",
    "'": "04040800000000", "!": "04040404040004", "(": "02040808080402",
    ")": "08040202020408", "/": "01010204081010", ":": "000C0C000C0C00",
}


class Sprite:
    __slots__ = ("surf", "w", "h", "bits", "px")

    def __init__(self, rows, color=WHITE):
        self.h = len(rows)
        self.w = max(len(r) for r in rows)
        self.surf = pygame.Surface((self.w, self.h))
        self.surf.fill(BLACK)
        self.surf.set_colorkey(BLACK)
        self.px = []
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c == "#":
                    self.px.append((x, y))
                    self.surf.set_at((x, y), color)
        self.bits = frozenset(self.px)


class Font:
    def __init__(self):
        self.glyphs = {}
        for ch, hx in FONT_HEX.items():
            s = pygame.Surface((5, 7))
            s.fill(BLACK)
            s.set_colorkey(BLACK)
            for y in range(7):
                row = int(hx[y * 2:y * 2 + 2], 16)
                for x in range(5):
                    if row & (0x10 >> x):
                        s.set_at((x, y), WHITE)
            self.glyphs[ch] = s

    def draw(self, surf, text, x, y, limit=None):
        if limit is not None:
            text = text[:max(0, limit)]
        for i, ch in enumerate(text.upper()):
            g = self.glyphs.get(ch, self.glyphs["?"])
            surf.blit(g, (x + i * 6, y))

    @staticmethod
    def width(text):
        return len(text) * 6 - 1

    def center(self, surf, text, y, limit=None):
        self.draw(surf, text, (W - self.width(text)) // 2, y, limit)


# ------------------------------------------------------------------- APU ----
class APU:
    """Famicom-flavoured synth. All sounds rendered once at startup."""
    CPU_HZ = 1789773
    NOISE_PERIODS = (4, 8, 16, 32, 64, 96, 128, 160, 202, 254,
                     380, 508, 762, 1016, 2034, 4068)  # NTSC noise timer table
    TRI_SEQ = tuple(list(range(15, -1, -1)) + list(range(0, 16)))

    def __init__(self):
        self.ok = False
        self.muted = False
        self.snd = {}
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            fq, _sz, ch = pygame.mixer.get_init()
            self.rate, self.chans = fq, ch
            pygame.mixer.set_num_channels(10)
            pygame.mixer.set_reserved(3)  # 0 march, 1 ufo loop, 2 player shot
            self._build()
            self.ok = True
        except Exception as e:  # no audio device: run silent
            print("audio disabled:", e)

    # --- channel generators (return float lists in -1..1) ---
    def _n(self, dur):
        return max(1, int(self.rate * dur))

    def pulse(self, f0, f1, dur, duty=0.5, vol=1.0, decay=1.0, vib=0.0, vib_hz=0.0):
        n, r = self._n(dur), self.rate
        out = [0.0] * n
        ph = 0.0
        ratio = f1 / f0
        for i in range(n):
            t = i / n
            f = f0 * (ratio ** t)
            if vib:
                f *= 1.0 + vib * math.sin(2 * math.pi * vib_hz * i / r)
            ph = (ph + f / r) % 1.0
            e = 1.0 - decay * t
            v = round(vol * e * 15) / 15.0  # 4-bit envelope like the APU
            out[i] = v if ph < duty else -v
        return out

    def triangle(self, f, dur, vol=1.0):
        n, r = self._n(dur), self.rate
        out = [0.0] * n
        ph = 0.0
        tail = max(1, int(r * 0.01))
        for i in range(n):
            ph = (ph + f / r) % 1.0
            v = self.TRI_SEQ[int(ph * 32)] / 7.5 - 1.0
            g = vol if i < n - tail else vol * (n - i) / tail
            out[i] = v * g
        return out

    def noise(self, dur, p0, p1=None, mode=0, vol=1.0, decay=1.0):
        n = self._n(dur)
        p1 = p0 if p1 is None else p1
        step = self.CPU_HZ / self.rate
        out = [0.0] * n
        lfsr, acc = 1, 0.0
        tap = 6 if mode else 1
        for i in range(n):
            t = i / n
            per = self.NOISE_PERIODS[int(round(p0 + (p1 - p0) * t))]
            acc += step
            while acc >= per:
                acc -= per
                fb = (lfsr ^ (lfsr >> tap)) & 1
                lfsr = (lfsr >> 1) | (fb << 14)
            v = round(vol * (1.0 - decay * t) * 15) / 15.0
            out[i] = -v if lfsr & 1 else v
        return out

    @staticmethod
    def mix(*tracks):
        n = max(len(t) for t in tracks)
        out = [0.0] * n
        for t in tracks:
            for i, v in enumerate(t):
                out[i] += v
        return out

    @staticmethod
    def cat(*tracks):
        out = []
        for t in tracks:
            out.extend(t)
        return out

    def make(self, samples, gain=0.3, fade=True):
        n = len(samples)
        fl = min(64, n) if fade else 0
        a = array.array("h")
        for i, s in enumerate(samples):
            if fl and i >= n - fl:
                s *= (n - i) / fl
            v = int(s * gain * 32767)
            a.append(32767 if v > 32767 else -32767 if v < -32767 else v)
        if self.chans == 2:
            b = array.array("h")
            for v in a:
                b.append(v); b.append(v)
            a = b
        return pygame.mixer.Sound(buffer=a.tobytes())

    def _build(self):
        s = self.snd
        # player shot: 12.5% pulse zap + hiss
        s["shoot"] = self.make(self.mix(
            self.pulse(1500, 220, 0.16, duty=0.125, vol=0.8),
            self.noise(0.12, 3, 6, vol=0.5)), 0.28)
        # invader hit: metallic noise burst + falling square
        s["inv_die"] = self.make(self.mix(
            self.noise(0.26, 2, 5, mode=1, vol=0.9),
            self.pulse(900, 120, 0.22, duty=0.25, vol=0.6)), 0.28)
        # player death: long rumbling noise
        s["player_die"] = self.make(self.mix(
            self.noise(1.1, 8, 13, vol=1.0, decay=0.9),
            self.noise(0.6, 4, 11, mode=1, vol=0.5)), 0.32, )
        # 4-note fleet march on the triangle (+ thin pulse for bite)
        for i, f in enumerate((98.0, 87.3, 77.8, 73.4)):
            s["march%d" % i] = self.make(self.mix(
                self.triangle(f, 0.09, vol=1.0),
                self.pulse(f, f, 0.05, duty=0.5, vol=0.35)), 0.45)
        # UFO warble loop: exactly 2 LFO cycles in 0.25 s so it loops cleanly
        s["ufo"] = self.make(self.pulse(560, 560, 0.25, duty=0.25, vol=0.55,
                                        decay=0.0, vib=0.35, vib_hz=8.0), 0.25, fade=False)
        # UFO destroyed: long descending warble
        s["ufo_hit"] = self.make(self.mix(
            self.pulse(1300, 180, 0.9, duty=0.5, vol=0.7, decay=0.7, vib=0.25, vib_hz=18),
            self.noise(0.35, 3, 9, mode=1, vol=0.4)), 0.28)
        # shot hits shield / ground / shot
        s["tick"] = self.make(self.noise(0.05, 5, 7, vol=0.6), 0.25)
        # extra life arpeggio
        s["extra"] = self.make(self.cat(*[
            self.pulse(f, f, 0.06, duty=0.25, vol=0.7, decay=0.3)
            for f in (523, 659, 784, 1047, 784, 1047, 1319)]), 0.25)
        # start jingle
        s["start"] = self.make(self.cat(*[
            self.pulse(f, f, 0.07, duty=0.5, vol=0.6, decay=0.4)
            for f in (262, 330, 392, 523)]), 0.22)

    def play(self, name, ch=None, loops=0):
        if not self.ok or self.muted:
            return
        snd = self.snd[name]
        if ch is None:
            snd.play()
        else:
            pygame.mixer.Channel(ch).play(snd, loops=loops)

    def stop(self, ch):
        if self.ok:
            pygame.mixer.Channel(ch).stop()


# ---------------------------------------------------------------- objects ---
class Alien:
    __slots__ = ("row", "col", "kind", "x", "y", "alive", "frame")

    def __init__(self, row, col, kind, x, y):
        self.row, self.col, self.kind = row, col, kind
        self.x, self.y = x, y
        self.alive = True
        self.frame = 0


def shield_on(x, y):
    if y < 4 and (x < 4 - y or x > 17 + y):
        return False
    if y >= 12:
        half = 4 if y == 12 else 5
        if 11 - half <= x < 11 + half:
            return False
    return True


# ------------------------------------------------------------------ game ----
class Game:
    def __init__(self, autotest=False):
        self.autotest = autotest
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((W * SCALE, H * SCALE))
        self.fb = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.font = Font()
        self.apu = APU()
        self._sprites()
        self.overlay = self._overlay()
        self.crt = False
        self._scan_cache = None
        self.joy = None
        if pygame.joystick.get_count():
            self.joy = pygame.joystick.Joystick(0)
            self.joy.init()
        self.hiscore = 0
        self.score = 0
        self.lives = 3
        self.credit = 0
        self.state = "attract"
        self.t = 0
        self.paused = False
        self.frame = 0
        self.setup_wave(0)

    # ---- setup ----
    def _sprites(self):
        self.s_alien = [[Sprite(f) for f in k] for k in (KITTEN, CAT, BIGCAT)]
        self.off = [(16 - k[0].w) // 2 for k in self.s_alien]
        self.wid = [k[0].w for k in self.s_alien]
        self.s_player = Sprite(PLAYER)
        self.s_pboom = [Sprite(f) for f in PLAYER_BOOM]
        self.s_aboom = Sprite(ALIEN_BOOM)
        self.s_ufo = Sprite(UFO)
        self.s_uboom = Sprite(UFO_BOOM)
        self.s_blast = Sprite(SHOT_BLAST)
        self.s_topblast = Sprite(TOP_BLAST)
        self.s_ashot = [[Sprite(f) for f in t] for t in ASHOTS]

    def _overlay(self):
        o = pygame.Surface((W, H))
        o.fill(WHITE)
        o.fill(NES_PAL[0x16], (0, 32, W, 32))      # red UFO band
        o.fill(NES_PAL[0x2A], (0, 184, W, 56))     # green shields/player band
        o.fill(NES_PAL[0x2A], (24, 240, 112, 16))  # green lives strip
        return o

    def new_game(self):
        self.score = 0
        self.lives = 3
        self.extra_given = False
        self.shots_fired = 0
        self.state = "play"
        self.t = 0
        self.setup_wave(0)
        self.apu.play("start")

    def setup_wave(self, wave):
        self.wave = wave
        by = WAVE_BOTTOM_Y + WAVE_DROP[min(wave, len(WAVE_DROP) - 1)]
        self.aliens = []
        for r in range(5):
            kind = 0 if r == 0 else (1 if r < 3 else 2)
            for c in range(11):
                self.aliens.append(Alien(r, c, kind, RACK_START_X + c * 16, by - (4 - r) * 16))
        self.order = [self.aliens[r * 11 + c] for r in (4, 3, 2, 1, 0) for c in range(11)]
        self.alive_count = 55
        self.move_ptr = len(self.order)  # forces begin_sweep on first move
        self.rack_dir = 1
        self.sweep_down = False
        self.march_t = 30
        self.march_idx = 0
        # shields + ground
        self.sgrid = bytearray(W * H)
        self.ssurf = pygame.Surface((W, H))
        self.ssurf.fill(BLACK)
        self.ssurf.set_colorkey(BLACK)
        for i in range(4):
            bx = 32 + i * 45
            for y in range(16):
                for x in range(22):
                    if shield_on(x, y):
                        self.sgrid[(SHIELD_Y + y) * W + bx + x] = 1
                        self.ssurf.set_at((bx + x, SHIELD_Y + y), WHITE)
        self.ground = pygame.Surface((W, 1))
        self.ground.fill(WHITE)
        self.ground.set_colorkey(BLACK)
        # actors
        self.px = PLAYER_START_X
        self.player_alive = True
        self.dying = 0
        self.respawn = 30
        self.invaded = False
        self.pshot = None
        self.pshot_cool = 0
        self.ashots = [None, None, None]
        self.ashot_reload = 48
        self.shot_turn = 0
        self.col_ptr = [0, 0, 6]
        self.aboom = None  # [x, y, frames]
        self.fx = []       # [x, y, sprite, frames]
        self.ufo = None
        self.ufo_timer = UFO_PERIOD
        self.wave_delay = 0
        self.apu.stop(1)

    # ---- helpers ----
    def add_score(self, pts):
        self.score += pts
        if self.score > self.hiscore:
            self.hiscore = self.score
        if not self.extra_given and self.score >= EXTRA_LIFE:
            self.extra_given = True
            self.lives += 1
            self.apu.play("extra")

    def reload_rate(self):
        for lim, rate in RELOAD:
            if self.score < lim:
                return rate
        return 7

    def march_delay(self):
        for k, v in zip(MARCH_KEYS, MARCH_VALS):
            if self.alive_count >= k:
                return v
        return 5

    def lowest_in_col(self, col):
        for r in (4, 3, 2, 1, 0):
            a = self.aliens[r * 11 + col]
            if a.alive:
                return a
        return None

    def erase(self, x0, y0, spr, ground=False):
        g, ss = self.sgrid, self.ssurf
        for dx, dy in spr.px:
            x, y = x0 + dx, y0 + dy
            if 0 <= x < W and 0 <= y < H and g[y * W + x]:
                g[y * W + x] = 0
                ss.set_at((x, y), BLACK)
            if ground and y == GROUND_Y and 0 <= x < W:
                self.ground.set_at((x, 0), BLACK)

    def shield_hit(self, x0, y0, spr):
        g = self.sgrid
        for dx, dy in spr.px:
            x, y = x0 + dx, y0 + dy
            if 0 <= x < W and 0 <= y < H and g[y * W + x]:
                return True
        return False

    def kill_player(self):
        if not self.player_alive:
            return
        self.player_alive = False
        self.dying = 96
        self.lives -= 1
        self.pshot = None
        self.ashots = [None, None, None]
        self.apu.stop(1)
        self.apu.play("player_die")

    def game_over(self):
        self.state = "over"
        self.t = 0
        self.apu.stop(1)
        if self.score > self.hiscore:
            self.hiscore = self.score

    # ---- input ----
    def read_input(self):
        k = pygame.key.get_pressed()
        left = k[pygame.K_LEFT] or k[pygame.K_a]
        right = k[pygame.K_RIGHT] or k[pygame.K_d]
        fire = k[pygame.K_SPACE] or k[pygame.K_z] or k[pygame.K_x]
        if self.joy:
            try:
                ax = self.joy.get_axis(0) if self.joy.get_numaxes() else 0
                hx = self.joy.get_hat(0)[0] if self.joy.get_numhats() else 0
                left = left or ax < -0.4 or hx < 0
                right = right or ax > 0.4 or hx > 0
                nb = self.joy.get_numbuttons()
                fire = fire or (nb > 0 and self.joy.get_button(0)) or (nb > 1 and self.joy.get_button(1))
            except pygame.error:
                pass
        if self.autotest:
            left, right, fire = self.bot()
        return left, right, fire

    def bot(self):
        target = None
        best = 999
        for c in range(11):
            a = self.lowest_in_col(c)
            if a:
                cx = a.x + 8
                d = abs(cx - (self.px + 6))
                if d < best:
                    best, target = d, cx
        if target is None:
            return False, False, True
        return target < self.px + 6, target > self.px + 6, True

    # ---- update ----
    def update(self):
        self.t += 1
        if self.state == "attract":
            return
        if self.state == "over":
            if self.t > 300:
                self.state = "attract"
                self.t = 0
            return
        if self.paused:
            return
        self.frame += 1
        f = self.frame

        if self.dying:
            self.dying -= 1
            if not self.dying:
                if self.lives <= 0 or self.invaded:
                    self.game_over()
                    return
                self.respawn = 48
            return
        if self.respawn:
            self.respawn -= 1
            if not self.respawn:
                self.player_alive = True
                self.px = PLAYER_START_X
            return
        if self.wave_delay:
            self.wave_delay -= 1
            if not self.wave_delay:
                self.setup_wave(self.wave + 1)
            return

        left, right, fire = self.read_input()
        # player
        if left and not right:
            self.px = max(PLAYER_MIN_X, self.px - 1)
        elif right and not left:
            self.px = min(PLAYER_MAX_X, self.px + 1)
        if self.pshot_cool:
            self.pshot_cool -= 1
        if fire and self.pshot is None and not self.pshot_cool and self.aboom is None:
            self.pshot = [self.px + 6, PLAYER_Y - 4]
            self.shots_fired += 1
            self.apu.play("shoot", ch=2)

        self.update_pshot()

        # rack
        if self.aboom:
            self.aboom[2] -= 1
            if self.aboom[2] <= 0:
                self.aboom = None
        elif self.alive_count:
            self.step_rack()
            if not self.player_alive:
                return
            self.march_t -= 1
            if self.march_t <= 0:
                self.apu.play("march%d" % self.march_idx, ch=0)
                self.march_idx = (self.march_idx + 1) & 3
                self.march_t = self.march_delay()

        self.alien_fire()
        self.update_ashots(f)
        if not self.player_alive:
            return
        self.update_ufo()

        for e in self.fx:
            e[3] -= 1
        self.fx = [e for e in self.fx if e[3] > 0]

        if self.alive_count == 0 and self.aboom is None:
            self.wave_delay = 90
            self.pshot = None
            self.ashots = [None, None, None]
            self.ufo = None
            self.apu.stop(1)

    def update_pshot(self):
        s = self.pshot
        if s is None:
            return
        s[1] -= 4
        sx, sy = s
        if sy <= TOP_LIMIT:
            self.fx.append([sx - 4, TOP_LIMIT, self.s_topblast, 16])
            self.pshot = None
            return
        # aliens (per-pixel)
        for a in self.aliens:
            if not a.alive:
                continue
            ax = a.x + self.off[a.kind]
            if not (ax <= sx < ax + self.wid[a.kind] and sy < a.y + 8 and sy + 4 > a.y):
                continue
            bits = self.s_alien[a.kind][a.frame].bits
            if any((sx - ax, sy + k - a.y) in bits for k in range(4)):
                a.alive = False
                self.alive_count -= 1
                self.add_score(POINTS[a.kind])
                self.aboom = [a.x + 8 - 6, a.y, 16]
                self.pshot = None
                self.pshot_cool = 16
                self.apu.play("inv_die")
                return
        # ufo
        u = self.ufo
        if u and u["state"] == "fly" and u["x"] <= sx < u["x"] + 16 and UFO_Y <= sy + 3 and sy < UFO_Y + 7:
            u["state"] = "boom"
            u["t"] = 24
            u["pts"] = UFO_TABLE[self.shots_fired % 15]
            self.add_score(u["pts"])
            self.pshot = None
            self.apu.stop(1)
            self.apu.play("ufo_hit")
            return
        # alien shots
        for i, a in enumerate(self.ashots):
            if a and a[0] <= sx < a[0] + 3 and sy < a[1] + 7 and sy + 4 > a[1]:
                self.fx.append([a[0] - 2, a[1], self.s_blast, 12])
                self.ashots[i] = None
                self.pshot = None
                self.apu.play("tick")
                return
        # shields
        g = self.sgrid
        for k in range(4):
            y = sy + k
            if 0 <= y < H and g[y * W + sx]:
                self.erase(sx - 4, y - 5, self.s_blast)
                self.pshot = None
                self.apu.play("tick")
                return

    def begin_sweep(self):
        if self.sweep_down:
            self.sweep_down = False
            return
        for a in self.aliens:
            if not a.alive:
                continue
            l = a.x + self.off[a.kind]
            r = l + self.wid[a.kind]
            if (self.rack_dir > 0 and r >= RACK_RIGHT) or (self.rack_dir < 0 and l <= RACK_LEFT):
                self.sweep_down = True
                self.rack_dir = -self.rack_dir
                return

    def step_rack(self):
        n = len(self.order)
        a = None
        for _ in range(n + 1):
            if self.move_ptr >= n:
                self.begin_sweep()
                self.move_ptr = 0
            c = self.order[self.move_ptr]
            self.move_ptr += 1
            if c.alive:
                a = c
                break
        if a is None:
            return
        if self.sweep_down:
            a.y += 8
        else:
            step = 3 if (self.alive_count == 1 and self.rack_dir > 0) else 2
            a.x += step * self.rack_dir
        a.frame ^= 1
        if a.y + 8 > SHIELD_Y and a.y < SHIELD_Y + 16:
            l = a.x + self.off[a.kind]
            g = self.sgrid
            for yy in range(a.y, a.y + 8):
                for xx in range(l, l + self.wid[a.kind]):
                    if 0 <= xx < W and g[yy * W + xx]:
                        g[yy * W + xx] = 0
                        self.ssurf.set_at((xx, yy), BLACK)
        if a.y + 8 >= PLAYER_Y:
            self.invaded = True
            self.lives = 0
            self.kill_player()

    def alien_fire(self):
        if not self.player_alive:
            return
        if self.ashot_reload > 0:
            self.ashot_reload -= 1
            return
        t = self.shot_turn
        self.shot_turn = (t + 1) % 3
        if self.ashots[t] is not None or self.alive_count == 0:
            return
        if t == 1 and self.alive_count == 1:
            return
        if t == 2 and self.ufo is not None:
            return
        if t == 0:  # rolling: aimed at the column over the player
            pcx = self.px + 6
            best, col = 999, None
            for c in range(11):
                a = self.lowest_in_col(c)
                if a:
                    d = abs(a.x + 8 - pcx)
                    if d < best:
                        best, col = d, c
            if col is None:
                return
        else:
            lo, hi = (0, 16) if t == 1 else (6, 21)
            idx = self.col_ptr[t]
            col = COL_TABLE[idx] - 1
            idx += 1
            self.col_ptr[t] = lo if idx >= hi else idx
        a = self.lowest_in_col(col)
        if a is None:
            return
        self.ashots[t] = [a.x + 7, a.y + 8, 0]
        self.ashot_reload = self.reload_rate()

    def update_ashots(self, f):
        speed = 5 if self.alive_count <= 8 else 4
        for t in range(3):
            s = self.ashots[t]
            if s is None or f % 3 != t:
                continue
            s[1] += speed
            s[2] = (s[2] + 1) & 3
            spr = self.s_ashot[t][s[2]]
            x, y = s[0], s[1]
            if self.shield_hit(x, y, spr):
                self.erase(x - 2, y + 1, self.s_blast)
                self.fx.append([x - 2, y + 1, self.s_blast, 8])
                self.ashots[t] = None
                continue
            if (self.player_alive and x + 3 > self.px and x < self.px + 13
                    and y + 7 > PLAYER_Y and y < PLAYER_Y + 8):
                pb = self.s_player.bits
                if any((x + dx - self.px, y + dy - PLAYER_Y) in pb for dx, dy in spr.px):
                    self.kill_player()
                    return
            if y + 7 >= GROUND_Y:
                self.erase(x - 2, GROUND_Y - 6, self.s_blast, ground=True)
                self.fx.append([x - 2, GROUND_Y - 7, self.s_blast, 8])
                self.ashots[t] = None

    def update_ufo(self):
        u = self.ufo
        if u is None:
            self.ufo_timer -= 1
            if self.ufo_timer <= 0:
                self.ufo_timer = UFO_PERIOD
                if self.alive_count >= 8 and self.ashots[2] is None:
                    d = 1 if self.shots_fired % 2 else -1
                    self.ufo = {"x": 8 if d > 0 else W - 24, "d": d, "state": "fly", "t": 0, "pts": 0}
                    self.apu.play("ufo", ch=1, loops=-1)
            return
        if u["state"] == "fly":
            u["x"] += u["d"]
            if u["x"] < 4 or u["x"] > W - 20:
                self.ufo = None
                self.apu.stop(1)
        elif u["state"] == "boom":
            u["t"] -= 1
            if u["t"] <= 0:
                u["state"], u["t"] = "score", 60
        else:
            u["t"] -= 1
            if u["t"] <= 0:
                self.ufo = None

    # ---- draw ----
    def draw_hud(self):
        fb, fn = self.fb, self.font
        fn.draw(fb, "SCORE<1> HI-SCORE SCORE<2>", 34, 8)
        fn.draw(fb, "%04d" % (self.score % 10000), 42, 24)
        fn.draw(fb, "%04d" % (self.hiscore % 10000), 100, 24)
        fn.draw(fb, "CREDIT %02d" % self.credit, 140, 242)
        if self.state != "attract":
            fn.draw(fb, str(max(0, self.lives)), 8, 242)
            for i in range(min(max(0, self.lives) - 1, 5)):
                fb.blit(self.s_player.surf, (24 + i * 16, 242))

    def draw_attract(self):
        fb, fn = self.fb, self.font
        t = self.t
        lim = lambda start: (t - start) // 4
        fn.center(fb, "PLAY", 64, lim(0))
        fn.center(fb, "CATS'S SPACE INVADERS 0.1", 84, lim(20))
        if t > 140:
            fn.center(fb, "*SCORE ADVANCE TABLE*", 120)
            rows = ((self.s_ufo, "=? MYSTERY"), (self.s_alien[0][(t // 32) & 1], "=30 POINTS"),
                    (self.s_alien[1][(t // 32) & 1], "=20 POINTS"), (self.s_alien[2][(t // 32) & 1], "=10 POINTS"))
            for i, (spr, txt) in enumerate(rows):
                y = 136 + i * 16
                fb.blit(spr.surf, (72 - spr.w // 2, y))
                fn.draw(fb, txt, 84, y, lim(160 + i * 50))
        if t > 400 and (t // 30) & 1:
            fn.center(fb, "PRESS ENTER OR START", 212)
        fn.center(fb, "A.C HOLDINGS / TEAM FLAMES", 226)

    def draw(self):
        fb = self.fb
        fb.fill(BLACK)
        self.draw_hud()
        if self.state == "attract":
            self.draw_attract()
        else:
            for a in self.aliens:
                if a.alive:
                    fb.blit(self.s_alien[a.kind][a.frame].surf, (a.x + self.off[a.kind], a.y))
            if self.aboom:
                fb.blit(self.s_aboom.surf, (self.aboom[0], self.aboom[1]))
            fb.blit(self.ssurf, (0, 0))
            if self.player_alive:
                fb.blit(self.s_player.surf, (self.px, PLAYER_Y))
            elif self.dying:
                fb.blit(self.s_pboom[(self.dying // 5) & 1].surf, (self.px - 1, PLAYER_Y))
            if self.pshot:
                fb.fill(WHITE, (self.pshot[0], self.pshot[1], 1, 4))
            for t, s in enumerate(self.ashots):
                if s:
                    fb.blit(self.s_ashot[t][s[2]].surf, (s[0], s[1]))
            u = self.ufo
            if u:
                if u["state"] == "fly":
                    fb.blit(self.s_ufo.surf, (u["x"], UFO_Y))
                elif u["state"] == "boom":
                    fb.blit(self.s_uboom.surf, (u["x"], UFO_Y))
                else:
                    self.font.draw(fb, str(u["pts"]), u["x"], UFO_Y)
            for x, y, spr, _ in self.fx:
                fb.blit(spr.surf, (x, y))
            fb.blit(self.ground, (0, GROUND_Y))
            if self.state == "over":
                self.font.center(fb, "GAME OVER", 48, self.t // 6)
                if self.t > 120:
                    self.font.center(fb, "PRESS ENTER", 64)
            if self.paused:
                self.font.center(fb, "PAUSED", 104)
        fb.blit(self.overlay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        sw, sh = self.screen.get_size()
        s = max(1, min(sw // W, sh // H))
        dw, dh = W * s, H * s
        ox, oy = (sw - dw) // 2, (sh - dh) // 2
        self.screen.fill(BLACK)
        self.screen.blit(pygame.transform.scale(fb, (dw, dh)), (ox, oy))
        if self.crt and s >= 2:
            if self._scan_cache is None or self._scan_cache[0] != (dw, dh, s):
                sc = pygame.Surface((dw, dh), pygame.SRCALPHA)
                for y in range(s - 1, dh, s):
                    sc.fill((0, 0, 0, 110), (0, y, dw, 1))
                self._scan_cache = ((dw, dh, s), sc)
            self.screen.blit(self._scan_cache[1], (ox, oy))
        pygame.display.flip()

    # ---- main loop ----
    def start_pressed(self):
        if self.state == "attract" or (self.state == "over" and self.t > 120):
            self.credit = min(99, self.credit + 1)
            self.credit -= 1
            self.new_game()

    def run(self, max_frames=None):
        running = True
        n = 0
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_1):
                        self.start_pressed()
                    elif e.key == pygame.K_5:
                        self.credit = min(99, self.credit + 1)
                    elif e.key == pygame.K_p and self.state == "play":
                        self.paused = not self.paused
                        if self.paused:
                            pygame.mixer.pause() if self.apu.ok else None
                        elif self.apu.ok:
                            pygame.mixer.unpause()
                    elif e.key == pygame.K_m:
                        self.apu.muted = not self.apu.muted
                        if self.apu.muted and self.apu.ok:
                            pygame.mixer.stop()
                        elif self.ufo and self.ufo["state"] == "fly":
                            self.apu.play("ufo", ch=1, loops=-1)
                    elif e.key == pygame.K_c:
                        self.crt = not self.crt
                    elif e.key == pygame.K_F11:
                        try:
                            pygame.display.toggle_fullscreen()
                        except pygame.error:
                            pass
                elif e.type == pygame.JOYBUTTONDOWN and e.button in (6, 7, 9):
                    self.start_pressed()
                elif e.type == pygame.JOYDEVICEADDED and self.joy is None:
                    self.joy = pygame.joystick.Joystick(e.device_index)
                    self.joy.init()
            if self.autotest and self.state != "play":
                self.state = "attract"
                self.start_pressed()
                self.games = getattr(self, "games", 0) + 1
            self.update()
            self.draw()
            n += 1
            if max_frames and n >= max_frames:
                break
            if not self.autotest:
                self.clock.tick(FPS)
        pygame.quit()
        return n


def main():
    autotest = "--autotest" in sys.argv
    if autotest:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    g = Game(autotest)
    frames = g.run(20000 if autotest else None)
    if autotest:
        print("autotest ok: %d frames, wave %d, score %d, hi %d, games %d"
              % (frames, g.wave, g.score, g.hiscore, getattr(g, "games", 0)))


if __name__ == "__main__":
    main()
