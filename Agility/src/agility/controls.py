"""Watching for the stop key, the stop corner, which app is in front, and your clicks while recording."""

import queue
import sys
import threading
import time
from dataclasses import dataclass

from pynput import keyboard
from pynput import mouse as pynput_mouse

from . import config, mouse


def front_window_name() -> str | None:
    """Name of the app (macOS) or window (Windows) in front, or None if we can't tell."""
    if sys.platform == "darwin":
        import Quartz

        options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        for window in Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []:
            if window.get("kCGWindowLayer") == 0:  # Normal windows, front to back
                return window.get("kCGWindowOwnerName")
        return None

    if sys.platform == "win32":
        import ctypes

        user32 = ctypes.windll.user32
        window = user32.GetForegroundWindow()
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(window, title, 512)
        return title.value

    return None


def game_in_front() -> bool:
    name = front_window_name()
    if name is None:
        return True  # Can't tell on this system, so assume it is
    return any(game in name.lower() for game in config.GAME_WINDOW_NAMES)


@dataclass
class Click:
    x: int
    y: int
    time: float  # time.monotonic()


class Controls:
    def __init__(self, watch_clicks: bool = False):
        self.stop = threading.Event()
        self.clicks: queue.Queue[Click] = queue.Queue()
        self.ignore_clicks_until = 0.0

        self._listeners = [keyboard.Listener(on_press=self._on_key)]
        if watch_clicks:
            self._listeners.append(pynput_mouse.Listener(on_click=self._on_click))
        for listener in self._listeners:
            listener.start()

    def _on_key(self, key):
        if getattr(key, "name", None) == config.STOP_KEY or getattr(key, "char", None) == config.STOP_KEY:
            self.stop.set()

    def _on_click(self, x, y, button, pressed):
        now = time.monotonic()
        if pressed and button == pynput_mouse.Button.left and now >= self.ignore_clicks_until and game_in_front():
            self.clicks.put(Click(round(x), round(y), now))

    def in_stop_corner(self) -> bool:
        x, y = mouse.position()
        return x <= config.STOP_CORNER_SIZE and y <= config.STOP_CORNER_SIZE

    def wait(self, seconds: float) -> bool:
        """Sleep, returning False early if you asked to stop."""
        end = time.monotonic() + seconds
        while True:
            if self.in_stop_corner():
                self.stop.set()
            if self.stop.wait(min(0.05, max(0.0, end - time.monotonic()))):
                return False
            if time.monotonic() >= end:
                return True

    def wait_for_game(self, message: str) -> bool:
        """Wait until the game window is in front. Returns False if you stopped instead."""
        if game_in_front():
            return True

        print(message)
        while not game_in_front():
            if not self.wait(0.2):
                return False

        # Ignore the click that brought it to the front
        self.ignore_clicks_until = time.monotonic() + 0.5
        return self.wait(0.5)

    def close(self):
        for listener in self._listeners:
            listener.stop()
