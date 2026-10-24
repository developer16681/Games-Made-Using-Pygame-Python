"""Sweet Crush - a match-3 candy game in Python (pygame).
Install:  pip install pygame
Run:      python sweet_crush.py
All graphics are drawn in code and all music/sound effects are synthesized (no asset files).
Controls: drag a candy (or click two neighbours) to swap. M = mute, Esc = quit.
"""
import math, random, sys, array
import pygame

N, CELL, BX, BY = 8, 64, 24, 150
W, H = N * CELL + 48, BY + N * CELL + 60
COLS = [(255, 59, 92), (255, 154, 31), (255, 217, 46), (61, 220, 95), (46, 155, 255), (180, 77, 255)]
RATE = 44100
PENT = [523, 587, 659, 784, 880, 1047, 1175, 1319, 1568]


# ---------------------------------------------------------------- audio synthesis
def synth(f, d, wave="sine", v=0.3, f2=None):
    n, out, ph = int(RATE * d), [], 0.0
    for i in range(n):
        k = i / n
        ph += (f if f2 is None else f + (f2 - f) * k) / RATE
        p = ph % 1
        s = math.sin(math.tau * p) if wave == "sine" else (4 * abs(p - .5) - 1 if wave == "tri" else 2 * p - 1)
        out.append(s * min(1, i / (RATE * .01)) * math.exp(-4 * k) * v)
    return out


def mix(parts, wrap=None):
    total = wrap or max(int(o * RATE) + len(s) for o, s in parts)
    out = [0.0] * total
    for o, s in parts:
        st = int(o * RATE)
        for j, x in enumerate(s):
            out[(st + j) % total] += x
    return out


def to_sound(samples):
    a = array.array("h", [int(max(-1, min(1, x)) * 32767) for x in samples])
    return pygame.mixer.Sound(buffer=a.tobytes())


def build_sounds():
    s = {}
    for i, f in enumerate(PENT):
        s["pop%d" % i] = to_sound(mix([(0, synth(f, .25, "sine", .35)), (.03, synth(f * 2, .15, "tri", .15))]))
    s["sel"] = to_sound(synth(900, .07, "tri", .25))
    s["swap"] = to_sound(synth(400, .12, "sine", .3, 700))
    s["bad"] = to_sound(synth(160, .25, "saw", .2, 100))
    s["special"] = to_sound(mix([(0, synth(300, .5, "saw", .15, 1800)), (0, synth(600, .5, "sine", .25, 2400))]))
    s["fall"] = to_sound(synth(250, .08, "sine", .12))
    s["win"] = to_sound(mix([(i * .12, synth(f, .4, "tri", .35)) for i, f in enumerate([523, 659, 784, 1047, 1319])]))
    s["lose"] = to_sound(mix([(i * .2, synth(f, .4, "tri", .3)) for i, f in enumerate([392, 349, 330, 262])]))
    return s


def build_music():
    ch = [(261, 329, 392), (220, 261, 329), (174, 220, 261), (196, 246, 293)]
    pat, mel, step = [0, 1, 2, 1, 2, 1, 0, 1], [2, 0, 1, 2, 1, 0, 2, 1], .23
    parts = []
    for st in range(32):
        c, i, t = ch[(st >> 3) & 3], st & 7, st * step
        parts.append((t, synth(c[pat[i]] * 2, .3, "tri", .12)))
        if i in (0, 4):
            parts.append((t, synth(c[0] / 2, .45, "sine", .3)))
        if i % 2 == 0 and (st >> 3) & 1:
            parts.append((t, synth(c[mel[i]] * 4, .25, "sine", .08)))
    return to_sound(mix(parts, wrap=int(32 * step * RATE)))


# ---------------------------------------------------------------- candy sprites
def shape_pts(t, r, cx, cy):
    if t == 0:
        return [(cx + r * math.cos(a * math.tau / 40), cy + r * math.sin(a * math.tau / 40)) for a in range(40)]
    if t == 1:
        pts = []
        for a in range(48):
            th = a * math.tau / 48
            c, s = math.cos(th), math.sin(th)
            pts.append((cx + r * math.copysign(abs(c) ** .35, c), cy + r * math.copysign(abs(s) ** .35, s)))
        return pts
    if t == 2:
        return [(cx + math.cos(-math.pi / 2 + i * math.pi / 5) * (r * 1.12 if i % 2 == 0 else r * .55),
                 cy + math.sin(-math.pi / 2 + i * math.pi / 5) * (r * 1.12 if i % 2 == 0 else r * .55)) for i in range(10)]
    if t == 3:
        pts = [(cx, cy - r * 1.15)]
        for a in range(-60, 241, 8):
            th = math.radians(a)
            pts.append((cx + .85 * r * math.cos(th), cy + .2 * r + .85 * r * math.sin(th)))
        return pts
    if t == 4:
        return [(cx + math.cos(i * math.pi / 3 + math.pi / 6) * r * 1.08, cy + math.sin(i * math.pi / 3 + math.pi / 6) * r * 1.08) for i in range(6)]
    return [(cx, cy - r * 1.1), (cx + r * 1.05, cy), (cx, cy + r * 1.1), (cx - r * 1.05, cy)]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_sprite(t, sp):
    Z = CELL * 2
    surf = pygame.Surface((Z, Z), pygame.SRCALPHA)
    cx = cy = Z / 2
    r = Z * .36
    base = COLS[t]
    dark = tuple(int(c * .55) for c in base)
    pygame.draw.polygon(surf, (0, 0, 0, 70), shape_pts(t, r, cx + 4, cy + 9))
    pts = shape_pts(t, r, cx, cy)
    pygame.draw.polygon(surf, dark, pts)
    for k in range(1, 13):
        f = k / 12
        col = lerp(dark, base, min(1, f * 1.6))
        if f > .6:
            col = lerp(base, (255, 255, 255), (f - .6) / .4 * .85)
        pygame.draw.polygon(surf, col, shape_pts(t, r * (1 - f * .75), cx - f * r * .3, cy - f * r * .35))
    if sp in (1, 2):
        layer = pygame.Surface((Z, Z), pygame.SRCALPHA)
        for i in (-2, 0, 2):
            if sp == 1:
                pygame.draw.rect(layer, (255, 255, 255, 215), (cx - r * 1.3, cy + i * r * .28 - r * .1, r * 2.6, r * .24))
            else:
                pygame.draw.rect(layer, (255, 255, 255, 215), (cx + i * r * .28 - r * .1, cy - r * 1.3, r * .24, r * 2.6))
        mask = pygame.Surface((Z, Z), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), pts)
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(layer, (0, 0))
    if sp == 3:
        for a in range(0, 360, 30):
            pygame.draw.circle(surf, (255, 255, 255), (cx + r * 1.2 * math.cos(math.radians(a)), cy + r * 1.2 * math.sin(math.radians(a))), 6)
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), r * .4)
    pygame.draw.polygon(surf, dark, pts, 4)
    hl = pygame.Surface((Z, Z), pygame.SRCALPHA)
    pygame.draw.ellipse(hl, (255, 255, 255, 170), (cx - r * .75, cy - r * .8, r * .55, r * .3))
    surf.blit(hl, (0, 0))
    return pygame.transform.smoothscale(surf, (CELL, CELL))


class Candy:
    def __init__(self, r, c, t=None):
        self.t = random.randrange(6) if t is None else t
        self.sp, self.x, self.y, self.s, self.dead, self.rot = 0, c * CELL, r * CELL, 1.0, False, 0.0


# ---------------------------------------------------------------- game
class Game:
    def __init__(self, screen, snd, music_ch):
        self.screen, self.snd, self.music_ch = screen, snd, music_ch
        self.muted, self.level, self.score, self.moves, self.target = False, 1, 0, 0, 1
        self.sel = self.drag = self.task = None
        self.parts, self.texts, self.T = [], [], 0
        self.sprites = {(t, sp): make_sprite(t, sp) for t in range(6) for sp in range(4)}
        self.f_big = pygame.font.SysFont("trebuchetms,arial,dejavusans", 56, bold=True)
        self.f_title = pygame.font.SysFont("trebuchetms,arial,dejavusans", 40, bold=True)
        self.f_mid = pygame.font.SysFont("trebuchetms,arial,dejavusans", 24, bold=True)
        self.f_sm = pygame.font.SysFont("trebuchetms,arial,dejavusans", 15, bold=True)
        self.bg = pygame.Surface((W, H))
        for y in range(H):
            pygame.draw.line(self.bg, lerp((255, 138, 216), (123, 63, 228), y / H), (0, y), (W, y))
        self.panel = pygame.Surface((N * CELL + 16, N * CELL + 16), pygame.SRCALPHA)
        pygame.draw.rect(self.panel, (58, 26, 122, 170), self.panel.get_rect(), border_radius=20)
        pygame.draw.rect(self.panel, (255, 255, 255, 140), self.panel.get_rect(), 3, border_radius=20)
        self.state = "menu"
        self.ov = ("Sweet Crush", "Match 3+ candies. Match 4 = striped, 5 = bomb!", "Play", "start")
        self.fill()

    # ---- helpers
    def play(self, k):
        if not self.muted:
            self.snd[k].play()

    def say(self, t):
        self.texts.append(dict(t=t, x=N * CELL / 2, y=N * CELL / 2, l=1.0, big=True))

    def burst(self, x, y, col, n=8):
        for _ in range(n):
            a, v = random.random() * math.tau, 2 + random.random() * 4
            self.parts.append(dict(x=x, y=y, vx=math.cos(a) * v, vy=math.sin(a) * v - 2, l=1.0, c=col, r=3 + random.random() * 4))

    def ok(self, r, c):
        return 0 <= r < N and 0 <= c < N and self.g[r][c] is not None and not self.g[r][c].dead

    def same(self, a, b, c, d):
        return self.ok(a, b) and self.ok(c, d) and self.g[a][b].t == self.g[c][d].t

    def runs(self):
        res = []
        for r in range(N):
            c = 0
            while c < N:
                k = c
                while k + 1 < N and self.same(r, c, r, k + 1):
                    k += 1
                if self.ok(r, c) and k - c >= 2:
                    res.append((True, [(r, i) for i in range(c, k + 1)]))
                c = k + 1
        for c in range(N):
            r = 0
            while r < N:
                k = r
                while k + 1 < N and self.same(r, c, k + 1, c):
                    k += 1
                if self.ok(r, c) and k - r >= 2:
                    res.append((False, [(i, c) for i in range(r, k + 1)]))
                r = k + 1
        return res

    def swap(self, a, b):
        self.g[a[0]][a[1]], self.g[b[0]][b[1]] = self.g[b[0]][b[1]], self.g[a[0]][a[1]]

    def has_move(self):
        for r in range(N):
            for c in range(N):
                for dr, dc in ((0, 1), (1, 0)):
                    r2, c2 = r + dr, c + dc
                    if r2 >= N or c2 >= N:
                        continue
                    self.swap((r, c), (r2, c2))
                    f = bool(self.runs())
                    self.swap((r, c), (r2, c2))
                    if f:
                        return True
        return False

    def fill(self):
        while True:
            self.g = [[None] * N for _ in range(N)]
            for r in range(N):
                for c in range(N):
                    while True:
                        t = random.randrange(6)
                        if (c > 1 and self.g[r][c - 1].t == t and self.g[r][c - 2].t == t) or \
                           (r > 1 and self.g[r - 1][c].t == t and self.g[r - 2][c].t == t):
                            continue
                        break
                    self.g[r][c] = Candy(r, c, t)
            if self.has_move():
                return

    def start(self):
        self.score, self.target, self.moves = 0, 1500 + self.level * 1000, 22 + min(self.level, 8)
        self.fill()
        for row in self.g:
            for d in row:
                d.y = -N * CELL - d.y
        self.parts, self.texts, self.sel, self.drag, self.task = [], [], None, None, None
        self.state = "play"

    @staticmethod
    def wait(n):
        for _ in range(n):
            yield

    # ---- game flow (generators advance one step per frame)
    def resolve(self, sw):
        combo = 0
        while True:
            rs = self.runs()
            if not rs:
                break
            combo += 1
            clear, sps = set(), []
            for h, cells in rs:
                clear.update(r * N + c for r, c in cells)
                n = len(cells)
                if n >= 4:
                    m = next((x for x in cells if sw and x in sw), cells[n // 2])
                    sps.append((m[0], m[1], 3 if n >= 5 else (2 if h else 1)))
            q, had = list(clear), False
            while q:
                r, c = divmod(q.pop(), N)
                d = self.g[r][c]
                if not d:
                    continue
                add = []
                if d.sp == 1:
                    add = [r * N + i for i in range(N)]
                elif d.sp == 2:
                    add = [i * N + c for i in range(N)]
                elif d.sp == 3:
                    add = [(r + a) * N + c + b for a in (-1, 0, 1) for b in (-1, 0, 1) if self.ok(r + a, c + b)]
                had = had or bool(d.sp)
                for a in add:
                    if a not in clear:
                        clear.add(a)
                        q.append(a)
            for r, c, s in sps:
                clear.discard(r * N + c)
            pts = len(clear) * 60 * combo
            self.score += pts
            self.play("pop%d" % min(combo - 1, 8))
            if had or sps:
                self.play("special")
            for k in clear:
                d = self.g[k // N][k % N]
                if d:
                    d.dead = True
                    self.burst(k % N * CELL + CELL / 2, k // N * CELL + CELL / 2, COLS[d.t])
            for r, c, s in sps:
                self.g[r][c].sp, self.g[r][c].s = s, 1.4
                self.burst(c * CELL + CELL / 2, r * CELL + CELL / 2, (255, 255, 255), 14)
            fr, fc = rs[0][1][0]
            self.texts.append(dict(t="+%d" % pts, x=fc * CELL + CELL / 2, y=fr * CELL + CELL / 2, l=1.0, big=False))
            if combo >= 2:
                self.say(["Sweet!", "Tasty!", "Delicious!", "Divine!"][min(combo, 5) - 2])
            yield from self.wait(16)
            for k in clear:
                self.g[k // N][k % N] = None
            for c in range(N):
                w = N - 1
                for r in range(N - 1, -1, -1):
                    if self.g[r][c]:
                        self.g[w][c] = self.g[r][c]
                        if w != r:
                            self.g[r][c] = None
                        w -= 1
                for r in range(w, -1, -1):
                    d = Candy(r, c)
                    d.y = -(w - r + 1) * CELL
                    self.g[r][c] = d
            self.play("fall")
            yield from self.wait(23)
            sw = None

    def do_swap(self, a, b):
        self.play("swap")
        self.swap(a, b)
        yield from self.wait(12)
        if not self.runs():
            self.play("bad")
            self.swap(a, b)
            yield from self.wait(13)
            return
        self.moves -= 1
        yield from self.resolve([a, b])
        if self.score >= self.target:
            self.play("win")
            self.state, self.ov = "over", ("Level %d Complete!" % self.level, "Score: %d" % self.score, "Next Level", "next")
        elif self.moves <= 0:
            self.play("lose")
            self.state, self.ov = "over", ("Out of moves", "You scored %d (goal %d)" % (self.score, self.target), "Try Again", "retry")
        elif not self.has_move():
            self.say("Shuffle!")
            self.fill()

    # ---- input
    def btn_rect(self):
        return pygame.Rect(0, 0, 200, 56).move(W / 2 - 100, BY + N * CELL / 2 + 40)

    def cell_at(self, pos):
        c, r = (pos[0] - BX) // CELL, (pos[1] - BY) // CELL
        return (r, c) if 0 <= r < N and 0 <= c < N else None

    def click(self, pos):
        if self.state != "play":
            if self.btn_rect().collidepoint(pos):
                if self.ov[3] == "next":
                    self.level += 1
                self.start()
            return
        if self.task:
            return
        p = self.cell_at(pos)
        if not p:
            return
        if self.sel and abs(self.sel[0] - p[0]) + abs(self.sel[1] - p[1]) == 1:
            a, self.sel, self.drag = self.sel, None, None
            self.task = self.do_swap(a, p)
            return
        self.sel, self.drag = p, (pos, p)
        self.play("sel")

    def motion(self, pos):
        if not self.drag or self.task or self.state != "play":
            return
        (x0, y0), p = self.drag
        dx, dy = pos[0] - x0, pos[1] - y0
        if max(abs(dx), abs(dy)) < 24:
            return
        q = (p[0], p[1] + (1 if dx > 0 else -1)) if abs(dx) > abs(dy) else (p[0] + (1 if dy > 0 else -1), p[1])
        self.drag = self.sel = None
        if 0 <= q[0] < N and 0 <= q[1] < N:
            self.task = self.do_swap(p, q)

    def toggle_mute(self):
        self.muted = not self.muted
        (self.music_ch.pause if self.muted else self.music_ch.unpause)()

    # ---- drawing
    def txt(self, s, font, x, y, alpha=255, o=2, col=(255, 255, 255)):
        base, out = font.render(s, True, col), font.render(s, True, (179, 35, 154))
        w, h = base.get_size()
        surf = pygame.Surface((w + 2 * o, h + 2 * o), pygame.SRCALPHA)
        for dx, dy in ((-o, 0), (o, 0), (0, -o), (0, o), (-o, -o), (o, o), (-o, o), (o, -o)):
            surf.blit(out, (o + dx, o + dy))
        surf.blit(base, (o, o))
        surf.set_alpha(alpha)
        self.screen.blit(surf, surf.get_rect(center=(x, y)))

    def draw(self):
        self.T += 1
        s = self.screen
        s.blit(self.bg, (0, 0))
        self.txt("Sweet Crush", self.f_title, W / 2, 32, o=3)
        bw = (W - 48 - 20) // 3
        for i, (lab, val) in enumerate((("LEVEL", self.level), ("SCORE", self.score), ("MOVES", self.moves))):
            rc = pygame.Rect(24 + i * (bw + 10), 62, bw, 52)
            pygame.draw.rect(s, (110, 50, 170), rc, border_radius=14)
            pygame.draw.rect(s, (255, 200, 245), rc, 2, border_radius=14)
            l = self.f_sm.render(lab, True, (255, 220, 250))
            s.blit(l, l.get_rect(center=(rc.centerx, rc.y + 12)))
            v = self.f_mid.render(str(val), True, (255, 255, 255))
            s.blit(v, v.get_rect(center=(rc.centerx, rc.y + 34)))
        bar = pygame.Rect(24, 124, W - 48, 12)
        pygame.draw.rect(s, (90, 40, 150), bar, border_radius=6)
        fw = int(bar.w * min(1, self.score / self.target))
        if fw > 0:
            pygame.draw.rect(s, (255, 190, 40), (bar.x, bar.y, fw, bar.h), border_radius=6)
        s.blit(self.panel, (BX - 8, BY - 8))
        s.set_clip(pygame.Rect(BX, BY, N * CELL, N * CELL))
        for r in range(N):
            for c in range(N):
                if (r + c) % 2 == 0:
                    pygame.draw.rect(s, (110, 70, 175), (BX + c * CELL, BY + r * CELL, CELL, CELL))
        for r in range(N):
            for c in range(N):
                d = self.g[r][c]
                if not d:
                    continue
                d.x += (c * CELL - d.x) * .35
                dy = r * CELL - d.y
                d.y += dy if abs(dy) < .5 else math.copysign(max(abs(dy) * .22, 5), dy)
                if d.dead:
                    d.s *= .82
                    d.rot += .25
                elif d.s > 1:
                    d.s = max(1, d.s - .02)
                pulse = 1.1 + math.sin(self.T * .3) * .06 if self.sel == (r, c) else 1
                spr = self.sprites[(d.t, d.sp)]
                sc = d.s * pulse
                if sc != 1 or d.rot:
                    spr = pygame.transform.rotozoom(spr, -math.degrees(d.rot), max(.01, sc))
                if d.dead:
                    spr.set_alpha(int(255 * min(1, d.s)))
                s.blit(spr, spr.get_rect(center=(BX + d.x + CELL / 2, BY + d.y + CELL / 2)))
        if self.sel and not self.task:
            pygame.draw.rect(s, (255, 255, 255), (BX + self.sel[1] * CELL + 3, BY + self.sel[0] * CELL + 3, CELL - 6, CELL - 6), 3, border_radius=8)
        self.parts = [p for p in self.parts if p["l"] > 0]
        for p in self.parts:
            p["x"] += p["vx"]; p["y"] += p["vy"]; p["vy"] += .3; p["l"] -= .03
            pygame.draw.circle(s, p["c"], (BX + p["x"], BY + p["y"]), max(1, p["r"] * p["l"]))
        self.texts = [t for t in self.texts if t["l"] > 0]
        for t in self.texts:
            t["y"] -= .6 if t["big"] else 1
            t["l"] -= .012 if t["big"] else .02
            self.txt(t["t"], self.f_big if t["big"] else self.f_mid, BX + t["x"], BY + t["y"], alpha=int(255 * max(0, min(1, t["l"]))), o=3)
        s.set_clip(None)
        if self.state != "play":
            ov = pygame.Surface((N * CELL, N * CELL), pygame.SRCALPHA)
            pygame.draw.rect(ov, (42, 15, 106, 215), ov.get_rect(), border_radius=14)
            s.blit(ov, (BX, BY))
            h, m, b, _ = self.ov
            self.txt(h, self.f_title, W / 2, BY + N * CELL / 2 - 60, o=3)
            self.txt(m, self.f_sm, W / 2, BY + N * CELL / 2 - 10)
            rc = self.btn_rect()
            pygame.draw.rect(s, (143, 22, 112), rc.move(0, 5), border_radius=28)
            pygame.draw.rect(s, (224, 40, 159), rc, border_radius=28)
            pygame.draw.rect(s, (255, 255, 255), rc, 3, border_radius=28)
            self.txt(b, self.f_mid, rc.centerx, rc.centery, o=1)
        hint = self.f_sm.render("Drag or click to swap  |  M: sound " + ("off" if self.muted else "on"), True, (255, 230, 250))
        s.blit(hint, hint.get_rect(center=(W / 2, H - 22)))


def main():
    pygame.mixer.pre_init(RATE, -16, 1, 512)
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Sweet Crush")
    f = pygame.font.SysFont("arial", 28, bold=True)
    screen.fill((123, 63, 228))
    t = f.render("Baking candies and sounds...", True, (255, 255, 255))
    screen.blit(t, t.get_rect(center=(W / 2, H / 2)))
    pygame.display.flip()
    snd, music = build_sounds(), build_music()
    music.set_volume(.35)
    game = Game(screen, snd, music.play(-1))
    clock = pygame.time.Clock()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                game.toggle_mute()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                game.click(e.pos)
            if e.type == pygame.MOUSEMOTION and e.buttons[0]:
                game.motion(e.pos)
            if e.type == pygame.MOUSEBUTTONUP:
                game.drag = None
        if game.task:
            try:
                next(game.task)
            except StopIteration:
                game.task = None
        game.draw()
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
