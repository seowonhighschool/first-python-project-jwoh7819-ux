import pygame
import math
import sys
import random

# ================================================================
#  전역 상수
# ================================================================
SCREEN_W, SCREEN_H = 800, 600
FPS = 60

# ── 색상 팔레트 ─────────────────────────────────────────────────
C_BG          = ( 45,  55,  40)   # 어두운 초록 배경
C_GRID        = ( 55,  65,  50)   # 격자선
C_FRANK       = ( 70, 130, 200)   # 프랭크 본체 (파랑) - 이미지 없을 때 예비용
C_FRANK_HC    = (160,  80, 240)   # 하이퍼차지 상태 (보라)
C_FRANK_WINDUP= (230, 200,  50)   # 선딜레이 중 (노랑)
C_FRANK_HEAL  = ( 80, 220, 130)   # 자동 치유 중 (민트)
C_ENEMY       = (220,  70,  70)   # 적 본체 (빨강)
C_ENEMY_STUN  = (255, 220,  50)   # 기절 중 적 (노랑)
C_HP_BG       = ( 50,  50,  50)
C_HP_FG       = ( 80, 200,  80)
C_HP_LOW      = (220,  80,  80)
C_SUPER_FG    = (255, 200,   0)
C_HYPER_FG    = (180,  80, 255)
C_GADGET_FG   = ( 80, 220, 255)
C_WHITE       = (255, 255, 255)
C_BLACK       = (  0,   0,   0)
C_BULLET_H    = (255, 240, 100)   # 해머 충격파
C_BULLET_S    = (255, 150,  50)   # 슈퍼 충격파
C_BULLET_G    = ( 80, 240, 255)   # 가젯 음파
C_BULLET_E    = (255, 100,  80)   # 적 투사체

# ── 프랭크 기본 스탯 ────────────────────────────────────────────
FRANK_MAX_HP       = 14_000
FRANK_SPEED        = 180       # px/s
FRANK_HC_SPEED     = FRANK_SPEED * 1.20   # 하이퍼차지 +20%

# ── 일반 공격 (해머링) ──────────────────────────────────────────
HAMMER_RANGE       = 200       # px
HAMMER_ANGLE       = 65        # 도 (부채꼴 전체 폭)
HAMMER_DAMAGE      = 3_500

HAMMER_DELAY_MAX   = 0.60      # s
HAMMER_DELAY_MIN   = 0.24      # s

# ── 특수 공격 (Super) ───────────────────────────────────────────
SUPER_RANGE        = 280
SUPER_ANGLE        = 90
SUPER_DAMAGE       = 5_000
SUPER_DELAY        = 1.10      # s
SUPER_STUN_DUR     = 2.50      # s
SUPER_CHARGE_HIT   = 25.0      # 타격 시 게이지 %
SUPER_CHARGE_RECV  = 10.0      # 피격 시 게이지 %

# ── 가젯 ──────────────────────────────────────────────────────
GADGET_DAMAGE      = 1_200
GADGET_SPEED       = 600       # px/s
GADGET_COOLDOWN    = 16.0      # s
GADGET_IMMUNE_DUR  = 3.50      # s

# ── 하이퍼차지 ─────────────────────────────────────────────────
HYPER_DURATION     = 5.0       # s
HYPER_360_RANGE    = 260       # 원형 충격파 반경 (px)

# ── 자동 치유 ──────────────────────────────────────────────────
HEAL_DELAY         = 3.0       # 비전투 후 치유 시작까지 (s)
HEAL_PER_SEC       = 0.13      # 최대 HP의 13%/s

# ── 적 봇 ──────────────────────────────────────────────────────
ENEMY_MAX_HP       = 3_500
ENEMY_SPEED        = 100       # px/s
ENEMY_ATTACK_RANGE = 250
ENEMY_BULLET_SPD   = 300
ENEMY_DAMAGE       = 400
ENEMY_ATTACK_CD    = 2.0       # s

# ── 오토에임 사정거리 ──────────────────────────────────────────
AUTO_AIM_RANGE     = 300


# ================================================================
#  유틸리티 함수
# ================================================================
def angle_between(ox, oy, tx, ty):
    return math.degrees(math.atan2(-(ty - oy), tx - ox))

def angle_diff(a, b):
    d = (a - b) % 360
    return d - 360 if d > 180 else d

def vec_from_angle(deg, length=1.0):
    rad = math.radians(deg)
    return math.cos(rad) * length, -math.sin(rad) * length

def dist(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)

def draw_bar(surf, x, y, w, h, ratio, fg, bg=C_HP_BG, border=1):
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surf, bg, (x, y, w, h))
    fill_w = int(w * ratio)
    if fill_w > 0:
        pygame.draw.rect(surf, fg, (x, y, fill_w, h))
    if border:
        pygame.draw.rect(surf, C_WHITE, (x, y, w, h), border)

def sector_hit(px, py, facing_deg, rng, full_angle_deg, tx, ty):
    if dist(px, py, tx, ty) > rng:
        return False
    target_ang = angle_between(px, py, tx, ty)
    return abs(angle_diff(target_ang, facing_deg)) <= full_angle_deg / 2

def draw_sector_poly(surf, cx, cy, facing_deg, rng, full_angle_deg,
                     color, alpha=80, steps=22):
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    half = full_angle_deg / 2
    pts = [(int(cx), int(cy))]
    for i in range(steps + 1):
        t = i / steps
        ang = math.radians(facing_deg - half + full_angle_deg * t)
        pts.append((int(cx + math.cos(ang) * rng),
                    int(cy - math.sin(ang) * rng)))
    pygame.draw.polygon(s, (*color, alpha), pts)
    surf.blit(s, (0, 0))


# ================================================================
#  Bullet  – 투사체 / 충격파 이펙트
# ================================================================
class Bullet:
    def __init__(self, x, y, angle_deg, speed, damage, kind,
                 owner_pos=None, sector_range=0, sector_angle=0,
                 radius360=0, lifetime=0.20, pierce=False):
        self.x = float(x)
        self.y = float(y)
        self.angle = angle_deg
        self.speed = speed
        self.damage = damage
        self.kind = kind
        self.alive = True
        self.pierce = pierce
        self.hit_set = set()

        self.owner_pos = owner_pos
        self.sector_range = sector_range
        self.sector_angle = sector_angle
        self.radius360 = radius360
        self.is_circle = radius360 > 0

        self.lifetime = lifetime
        self.age = 0.0

        vx, vy = vec_from_angle(angle_deg, speed)
        self.vx = vx
        self.vy = vy

    def update(self, dt):
        if not self.alive: return
        self.age += dt
        if self.age >= self.lifetime:
            self.alive = False
            return
        if self.speed > 0:
            self.x += self.vx * dt
            self.y += self.vy * dt
            if not (-60 < self.x < SCREEN_W + 60 and -60 < self.y < SCREEN_H + 60):
                self.alive = False

    def draw(self, surf):
        if not self.alive: return
        alpha = max(0, int(255 * (1.0 - self.age / max(self.lifetime, 0.001))))

        if self.kind == 'player_hammer':
            if self.owner_pos and self.sector_range > 0:
                ox, oy = self.owner_pos
                draw_sector_poly(surf, ox, oy, self.angle,
                                 self.sector_range, self.sector_angle,
                                 C_BULLET_H, alpha=int(100 * (1 - self.age / self.lifetime)))
                half = self.sector_angle / 2
                for offset in (-half, 0, half):
                    ex, ey = vec_from_angle(self.angle + offset, self.sector_range)
                    pygame.draw.line(surf, C_BULLET_H,
                                     (int(ox), int(oy)),
                                     (int(ox + ex), int(oy + ey)), 2)

        elif self.kind in ('player_super', 'player_super360'):
            if not self.owner_pos: return
            ox, oy = self.owner_pos
            t_alpha = int(130 * (1 - self.age / max(self.lifetime, 0.001)))
            if self.is_circle:
                s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                pygame.draw.circle(s, (*C_BULLET_S, t_alpha), (int(ox), int(oy)), int(self.radius360))
                pygame.draw.circle(s, (255, 255, 255, t_alpha // 2), (int(ox), int(oy)), int(self.radius360), 3)
                surf.blit(s, (0, 0))
            else:
                draw_sector_poly(surf, ox, oy, self.angle,
                                 self.sector_range, self.sector_angle,
                                 C_BULLET_S, alpha=t_alpha)
                half = self.sector_angle / 2
                for offset in (-half, 0, half):
                    ex, ey = vec_from_angle(self.angle + offset, self.sector_range)
                    pygame.draw.line(surf, C_BULLET_S,
                                     (int(ox), int(oy)),
                                     (int(ox + ex), int(oy + ey)), 3)

        elif self.kind == 'player_gadget':
            pygame.draw.circle(surf, C_BULLET_G, (int(self.x), int(self.y)), 7)
            pygame.draw.circle(surf, C_WHITE, (int(self.x), int(self.y)), 7, 2)

        elif self.kind == 'enemy':
            pygame.draw.circle(surf, C_BULLET_E, (int(self.x), int(self.y)), 6)


# ================================================================
#  EnemyBot
# ================================================================
class EnemyBot:
    RADIUS = 18

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.hp = ENEMY_MAX_HP
        self.max_hp = ENEMY_MAX_HP
        self.alive = True
        self.stun_timer = 0.0
        self.attack_cd = random.uniform(0.5, ENEMY_ATTACK_CD)
        self.wander_angle = random.uniform(0, 360)
        self.wander_timer = random.uniform(1, 3)

    @property
    def is_stunned(self):
        return self.stun_timer > 0

    def apply_stun(self, duration):
        self.stun_timer = max(self.stun_timer, duration)

    def take_damage(self, dmg):
        self.hp = max(0, self.hp - int(dmg))
        if self.hp == 0:
            self.alive = False
        return not self.alive

    def update(self, dt, player, bullets_out):
        if not self.alive: return
        if self.stun_timer > 0:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            return

        px, py = player.x, player.y
        d = dist(self.x, self.y, px, py)

        if d > ENEMY_ATTACK_RANGE * 0.75:
            ang = math.atan2(py - self.y, px - self.x)
            self.x += math.cos(ang) * ENEMY_SPEED * dt
            self.y += math.sin(ang) * ENEMY_SPEED * dt
        else:
            self.wander_timer -= dt
            if self.wander_timer <= 0:
                self.wander_angle = random.uniform(0, 360)
                self.wander_timer = random.uniform(1.0, 2.5)
            wx, wy = vec_from_angle(self.wander_angle, ENEMY_SPEED * 0.5)
            self.x += wx * dt
            self.y += wy * dt

        r = self.RADIUS
        self.x = max(r, min(SCREEN_W - r, self.x))
        self.y = max(r, min(SCREEN_H - r, self.y))

        self.attack_cd -= dt
        if self.attack_cd <= 0 and d <= ENEMY_ATTACK_RANGE:
            self.attack_cd = ENEMY_ATTACK_CD
            ang_deg = angle_between(self.x, self.y, px, py)
            b = Bullet(self.x, self.y, ang_deg,
                       ENEMY_BULLET_SPD, ENEMY_DAMAGE, 'enemy',
                       lifetime=3.0)
            bullets_out.append(b)

    def draw(self, surf, font_small):
        if not self.alive: return
        r = self.RADIUS
        color = C_ENEMY_STUN if self.is_stunned else C_ENEMY
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), r)
        pygame.draw.circle(surf, C_WHITE, (int(self.x), int(self.y)), r, 2)
        bw, bh = 44, 5
        draw_bar(surf, int(self.x) - bw // 2, int(self.y) - r - 10, bw, bh, self.hp / self.max_hp, C_HP_FG)

        if self.is_stunned:
            stun_surf = font_small.render("STUNNED", True, C_ENEMY_STUN)
            surf.blit(stun_surf, (int(self.x) - stun_surf.get_width() // 2, int(self.y) - r - 24))


# ================================================================
#  FrankPlayer
# ================================================================
class FrankPlayer:
    RADIUS = 22

    def __init__(self, x, y, image=None):
        self.x = float(x)
        self.y = float(y)
        self.hp = FRANK_MAX_HP
        self.max_hp = FRANK_MAX_HP
        self.image = image  # 사용자 정의 캐릭터 이미지 

        self.facing = 0.0
        self.attack_state = 'idle'
        self.windup_timer  = 0.0
        self.super_charge = 0.0
        self.hyper_charge  = 0.0
        self.hyper_active  = False
        self.hyper_timer   = 0.0
        self.gadget_cd           = 0.0
        self.gadget_immune       = False
        self.gadget_immune_timer = 0.0
        self.heal_inactive_timer = 0.0
        self.is_healing          = False
        self.heal_tick_timer     = 0.0
        self.alive = True

    @property
    def hp_ratio(self):
        return self.hp / self.max_hp

    @property
    def sponge_active(self):
        return self.hp_ratio >= 0.50

    def _reset_heal_timer(self):
        self.heal_inactive_timer = 0.0
        self.is_healing          = False
        self.heal_tick_timer     = 0.0

    def _charge_super(self, amount):
        self.super_charge = min(100.0, self.super_charge + amount)
        self.hyper_charge = min(100.0, self.hyper_charge + amount * 0.4)

    def get_hammer_delay(self):
        if self.hyper_active: return HAMMER_DELAY_MIN
        return HAMMER_DELAY_MIN + (HAMMER_DELAY_MAX - HAMMER_DELAY_MIN) * self.hp_ratio

    def move(self, keys, dt):
        if self.attack_state != 'idle': return
        spd = FRANK_HC_SPEED if self.hyper_active else FRANK_SPEED
        dx = dy = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1.0
        if dx or dy:
            ln = math.hypot(dx, dy)
            self.x += (dx / ln) * spd * dt
            self.y += (dy / ln) * spd * dt
        r = self.RADIUS
        self.x = max(r, min(SCREEN_W - r, self.x))
        self.y = max(r, min(SCREEN_H - r, self.y))

    def aim_at(self, mx, my):
        self.facing = angle_between(self.x, self.y, mx, my)

    def auto_aim(self, enemies):
        best_d = AUTO_AIM_RANGE + 1
        best   = None
        for e in enemies:
            if not e.alive: continue
            d = dist(self.x, self.y, e.x, e.y)
            if d < best_d:
                best_d = d
                best   = e
        if best:
            self.facing = angle_between(self.x, self.y, best.x, best.y)

    def request_attack(self, kind, enemies=None, auto_aim=False):
        if self.attack_state != 'idle': return None
        if kind == 'gadget':
            if self.gadget_cd > 0: return None
            return self._fire_gadget()
        if kind == 'hammer':
            if auto_aim and enemies:
                self.auto_aim(enemies)
            self.attack_state = 'windup_hammer'
            self.windup_timer = self.get_hammer_delay()
            self._reset_heal_timer()
        elif kind == 'super':
            if self.super_charge < 100.0: return None
            self.attack_state = 'windup_super'
            self.windup_timer = SUPER_DELAY
            self._reset_heal_timer()
        return None

    def _fire_gadget(self):
        self.gadget_cd           = GADGET_COOLDOWN
        self.gadget_immune       = True
        self.gadget_immune_timer = GADGET_IMMUNE_DUR
        self._reset_heal_timer()
        return Bullet(self.x, self.y, self.facing, GADGET_SPEED, GADGET_DAMAGE, 'player_gadget',
                      lifetime=2.0, pierce=True)

    def _execute_hammer(self, enemies):
        for e in enemies:
            if not e.alive: continue
            if sector_hit(self.x, self.y, self.facing, HAMMER_RANGE, HAMMER_ANGLE, e.x, e.y):
                e.take_damage(HAMMER_DAMAGE)
                self._charge_super(SUPER_CHARGE_HIT)
        return Bullet(self.x, self.y, self.facing, 0, 0, 'player_hammer',
                      owner_pos=(self.x, self.y), sector_range=HAMMER_RANGE,
                      sector_angle=HAMMER_ANGLE, lifetime=0.22)

    def _execute_super(self, enemies):
        self.super_charge = 0.0
        if self.hyper_active:
            for e in enemies:
                if not e.alive: continue
                if dist(self.x, self.y, e.x, e.y) <= HYPER_360_RANGE:
                    e.take_damage(SUPER_DAMAGE)
                    e.apply_stun(SUPER_STUN_DUR)
                    self._charge_super(SUPER_CHARGE_HIT)
            return Bullet(self.x, self.y, self.facing, 0, 0, 'player_super360',
                          owner_pos=(self.x, self.y), radius360=HYPER_360_RANGE, lifetime=0.35)
        else:
            for e in enemies:
                if not e.alive: continue
                if sector_hit(self.x, self.y, self.facing, SUPER_RANGE, SUPER_ANGLE, e.x, e.y):
                    e.take_damage(SUPER_DAMAGE)
                    e.apply_stun(SUPER_STUN_DUR)
                    self._charge_super(SUPER_CHARGE_HIT)
            return Bullet(self.x, self.y, self.facing, 0, 0, 'player_super',
                          owner_pos=(self.x, self.y), sector_range=SUPER_RANGE,
                          sector_angle=SUPER_ANGLE, lifetime=0.35)

    def activate_hypercharge(self):
        if self.hyper_charge < 100.0: return False
        self.hyper_charge = 0.0
        self.hyper_active = True
        self.hyper_timer  = HYPER_DURATION
        return True

    def take_damage(self, raw_dmg):
        dmg = int(raw_dmg * 0.90) if self.sponge_active else int(raw_dmg)
        self.hp = max(0, self.hp - dmg)
        self._charge_super(SUPER_CHARGE_RECV)
        self._reset_heal_timer()
        if self.hp == 0:
            self.alive = False

    def update(self, dt, enemies, bullets_out):
        if not self.alive: return

        if self.attack_state in ('windup_hammer', 'windup_super'):
            self.windup_timer -= dt
            if self.windup_timer <= 0.0:
                if self.attack_state == 'windup_hammer': b = self._execute_hammer(enemies)
                else: b = self._execute_super(enemies)
                bullets_out.append(b)
                self.attack_state = 'idle'

        if self.hyper_active:
            self.hyper_timer -= dt
            if self.hyper_timer <= 0.0:
                self.hyper_active = False

        if self.gadget_immune:
            self.gadget_immune_timer -= dt
            if self.gadget_immune_timer <= 0.0:
                self.gadget_immune       = False
                self.gadget_immune_timer = 0.0

        if self.gadget_cd > 0:
            self.gadget_cd = max(0.0, self.gadget_cd - dt)

        if self.hp < self.max_hp:
            self.heal_inactive_timer += dt
            if self.heal_inactive_timer >= HEAL_DELAY:
                self.is_healing   = True
                self.heal_tick_timer += dt
                if self.heal_tick_timer >= 1.0:
                    self.heal_tick_timer -= 1.0
                    heal_amt = int(self.max_hp * HEAL_PER_SEC)
                    self.hp  = min(self.max_hp, self.hp + heal_amt)
            else:
                self.is_healing = False
        else:
            self.is_healing          = False
            self.heal_inactive_timer = 0.0
            self.heal_tick_timer     = 0.0

    def draw(self, surf, font_small):
        if not self.alive: return
        r = self.RADIUS

        # 색상 상태값 (이미지 로드 실패 시 백업 혹은 텍스트 용도)
        if self.hyper_active:
            body_col = C_FRANK_HC
        elif self.attack_state != 'idle':
            body_col = C_FRANK_WINDUP
        elif self.is_healing:
            body_col = C_FRANK_HEAL
        else:
            body_col = C_FRANK

        # 가젯 면역 링 (외각)
        if self.gadget_immune:
            pygame.draw.circle(surf, C_GADGET_FG, (int(self.x), int(self.y)), r + 20, 3)

        # 하이퍼차지 글로우 링
        if self.hyper_active:
            pygame.draw.circle(surf, C_HYPER_FG, (int(self.x), int(self.y)), r + 25, 2)

        # 본체 렌더링 (이미지가 있으면 이미지 렌더링, 없으면 원형 유지)
        if self.image:
            img_rect = self.image.get_rect(center=(int(self.x), int(self.y)))
            surf.blit(self.image, img_rect)
            
            # 발밑에 작게 상태를 나타내는 오라 표시
            if self.attack_state != 'idle':
                pygame.draw.circle(surf, C_FRANK_WINDUP, (int(self.x), int(self.y)), r + 10, 2)
            elif self.is_healing:
                pygame.draw.circle(surf, C_FRANK_HEAL, (int(self.x), int(self.y)), r + 10, 2)
        else:
            pygame.draw.circle(surf, body_col, (int(self.x), int(self.y)), r)
            pygame.draw.circle(surf, C_WHITE,  (int(self.x), int(self.y)), r, 3)

        # 조준 방향 표시선 (이미지 크기를 고려하여 길이를 조금 늘림)
        fx, fy = vec_from_angle(self.facing, r + 25)
        pygame.draw.line(surf, C_WHITE,
                         (int(self.x), int(self.y)),
                         (int(self.x + fx), int(self.y + fy)), 3)

        # 머리 위 상태 텍스트
        status = ""
        if self.attack_state == 'windup_hammer': status = "SWING!"
        elif self.attack_state == 'windup_super': status = "SUPER!"
        elif self.is_healing: status = "HEAL"
        elif self.hyper_active: status = "HYPER"

        if status:
            col = {
                "SWING!": C_FRANK_WINDUP,
                "SUPER!" : C_BULLET_S,
                "HEAL"  : C_FRANK_HEAL,
                "HYPER" : C_HYPER_FG,
            }.get(status, C_WHITE)
            txt = font_small.render(status, True, col)
            surf.blit(txt, (int(self.x) - txt.get_width() // 2, int(self.y) - r - 35))


# ================================================================
#  HUD 및 배경
# ================================================================
def draw_hud(surf, player, font_mid, font_small, enemy_count):
    pad = 12
    y0  = 10

    hp_w, hp_h = 270, 22
    hp_col = C_HP_FG if player.hp_ratio > 0.40 else C_HP_LOW
    draw_bar(surf, pad, y0, hp_w, hp_h, player.hp_ratio, hp_col)
    hp_txt = font_small.render(f"HP  {player.hp:,} / {player.max_hp:,}", True, C_WHITE)
    surf.blit(hp_txt, (pad + 4, y0 + 3))

    if player.sponge_active:
        sp = font_small.render("[SPONGE -10%DMG]", True, (150, 200, 255))
        surf.blit(sp, (pad + hp_w + 6, y0 + 3))

    sy = y0 + hp_h + 5
    sw, sh = 170, 16
    s_col = C_SUPER_FG if player.super_charge >= 100 else (160, 120, 20)
    draw_bar(surf, pad, sy, sw, sh, player.super_charge / 100, s_col)
    s_txt = font_small.render(f"SUPER  {int(player.super_charge)}%" + ("  READY!" if player.super_charge >= 100 else ""), True, C_WHITE)
    surf.blit(s_txt, (pad + 4, sy + 1))

    hy = sy + sh + 4
    hw, hh = 170, 16
    draw_bar(surf, pad, hy, hw, hh, player.hyper_charge / 100, C_HYPER_FG)
    h_txt = font_small.render(f"HYPER  {int(player.hyper_charge)}%" + ("  READY!" if player.hyper_charge >= 100 else ""), True, C_WHITE)
    surf.blit(h_txt, (pad + 4, hy + 1))

    gy = hy + hh + 4
    gw, gh = 130, 14
    if player.gadget_cd > 0:
        draw_bar(surf, pad, gy, gw, gh, 1.0 - player.gadget_cd / GADGET_COOLDOWN, C_GADGET_FG)
        g_txt = font_small.render(f"GADGET {player.gadget_cd:.1f}s", True, (180, 180, 180))
    else:
        draw_bar(surf, pad, gy, gw, gh, 1.0, C_GADGET_FG)
        g_txt = font_small.render("GADGET  READY", True, C_GADGET_FG)
    surf.blit(g_txt, (pad + 4, gy + 1))

    if player.gadget_immune:
        gi_txt = font_small.render(f"CC IMMUNE  {player.gadget_immune_timer:.1f}s", True, C_GADGET_FG)
        surf.blit(gi_txt, (pad, gy + gh + 4))

    if player.attack_state != 'idle':
        if player.attack_state == 'windup_hammer':
            total = player.get_hammer_delay()
            label = f"SWING WINDUP  {player.windup_timer:.2f}s"
            col   = C_FRANK_WINDUP
        else:
            total = SUPER_DELAY
            label = f"SUPER WINDUP  {player.windup_timer:.2f}s"
            col   = C_BULLET_S

        elapsed_r = 1.0 - (player.windup_timer / max(total, 0.001))
        wx = SCREEN_W // 2 - 110
        wy = SCREEN_H - 52
        draw_bar(surf, wx, wy, 220, 20, elapsed_r, col)
        wl = font_small.render(label, True, C_WHITE)
        surf.blit(wl, (wx + 4, wy + 3))

    if player.is_healing:
        ht = font_mid.render("♥  AUTO HEALING", True, C_FRANK_HEAL)
        surf.blit(ht, (SCREEN_W // 2 - ht.get_width() // 2, SCREEN_H - 82))

    if player.hyper_active:
        ha = font_mid.render(f"  HYPERCHARGE  {player.hyper_timer:.1f}s  ", True, C_HYPER_FG)
        pygame.draw.rect(surf, (30, 0, 50), (SCREEN_W // 2 - ha.get_width() // 2 - 4, 6, ha.get_width() + 8, ha.get_height() + 4))
        surf.blit(ha, (SCREEN_W // 2 - ha.get_width() // 2, 8))

    tips = [
        "WASD: Move",
        "LClick/Space: Hammer",
        "Q/RClick: Super (needs 100%)",
        "E: Gadget  |  R: Hypercharge",
        f"Enemies: {enemy_count}",
    ]
    for i, t in enumerate(tips):
        ts = font_small.render(t, True, (150, 150, 150))
        surf.blit(ts, (SCREEN_W - ts.get_width() - 10, SCREEN_H - (len(tips) - i) * 18 - 6))

def draw_background(surf):
    surf.fill(C_BG)
    step = 60
    for gx in range(0, SCREEN_W, step):
        pygame.draw.line(surf, C_GRID, (gx, 0), (gx, SCREEN_H))
    for gy in range(0, SCREEN_H, step):
        pygame.draw.line(surf, C_GRID, (0, gy), (SCREEN_W, gy))

def spawn_enemies(n, avoid_x=SCREEN_W // 2, avoid_y=SCREEN_H // 2, min_dist=180):
    enemies = []
    for _ in range(n):
        for _ in range(100):
            ex = random.randint(50, SCREEN_W - 50)
            ey = random.randint(50, SCREEN_H - 50)
            if dist(ex, ey, avoid_x, avoid_y) > min_dist:
                break
        enemies.append(EnemyBot(ex, ey))
    return enemies


# ================================================================
#  메인 게임 루프
# ================================================================
def main():
    pygame.init()
    screen  = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Brawl Stars – Frank Prototype  |  ESC: Quit")
    clock   = pygame.time.Clock()

    try:
        font_mid   = pygame.font.SysFont("Arial", 16, bold=True)
        font_small = pygame.font.SysFont("Arial", 13)
    except Exception:
        font_mid   = pygame.font.Font(None, 20)
        font_small = pygame.font.Font(None, 16)

    # ──────────────────────────────────────────────────────────
    # 프랭크 이미지 로드 및 크기 조정 추가 
    # ──────────────────────────────────────────────────────────
    try:
        frank_img = pygame.image.load("image_b68f7d.png").convert_alpha()
        # 플레이어의 히트박스(Radius)에 맞게 이미지 크기 조정 (약 60x75)
        frank_img = pygame.transform.smoothscale(frank_img, (60, 75))
    except Exception as e:
        print(f"이미지를 불러올 수 없습니다: {e}")
        frank_img = None

    # 엔티티 초기화 (이미지 전달)
    player  = FrankPlayer(SCREEN_W // 2, SCREEN_H // 2, frank_img)
    enemies = spawn_enemies(6)
    bullets = []

    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                elif event.key == pygame.K_q:
                    player.aim_at(mx, my)
                    player.request_attack('super')
                elif event.key == pygame.K_e:
                    player.aim_at(mx, my)
                    b = player.request_attack('gadget')
                    if b: bullets.append(b)
                elif event.key == pygame.K_r:
                    player.activate_hypercharge()
                elif event.key == pygame.K_SPACE:
                    player.request_attack('hammer', enemies, auto_aim=True)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    player.aim_at(mx, my)
                    player.request_attack('hammer')
                elif event.button == 3:
                    player.aim_at(mx, my)
                    player.request_attack('super')

        # 상태 및 이동 업데이트
        keys = pygame.key.get_pressed()
        player.move(keys, dt)
        player.update(dt, enemies, bullets)

        for e in enemies:
            e.update(dt, player, bullets)

        for b in bullets:
            b.update(dt)
            if not b.alive: continue
            # 투사체 충돌 판정
            if b.kind == 'player_gadget':
                for e in enemies:
                    if e.alive and e not in b.hit_set:
                        if dist(b.x, b.y, e.x, e.y) < EnemyBot.RADIUS + 7:
                            e.take_damage(b.damage)
                            e.apply_stun(1.5)
                            b.hit_set.add(e)
            elif b.kind == 'enemy':
                if dist(b.x, b.y, player.x, player.y) < FrankPlayer.RADIUS + 6:
                    if not player.gadget_immune:
                        player.take_damage(b.damage)
                    b.alive = False

        enemies = [e for e in enemies if e.alive]
        bullets = [b for b in bullets if b.alive]

        # 적 모두 처치 시 리스폰
        if not enemies:
            enemies = spawn_enemies(6, player.x, player.y)

        # 화면 렌더링
        draw_background(screen)
        for b in bullets: b.draw(screen)
        for e in enemies: e.draw(screen, font_small)
        player.draw(screen, font_small)
        draw_hud(screen, player, font_mid, font_small, len(enemies))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()