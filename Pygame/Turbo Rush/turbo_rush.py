"""
TURBO RUSH - a top-down traffic racer
-------------------------------------
Requires:  pip install pygame
Run:       python turbo_rush.py

Controls
  LEFT/RIGHT or A/D ... steer
  SPACE / UP .......... nitro (uses the blue bar, refilled by coins)
  P ................... pause      M ... mute      ESC ... quit
  ENTER ............... start / restart

All graphics are drawn with code and all audio is synthesized at start-up,
so no asset files are needed.
"""
import math
import os
import random
import sys
from array import array

import pygame

pygame.mixer.pre_init(22050, -16, 2, 512)
pygame.init()

W, H = 900, 700
FPS = 60
SR = 22050
ROAD_L, LANE_W, LANES = 250, 100, 4
ROAD_R = ROAD_L + LANE_W * LANES
LANE_X = [ROAD_L + LANE_W * i + LANE_W // 2 for i in range(LANES)]

screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("TURBO RUSH")
clock = pygame.time.Clock()
F_BIG = pygame.font.SysFont("arial", 72, bold=True)
F_MED = pygame.font.SysFont("arial", 32, bold=True)
F_SM = pygame.font.SysFont("arial", 20, bold=True)


# --------------------------------------------------------------------------
# Audio synthesis
# --------------------------------------------------------------------------
def to_sound(buf, vol=1.0):
    data = array("h")
    for s in buf:
        v = int(max(-1.0, min(1.0, s * vol)) * 32767)
        data.append(v)
        data.append(v)
    return pygame.mixer.Sound(buffer=data.tobytes())


def add_note(buf, start, freq, dur, wave="sq", vol=0.3, decay=6.0, sweep=0.0):
    n = int(dur * SR)
    phase = 0.0
    for i in range(n):
        idx = start + i
        if idx >= len(buf):
            break
        t = i / SR
        f = freq + sweep * t
        phase += f / SR
        p = phase % 1.0
        if wave == "sq":
            s = 1.0 if p < 0.5 else -1.0
        elif wave == "saw":
            s = 2 * p - 1
        elif wave == "noise":
            s = random.uniform(-1, 1)
        else:
            s = math.sin(2 * math.pi * p)
        env = min(1.0, i / 120) * math.exp(-decay * t / dur)
        buf[idx] += s * env * vol


def make_music():
    bpm = 128
    step = 60.0 / bpm / 4  # 16th note
    bars = 4
    total = int(step * 16 * bars * SR)
    buf = [0.0] * total
    bass = [110.0, 87.31, 130.81, 98.0]  # Am F C G
    chords = [
        [220.0, 261.63, 329.63],
        [174.61, 220.0, 261.63],
        [261.63, 329.63, 392.0],
        [196.0, 246.94, 293.66],
    ]
    pattern = [0, 1, 2, 3, 2, 1, 2, 1] * 2
    for bar in range(bars):
        for s in range(16):
            t0 = int((bar * 16 + s) * step * SR)
            # bass on 8ths
            if s % 2 == 0:
                add_note(buf, t0, bass[bar], step * 1.8, "saw", 0.22, 4)
            # arpeggio
            tones = chords[bar] + [chords[bar][0] * 2]
            add_note(buf, t0, tones[pattern[s]], step * 1.5, "sq", 0.09, 5)
            # drums
            if s % 4 == 0:
                add_note(buf, t0, 130, 0.18, "sine", 0.55, 7, sweep=-300)
            if s % 4 == 2:
                add_note(buf, t0, 0, 0.05, "noise", 0.10, 8)
            if s in (4, 12):
                add_note(buf, t0, 0, 0.14, "noise", 0.20, 6)
    return to_sound(buf, 0.7)


def make_engine_loops():
    """Seamless looping engine hums at 4 pitches."""
    loops = []
    n = SR // 5
    for cycles in (12, 18, 26, 38):
        buf = []
        for i in range(n):
            p = cycles * i / n
            s = 0.0
            for k, a in ((1, 1.0), (2, 0.5), (3, 0.35), (4, 0.2)):
                s += a * math.sin(2 * math.pi * k * p)
            s += 0.15 * math.sin(2 * math.pi * cycles * 0.5 * i / n)
            buf.append(s * 0.35)
        loops.append(to_sound(buf))
    return loops


def make_sfx():
    sfx = {}
    # crash: noise burst + thump
    b = [0.0] * int(0.9 * SR)
    add_note(b, 0, 0, 0.9, "noise", 0.8, 5)
    add_note(b, 0, 90, 0.6, "sine", 0.9, 5, sweep=-80)
    sfx["crash"] = to_sound(b)
    # coin: two rising notes
    b = [0.0] * int(0.3 * SR)
    add_note(b, 0, 988, 0.08, "sq", 0.25, 2)
    add_note(b, int(0.07 * SR), 1319, 0.22, "sq", 0.25, 5)
    sfx["coin"] = to_sound(b)
    # nitro: rising whoosh
    b = [0.0] * int(0.6 * SR)
    add_note(b, 0, 0, 0.6, "noise", 0.35, 2)
    add_note(b, 0, 200, 0.6, "saw", 0.25, 2, sweep=700)
    sfx["nitro"] = to_sound(b)
    # near miss whoosh
    b = [0.0] * int(0.25 * SR)
    add_note(b, 0, 0, 0.25, "noise", 0.3, 4)
    sfx["whoosh"] = to_sound(b)
    # game over jingle
    b = [0.0] * int(1.4 * SR)
    for i, f in enumerate((440, 392, 349, 262)):
        add_note(b, int(i * 0.25 * SR), f, 0.35, "sq", 0.25, 3)
    sfx["over"] = to_sound(b)
    # start beep
    b = [0.0] * int(0.4 * SR)
    add_note(b, 0, 660, 0.12, "sq", 0.25, 2)
    add_note(b, int(0.12 * SR), 880, 0.25, "sq", 0.25, 4)
    sfx["start"] = to_sound(b)
    return sfx


# --------------------------------------------------------------------------
# Graphics helpers
# --------------------------------------------------------------------------
def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def make_car(color, player=False):
    w, h = 46, 86
    s = pygame.Surface((w + 20, h + 20), pygame.SRCALPHA)
    ox, oy = 10, 10
    pygame.draw.ellipse(s, (0, 0, 0, 70), (ox - 2, oy + 6, w + 6, h + 4))
    for wy in (16, 58):  # wheels
        pygame.draw.rect(s, (20, 20, 20), (ox - 3, oy + wy, 8, 18), border_radius=3)
        pygame.draw.rect(s, (20, 20, 20), (ox + w - 5, oy + wy, 8, 18), border_radius=3)
    pygame.draw.rect(s, shade(color, 0.7), (ox, oy, w, h), border_radius=14)
    pygame.draw.rect(s, color, (ox + 2, oy + 2, w - 4, h - 6), border_radius=12)
    pygame.draw.rect(s, shade(color, 1.25), (ox + 15, oy + 4, w - 30, 22), border_radius=6)
    if player:
        pygame.draw.rect(s, (245, 245, 245), (ox + w // 2 - 4, oy + 2, 3, h - 8))
        pygame.draw.rect(s, (245, 245, 245), (ox + w // 2 + 2, oy + 2, 3, h - 8))
    glass = (40, 60, 90)
    pygame.draw.polygon(s, glass, [(ox + 8, oy + 38), (ox + w - 8, oy + 38),
                                    (ox + w - 12, oy + 26), (ox + 12, oy + 26)])
    pygame.draw.rect(s, shade(color, 0.6), (ox + 8, oy + 38, w - 16, 20), border_radius=3)
    pygame.draw.polygon(s, glass, [(ox + 9, oy + 58), (ox + w - 9, oy + 58),
                                    (ox + w - 13, oy + 68), (ox + 13, oy + 68)])
    pygame.draw.ellipse(s, (255, 245, 170), (ox + 4, oy + 2, 11, 7))
    pygame.draw.ellipse(s, (255, 245, 170), (ox + w - 15, oy + 2, 11, 7))
    pygame.draw.rect(s, (230, 20, 20), (ox + 4, oy + h - 7, 11, 4), border_radius=2)
    pygame.draw.rect(s, (230, 20, 20), (ox + w - 15, oy + h - 7, 11, 4), border_radius=2)
    return s


def make_tree(r):
    s = pygame.Surface((r * 2 + 10, r * 2 + 10), pygame.SRCALPHA)
    c = r + 5
    pygame.draw.circle(s, (0, 0, 0, 60), (c + 5, c + 6), r)
    for rad, col in ((r, (24, 98, 44)), (int(r * .75), (34, 128, 58)), (int(r * .45), (56, 160, 78))):
        pygame.draw.circle(s, col, (c, c), rad)
    return s


def make_vignette():
    v = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(70):
        a = int(110 * (1 - i / 70) ** 2.2)
        pygame.draw.rect(v, (0, 0, 0, a), (i, i, W - 2 * i, H - 2 * i), 1)
    return v


CAR_COLORS = [(214, 48, 49), (9, 132, 227), (253, 203, 110), (0, 184, 148),
              (162, 155, 254), (225, 112, 85), (45, 52, 54), (255, 118, 117)]
ENEMY_SURFS = [make_car(c) for c in CAR_COLORS]
PLAYER_SURF = make_car((250, 140, 20), player=True)
TREES = [make_tree(r) for r in (22, 30, 38)]
VIGNETTE = make_vignette()


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------
class Game:
    def __init__(self, sounds):
        self.music, self.engines, self.sfx = sounds
        self.muted = False
        self.best = 0
        self.state = "menu"
        self.t = 0
        self.eng_ch = [pygame.mixer.Channel(i + 1) for i in range(4)]
        self.music_ch = pygame.mixer.Channel(0)
        self.music_ch.play(self.music, loops=-1)
        self.music_ch.set_volume(0.5)
        for ch, snd in zip(self.eng_ch, self.engines):
            ch.play(snd, loops=-1)
            ch.set_volume(0)
        self.trees = [[random.choice((1, -1)), random.randint(0, H), random.choice(TREES), random.randint(0, 90)]
                      for _ in range(14)]
        self.reset()

    def reset(self):
        self.px = LANE_X[1]
        self.vx = 0.0
        self.speed = 6.0
        self.nitro = 100.0
        self.boosting = False
        self.dist = 0.0
        self.coins = 0
        self.bonus = 0
        self.enemies = []
        self.pickups = []
        self.particles = []
        self.spawn_t = 0
        self.scroll = 0.0
        self.shake = 0
        self.paused = False
        self.msgs = []
        self.py = H - 150

    @property
    def score(self):
        return int(self.dist / 10) + self.coins * 50 + self.bonus

    def play(self, name, vol=1.0):
        if not self.muted:
            s = self.sfx[name]
            s.set_volume(vol)
            s.play()

    def toggle_mute(self):
        self.muted = not self.muted
        self.music_ch.set_volume(0 if self.muted else 0.5)

    def start(self):
        self.reset()
        self.state = "play"
        self.play("start")

    # ---- update ----------------------------------------------------------
    def update(self, keys):
        self.t += 1
        if self.state != "play" or self.paused:
            self.engine_audio(0)
            if self.state != "play":
                self.scroll += 2
                self.move_trees(2)
            self.update_particles()
            return

        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        boost = (keys[pygame.K_SPACE] or keys[pygame.K_UP]) and self.nitro > 0

        if boost and not self.boosting:
            self.play("nitro", 0.7)
        self.boosting = boost

        base = min(6 + self.dist / 3000, 12)
        target = base + (6 if boost else 0)
        self.speed += (target - self.speed) * 0.04
        if boost:
            self.nitro = max(0, self.nitro - 0.6)
        else:
            self.nitro = min(100, self.nitro + 0.05)

        # steering
        steer = (right - left) * (0.9 + self.speed * 0.03)
        self.vx = self.vx * 0.86 + steer
        self.px += self.vx
        lo, hi = ROAD_L + 26, ROAD_R - 26
        if self.px < lo or self.px > hi:
            self.px = max(lo, min(hi, self.px))
            self.vx = 0
            self.speed *= 0.995
            self.spark(self.px, self.py)

        self.dist += self.speed
        self.scroll += self.speed
        self.move_trees(self.speed)
        self.engine_audio(self.speed)

        # spawning
        self.spawn_t -= 1
        if self.spawn_t <= 0:
            self.spawn()
            self.spawn_t = max(18, int(60 - self.dist / 400)) + random.randint(0, 15)

        prect = pygame.Rect(0, 0, 34, 74)
        prect.center = (self.px, self.py)

        for e in self.enemies:
            e["y"] += self.speed - e["spd"]
            r = pygame.Rect(0, 0, 34, 74)
            r.center = (e["x"], e["y"])
            if r.colliderect(prect):
                self.crash(e)
                return
            if not e["passed"] and e["y"] > self.py + 40:
                e["passed"] = True
                if abs(e["x"] - self.px) < 70:
                    self.bonus += 10
                    self.msgs.append(["NEAR MISS +10", 60, self.px, self.py - 80])
                    self.play("whoosh", 0.5)
        self.enemies = [e for e in self.enemies if -300 < e["y"] < H + 120]

        for c in self.pickups:
            c["y"] += self.speed
            if math.hypot(c["x"] - self.px, c["y"] - self.py) < 40:
                c["dead"] = True
                self.coins += 1
                self.nitro = min(100, self.nitro + 12)
                self.play("coin", 0.6)
                for _ in range(10):
                    a = random.uniform(0, 6.28)
                    self.particles.append([c["x"], c["y"], math.cos(a) * 3, math.sin(a) * 3,
                                           25, 25, (255, 215, 0), 4])
        self.pickups = [c for c in self.pickups if not c.get("dead") and c["y"] < H + 40]

        # exhaust / nitro flames
        if self.t % 2 == 0:
            if boost:
                for dx in (-12, 12):
                    self.particles.append([self.px + dx, self.py + 44, random.uniform(-.5, .5),
                                           random.uniform(3, 6), 18, 18,
                                           random.choice(((255, 160, 30), (255, 80, 20), (80, 180, 255))), 6])
            else:
                self.particles.append([self.px + random.choice((-12, 12)), self.py + 44,
                                       random.uniform(-.3, .3), random.uniform(1, 2),
                                       22, 22, (150, 150, 150), 4])
        self.update_particles()
        for m in self.msgs:
            m[1] -= 1
            m[3] -= 0.8
        self.msgs = [m for m in self.msgs if m[1] > 0]
        if self.shake:
            self.shake -= 1

    def spawn(self):
        lanes = random.sample(range(LANES), 2 if random.random() < 0.25 else 1)
        for ln in lanes:
            x = LANE_X[ln]
            if any(abs(e["x"] - x) < 5 and e["y"] < 100 for e in self.enemies):
                continue
            self.enemies.append({"x": x, "y": -120, "spd": random.uniform(2.5, 5.5),
                                 "img": random.choice(ENEMY_SURFS), "passed": False})
        if random.random() < 0.45:
            free = [i for i in range(LANES) if i not in lanes]
            if free:
                self.pickups.append({"x": LANE_X[random.choice(free)], "y": -60})

    def crash(self, e):
        self.state = "over"
        self.shake = 30
        self.best = max(self.best, self.score)
        self.play("crash")
        pygame.time.set_timer(pygame.USEREVENT, 600, loops=1)
        for _ in range(60):
            a = random.uniform(0, 6.28)
            sp = random.uniform(1, 7)
            self.particles.append([self.px, self.py, math.cos(a) * sp, math.sin(a) * sp, 45, 45,
                                   random.choice(((255, 140, 0), (255, 60, 30), (90, 90, 90), (255, 220, 80))),
                                   random.randint(4, 9)])
        e["spd"] = 0

    def spark(self, x, y):
        if self.t % 3 == 0:
            self.particles.append([x + random.choice((-24, 24)), y + random.randint(-30, 30),
                                   random.uniform(-2, 2), random.uniform(-2, 2), 10, 10, (255, 230, 120), 2])

    def update_particles(self):
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3] + (self.speed * 0.3 if self.state == "play" else 0)
            p[4] -= 1
        self.particles = [p for p in self.particles if p[4] > 0]

    def move_trees(self, spd):
        for tr in self.trees:
            tr[1] += spd
            if tr[1] > H + 60:
                tr[1] = -60
                tr[0] = random.choice((1, -1))
                tr[2] = random.choice(TREES)
                tr[3] = random.randint(0, 90)

    def engine_audio(self, speed):
        if self.muted or speed == 0:
            for ch in self.eng_ch:
                ch.set_volume(0)
            return
        pos = max(0.0, min(3.0, (speed - 5) / 14 * 3))
        for i, ch in enumerate(self.eng_ch):
            ch.set_volume(max(0.0, 1 - abs(pos - i)) * 0.35)

    # ---- drawing ---------------------------------------------------------
    def draw(self, surf):
        # grass with scrolling stripes
        surf.fill((38, 140, 62))
        off = int(self.scroll) % 160
        for y in range(-160, H + 160, 160):
            pygame.draw.rect(surf, (42, 150, 68), (0, y + off, W, 80))
        # road
        pygame.draw.rect(surf, (52, 55, 62), (ROAD_L, 0, ROAD_R - ROAD_L, H))
        pygame.draw.rect(surf, (62, 66, 74), (ROAD_L + 8, 0, ROAD_R - ROAD_L - 16, H), 0)
        # curbs
        co = int(self.scroll) % 80
        for y in range(-80, H + 80, 40):
            col = (220, 40, 40) if ((y + co) // 40) % 2 == 0 else (240, 240, 240)
            pygame.draw.rect(surf, col, (ROAD_L - 10, y + co, 10, 40))
            pygame.draw.rect(surf, col, (ROAD_R, y + co, 10, 40))
        # lane dashes
        lo = int(self.scroll) % 100
        for i in range(1, LANES):
            x = ROAD_L + i * LANE_W
            for y in range(-100, H + 100, 100):
                pygame.draw.rect(surf, (235, 235, 235), (x - 2, y + lo, 4, 50))
        pygame.draw.rect(surf, (255, 210, 60), (ROAD_L + 4, 0, 3, H))
        pygame.draw.rect(surf, (255, 210, 60), (ROAD_R - 7, 0, 3, H))

        # trees (below cars)
        for side, y, img, jit in self.trees:
            x = (110 + jit) if side < 0 else (W - 110 - jit)
            surf.blit(img, (x - img.get_width() // 2 - (jit // 2 if side < 0 else -jit // 2), y))

        # coins
        for c in self.pickups:
            wdt = max(4, int(abs(math.cos(self.t * 0.12)) * 14))
            pygame.draw.circle(surf, (255, 190, 0, 90), (c["x"], int(c["y"])), 20, 2)
            pygame.draw.ellipse(surf, (255, 205, 20), (c["x"] - wdt, c["y"] - 14, wdt * 2, 28))
            pygame.draw.ellipse(surf, (255, 240, 130), (c["x"] - wdt + 3, c["y"] - 10, max(2, wdt * 2 - 6), 20), 2)

        # enemies
        for e in self.enemies:
            img = e["img"]
            surf.blit(img, img.get_rect(center=(e["x"], e["y"])))

        # player
        if self.state != "over":
            beam = pygame.Surface((160, 260), pygame.SRCALPHA)
            pygame.draw.polygon(beam, (255, 250, 200, 38), [(60, 260), (100, 260), (160, 0), (0, 0)])
            surf.blit(beam, beam.get_rect(midbottom=(self.px, self.py - 30)))
            img = pygame.transform.rotate(PLAYER_SURF, -self.vx * 2.5)
            surf.blit(img, img.get_rect(center=(self.px, self.py)))

        # particles
        for x, y, _, _, life, mx, col, size in self.particles:
            r = max(1, int(size * life / mx))
            pygame.draw.circle(surf, col, (int(x), int(y)), r)

        # speed lines when boosting
        if self.boosting and self.state == "play":
            for _ in range(8):
                x = random.randint(0, W)
                y = random.randint(0, H)
                pygame.draw.line(surf, (255, 255, 255), (x, y), (x, y + random.randint(30, 90)), 1)

        surf.blit(VIGNETTE, (0, 0))
        self.draw_hud(surf)
        for text, life, x, y in self.msgs:
            self.text(surf, text, F_SM, (255, 240, 120), (x, y), True)

        if self.state == "menu":
            self.overlay(surf, "TURBO RUSH", "Press ENTER to start",
                         ["Arrows / A D  steer", "SPACE  nitro", "Dodge traffic, grab coins!"])
        elif self.state == "over":
            self.overlay(surf, "CRASH!", "Press ENTER to retry",
                         [f"Score  {self.score}", f"Best  {self.best}", f"Coins  {self.coins}"])
        elif self.paused:
            self.overlay(surf, "PAUSED", "Press P to resume", [])

    def text(self, surf, s, font, col, pos, center=False):
        sh = font.render(s, True, (0, 0, 0))
        im = font.render(s, True, col)
        r = im.get_rect(center=pos) if center else im.get_rect(topleft=pos)
        surf.blit(sh, r.move(2, 2))
        surf.blit(im, r)

    def draw_hud(self, surf):
        panel = pygame.Surface((200, 150), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0, 0, 0, 120), panel.get_rect(), border_radius=12)
        surf.blit(panel, (20, 20))
        self.text(surf, f"{int(self.speed * 12)}", F_MED, (255, 255, 255), (35, 28))
        self.text(surf, "km/h", F_SM, (200, 200, 200), (120, 38))
        self.text(surf, f"Score {self.score}", F_SM, (255, 240, 120), (35, 76))
        self.text(surf, f"Best  {self.best}", F_SM, (190, 190, 190), (35, 100))
        self.text(surf, "NITRO", F_SM, (120, 200, 255), (35, 126))
        pygame.draw.rect(surf, (30, 30, 40), (100, 130, 100, 14), border_radius=6)
        pygame.draw.rect(surf, (60, 170, 255) if not self.boosting else (255, 150, 40),
                         (100, 130, int(self.nitro), 14), border_radius=6)
        if self.muted:
            self.text(surf, "MUTED", F_SM, (255, 120, 120), (W - 90, 20))

    def overlay(self, surf, title, sub, lines):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surf.blit(dim, (0, 0))
        self.text(surf, title, F_BIG, (255, 170, 40), (W // 2, 210), True)
        for i, ln in enumerate(lines):
            self.text(surf, ln, F_MED, (240, 240, 240), (W // 2, 300 + i * 44), True)
        pulse = 200 + int(55 * math.sin(self.t * 0.1))
        self.text(surf, sub, F_MED, (pulse, pulse, 255), (W // 2, 520), True)


def main():
    pygame.display.flip()
    # Brief loading screen while audio is synthesized
    screen.fill((20, 22, 30))
    lbl = F_MED.render("Synthesizing music & sound effects...", True, (230, 230, 230))
    screen.blit(lbl, lbl.get_rect(center=(W // 2, H // 2)))
    pygame.display.flip()
    sounds = (make_music(), make_engine_loops(), make_sfx())
    game = Game(sounds)
    canvas = pygame.Surface((W, H))
    test_frames = int(os.environ.get("CARGAME_TEST", "0"))
    frame = 0

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.USEREVENT and game.state == "over":
                game.play("over", 0.6)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if ev.key == pygame.K_m:
                    game.toggle_mute()
                if ev.key == pygame.K_p and game.state == "play":
                    game.paused = not game.paused
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and game.state in ("menu", "over"):
                    game.start()

        keys = pygame.key.get_pressed()
        game.update(keys)
        game.draw(canvas)
        ox = oy = 0
        if game.shake:
            ox, oy = random.randint(-8, 8), random.randint(-8, 8)
        screen.fill((0, 0, 0))
        screen.blit(canvas, (ox, oy))
        pygame.display.flip()
        clock.tick(FPS)

        frame += 1
        if test_frames:
            if frame == 5:
                game.start()
            if frame >= test_frames:
                print("smoke test ok, score", game.score)
                return


if __name__ == "__main__":
    main()
