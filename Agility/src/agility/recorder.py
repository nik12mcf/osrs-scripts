"""Teach the script a course by doing a lap while it watches your clicks."""

import math
import queue
import time
from collections import deque

import cv2
import numpy as np

from . import config, mouse
from .controls import Click, Controls
from .course import Course, Step
from .screen import Capture, Screen


Frame = tuple[float, tuple[int, int], Capture]  # When, where the mouse was, what the screen looked like


def outside_tooltip(shape: tuple[int, ...], cursor: tuple[int, int], click: Click, size: int, scale: float) -> np.ndarray:
    """For a size x size picture around the click, True everywhere except where the tooltip
    beside the mouse could be."""
    left, top = click.x - size / 2, click.y - size / 2
    tooltip_width, tooltip_height = config.TOOLTIP_SIZE
    x1, y1 = max(0, round((cursor[0] - 5 - left) * scale)), max(0, round((cursor[1] - 5 - top) * scale))
    x2, y2 = max(0, round((cursor[0] + tooltip_width - left) * scale)), max(0, round((cursor[1] + tooltip_height - top) * scale))
    keep = np.ones(shape[:2], bool)
    keep[y1:y2, x1:x2] = False
    return keep


def unaffected_by_mouse(shape: tuple[int, ...], cursor: tuple[int, int], center: tuple[int, int], size: int, scale: float) -> np.ndarray:
    """For a size x size picture around center, 255 where the mouse at cursor can't have changed
    anything, and 0 over its tooltip and whatever's under it (RuneLite darkens that)."""
    keep = outside_tooltip(shape, cursor, Click(center[0], center[1], 0), size, scale)
    half = config.TEMPLATE_SIZE / 2
    left, top = center[0] - size / 2, center[1] - size / 2
    x1, y1 = max(0, round((cursor[0] - half - left) * scale)), max(0, round((cursor[1] - half - top) * scale))
    x2, y2 = max(0, round((cursor[0] + half - left) * scale)), max(0, round((cursor[1] + half - top) * scale))
    keep[y1:y2, x1:x2] = False
    return keep.astype(np.uint8) * 255


def same_scene(capture: Capture, reference: Capture, click: Click, cursor: tuple[int, int]) -> bool:
    """Whether two screenshots show the camera in the same place around the click, ignoring
    the tooltip beside the mouse in reference."""
    size = config.TEMPLATE_SIZE * 2
    a = capture.crop(click.x, click.y, size)
    b = reference.crop(click.x, click.y, size)
    if a is None or b is None or a.shape != b.shape:
        return False

    # Compare the pattern rather than raw pixel differences, so flat areas (sand, sky) don't
    # make a moving camera look still. Leave out what the mouse changes in reference.
    mask = unaffected_by_mouse(b.shape, cursor, (click.x, click.y), size, reference.scale)
    score = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED, mask=mask)[0, 0]
    return bool(np.nan_to_num(score, nan=-1.0) >= config.SAME_SCENE_THRESHOLD)


def template_before(
    frames: deque[Frame], click: Click
) -> tuple[np.ndarray, np.ndarray | None, Capture, tuple[Capture, tuple[int, int]]] | None:
    """The picture around the click from just before the mouse got there, so nothing the
    mouse causes (tooltip, darker highlight, click cross) is in it.

    If the mouse was already there when you landed, it uses the picture with the mouse in
    it instead, and returns a mask that hides the tooltip. Also returns the screenshot the
    picture came from, and the latest one before the click (with the mouse on the spot) along
    with where the mouse was in it."""
    before = [frame for frame in frames if frame[0] <= click.time - config.RECORD_FRAME_AGE]
    if not before:
        return None
    _, latest_cursor, latest = before[-1]

    for _, cursor, capture in reversed(before):
        if not mouse.clear_of(cursor, (click.x, click.y)):
            continue
        if not same_scene(capture, latest, click, latest_cursor):
            break  # From before you landed, and older ones will be too
        template = capture.crop(click.x, click.y, config.TEMPLATE_SIZE)
        if template is not None:
            return template, None, capture, (latest, latest_cursor)

    template = latest.crop(click.x, click.y, config.TEMPLATE_SIZE)
    if template is None:
        return None
    mask = outside_tooltip(template.shape, latest_cursor, click, config.TEMPLATE_SIZE, latest.scale)
    return template, mask.astype(np.uint8) * 255, latest, (latest, latest_cursor)


def is_first_step_again(course: Course, click: Click, captures: list[Capture]) -> bool:
    """Clicking the first obstacle again from the same spot means the lap is done. Checks each
    screenshot, since the first step may have been recorded with or without the mouse on it.
    This can miss (for example if one has the mouse in it and the other doesn't), so Esc
    finishes too."""
    if len(course.steps) < 2:
        return False

    first = course.steps[0]
    if math.dist((click.x, click.y), (first.x, first.y)) > config.READY_MAX_OFFSET:
        return False

    for capture in captures:
        point, score = capture.best_match(first.template, first.mask)
        if score >= config.MATCH_THRESHOLD and math.dist(point, (first.x, first.y)) <= config.READY_MAX_OFFSET:
            return True
    return False


def record(screen: Screen, controls: Controls) -> Course | None:
    """Returns None if you stop before recording anything."""
    course = Course()
    frames: deque[Frame] = deque(maxlen=config.RECORD_FRAMES)
    last_click = 0.0

    while not controls.stop.is_set():
        x, y = mouse.position()
        frames.append((time.monotonic(), (x, y), screen.grab_around(x, y, config.RECORD_FRAME_RADIUS)))

        while True:
            try:
                click = controls.clicks.get_nowait()
            except queue.Empty:
                break

            if course.player is None:
                course.player = (click.x, click.y)
                print(f"Character at {course.player}. Now do a lap.")
                continue

            if (
                course.steps
                and click.time - last_click < config.DOUBLE_CLICK_TIME
                and math.dist((click.x, click.y), (course.steps[-1].x, course.steps[-1].y)) < config.DOUBLE_CLICK_DISTANCE
            ):
                print("  (ignored a second click on the same spot)")
                continue

            found = template_before(frames, click)
            if found is None:
                print("  Couldn't get a picture of that spot (too close to the edge of the screen?).")
                print("  Press Esc and record again.")
                continue
            template, mask, capture, (latest, _) = found

            if is_first_step_again(course, click, [capture, latest]):
                course.steps[-1].delay = click.time - last_click
                print(f"Back at the first obstacle, lap recorded with {len(course.steps)} steps.")
                return course

            if course.steps:
                course.steps[-1].delay = click.time - last_click
            course.steps.append(Step(click.x, click.y, 0, template, mask))
            last_click = click.time
            print(f"Step {len(course.steps)} at ({click.x}, {click.y})" + (" (mouse was already on it)" if mask is not None else ""))

        controls.wait(config.RECORD_FRAME_INTERVAL)

    if not course.steps:
        print("Stopped, nothing saved.")
        return None

    # If you clicked the first obstacle again before pressing Esc, that click isn't a new step
    first, last = course.steps[0], course.steps[-1]
    if len(course.steps) > 2 and math.dist((first.x, first.y), (last.x, last.y)) <= config.READY_MAX_OFFSET:
        course.steps.pop()
    else:
        course.steps[-1].delay = time.monotonic() - last_click

    print(f"Saving {len(course.steps)} steps. The last one should take you back to the start.")
    return course
