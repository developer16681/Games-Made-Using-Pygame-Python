#!/usr/bin/env python3
"""
PACMAN  -  a polished single-file Pac-Man style game for Python + pygame.

Install:   pip install pygame
Run:       python pacman.py

Controls
    Arrow keys / WASD   steer Pac-Man
    ENTER / SPACE       start game
    P                   pause
    M                   mute / unmute
    ESC                 quit

Everything (neon maze, sprites, glow effects, and ALL sounds) is generated
in code, so there are no external files needed.  To use your own audio, put files
in a "sounds/" folder next to this script (see Sounds._load_overrides).
"""
import array
import math
import os
import random
import sys
from collections import deque

try:
    import pygame
    import pygame.gfxdraw as gfx
except ImportError:
    sys.exit("This game needs pygame.  Install it with:  pip install pygame")

# --------------------------------------------------------------------------
#  Constants
# --------------------------------------------------------------------------
T = 21                              # tile size in pixels
COLS, ROWS = 28, 31
HUD_TOP = 3 * T
HUD_BOT = 2 * T
W = COLS * T
H = HUD_TOP + ROWS * T + HUD_BOT
FPS = 60

LAYOUT = [
    "############################",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#.####.#####.##.#####.####.#",
    "#..........................#",
    "#.####.##.########.##.####.#",
    "#.####.##.########.##.####.#",
    "#......##....##....##......#",
    "######.##### ## #####.######",
    "     #.##### ## #####.#     ",
    "     #.##          ##.#     ",
    "     #.## ###--### ##.#     ",
    "######.## #      # ##.######",
    "      .   #      #   .      ",
    "######.## #      # ##.######",
    "     #.## ######## ##.#     ",
    "     #.##          ##.#     ",
    "     #.## ######## ##.#     ",
    "######.## ######## ##.######",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#.####.#####.##.#####.####.#",
    "#o..##.......  .......##..o#",
    "###.##.##.########.##.##.###",
    "###.##.##.########.##.##.###",
    "#......##....##....##......#",
    "#.##########.##.##########.#",
    "#.##########.##.##########.#",
    "#..........................#",
    "############################",
]
assert len(LAYOUT) == ROWS and all(len(r) == COLS for r in LAYOUT), "bad maze"

TUNNEL_ROW = 14
HOUSE_IN = (13, 13)      # inside the ghost house
HOUSE_OUT = (13, 11)     # just outside the door

UP, LEFT, DOWN, RIGHT = (0, -1), (-1, 0), (0, 1), (1, 0)
ORDER = [UP, LEFT, DOWN, RIGHT]          # ghost tie-break priority

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 225, 0)
WALL_BLUE = (40, 60, 255)
WALL_FLASH = (235, 235, 255)
DOT_COLOR = (255, 214, 190)
PINK_DOOR = (255, 184, 222)

PAC_R = int(T * 0.62)
GHOST_R = int(T * 0.66)

MODE_SCHEDULE = [(7, "scatter"), (20, "chase"), (7, "scatter"), (20, "chase"),
                 (5, "scatter"), (20, "chase"), (5, "scatter"), (1e9, "chase")]

FRUITS = [("cherry", 100), ("strawberry", 300), ("orange", 500),
          ("apple", 700), ("melon", 1000)]

HS_FILE = os.path.join(os.path.expanduser("~"), ".pacman_highscore")


def opposite(d):
    return (-d[0], -d[1])


def passable(c, r, door=False):
    """Can a creature enter tile (c, r)?  The tunnel extends one tile off-screen."""
    if r == TUNNEL_ROW and -1 <= c <= COLS:
        return True
    if not (0 <= c < COLS and 0 <= r < ROWS):
        return False
    ch = LAYOUT[r][c]
    if ch == "#":
        return False
    if ch == "-":
        return door
    return True


def bfs_dir(start, target):
    """First step of the shortest path (ghost door allowed)."""
    if start == target:
        return None
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == target:
            break
        for d in ORDER:
            n = (cur[0] + d[0], cur[1] + d[1])
            if n in prev or not (0 <= n[0] < COLS and 0 <= n[1] < ROWS):
                continue
            if not passable(n[0], n[1], True):
                continue
            prev[n] = (cur, d)
            q.append(n)
    if target not in prev:
        return None
    cur = target
    while prev[cur] is not None and prev[cur][0] != start:
        cur = prev[cur][0]
    return prev[cur][1] if prev[cur] else None


DOTS = {(c, r) for r in range(ROWS) for c in range(COLS) if LAYOUT[r][c] == "."}
PELLETS = {(c, r) for r in range(ROWS) for c in range(COLS) if LAYOUT[r][c] == "o"}


# --------------------------------------------------------------------------
#  Sound synthesis
# --------------------------------------------------------------------------
def _wave(kind, ph):
    if kind == "square":
        return 1.0 if ph < 0.5 else -1.0
    if kind == "tri":
        return 4.0 * abs(ph - 0.5) - 1.0
    if kind == "saw":
        return 2.0 * ph - 1.0
    return math.sin(2 * math.pi * ph)


def render(segments, wave="square", vol=0.3, env=True, rate=44100):
    """segments: list of (freq_start, freq_end, seconds).  freq 0 = silence.
    Returns a list of float samples in [-1, 1]."""
    out = []
    phase = 0.0
    for f0, f1, dur in segments:
        n = max(1, int(rate * dur))
        for i in range(n):
            f = f0 + (f1 - f0) * (i / n)
            if f <= 0:
                v = 0.0
            else:
                phase = (phase + f / rate) % 1.0
                v = _wave(wave, phase)
            if env:
                v *= min(1.0, i / 60.0, (n - i) / (0.25 * n + 1.0))
            out.append(v * vol)
    return out


def mix(*tracks):
    n = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(n)]


def to_sound(samples):
    init = pygame.mixer.get_init()
    channels = init[2] if init else 1
    buf = array.array("h")
    for v in samples:
        s = int(max(-1.0, min(1.0, v)) * 32767)
        buf.append(s)
        if channels == 2:
            buf.append(s)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def synth(segments, wave="square", vol=0.3, env=True, rate=44100):
    return to_sound(render(segments, wave, vol, env, rate))


class Sounds:
    def __init__(self):
        self.ok = False
        self.muted = False
        self.s = {}
        self.loop_name = None
        self.toggle = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 1, 512)
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(2)       # ch0 = loops, ch1 = waka
            self._build()
            self._load_overrides()
            self.ok = True
        except Exception as exc:               # no audio device etc.
            print("Audio disabled:", exc)

    def _build(self):
        s = self.s
        s["waka1"] = synth([(250, 650, 0.085)], "tri", 0.55)
        s["waka2"] = synth([(650, 250, 0.085)], "tri", 0.55)
        s["power"] = synth([(330, 330, .045), (495, 495, .045), (660, 660, .045),
                            (990, 990, .09)], "square", 0.22)
        s["eatghost"] = synth([(150, 1500, 0.30)], "square", 0.22)
        s["fruit"] = synth([(784, 784, .06), (1046, 1046, .06), (1318, 1318, .06),
                            (1568, 1568, .16)], "sine", 0.45)
        s["extra"] = synth([(523, 523, .08), (659, 659, .08), (784, 784, .08),
                            (1046, 1046, .08), (784, 784, .08), (1318, 1318, .25)],
                           "square", 0.2)
        death = []
        f = 950.0
        for _ in range(9):
            death.append((f, f * 0.5, 0.11))
            f *= 0.8
        death += [(0, 0, 0.05), (400, 60, 0.18)]
        s["death"] = synth(death, "square", 0.26)

        # Original two-voice chiptune theme (lead + bass), composed for this game
        n = {"A2": 110, "D3": 147, "E3": 165, "A3": 220, "B3": 247,
             "A4": 440, "B4": 494, "C5": 523, "D5": 587, "E5": 659, "F5": 698,
             "G5": 784, "G#4": 415, "G#5": 831, "A5": 880, "B5": 988, "C6": 1047}
        eighth = 0.14
        lead_notes = [
            ("A4", 1), ("C5", 1), ("E5", 1), ("A5", 2), ("G5", 1), ("E5", 1), ("C5", 1),
            ("D5", 1), ("F5", 1), ("A5", 1), ("F5", 2), ("E5", 1), ("D5", 1), ("A4", 1),
            ("E5", 1), ("G#5", 1), ("B5", 1), ("G#5", 2), ("E5", 1), ("B4", 1), ("G#4", 1),
            ("A4", 1), ("C5", 1), ("E5", 1), ("A5", 1), ("C6", 4),
        ]
        bass_bars = [("A2", "E3"), ("D3", "A3"), ("E3", "B3"), ("A2", "E3")]
        lead = []
        for k, beats in lead_notes:
            lead.append((n[k], n[k], eighth * beats * 0.92))
            lead.append((0, 0, eighth * beats * 0.08))
        bass = []
        for root, fifth in bass_bars:
            for i in range(8):
                f = n[root] if i % 2 == 0 else n[fifth]
                bass.append((f, f, eighth * 0.9))
                bass.append((0, 0, eighth * 0.1))
        s["intro"] = to_sound(mix(render(lead, "square", 0.13),
                                  render(bass, "tri", 0.22)))

        # Looping background sounds (no envelope so they loop cleanly)
        for i, base in enumerate((430, 520, 620), 1):
            s["siren%d" % i] = synth([(base, base * 1.8, 0.28), (base * 1.8, base, 0.28)],
                                     "tri", 0.2, env=False)
        s["fright"] = synth([(220, 360, 0.07), (360, 220, 0.07)] * 4,
                            "square", 0.1, env=False)
        s["retreat"] = synth([(700, 1400, 0.07), (1400, 700, 0.07)] * 3,
                             "sine", 0.22, env=False)

    def _load_overrides(self):
        """Use your own audio from a 'sounds/' folder next to this script.
        Name files after the sounds: intro, waka1, waka2, power, eatghost,
        fruit, extra, death, siren1, siren2, siren3, fright, retreat
        (.wav / .ogg / .mp3)."""
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
        if not os.path.isdir(folder):
            return
        for name in list(self.s):
            for ext in (".wav", ".ogg", ".mp3"):
                path = os.path.join(folder, name + ext)
                if os.path.isfile(path):
                    try:
                        self.s[name] = pygame.mixer.Sound(path)
                        print("Loaded custom sound:", name + ext)
                    except Exception as exc:
                        print("Could not load", path, exc)
                    break

    # ------------------------------------------------------------------
    def play(self, name):
        if self.ok and not self.muted and name in self.s:
            self.s[name].play()

    def waka(self):
        if self.ok and not self.muted:
            self.toggle = not self.toggle
            pygame.mixer.Channel(1).play(self.s["waka1" if self.toggle else "waka2"])

    def set_loop(self, name):
        want = None if (self.muted or not self.ok) else name
        if want == self.loop_name:
            return
        ch = pygame.mixer.Channel(0)
        ch.stop()
        if want:
            ch.play(self.s[want], loops=-1)
        self.loop_name = want

    def toggle_mute(self):
        self.muted = not self.muted
        if self.ok:
            pygame.mixer.stop()
            self.loop_name = None


# --------------------------------------------------------------------------
#  Rendering helpers
# --------------------------------------------------------------------------
def build_maze(color):
    """Neon-outlined hollow walls with rounded corners and a soft glow."""
    surf = pygame.Surface((W, ROWS * T)).convert()
    surf.fill(BLACK)

    def is_open(c, r):
        return 0 <= c < COLS and 0 <= r < ROWS and LAYOUT[r][c] != "#"

    R, S = 8, 3
    for r in range(ROWS):
        for c in range(COLS):
            if LAYOUT[r][c] != "#":
                continue
            x, y = c * T, r * T
            up, dn = is_open(c, r - 1), is_open(c, r + 1)
            lf, rt = is_open(c - 1, r), is_open(c + 1, r)
            tl, tr = (R if up and lf else 0), (R if up and rt else 0)
            bl, br = (R if dn and lf else 0), (R if dn and rt else 0)
            pygame.draw.rect(surf, color, (x, y, T, T), 0, 0, tl, tr, bl, br)
            ix, iy = x + (S if lf else 0), y + (S if up else 0)
            iw = T - (S if lf else 0) - (S if rt else 0)
            ih = T - (S if up else 0) - (S if dn else 0)
            pygame.draw.rect(surf, BLACK, (ix, iy, iw, ih), 0, 0,
                             max(0, tl - S), max(0, tr - S),
                             max(0, bl - S), max(0, br - S))
            # concave corners: keep the stroke continuous
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                if (not is_open(c + dx, r) and not is_open(c, r + dy)
                        and is_open(c + dx, r + dy)):
                    cx = x if dx < 0 else x + T - S
                    cy = y if dy < 0 else y + T - S
                    pygame.draw.rect(surf, color, (cx, cy, S, S))
    # glow
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (w // 4, h // 4))
    small = pygame.transform.smoothscale(small, (w // 8, h // 8))
    glow = pygame.transform.smoothscale(small, (w, h))
    surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    return surf


def pac_surface(r, angle, mouth):
    """Supersampled, shaded Pac-Man wedge."""
    ss = 4
    sz = int(2 * r + 6)
    big = pygame.Surface((sz * ss, sz * ss), pygame.SRCALPHA)
    cx = cy = sz * ss / 2
    for scale, col in ((1.0, (230, 175, 0)), (0.9, (255, 215, 0)), (0.68, (255, 240, 70))):
        pts = [(cx, cy)]
        a0, a1 = angle + mouth, angle + 2 * math.pi - mouth
        n = 40
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append((cx + r * ss * scale * math.cos(a), cy + r * ss * scale * math.sin(a)))
        pygame.draw.polygon(big, col, pts)
    return pygame.transform.smoothscale(big, (sz, sz))


def ghost_body(color, frame, r):
    ss = 4
    sz = int(2 * r + 6)
    big = pygame.Surface((sz * ss, sz * ss), pygame.SRCALPHA)
    cx = sz * ss / 2
    R = r * ss
    cy = sz * ss / 2 - 0.12 * R
    bottom = cy + 1.12 * R
    pts = []
    n = 24
    for i in range(n + 1):
        a = math.pi - math.pi * i / n
        pts.append((cx + R * math.cos(a), cy - R * math.sin(a)))
    feet = 6
    for k in range(feet + 1):
        x = cx + R - k * (2 * R / feet)
        up = (k + frame) % 2 == 1
        pts.append((x, bottom - (0.30 * R if up else 0)))
    pygame.draw.polygon(big, color, pts)
    # soft highlight for a bit of depth
    hl = tuple(min(255, int(c + (255 - c) * 0.35)) for c in color)
    pygame.draw.ellipse(big, hl, (cx - 0.75 * R, cy - 0.95 * R, 0.9 * R, 0.55 * R))
    pygame.draw.polygon(big, color, [(cx - 0.9 * R, cy - 0.2 * R), (cx + 0.9 * R, cy - 0.2 * R),
                                     (cx + 0.9 * R, cy + 0.4 * R), (cx - 0.9 * R, cy + 0.4 * R)])
    return pygame.transform.smoothscale(big, (sz, sz))


def radial_glow(radius, color, strength=70):
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for i in range(radius, 0, -1):
        a = int(strength * (1 - i / radius) ** 2)
        gfx.filled_circle(surf, radius, radius, i, (*color, a))
    return surf


def aacircle(surf, x, y, r, color):
    x, y, r = int(x), int(y), max(1, int(r))
    gfx.filled_circle(surf, x, y, r, color)
    gfx.aacircle(surf, x, y, r, color)


def draw_fruit(surf, cx, cy, kind, s=1.0):
    u = T * 0.36 * s
    GREEN, BROWN = (40, 200, 60), (150, 90, 40)
    if kind == "cherry":
        for dx, dy in ((-0.95, 0.65), (0.9, 0.85)):
            pygame.draw.line(surf, GREEN, (cx + dx * u, cy + dy * u - u * 0.6),
                             (cx + 0.35 * u, cy - 1.5 * u), max(1, int(u * 0.22)))
        for dx, dy in ((-0.95, 0.65), (0.9, 0.85)):
            aacircle(surf, cx + dx * u, cy + dy * u, u * 0.9, (230, 20, 40))
            aacircle(surf, cx + dx * u - u * 0.3, cy + dy * u - u * 0.3, u * 0.22, (255, 190, 190))
    elif kind == "strawberry":
        aacircle(surf, cx, cy + u * 0.15, u * 1.25, (240, 30, 60))
        pygame.draw.polygon(surf, GREEN, [(cx - u * 0.9, cy - u * 0.9), (cx, cy - u * 0.45),
                                          (cx + u * 0.9, cy - u * 0.9), (cx, cy - u * 1.5)])
        for dx, dy in ((-0.5, 0.0), (0.5, 0.1), (0, 0.6), (-0.4, 0.8), (0.4, 0.8)):
            pygame.draw.circle(surf, (255, 230, 120), (int(cx + dx * u), int(cy + dy * u)), 1)
    elif kind == "orange":
        aacircle(surf, cx, cy + u * 0.1, u * 1.25, (255, 150, 20))
        pygame.draw.ellipse(surf, GREEN, (cx - u * 0.1, cy - u * 1.6, u * 1.0, u * 0.6))
        aacircle(surf, cx - u * 0.4, cy - u * 0.2, u * 0.25, (255, 210, 130))
    elif kind == "apple":
        aacircle(surf, cx - u * 0.45, cy + u * 0.1, u * 0.95, (225, 25, 35))
        aacircle(surf, cx + u * 0.45, cy + u * 0.1, u * 0.95, (225, 25, 35))
        pygame.draw.line(surf, BROWN, (cx, cy - u * 0.8), (cx + u * 0.2, cy - u * 1.5), 2)
        pygame.draw.ellipse(surf, GREEN, (cx + u * 0.2, cy - u * 1.5, u * 0.9, u * 0.5))
    else:  # melon
        aacircle(surf, cx, cy + u * 0.1, u * 1.3, (60, 190, 90))
        for dx in (-0.6, 0, 0.6):
            pygame.draw.line(surf, (160, 240, 170), (cx + dx * u, cy - u * 0.9),
                             (cx + dx * u, cy + u * 1.1), 1)
        pygame.draw.line(surf, BROWN, (cx, cy - u * 1.2), (cx, cy - u * 1.6), 2)


# --------------------------------------------------------------------------
#  Game entities
# --------------------------------------------------------------------------
class Mover:
    """Tile-to-tile mover with smooth sub-tile interpolation."""

    def __init__(self, c, r):
        self.c, self.r = c, r
        self.nc, self.nr = c, r
        self.p = 0.0
        self.moving = False
        self.dir = LEFT

    def pos(self):
        return (self.c + (self.nc - self.c) * self.p + 0.5,
                self.r + (self.nr - self.r) * self.p + 0.5)

    def advance(self, dist, game):
        guard = 0
        while dist > 1e-9 and guard < 8:
            guard += 1
            if self.moving:
                rem = 1.0 - self.p
                if dist < rem:
                    self.p += dist
                    return
                dist -= rem
                self.c, self.r = self.nc, self.nr
                if self.c < 0:                      # tunnel wrap
                    self.c = COLS
                elif self.c >= COLS:
                    self.c = -1
                self.nc, self.nr = self.c, self.r
                self.p = 0.0
                self.moving = False
                self.arrive(game)
                if game.state != "play":
                    return
            d = self.decide(game)
            if d is None:
                return
            self.dir = d
            self.nc, self.nr = self.c + d[0], self.r + d[1]
            self.moving = True
            self.p = 0.0

    def arrive(self, game):
        pass

    def decide(self, game):
        return None


class Pacman(Mover):
    def __init__(self):
        super().__init__(13, 23)
        self.want = LEFT
        self.phase = 0.0

    def tile(self):
        x, y = self.pos()
        return int(math.floor(x)), int(math.floor(y))

    def update(self, dt, game):
        if self.moving and self.want == opposite(self.dir):
            self.c, self.nc = self.nc, self.c
            self.r, self.nr = self.nr, self.r
            self.p = 1.0 - self.p
            self.dir = self.want
        before = self.pos()
        self.advance(game.pac_speed() * dt, game)
        after = self.pos()
        if abs(after[0] - before[0]) + abs(after[1] - before[1]) > 1e-6:
            self.phase += dt * 15.0

    def decide(self, game):
        for d in (self.want, self.dir):
            if d and passable(self.c + d[0], self.r + d[1]):
                return d
        return None

    def arrive(self, game):
        game.pac_arrive(self.c, self.r)


class Ghost(Mover):
    def __init__(self, name, color, start, corner, release):
        super().__init__(*start)
        self.name, self.color = name, color
        self.start, self.corner, self.release = start, corner, release
        self.state = "normal" if release == 0 else "house"
        self.fright = False
        self.reverse_pending = False
        self.hide = False
        self.dir = LEFT if release == 0 else UP
        self.bob = random.random() * 6

    def speed(self, game):
        if self.state == "eaten":
            return 15.0
        base = game.ghost_speed()
        if self.name == "blinky" and game.remaining() <= 20 and not self.fright:
            base *= 1.1
        if self.r == TUNNEL_ROW and (self.c <= 5 or self.c >= 22):
            return base * 0.55
        if self.fright:
            return base * 0.55
        if self.state == "leaving":
            return base * 0.7
        return base

    def update(self, dt, game):
        if self.state == "house":
            if game.play_time >= self.release:
                self.state = "leaving"
            else:
                return
        self.advance(self.speed(game) * dt, game)

    def decide(self, game):
        here = (self.c, self.r)
        if self.state == "eaten":
            if here == HOUSE_IN:
                self.state = "leaving"
                self.fright = False
            else:
                return bfs_dir(here, HOUSE_IN)
        if self.state == "leaving":
            if here == HOUSE_OUT:
                self.state = "normal"
            else:
                d = bfs_dir(here, HOUSE_OUT)
                if d:
                    return d
                self.state = "normal"
        rev = opposite(self.dir)
        if self.reverse_pending:
            self.reverse_pending = False
            if passable(self.c + rev[0], self.r + rev[1]):
                return rev
        opts = [d for d in ORDER if d != rev and passable(self.c + d[0], self.r + d[1])]
        if not opts:
            return rev if passable(self.c + rev[0], self.r + rev[1]) else None
        if self.fright:
            return random.choice(opts)
        tx, ty = game.ghost_target(self)
        return min(opts, key=lambda d: (self.c + d[0] - tx) ** 2 + (self.r + d[1] - ty) ** 2)


# --------------------------------------------------------------------------
#  The game
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        flags = pygame.SCALED | pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("PACMAN")
        self.clock = pygame.time.Clock()
        self.snd = Sounds()

        names = ["couriernew", "consolas", "dejavusansmono", "menlo", "monospace"]
        self.f_s = pygame.font.SysFont(names, 20, bold=True)
        self.f_m = pygame.font.SysFont(names, 28, bold=True)
        self.f_l = pygame.font.SysFont(names, 70, bold=True)

        self.maze_blue = build_maze(WALL_BLUE)
        self.maze_white = build_maze(WALL_FLASH)
        self.pac_glow = radial_glow(int(PAC_R * 2.6), (255, 220, 0), 60)
        self.ghost_cache = {}
        self.pac_cache = {}

        self.high = self.load_high()
        self.t = 0.0
        self.paused = False
        self.particles = []
        self.state = "title"
        self.score = 0
        self.level = 1
        self.lives = 3
        self.dots, self.pellets = set(), set()
        self.reset_positions()

    # ---------------- persistence -----------------
    def load_high(self):
        try:
            with open(HS_FILE) as fh:
                return int(fh.read().strip())
        except Exception:
            return 0

    def save_high(self):
        try:
            with open(HS_FILE, "w") as fh:
                fh.write(str(self.high))
        except Exception:
            pass

    # ---------------- setup -----------------
    def start_game(self):
        self.score = 0
        self.level = 1
        self.lives = 3
        self.extra_given = False
        self.new_level(first=True)

    def new_level(self, first=False):
        self.dots = set(DOTS)
        self.pellets = set(PELLETS)
        self.eaten = 0
        self.fruit = None
        self.reset_positions()
        self.begin_ready(first)

    def reset_positions(self):
        self.pac = Pacman()
        self.ghosts = [
            Ghost("blinky", (255, 30, 30), (13, 11), (25, -3), 0),
            Ghost("pinky", (255, 150, 255), (13, 14), (2, -3), 1.0),
            Ghost("inky", (0, 235, 255), (11, 14), (27, 32), 5.0),
            Ghost("clyde", (255, 175, 60), (16, 14), (0, 32), 9.0),
        ]
        self.mode_idx = 0
        self.mode_timer = 0.0
        self.mode = MODE_SCHEDULE[0][1]
        self.fright_timer = 0.0
        self.play_time = 0.0
        self.combo = 0
        self.popups = []
        self.freeze = 0.0

    def begin_ready(self, intro):
        self.state = "ready"
        self.timer = 4.7 if intro else 1.7
        if intro:
            self.snd.play("intro")

    # ---------------- rules helpers -----------------
    def remaining(self):
        return len(self.dots) + len(self.pellets)

    def pac_speed(self):
        base = 7.6 + min(self.level - 1, 4) * 0.12
        return base * (1.12 if self.fright_timer > 0 else 1.0)

    def ghost_speed(self):
        return 7.0 + min(self.level - 1, 6) * 0.25

    def add_score(self, n):
        self.score += n
        if self.score > self.high:
            self.high = self.score
        if self.score >= 10000 and not self.extra_given:
            self.extra_given = True
            self.lives += 1
            self.snd.play("extra")

    def ghost_target(self, g):
        if self.mode == "scatter":
            return g.corner
        pc, pr = self.pac.tile()
        d = self.pac.dir
        if g.name == "blinky":
            return pc, pr
        if g.name == "pinky":
            return pc + 4 * d[0], pr + 4 * d[1]
        if g.name == "inky":
            b = self.ghosts[0]
            px, py = pc + 2 * d[0], pr + 2 * d[1]
            return 2 * px - b.c, 2 * py - b.r
        if (g.c - pc) ** 2 + (g.r - pr) ** 2 > 64:         # clyde
            return pc, pr
        return g.corner

    def start_fright(self):
        self.fright_timer = max(1.5, 7.0 - 0.9 * (self.level - 1))
        self.combo = 0
        for g in self.ghosts:
            if g.state != "eaten":
                g.fright = True
                if g.state == "normal":
                    g.reverse_pending = True

    def fruit_kind(self):
        return FRUITS[min(self.level - 1, len(FRUITS) - 1)]

    def burst(self, x, y, color, n=12, speed=90):
        for _ in range(n):
            a = random.random() * math.tau
            v = speed * (0.4 + random.random() * 0.8)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v,
                                   0.5 + random.random() * 0.4, 0.9, color])

    def px(self, x, y):
        return int(x * T), int(y * T) + HUD_TOP

    # ---------------- events -----------------
    def pac_arrive(self, c, r):
        if (c, r) in self.dots:
            self.dots.remove((c, r))
            self.add_score(10)
            self.eaten += 1
            self.snd.waka()
            self.after_eat()
        elif (c, r) in self.pellets:
            self.pellets.remove((c, r))
            self.add_score(50)
            self.eaten += 1
            self.snd.play("power")
            self.start_fright()
            x, y = self.px(c + 0.5, r + 0.5)
            self.burst(x, y, (255, 230, 200), 14, 110)
            self.after_eat()

    def after_eat(self):
        if self.eaten in (70, 170) and self.fruit is None:
            self.fruit = 10.0
        if self.remaining() == 0:
            self.state = "win"
            self.timer = 2.6
            self.fruit = None

    def kill_pacman(self):
        self.state = "dying"
        self.timer = 2.4
        self.death_played = False

    # ---------------- update -----------------
    def update(self, dt):
        self.t += dt
        self.update_particles(dt)
        s = self.state
        if s == "ready":
            self.timer -= dt
            if self.timer <= 0:
                self.state = "play"
        elif s == "play":
            self.update_play(dt)
        elif s == "dying":
            self.timer -= dt
            elapsed = 2.4 - self.timer
            if elapsed >= 0.8 and not self.death_played:
                self.death_played = True
                self.snd.play("death")
            if self.timer <= 0:
                x, y = self.pac.pos()
                px, py = self.px(x, y)
                self.burst(px, py, (255, 225, 0), 18, 120)
                self.lives -= 1
                if self.lives <= 0:
                    self.state = "gameover"
                    self.timer = 3.5
                    self.save_high()
                else:
                    self.reset_positions()
                    self.begin_ready(False)
        elif s == "win":
            self.timer -= dt
            if self.timer <= 0:
                self.level += 1
                self.new_level()
        elif s == "gameover":
            self.timer -= dt
            if self.timer <= 0:
                self.state = "title"
        self.update_loops()

    def update_particles(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.96
            p[3] *= 0.96
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for pop in self.popups:
            pop[3] -= dt
        self.popups = [p for p in self.popups if p[3] > 0]

    def update_play(self, dt):
        if self.freeze > 0:
            self.freeze -= dt
            if self.freeze <= 0:
                for g in self.ghosts:
                    g.hide = False
            return
        self.play_time += dt

        if self.fright_timer > 0:
            self.fright_timer -= dt
            if self.fright_timer <= 0:
                self.fright_timer = 0
                self.combo = 0
                for g in self.ghosts:
                    g.fright = False
        else:
            self.mode_timer += dt
            if self.mode_timer >= MODE_SCHEDULE[self.mode_idx][0]:
                self.mode_timer = 0
                self.mode_idx = min(self.mode_idx + 1, len(MODE_SCHEDULE) - 1)
                self.mode = MODE_SCHEDULE[self.mode_idx][1]
                for g in self.ghosts:
                    if g.state == "normal":
                        g.reverse_pending = True

        if self.fruit is not None:
            self.fruit -= dt
            if self.fruit <= 0:
                self.fruit = None

        self.pac.update(dt, self)
        if self.state != "play":
            return
        for g in self.ghosts:
            g.update(dt, self)

        # collisions
        px, py = self.pac.pos()
        for g in self.ghosts:
            if g.state in ("eaten", "house"):
                continue
            gx, gy = g.pos()
            if (gx - px) ** 2 + (gy - py) ** 2 < 0.55 ** 2:
                if g.fright:
                    pts = 200 * (2 ** self.combo)
                    self.combo = min(self.combo + 1, 3)
                    self.add_score(pts)
                    g.state = "eaten"
                    g.fright = False
                    g.hide = True
                    self.freeze = 0.7
                    sx, sy = self.px(gx, gy)
                    self.popups.append([str(pts), sx, sy, 0.9])
                    self.burst(sx, sy, (120, 160, 255), 14, 110)
                    self.snd.play("eatghost")
                else:
                    self.kill_pacman()
                    return

        if self.fruit is not None and (px - 14.0) ** 2 + (py - 17.5) ** 2 < 0.8 ** 2:
            name, val = self.fruit_kind()
            self.add_score(val)
            self.fruit = None
            sx, sy = self.px(14.0, 17.5)
            self.popups.append([str(val), sx, sy, 1.2])
            self.snd.play("fruit")

    def update_loops(self):
        if self.state != "play" or self.paused:
            self.snd.set_loop(None)
            return
        if any(g.state == "eaten" for g in self.ghosts):
            self.snd.set_loop("retreat")
        elif self.fright_timer > 0:
            self.snd.set_loop("fright")
        else:
            frac = self.remaining() / max(1, len(DOTS) + len(PELLETS))
            self.snd.set_loop("siren1" if frac > 0.55 else "siren2" if frac > 0.25 else "siren3")

    # ---------------- drawing helpers -----------------
    def text(self, s, font, color, x, y, anchor="center", outline=None):
        img = font.render(s, True, color)
        rect = img.get_rect(**{anchor: (x, y)})
        if outline:
            shade = font.render(s, True, outline)
            for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
                self.screen.blit(shade, rect.move(ox, oy))
        self.screen.blit(img, rect)

    def ghost_sprite(self, color, frame):
        key = (color, frame)
        if key not in self.ghost_cache:
            self.ghost_cache[key] = ghost_body(color, frame, GHOST_R)
        return self.ghost_cache[key]

    def draw_ghost_sprite(self, px, py, color, d, fright=False, flash=False,
                          eyes_only=False, t=0.0):
        scr, r = self.screen, GHOST_R
        if not eyes_only:
            body = ((240, 240, 255) if flash else (30, 45, 235)) if fright else color
            spr = self.ghost_sprite(body, int(t * 8) % 2)
            scr.blit(spr, spr.get_rect(center=(px, py)))
        if fright and not eyes_only:
            face = (255, 30, 30) if flash else (255, 205, 185)
            for sx in (-1, 1):
                pygame.draw.rect(scr, face, (px + sx * r * 0.36 - 2, py - r * 0.3 - 2, 4, 4))
            pts = [(px - r * 0.72 + i * (r * 1.44 / 6), py + r * 0.38 + (-2 if i % 2 == 0 else 2))
                   for i in range(7)]
            pygame.draw.lines(scr, face, False, pts, 2)
        else:
            er = r * 0.33
            for sx in (-1, 1):
                ex, ey = px + sx * r * 0.40, py - r * 0.18
                gfx.filled_ellipse(scr, int(ex), int(ey), int(er * 0.95), int(er * 1.25), WHITE)
                gfx.aaellipse(scr, int(ex), int(ey), int(er * 0.95), int(er * 1.25), WHITE)
                aacircle(scr, ex + d[0] * er * 0.5, ey + d[1] * er * 0.55,
                         max(2, er * 0.55), (25, 55, 215))

    def draw_pac_at(self, px, py, angle, mouth, glow=True):
        key = (round(angle, 2), int(mouth * 25))
        spr = self.pac_cache.get(key)
        if spr is None:
            if len(self.pac_cache) > 400:
                self.pac_cache.clear()
            spr = self.pac_cache[key] = pac_surface(PAC_R, angle, mouth)
        if glow:
            self.screen.blit(self.pac_glow, self.pac_glow.get_rect(center=(px, py)))
        self.screen.blit(spr, spr.get_rect(center=(px, py)))

    def pac_mouth(self):
        return 0.03 + 0.62 * abs(math.sin(self.pac.phase))

    # ---------------- drawing -----------------
    def draw(self):
        scr = self.screen
        scr.fill(BLACK)
        if self.state == "title":
            self.draw_title()
        else:
            self.draw_world()
            self.draw_hud()
        if self.paused:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 160))
            scr.blit(veil, (0, 0))
            self.text("PAUSED", self.f_l, YELLOW, W // 2, H // 2, outline=(120, 80, 0))
            self.text("press P to resume", self.f_s, WHITE, W // 2, H // 2 + 60)
        pygame.display.flip()

    def draw_world(self):
        scr, s = self.screen, self.state
        elapsed_win = 2.6 - self.timer if s == "win" else 0
        maze = self.maze_blue
        if s == "win" and elapsed_win > 0.8 and int((elapsed_win - 0.8) / 0.22) % 2 == 0:
            maze = self.maze_white
        scr.blit(maze, (0, HUD_TOP))
        # ghost-house door
        dy = HUD_TOP + 12 * T + T // 2 - 2
        pygame.draw.rect(scr, PINK_DOOR, (13 * T + 1, dy, 2 * T - 2, 4), border_radius=2)

        # dots
        dr = max(2, T // 7)
        for c, r in self.dots:
            pygame.draw.circle(scr, DOT_COLOR, (c * T + T // 2, HUD_TOP + r * T + T // 2), dr)
        if s != "win" or elapsed_win < 0.8:
            blink = s != "play" or int(self.t * 3.6) % 2 == 0
            if blink:
                pr = int(T * 0.36)
                for c, r in self.pellets:
                    cx, cy = c * T + T // 2, HUD_TOP + r * T + T // 2
                    aacircle(scr, cx, cy, pr + 3, (60, 55, 50))
                    aacircle(scr, cx, cy, pr, (255, 235, 215))

        # fruit
        if self.fruit is not None:
            x, y = self.px(14.0, 17.5)
            draw_fruit(scr, x, y + math.sin(self.t * 5) * 1.5, self.fruit_kind()[0], 1.15)

        # ghosts
        show_ghosts = (s in ("ready", "play", "gameover")
                       or (s == "dying" and 2.4 - self.timer < 0.8)
                       or (s == "win" and elapsed_win < 0.7))
        if show_ghosts:
            flash = 0 < self.fright_timer < 2.0 and int(self.t * 6) % 2 == 0
            for g in self.ghosts:
                if g.hide:
                    continue
                x, y = g.pos()
                if g.state == "house":
                    y += 0.18 * math.sin(self.t * 7 + g.bob)
                px, py = self.px(x, y)
                self.draw_ghost_sprite(px, py, g.color, g.dir, g.fright, flash,
                                       g.state == "eaten", self.t)

        # pac-man
        if s in ("ready", "play", "win"):
            x, y = self.pac.pos()
            px, py = self.px(x, y)
            ang = math.atan2(self.pac.dir[1], self.pac.dir[0])
            mouth = 0.5 if s == "ready" else self.pac_mouth()
            self.draw_pac_at(px, py, ang, mouth)
        elif s == "dying":
            x, y = self.pac.pos()
            px, py = self.px(x, y)
            k = (2.4 - self.timer - 0.8) / 1.4
            if k <= 0:
                ang = math.atan2(self.pac.dir[1], self.pac.dir[0])
                self.draw_pac_at(px, py, ang, 0.35)
            elif k < 1:
                self.draw_pac_at(px, py, -math.pi / 2, 0.05 + k * (math.pi - 0.1), glow=False)

        # particles & popups
        for x, y, vx, vy, life, _, col in self.particles:
            a = max(0.0, min(1.0, life / 0.5))
            c = tuple(int(v * a) for v in col)
            pygame.draw.circle(scr, c, (int(x), int(y)), 2 + int(2 * a))
        for txt, x, y, life in self.popups:
            self.text(txt, self.f_s, (0, 255, 255), x, y - (1 - min(1, life)) * 12,
                      outline=(0, 60, 80))

        # banners
        cy = HUD_TOP + 17 * T + T // 2
        if s == "ready":
            self.text("READY!", self.f_m, YELLOW, W // 2, cy, outline=(110, 70, 0))
        elif s == "gameover":
            self.text("GAME OVER", self.f_m, (255, 40, 40), W // 2, cy, outline=(90, 0, 0))

    def draw_hud(self):
        scr = self.screen
        blink = int(self.t * 2.5) % 2 == 0
        self.text("1UP", self.f_s, WHITE if blink else (120, 120, 120), 3 * T, 14)
        self.text("%06d" % self.score, self.f_s, WHITE, 3 * T, 38)
        self.text("HIGH SCORE", self.f_s, WHITE, W // 2, 14)
        self.text("%06d" % self.high, self.f_s, WHITE, W // 2, 38)
        self.text("LEVEL", self.f_s, WHITE, W - 3 * T, 14)
        self.text(str(self.level), self.f_s, (255, 215, 80), W - 3 * T, 38)

        y = HUD_TOP + ROWS * T + HUD_BOT // 2 + 2
        n = max(0, self.lives - (0 if self.state == "gameover" else 1))
        for i in range(min(n, 6)):
            spr = pac_surface(int(T * 0.5), math.pi, 0.45)
            scr.blit(spr, spr.get_rect(center=(T + 12 + i * int(T * 1.5), y)))
        shown = FRUITS[:min(self.level, len(FRUITS))][-5:]
        for i, (name, _) in enumerate(reversed(shown)):
            draw_fruit(scr, W - T - 8 - i * int(T * 1.6), y, name, 0.85)

    # ---------------- title screen -----------------
    def draw_title(self):
        scr, t = self.screen, self.t
        # drifting star dots in the background
        for i in range(40):
            sx = (i * 97 + t * (6 + i % 5)) % W
            sy = (i * 61) % H
            v = 60 + (i * 37) % 80
            scr.set_at((int(sx), int(sy)), (v, v, v + 40))

        self.text("HIGH SCORE  %06d" % self.high, self.f_s, WHITE, W // 2, 34)
        wob = math.sin(t * 2.2) * 4
        self.text("PACMAN", self.f_l, YELLOW, W // 2, 140 + wob, outline=(150, 90, 0))

        # chase animation
        u = t % 14.0
        y = 255
        cols = [(255, 30, 30), (255, 150, 255), (0, 235, 255), (255, 175, 60)]
        dirs = [LEFT, RIGHT]
        if u < 7:
            x = W + 60 - (u / 7) * (W + 280)
            d = LEFT
            self.draw_pac_at(int(x), y, math.pi, 0.03 + 0.62 * abs(math.sin(t * 15)))
            for i, c in enumerate(cols):
                self.draw_ghost_sprite(int(x + 50 + i * 38), y, c, d, t=t)
        else:
            x = -60 + ((u - 7) / 7) * (W + 280)
            self.draw_pac_at(int(x), y, 0, 0.03 + 0.62 * abs(math.sin(t * 15)))
            fl = (u - 7) > 5.0 and int(t * 6) % 2 == 0
            for i, c in enumerate(cols):
                self.draw_ghost_sprite(int(x + 60 + i * 38), y, c, RIGHT, True, fl, t=t)

        # cast list
        cast = [("BLINKY", "chases you down", cols[0]), ("PINKY", "ambushes ahead", cols[1]),
                ("INKY", "flanks unpredictably", cols[2]), ("CLYDE", "wanders off shyly", cols[3])]
        for i, (nm, desc, col) in enumerate(cast):
            yy = 345 + i * 52
            self.draw_ghost_sprite(95, yy, col, RIGHT, t=t)
            self.text(nm, self.f_s, col, 135, yy, "midleft")
            self.text(desc, self.f_s, (200, 200, 220), 250, yy, "midleft")

        # points info
        base = 585
        pygame.draw.circle(scr, DOT_COLOR, (95, base), 3)
        self.text("10 pts", self.f_s, WHITE, 135, base, "midleft")
        aacircle(scr, 95, base + 32, 8, (255, 235, 215))
        self.text("50 pts  - eat ghosts!", self.f_s, WHITE, 135, base + 32, "midleft")

        if int(t * 2) % 2 == 0:
            self.text("PRESS ENTER TO START", self.f_m, YELLOW, W // 2, 665)
        self.text("ARROWS / WASD move    P pause    M mute    ESC quit",
                  self.f_s, (150, 150, 180), W // 2, 715)

    # ---------------- main loop -----------------
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            self.save_high()
            pygame.quit()
            sys.exit()
        if key == pygame.K_m:
            self.snd.toggle_mute()
            return
        if key == pygame.K_p and self.state not in ("title",):
            self.paused = not self.paused
            if self.snd.ok:
                (pygame.mixer.pause if self.paused else pygame.mixer.unpause)()
            return
        if self.state == "title":
            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.start_game()
            return
        keymap = {pygame.K_UP: UP, pygame.K_w: UP, pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
                  pygame.K_LEFT: LEFT, pygame.K_a: LEFT, pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT}
        if key in keymap:
            self.pac.want = keymap[key]

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.save_high()
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.KEYDOWN:
                    self.handle_key(e.key)
            if not self.paused:
                self.update(dt)
            self.draw()


def main():
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    Game().run()


if __name__ == "__main__":
    main()
