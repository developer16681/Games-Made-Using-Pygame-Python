from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random, math, wave, struct, os

SR = 44100
def C(r, g, b, a=1.0):
    """Version-proof colour helper (0-1 floats)."""
    return color.Color(r, g, b, a)

# ---------------------------------------------------------------- Sound synthesis
def synth(name, duration, fn):
    if os.path.exists(name):
        return
    data = []
    for i in range(int(SR * duration)):
        t = i / SR
        data.append(max(-32768, min(32767, int(fn(t, t / duration)))))
    with wave.open(name, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(struct.pack('<%dh' % len(data), *data))

def tone(f, t): return math.sin(2 * math.pi * f * t)

def create_sound_assets():
    synth('coin.wav', .22, lambda t, p: 18000 * (1 - p) * tone(987.77 if t < .09 else 1318.51, t))
    synth('jump.wav', .2, lambda t, p: 14000 * (1 - p) * tone(180 + p * 320, t))
    synth('shoot_pistol.wav', .16, lambda t, p: 22000 * (1 - p) * tone(950 * math.exp(-20 * t) + 120, t))
    synth('shoot_shotgun.wav', .38, lambda t, p: 28000 * (1 - p) * (tone(240 * math.exp(-12 * t) + 40, t) * .55 + (random.random() * 2 - 1) * .45))
    synth('shoot_smg.wav', .08, lambda t, p: 19000 * (1 - p) * tone(1400 * math.exp(-35 * t) + 200, t))
    synth('switch.wav', .06, lambda t, p: 12000 * tone(1800 if t < .03 else 2400, t))
    synth('reload.wav', .3, lambda t, p: 15000 * (1 - p) * tone(500 if t < .15 else 800, t))
    synth('hit.wav', .05, lambda t, p: 14000 * (1 - p) * tone(2200, t))
    synth('hurt.wav', .28, lambda t, p: 24000 * (1 - p) * (tone(90, t) * .6 + (random.random() * 2 - 1) * .4))
    synth('pickup.wav', .25, lambda t, p: 15000 * (1 - p) * tone(660 if t < .08 else 880 if t < .16 else 1175, t))
    synth('wave.wav', .6, lambda t, p: 16000 * (1 - p) * tone(220 if t < .2 else 330 if t < .4 else 440, t))
    # seamless 8s ambient pad: every frequency fits a whole number of cycles in the loop
    D = 8.0
    f = lambda hz: round(hz * D) / D
    synth('bgm.wav', D, lambda t, p: 5500 * (0.75 + 0.25 * tone(1 / D * 2, t)) *
          (tone(f(110), t) + .6 * tone(f(164.8), t) + .4 * tone(f(220), t) + .2 * tone(f(329.6), t)) / 2.2)

create_sound_assets()

# ---------------------------------------------------------------- Engine setup
app = Ursina()
cylinder_mesh, cone_mesh = Cylinder(resolution=12), Cone(resolution=12)
window.title = "3D Open Forest - Survive the Guardians"
window.borderless = False
window.fps_counter.enabled = True
window.exit_button.visible = False

sky_dome = Sky(color=color.hex('#78b7e3'))
scene.fog_density = 0.005
scene.fog_color = color.hex('#9ec5d9')
camera.clip_plane_far = 350

sun_light = DirectionalLight(shadows=True)
ambient_light = AmbientLight(color=C(.43, .47, .51, .82))
sun_orb = Entity(model='sphere', scale=16, color=color.hex('#FFF68F'), unlit=True)
Entity(parent=sun_orb, model='sphere', scale=1.35, color=C(1, .9, .47, .27), unlit=True)

Audio('bgm.wav', loop=True, autoplay=True, volume=.25)
def sfx(name, vol): return Audio(name, autoplay=False, loop=False, volume=vol)
coin_sfx, jump_sfx, switch_sfx, reload_sfx = sfx('coin.wav', .7), sfx('jump.wav', .6), sfx('switch.wav', .6), sfx('reload.wav', .7)
hit_sfx, hurt_sfx, pickup_sfx, wave_sfx = sfx('hit.wav', .5), sfx('hurt.wav', .9), sfx('pickup.wav', .7), sfx('wave.wav', .8)

# ---------------------------------------------------------------- Terrain
WALL, LIMIT = 140, 130
ground = Entity(model='plane', scale=(300, 1, 300), color=color.hex('#3b6634'), texture='grass', texture_scale=(150, 150), collider='box')
for sc, pos in [((WALL*2, 8, 3), (0, 4, WALL)), ((WALL*2, 8, 3), (0, 4, -WALL)), ((3, 8, WALL*2), (WALL, 4, 0)), ((3, 8, WALL*2), (-WALL, 4, 0))]:
    Entity(model='cube', scale=sc, position=pos, color=color.hex('#3e4242'), collider='box')

HAMLETS = [(-25, 25, 20), (-35, 12, -35), (-18, -30, 95), (60, 50, -15), (75, 40, 110), (-70, -60, 45), (40, -80, -70), (-85, 75, 130)]
def rand_xz(limit, avoid=(), clear=7):
    while True:
        x, z = random.uniform(-limit, limit), random.uniform(-limit, limit)
        if math.hypot(x, z) < clear: continue
        if any(math.hypot(x - ax, z - az) < 9 for ax, az in avoid): continue
        return x, z

# ---------------------------------------------------------------- Scenery
clouds = []
class Cloud(Entity):
    def __init__(self, position):
        super().__init__(position=position)
        self.drift = random.uniform(1.5, 3.5)
        for ox, oy, oz, sx, sy, sz in [(0,0,0,7,3.5,6), (-4,-.6,.6,5,2.6,4.5), (3.8,-.5,-.5,5.2,2.8,4.8), (1.5,.8,1.8,4.5,3,4.2), (-1.8,.6,-1.5,4.2,2.5,4)]:
            Entity(parent=self, model='sphere', position=(ox, oy, oz), scale=(sx, sy, sz), color=C(.96, .98, 1, .84), unlit=True)
        clouds.append(self)
    def update_drift(self):
        self.x += self.drift * time.dt
        if self.x > 170:
            self.x, self.z, self.y = -170, random.uniform(-150, 150), random.uniform(40, 60)
for _ in range(32):
    Cloud((random.uniform(-160, 160), random.uniform(40, 60), random.uniform(-160, 160)))

class PineTree(Entity):
    def __init__(self, position):
        super().__init__(position=position)
        Entity(parent=self, model=cylinder_mesh, color=color.hex('#4a2f1c'), scale=(.8, 3.8, .8), y=1.9, collider='box')
        for oy, s, c in [(3.2, 4, '#1d4722'), (4.6, 3.1, '#265c2c'), (5.8, 2.1, '#317838')]:
            Entity(parent=self, model=cone_mesh, color=color.hex(c), scale=(s, 2.5, s), y=oy)

class BroadleafTree(Entity):
    def __init__(self, position):
        super().__init__(position=position)
        Entity(parent=self, model=cylinder_mesh, color=color.hex('#543928'), scale=(.9, 3, .9), y=1.5, collider='box')
        Entity(parent=self, model='sphere', scale=(3.4, 2.8, 3.4), y=4, color=color.hex('#2e6e2e'))
        Entity(parent=self, model='sphere', scale=(2.6, 2.2, 2.6), position=(.8, 4.8, -.4), color=color.hex('#3c8a3c'))

class House(Entity):
    def __init__(self, position, rotation_y=0):
        super().__init__(position=position, rotation_y=rotation_y)
        Entity(parent=self, model='cube', scale=(7, 3.5, 5.5), y=1.75, color=color.hex('#6e4c30'), collider='box')
        Entity(parent=self, model=cone_mesh, scale=(7.8, 2.8, 6.2), y=4.6, rotation_y=45, color=color.hex('#3e2515'))
        Entity(parent=self, model='cube', scale=(.9, 4.2, .9), position=(2, 3.4, 1.4), color=color.hex('#5c5c5c'), collider='box')
        Entity(parent=self, model='cube', scale=(1.2, 2.1, .2), position=(0, 1.05, 2.76), color=color.hex('#2e190e'))
        for wx in (-2, 2):
            Entity(parent=self, model='cube', scale=(1.1, 1.1, .1), position=(wx, 1.8, 2.76), color=color.hex('#f4d06f'), unlit=True)

class AncientRuin(Entity):
    def __init__(self, position, rotation_y=0):
        super().__init__(position=position, rotation_y=rotation_y)
        stone = color.hex('#6e7271')
        Entity(parent=self, model='cube', scale=(4, .8, 2), y=.4, color=color.hex('#52574e'), collider='box')
        for px in (-1.3, 1.3):
            Entity(parent=self, model=cylinder_mesh, scale=(.7, 4, .7), position=(px, 2.4, 0), color=stone, collider='box')
        Entity(parent=self, model='cube', scale=(4.2, .8, 1.4), y=4.8, color=stone, collider='box')

class Altar(Entity):
    def __init__(self, position):
        super().__init__(position=position)
        Entity(parent=self, model=cylinder_mesh, scale=(2.2, .4, 2.2), y=.2, color=color.hex('#474747'), collider='box')
        Entity(parent=self, model=cylinder_mesh, scale=(1.4, .8, 1.4), y=.8, color=color.hex('#5c5c5c'), collider='box')

# ---------------------------------------------------------------- Animals
active_animals = []
class Deer(Entity):
    def __init__(self, position):
        super().__init__(position=position, name='animal')
        hide, dark = color.hex('#8b5a2b'), color.hex('#5c3a1e')
        Entity(parent=self, model='cube', scale=(.8, .9, 1.8), y=1.2, color=hide, collider='box')
        Entity(parent=self, model='cube', scale=(.4, .9, .5), position=(0, 1.8, .8), rotation_x=-25, color=hide)
        Entity(parent=self, model='cube', scale=(.45, .45, .7), position=(0, 2.2, 1.15), color=hide)
        for sx, rz in ((-.25, -20), (.25, 20)):
            Entity(parent=self, model='cube', scale=(.08, .6, .08), position=(sx, 2.6, 1.05), rotation_z=rz, color=color.hex('#e8dcc4'))
        for lx, lz in ((-.3, .7), (.3, .7), (-.3, -.7), (.3, -.7)):
            Entity(parent=self, model=cylinder_mesh, scale=(.14, 1.1, .14), position=(lx, .55, lz), color=dark)
        self.move_timer, self.is_walking, self.speed = random.uniform(1, 3), False, 2.2
        active_animals.append(self)
    def update_ai(self):
        d = math.hypot(self.x - player.x, self.z - player.z)
        if d > 90: return
        self.move_timer -= time.dt
        if self.move_timer <= 0:
            self.is_walking = not self.is_walking
            self.move_timer = random.uniform(2, 5)
            if self.is_walking: self.rotation_y += random.uniform(-60, 60)
        if d < 8:
            self.rotation_y = math.degrees(math.atan2(self.x - player.x, self.z - player.z))
            self.position += self.forward * 6 * time.dt
        elif self.is_walking:
            self.position += self.forward * self.speed * time.dt
        self.x, self.z = clamp(self.x, -135, 135), clamp(self.z, -135, 135)

class Rabbit(Entity):
    def __init__(self, position):
        super().__init__(position=position, name='animal')
        fur = color.hex('#e0d5c1')
        Entity(parent=self, model='sphere', scale=(.4, .35, .55), y=.22, color=fur, collider='box')
        Entity(parent=self, model='sphere', scale=(.28, .28, .32), position=(0, .4, .24), color=fur)
        for ex, rz in ((-.08, -12), (.08, 12)):
            Entity(parent=self, model='cube', scale=(.06, .32, .08), position=(ex, .65, .2), rotation_z=rz, color=fur)
        self.hop_timer = random.uniform(.5, 2)
        active_animals.append(self)
    def update_ai(self):
        if math.hypot(self.x - player.x, self.z - player.z) > 90: return
        self.hop_timer -= time.dt
        if self.hop_timer <= 0:
            self.hop_timer = random.uniform(1.2, 3)
            self.rotation_y = random.uniform(0, 360)
            self.animate_position(self.position + self.forward * 1.6 + Vec3(0, .4, 0), duration=.2, curve=curve.out_quad)
            invoke(lambda: self.animate_position(Vec3(self.x, 0, self.z), duration=.2, curve=curve.in_quad) if self else None, delay=.2)
        self.x, self.z = clamp(self.x, -135, 135), clamp(self.z, -135, 135)

# ---------------------------------------------------------------- Game state
MAX_HP = 100
player_hp, score = MAX_HP, 0
wave_no, wave_active, wave_cooldown = 0, False, 3.0
paused = game_over = False
msg_timer = hit_timer = 0.0
elapsed = 0.9           # game clock for the day/night cycle (starts mid-morning)
reload_id = 0           # invalidates in-flight reloads on weapon switch / restart

# ---------------------------------------------------------------- Guardians
active_guardians = []
class AggressiveGuardian(Entity):
    def __init__(self, position, wave_level=1):
        super().__init__(position=position, name='guardian')
        self.max_health = self.health = 100 + 15 * (wave_level - 1)
        self.speed = min(3.2 + .2 * wave_level, 6.5)
        self.damage = 8 + 2 * wave_level
        self.atk_cd, self.dead = 0.0, False
        armor, skin, accent = color.hex('#8b2626'), color.hex('#c2b280'), color.hex('#3b1a1a')
        Entity(parent=self, model='cube', scale=(.8, 1.2, .5), y=1.6, color=armor, collider='box')
        Entity(parent=self, model='sphere', scale=.5, y=2.4, color=skin, collider='box')   # head (headshots!)
        Entity(parent=self, model='cube', scale=(.6, .1, .6), y=2.6, color=accent)
        for lx in (-.25, .25):
            Entity(parent=self, model=cylinder_mesh, scale=(.25, 1, .25), position=(lx, .5, 0), color=accent, collider='box')
        for ax, rz in ((-.55, 15), (.55, -15)):
            Entity(parent=self, model=cylinder_mesh, scale=(.2, 1.1, .2), position=(ax, 1.6, 0), rotation_z=rz, color=armor)
        self.bar_bg = Entity(parent=self, model='quad', scale=(1.2, .14), y=3.0, color=color.black, billboard=True)
        self.hp_bar = Entity(parent=self.bar_bg, model='quad', scale=(.96, .7), color=color.red, origin_x=-.5, x=-.48)
        active_guardians.append(self)

    def take_damage(self, dmg):
        if self.dead: return False
        self.health -= dmg
        self.hp_bar.scale_x = max(0, self.health / self.max_health) * .96
        if self.health <= 0:
            self.dead = True
            active_guardians.remove(self)
            r = random.random()
            if r < .35: spawn_pickup(self.position, 'health')
            elif r < .75: spawn_pickup(self.position, 'ammo')
            destroy(self)
            return True
        return False

    def update_ai(self):
        self.atk_cd -= time.dt
        dist = math.hypot(self.x - player.x, self.z - player.z)
        if dist < 60:
            self.look_at_2d(player.position, 'y')
            if dist > 2.3:
                self.position += self.forward * self.speed * time.dt
            elif self.atk_cd <= 0:
                self.atk_cd = 1.0
                damage_player(self.damage)
        self.x, self.z = clamp(self.x, -135, 135), clamp(self.z, -135, 135)

# ---------------------------------------------------------------- World population
for hx, hz, hr in HAMLETS:
    House(position=(hx, 0, hz), rotation_y=hr)
house_pts = [(h[0], h[1]) for h in HAMLETS]
for _ in range(120): PineTree(position=(*[rand_xz(LIMIT, house_pts)][0][:1], 0, rand_xz(LIMIT, house_pts)[1]))
for _ in range(80):
    x, z = rand_xz(LIMIT, house_pts); BroadleafTree(position=(x, 0, z))
for _ in range(18):
    x, z = rand_xz(125, clear=8); Deer(position=(x, 0, z))
for _ in range(26):
    x, z = rand_xz(125); Rabbit(position=(x, 0, z))
for _ in range(14):
    x, z = rand_xz(125, house_pts, 10); AncientRuin(position=(x, 0, z), rotation_y=random.randint(0, 360))

# ---------------------------------------------------------------- Player & viewmodel
player = FirstPersonController(speed=11, jump_height=1.6, origin_y=-.5, position=(0, 2, 0))
player.cursor.color = C(1, .24, .24, .8)
player.cursor.scale = .015

gun_rig = Entity(parent=camera, position=(.42, -.32, .75), rotation=(0, -5, 0))
default_rig_pos = gun_rig.position
Entity(parent=gun_rig, model='cube', position=(.08, -.15, -.35), scale=(.14, .16, .8), rotation=(15, -5, 0), color=color.hex('#d69f7e'))

def box(p, pos, sc, col, rot=(0, 0, 0), m='cube'):
    Entity(parent=p, model=m, position=pos, scale=sc, rotation=rot, color=color.hex(col) if isinstance(col, str) else col)

pistol_root = Entity(parent=gun_rig)
box(pistol_root, (0, 0, 0), (.1, .14, .45), '#22252a')
box(pistol_root, (0, .03, .35), (.06, .35, .06), '#101214', (90, 0, 0), cylinder_mesh)
box(pistol_root, (0, .07, .05), (.04, .03, .3), color.cyan)
box(pistol_root, (0, -.12, -.1), (.08, .22, .1), '#353a40', (-20, 0, 0))

shotgun_root = Entity(parent=gun_rig, enabled=False)
box(shotgun_root, (0, 0, -.05), (.14, .16, .5), '#282828')
for bx in (-.04, .04):
    box(shotgun_root, (bx, .05, .45), (.065, .65, .065), '#1a1a1a', (90, 0, 0), cylinder_mesh)
box(shotgun_root, (0, -.02, .35), (.12, .1, .3), '#8B4513')
box(shotgun_root, (0, -.16, -.2), (.1, .26, .12), '#8B4513', (-25, 0, 0))

smg_root = Entity(parent=gun_rig, enabled=False)
box(smg_root, (0, 0, 0), (.11, .18, .42), '#1f2326')
box(smg_root, (0, .04, .38), (.05, .4, .05), '#393e46', (90, 0, 0), cylinder_mesh)
box(smg_root, (0, -.25, .06), (.06, .35, .12), '#0f1112', (15, 0, 0))
box(smg_root, (0, .11, -.05), (.04, .05, .22), '#00adb5')
box(smg_root, (0, -.15, .25), (.04, .18, .04), '#1f2326', m=cylinder_mesh)

muzzle_flash = Entity(parent=gun_rig, model='sphere', scale=.18, enabled=False)
INF = math.inf
weapons = [
    dict(name='Plasma Pistol', root=pistol_root, sfx=sfx('shoot_pistol.wav', .8), cooldown=.25, recoil_pos=Vec3(0, .04, -.15), recoil_rot=Vec3(-8, -5, 4),
         flash_pos=Vec3(0, .03, .6), flash_color=color.cyan, pellets=1, spread=0, damage=34, mag_size=12, current_ammo=12, reserve=INF, reload_time=1.1, automatic=False),
    dict(name='Boomstick Shotgun', root=shotgun_root, sfx=sfx('shoot_shotgun.wav', .9), cooldown=.85, recoil_pos=Vec3(0, .1, -.32), recoil_rot=Vec3(-18, -6, 7),
         flash_pos=Vec3(0, .05, .82), flash_color=color.orange, pellets=8, spread=.06, damage=15, mag_size=6, current_ammo=6, reserve=24, reload_time=1.6, automatic=False),
    dict(name='Rapid SMG', root=smg_root, sfx=sfx('shoot_smg.wav', .7), cooldown=.09, recoil_pos=Vec3(0, .02, -.08), recoil_rot=Vec3(-3, -2, 2),
         flash_pos=Vec3(0, .04, .62), flash_color=color.yellow, pellets=1, spread=.018, damage=16, mag_size=30, current_ammo=30, reserve=90, reload_time=1.3, automatic=True),
]
START_RESERVE = [w['reserve'] for w in weapons]
cur_idx, time_since_shot, is_reloading = 0, 0.0, False

# ---------------------------------------------------------------- HUD
Entity(parent=camera.ui, model='quad', scale=(.32, .08), position=(-.68, .43), color=C(0, 0, 0, .55))
score_text = Text(parent=camera.ui, text='Gems: 0', position=(-.82, .45), scale=1.4, color=color.gold)
wave_text = Text(parent=camera.ui, text='', origin=(0, 0), position=(0, .47), scale=1.3, color=color.white)
Entity(parent=camera.ui, model='quad', scale=(.42, .08), position=(.64, -.43), color=C(0, 0, 0, .63))
weapon_text = Text(parent=camera.ui, text='', position=(.45, -.41), scale=1.1, color=color.cyan)
hp_bg = Entity(parent=camera.ui, model='quad', scale=(.4, .035), position=(-.55, -.45), color=C(0, 0, 0, .7))
hp_fill = Entity(parent=hp_bg, model='quad', origin_x=-.5, x=-.5, z=-.1, color=color.red)
hp_text = Text(parent=camera.ui, text='', position=(-.74, -.425), scale=1, color=color.white)
msg_text = Text(parent=camera.ui, text='', origin=(0, 0), position=(0, .28), scale=2.2, color=color.gold, enabled=False)
hitmarker = Text(parent=camera.ui, text='x', origin=(0, 0), scale=2, color=color.white, enabled=False)
damage_overlay = Entity(parent=camera.ui, model='quad', scale=(2, 1), color=C(1, 0, 0, 0), z=1)

# radar
RADAR_C, RADAR_R, RADAR_RANGE = Vec2(.72, .33), .13, 60
Entity(parent=camera.ui, model='quad', scale=RADAR_R * 2, position=RADAR_C, color=C(0, 0, 0, .5))
Entity(parent=camera.ui, model='quad', scale=.01, position=RADAR_C, color=color.white, z=-.2)
radar_dots = [Entity(parent=camera.ui, model='quad', scale=.009, enabled=False, z=-.1) for _ in range(70)]

def update_radar():
    yaw = math.radians(player.rotation_y)
    cs, sn = math.cos(yaw), math.sin(yaw)
    targets = [(g.position, color.red) for g in active_guardians] + [(c.position, color.gold) for c in active_coins]
    for i, dot in enumerate(radar_dots):
        if i >= len(targets):
            dot.enabled = False; continue
        pos, col = targets[i]
        rx, rz = pos.x - player.x, pos.z - player.z
        lx, lz = rx * cs - rz * sn, rx * sn + rz * cs
        if math.hypot(lx, lz) > RADAR_RANGE:
            dot.enabled = False; continue
        dot.enabled, dot.color = True, col
        dot.position = (RADAR_C.x + lx / RADAR_RANGE * RADAR_R, RADAR_C.y + lz / RADAR_RANGE * RADAR_R)

def show_message(text, duration=2.0):
    global msg_timer
    msg_text.text, msg_text.enabled, msg_timer = text, True, duration

def update_hud():
    w = weapons[cur_idx]
    res = '∞' if w['reserve'] == INF else int(w['reserve'])
    status = 'RELOADING...' if is_reloading else f"{w['current_ammo']} / {w['mag_size']}  (+{res})"
    weapon_text.text = f"[{cur_idx + 1}] {w['name']}\nAMMO: {status}"
    weapon_text.color = [color.cyan, color.orange, color.yellow][cur_idx]
    hp_fill.scale_x = max(0, player_hp / MAX_HP)
    hp_text.text = f'HP {max(0, int(player_hp))}'
    score_text.text = f'Gems: {score}'
    wave_text.text = f'Wave {wave_no}  |  Guardians: {len(active_guardians)}' if wave_active else (f'Wave {wave_no} cleared - next wave in {max(0, wave_cooldown):.0f}' if wave_no else 'Get ready...')
update_hud()

# ---------------------------------------------------------------- Combat helpers
def damage_player(dmg):
    global player_hp, game_over
    if game_over: return
    player_hp -= dmg
    hurt_sfx.play()
    damage_overlay.color = C(1, 0, 0, .45)
    damage_overlay.animate_color(C(1, 0, 0, 0), duration=.45)
    if player_hp <= 0:
        game_over = True
        player.enabled = False
        mouse.locked = False
        show_message(f'YOU DIED\nWave {wave_no}  -  Gems {score}\nPress ENTER to restart', 9999)
    update_hud()

active_pickups, active_coins, active_particles = [], [], []

def spawn_pickup(pos, kind):
    root = Entity(position=Vec3(pos.x, 1.0, pos.z))
    root.kind, root.life = kind, 40.0
    if kind == 'health':
        Entity(parent=root, model='cube', scale=(.5, .15, .15), color=color.lime, unlit=True)
        Entity(parent=root, model='cube', scale=(.15, .5, .15), color=color.lime, unlit=True)
    else:
        Entity(parent=root, model='cube', scale=.4, color=color.orange, unlit=True)
    active_pickups.append(root)

def spawn_coin():
    x, z = rand_xz(125, house_pts)
    altar = Altar(position=(x, 0, z))
    root = Entity(position=(x, 1.8, z), base_y=1.8, seed=random.uniform(0, 100))
    root.altar = altar
    Entity(parent=root, model='diamond', scale=(.9, 1.3, .9), color=color.hex('#FFD700'), collider='box')
    Entity(parent=root, model='sphere', scale=.4, color=color.white)
    active_coins.append(root)

def collect_coin(c):
    global score
    coin_sfx.play()
    trigger_particles(c.position, color.gold, 14)
    active_coins.remove(c)
    destroy(c.altar); destroy(c)
    score += 1
    spawn_coin()
    update_hud()

def trigger_particles(pos, col=color.gold, count=12):
    for _ in range(count):
        p = Entity(model='cube', scale=.12, color=col, position=pos + Vec3(*(random.uniform(-.15, .15) for _ in range(3))))
        p.velocity = Vec3(random.uniform(-4, 4), random.uniform(2, 6), random.uniform(-4, 4))
        p.lifetime = .4
        active_particles.append(p)

for _ in range(24): spawn_coin()

def spawn_wave():
    global wave_no, wave_active
    wave_no += 1
    wave_active = True
    wave_sfx.play()
    show_message(f'WAVE {wave_no}', 2.5)
    for _ in range(min(4 + wave_no * 2, 24)):
        a, r = random.uniform(0, math.tau), random.uniform(45, 75)
        gx, gz = clamp(player.x + math.cos(a) * r, -130, 130), clamp(player.z + math.sin(a) * r, -130, 130)
        AggressiveGuardian(position=(gx, 0, gz), wave_level=wave_no)
    update_hud()

def reset_game():
    global player_hp, score, wave_no, wave_active, wave_cooldown, game_over, is_reloading, reload_id, cur_idx
    for g in list(active_guardians): destroy(g)
    active_guardians.clear()
    for p in active_pickups: destroy(p)
    active_pickups.clear()
    player_hp, score, wave_no, wave_active, wave_cooldown, game_over = MAX_HP, 0, 0, False, 3.0, False
    reload_id += 1
    is_reloading = False
    for w, res in zip(weapons, START_RESERVE):
        w['current_ammo'], w['reserve'] = w['mag_size'], res
    switch_weapon(0, force=True)
    player.position = (0, 2, 0)
    player.enabled = True
    mouse.locked = True
    msg_text.enabled = False
    update_hud()

# ---------------------------------------------------------------- Weapons
def finish_reload(wep, rid):
    global is_reloading
    if rid != reload_id: return
    take = min(wep['mag_size'] - wep['current_ammo'], wep['reserve'])
    wep['current_ammo'] += int(take)
    if wep['reserve'] != INF: wep['reserve'] -= take
    is_reloading = False
    gun_rig.animate_position(default_rig_pos, duration=.15)
    switch_sfx.play()
    update_hud()

def reload_weapon():
    global is_reloading, reload_id
    wep = weapons[cur_idx]
    if is_reloading or wep['current_ammo'] == wep['mag_size']: return
    if wep['reserve'] <= 0:
        show_message('NO AMMO - find orange crates!', 1.2); return
    is_reloading = True
    reload_id += 1
    rid = reload_id
    reload_sfx.play()
    update_hud()
    gun_rig.animate_position(default_rig_pos + Vec3(0, -.38, 0), duration=.25)
    invoke(lambda: finish_reload(wep, rid), delay=wep['reload_time'])

def switch_weapon(i, force=False):
    global cur_idx, is_reloading, reload_id
    if (i == cur_idx and not force) or not 0 <= i < len(weapons): return
    reload_id += 1
    is_reloading = False
    weapons[cur_idx]['root'].enabled = False
    cur_idx = i
    weapons[cur_idx]['root'].enabled = True
    switch_sfx.play()
    gun_rig.y = default_rig_pos.y - .2
    gun_rig.animate_position(default_rig_pos, duration=.15, curve=curve.out_quad)
    update_hud()

def fire_weapon():
    global time_since_shot, score, hit_timer
    w = weapons[cur_idx]
    if is_reloading or time_since_shot < w['cooldown']: return
    if w['current_ammo'] <= 0:
        reload_weapon(); return
    time_since_shot = 0.0
    w['current_ammo'] -= 1
    update_hud()
    w['sfx'].play()
    muzzle_flash.position, muzzle_flash.color, muzzle_flash.enabled = w['flash_pos'], w['flash_color'], True
    invoke(lambda: setattr(muzzle_flash, 'enabled', False), delay=.04)
    gun_rig.animate_position(default_rig_pos + w['recoil_pos'], duration=.03, curve=curve.linear)
    gun_rig.animate_rotation(w['recoil_rot'], duration=.03)
    invoke(lambda: gun_rig.animate_position(default_rig_pos, duration=.14, curve=curve.out_bounce), delay=.04)
    invoke(lambda: gun_rig.animate_rotation(Vec3(0, -5, 0), duration=.14), delay=.04)

    s = w['spread']
    for _ in range(w['pellets']):
        d = (camera.forward + Vec3(random.uniform(-s, s), random.uniform(-s, s), random.uniform(-s, s))).normalized()
        hit = raycast(camera.world_position, d, distance=85, ignore=[player, gun_rig])
        if not hit.hit: continue
        trigger_particles(hit.world_point, w['flash_color'], 5)
        e = hit.entity
        owner = e.parent

        coin = next((c for c in active_coins if e == c or e.parent == c), None)
        if coin:
            collect_coin(coin)
        elif isinstance(owner, AggressiveGuardian):
            dmg = w['damage']
            headshot = hit.world_point.y - owner.y > 2.15
            if headshot: dmg *= 2
            trigger_particles(hit.world_point, color.red if headshot else color.smoke, 8)
            owner.position += Vec3(d.x, 0, d.z) * .6
            hit_sfx.play()
            hitmarker.color = color.red if headshot else color.white
            hitmarker.enabled, hit_timer = True, .1
            if owner.take_damage(dmg):
                score += 5
                update_hud()
            else:
                update_hud()
        elif getattr(owner, 'name', '') == 'animal':
            trigger_particles(hit.world_point, color.smoke, 6)
            owner.rotation_y = random.uniform(0, 360)
            owner.position += owner.forward * 5

# ---------------------------------------------------------------- Frame loop
def update():
    global time_since_shot, elapsed, wave_active, wave_cooldown, msg_timer, hit_timer, player_hp, score
    if paused or game_over:
        return
    dt = time.dt
    time_since_shot += dt
    elapsed += dt
    player.speed = 16 if held_keys['left shift'] else 11

    if weapons[cur_idx]['automatic'] and mouse.left:
        fire_weapon()

    # timers
    if msg_timer > 0:
        msg_timer -= dt
        if msg_timer <= 0: msg_text.enabled = False
    if hit_timer > 0:
        hit_timer -= dt
        if hit_timer <= 0: hitmarker.enabled = False

    # waves
    if wave_active and not active_guardians:
        wave_active, wave_cooldown = False, 6.0
        bonus = 10 * wave_no
        score += bonus
        player_hp = min(MAX_HP, player_hp + 25)
        show_message(f'WAVE CLEARED!  +{bonus} gems, +25 HP', 3)
        pickup_sfx.play()
    elif not wave_active:
        wave_cooldown -= dt
        if wave_cooldown <= 0: spawn_wave()
    update_hud()

    # day / night
    sun_a = elapsed * .03
    sun_orb.position = Vec3(math.cos(sun_a) * 160, math.sin(sun_a) * 160, 80)
    sun_light.position = sun_orb.position
    sun_light.look_at(Vec3(0, 0, 0))
    day = clamp(math.sin(sun_a) * 1.2 + .25, .2, 1.0)
    sky_dome.color = C(.47 * day, .71 * day, .89 * day)
    scene.fog_color = C(.62 * day, .77 * day, .85 * day)
    ambient_light.color = C(.43 * day, .47 * day, .51 * day, .82)

    for c in clouds: c.update_drift()
    for a in active_animals: a.update_ai()
    for g in list(active_guardians): g.update_ai()

    # gems
    t = time.time()
    for c in list(active_coins):
        c.rotation_y += 90 * dt
        c.y = c.base_y + math.sin(t * 3 + c.seed) * .25
        if distance(player.position, c.position) < 1.7:
            collect_coin(c)

    # pickups
    for p in list(active_pickups):
        p.rotation_y += 120 * dt
        p.y = 1.0 + math.sin(t * 4) * .15
        p.life -= dt
        if p.life <= 0:
            active_pickups.remove(p); destroy(p); continue
        if distance(player.position, p.position) < 1.8:
            if p.kind == 'health':
                if player_hp >= MAX_HP: continue
                player_hp = min(MAX_HP, player_hp + 35)
            else:
                for w in weapons[1:]: w['reserve'] += w['mag_size']
            pickup_sfx.play()
            trigger_particles(p.position, color.lime if p.kind == 'health' else color.orange, 10)
            active_pickups.remove(p); destroy(p)

    # particles
    for p in list(active_particles):
        p.position += p.velocity * dt
        p.velocity.y -= 14 * dt
        p.scale *= .92
        p.lifetime -= dt
        if p.lifetime <= 0:
            active_particles.remove(p); destroy(p)

    # weapon sway
    if not is_reloading:
        moving = held_keys['w'] or held_keys['a'] or held_keys['s'] or held_keys['d']
        if moving and player.grounded:
            gun_rig.x = default_rig_pos.x + math.sin(t * 10) * .015
            gun_rig.y = default_rig_pos.y + math.cos(t * 20) * .012
        else:
            gun_rig.y = default_rig_pos.y + math.sin(t * 2) * .004

    update_radar()
    if player.y < -15:
        player.position = (0, 3, 0)

# ---------------------------------------------------------------- Input
def input(key):
    global paused
    if game_over:
        if key == 'enter': reset_game()
        return
    if key == 'escape':
        paused = not paused
        player.enabled = not paused
        mouse.locked = not paused
        show_message('PAUSED\nESC to resume  -  Q to quit', 9999) if paused else setattr(msg_text, 'enabled', False)
        return
    if paused:
        if key == 'q': application.quit()
        return
    if key == 'left mouse down' and not weapons[cur_idx]['automatic']: fire_weapon()
    if key == 'r': reload_weapon()
    if key in ('1', '2', '3'): switch_weapon(int(key) - 1)
    if key == 'scroll up': switch_weapon((cur_idx - 1) % len(weapons))
    if key == 'scroll down': switch_weapon((cur_idx + 1) % len(weapons))
    if key == 'space' and player.grounded: jump_sfx.play()

app.run()