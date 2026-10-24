"""
TIC TAC TOE  -  a polished pygame version
-----------------------------------------
Features
  * 1-player (unbeatable minimax AI or easy AI) and 2-player modes
  * Animated marks, glowing win line, confetti, floating background
  * Chiptune background music + sound effects, all synthesized in code
    (no asset files needed)

Install:  pip install pygame
Run:      python tictactoe.py

Controls
  Mouse    - click to play / press buttons
  R        - restart round        M - toggle music
  S        - toggle sound effects ESC - back to menu / quit
"""
import array
import math
import random
import sys

import pygame

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------
SR = 44100
pygame.mixer.pre_init(SR, -16, 1, 512)
pygame.init()

W, H = 600, 780
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Tic Tac Toe")
clock = pygame.time.Clock()

BOARD, CELL = 480, 160
BL, BT = (W - BOARD) // 2, 200

X_COL = (255, 96, 128)
O_COL = (84, 220, 255)
WHITE = (245, 247, 255)
GOLD = (255, 214, 102)
BG_TOP, BG_BOT = (16, 18, 46), (58, 26, 90)


def font(size, bold=True):
    return pygame.font.SysFont("segoeui,helveticaneue,poppins,arial", size, bold=bold)


F_TITLE, F_BIG, F_MED, F_SMALL = font(64), font(38), font(26), font(18)

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6),
         (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


# --------------------------------------------------------------------------
# Audio synthesis
# --------------------------------------------------------------------------
class Silent:
    def play(self, *a, **k): pass
    def stop(self): pass
    def set_volume(self, v): pass


AUDIO_OK = False
CHANNELS = 1
try:
    pygame.mixer.init()
    init = pygame.mixer.get_init()
    if init:
        AUDIO_OK = True
        CHANNELS = init[2]
except pygame.error:
    pass


def synth(freq, dur, vol=0.5, wave="sine", freq2=None, attack=0.004, decay=None):
    """Return a list of float samples. freq2 makes a pitch sweep."""
    n = int(SR * dur)
    decay = decay if decay is not None else 4.0 / dur
    out, phase = [], 0.0
    for i in range(n):
        t = i / SR
        f = freq if freq2 is None else freq + (freq2 - freq) * (i / n)
        phase += 2 * math.pi * f / SR
        if wave == "sine":
            s = math.sin(phase)
        elif wave == "square":
            s = 0.6 if math.sin(phase) >= 0 else -0.6
        elif wave == "tri":
            s = 2 / math.pi * math.asin(math.sin(phase))
        elif wave == "noise":
            s = random.uniform(-1, 1)
        else:
            s = 0
        env = min(1.0, t / attack) * math.exp(-t * decay)
        out.append(s * env * vol)
    return out


def mix(buf, samples, start_sec):
    start = int(start_sec * SR)
    end = start + len(samples)
    if end > len(buf):
        buf.extend([0.0] * (end - len(buf)))
    for i, s in enumerate(samples):
        buf[start + i] += s


def to_sound(samples, volume=1.0):
    if not AUDIO_OK:
        return Silent()
    data = array.array("h")
    for s in samples:
        v = max(-32767, min(32767, int(s * 32767)))
        data.append(v)
        if CHANNELS == 2:
            data.append(v)
    snd = pygame.mixer.Sound(buffer=data.tobytes())
    snd.set_volume(volume)
    return snd


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def arpeggio(notes, step, wave="square", vol=0.35, dur=0.18):
    buf = []
    for i, m in enumerate(notes):
        mix(buf, synth(midi(m), dur, vol, wave), i * step)
    return buf


def build_sounds():
    s = {}
    s["x"] = to_sound(synth(520, 0.14, 0.55, "square", freq2=320, decay=22), 0.6)
    s["o"] = to_sound(synth(300, 0.18, 0.7, "sine", freq2=520, decay=16), 0.9)
    s["hover"] = to_sound(synth(880, 0.04, 0.25, "sine", decay=60), 0.35)
    s["click"] = to_sound(synth(660, 0.08, 0.5, "square", freq2=990, decay=30), 0.5)
    s["win"] = to_sound(arpeggio([72, 76, 79, 84, 79, 84, 88], 0.1, "square", 0.35, 0.3), 0.7)
    s["lose"] = to_sound(arpeggio([67, 64, 60, 55], 0.18, "tri", 0.6, 0.4), 0.8)
    s["draw"] = to_sound(arpeggio([64, 62, 60], 0.15, "tri", 0.6, 0.35), 0.7)
    s["start"] = to_sound(arpeggio([60, 67, 72], 0.07, "square", 0.35, 0.15), 0.6)
    return s


def build_music():
    """A looping chiptune: Am - F - C - G with arpeggios, bass and a lead."""
    bpm = 108
    beat = 60.0 / bpm
    bar = beat * 4
    chords = [  # bass, triad
        (45, (57, 60, 64)),
        (41, (53, 57, 60)),
        (48, (60, 64, 67)),
        (43, (55, 59, 62)),
    ]
    lead = [
        [(76, 1), (74, 1), (72, 2)],
        [(72, 1), (69, 1), (77, 2)],
        [(79, 1), (76, 1), (72, 2)],
        [(74, 2), (71, 1), (67, 1)],
    ]
    buf = []
    for b in range(8):
        bass, triad = chords[b % 4]
        t0 = b * bar
        # bass
        for k in (0, 2):
            mix(buf, synth(midi(bass), beat * 1.8, 0.45, "tri", decay=2.0), t0 + k * beat)
        # arpeggio (eighth notes)
        pattern = [0, 1, 2, 1, 0, 1, 2, 1]
        for i, p in enumerate(pattern):
            note = triad[p] + (12 if i % 4 == 2 else 0)
            mix(buf, synth(midi(note), beat * 0.6, 0.16, "square", decay=7), t0 + i * beat / 2)
        # lead on second half of the loop
        if b >= 4:
            tt = t0
            for note, beats in lead[b % 4]:
                mix(buf, synth(midi(note + 12 if b % 2 else note), beats * beat * 0.9,
                               0.22, "tri", decay=2.5), tt)
                tt += beats * beat
        # soft hi-hat
        for i in range(8):
            mix(buf, synth(0, 0.04, 0.05, "noise", decay=70), t0 + i * beat / 2)
    total = int(8 * bar * SR)
    buf = buf[:total] + [0.0] * max(0, total - len(buf))
    return to_sound(buf, 0.35)


# --------------------------------------------------------------------------
# Game logic
# --------------------------------------------------------------------------
def get_winner(b):
    for line in LINES:
        a, c, d = line
        if b[a] and b[a] == b[c] == b[d]:
            return b[a], line
    return None


def minimax(b, player, ai, depth, alpha, beta):
    w = get_winner(b)
    if w:
        return 10 - depth if w[0] == ai else depth - 10
    if all(b):
        return 0
    other = "O" if player == "X" else "X"
    if player == ai:
        best = -99
        for i in range(9):
            if not b[i]:
                b[i] = player
                best = max(best, minimax(b, other, ai, depth + 1, alpha, beta))
                b[i] = ""
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
        return best
    best = 99
    for i in range(9):
        if not b[i]:
            b[i] = player
            best = min(best, minimax(b, other, ai, depth + 1, alpha, beta))
            b[i] = ""
            beta = min(beta, best)
            if beta <= alpha:
                break
    return best


def ai_move(b, ai, hard):
    empty = [i for i in range(9) if not b[i]]
    if not hard and random.random() < 0.55:
        return random.choice(empty)
    best, moves = -99, []
    other = "O" if ai == "X" else "X"
    for i in empty:
        b[i] = ai
        score = minimax(b, other, ai, 1, -99, 99)
        b[i] = ""
        if score > best:
            best, moves = score, [i]
        elif score == best:
            moves.append(i)
    return random.choice(moves)


# --------------------------------------------------------------------------
# Visual helpers
# --------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t


def ease_out(t):
    return 1 - (1 - t) ** 3


def make_background():
    surf = pygame.Surface((W, H))
    for y in range(H):
        t = y / H
        c = tuple(int(lerp(BG_TOP[i], BG_BOT[i], t)) for i in range(3))
        pygame.draw.line(surf, c, (0, y), (W, y))
    return surf


BACKGROUND = make_background()


def text(surf, msg, f, color, center=None, topleft=None, shadow=True, alpha=255):
    img = f.render(msg, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    r = img.get_rect()
    if center:
        r.center = center
    if topleft:
        r.topleft = topleft
    if shadow:
        sh = f.render(msg, True, (0, 0, 0))
        sh.set_alpha(90 if alpha == 255 else alpha // 3)
        surf.blit(sh, r.move(2, 3))
    surf.blit(img, r)
    return r


def rounded(surf, rect, color, radius=18, alpha=255):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    surf.blit(s, rect.topleft)


def stroke(surf, p1, p2, color, width, progress=1.0, glow=True):
    """Draw a round-capped line from p1 toward p2."""
    end = (lerp(p1[0], p2[0], progress), lerp(p1[1], p2[1], progress))
    if glow:
        pygame.draw.line(surf, (*color, 45), p1, end, width + 16)
        pygame.draw.line(surf, (*color, 90), p1, end, width + 7)
    pygame.draw.line(surf, color, p1, end, width)
    for p in (p1, end):
        pygame.draw.circle(surf, color, (int(p[0]), int(p[1])), width // 2)


def draw_x(surf, center, size, progress, alpha=255, glow=True):
    layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    c = (CELL // 2, CELL // 2)
    s = size
    col = X_COL
    a1 = (c[0] - s, c[1] - s), (c[0] + s, c[1] + s)
    a2 = (c[0] + s, c[1] - s), (c[0] - s, c[1] + s)
    stroke(layer, *a1, col, 14, min(1, progress * 2), glow)
    if progress > 0.5:
        stroke(layer, *a2, col, 14, (progress - 0.5) * 2, glow)
    layer.set_alpha(alpha)
    surf.blit(layer, (center[0] - CELL // 2, center[1] - CELL // 2))


def draw_o(surf, center, radius, progress, alpha=255, glow=True):
    layer = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
    c = (CELL // 2, CELL // 2)
    steps = max(2, int(80 * progress))
    pts = []
    for i in range(steps + 1):
        ang = -math.pi / 2 + 2 * math.pi * progress * i / steps
        pts.append((c[0] + radius * math.cos(ang), c[1] + radius * math.sin(ang)))
    if len(pts) > 1:
        if glow:
            pygame.draw.lines(layer, (*O_COL, 45), False, pts, 30)
            pygame.draw.lines(layer, (*O_COL, 90), False, pts, 21)
        pygame.draw.lines(layer, O_COL, False, pts, 14)
        for p in (pts[0], pts[-1]):
            pygame.draw.circle(layer, O_COL, (int(p[0]), int(p[1])), 7)
        for p in pts[::2]:
            pygame.draw.circle(layer, O_COL, (int(p[0]), int(p[1])), 7)
    layer.set_alpha(alpha)
    surf.blit(layer, (center[0] - CELL // 2, center[1] - CELL // 2))


def cell_rect(i):
    return pygame.Rect(BL + (i % 3) * CELL, BT + (i // 3) * CELL, CELL, CELL)


def cell_at(pos):
    x, y = pos
    if BL <= x < BL + BOARD and BT <= y < BT + BOARD:
        return ((y - BT) // CELL) * 3 + (x - BL) // CELL
    return None


class Button:
    def __init__(self, rect, label, color):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.color = color
        self.h = 0.0

    def draw(self, surf, mouse, f=F_MED):
        hover = self.rect.collidepoint(mouse)
        self.h += ((1.0 if hover else 0.0) - self.h) * 0.25
        r = self.rect.inflate(int(10 * self.h), int(6 * self.h))
        rounded(surf, r.move(0, 5), (0, 0, 0), 20, 80)
        top = tuple(min(255, int(c + 40 * self.h)) for c in self.color)
        rounded(surf, r, top, 20)
        rounded(surf, pygame.Rect(r.x + 4, r.y + 3, r.w - 8, r.h // 2 - 3), (255, 255, 255), 16, 28)
        text(surf, self.label, f, WHITE, center=r.center)
        return hover

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class Particle:
    def __init__(self, x, y, color):
        ang = random.uniform(0, 2 * math.pi)
        spd = random.uniform(120, 520)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(ang) * spd, math.sin(ang) * spd - 200
        self.color = color
        self.life = random.uniform(1.0, 2.2)
        self.age = 0
        self.size = random.randint(5, 10)
        self.rot = random.uniform(0, 6.28)
        self.vr = random.uniform(-8, 8)

    def update(self, dt):
        self.age += dt
        self.vy += 700 * dt
        self.vx *= 0.99
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rot += self.vr * dt
        return self.age < self.life

    def draw(self, surf):
        a = max(0, 1 - self.age / self.life)
        s = self.size
        pts = [(self.x + math.cos(self.rot + k * math.pi / 2) * s,
                self.y + math.sin(self.rot + k * math.pi / 2) * s * 0.55) for k in range(4)]
        layer_col = (*self.color, int(255 * a))
        tmp = pygame.Surface((s * 4, s * 4), pygame.SRCALPHA)
        shifted = [(p[0] - self.x + s * 2, p[1] - self.y + s * 2) for p in pts]
        pygame.draw.polygon(tmp, layer_col, shifted)
        surf.blit(tmp, (self.x - s * 2, self.y - s * 2))


class Bubble:
    """Floating background decoration."""
    def __init__(self):
        self.reset(True)

    def reset(self, anywhere=False):
        self.x = random.uniform(0, W)
        self.y = random.uniform(0, H) if anywhere else H + 30
        self.r = random.uniform(6, 26)
        self.v = random.uniform(10, 38)
        self.drift = random.uniform(-10, 10)
        self.col = random.choice([X_COL, O_COL, (180, 140, 255)])
        self.a = random.randint(18, 48)

    def update(self, dt):
        self.y -= self.v * dt
        self.x += self.drift * dt
        if self.y < -40:
            self.reset()

    def draw(self, layer):
        pygame.draw.circle(layer, (*self.col, self.a), (int(self.x), int(self.y)), int(self.r))


# --------------------------------------------------------------------------
# Main game
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.state = "menu"           # menu | play
        self.mode = 1                 # 1 or 2 players
        self.hard = True
        self.music_on = True
        self.sfx_on = True
        self.scores = {"X": 0, "O": 0, "D": 0}
        self.bubbles = [Bubble() for _ in range(26)]
        self.particles = []
        self.overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        self.shake = 0.0
        self.hover_cell = None
        self.sounds = {}
        self.music = Silent()

        cx = W // 2
        self.btn_1p = Button((cx - 170, 330, 340, 70), "1 Player", (88, 86, 214))
        self.btn_2p = Button((cx - 170, 420, 340, 70), "2 Players", (214, 86, 150))
        self.btn_diff = Button((cx - 170, 510, 340, 56), "AI: Hard", (52, 140, 120))
        self.btn_quit = Button((cx - 170, 590, 340, 56), "Quit", (90, 90, 120))

        self.btn_menu = Button((BL, 705, 108, 48), "Menu", (90, 90, 150))
        self.btn_again = Button((BL + 120, 705, 140, 48), "Restart", (52, 140, 120))
        self.btn_music = Button((BL + 272, 705, 100, 48), "Music", (88, 86, 214))
        self.btn_sfx = Button((BL + 384, 705, 96, 48), "SFX", (214, 86, 150))

        self.starter = "X"
        self.new_round()

    # ---- audio ----
    def play(self, name):
        if self.sfx_on:
            self.sounds[name].play()

    def toggle_music(self):
        self.music_on = not self.music_on
        if self.music_on:
            self.music.play(loops=-1)
        else:
            self.music.stop()

    # ---- round management ----
    def new_round(self):
        self.board = [""] * 9
        self.spawn = [0.0] * 9
        self.turn = self.starter
        self.winner = None
        self.line = None
        self.over = False
        self.over_time = 0.0
        self.ai_timer = 0.0
        self.particles.clear()

    def start_game(self, mode):
        self.mode = mode
        self.scores = {"X": 0, "O": 0, "D": 0}
        self.starter = "X"
        self.new_round()
        self.state = "play"
        self.play("start")

    def is_ai_turn(self):
        return self.mode == 1 and self.turn == "O" and not self.over

    def place(self, i, now):
        if self.board[i] or self.over:
            return
        self.board[i] = self.turn
        self.spawn[i] = now
        self.play("x" if self.turn == "X" else "o")
        self.shake = 0.12
        res = get_winner(self.board)
        if res:
            self.winner, self.line = res
            self.finish(now)
        elif all(self.board):
            self.finish(now)
        else:
            self.turn = "O" if self.turn == "X" else "X"
            if self.is_ai_turn():
                self.ai_timer = 0.55

    def finish(self, now):
        self.over = True
        self.over_time = now
        if self.winner:
            self.scores[self.winner] += 1
            if self.mode == 1 and self.winner == "O":
                self.play("lose")
            else:
                self.play("win")
                col = X_COL if self.winner == "X" else O_COL
                a, b = cell_rect(self.line[0]).center, cell_rect(self.line[2]).center
                for _ in range(90):
                    t = random.random()
                    self.particles.append(Particle(lerp(a[0], b[0], t), lerp(a[1], b[1], t),
                                                   random.choice([col, GOLD, WHITE])))
        else:
            self.scores["D"] += 1
            self.play("draw")
        self.starter = "O" if self.starter == "X" else "X"

    # ---- events ----
    def handle_click(self, pos, now):
        if self.state == "menu":
            if self.btn_1p.hit(pos):
                self.play("click"); self.start_game(1)
            elif self.btn_2p.hit(pos):
                self.play("click"); self.start_game(2)
            elif self.btn_diff.hit(pos):
                self.play("click")
                self.hard = not self.hard
            elif self.btn_quit.hit(pos):
                pygame.quit(); sys.exit()
            return
        # play state
        if self.btn_menu.hit(pos):
            self.play("click"); self.state = "menu"; return
        if self.btn_again.hit(pos):
            self.play("click"); self.new_round_keep(); return
        if self.btn_music.hit(pos):
            self.play("click"); self.toggle_music(); return
        if self.btn_sfx.hit(pos):
            self.sfx_on = not self.sfx_on
            self.play("click"); return
        i = cell_at(pos)
        if self.over:
            if i is not None and now - self.over_time > 0.6:
                self.new_round_keep()
            return
        if i is not None and not self.is_ai_turn():
            self.place(i, now)

    def new_round_keep(self):
        if not self.over and any(self.board):
            self.starter = "X"  # manual restart mid-round
        self.new_round()
        if self.is_ai_turn():
            self.ai_timer = 0.6

    # ---- update ----
    def update(self, dt, now, mouse):
        for b in self.bubbles:
            b.update(dt)
        self.particles = [p for p in self.particles if p.update(dt)]
        self.shake = max(0, self.shake - dt)
        if self.state != "play":
            return
        if self.is_ai_turn():
            self.ai_timer -= dt
            if self.ai_timer <= 0:
                self.place(ai_move(self.board, "O", self.hard), now)
        # hover blip
        c = cell_at(mouse)
        if c is not None and (self.board[c] or self.over or self.is_ai_turn()):
            c = None
        if c != self.hover_cell and c is not None:
            self.play("hover")
        self.hover_cell = c

    # ---- drawing ----
    def draw_background(self, surf):
        surf.blit(BACKGROUND, (0, 0))
        self.overlay.fill((0, 0, 0, 0))
        for b in self.bubbles:
            b.draw(self.overlay)
        surf.blit(self.overlay, (0, 0))

    def draw_menu(self, surf, now, mouse):
        # animated decorative marks
        bob = math.sin(now * 2) * 8
        draw_x(surf, (130, 150 + bob), 40, 1.0)
        draw_o(surf, (W - 130, 150 - bob), 42, 1.0)
        pulse = 1 + 0.03 * math.sin(now * 3)
        title = pygame.transform.rotozoom(F_TITLE.render("TIC TAC", True, WHITE), 0, pulse)
        title2 = pygame.transform.rotozoom(F_TITLE.render("TOE", True, GOLD), 0, pulse)
        surf.blit(title, title.get_rect(center=(W // 2 + 2, 126)))
        surf.blit(title2, title2.get_rect(center=(W // 2 + 2, 200)))
        text(surf, "Get three in a row!", F_MED, (190, 195, 235), center=(W // 2, 262))
        self.btn_diff.label = "AI: Hard" if self.hard else "AI: Easy"
        for b in (self.btn_1p, self.btn_2p, self.btn_diff, self.btn_quit):
            b.draw(surf, mouse)
        text(surf, "M: music   S: sound   R: restart", F_SMALL, (150, 155, 200),
             center=(W // 2, 700), shadow=False)

    def draw_scoreboard(self, surf):
        panel = pygame.Rect(BL, 30, BOARD, 100)
        rounded(surf, panel, (255, 255, 255), 22, 24)
        names = {"X": "Player 1" if self.mode == 2 else "You",
                 "O": "Player 2" if self.mode == 2 else "AI"}
        cols = [(BL + 80, "X", X_COL), (BL + 240, "D", GOLD), (BL + 400, "O", O_COL)]
        for x, k, col in cols:
            active = (not self.over and self.turn == k)
            if active:
                glow = 70 + int(40 * math.sin(pygame.time.get_ticks() / 150))
                rounded(surf, pygame.Rect(x - 62, 38, 124, 84), col, 18, glow)
            label = "Draws" if k == "D" else names[k]
            text(surf, label, F_SMALL, WHITE, center=(x, 56), shadow=False)
            text(surf, str(self.scores[k]), F_BIG, col, center=(x, 94))

    def status_text(self):
        if self.over:
            if self.winner:
                if self.mode == 1:
                    return ("You win!", X_COL) if self.winner == "X" else ("AI wins!", O_COL)
                return (f"{self.winner} wins!", X_COL if self.winner == "X" else O_COL)
            return ("It's a draw!", GOLD)
        if self.is_ai_turn():
            dots = "." * (1 + int(pygame.time.get_ticks() / 300) % 3)
            return ("AI is thinking" + dots, O_COL)
        if self.mode == 1:
            return ("Your turn", X_COL)
        return (f"{self.turn}'s turn", X_COL if self.turn == "X" else O_COL)

    def draw_board(self, surf, now):
        ox = oy = 0
        if self.shake > 0:
            ox = random.randint(-3, 3)
            oy = random.randint(-3, 3)
        board_surf = pygame.Surface((BOARD + 40, BOARD + 40), pygame.SRCALPHA)
        panel = pygame.Rect(0, 0, BOARD + 40, BOARD + 40)
        rounded(board_surf, panel, (255, 255, 255), 30, 20)
        # grid lines
        gcol = (150, 160, 230)
        for k in (1, 2):
            pygame.draw.line(board_surf, gcol, (20 + k * CELL, 40), (20 + k * CELL, BOARD), 6)
            pygame.draw.line(board_surf, gcol, (40, 20 + k * CELL), (BOARD, 20 + k * CELL), 6)
            for p in ((20 + k * CELL, 40), (20 + k * CELL, BOARD), (40, 20 + k * CELL), (BOARD, 20 + k * CELL)):
                pygame.draw.circle(board_surf, gcol, p, 3)
        surf.blit(board_surf, (BL - 20 + ox, BT - 20 + oy))

        # hover ghost
        if self.hover_cell is not None and not self.over:
            r = cell_rect(self.hover_cell)
            rounded(surf, r.inflate(-16, -16).move(ox, oy), (255, 255, 255), 16, 22)
            if self.turn == "X":
                draw_x(surf, (r.centerx + ox, r.centery + oy), 36, 1.0, 70, False)
            else:
                draw_o(surf, (r.centerx + ox, r.centery + oy), 38, 1.0, 70, False)

        # marks
        for i, m in enumerate(self.board):
            if not m:
                continue
            r = cell_rect(i)
            p = ease_out(min(1.0, (now - self.spawn[i]) / 0.35))
            dim = 255
            if self.over and self.line and i not in self.line:
                dim = 110
            c = (r.centerx + ox, r.centery + oy)
            if m == "X":
                draw_x(surf, c, 38, p, dim)
            else:
                draw_o(surf, c, 40, p, dim)

        # win line
        if self.over and self.line:
            prog = ease_out(min(1.0, (now - self.over_time) / 0.5))
            a = cell_rect(self.line[0]).center
            b = cell_rect(self.line[2]).center
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy)
            ext = 52 / ln
            a = (a[0] - dx * ext, a[1] - dy * ext)
            b = (b[0] + dx * ext, b[1] + dy * ext)
            layer = pygame.Surface((W, H), pygame.SRCALPHA)
            stroke(layer, a, b, WHITE, 10, prog)
            surf.blit(layer, (ox, oy))

    def draw_play(self, surf, now, mouse):
        self.draw_scoreboard(surf)
        msg, col = self.status_text()
        bounce = 0
        if self.over:
            bounce = math.sin((pygame.time.get_ticks() / 1000) * 5) * 3
        text(surf, msg, F_BIG, col, center=(W // 2, 162 + bounce))
        self.draw_board(surf, now)
        for p in self.particles:
            p.draw(surf)
        if self.over and now - self.over_time > 0.6:
            alpha = 150 + int(90 * math.sin(pygame.time.get_ticks() / 250))
            text(surf, "Click the board to play again", F_SMALL, WHITE,
                 center=(W // 2, BT + BOARD + 38), alpha=alpha)
        self.btn_music.color = (88, 86, 214) if self.music_on else (80, 80, 100)
        self.btn_sfx.color = (214, 86, 150) if self.sfx_on else (80, 80, 100)
        for b in (self.btn_menu, self.btn_again, self.btn_music, self.btn_sfx):
            b.draw(surf, mouse, F_SMALL)


def main():
    game = Game()

    # loading screen while audio is synthesized
    screen.blit(BACKGROUND, (0, 0))
    text(screen, "TIC TAC TOE", F_TITLE, WHITE, center=(W // 2, H // 2 - 40))
    text(screen, "Composing music...", F_MED, (190, 195, 235), center=(W // 2, H // 2 + 30))
    pygame.display.flip()
    pygame.event.pump()

    game.sounds = build_sounds()
    game.music = build_music()
    if game.music_on:
        game.music.play(loops=-1)

    while True:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        now = pygame.time.get_ticks() / 1000.0
        mouse = pygame.mouse.get_pos()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                game.handle_click(e.pos, now)
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if game.state == "play":
                        game.state = "menu"
                    else:
                        pygame.quit()
                        sys.exit()
                elif e.key == pygame.K_m:
                    game.toggle_music()
                elif e.key == pygame.K_s:
                    game.sfx_on = not game.sfx_on
                elif e.key == pygame.K_r and game.state == "play":
                    game.new_round_keep()

        game.update(dt, now, mouse)
        game.draw_background(screen)
        if game.state == "menu":
            game.draw_menu(screen, now, mouse)
        else:
            game.draw_play(screen, now, mouse)
        pygame.display.flip()


if __name__ == "__main__":
    main()