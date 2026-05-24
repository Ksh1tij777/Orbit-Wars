import math

# ── Constants ──────────────────────────────────────────────────────────────────
SUN_X, SUN_Y   = 50, 50
SUN_RADIUS      = 5
MIN_FLEET       = 10    # never send fewer ships than this
CAPTURE_BUFFER  = 5     # extra ships on top of minimum needed to capture
EARLY_TURNS     = 40    # aggressive expansion phase

# Global turn counter (obs doesn't expose step number directly)
_turn = 0


# ── Physics helpers ────────────────────────────────────────────────────────────

def fleet_speed(n):
    """Bigger fleets move faster, capped at 6/turn."""
    return min(6.0, 1.0 + n * 0.05)


def travel_time(dist, n):
    return dist / fleet_speed(max(n, 1))


def planet_pos(planet, turns, av):
    """
    Returns (x, y) position of a planet `turns` turns from now.
    Inner planets (dist < 30 from sun) orbit; outer ones stay still.
    """
    _, _, x, y, _, _, _ = planet
    d = math.hypot(x - SUN_X, y - SUN_Y)
    if d < 30:
        a = math.atan2(y - SUN_Y, x - SUN_X) + av * turns
        return SUN_X + d * math.cos(a), SUN_Y + d * math.sin(a)
    return x, y


def hits_sun(sx, sy, tx, ty):
    """
    True if the straight line from source (sx, sy) to target (tx, ty)
    passes within SUN_RADIUS + 3 of the sun centre.
    Uses point-to-segment distance formula.
    """
    dx, dy = tx - sx, ty - sy
    d2 = dx * dx + dy * dy
    if d2 < 1e-9:
        return False
    t = max(0.0, min(1.0, ((SUN_X - sx) * dx + (SUN_Y - sy) * dy) / d2))
    return math.hypot(sx + t * dx - SUN_X, sy + t * dy - SUN_Y) < SUN_RADIUS + 3


# ── Garrison ───────────────────────────────────────────────────────────────────

def get_garrison(ships, turn):
    """
    Dynamic garrison:
      - Early game (turn < 40): keep only 15% — expand fast
      - Late game: keep 30% — defend territory
    """
    ratio = 0.15 if turn < EARLY_TURNS else 0.30
    return max(5, int(ships * ratio))


# ── Fleet intent detection ─────────────────────────────────────────────────────

def fleet_aims_at(fleet, planet):
    """
    Returns True if this fleet's trajectory passes within 5 units of `planet`.
    Uses perpendicular distance from planet to the fleet's direction line.
    """
    _, _, fx, fy, fangle, from_pid, _ = fleet
    pid, _, px, py, _, _, _ = planet
    if pid == from_pid:
        return False

    fdx, fdy = math.cos(fangle), math.sin(fangle)
    dx,  dy  = px - fx, py - fy

    # Must be moving toward the planet (dot product > 0)
    if dx * fdx + dy * fdy < 0:
        return False

    # Perpendicular distance from planet to fleet's travel line
    perp = abs(dx * fdy - dy * fdx)
    return perp < 6


def enemy_ships_toward(planet, fleets, my_id):
    """Sum of all enemy ships on a trajectory toward `planet`."""
    return sum(
        f[6] for f in fleets
        if f[1] != my_id and fleet_aims_at(f, planet)
    )


def friendly_ships_toward(planet_id, fleets, my_id):
    """
    Sum of friendly ships already dispatched toward `planet_id`.
    We track this via `committed_to` in the main loop, but this
    can catch fleets launched in previous turns.
    """
    total = 0
    for f in fleets:
        if f[1] == my_id and fleet_aims_at(f, {'_pid': planet_id, 2: None, 3: None}):
            total += f[6]
    return total


# ── Target scoring ─────────────────────────────────────────────────────────────

def score_neutral(tgt, sx, sy, turn):
    """
    Score a neutral planet as a target.
    Rewards: high production, close distance.
    Penalises: many ships to overcome.
    Early game bonus to encourage rapid expansion.
    """
    _, _, tx, ty, _, tships, tprod = tgt
    dist = math.hypot(tx - sx, ty - sy)
    base = (tprod + 1) * 12 / (dist + 1)
    early_bonus = 1.5 if turn < EARLY_TURNS else 1.0
    return base * early_bonus - tships * 0.08


def score_enemy(tgt, sx, sy, ships_needed):
    """
    Score an enemy planet as a target.
    Rewards: high production, close distance.
    Penalises: many ships needed (costly attack).
    """
    _, _, tx, ty, _, _, tprod = tgt
    dist = math.hypot(tx - sx, ty - sy)
    return (tprod + 1) * 8 / (dist + 1) - ships_needed * 0.04


# ── Main agent ─────────────────────────────────────────────────────────────────

def agent(obs):
    global _turn
    _turn += 1
    turn = _turn

    my_id   = obs.player
    planets = obs.planets          # [id, owner, x, y, radius, ships, production]
    fleets  = obs.fleets           # [id, owner, x, y, angle, from_planet_id, ships]
    av      = obs.angular_velocity

    my_planets      = [p for p in planets if p[1] == my_id]
    neutral_planets = [p for p in planets if p[1] == -1]
    enemy_planets   = [p for p in planets if p[1] not in (-1, my_id)]

    moves = []

    # committed_from[sid] = ships already dispatched from source planet this turn
    # committed_to[tid]   = ships already en-route to target this turn
    committed_from = {}
    committed_to   = {}

    # ── Phase 1: DEFENSE ──────────────────────────────────────────────────────
    # For each of our planets, check if enemy fleets are heading toward it.
    # If we're outnumbered, pull reinforcements from the nearest ally.

    for p in my_planets:
        pid, _, px, py, _, pships, _ = p
        incoming = enemy_ships_toward(p, fleets, my_id)
        if incoming == 0:
            continue

        deficit = incoming - pships + 3   # ships we need to survive + buffer
        if deficit <= 0:
            continue  # current garrison holds

        # Sort allies by distance to threatened planet
        allies = sorted(
            [s for s in my_planets if s[0] != pid],
            key=lambda s: math.hypot(s[2] - px, s[3] - py)
        )

        for helper in allies:
            hid, _, hx, hy, _, hships, _ = helper
            already_sent = committed_from.get(hid, 0)
            avail = hships - get_garrison(hships, turn) - already_sent
            send  = min(avail, deficit)

            if send < MIN_FLEET:
                continue

            if hits_sun(hx, hy, px, py):
                continue

            angle = math.atan2(py - hy, px - hx)
            moves.append([hid, angle, send])
            committed_from[hid] = committed_from.get(hid, 0) + send
            committed_to[pid]   = committed_to.get(pid, 0) + send
            deficit -= send

            if deficit <= 0:
                break

    # ── Phase 2: EXPANSION & ATTACK ───────────────────────────────────────────
    # Each source planet scores all valid targets and sends to as many as it
    # can afford — not just the top one. This eliminates idle ships.

    for src in my_planets:
        sid, _, sx, sy, _, sships, _ = src
        already_sent = committed_from.get(sid, 0)
        avail = sships - get_garrison(sships, turn) - already_sent

        if avail < MIN_FLEET:
            continue

        candidates = []

        # — Neutrals —
        for tgt in neutral_planets:
            tid, _, tx, ty, _, tships, tprod = tgt
            dist = math.hypot(tx - sx, ty - sy)
            # Reduce ships needed by what's already committed toward this target
            already = committed_to.get(tid, 0)
            ships_needed = max(1, tships + CAPTURE_BUFFER - already)
            sc = score_neutral(tgt, sx, sy, turn)
            candidates.append((sc, tgt, ships_needed, dist, 'neutral'))

        # — Enemies —
        for tgt in enemy_planets:
            tid, _, tx, ty, _, tships, tprod = tgt
            dist = math.hypot(tx - sx, ty - sy)
            tt = travel_time(dist, avail)
            projected = tships + int(tprod * tt)   # ships at arrival time
            already = committed_to.get(tid, 0)
            ships_needed = max(1, projected + CAPTURE_BUFFER - already)
            sc = score_enemy(tgt, sx, sy, ships_needed)
            candidates.append((sc, tgt, ships_needed, dist, 'enemy'))

        # Sort: best score first
        candidates.sort(key=lambda c: -c[0])

        for sc, tgt, ships_needed, dist, kind in candidates:
            if avail < MIN_FLEET:
                break

            # Send exactly what's needed (min MIN_FLEET), capped by available
            send = min(avail, max(MIN_FLEET, ships_needed))
            tid, _, tx, ty, _, _, _ = tgt

            # Aim at future position (orbit prediction)
            tt = travel_time(dist, send)
            ftx, fty = planet_pos(tgt, int(tt), av)
            angle = math.atan2(fty - sy, ftx - sx)

            if hits_sun(sx, sy, ftx, fty):
                continue

            moves.append([sid, angle, send])
            committed_from[sid] = committed_from.get(sid, 0) + send
            committed_to[tid]   = committed_to.get(tid, 0) + send
            avail -= send

    return moves
