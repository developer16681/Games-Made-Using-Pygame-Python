"""
NEON DRIFT - a 3D arcade space-runner in Python (Panda3D + NumPy)

Install:  pip install panda3d numpy
Run:      python neon_drift.py

Controls: LEFT/RIGHT or A/D = change lane | ENTER/SPACE = start | M = mute | ESC = quit
Everything (3D models, music, sound effects) is generated in code - no asset files.
"""
import os, sys, math, random, wave, tempfile
import numpy as np
from panda3d.core import (loadPrcFileData, Vec3, Point3, Filename, NodePath, LineSegs,
                          GeomVertexFormat, GeomVertexData, GeomVertexWriter, Geom,
                          GeomTriangles, GeomNode, AmbientLight, DirectionalLight,
                          PointLight, Fog, TransparencyAttrib, Material, TextNode)

loadPrcFileData("", "window-title Neon Drift\nwin-size 1280 720\nmultisamples 4\nframebuffer-multisample 1\nsync-video 1")
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from direct.filter.CommonFilters import CommonFilters

CYAN, PINK = (0.0, 0.94, 1.0, 1), (1.0, 0.18, 0.58, 1)

# ----------------------------------------------------------------- procedural meshes
def make_mesh(tris, color, center=(0, 0, 0), name="mesh"):
    vd = GeomVertexData(name, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    vd.setNumRows(len(tris) * 3)
    vw, nw, cw = (GeomVertexWriter(vd, c) for c in ("vertex", "normal", "color"))
    prim, i, ctr = GeomTriangles(Geom.UHStatic), 0, Vec3(*center)
    for a, b, c in tris:
        A, B, C = Vec3(*a), Vec3(*b), Vec3(*c)
        n = (B - A).cross(C - A)
        if n.lengthSquared() > 0:
            n.normalize()
        if n.dot((A + B + C) / 3 - ctr) < 0:
            n = -n
        for p in (A, B, C):
            vw.addData3(p); nw.addData3(n); cw.addData4(*color)
        prim.addVertices(i, i + 1, i + 2); i += 3
    g = Geom(vd); g.addPrimitive(prim)
    node = GeomNode(name); node.addGeom(g)
    np_ = NodePath(node); np_.setTwoSided(True)
    return np_

def box(sx, sy, sz, color):
    x, y, z = sx / 2, sy / 2, sz / 2
    v = [(a, b, c) for a in (-x, x) for b in (-y, y) for c in (-z, z)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = []
    for a, b, c, d in faces:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return make_mesh(tris, color, name="box")

def cone(r, length, color, sides=6):  # tip points along +Y
    tip, base = (0, length / 2, 0), -length / 2
    ring = [(r * math.cos(2 * math.pi * i / sides), base, r * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    tris = []
    for i in range(sides):
        a, b = ring[i], ring[(i + 1) % sides]
        tris += [(tip, a, b), ((0, base, 0), b, a)]
    return make_mesh(tris, color, name="cone")

def octa(r, color):
    ax = [(r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r)]
    tris = [(ax[x], ax[y], ax[z]) for x in (0, 1) for y in (2, 3) for z in (4, 5)]
    return make_mesh(tris, color, name="octa")

def sphere(r, color, seg=14):
    def P(i, j):
        th, ph = math.pi * i / seg, 2 * math.pi * j / seg
        return (r * math.sin(th) * math.cos(ph), r * math.sin(th) * math.sin(ph), r * math.cos(th))
    tris = []
    for i in range(seg):
        for j in range(seg):
            a, b, c, d = P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)
            tris += [(a, b, c), (a, c, d)]
    return make_mesh(tris, color, name="sphere")

def torus(R, r, color, seg=48, tseg=8):  # ring around the Y axis (the tunnel direction)
    def P(i, j):
        u, v = 2 * math.pi * i / seg, 2 * math.pi * j / tseg
        return ((R + r * math.cos(v)) * math.cos(u), r * math.sin(v), (R + r * math.cos(v)) * math.sin(u))
    tris = []
    for i in range(seg):
        for j in range(tseg):
            a, b, c, d = P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)
            tris += [(a, b, c), (a, c, d)]
    return make_mesh(tris, color, name="torus")

# ----------------------------------------------------------------- procedural audio
SR = 22050
mt = lambda n: 440 * 2 ** ((n - 69) / 12)
CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G

def tone(f, d, kind="sine", v=0.3, slide=None):
    n = int(SR * d); t = np.arange(n) / SR
    fr = f * (slide / f) ** (t / d) if slide else np.full(n, float(f))
    ph = 2 * np.pi * np.cumsum(fr) / SR
    w = np.sin(ph) if kind == "sine" else np.sign(np.sin(ph)) if kind == "square" else 2 * ((ph / (2 * np.pi)) % 1) - 1
    return w * v * np.exp(-6.9 * t / d) * np.minimum(1, t / 0.003)

def noise(d, v=0.3, hp=False):
    n = int(SR * d); t = np.arange(n) / SR
    x = np.random.uniform(-1, 1, n)
    if hp:
        x = np.diff(x, prepend=0)
    return x * v * np.exp(-6.9 * t / d)

def mix(buf, sig, start):
    end = min(len(buf), start + len(sig))
    if end > start:
        buf[start:end] += sig[:end - start]

def build_music():
    sd = 60 / 132 / 4; steps = 64
    buf = np.zeros(int(SR * sd * steps))
    for s in range(steps):
        t0, c, k = int(s * sd * SR), CHORDS[(s >> 4) & 3], s & 15
        mix(buf, tone(mt(c[[0, 1, 2, 1][k & 3]] + 12 + (12 if k > 7 else 0)), 0.18, "square", 0.05), t0)
        if k % 2 == 0: mix(buf, tone(mt(c[0] - 12), 0.22, "saw", 0.13), t0)
        if k % 4 == 0: mix(buf, tone(120, 0.15, "sine", 0.5, 40), t0)
        if k in (4, 12): mix(buf, noise(0.15, 0.2, True), t0)
        if k % 2 == 1: mix(buf, noise(0.04, 0.06, True), t0)
    buf = buf + np.roll(buf, int(0.34 * SR)) * 0.35 + np.roll(buf, int(0.68 * SR)) * 0.15
    return buf / np.abs(buf).max() * 0.85

def build_engine():
    t = np.arange(SR) / SR
    w = (2 * ((55 * t) % 1) - 1) * 0.6 + np.sin(2 * np.pi * 110 * t) * 0.3
    k = np.ones(40) / 40
    return np.convolve(np.r_[w[-40:], w, w[:40]], k, "same")[40:-40] * 0.5

def save_wav(folder, name, arr):
    p = os.path.join(folder, name)
    with wave.open(p, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((np.clip(arr, -1, 1) * 32767).astype("<i2").tobytes())
    return Filename.fromOsSpecific(p)

# ----------------------------------------------------------------- game
class Item:
    def __init__(self, np_, kind):
        self.np, self.kind = np_, kind

class Game(ShowBase):
    def __init__(self):
        super().__init__()
        self.disableMouse()
        self.setBackgroundColor(0.02, 0.012, 0.06)
        self.state, self.lane, self.score, self.lives = "menu", 0, 0.0, 3
        self.spd, self.acc, self.inv, self.shake, self.off = 12.0, 0.0, 0.0, 0.0, 0.0
        self.items, self.pi, self.muted = [], 0, False
        self.hi_path = os.path.join(os.path.expanduser("~"), ".neon_drift_hi")
        try: self.hi = int(open(self.hi_path).read())
        except Exception: self.hi = 0

        self.build_lighting(); self.build_world(); self.build_ship(); self.build_particles()
        self.build_audio(); self.build_hud(); self.build_input()
        try:  # glow post-processing (needs a shader-capable GPU)
            self.filters = CommonFilters(self.win, self.cam)
            self.filters.setBloom(blend=(0, 0, 0, 1), mintrigger=0.55, maxtrigger=1.0, desat=0.2, intensity=1.3, size="medium")
        except Exception as e:
            print("Bloom unavailable:", e)
        self.taskMgr.add(self.update, "update")

    # ---- setup
    def build_lighting(self):
        a = AmbientLight("a"); a.setColor((0.35, 0.25, 0.55, 1)); self.render.setLight(self.render.attachNewNode(a))
        d = DirectionalLight("d"); d.setColor((1, 0.5, 0.8, 1))
        dn = self.render.attachNewNode(d); dn.setHpr(30, -50, 0); self.render.setLight(dn)
        p = PointLight("p"); p.setColor((0, 2.2, 2.5, 1)); p.setAttenuation((1, 0, 0.02))
        self.pln = self.render.attachNewNode(p); self.render.setLight(self.pln)
        fog = Fog("fog"); fog.setColor(0.04, 0.015, 0.1); fog.setExpDensity(0.02)
        self.render.setFog(fog)
        self.render.setShaderAuto()

    def build_world(self):
        self.rings = []
        for i in range(14):
            r = torus(9, 0.09, PINK if i % 2 else CYAN)
            r.reparentTo(self.render); r.setLightOff(); r.setPos(0, i * 12, 2)
            self.rings.append(r)
        ls = LineSegs(); ls.setThickness(1.5); ls.setColor(0.7, 0.15, 0.55, 1)
        for i in range(-20, 21):
            ls.moveTo(i * 4, 0, 0); ls.drawTo(i * 4, 200, 0)
        for j in range(51):
            ls.moveTo(-80, j * 4, 0); ls.drawTo(80, j * 4, 0)
        self.grid = self.render.attachNewNode(ls.create()); self.grid.setLightOff(); self.grid.setZ(-0.5)
        ls = LineSegs(); ls.setThickness(2.5); ls.setColor(1, 1, 1, 1)
        for _ in range(500):
            ls.moveTo(random.uniform(-80, 80), random.uniform(0, 300), random.uniform(-5, 60))
            ls.moveTo(0, -999, 0)  # isolated vertices render as points
        star = ls.create()
        self.stars = [self.render.attachNewNode(star)]
        self.stars.append(self.render.attachNewNode(star))
        for s in self.stars: s.setLightOff()

    def build_ship(self):
        self.ship = self.render.attachNewNode("ship")
        body = cone(0.5, 2.4, (0.55, 0.6, 0.85, 1)); body.reparentTo(self.ship)
        wing = box(2.6, 0.9, 0.07, (0.15, 0.15, 0.3, 1)); wing.reparentTo(self.ship); wing.setY(-0.5)
        fin = box(0.07, 0.7, 0.6, (0.15, 0.15, 0.3, 1)); fin.reparentTo(self.ship); fin.setPos(0, -0.7, 0.35)
        for sx in (-1.3, 1.3):
            tip = box(0.12, 0.9, 0.1, PINK); tip.reparentTo(self.ship); tip.setPos(sx, -0.5, 0); tip.setLightOff()
        self.eng = sphere(0.3, CYAN); self.eng.reparentTo(self.ship); self.eng.setY(-1.2); self.eng.setLightOff()
        self.ship.setZ(1)

    def build_particles(self):
        tpl = box(0.18, 0.18, 0.18, (1, 1, 1, 1)); tpl.setLightOff()
        self.parts = []
        for _ in range(100):
            n = tpl.copyTo(self.render); n.setTransparency(TransparencyAttrib.MAlpha); n.hide()
            self.parts.append({"n": n, "v": Vec3(0), "life": 0.0, "max": 1.0})

    def puff(self, pos, col, vel, life):
        p = self.parts[self.pi % len(self.parts)]; self.pi += 1
        p.update(v=Vec3(*vel), life=life, max=life); p["n"].setPos(pos); p["n"].setColor(*col); p["n"].show()

    def burst(self, pos, col, n):
        for _ in range(n):
            self.puff(pos, col, (random.uniform(-7, 7), random.uniform(-7, 7), random.uniform(-7, 7)), 0.7)

    def build_audio(self):
        folder = tempfile.mkdtemp(prefix="neon_drift_")
        F = lambda name, arr: save_wav(folder, name, arr)
        orb = np.zeros(int(SR * 0.3)); mix(orb, tone(880, 0.1, v=0.4), 0); mix(orb, tone(1320, 0.18, v=0.4), int(SR * 0.07))
        hit = np.zeros(int(SR * 0.5)); mix(hit, noise(0.5, 0.7), 0); mix(hit, tone(160, 0.4, "saw", 0.4, 30), 0)
        files = {"music": F("music.wav", build_music()), "engine": F("engine.wav", build_engine()),
                 "orb": F("orb.wav", orb), "hit": F("hit.wav", hit),
                 "over": F("over.wav", tone(330, 0.9, "saw", 0.3, 55)), "lane": F("lane.wav", noise(0.1, 0.25, True))}
        self.snd = {k: self.loader.loadSfx(v) for k, v in files.items()}
        for k in ("music", "engine"): self.snd[k].setLoop(True)
        self.snd["music"].setVolume(0.55); self.snd["engine"].setVolume(0.25)
        self.snd["music"].play(); self.snd["engine"].play()

    def build_hud(self):
        kw = dict(fg=CYAN, shadow=(0, 0, 0, 1), scale=0.065, mayChange=True)
        self.t_score = OnscreenText(parent=self.a2dTopLeft, pos=(0.06, -0.11), align=TextNode.ALeft, text="SCORE 0", **kw)
        self.t_lives = OnscreenText(parent=self.a2dTopCenter, pos=(0, -0.11), text="", **dict(kw, fg=PINK))
        self.t_hi = OnscreenText(parent=self.a2dTopRight, pos=(-0.06, -0.11), align=TextNode.ARight, text=f"BEST {self.hi}", **kw)
        self.t_title = OnscreenText(text="NEON DRIFT", pos=(0, 0.2), scale=0.2, fg=CYAN, shadow=PINK, mayChange=True)
        self.t_sub = OnscreenText(text="Collect cyan orbs, dodge magenta crystals\nLEFT/RIGHT or A/D to steer  -  M to mute\n\nPress ENTER to launch",
                                  pos=(0, -0.05), scale=0.06, fg=(0.9, 0.97, 1, 1), shadow=(0, 0, 0, 1), mayChange=True)
        self.set_lives()

    def build_input(self):
        for k in ("arrow_left", "a"): self.accept(k, self.move, [-1])
        for k in ("arrow_right", "d"): self.accept(k, self.move, [1])
        for k in ("enter", "space"): self.accept(k, self.start)
        self.accept("m", self.toggle_mute); self.accept("escape", sys.exit)

    # ---- game logic
    def set_lives(self):
        self.t_lives.setText("SHIELDS " + "[#]" * max(self.lives, 0) + "[ ]" * (3 - max(self.lives, 0)))

    def toggle_mute(self):
        self.muted = not self.muted
        self.snd["music"].setVolume(0 if self.muted else 0.55); self.snd["engine"].setVolume(0 if self.muted else 0.25)

    def play(self, name):
        if not self.muted: self.snd[name].play()

    def move(self, d):
        if self.state == "play":
            new = max(-1, min(1, self.lane + d))
            if new != self.lane: self.play("lane")
            self.lane = new

    def start(self):
        if self.state == "play": return
        for it in self.items: it.np.removeNode()
        self.items.clear(); self.score, self.lives, self.lane, self.inv, self.acc = 0.0, 3, 0, 0.0, 0.0
        self.state = "play"; self.t_title.hide(); self.t_sub.hide(); self.set_lives()

    def game_over(self):
        self.state = "over"; self.play("over")
        if int(self.score) > self.hi:
            self.hi = int(self.score); self.t_hi.setText(f"BEST {self.hi}")
            try: open(self.hi_path, "w").write(str(self.hi))
            except Exception: pass
        self.t_title.setText("CRASHED"); self.t_title.show()
        self.t_sub.setText(f"Final score {int(self.score)}\n\nPress ENTER to retry"); self.t_sub.show()

    def spawn(self):
        lanes = [-1, 0, 1]; random.shuffle(lanes)
        n = 2 if random.random() < 0.4 else 1
        for i in range(n):
            o = octa(1.1, PINK); o.reparentTo(self.render); o.setPos(lanes[i] * 4, 150, 1)
            m = Material(); m.setEmission((0.5, 0.05, 0.25, 1)); o.setMaterial(m)
            self.items.append(Item(o, 0))
        if random.random() < 0.7:
            b = sphere(0.55, CYAN); b.reparentTo(self.render); b.setPos(lanes[n] * 4, 150, 1.2); b.setLightOff()
            self.items.append(Item(b, 1))

    def update(self, task):
        dt, t = min(globalClock.getDt(), 0.05), task.time
        run = self.state == "play"
        if run:
            self.spd = min(30 + self.score / 30, 75)
            self.score += dt * self.spd * 0.3; self.acc += self.spd * dt
            if self.acc > 16: self.acc = 0; self.spawn()
        v = self.spd if run else 12
        self.off += v * dt

        for r in self.rings:
            r.setY(r.getY() - v * dt)
            if r.getY() < -10: r.setY(r.getY() + 168)
            r.setR(r.getR() + dt * 12)
        self.grid.setY(-20 - (self.off % 4))
        base = -(self.off * 1.5) % 300
        self.stars[0].setY(base - 20); self.stars[1].setY(base + 280)

        sx = self.ship.getX(); tgt = self.lane * 4
        sx += (tgt - sx) * min(1, dt * 10); self.ship.setX(sx)
        self.ship.setR((tgt - sx) * 8); self.ship.setH(-(tgt - sx) * 2.5)
        self.ship.setZ(1 + math.sin(t * 3) * 0.12)
        self.pln.setPos(sx, -2.5, 2)
        self.eng.setScale(1 + math.sin(t * 40) * 0.2)
        self.inv = max(0, self.inv - dt)
        if self.inv > 0 and int(t * 14) % 2: self.ship.hide()
        else: self.ship.show()
        if run:
            p = self.ship.getPos() + Vec3(0, -1.4, 0)
            self.puff(p, CYAN if random.random() < 0.5 else PINK,
                      (random.uniform(-1.5, 1.5), -v * 0.7, random.uniform(-1.5, 1.5)), 0.4)

        for it in list(self.items):
            n = it.np; n.setY(n.getY() - v * dt)
            n.setH(n.getH() + dt * (170 if it.kind else 90)); n.setP(n.getP() + dt * (0 if it.kind else 70))
            if run and abs(n.getY()) < 1.4 and abs(n.getX() - sx) < 1.5:
                if it.kind:
                    self.score += 50; self.play("orb"); self.burst(n.getPos(), CYAN, 14)
                elif self.inv <= 0:
                    self.lives -= 1; self.inv = 1.6; self.shake = 0.6
                    self.play("hit"); self.burst(n.getPos(), PINK, 30); self.set_lives()
                    if self.lives <= 0: self.game_over()
                else:
                    continue
                n.removeNode(); self.items.remove(it)
            elif n.getY() < -12:
                n.removeNode(); self.items.remove(it)

        for p in self.parts:
            if p["life"] > 0:
                p["life"] -= dt; k = max(0, p["life"] / p["max"])
                p["n"].setPos(p["n"].getPos() + p["v"] * dt); p["n"].setAlphaScale(k); p["n"].setScale(k + 0.1)
                if p["life"] <= 0: p["n"].hide()

        self.shake = max(0, self.shake - dt); sh = self.shake * 0.5
        self.camera.setPos(sx * 0.6 + random.uniform(-sh, sh), -9, 3.6 + random.uniform(-sh, sh))
        self.camera.lookAt(Point3(sx * 0.3, 12, 1.2))
        self.camLens.setFov(65 + (v - 30) * 0.25)
        self.snd["engine"].setPlayRate(0.7 + v / 80)
        self.t_score.setText(f"SCORE {int(self.score)}")
        return task.cont

if __name__ == "__main__":
    Game().run()
