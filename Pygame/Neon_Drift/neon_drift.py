"""
NEON DRIFT - a retro-synthwave 3D space racer
---------------------------------------------
Install:  pip install ursina numpy
Run:      python neon_drift.py

Controls: WASD / Arrow keys = fly   |   SHIFT = boost
          SPACE = start             |   R = restart   |   ESC = quit

All music and sound effects are synthesised at start-up (no asset files needed).
"""
import os, math, random, wave, tempfile
import numpy as np
from ursina import *
from panda3d.core import Filename

# ----------------------------------------------------------------------------
# Procedural audio
# ----------------------------------------------------------------------------
SR = 44100
rng = np.random.default_rng(7)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def save_wav(name, data):
    data = np.clip(data, -1, 1)
    path = os.path.join(tempfile.gettempdir(), f"neon_drift_{name}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())
    return path


def synth(f, d, vol=1.0, decay=6.0):
    t = np.arange(int(d * SR)) / SR
    s = (np.sin(2 * np.pi * f * t) + .5 * np.sin(4 * np.pi * f * t)
         + .3 * np.sin(6 * np.pi * f * t) + .6 * np.sin(2 * np.pi * f * 1.006 * t))
    env = np.exp(-t * decay) * (1 - np.exp(-t * 300))
    return s * env * vol / 2.4


def make_music():
    bpm = 124
    step = 60 / bpm / 4
    chords = [(57, 60, 64), (53, 57, 60), (60, 64, 67), (55, 59, 62)]
    roots = [33, 29, 36, 31]
    leads = [(69, 72, 76), (65, 69, 72), (72, 76, 79), (67, 71, 74)]
    steps = 8 * 16
    L = int(steps * step * SR)
    buf = np.zeros(L + SR)

    def add(sig, start):
        i = int(start * SR)
        sig = sig[: len(buf) - i]
        buf[i:i + len(sig)] += sig

    arp_pat = [0, 1, 2, 1, 2, 1, 0, 1]
    for s in range(steps):
        bar, ps, tm = (s // 16) % 4, s % 16, s * step
        if ps % 4 == 0:  # kick
            t = np.arange(int(.25 * SR)) / SR
            ph = np.cumsum(2 * np.pi * (45 + 150 * np.exp(-t * 28)) / SR)
            add(np.sin(ph) * np.exp(-t * 9) * .9, tm)
        if ps in (4, 12):  # snare
            t = np.arange(int(.18 * SR)) / SR
            add(rng.uniform(-1, 1, len(t)) * np.exp(-t * 22) * .35, tm)
        if ps % 2 == 0:  # hats
            t = np.arange(int(.05 * SR)) / SR
            add(rng.uniform(-1, 1, len(t)) * np.exp(-t * 70) * (.2 if ps % 4 == 2 else .1), tm)
        if ps in (0, 3, 6, 8, 11, 14):  # bass
            m = roots[bar] + (12 if ps == 6 else 0)
            add(synth(hz(m), .28, .55, 5), tm)
        add(synth(hz(chords[bar][arp_pat[ps % 8] % 3] + 12), .22, .2, 10), tm)  # arp
        if s >= 64 and ps in (0, 6, 10):  # lead in 2nd half
            add(synth(hz(leads[bar][(ps // 5) % 3] + (0 if ps else 0)), .5, .25, 3.2), tm)
        if ps == 0:  # pad
            d = step * 16
            t = np.arange(int(d * SR)) / SR
            env = np.sin(np.pi * t / d) ** .6
            for m in chords[bar]:
                add(np.sin(2 * np.pi * hz(m) * t) * env * .05, tm)

    tail = buf[L:].copy()
    buf = buf[:L]
    buf[:len(tail)] += tail
    buf = np.tanh(buf * 1.1)
    return save_wav("music", buf / max(np.abs(buf).max(), 1e-6) * .85)


def make_sfx():
    out = {}
    t = np.arange(int(.35 * SR)) / SR  # collect blip
    f = np.where(t < .1, 988, 1319)
    ph = np.cumsum(2 * np.pi * f / SR)
    out["collect"] = save_wav("collect", (np.sin(ph) + .3 * np.sin(2 * ph)) * np.exp(-t * 8) * .6)

    t = np.arange(int(.9 * SR)) / SR  # crash
    noise = np.convolve(rng.uniform(-1, 1, len(t)), np.ones(25) / 25, "same")
    ph = np.cumsum(2 * np.pi * (30 + 90 * np.exp(-t * 6)) / SR)
    out["crash"] = save_wav("crash", (noise * 1.8 + np.sin(ph)) * np.exp(-t * 5) * .8)

    t = np.arange(int(.6 * SR)) / SR  # start whoosh
    ph = np.cumsum(2 * np.pi * (250 + 1400 * (t / .6) ** 2) / SR)
    out["start"] = save_wav("start", np.sin(ph) * np.sin(np.pi * t / .6) * .5)

    over = np.zeros(int(1.6 * SR))  # game over jingle
    for i, m in enumerate((69, 65, 62, 57)):
        s = synth(hz(m), .6, 1.0, 3)
        a = int(i * .3 * SR)
        over[a:a + len(s)] += s[: len(over) - a]
    out["over"] = save_wav("over", over * .8)
    return out


# ----------------------------------------------------------------------------
# Game setup
# ----------------------------------------------------------------------------
app = Ursina(title="NEON DRIFT", borderless=False, vsync=True)
window.exit_button.visible = False
window.fps_counter.enabled = False

BG = color.hex("#08041a")
window.color = BG
scene.fog_color = BG
scene.fog_density = (60, 260)
camera.fov = 80

music_path = make_music()
sfx_paths = make_sfx()
music = base.loader.loadSfx(Filename.fromOsSpecific(music_path))
music.setLoop(True)
music.setVolume(.5)
music.play()
sfx = {k: base.loader.loadSfx(Filename.fromOsSpecific(v)) for k, v in sfx_paths.items()}


def play(name, rate=1.0, vol=.8):
    s = sfx[name]
    s.setVolume(vol)
    s.setPlayRate(rate)
    s.play()


NEON = ["#ff2bd6", "#00e5ff", "#7c4dff", "#ff7a3d", "#39ff14"]

# --- environment -------------------------------------------------------------
floor = Entity(model="cube", scale=(120, .1, 420), position=(0, -.05, 200), color=color.hex("#0b0620"))

GRID_SPAN = 240
grid_lines = [Entity(model="cube", scale=(120, .06, .14), position=(0, .03, i * 6),
                     color=color.hex("#ff2bd6")) for i in range(GRID_SPAN // 6)]
for x in range(-60, 61, 6):
    Entity(model="cube", scale=(.14, .06, 420), position=(x, .03, 200), color=color.hex("#2b6bff"))

sun = Entity(model="circle", scale=110, position=(0, 45, 330), color=color.hex("#ff7a3d"))
sun.setFogOff()
for i in range(6):
    st = Entity(model="quad", scale=(120, 1.5 + i * 1.6), position=(0, 8 + i * 6.5, 329), color=BG)
    st.setFogOff()

stars = []
for _ in range(220):
    s = Entity(model="cube", scale=random.uniform(.1, .3),
               position=(random.uniform(-110, 110), random.uniform(10, 90), random.uniform(0, 220)),
               color=color.hex(random.choice(["#ffffff", "#b3f5ff", "#ffc4f2"])))
    s.setFogOff()
    stars.append(s)

TOWER_SPAN = 300
towers = []
for side in (-1, 1):
    for i in range(14):
        w, h = random.uniform(4, 9), random.uniform(8, 40)
        tw = Entity(model="cube", scale=(w, h, w),
                    position=(side * random.uniform(16, 34), h / 2, i * (TOWER_SPAN / 14) + random.uniform(0, 8)),
                    color=color.hex("#140a30"))
        Entity(parent=tw, model="wireframe_cube", scale=1.005, color=color.hex(random.choice(NEON)))
        towers.append(tw)

# --- player ship -------------------------------------------------------------
ship = Entity(position=(0, 2, 0))
Entity(parent=ship, model="cube", scale=(.7, .35, 2.0), color=color.hex("#00e5ff"))
Entity(parent=ship, model="sphere", scale=(.5, .4, .9), position=(0, .25, .2), color=color.hex("#b3f5ff"))
Entity(parent=ship, model="cube", scale=(2.6, .08, 1.0), position=(0, 0, -.4), color=color.hex("#ff2bd6"))
for sx in (-1.25, 1.25):
    Entity(parent=ship, model="cube", scale=(.1, .45, .7), position=(sx, .2, -.5), color=color.hex("#ff2bd6"))
glow = Entity(parent=ship, model="sphere", scale=.5, position=(0, 0, -1.1), color=color.hex("#ffb300"))
ship_shadow = Entity(model="circle", scale=1.8, rotation_x=90, y=.05, color=color.hex("#0000008c"))

# --- HUD ---------------------------------------------------------------------
hud_score = Text(text="", x=-.85, y=.47, scale=1.6, color=color.hex("#00e5ff"))
hud_best = Text(text="", x=-.85, y=.43, scale=1.1, color=color.hex("#ff2bd6"))
hud_lives = Text(text="", x=.55, y=.47, scale=1.6, color=color.hex("#ff7a3d"))
hud_combo = Text(text="", origin=(0, 0), y=.33, scale=2, color=color.hex("#ffe94d"))

title_ui = [
    Text("NEON DRIFT", origin=(0, 0), y=.18, scale=5.5, color=color.hex("#00e5ff")),
    Text("collect the golden orbs  -  dodge the neon blocks", origin=(0, 0), y=.05, scale=1.5, color=color.hex("#ff2bd6")),
    Text("WASD / ARROWS fly    SHIFT boost", origin=(0, 0), y=-.04, scale=1.3, color=color.white),
    Text("press SPACE to start", origin=(0, 0), y=-.15, scale=2, color=color.hex("#ffe94d")),
]
over_ui = [
    Text("CRASHED", origin=(0, 0), y=.15, scale=5, color=color.hex("#ff2bd6")),
    Text("", origin=(0, 0), y=.02, scale=2, color=color.white),
    Text("press R to fly again", origin=(0, 0), y=-.1, scale=1.8, color=color.hex("#ffe94d")),
]
for t in over_ui:
    t.enabled = False

# --- state -------------------------------------------------------------------
state = "title"
speed, dist, bonus, lives, best = 22.0, 0.0, 0, 3, 0
vx = vy = 0.0
invuln = shake = trail_t = combo_t = 0.0
combo = 0
spawn_t = 1.0
obstacles, orbs, particles = [], [], []


def burst(pos, col, n=18, spd=9):
    for _ in range(n):
        p = Entity(model="cube", position=pos, color=col)
        p.base = random.uniform(.12, .32)
        p.scale = p.base
        p.vel = Vec3(random.uniform(-1, 1), random.uniform(-.3, 1), random.uniform(-1, 1)).normalized() * random.uniform(2, spd)
        p.max = p.life = random.uniform(.5, 1.1)
        particles.append(p)


def spawn_wave():
    xs = random.sample(range(-8, 9, 3), random.randint(1, 3))
    for x in xs:
        kind = random.random()
        if kind < .35:   # tall pillar
            size = Vec3(2, 9, 2); y = 4.5
        elif kind < .7:  # flying block
            size = Vec3(random.uniform(1.8, 3), random.uniform(1.5, 2.8), random.uniform(1.8, 3)); y = random.uniform(1, 5.5)
        else:            # low wall
            size = Vec3(3, 1.6, 1.6); y = .8 + random.uniform(0, 4)
        col = color.hex(random.choice(["#ff1744", "#ff2bd6", "#ff7a3d"]))
        o = Entity(model="cube", scale=size, position=(x, y, 150), color=color.hex("#3a0a2a"))
        Entity(parent=o, model="wireframe_cube", scale=1.02, color=col)
        o.hit = size
        o.col = col
        obstacles.append(o)
    if random.random() < .75:
        free = [x for x in range(-8, 9, 3) if x not in xs] or [0]
        o = Entity(model="sphere", scale=.9, position=(random.choice(free), random.uniform(1, 5.5), 150),
                   color=color.hex("#ffe94d"))
        Entity(parent=o, model="sphere", scale=1.7, color=color.hex("#ffe94d38"))
        orbs.append(o)


def clear_world():
    for e in obstacles + orbs + particles:
        destroy(e)
    obstacles.clear(); orbs.clear(); particles.clear()


def start():
    global state, dist, bonus, lives, invuln, combo, spawn_t, vx, vy
    clear_world()
    dist, bonus, lives, invuln, combo, spawn_t, vx, vy = 0.0, 0, 3, 0.0, 0, 1.0, 0.0, 0.0
    ship.position = Vec3(0, 2, 0)
    ship.visible = ship_shadow.visible = True
    for t in title_ui + over_ui:
        t.enabled = False
    state = "play"
    music.setVolume(.5)
    play("start")


def game_over():
    global state, best
    state = "over"
    best = max(best, int(dist / 10) + bonus)
    ship.visible = ship_shadow.visible = False
    burst(ship.position, color.hex("#00e5ff"), 40, 14)
    burst(ship.position, color.hex("#ff2bd6"), 40, 14)
    over_ui[1].text = f"score  {int(dist / 10) + bonus}      best  {best}"
    for t in over_ui:
        t.enabled = True
    music.setVolume(.25)
    play("over")


def hit():
    global lives, invuln, shake, combo
    lives -= 1
    combo = 0
    shake = 1.0
    invuln = 1.6
    burst(ship.position, color.hex("#ff7a3d"), 30, 12)
    play("crash")
    if lives <= 0:
        game_over()


def collect(o):
    global bonus, combo, combo_t
    combo = combo + 1 if combo_t > 0 else 1
    combo_t = 1.8
    bonus += 50 * min(combo, 5)
    burst(o.position, color.hex("#ffe94d"), 14, 7)
    play("collect", rate=1 + min(combo, 12) * .06)


def input(key):
    if key == "escape":
        application.quit()
    if state == "title" and key == "space":
        start()
    elif state == "over" and key == "r":
        start()


def update():
    global speed, dist, lives, invuln, shake, trail_t, combo_t, combo, spawn_t, vx, vy
    dt = min(time.dt, .05)

    # speed / difficulty
    if state == "play":
        base = min(28 + dist * .004, 58)
        speed = lerp(speed, base * (1.6 if held_keys["shift"] else 1), 3 * dt)
    elif state == "title":
        speed = 22
    else:
        speed = lerp(speed, 6, 2 * dt)
    camera.fov = lerp(camera.fov, 78 + min(max(speed - 28, 0), 40) * .5, 4 * dt)

    # scroll the world
    for l in grid_lines:
        l.z -= speed * dt
        if l.z < -12:
            l.z += GRID_SPAN
    for s in stars:
        s.z -= speed * dt * .25
        if s.z < -10:
            s.z += 220
    for tw in towers:
        tw.z -= speed * dt
        if tw.z < -25:
            tw.z += TOWER_SPAN
    sun.scale = 110 + math.sin(application.time_scale * 0 + (dist * .02)) * 2

    # particles
    for p in particles[:]:
        p.position += p.vel * dt
        p.life -= dt
        if p.life <= 0:
            particles.remove(p); destroy(p)
        else:
            p.scale = max(p.base * p.life / p.max, .001)

    if state == "play":
        ax = (held_keys["d"] + held_keys["right arrow"]) - (held_keys["a"] + held_keys["left arrow"])
        ay = (held_keys["w"] + held_keys["up arrow"]) - (held_keys["s"] + held_keys["down arrow"])
        vx = lerp(vx, ax * 13, 9 * dt)
        vy = lerp(vy, ay * 9, 9 * dt)
        ship.x = clamp(ship.x + vx * dt, -8, 8)
        ship.y = clamp(ship.y + vy * dt, .8, 6.5)
        ship.rotation_z = lerp(ship.rotation_z, -vx * 2.6, 10 * dt)
        ship.rotation_x = lerp(ship.rotation_x, -vy * 2, 10 * dt)
        glow.scale = .5 + random.uniform(0, .25) + (.3 if held_keys["shift"] else 0)
        ship_shadow.x, ship_shadow.z = ship.x, ship.z
        ship_shadow.scale = max(.8, 2.2 - ship.y * .25)

        dist += speed * dt
        invuln = max(invuln - dt, 0)
        ship.visible = invuln <= 0 or int(invuln * 12) % 2 == 0
        combo_t = max(combo_t - dt, 0)
        if combo_t == 0:
            combo = 0

        trail_t -= dt
        if trail_t <= 0:
            trail_t = .02
            p = Entity(model="cube", position=ship.position + Vec3(random.uniform(-.1, .1), 0, -1.2),
                       color=color.hex(random.choice(["#ffb300", "#ff7a3d", "#ffe94d"])))
            p.base, p.max, p.life = .28, .4, .4
            p.scale = p.base
            p.vel = Vec3(0, 0, -speed * .5)
            particles.append(p)

        spawn_t -= dt * speed / 28
        if spawn_t <= 0:
            spawn_wave()
            spawn_t = random.uniform(.55, 1.1) * max(.55, 1 - dist / 12000)

        for o in obstacles[:]:
            o.z -= speed * dt
            if o.z < -15:
                obstacles.remove(o); destroy(o); continue
            if (invuln <= 0 and abs(o.z) < o.hit.z / 2 + .8 and abs(o.x - ship.x) < o.hit.x / 2 + .7
                    and abs(o.y - ship.y) < o.hit.y / 2 + .3):
                hit()
                if state != "play":
                    break
        for o in orbs[:]:
            o.z -= speed * dt
            o.children[0].scale = 1.7 + math.sin(o.z * .3) * .25
            if o.z < -15:
                orbs.remove(o); destroy(o); continue
            if abs(o.z) < 1.6 and abs(o.x - ship.x) < 1.4 and abs(o.y - ship.y) < 1.4:
                orbs.remove(o); collect(o); destroy(o)
    else:
        for o in obstacles + orbs:
            o.z -= speed * dt

    # camera
    shake = max(shake - 2 * dt, 0)
    camera.position = Vec3(ship.x * .5 + random.uniform(-1, 1) * shake * .5,
                           ship.y * .25 + 3.6 + random.uniform(-1, 1) * shake * .5, -9.5)
    camera.rotation_x = 8
    camera.rotation_z = -vx * .12 if state == "play" else 0

    # HUD
    on = state == "play"
    hud_score.text = f"SCORE {int(dist / 10) + bonus}" if on else ""
    hud_best.text = f"BEST {best}" if on else ""
    hud_lives.text = ("SHIELD " + "# " * lives) if on else ""
    hud_combo.text = f"COMBO x{min(combo, 5)}" if on and combo > 1 else ""


app.run()
