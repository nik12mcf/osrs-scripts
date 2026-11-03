"""Click through a recorded course, waiting for each step to show up on screen."""

import math
import random
import time
from pathlib import Path

import cv2

from . import config, mouse
from .course import Course, Step
from .controls import Controls, game_in_front
from .screen import Screen


class Runner:
    def __init__(self, course: Course, screen: Screen, controls: Controls, debug_dir: Path):
        self.course = course
        self.debug_dir = debug_dir
        self.screen = screen
        self.controls = controls
        self.player = course.player or screen.center()

    @property
    def stopped(self) -> bool:
        return self.controls.stop.is_set()

    def run(self, laps: int = 0):
        """laps = 0 runs until the stop key is pressed."""
        steps = self.course.steps
        lap = 0

        # You might not be at the start, for example after recording or stopping mid-lap
        print("Looking for where you are on the course...")
        index = self.resync()
        if index is None:
            if not self.stopped:
                print("Couldn't see any step of the course. Stand at the start with the camera set like when you recorded.")
                self.save_debug(0)
            return
        print(f"Starting from step {index + 1}")

        while not self.stopped and (laps == 0 or lap < laps):
            step = steps[index]
            previous = steps[index - 1]

            self.position_mouse_for(step)

            target = self.wait_until_ready(step, timeout=previous.delay * 1.5 + 5)

            if target and config.COLLECT_MARKS:
                mark = self.grab_mark()
                if mark:
                    target = self.return_after_mark(step, mark)

            if target is None:
                if self.stopped:
                    break

                print(f"Step {index + 1} never showed up, maybe you fell.")
                self.save_debug(index)
                print("Looking for where you are...")
                found = self.resync()
                if found is None:
                    if not self.stopped:
                        print("Couldn't work out where you are. Get back to the course start and run again.")
                        print("\a", end="", flush=True)
                    break

                print(f"Found step {found + 1}, carrying on")
                index = found
                continue

            if self.stopped:
                break

            if not self.click(*mouse.jitter(*target)):
                continue  # Paused, so check this step again
            if not self.controls.wait(random.uniform(0.6, 0.9)):  # Give the character a tick to start moving
                break

            index += 1
            if index == len(steps):
                index = 0
                lap += 1
                print(f"Lap {lap} complete")
                self.maybe_take_break()

        print(f"Stopped after {lap} laps")

    def find(self, step: Step, radius: int, max_offset: int | None) -> tuple[int, int] | None:
        found = self.screen.find_template(step.template, step.x, step.y, radius, step.mask)
        if found and max_offset is not None and math.dist(found, (step.x, step.y)) > max_offset:
            return None
        return found

    def wait_until_ready(
        self,
        step: Step,
        timeout: float,
        radius: int = config.SEARCH_RADIUS,
        max_offset: int | None = config.READY_MAX_OFFSET,
    ) -> tuple[int, int] | None:
        """Wait until the step is on screen and has stopped moving, and return where it is."""
        end = time.monotonic() + timeout
        last = None
        stable = 0

        while time.monotonic() < end:
            found = self.find(step, radius, max_offset)
            if found and last and math.dist(found, last) <= 2:
                stable += 1
            else:
                stable = 1 if found else 0
            last = found

            if stable >= config.STABLE_FRAMES:
                return found

            if not self.controls.wait(0.06):
                return None

        return None

    def save_debug(self, index: int):
        """Explain why a step wasn't found, and save what it was looking for next to what it saw."""
        step = self.course.steps[index]
        self.position_mouse_for(step)
        point, score, capture = self.screen.best_match(step.template, step.x, step.y, config.SEARCH_RADIUS, step.mask)
        offset = (point[0] - step.x, point[1] - step.y)
        print(f"  Best match was {score:.2f} (needs {config.MATCH_THRESHOLD}), {math.dist(point, (step.x, step.y)):.0f}px "
              f"from the recorded spot (allowed {config.READY_MAX_OFFSET}), offset {offset}")

        # Draw the recorded spot in red and the best match in green on what the screen looked like
        image = capture.image.copy()
        half_width, half_height = step.template.shape[1] // 2, step.template.shape[0] // 2
        for (x, y), color in (((step.x, step.y), (0, 0, 255)), (point, (0, 255, 0))):
            px, py = round((x - capture.left) * capture.scale), round((y - capture.top) * capture.scale)
            cv2.rectangle(image, (px - half_width, py - half_height), (px + half_width, py + half_height), color, 2)

        self.debug_dir.mkdir(parents=True, exist_ok=True)
        name = f"step_{index + 1:02}"
        expected = step.template.copy()
        if step.mask is not None:
            expected[step.mask == 0] //= 4  # Darken the part that's ignored
        cv2.imwrite(str(self.debug_dir / f"{name}_expected.png"), expected)
        cv2.imwrite(str(self.debug_dir / f"{name}_seen.png"), image)
        print(f"  Saved {name}_expected.png and {name}_seen.png to {self.debug_dir}")

    def resync(self) -> int | None:
        """Look for any step that looks ready, for after a fall."""
        end = time.monotonic() + config.RESYNC_TIMEOUT

        steps = list(enumerate(self.course.steps))
        clean = [(i, step) for i, step in steps if not step.hovered]
        hovered = [(i, step) for i, step in steps if step.hovered]

        while time.monotonic() < end:
            # Steps recorded with the mouse out of the way can all be checked at once
            self.move_mouse_clear_of([step for _, step in clean])
            for i, step in clean:
                if self.find(step, config.SEARCH_RADIUS, config.READY_MAX_OFFSET):
                    return i

            # The rest need the mouse on them, like when they were recorded
            for i, step in hovered:
                self.position_mouse_for(step)
                if not self.controls.wait(0.1):  # Give RuneLite a moment to draw the tooltip
                    return None
                if self.find(step, config.SEARCH_RADIUS, config.READY_MAX_OFFSET):
                    return i

            if not self.controls.wait(0.3):
                return None

        return None

    def click(self, x: int, y: int) -> bool:
        """Click, unless the game isn't in front (so the click would land somewhere else).
        Then wait until it is, and return False because things may have changed meanwhile."""
        if not game_in_front():
            print("Paused because the game isn't in front. Click on it to carry on.")
            while not self.stopped and not game_in_front():
                self.controls.wait(0.3)
            self.controls.wait(0.5)
            return False

        mouse.click_at(x, y)
        return True

    def marks(self) -> list[tuple[int, int]]:
        return self.screen.find_color(config.MARK_COLOR, *self.player, config.MARK_MAX_DISTANCE)

    def grab_mark(self) -> tuple[int, int] | None:
        """Pick up the closest mark of grace if one is visible, and return where it was."""
        marks = self.marks()
        if not marks:
            return None

        print("Picking up a mark of grace")
        if not self.click(*mouse.jitter(*marks[0], amount=2)):
            return None
        self.controls.wait(random.uniform(0.6, 0.9))

        # Wait for it to disappear from the ground
        end = time.monotonic() + 10
        while time.monotonic() < end and len(self.marks()) >= len(marks):
            if not self.controls.wait(0.15):
                break

        self.controls.wait(random.uniform(0.3, 0.6))
        return marks[0]

    def return_after_mark(self, step: Step, mark: tuple[int, int]) -> tuple[int, int] | None:
        """We're standing where the mark was now, so the step isn't where it was recorded."""
        if not step.hovered:  # Can't hover over it without knowing where it's moved to
            self.move_mouse_clear_of([step])
            found = self.wait_until_ready(step, timeout=3, radius=config.MARK_SEARCH_RADIUS, max_offset=None)
            if found:
                return found

        # Can't see it (or it's a patch of ground, which looks much the same everywhere).
        # Walk back to where we were. The camera follows us, so that spot is now as far
        # from us as the mark was, in the other direction.
        px, py = self.player
        print("Walking back to where we were before the mark")
        if not self.click(*mouse.jitter(2 * px - mark[0], 2 * py - mark[1], amount=2)):
            return None
        self.controls.wait(random.uniform(0.6, 0.9))
        self.position_mouse_for(step)
        return self.wait_until_ready(step, timeout=8)

    def position_mouse_for(self, step: Step):
        """Put the mouse where it was when the step's picture was taken: on it, or out of the way."""
        if not step.hovered:
            self.move_mouse_clear_of([step])
        elif mouse.position() != (step.x, step.y):
            mouse.move_to(step.x, step.y)

    def move_mouse_clear_of(self, steps: list[Step]):
        """Get the mouse and its tooltip out of the way of these steps, so the screen looks like the recording."""
        points = [(step.x, step.y) for step in steps]
        half = config.TEMPLATE_SIZE // 2
        tooltip_height = config.TOOLTIP_SIZE[1]

        # Stay put if already out of the way, otherwise try just above or below each step
        candidates = [mouse.position()]
        for x, y in points:
            candidates += [mouse.jitter(x, y - half - tooltip_height - 20), mouse.jitter(x, y + half + 20)]

        bounds = self.screen.bounds
        on_screen = [
            (x, y) for x, y in candidates
            if bounds["left"] + 20 <= x < bounds["left"] + bounds["width"] - 20
            and bounds["top"] + 20 <= y < bounds["top"] + bounds["height"] - 20
        ]
        if not on_screen:
            return

        # The first spot that's clear of the most steps
        best = max(on_screen, key=lambda cursor: sum(mouse.clear_of(cursor, point) for point in points))
        if best != mouse.position():
            mouse.move_to(*best)

    def maybe_take_break(self):
        if random.random() < config.BREAK_CHANCE:
            seconds = random.uniform(*config.BREAK_SECONDS)
            print(f"Taking a {seconds:.0f}s break")
            self.controls.wait(seconds)
