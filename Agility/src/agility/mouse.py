"""Mouse movement that doesn't teleport or click the same pixel every time."""

import math
import random
import time

from pynput.mouse import Button, Controller

from . import config

_mouse = Controller()


def position() -> tuple[int, int]:
    x, y = _mouse.position
    return round(x), round(y)


def clear_of(cursor: tuple[int, int], point: tuple[int, int]) -> bool:
    """Whether the mouse at cursor, and the tooltip beside it, are outside the picture around point."""
    half = config.TEMPLATE_SIZE / 2
    tooltip_width, tooltip_height = config.TOOLTIP_SIZE
    cx, cy = cursor
    px, py = point
    return cx - 5 > px + half or cx + tooltip_width < px - half or cy - 5 > py + half or cy + tooltip_height < py - half


def jitter(x: int, y: int, amount: int = 4) -> tuple[int, int]:
    return x + random.randint(-amount, amount), y + random.randint(-amount, amount)


def move_to(x: int, y: int):
    start_x, start_y = position()
    dx, dy = x - start_x, y - start_y
    distance = math.hypot(dx, dy)
    steps = max(5, int(distance / random.uniform(15, 25)))

    # Bend the path slightly to one side
    bend = random.uniform(-0.15, 0.15) * distance

    for i in range(1, steps + 1):
        t = i / steps
        ease = t * t * (3 - 2 * t)
        offset = math.sin(t * math.pi) * bend

        px = start_x + dx * ease
        py = start_y + dy * ease
        if distance > 0:
            px += -dy / distance * offset
            py += dx / distance * offset

        _mouse.position = (px, py)
        time.sleep(random.uniform(0.005, 0.012))

    _mouse.position = (x, y)


def click():
    # The with block makes this count as a click. Without it macOS sends a click count of 0,
    # which Java apps like RuneLite ignore.
    with _mouse as controller:
        controller.press(Button.left)
        time.sleep(random.uniform(0.03, 0.09))
        controller.release(Button.left)


def click_at(x: int, y: int):
    move_to(x, y)
    time.sleep(random.uniform(0.04, 0.12))
    click()
