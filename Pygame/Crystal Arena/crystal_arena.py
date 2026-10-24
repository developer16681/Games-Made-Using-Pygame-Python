"""
CRYSTAL ARENA - a 3D first-person arena shooter in Python (Ursina engine)

Install:  pip install ursina numpy
Run:      python crystal_arena.py

Controls: WASD move | SPACE jump | MOUSE look | LEFT CLICK shoot | R restart | ESC quit
Goal:     Shoot the red Gloom Orbs, grab golden crystals (+score, +health). Survive!

All music and sound effects are synthesized in code at startup (no asset files needed).
"""
import math, random, wave
import numpy as np
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.shaders import lit_with_shadows_shader, unlit_shader

SHADOWS = True  # set False if your GPU struggles

app = Ursina(title='Crystal Arena', borderless=False)
window.fps_counter.enabled = True
window.exit_button.visible = False

# --------------------------------------------------------------------------
#  PROCEDURAL AUDIO  (music + sfx written to .wav files, then loaded)
# --------------------------------------------------------------------------
SR = 22050


def save_wav(name, data):
    data = np.clip(data, -1, 1)
    pcm = (data * 32767).astype(np.int16)
    with wave.open(str(application.asset_folder / name), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def midi(n):
    return 440 * 2 ** ((n - 69) / 12)


def note(freq, dur, vol=.3, decay=5, harmonics=(1, .5, .25)):
    t = np.linspace(0, dur, int(SR * dur), False)
    s = sum(h * np.sin(2 * np.pi * freq * (i + 1) * t) for i, h in enumerate(harmonics))
    env = np.exp(-decay * t / dur) * np.minimum(1, t * 200)
    return s * env * vol


def make_audio():
    rng = np.random.default_rng(1)
    # --- laser shot: falling square-ish chirp
    n = int(SR * .2); t = np.linspace(0, .2, n, False)
    f = np.linspace(1100, 140, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    save_wav('shoot.wav', (np.sign(np.sin(ph)) * .25 + np.sin(ph) * .2) * np.exp(-9 * t))
    # --- enemy hit: short noisy tick
    n = int(SR * .12); t = np.linspace(0, .12, n, False)
    save_wav('hit.wav', (rng.uniform(-1, 1, n) * .4 + np.sin(2 * np.pi * 300 * t) * .3) * np.exp(-25 * t))
    # --- explosion: lowpassed noise + falling rumble
    n = int(SR * .6); t = np.linspace(0, .6, n, False)
    noise = np.convolve(rng.uniform(-1, 1, n), np.ones(12) / 12, 'same')
    rumble = np.sin(2 * np.pi * np.cumsum(np.linspace(180, 35, n)) / SR)
    save_wav('boom.wav', (noise * .8 + rumble * .5) * np.exp(-5 * t))
    # --- pickup: rising arpeggio
    seq = [midi(79), midi(83), midi(86), midi(91)]
    save_wav('pickup.wav', np.concatenate([note(fr, .09, .35, 3, (1, .3)) for fr in seq]))
    # --- player hurt: low thud
    n = int(SR * .35); t = np.linspace(0, .35, n, False)
    save_wav('hurt.wav', (np.sin(2 * np.pi * 75 * t) * .7 + rng.uniform(-1, 1, n) * .25) * np.exp(-9 * t))
    # --- game over: sad descending notes
    seq = [midi(69), midi(65), midi(62), midi(57)]
    save_wav('gameover.wav', np.concatenate([note(fr, .35, .35, 3) for fr in seq]))
    # --- music loop: Am - F - C - G, arpeggio + bass + pad
    bpm = 110; eighth = 60 / bpm / 2
    chords = [[57, 60, 64], [53, 57, 60], [60, 64, 67], [55, 59, 62]]
    pattern = [0, 1, 2, 3, 2, 1, 2, 1]
    tracks = []
    for ch in chords:
        notes = ch + [ch[0] + 12]
        arp = np.concatenate([note(midi(notes[p] + 12), eighth, .22, 4) for p in pattern])
        bass = np.concatenate([note(midi(ch[0] - 12), eighth * 2, .45, 2.5, (1, .4)) for _ in range(4)])
        L = len(arp)
        t = np.linspace(0, L / SR, L, False)
        pad = sum(np.sin(2 * np.pi * midi(m) * t) for m in ch) * .05 * (.6 + .4 * np.sin(np.pi * t / t[-1]))
        m = min(L, len(bass))
        tracks.append(arp[:m] + bass[:m] + pad[:m])
    music = np.concatenate(tracks)
    save_wav('music.wav', music / np.max(np.abs(music)) * .8)


make_audio()
music = Audio('music.wav', loop=True, autoplay=True, volume=.45)


def sfx(name, vol=.7, pitch=1):
    Audio(name, autoplay=True, auto_destroy=True, volume=vol, pitch=pitch)


# --------------------------------------------------------------------------
#  WORLD
# --------------------------------------------------------------------------
Entity.default_shader = lit_with_shadows_shader
random.seed(7)
ARENA = 38

Sky(texture='sky_sunset')
scene.fog_color = color.rgb(60, 30, 80)
scene.fog_density = (30, 110)

sun = DirectionalLight(shadows=SHADOWS, shadow_map_resolution=Vec2(2048, 2048))
sun.look_at(Vec3(1, -1.4, -.6))
AmbientLight(color=color.rgba(110, 90, 140, .6))

ground = Entity(model='plane', scale=ARENA * 2, texture='white_cube', texture_scale=(ARENA, ARENA),
                color=color.rgb(70, 60, 95), collider='box')

# glowing grid lines & border
for i in range(-ARENA, ARENA + 1, 19):
    Entity(model='cube', scale=(ARENA * 2, .02, .12), y=.02, z=i, color=color.cyan, shader=unlit_shader)
    Entity(model='cube', scale=(.12, .02, ARENA * 2), y=.02, x=i, color=color.magenta, shader=unlit_shader)

for (pos, sc) in [((0, 4, ARENA), (ARENA * 2, 8, 2)), ((0, 4, -ARENA), (ARENA * 2, 8, 2)),
                  ((ARENA, 4, 0), (2, 8, ARENA * 2)), ((-ARENA, 4, 0), (2, 8, ARENA * 2))]:
    Entity(model='cube', position=pos, scale=sc, color=color.rgb(45, 40, 75), collider='box')
    Entity(model='cube', position=(pos[0], 8.05, pos[2]), scale=(sc[0], .3, sc[2]) , color=color.cyan, shader=unlit_shader)

# pillars with neon tops
for _ in range(16):
    x, z = random.uniform(-30, 30), random.uniform(-30, 30)
    if abs(x) < 7 and abs(z) < 7:
        continue
    h = random.uniform(3, 9)
    c = random.choice([color.rgb(90, 70, 140), color.rgb(60, 90, 130), color.rgb(120, 60, 110)])
    Entity(model='cube', position=(x, h / 2, z), scale=(2.5, h, 2.5), color=c, collider='box')
    Entity(model='cube', position=(x, h + .1, z), scale=(2.7, .25, 2.7),
           color=random.choice([color.cyan, color.magenta, color.lime]), shader=unlit_shader)

# --------------------------------------------------------------------------
#  PLAYER + HUD
# --------------------------------------------------------------------------
player = FirstPersonController(position=(0, 2, 0), speed=9, jump_height=2.2)
player.cursor.visible = False
gun = Entity(parent=camera, model='cube', scale=(.12, .12, .7), position=(.45, -.32, .8),
             color=color.rgb(40, 40, 55), shader=unlit_shader)
Entity(parent=gun, model='cube', scale=(1.05, .3, .3), z=.45, color=color.cyan, shader=unlit_shader)
flash = Entity(parent=gun, model='sphere', scale=(1.5, 1.5, .8), z=.8, color=color.yellow,
               shader=unlit_shader, enabled=False)

Entity(parent=camera.ui, model='circle', scale=.007, color=color.white)
hurt_overlay = Entity(parent=camera.ui, model='quad', scale=(2, 1), color=color.rgba(255, 0, 0, 0))
hp_bg = Entity(parent=camera.ui, model='quad', origin=(-.5, 0), position=(-.85, .44), scale=(.3, .028),
               color=color.rgba(0, 0, 0, 160))
hp_bar = Entity(parent=camera.ui, model='quad', origin=(-.5, 0), position=(-.85, .44), scale=(.3, .028),
                color=color.lime)
score_text = Text('SCORE 0', position=(-.85, .49), scale=1.4, color=color.yellow)
msg_text = Text('', origin=(0, 0), scale=2.5, color=color.white, y=.1)
help_text = Text('WASD move | SPACE jump | CLICK shoot', position=(-.85, -.45), scale=.9, color=color.light_gray)

G = dict(hp=100, score=0, over=False, spawn_t=0, last_shot=0)
enemies, crystals = [], []


# --------------------------------------------------------------------------
#  ENTITIES
# --------------------------------------------------------------------------
def burst(pos, col, n=14, speed=4):
    for _ in range(n):
        p = Entity(model='cube', position=pos, scale=.15, color=col, shader=unlit_shader)
        d = Vec3(random.uniform(-1, 1), random.uniform(0, 1.2), random.uniform(-1, 1)) * speed
        p.animate_position(pos + d, duration=.5, curve=curve.out_expo)
        p.animate_scale(0, duration=.5)
        destroy(p, delay=.55)


class Crystal(Entity):
    def __init__(self, pos):
        super().__init__(model='diamond', position=pos, scale=.8, color=color.gold, shader=unlit_shader)
        self.glow = Entity(parent=self, model='sphere', scale=1.8, color=color.rgba(255, 220, 80, 40),
                           shader=unlit_shader)
        self.base_y = pos.y
        crystals.append(self)

    def update(self):
        self.rotation_y += 120 * time.dt
        self.y = self.base_y + math.sin(time.time() * 2 + self.x) * .25
        if not G['over'] and distance(self, player) < 2.2:
            G['score'] += 10
            G['hp'] = min(100, G['hp'] + 8)
            sfx('pickup.wav', .6)
            burst(self.position, color.gold, 10, 3)
            crystals.remove(self)
            destroy(self)


class Enemy(Entity):
    def __init__(self, pos):
        super().__init__(model='sphere', position=pos, scale=1.6, color=color.rgb(200, 30, 50),
                         collider='sphere')
        self.hp = 3
        self.phase = random.uniform(0, 6)
        self.speed = min(3 + G['score'] / 120, 7.5)
        self.last_hit = 0
        self.eye = Entity(parent=self, model='sphere', scale=.45, position=(0, .15, .42),
                          color=color.white, shader=unlit_shader)
        Entity(parent=self.eye, model='sphere', scale=.5, z=.4, color=color.black, shader=unlit_shader)
        self.glow = Entity(parent=self, model='sphere', scale=1.25, color=color.rgba(255, 40, 60, 40),
                           shader=unlit_shader)
        enemies.append(self)

    def update(self):
        if G['over']:
            return
        d = player.position - self.position
        self.rotation_y = math.degrees(math.atan2(d.x, d.z))
        flat = Vec3(d.x, 0, d.z)
        if flat.length() > 1.6:
            self.position += flat.normalized() * self.speed * time.dt
        self.y = 1.4 + math.sin(time.time() * 3 + self.phase) * .35
        if distance(self, player) < 2.2 and time.time() - self.last_hit > 1:
            self.last_hit = time.time()
            hurt(15)

    def damage(self):
        self.hp -= 1
        self.animate_scale(1.9, .05)
        self.animate_scale(1.6, .1, delay=.05)
        if self.hp <= 0:
            sfx('boom.wav', .8)
            burst(self.position, color.orange, 26, 6)
            G['score'] += 5
            if random.random() < .35:
                Crystal(Vec3(self.x, 1.2, self.z))
            enemies.remove(self)
            destroy(self)
        else:
            sfx('hit.wav', .6, random.uniform(.9, 1.2))


def hurt(amount):
    G['hp'] -= amount
    sfx('hurt.wav', .9)
    hurt_overlay.color = color.rgba(255, 0, 0, 120)
    hurt_overlay.animate_color(color.rgba(255, 0, 0, 0), duration=.4)
    camera.shake(duration=.2, magnitude=1)
    if G['hp'] <= 0:
        game_over()


def spawn_enemy():
    a = random.uniform(0, 2 * math.pi)
    r = random.uniform(22, 32)
    pos = player.position + Vec3(math.cos(a) * r, 0, math.sin(a) * r)
    pos.x = clamp(pos.x, -ARENA + 3, ARENA - 3)
    pos.z = clamp(pos.z, -ARENA + 3, ARENA - 3)
    pos.y = 1.5
    Enemy(pos)
    burst(pos, color.red, 8, 2)


def spawn_crystal():
    Crystal(Vec3(random.uniform(-32, 32), 1.2, random.uniform(-32, 32)))


def game_over():
    G['over'] = True
    player.enabled = False
    music.volume = .15
    sfx('gameover.wav', .8)
    msg_text.text = f'GAME OVER\nScore: {G["score"]}\n\nPress R to restart'
    mouse.locked = False


def restart():
    for e in enemies[:] + crystals[:]:
        destroy(e)
    enemies.clear(); crystals.clear()
    G.update(hp=100, score=0, over=False, spawn_t=0)
    msg_text.text = ''
    music.volume = .45
    player.position = Vec3(0, 2, 0)
    player.enabled = True
    mouse.locked = True
    for _ in range(5):
        spawn_crystal()


def shoot():
    if G['over'] or time.time() - G['last_shot'] < .18:
        return
    G['last_shot'] = time.time()
    sfx('shoot.wav', .5, random.uniform(.95, 1.1))
    flash.enabled = True
    invoke(setattr, flash, 'enabled', False, delay=.05)
    gun.animate_z(.65, .04)
    gun.animate_z(.8, .08, delay=.04)
    hit = raycast(camera.world_position, camera.forward, distance=90, ignore=[player])
    if hit.hit:
        burst(hit.world_point, color.yellow, 5, 1.2)
        if isinstance(hit.entity, Enemy):
            hit.entity.damage()


# --------------------------------------------------------------------------
#  MAIN LOOP
# --------------------------------------------------------------------------
def update():
    hp_bar.scale_x = .3 * max(0, G['hp']) / 100
    hp_bar.color = color.lime if G['hp'] > 50 else (color.orange if G['hp'] > 25 else color.red)
    score_text.text = f'SCORE {G["score"]}'
    if G['over']:
        return
    if held_keys['left mouse']:
        shoot()
    if player.y < -10:
        player.position = Vec3(0, 3, 0)
    G['spawn_t'] += time.dt
    interval = max(1.0, 3.5 - G['score'] / 80)
    if G['spawn_t'] > interval and len(enemies) < 4 + G['score'] // 40:
        G['spawn_t'] = 0
        spawn_enemy()
    while len(crystals) < 4:
        spawn_crystal()


def input(key):
    if key == 'left mouse down':
        shoot()
    if key == 'r' and G['over']:
        restart()
    if key == 'escape':
        application.quit()


for _ in range(5):
    spawn_crystal()
spawn_enemy()
app.run()
