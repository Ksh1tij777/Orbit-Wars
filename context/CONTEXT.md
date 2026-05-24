# Orbit Wars — Project Context

## Game Overview
- **Type:** Space strategy game on a 100×100 grid
- **Players:** Up to 4 (IDs: 0, 1, 2, 3)
- **Win condition:** Most ships (planets + fleets) when time runs out, OR be the last player alive
- **Total steps per game:** 240

### Game Mechanics
| Element | Behaviour |
|---------|-----------|
| Planets | Produce ships every turn. Bigger radius = more production. Owner -1 = neutral |
| Fleets | Fly in a straight line. Speed = `min(6, 1 + ships * 0.05)`. Bigger = faster |
| Combat | Fleet arrives → ships subtracted from garrison. Garrison ≤ 0 → you own it |
| Sun | At (50, 50). Any fleet flying through it is destroyed |
| Inner planets | Orbit the sun (dist < ~30). Use `angular_velocity` to predict future position |
| Outer planets | Stay still |
| Comets | Temporary bonus planets flying through the map |

### `obs` Object (what the agent receives each turn)
| Field | Type | Description |
|-------|------|-------------|
| `obs.player` | int | Your player ID (0–3) |
| `obs.planets` | list | `[id, owner, x, y, radius, ships, production]` |
| `obs.fleets` | list | `[id, owner, x, y, angle, from_planet_id, ships]` |
| `obs.angular_velocity` | float | Radians/turn for inner orbiting planets |

### Agent Return Format
A list of moves: `[[from_planet_id, angle_in_radians, num_ships], ...]`

---

## Repository
- **GitHub:** https://github.com/Ksh1tij777/Orbit-Wars
- **Local path:** `C:\Users\Kshitij verma\orbit-wars\`
- **Main agent file:** `main.py`

---

## Session Log

### Session 2 — v2 Agent Rewrite (2026-05-24)

#### Changes Made
Complete rewrite of `main.py`. Key additions:

| Change | Detail |
|--------|--------|
| **Two-phase logic** | Phase 1 = Defense, Phase 2 = Expansion/Attack |
| **`fleet_aims_at()`** | Detects if any fleet's trajectory passes within 6 units of a planet using perpendicular distance math (replaces broken `enemy_ships_incoming`) |
| **`get_garrison(ships, turn)`** | 15% early game, 30% late game |
| **`committed_from / committed_to`** | Tracks ships dispatched per source and per target in the same turn — prevents double-spending |
| **Multi-target per planet** | Removed `break` — each planet keeps sending until ships run out |
| **`score_neutral()` / `score_enemy()`** | Proper scoring with early-game 1.5× expansion bonus |
| **`MIN_FLEET = 10`** | No more useless 5-ship fleets |
| **Global `_turn` counter** | Used to switch garrison ratio at turn 40 |

---

### Session 1 — Initial Setup
**Date:** 2026-05-24

#### What was built
- Created `main.py` with a baseline agent using the following strategy:
  - Hold back 30% of ships as garrison (`GARRISON_RATIO = 0.3`)
  - Score targets by `production / distance`
  - Neutrals prioritised over enemy planets
  - Predict future position of orbiting (inner) planets
  - Skip fleet paths that pass through the sun
  - One move per owned planet per turn

#### Test Result
- Ran locally vs `random` bot
- **Player 0 (us): reward = -1 (LOSS)**
- **Player 1 (random): reward = +1 (WIN)**

#### Replay Analysis (Step 66/240)
Observed via `replay.html`:
- Blue (us) stuck in bottom-left with 3 small planets (20, 12, 9 ships)
- Orange (random) dominated with 5+ planets (40, 28, 23, 17, 64 ships)
- We were sending many tiny fleets of 5–8 ships — too weak to capture anything
- Some tiny fleets heading near the sun (likely destroyed)

---

## Bugs Identified

| # | Bug | Location | Impact |
|---|-----|----------|--------|
| 1 | `enemy_ships_incoming()` defined but never called | `main.py:42` | Zero defense — we never reinforce threatened planets |
| 2 | `break` after first valid target — idle ships left behind | `main.py:109` | Ships sit idle instead of being sent to secondary targets |
| 3 | `ships_needed = tships + 1` — no capture buffer | `main.py:76` | Fleets barely capture, leaving planets with 1 ship garrison |
| 4 | No minimum fleet size — sends 5-ship fleets | `main.py:107` | Tiny fleets crawl slowly and achieve nothing |
| 5 | Static 30% garrison from turn 1 | `main.py:65` | Slow early expansion, enemy grabs neutrals first |

---

## Planned Improvements

### v2 — Core Fixes ✅ SHIPPED (2026-05-24)
- [x] `MIN_FLEET = 10` — never send fewer than 10 ships
- [x] Remove `break` — loop and send to multiple targets per turn using remaining ships
- [x] Dynamic garrison: **15% turns 0–40**, **30% turns 40+** via `get_garrison()`
- [x] Wire in defense: `fleet_aims_at()` detects trajectories, reinforcements auto-dispatched
- [x] Capture buffer: `ships_needed = tships + CAPTURE_BUFFER(5)` for neutrals
- [x] `committed_from` / `committed_to` dicts prevent over-committing same ships twice
- [x] Improved target scoring functions: `score_neutral()` and `score_enemy()` with early-game bonus
- [x] `fleet_aims_at()` uses perpendicular distance (more accurate than angle threshold)

### v3 — Strategy Upgrades (Future)
- [ ] Multi-planet coordination: gang up multiple planets on one target
- [ ] Threat scoring: prioritise defending high-production planets
- [ ] Comet targeting: detect and intercept bonus comets
- [ ] Avoid sending to already-targeted planets (deduplicate targets across source planets)

---

## Key Formulas

```python
# Fleet speed
speed = min(6, 1 + num_ships * 0.05)

# Travel time
turns = distance / speed

# Future position of orbiting planet
angle_future = atan2(y - 50, x - 50) + angular_velocity * turns
future_x = 50 + dist_to_sun * cos(angle_future)
future_y = 50 + dist_to_sun * sin(angle_future)

# Aim angle
angle = atan2(target_y - source_y, target_x - source_x)

# Ships needed to capture enemy planet
ships_needed = current_ships + (production * travel_turns) + buffer
```

---

## File Structure
```
orbit-wars/
├── main.py          # Agent (submitted to Kaggle)
├── context/
│   └── CONTEXT.md   # This file — living project context
└── replay.html      # Last local test replay (not committed)
```
