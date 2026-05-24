from kaggle_environments import make

env = make("orbit_wars", debug=True)
env.run(["main.py", "random"])

# Option 1 — save as HTML and open in browser
with open("replay.html", "w") as f:
    f.write(env.render(mode="html"))

# Option 2 — print each step's state
for step_num, step in enumerate(env.steps):
    print(f"\n--- Turn {step_num} ---")
    for player_i, obs in enumerate(step):
        print(f"  Player {player_i}: reward={obs.reward}, status={obs.status}")