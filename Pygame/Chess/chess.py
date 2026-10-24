#!/usr/bin/env python3
"""Chess with an AI opponent, procedural graphics, synthesized music & sound effects.
Requires: pip install pygame     Run: python chess.py
Keys: N new | U undo | F flip | P vs AI/2-player | C swap side | 1/2/3 level | M music | S sfx
"""
import math, random, threading, time, array
import pygame

# ───────────────────────── Chess engine ─────────────────────────
N_D = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
K_D = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
B_D = [(-1,-1),(-1,1),(1,-1),(1,1)]
R_D = [(-1,0),(1,0),(0,-1),(0,1)]
RIGHTS = {60:'KQ', 63:'K', 56:'Q', 4:'kq', 7:'k', 0:'q'}
VAL = {'P':100,'N':320,'B':330,'R':500,'Q':900,'K':0}
FILES = 'abcdefgh'

class Pos:
    __slots__ = ('b','turn','castle','ep')
    def __init__(s, b, turn, castle, ep): s.b, s.turn, s.castle, s.ep = b, turn, castle, ep

def start_pos():
    back = 'RNBQKBNR'
    b = ['b'+p for p in back] + ['bP']*8 + ['']*32 + ['wP']*8 + ['w'+p for p in back]
    return Pos(b, 'w', 'KQkq', None)

def attacked(b, sq, by):
    r, c = divmod(sq, 8)
    pr = r+1 if by == 'w' else r-1
    for dc in (-1, 1):
        if 0 <= pr < 8 and 0 <= c+dc < 8 and b[pr*8+c+dc] == by+'P': return True
    for dr, dc in N_D:
        rr, cc = r+dr, c+dc
        if 0 <= rr < 8 and 0 <= cc < 8 and b[rr*8+cc] == by+'N': return True
    for dr, dc in K_D:
        rr, cc = r+dr, c+dc
        if 0 <= rr < 8 and 0 <= cc < 8 and b[rr*8+cc] == by+'K': return True
    for dirs, kinds in ((B_D, 'BQ'), (R_D, 'RQ')):
        for dr, dc in dirs:
            rr, cc = r+dr, c+dc
            while 0 <= rr < 8 and 0 <= cc < 8:
                p = b[rr*8+cc]
                if p:
                    if p[0] == by and p[1] in kinds: return True
                    break
                rr += dr; cc += dc
    return False

def pseudo(pos):
    b, us = pos.b, pos.turn
    them = 'b' if us == 'w' else 'w'
    out = []
    for f, p in enumerate(b):
        if not p or p[0] != us: continue
        k = p[1]; r, c = divmod(f, 8)
        if k == 'P':
            d = -1 if us == 'w' else 1; last = 0 if us == 'w' else 7; rr = r+d
            def add(t, f=f):
                if t//8 == last: out.extend((f, t, q) for q in 'QRBN')
                else: out.append((f, t, ''))
            if not b[rr*8+c]:
                add(rr*8+c)
                if r == (6 if us == 'w' else 1) and not b[(r+2*d)*8+c]: out.append((f, (r+2*d)*8+c, ''))
            for dc in (-1, 1):
                cc = c+dc
                if 0 <= cc < 8:
                    t = rr*8+cc
                    if (b[t] and b[t][0] == them) or t == pos.ep: add(t)
        elif k in 'NK':
            for dr, dc in (N_D if k == 'N' else K_D):
                rr, cc = r+dr, c+dc
                if 0 <= rr < 8 and 0 <= cc < 8:
                    t = rr*8+cc
                    if not b[t] or b[t][0] == them: out.append((f, t, ''))
            if k == 'K' and f == (60 if us == 'w' else 4) and not attacked(b, f, them):
                ks, qs = ('K', 'Q') if us == 'w' else ('k', 'q')
                if ks in pos.castle and not b[f+1] and not b[f+2] and not attacked(b, f+1, them) and not attacked(b, f+2, them):
                    out.append((f, f+2, ''))
                if qs in pos.castle and not b[f-1] and not b[f-2] and not b[f-3] and not attacked(b, f-1, them) and not attacked(b, f-2, them):
                    out.append((f, f-2, ''))
        else:
            for dr, dc in (B_D if k == 'B' else R_D if k == 'R' else B_D+R_D):
                rr, cc = r+dr, c+dc
                while 0 <= rr < 8 and 0 <= cc < 8:
                    t = rr*8+cc
                    if b[t]:
                        if b[t][0] == them: out.append((f, t, ''))
                        break
                    out.append((f, t, '')); rr += dr; cc += dc
    return out

def make(pos, m):
    f, t, pr = m; b = pos.b[:]; p = b[f]; us = p[0]; ep = None; cast = pos.castle
    if p[1] == 'P':
        if f % 8 != t % 8 and not b[t]: b[(f//8)*8 + t%8] = ''
        if abs(t-f) == 16: ep = (f+t)//2
    if p[1] == 'K' and abs(t-f) == 2:
        if t > f: b[f+1] = b[f+3]; b[f+3] = ''
        else: b[f-1] = b[f-4]; b[f-4] = ''
    b[t] = us+pr if pr else p; b[f] = ''
    for s in (f, t):
        rm = RIGHTS.get(s)
        if rm: cast = ''.join(ch for ch in cast if ch not in rm)
    return Pos(b, 'b' if us == 'w' else 'w', cast, ep)

def opp(c): return 'b' if c == 'w' else 'w'
def in_check(pos): return attacked(pos.b, pos.b.index(pos.turn+'K'), opp(pos.turn))
def legal(pos):
    us, them = pos.turn, opp(pos.turn)
    return [m for m in pseudo(pos) if not attacked((n := make(pos, m)).b, n.b.index(us+'K'), them)]

def sq_name(s): return FILES[s % 8] + str(8 - s//8)

def san(pos, m, newpos, mate):
    f, t, pr = m; p = pos.b[f]
    if p[1] == 'K' and abs(t-f) == 2: s = 'O-O' if t > f else 'O-O-O'
    else:
        cap = bool(pos.b[t]) or (p[1] == 'P' and f % 8 != t % 8)
        if p[1] == 'P': s = (FILES[f % 8] + 'x' if cap else '') + sq_name(t)
        else: s = p[1] + ('x' if cap else '') + sq_name(t)
        if pr: s += '=' + pr
    return s + ('#' if mate else '+' if in_check(newpos) else '')

# ── AI: negamax + alpha-beta + quiescence ──
def evaluate(pos):
    s = 0
    for i, p in enumerate(pos.b):
        if not p: continue
        r, c = divmod(i, 8); v = VAL[p[1]]; cd = abs(3.5-c) + abs(3.5-r)
        if p[1] in 'NB': v += int((7-cd)*5)
        elif p[1] == 'P': v += ((6-r) if p[0] == 'w' else (r-1))*6 + int((3.5-abs(3.5-c))*3)
        s += v if p[0] == pos.turn else -v
    return s

def order(pos, m):
    v = pos.b[m[1]]; sc = VAL[v[1]]*10 - VAL[pos.b[m[0]][1]] if v else 0
    return sc + (800 if m[2] == 'Q' else 0)

def quiesce(pos, alpha, beta, d=0):
    stand = evaluate(pos)
    if stand >= beta: return beta
    alpha = max(alpha, stand)
    if d >= 3: return alpha
    caps = [m for m in legal(pos) if pos.b[m[1]]]
    for m in sorted(caps, key=lambda m: -order(pos, m)):
        sc = -quiesce(make(pos, m), -beta, -alpha, d+1)
        if sc >= beta: return beta
        alpha = max(alpha, sc)
    return alpha

def search(pos, depth, alpha, beta):
    moves = legal(pos)
    if not moves: return -(100000+depth) if in_check(pos) else 0
    if depth == 0: return quiesce(pos, alpha, beta)
    for m in sorted(moves, key=lambda m: -order(pos, m)):
        sc = -search(make(pos, m), depth-1, -beta, -alpha)
        if sc >= beta: return beta
        alpha = max(alpha, sc)
    return alpha

def choose(pos, depth):
    scored = []
    for m in legal(pos):
        scored.append((-search(make(pos, m), depth-1, -10**7, 10**7), m))
    best = max(s for s, _ in scored)
    return random.choice([m for s, m in scored if s >= best - (12 if depth > 1 else 40)])

# ───────────────────────── Audio synthesis ─────────────────────────
SR = 22050
TAU = 2*math.pi
def to_sound(samples, vol=0.8):
    peak = max(1e-9, max(abs(x) for x in samples))
    return pygame.mixer.Sound(buffer=array.array('h', [int(x/peak*vol*32767) for x in samples]))

def tock(freq=190, dur=.14, nz=.5):
    out, lp = [], 0.0
    for i in range(int(SR*dur)):
        t = i/SR
        w = math.sin(TAU*freq*t*(1+.3*math.exp(-t*60)))*math.exp(-t*38)
        lp += (random.uniform(-1, 1)-lp)*.35
        out.append(w + nz*lp*math.exp(-t*140))
    return out

def ping(freq, dur=.35, decay=7):
    return [min(1, i/SR*200)*math.exp(-i/SR*decay)*(math.sin(TAU*freq*i/SR)+.3*math.sin(TAU*freq*2*i/SR)) for i in range(int(SR*dur))]

def mix(parts):
    n = max(int(o*SR)+len(s) for o, s in parts); out = [0.0]*n
    for o, s in parts:
        st = int(o*SR)
        for i, x in enumerate(s): out[st+i] += x
    return out

def hz(m): return 440*2**((m-69)/12)

def build_sfx():
    S = {}
    S['move'] = to_sound(tock(190), .7)
    S['capture'] = to_sound(mix([(0, tock(130, .22, 1.0)), (.05, tock(95, .2, .8))]), .9)
    S['castle'] = to_sound(mix([(0, tock(190)), (.13, tock(160))]), .7)
    S['check'] = to_sound(mix([(0, tock(150, .2, .8)), (.06, ping(880, .3)), (.14, ping(1175, .4))]), .8)
    S['promote'] = to_sound(mix([(i*.09, ping(hz(m), .4, 6)) for i, m in enumerate((72, 76, 79, 84))]), .7)
    S['select'] = to_sound(ping(1400, .05, 60), .25)
    S['illegal'] = to_sound([math.copysign(1, math.sin(TAU*90*i/SR))*math.exp(-i/SR*18) for i in range(int(SR*.18))], .3)
    S['win'] = to_sound(mix([(i*.12, ping(hz(m), .8, 3)) for i, m in enumerate((60, 64, 67, 72, 76))]), .8)
    S['lose'] = to_sound(mix([(i*.2, ping(hz(m), .8, 3)) for i, m in enumerate((69, 65, 62, 57))]), .8)
    S['draw'] = to_sound(mix([(0, ping(hz(64), .8, 3)), (.25, ping(hz(60), .9, 3))]), .7)
    return S

def build_music():
    L = int(SR*16); buf = [0.0]*L
    chords = [(45, (57, 60, 64)), (41, (53, 57, 60)), (36, (48, 52, 55)), (43, (55, 59, 62))]
    for ci, (bass, tones) in enumerate(chords):
        s0 = int(ci*4*SR)
        for m, amp in [(bass, .13)] + [(t, .045) for t in tones]:
            f = hz(m); dur = 5.2
            for i in range(int(dur*SR)):
                t = i/SR; env = min(t/1.2, 1)*min((dur-t)/1.5, 1)
                buf[(s0+i) % L] += env*amp*(math.sin(TAU*f*t) + .4*math.sin(TAU*f*2.003*t))
        for n in range(8):
            f = hz(tones[(0, 1, 2, 1, 2, 1, 2, 1)[n]]+12); st = s0 + int(n*.5*SR)
            for i in range(int(1.4*SR)):
                t = i/SR
                buf[(st+i) % L] += .07*math.exp(-t*3.5)*min(1, t*80)*math.sin(TAU*f*t)
    dry = buf[:]; d = int(SR*.375)
    for i in range(L): buf[i] += .35*dry[i-d] + .2*dry[i-2*d]
    return to_sound(buf, .55)

# ───────────────────────── Graphics ─────────────────────────
SQ, BX, BY = 80, 50, 50
W, H = 930, 740
LIGHT, DARK = (240, 217, 181), (181, 136, 99)

def make_piece(kind, color):
    S = 400; k = S/100
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    fill = (248, 244, 234) if color == 'w' else (58, 58, 70)
    shade = (206, 198, 180) if color == 'w' else (92, 92, 108)
    line = (30, 24, 28); lw = int(2.6*k)
    def poly(pts, col=fill):
        P = [(x*k, y*k) for x, y in pts]
        pygame.draw.polygon(surf, col, P); pygame.draw.lines(surf, line, True, P, lw)
    def circ(cx, cy, r, col=fill):
        pygame.draw.circle(surf, col, (cx*k, cy*k), r*k); pygame.draw.circle(surf, line, (cx*k, cy*k), r*k, lw)
    def rect(x, y, w, h, col=fill, rad=3):
        R = pygame.Rect(x*k, y*k, w*k, h*k)
        pygame.draw.rect(surf, col, R, border_radius=int(rad*k)); pygame.draw.rect(surf, line, R, lw, border_radius=int(rad*k))
    rect(24, 76, 52, 9, shade); rect(18, 84, 64, 8, shade)
    if kind == 'P':
        poly([(40, 46), (60, 46), (67, 76), (33, 76)]); rect(35, 42, 30, 7); circ(50, 30, 11)
    elif kind == 'R':
        poly([(34, 36), (66, 36), (70, 77), (30, 77)]); rect(27, 31, 46, 8)
        for x in (28, 44, 60): rect(x, 18, 12, 15, rad=1)
    elif kind == 'N':
        poly([(28, 78), (32, 58), (42, 46), (34, 42), (30, 34), (42, 22), (46, 13), (53, 22), (65, 27), (73, 46), (71, 78)])
        circ(52, 33, 2.6, line); pygame.draw.circle(surf, line, (35*k, 38*k), 2*k)
    elif kind == 'B':
        poly([(38, 50), (62, 50), (67, 76), (33, 76)]); rect(34, 46, 32, 7)
        pygame.draw.ellipse(surf, fill, (38*k, 20*k, 24*k, 30*k)); pygame.draw.ellipse(surf, line, (38*k, 20*k, 24*k, 30*k), lw)
        circ(50, 15, 4.5); pygame.draw.line(surf, line, (50*k, 27*k), (57*k, 36*k), lw)
    elif kind == 'Q':
        poly([(36, 50), (64, 50), (70, 77), (30, 77)])
        poly([(28, 24), (36, 48), (40, 20), (46, 46), (50, 17), (54, 46), (60, 20), (64, 48), (72, 24), (67, 54), (33, 54)])
        for x, y in ((28, 22), (40, 17), (50, 14), (60, 17), (72, 22)): circ(x, y, 4.2)
    else:
        poly([(36, 48), (64, 48), (70, 77), (30, 77)]); rect(31, 36, 38, 14)
        rect(46, 8, 8, 28, rad=1); rect(39, 15, 22, 8, rad=1)
    return surf

# ───────────────────────── Game ─────────────────────────
class Game:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 1, 512)
        pygame.init(); pygame.display.set_caption('Chess')
        self.screen = pygame.display.set_mode((W, H)); self.clock = pygame.time.Clock()
        self.audio = pygame.mixer.get_init() is not None
        self.sfx = {}; self.music_ch = None; self.music_on = True; self.sfx_on = True
        if self.audio:
            self.sfx = build_sfx()
            threading.Thread(target=self._music_worker, daemon=True).start()
        self.f_title = pygame.font.SysFont('georgia,timesnewroman,serif', 38, bold=True)
        self.f_big = pygame.font.SysFont('georgia,timesnewroman,serif', 54, bold=True)
        self.f = pygame.font.SysFont('segoeui,helvetica,arial', 17)
        self.f_s = pygame.font.SysFont('segoeui,helvetica,arial', 14)
        self.img, self.icon = {}, {}
        for c in 'wb':
            for kd in 'PNBRQK':
                big = make_piece(kd, c)
                im = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
                pygame.draw.ellipse(im, (0, 0, 0, 55), (14, 64, 52, 13))
                im.blit(pygame.transform.smoothscale(big, (72, 72)), (4, 3))
                self.img[c+kd] = im; self.icon[c+kd] = pygame.transform.smoothscale(big, (26, 26))
        self.bg = pygame.Surface((W, H))
        for y in range(H):
            t = y/H; pygame.draw.line(self.bg, (int(34-18*t), int(38-18*t), int(58-26*t)), (0, y), (W, y))
        self.vs_ai, self.level, self.human, self.flip = True, 2, 'w', False
        self.reset()

    def _music_worker(self):
        try:
            snd = build_music(); self.music_ch = snd.play(loops=-1); self.music_ch.set_volume(.4)
            if not self.music_on: self.music_ch.pause()
        except Exception: pass

    def play(self, name):
        if self.audio and self.sfx_on and name in self.sfx: self.sfx[name].play()

    def reset(self):
        self.pos = start_pos(); self.hist = []; self.sans = []; self.last = None
        self.sel = None; self.promo = None; self.result = None; self.anim = None
        self.thinking = False; self.ai_move = None; self.gen = getattr(self, 'gen', 0)+1
        self.refresh()

    def refresh(self):
        self.legal = legal(self.pos); self.chk = in_check(self.pos)

    def ai_turn(self): return self.vs_ai and self.pos.turn != self.human

    def apply(self, m):
        pos = self.pos; piece = pos.b[m[0]]
        cap = bool(pos.b[m[1]]) or (piece[1] == 'P' and m[0] % 8 != m[1] % 8)
        newp = make(pos, m); nl = legal(newp); chk = in_check(newp); mate = chk and not nl
        self.hist.append((pos, self.last)); self.sans.append(san(pos, m, newp, mate))
        self.pos, self.legal, self.chk, self.last, self.sel = newp, nl, chk, m, None
        self.anim = dict(piece=piece, frm=m[0], to=m[1], t0=time.time(), dur=.2)
        castle = piece[1] == 'K' and abs(m[1]-m[0]) == 2
        if not nl:
            winner = opp(newp.turn) if chk else None
            self.result = ('mate', winner) if chk else ('stalemate', None)
            self.play('capture' if cap else 'move')
            self.play('draw' if not chk else ('win' if (not self.vs_ai or winner == self.human) else 'lose'))
        else:
            self.play('check' if chk else 'promote' if m[2] else 'castle' if castle else 'capture' if cap else 'move')

    def undo(self):
        if self.thinking or not self.hist: return
        n = 2 if (self.vs_ai and len(self.hist) >= 2 and opp(self.pos.turn) == self.human and not self.result) or \
                 (self.vs_ai and self.pos.turn != self.human and len(self.hist) >= 2) else 1
        for _ in range(n):
            self.pos, self.last = self.hist.pop(); self.sans.pop()
        self.result = None; self.sel = None; self.anim = None; self.refresh()

    def update(self):
        now = time.time()
        if self.anim and now >= self.anim['t0'] + self.anim['dur']: self.anim = None
        if self.result or self.anim or self.promo or not self.ai_turn(): return
        if not self.thinking:
            self.thinking, self.ai_start, self.ai_move = True, now, None
            def work(pos, depth, gen):
                mv = choose(pos, depth); self.ai_move = (gen, mv)
            threading.Thread(target=work, args=(self.pos, self.level, self.gen), daemon=True).start()
        elif self.ai_move and self.ai_move[0] == self.gen and now - self.ai_start > .5:
            m = self.ai_move[1]; self.ai_move = None; self.thinking = False; self.apply(m)

    # ── input ──
    def sq_xy(self, sq):
        r, c = divmod(sq, 8)
        if self.flip: r, c = 7-r, 7-c
        return BX + c*SQ, BY + r*SQ

    def xy_sq(self, x, y):
        c, r = (x-BX)//SQ, (y-BY)//SQ
        if not (0 <= c < 8 and 0 <= r < 8): return None
        if self.flip: r, c = 7-r, 7-c
        return r*8+c

    def click(self, pos_xy):
        if self.result or self.anim or self.thinking or self.ai_turn(): return
        if self.promo:
            f, t = self.promo; x0 = BX + 4*SQ - 2*SQ
            for i, q in enumerate('QRBN'):
                if pygame.Rect(x0+i*SQ, BY+4*SQ-SQ//2, SQ, SQ).collidepoint(pos_xy):
                    self.promo = None; self.apply((f, t, q)); return
            self.promo = None; return
        sq = self.xy_sq(*pos_xy)
        if sq is None: self.sel = None; return
        if self.sel is not None:
            ms = [m for m in self.legal if m[0] == self.sel and m[1] == sq]
            if ms:
                if ms[0][2]: self.promo = (self.sel, sq); self.sel = None
                else: self.apply(ms[0])
                return
        p = self.pos.b[sq]
        if p and p[0] == self.pos.turn:
            self.sel = sq; self.play('select')
        else:
            if self.sel is not None: self.play('illegal')
            self.sel = None

    def key(self, k):
        if k == pygame.K_n: self.reset()
        elif k == pygame.K_u: self.undo()
        elif k == pygame.K_f: self.flip = not self.flip
        elif k == pygame.K_p: self.vs_ai = not self.vs_ai; self.reset()
        elif k == pygame.K_c: self.human = opp(self.human); self.flip = self.human == 'b'; self.reset()
        elif k in (pygame.K_1, pygame.K_2, pygame.K_3): self.level = int(pygame.key.name(k))
        elif k == pygame.K_m:
            self.music_on = not self.music_on
            if self.music_ch: (self.music_ch.unpause if self.music_on else self.music_ch.pause)()
        elif k == pygame.K_s: self.sfx_on = not self.sfx_on

    # ── drawing ──
    def text(self, s, font, col, x, y, center=False):
        im = font.render(s, True, col); r = im.get_rect()
        if center: r.center = (x, y)
        else: r.topleft = (x, y)
        self.screen.blit(im, r)

    def draw(self):
        sc = self.screen; sc.blit(self.bg, (0, 0))
        pygame.draw.rect(sc, (92, 60, 38), (BX-16, BY-16, 8*SQ+32, 8*SQ+32), border_radius=12)
        pygame.draw.rect(sc, (60, 38, 24), (BX-16, BY-16, 8*SQ+32, 8*SQ+32), 3, border_radius=12)
        for r in range(8):
            for c in range(8):
                pygame.draw.rect(sc, LIGHT if (r+c) % 2 == 0 else DARK, (BX+c*SQ, BY+r*SQ, SQ, SQ))
        for i in range(8):
            fi = 7-i if self.flip else i; rk = (i+1) if self.flip else 8-i
            self.text(FILES[fi], self.f_s, (230, 210, 180), BX+i*SQ+SQ//2, BY+8*SQ+8, True)
            self.text(str(rk), self.f_s, (230, 210, 180), BX-8-3, BY+i*SQ+SQ//2, True)
        ov = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
        def tint(sq, col): ov.fill(col); sc.blit(ov, self.sq_xy(sq))
        if self.last: tint(self.last[0], (245, 220, 70, 95)); tint(self.last[1], (245, 220, 70, 120))
        if self.sel is not None: tint(self.sel, (110, 200, 90, 130))
        if self.chk:
            kx, ky = self.sq_xy(self.pos.b.index(self.pos.turn+'K')); g = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
            for i, r in enumerate(range(40, 0, -5)): pygame.draw.circle(g, (230, 40, 40, 20+i*16), (40, 40), r)
            sc.blit(g, (kx, ky))
        hide = self.anim['to'] if self.anim else -1
        for sq, p in enumerate(self.pos.b):
            if p and sq != hide: sc.blit(self.img[p], self.sq_xy(sq))
        if self.sel is not None:
            d = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
            for m in self.legal:
                if m[0] != self.sel: continue
                d.fill((0, 0, 0, 0))
                if self.pos.b[m[1]] or (self.pos.b[m[0]][1] == 'P' and m[0] % 8 != m[1] % 8):
                    pygame.draw.circle(d, (200, 50, 50, 150), (40, 40), 38, 6)
                else: pygame.draw.circle(d, (40, 90, 40, 140), (40, 40), 11)
                sc.blit(d, self.sq_xy(m[1]))
        if self.anim:
            a = self.anim; t = min(1, (time.time()-a['t0'])/a['dur']); t = 1-(1-t)**3
            x0, y0 = self.sq_xy(a['frm']); x1, y1 = self.sq_xy(a['to'])
            sc.blit(self.img[a['piece']], (x0+(x1-x0)*t, y0+(y1-y0)*t))
        if self.promo:
            dim = pygame.Surface((8*SQ, 8*SQ), pygame.SRCALPHA); dim.fill((0, 0, 0, 150)); sc.blit(dim, (BX, BY))
            x0 = BX+4*SQ-2*SQ; pygame.draw.rect(sc, (240, 235, 220), (x0-8, BY+4*SQ-SQ//2-8, 4*SQ+16, SQ+16), border_radius=12)
            for i, q in enumerate('QRBN'): sc.blit(self.img[self.pos.turn+q], (x0+i*SQ, BY+4*SQ-SQ//2))
        self.draw_panel()
        if self.result:
            ban = pygame.Surface((8*SQ, 170), pygame.SRCALPHA); ban.fill((10, 10, 20, 205)); sc.blit(ban, (BX, BY+235))
            k, w = self.result
            self.text('Checkmate!' if k == 'mate' else 'Stalemate', self.f_big, (255, 215, 90), BX+4*SQ, BY+292, True)
            sub = ('White wins' if w == 'w' else 'Black wins') if k == 'mate' else 'The game is a draw'
            self.text(sub + '  -  press N for a new game', self.f, (230, 230, 240), BX+4*SQ, BY+350, True)
        pygame.display.flip()

    def draw_panel(self):
        sc = self.screen; px, pw = 722, 190
        pygame.draw.rect(sc, (22, 25, 38), (px, 34, pw, H-68), border_radius=14)
        pygame.draw.rect(sc, (70, 76, 100), (px, 34, pw, H-68), 2, border_radius=14)
        self.text('CHESS', self.f_title, (240, 215, 150), px+pw//2, 68, True)
        mode = f"vs AI ({['Easy','Medium','Hard'][self.level-1]})" if self.vs_ai else '2 players'
        self.text(mode, self.f, (160, 170, 200), px+pw//2, 102, True)
        if self.result: st = 'Game over'
        elif self.thinking: st = 'AI is thinking' + '.'*(int(time.time()*2) % 4)
        elif self.chk: st = ('White' if self.pos.turn == 'w' else 'Black') + ' in check!'
        else: st = ('White' if self.pos.turn == 'w' else 'Black') + ' to move'
        pygame.draw.circle(sc, (245, 245, 235) if self.pos.turn == 'w' else (20, 20, 25), (px+22, 134), 9)
        pygame.draw.circle(sc, (150, 150, 160), (px+22, 134), 9, 2)
        self.text(st, self.f, (255, 130, 110) if self.chk else (230, 232, 245), px+40, 124)
        # captured pieces
        init = {'P': 8, 'N': 2, 'B': 2, 'R': 2, 'Q': 1}; y = 162; mat = {'w': 0, 'b': 0}
        for side in 'wb':
            have = {k: 0 for k in init}
            for p in self.pos.b:
                if p and p[0] == side and p[1] != 'K': have[p[1]] += 1
            self.text(('White' if side == 'b' else 'Black') + ' captured:', self.f_s, (150, 158, 185), px+14, y); y += 20
            x = px+14
            for kd in 'QRBNP':
                for _ in range(init[kd]-have[kd]):
                    sc.blit(self.icon[side+kd], (x, y)); x += 15; mat[opp(side)] += VAL[kd]
            y += 34
        diff = (mat['w']-mat['b'])//100
        if diff: self.text(f"{'White' if diff > 0 else 'Black'} +{abs(diff)}", self.f, (140, 220, 140), px+pw//2, y+6, True)
        # move list
        y = 300; self.text('Moves', self.f_s, (150, 158, 185), px+14, y); y += 22
        pairs = [(i//2+1, self.sans[i], self.sans[i+1] if i+1 < len(self.sans) else '') for i in range(0, len(self.sans), 2)][-13:]
        for n, a, b in pairs:
            self.text(f'{n}.', self.f_s, (120, 128, 155), px+14, y); self.text(a, self.f_s, (230, 232, 245), px+46, y)
            self.text(b, self.f_s, (230, 232, 245), px+112, y); y += 20
        hints = ['N new   U undo   F flip', 'P mode   C swap side', '1/2/3 AI level', f"M music {'on' if self.music_on else 'off'}   S sfx {'on' if self.sfx_on else 'off'}"]
        for i, h in enumerate(hints): self.text(h, self.f_s, (130, 138, 168), px+pw//2, H-130+i*20, True)
        if not self.audio: self.text('(no audio device)', self.f_s, (200, 120, 120), px+pw//2, H-48, True)

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE): return
                if e.type == pygame.KEYDOWN: self.key(e.key)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1: self.click(e.pos)
            self.update(); self.draw(); self.clock.tick(60)

if __name__ == '__main__':
    Game().run()
    pygame.quit()
