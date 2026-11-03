# osrs-scripts

Python scripts for Old School RuneScape that read the screen and drive the mouse. Works on Windows and macOS.

## Scripts

- [Agility](Agility/README.md): you record an agility course by doing one lap, then it runs laps for you and picks up marks of grace. Works on any course.

## Quick start

Install [uv](https://docs.astral.sh/uv/), then:

```
cd Agility
uv sync
uv run agility record canifis   # do one lap, press Esc to save
uv run agility run canifis      # press Esc to stop
```

See the [Agility README](Agility/README.md) for setup (macOS permissions, RuneLite settings) and troubleshooting.

## Note

Automating gameplay is against Jagex's rules and can get your account banned. Use at your own risk.
