"""OSRS agility trainer: record a course once, then replay it."""

import argparse
import sys
import time

from . import config
from .course import load, save
from .controls import Controls
from .recorder import record
from .runner import Runner
from .screen import Screen


def use_real_pixels():
    """On Windows with display scaling, make mouse and screen coordinates line up."""
    if sys.platform == "win32":
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def main():
    parser = argparse.ArgumentParser(prog="agility", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    record_parser = commands.add_parser("record", help="Record a course by doing a lap")
    record_parser.add_argument("course", help="Name to save the course as, e.g. canifis")

    run_parser = commands.add_parser("run", help="Run a recorded course")
    run_parser.add_argument("course", help="Name of a recorded course")
    run_parser.add_argument("laps", nargs="?", type=int, default=0, help="Laps to run (default: until stopped)")

    args = parser.parse_args()
    folder = config.COURSES_DIR / args.course

    use_real_pixels()
    screen = Screen()
    stop_hint = f"Press {config.STOP_KEY.capitalize()} or move the mouse to the top-left corner to stop."

    if args.command == "run":
        if not (folder / "course.json").exists():
            sys.exit(f"No course recorded at {folder}, run: agility record {args.course}")
        course = load(folder)
        print(f"Loaded {len(course.steps)} steps from {folder}")

    controls = Controls(watch_clicks=args.command == "record")
    try:
        if args.command == "record":
            print("Stand at the start of the course with the camera set how you'll run it.")
            print("  1. Click on your character (used to find marks of grace).")
            print("  2. Do a lap. Wait until you've stopped moving before each click, and only click the course.")
            print(f"  3. When you're back at the start, press {config.STOP_KEY.capitalize()} to save.")
            print("Don't pick up marks of grace while recording. " + stop_hint)
            controls.ignore_clicks_until = time.monotonic() + 0.5
            if controls.wait_for_game("Click on the game window to start (make sure nothing is covering it)."):
                print("Recording, click on your character.")
                course = record(screen, controls)
                if course:
                    save(course, folder)
                    print(f"Saved course to {folder}")

        else:
            print(stop_hint)
            if controls.wait_for_game("Click on the game window to start (make sure nothing is covering it)."):
                Runner(course, screen, controls, folder / "debug").run(args.laps)
    except KeyboardInterrupt:
        print("Stopped")
    finally:
        controls.close()
