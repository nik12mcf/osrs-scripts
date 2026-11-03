# Agility

Records an agility course once, then runs laps of it for you. Works for any course (rooftops, Gnome Stronghold, etc.) and on Windows and macOS.

It reads the screen rather than relying on timings. You record by doing a lap normally, and it saves a small picture of the screen everywhere you click. When it runs, it waits until each picture shows up in the same spot and stops moving, which means your character has landed, then clicks it. It also picks up marks of grace that the RuneLite Agility plugin highlights.

## Setup

Install [uv](https://docs.astral.sh/uv/), then from this folder:

```
uv sync
```

**macOS:** give your terminal app **Accessibility**, **Input Monitoring** and **Screen Recording** permission in System Settings → Privacy & Security, then restart the terminal.

## RuneLite setup (for marks of grace)

In the **Agility** plugin config, turn on mark of grace highlighting and set its colour to pure magenta `#FF00FF`. If you use another colour, change `MARK_COLOR` in `src/agility/config.py`. To skip marks, set `COLLECT_MARKS = False`.

## Record a course

1. Stand at the start of the course. Set the camera how you want to run it: compass facing north (click the compass), camera fully up (hold the up arrow), and a fixed zoom.
2. Run `uv run agility record canifis`, then click on the game window. Make sure nothing (like the terminal) covers any part of the game.
3. Click on your character.
4. Do a lap, clicking obstacles and the ground like normal. **Wait until your character has stopped moving before each click.** Accidental double-clicks are ignored.
5. When you're back at the start, press **Esc** to save.

The course is saved in `courses/canifis/` (not committed to git, since it contains screenshots of your game). Don't pick up marks of grace while recording, and try to only click in the game view. Minimap and interface clicks can work, but they're less reliable.

## Run

```
uv run agility run canifis        # runs until you stop it
uv run agility run canifis 50     # runs 50 laps
```

Click on the game window to start, and keep it uncovered. If another app comes to the front, the script pauses rather than clicking into it, and carries on once the game is back in front. You don't have to be at the start: it looks for whichever step it can see and carries on from there.

**To stop**, press **Esc** or move the mouse into the top-left corner of the screen.

## What happens if you fail an obstacle

If the next step doesn't show up in time, the script prints how close the best match was and saves `step_NN_expected.png` (what it was looking for) and `step_NN_seen.png` (what was on screen) to `courses/<name>/debug/`. Then it looks for any recorded step on screen for 10 seconds and carries on from the one it finds. If it can't find one (for example, you fell off and need to walk back), it beeps and stops.

## Tuning

All the settings are in `src/agility/config.py`:

- `MATCH_THRESHOLD`: lower it if steps are never found, and raise it if it clicks the wrong thing.
- `READY_MAX_OFFSET`: how far from the recorded spot a step can be and still count as "you've landed".
- `MARK_MAX_DISTANCE`: how far from your character a mark can be and still get picked up. Lower it if it tries to grab marks on other rooftops.

## Limitations

- Keep the game window in the same place and at the same size, and don't change the camera or zoom after recording. If you do, record again.
- Things that cover a step (other players, weather) can stop it being found. The script then times out and tries to resync.
