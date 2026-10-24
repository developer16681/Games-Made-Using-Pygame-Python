#!/usr/bin/env python3
"""
NEON SNAKE - a polished Snake game with smooth animation, particles,
procedurally generated chiptune music and sound effects.

Requirements:  pip install pygame
Run:           python snake_game.py

Controls:
  Arrow keys / WASD  - steer
  P                  - pause
  M                  - toggle music
  N                  - toggle sound effects
  SPACE / ENTER      - start / restart
  ESC                - quit
"""
import array
import math
import os
import random
import sys

import pygame

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
CELL = 28
COLS, ROWS = 24, 20
HUD_H = 64
W, H = COLS * CELL, ROWS * CELL + HUD_H
FPS = 60
SAMPLE_RATE = 44100

BG_A = (18, 28, 36)
BG_B = (22, 34, 43)
WALL = (60, 220, 170)
TEXT = (230, 240, 245)
DIM = (120, 140, 150)
HEAD_COL = (90, 255, 170)
TAIL_COL = (20, 140, 150)
FOOD_COL = (255, 70, 90)
GOLD_COL = (255, 215, 70)

HS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snake_highscore.txt")

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


# --------------------------------------------------------------------------
# Procedural audio
# --------------------------------------------------------------------------
def osc(wave, ph, duty=0.5):
    p = ph % 1.0
    if wave == "square":
        return 1.0 if p < duty else -1.0
    if wave == "triangle":
        return 4.0 * abs(p - 0.5) - 1.0
    if wave == "saw":
        return 2.0 * p - 1.0
    if wave == "sine":
        return math.sin(2 * math.pi * p)
    return random.uniform(-1, 1)  # noise


def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def add_note(buf, start, dur, freq, vol, wave="square", duty=0.5, sweep_to=None):
    s0 = int(start * SAMPLE_RATE)
    n = int(dur * SAMPLE_RATE)
    attack = max(1, int(0.004 * SAMPLE_RATE))
    phase = 0.0
    for i in range(n):
        if s0 + i >= len(buf):
            break
        f = freq if sweep_to is None else freq + (sweep_to - freq) * (i / n)
        phase += f / SAMPLE_RATE
        env = min(1.0, i / attack) * (1.0 - i / n) ** 1.5
        buf[s0 + i] += osc(wave, phase, duty) * vol * env


def to_sound(buf, volume=1.0):
    data = array.array("h", [int(max(-1.0, min(1.0, s)) * 32000) for s in buf])
    snd = pygame.mixer.Sound(buffer=data.tobytes())
    snd.set_volume(volume)
    return snd


def blank(seconds):
    return [0.0] * int(seconds * SAMPLE_RATE)


def build_eat():
    b = blank(0.22)
    add_note(b, 0.00, 0.09, midi_freq(76), 0.35, "square", 0.25)
    add_note(b, 0.07, 0.14, midi_freq(83), 0.35, "square", 0.25)
    return to_sound(b)


def build_bonus():
    b = blank(0.5)
    for i, m in enumerate([72, 76, 79, 84, 88]):
        add_note(b, i * 0.07, 0.15, midi_freq(m), 0.3, "square", 0.5)
        add_note(b, i * 0.07, 0.15, midi_freq(m + 12), 0.1, "triangle")
    return to_sound(b)


def build_turn():
    b = blank(0.04)
    add_note(b, 0, 0.035, 520, 0.08, "triangle")
    return to_sound(b)


def build_die():
    b = blank(1.0)
    add_note(b, 0.0, 0.8, 440, 0.35, "saw", sweep_to=50)
    add_note(b, 0.0, 0.35, 200, 0.25, "noise")
    add_note(b, 0.0, 0.9, 220, 0.25, "square", 0.5, sweep_to=35)
    return to_sound(b)


def build_start():
    b = blank(0.6)
    for i, m in enumerate([60, 64, 67, 72]):
        add_note(b, i * 0.1, 0.2, midi_freq(m), 0.3, "square", 0.25)
    return to_sound(b)


def build_music():
    """An 8-bar looping chiptune track (Am - F - C - G, twice)."""
    bpm = 132
    eighth = 60.0 / bpm / 2
    bar = eighth * 8
    total = bar * 8
    b = blank(total)

    prog = [  # (bass root, arpeggio chord tones)
        (45, (57, 60, 64)),   # Am
        (41, (53, 57, 60)),   # F
        (48, (55, 60, 64)),   # C
        (43, (55, 59, 62)),   # G
    ]
    lead = [
        [76, None, 72, None, 74, 76, None, 79],
        [77, None, 76, 72, None, 69, None, 72],
        [76, None, 79, None, 84, None, 79, 76],
        [74, None, 71, 74, 79, None, 74, None],
    ]

    for bar_i in range(8):
        root, chord = prog[bar_i % 4]
        t0 = bar_i * bar
        for e in range(8):
            t = t0 + e * eighth
            # driving bass: root on every eighth, octave jump on off-beats
            bm = root + (12 if e % 4 == 3 else 0)
            add_note(b, t, eighth * 0.9, midi_freq(bm), 0.16, "square", 0.35)
            # arpeggio in 16ths
            for k in range(2):
                tone = chord[(e * 2 + k) % 3] + 12
                add_note(b, t + k * eighth / 2, eighth * 0.45, midi_freq(tone), 0.11, "triangle")
            # percussion: kick on 0/4, hat on odd, snare on 2/6
            if e % 4 == 0:
                add_note(b, t, 0.12, 140, 0.30, "sine", sweep_to=45)
            if e % 4 == 2:
                add_note(b, t, 0.09, 1, 0.12, "noise")
            if e % 2 == 1:
                add_note(b, t, 0.03, 1, 0.04, "noise")
            # lead melody in the second half of the loop
            if bar_i >= 4:
                m = lead[bar_i - 4][e]
                if m:
                    add_note(b, t, eighth * 1.3, midi_freq(m), 0.13, "square", 0.25)
    return to_sound(b, 0.45)


class Audio:
    def __init__(self):
        self.ok = False
        self.music_on = True
        self.sfx_on = True
        try:
            pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
            pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
            pygame.mixer.set_num_channels(12)
            self.eat = build_eat()
            self.bonus = build_bonus()
            self.turn = build_turn()
            self.die = build_die()
            self.start = build_start()
            self.music = build_music()
            self.music_ch = None
            self.ok = True
        except Exception as exc:  # no audio device etc.
            print("Audio disabled:", exc)

    def play(self, name):
        if self.ok and self.sfx_on:
            getattr(self, name).play()

    def start_music(self):
        if self.ok and self.music_on:
            self.music_ch = self.music.play(loops=-1)

    def stop_music(self):
        if self.ok:
            self.music.stop()

    def toggle_music(self, playing):
        self.music_on = not self.music_on
        if not self.ok:
            return
        if self.music_on and playing:
            self.start_music()
        else:
            self.stop_music()

    def pause_music(self, paused):
        if self.ok and self.music_on:
            pygame.mixer.pause() if paused else pygame.mixer.unpause()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def make_glow(radius, color):
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        a = int(110 * (1 - r / radius) ** 2)
        pygame.draw.circle(surf, (*color, a), (radius, radius), r)
    return surf


def load_hs():
    try:
        with open(HS_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def save_hs(v):
    try:
        with open(HS_FILE, "w") as f:
            f.write(str(v))
    except Exception:
        pass


def draw_text(surf, font, text, color, center=None, topleft=None, topright=None, shadow=True):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif topright:
        rect.topright = topright
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        surf.blit(sh, rect.move(2, 2))
    surf.blit(img, rect)
    return rect


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Neon Snake")
        self.screen = pygame.display.set_mode((W, H))
        self.canvas = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.audio = Audio()

        self.f_big = pygame.font.Font(None, 84)
        self.f_mid = pygame.font.Font(None, 40)
        self.f_small = pygame.font.Font(None, 26)

        self.board = self.build_board()
        self.glow_red = make_glow(46, FOOD_COL)
        self.glow_gold = make_glow(54, GOLD_COL)
        self.glow_head = make_glow(40, HEAD_COL)
        self.stars = [(random.randrange(W), random.randrange(H), random.random()) for _ in range(40)]

        self.high = load_hs()
        self.state = "menu"
        self.t = 0.0
        self.particles = []
        self.shake = 0.0
        self.reset()

    # ----- setup -----
    def build_board(self):
        surf = pygame.Surface((COLS * CELL, ROWS * CELL))
        for y in range(ROWS):
            for x in range(COLS):
                c = BG_A if (x + y) % 2 == 0 else BG_B
                pygame.draw.rect(surf, c, (x * CELL, y * CELL, CELL, CELL))
        return surf

    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.prev = list(self.snake)
        self.dir = RIGHT
        self.queue = []
        self.score = 0
        self.eaten = 0
        self.grow = 0
        self.acc = 0.0
        self.food = None
        self.bonus = None  # (pos, time_left)
        self.food_pulse = 0.0
        self.popups = []
        self.spawn_food()

    @property
    def delay(self):
        return max(0.065, 0.15 - self.eaten * 0.004)

    def free_cell(self):
        occupied = set(self.snake)
        if self.food:
            occupied.add(self.food)
        if self.bonus:
            occupied.add(self.bonus[0])
        while True:
            p = (random.randrange(COLS), random.randrange(ROWS))
            if p not in occupied:
                return p

    def spawn_food(self):
        self.food = self.free_cell()

    # ----- helpers -----
    def cell_center(self, p):
        return (p[0] * CELL + CELL / 2, p[1] * CELL + CELL / 2 + HUD_H)

    def burst(self, p, color, n=22, speed=170):
        cx, cy = self.cell_center(p)
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(speed * 0.3, speed)
            self.particles.append({
                "x": cx, "y": cy,
                "vx": math.cos(a) * s, "vy": math.sin(a) * s,
                "life": random.uniform(0.4, 0.9), "max": 0.9,
                "col": color, "r": random.uniform(2, 5),
            })

    # ----- logic -----
    def steer(self, d):
        last = self.queue[-1] if self.queue else self.dir
        if d == last or (d[0] == -last[0] and d[1] == -last[1]):
            return
        if len(self.queue) < 2:
            self.queue.append(d)
            self.audio.play("turn")

    def step(self):
        if self.queue:
            self.dir = self.queue.pop(0)
        hx, hy = self.snake[0]
        nh = (hx + self.dir[0], hy + self.dir[1])

        tail_moves = self.grow == 0
        body = self.snake[:-1] if tail_moves else self.snake
        if not (0 <= nh[0] < COLS and 0 <= nh[1] < ROWS) or nh in body:
            self.die()
            return

        old = list(self.snake)
        self.snake.insert(0, nh)
        if self.grow > 0:
            self.grow -= 1
            self.prev = old + [old[-1]]
        else:
            self.snake.pop()
            self.prev = old

        if nh == self.food:
            self.eaten += 1
            self.score += 10
            self.grow += 1
            self.audio.play("eat")
            self.burst(nh, FOOD_COL)
            self.popups.append([self.cell_center(nh), "+10", FOOD_COL, 1.0])
            self.spawn_food()
            if self.eaten % 5 == 0 and not self.bonus:
                self.bonus = [self.free_cell(), 7.0]
        elif self.bonus and nh == self.bonus[0]:
            self.score += 50
            self.grow += 2
            self.audio.play("bonus")
            self.burst(nh, GOLD_COL, 40, 240)
            self.popups.append([self.cell_center(nh), "+50", GOLD_COL, 1.2])
            self.bonus = None

    def die(self):
        self.state = "over"
        self.audio.stop_music()
        self.audio.play("die")
        self.shake = 0.5
        self.burst(self.snake[0], HEAD_COL, 50, 260)
        if self.score > self.high:
            self.high = self.score
            save_hs(self.high)

    def start(self):
        self.reset()
        self.state = "play"
        self.audio.play("start")
        self.audio.stop_music()
        self.audio.start_music()

    def update(self, dt):
        self.t += dt
        self.food_pulse += dt * 5

        for p in self.particles:
            p["life"] -= dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vx"] *= 0.97
            p["vy"] *= 0.97
        self.particles = [p for p in self.particles if p["life"] > 0]
        for pop in self.popups:
            pop[3] -= dt
            pop[0] = (pop[0][0], pop[0][1] - 40 * dt)
        self.popups = [p for p in self.popups if p[3] > 0]
        self.shake = max(0.0, self.shake - dt)

        if self.state != "play":
            return
        if self.bonus:
            self.bonus[1] -= dt
            if self.bonus[1] <= 0:
                self.bonus = None

        self.acc += dt
        while self.acc >= self.delay and self.state == "play":
            self.acc -= self.delay
            self.step()

    # ----- drawing -----
    def draw_background(self, s):
        s.fill((10, 16, 22))
        for x, y, ph in self.stars:
            a = 0.5 + 0.5 * math.sin(self.t * 1.5 + ph * 6)
            c = int(40 + 60 * a)
            s.set_at((x, y), (c, c, c + 20))
        s.blit(self.board, (0, HUD_H))
        pygame.draw.rect(s, WALL, (0, HUD_H, COLS * CELL, ROWS * CELL), 3, border_radius=4)

    def draw_hud(self, s):
        pygame.draw.rect(s, (14, 22, 30), (0, 0, W, HUD_H))
        pygame.draw.line(s, WALL, (0, HUD_H - 1), (W, HUD_H - 1), 2)
        draw_text(s, self.f_mid, f"SCORE  {self.score}", TEXT, topleft=(18, 12))
        draw_text(s, self.f_small, f"LENGTH {len(self.snake)}", DIM, topleft=(20, 42))
        draw_text(s, self.f_mid, f"BEST  {self.high}", GOLD_COL, topright=(W - 18, 12))
        icons = f"music {'ON' if self.audio.music_on else 'OFF'}  |  sfx {'ON' if self.audio.sfx_on else 'OFF'}"
        draw_text(s, self.f_small, icons, DIM, topright=(W - 20, 42), shadow=False)

    def draw_food(self, s):
        if self.food:
            cx, cy = self.cell_center(self.food)
            pulse = 1 + 0.12 * math.sin(self.food_pulse)
            g = pygame.transform.smoothscale(self.glow_red, (int(92 * pulse), int(92 * pulse)))
            s.blit(g, g.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGBA_ADD)
            r = int(CELL * 0.38 * pulse)
            pygame.draw.circle(s, (170, 20, 45), (cx, cy + 1), r)
            pygame.draw.circle(s, FOOD_COL, (cx, cy), r - 1)
            pygame.draw.circle(s, (255, 150, 160), (cx - r * 0.35, cy - r * 0.35), max(2, r // 3))
            pygame.draw.line(s, (110, 70, 40), (cx, cy - r), (cx + 3, cy - r - 5), 2)
            pygame.draw.ellipse(s, (80, 220, 100), (cx + 2, cy - r - 8, 9, 5))

        if self.bonus:
            pos, left = self.bonus
            if left > 2 or int(self.t * 8) % 2 == 0:
                cx, cy = self.cell_center(pos)
                pulse = 1 + 0.18 * math.sin(self.t * 9)
                g = pygame.transform.smoothscale(self.glow_gold, (int(110 * pulse), int(110 * pulse)))
                s.blit(g, g.get_rect(center=(cx, cy)), special_flags=pygame.BLEND_RGBA_ADD)
                pts = []
                for i in range(10):
                    rad = (CELL * 0.48 if i % 2 == 0 else CELL * 0.2) * pulse
                    a = self.t * 2 + i * math.pi / 5 - math.pi / 2
                    pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
                pygame.draw.polygon(s, GOLD_COL, pts)
                pygame.draw.polygon(s, (255, 250, 200), pts, 2)
                # countdown bar
                w = CELL * left / 7.0
                pygame.draw.rect(s, GOLD_COL, (cx - CELL / 2, cy + CELL / 2 + 2, w, 3))

    def snake_points(self):
        t = 1.0 if self.state != "play" else min(1.0, self.acc / self.delay)
        # ease for a smoother glide
        t = t * t * (3 - 2 * t) if self.state == "play" else 1.0
        pts = []
        for i, cur in enumerate(self.snake):
            pv = self.prev[i] if i < len(self.prev) else cur
            x = lerp(pv[0], cur[0], t)
            y = lerp(pv[1], cur[1], t)
            pts.append((x * CELL + CELL / 2, y * CELL + CELL / 2 + HUD_H))
        return pts

    def draw_snake(self, s):
        pts = self.snake_points()
        n = len(pts)
        if self.state == "over" and int(self.t * 10) % 2 == 0:
            body_tint = (255, 90, 90)
        else:
            body_tint = None

        # shadow
        for p in pts:
            pygame.draw.circle(s, (6, 10, 14), (p[0] + 3, p[1] + 4), CELL * 0.42)

        # body from tail to head
        for i in range(n - 1, -1, -1):
            k = i / max(1, n - 1)
            col = lerp_col(HEAD_COL, TAIL_COL, k)
            if body_tint:
                col = lerp_col(col, body_tint, 0.7)
            r = CELL * (0.46 - 0.12 * k)
            if i < n - 1:
                a, b = pts[i], pts[i + 1]
                pygame.draw.line(s, col, a, b, int(r * 2))
            pygame.draw.circle(s, col, pts[i], r)
            # belly highlight / scale pattern
            if i % 2 == 0 and i > 0:
                pygame.draw.circle(s, lerp_col(col, (255, 255, 255), 0.18), pts[i], r * 0.55)

        # head
        hx, hy = pts[0]
        g = self.glow_head
        s.blit(g, g.get_rect(center=(hx, hy)), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.circle(s, lerp_col(HEAD_COL, (255, 255, 255), 0.25), (hx, hy), CELL * 0.5)
        pygame.draw.circle(s, HEAD_COL, (hx, hy), CELL * 0.46)

        dx, dy = self.dir
        px, py = -dy, dx  # perpendicular
        # tongue
        if self.state == "play" and int(self.t * 3) % 3 == 0:
            tx, ty = hx + dx * CELL * 0.5, hy + dy * CELL * 0.5
            ex, ey = hx + dx * CELL * 0.85, hy + dy * CELL * 0.85
            pygame.draw.line(s, (255, 70, 110), (tx, ty), (ex, ey), 2)
            pygame.draw.line(s, (255, 70, 110), (ex, ey), (ex + dx * 4 + px * 4, ey + dy * 4 + py * 4), 2)
            pygame.draw.line(s, (255, 70, 110), (ex, ey), (ex + dx * 4 - px * 4, ey + dy * 4 - py * 4), 2)
        # eyes (look toward food)
        for sgn in (-1, 1):
            ex = hx + dx * CELL * 0.14 + px * sgn * CELL * 0.22
            ey = hy + dy * CELL * 0.14 + py * sgn * CELL * 0.22
            pygame.draw.circle(s, (255, 255, 255), (ex, ey), CELL * 0.15)
            lx, ly = 0, 0
            if self.food:
                fx, fy = self.cell_center(self.food)
                d = math.hypot(fx - ex, fy - ey) or 1
                lx, ly = (fx - ex) / d * 2, (fy - ey) / d * 2
            pygame.draw.circle(s, (10, 20, 30), (ex + lx, ey + ly), CELL * 0.08)

    def draw_particles(self, s):
        for p in self.particles:
            a = max(0.0, p["life"] / p["max"])
            r = max(1, int(p["r"] * a + 1))
            col = lerp_col((0, 0, 0), p["col"], a)
            pygame.draw.circle(s, col, (int(p["x"]), int(p["y"])), r)
        for pos, txt, col, life in self.popups:
            a = min(1.0, life)
            img = self.f_mid.render(txt, True, lerp_col((0, 0, 0), col, a))
            s.blit(img, img.get_rect(center=pos))

    def overlay(self, s, alpha=150):
        dark = pygame.Surface((W, H), pygame.SRCALPHA)
        dark.fill((5, 10, 15, alpha))
        s.blit(dark, (0, 0))

    def draw_menu(self, s):
        self.overlay(s, 170)
        bob = math.sin(self.t * 2) * 6
        title_col = lerp_col(HEAD_COL, (90, 200, 255), (math.sin(self.t * 2) + 1) / 2)
        draw_text(s, self.f_big, "NEON SNAKE", title_col, center=(W // 2, H // 2 - 90 + bob))
        draw_text(s, self.f_mid, "Press SPACE to start", TEXT, center=(W // 2, H // 2 - 10))
        lines = [
            "Arrow keys / WASD  -  steer",
            "P  -  pause     M  -  music     N  -  sound fx",
            "Eat apples to grow. Grab the golden star for bonus points!",
        ]
        for i, ln in enumerate(lines):
            draw_text(s, self.f_small, ln, DIM, center=(W // 2, H // 2 + 50 + i * 28))
        if self.high:
            draw_text(s, self.f_small, f"Best score: {self.high}", GOLD_COL, center=(W // 2, H // 2 + 150))

    def draw_over(self, s):
        self.overlay(s, 150)
        draw_text(s, self.f_big, "GAME OVER", (255, 90, 100), center=(W // 2, H // 2 - 70))
        draw_text(s, self.f_mid, f"Score: {self.score}", TEXT, center=(W // 2, H // 2 - 5))
        if self.score >= self.high and self.score > 0:
            draw_text(s, self.f_mid, "NEW HIGH SCORE!", GOLD_COL, center=(W // 2, H // 2 + 35))
        else:
            draw_text(s, self.f_small, f"Best: {self.high}", GOLD_COL, center=(W // 2, H // 2 + 35))
        draw_text(s, self.f_small, "SPACE to play again   |   ESC to quit", DIM, center=(W // 2, H // 2 + 85))

    def draw_pause(self, s):
        self.overlay(s, 150)
        draw_text(s, self.f_big, "PAUSED", TEXT, center=(W // 2, H // 2 - 20))
        draw_text(s, self.f_small, "Press P to resume", DIM, center=(W // 2, H // 2 + 35))

    def draw(self):
        s = self.canvas
        self.draw_background(s)
        self.draw_food(s)
        self.draw_snake(s)
        self.draw_particles(s)
        self.draw_hud(s)
        if self.state == "menu":
            self.draw_menu(s)
        elif self.state == "over":
            self.draw_over(s)
        elif self.state == "pause":
            self.draw_pause(s)

        ox = oy = 0
        if self.shake > 0:
            m = self.shake * 18
            ox, oy = random.uniform(-m, m), random.uniform(-m, m)
        self.screen.fill((0, 0, 0))
        self.screen.blit(s, (ox, oy))
        pygame.display.flip()

    # ----- main loop -----
    def handle_key(self, key):
        keymap = {
            pygame.K_UP: UP, pygame.K_w: UP,
            pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
            pygame.K_LEFT: LEFT, pygame.K_a: LEFT,
            pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
        }
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_m:
            self.audio.toggle_music(self.state == "play")
        elif key == pygame.K_n:
            self.audio.sfx_on = not self.audio.sfx_on
        elif self.state in ("menu", "over"):
            if key in (pygame.K_SPACE, pygame.K_RETURN):
                self.start()
        elif self.state == "play":
            if key in keymap:
                self.steer(keymap[key])
            elif key == pygame.K_p:
                self.state = "pause"
                self.audio.pause_music(True)
        elif self.state == "pause":
            if key == pygame.K_p:
                self.state = "play"
                self.audio.pause_music(False)
        return True

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    running = self.handle_key(e.key) and running
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()