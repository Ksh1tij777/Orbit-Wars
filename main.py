import math


SUN_X, SUN_Y = 50, 50
SUN_RADIUS = 5
GARRISON_RATIO = 0.3  # keep 30% of ships as garrison


def fleet_speed(num_ships):
    # bigger fleets are faster, max 6/turn
    return min(6, 1 + num_ships * 0.05)


def travel_time(dist, num_ships):
    return dist / fleet_speed(num_ships)


def planet_future_pos(planet, turns, angular_velocity):
    pid, owner, x, y, radius, ships, production = planet
    dist_to_sun = math.hypot(x - SUN_X, y - SUN_Y)
    if dist_to_sun < 30:  # inner planet — it orbits
        angle_now = math.atan2(y - SUN_Y, x - SUN_X)
        angle_future = angle_now + angular_velocity * turns
        fx = SUN_X + dist_to_sun * math.cos(angle_future)
        fy = SUN_Y + dist_to_sun * math.sin(angle_future)
        return fx, fy
    return x, y  # outer planet stays still


def will_hit_sun(sx, sy, angle, dist):
    # check if straight-line path from (sx,sy) at angle passes through sun
    ex = sx + dist * math.cos(angle)
    ey = sy + dist * math.sin(angle)
    # distance from sun to segment
    dx, dy = ex - sx, ey - sy
    t = max(0, min(1, ((SUN_X - sx) * dx + (SUN_Y - sy) * dy) / (dx * dx + dy * dy + 1e-9)))
    cx = sx + t * dx
    cy = sy + t * dy
    return math.hypot(cx - SUN_X, cy - SUN_Y) < SUN_RADIUS + 2


def enemy_ships_incoming(planet_id, fleets, my_id):
    total = 0
    for f in fleets:
        fid, fowner, fx, fy, fangle, from_pid, fships = f
        if fowner != my_id and from_pid == planet_id:
            total += fships
    return total


def agent(obs):
    my_id = obs.player
    planets = obs.planets   # [id, owner, x, y, radius, ships, production]
    fleets = obs.fleets     # [id, owner, x, y, angle, from_planet_id, ships]
    angular_velocity = obs.angular_velocity

    my_planets = [p for p in planets if p[1] == my_id]
    neutral_planets = [p for p in planets if p[1] == -1]
    enemy_planets = [p for p in planets if p[1] not in (-1, my_id)]

    moves = []

    for src in my_planets:
        sid, _, sx, sy, sradius, sships, sprod = src
        garrison = max(5, int(sships * GARRISON_RATIO))
        available = sships - garrison
        if available <= 0:
            continue

        # build candidate targets: neutrals first, then weak enemies
        candidates = []

        for tgt in neutral_planets:
            tid, _, tx, ty, tradius, tships, tprod = tgt
            dist = math.hypot(tx - sx, ty - sy)
            ships_needed = tships + 1
            score = tprod / (dist + 1) - ships_needed * 0.1  # high-value close neutrals
            candidates.append((score, tgt, ships_needed, dist))

        for tgt in enemy_planets:
            tid, _, tx, ty, tradius, tships, tprod = tgt
            dist = math.hypot(tx - sx, ty - sy)
            turns = travel_time(dist, available)
            # estimate ships on arrival (they keep producing)
            ships_needed = tships + int(tprod * turns) + 1
            score = tprod / (dist + 1) - ships_needed * 0.05
            candidates.append((score, tgt, ships_needed, dist))

        if not candidates:
            continue

        candidates.sort(key=lambda c: -c[0])

        for score, tgt, ships_needed, dist in candidates:
            if available < ships_needed:
                continue  # can't afford it, try next

            tid, _, tx, ty, tradius, tships, tprod = tgt
            turns = travel_time(dist, ships_needed)
            ftx, fty = planet_future_pos(tgt, int(turns), angular_velocity)

            angle = math.atan2(fty - sy, ftx - sx)

            if will_hit_sun(sx, sy, angle, dist):
                continue  # skip paths through sun

            moves.append([sid, angle, ships_needed])
            available -= ships_needed
            break  # one move per source planet per turn

    return moves
