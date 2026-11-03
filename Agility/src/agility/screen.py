"""Screen capture and finding things on screen.

Everything in and out of here is in mouse coordinates. Captures can be at a higher
resolution than that (Retina, display scaling), so positions get converted back.
"""

import math
from dataclasses import dataclass

import cv2
import mss
import numpy as np

from . import config


@dataclass
class Capture:
    image: np.ndarray  # BGR
    left: int
    top: int
    scale: float  # Image pixels per mouse pixel

    def to_screen(self, px: float, py: float) -> tuple[int, int]:
        return round(self.left + px / self.scale), round(self.top + py / self.scale)

    def to_image(self, x: float, y: float) -> tuple[int, int]:
        return round((x - self.left) * self.scale), round((y - self.top) * self.scale)

    def crop(self, x: int, y: int, size: int) -> np.ndarray | None:
        """The size x size square around (x, y), or None if it isn't all in this capture."""
        left, top = self.to_image(x - size / 2, y - size / 2)
        right, bottom = self.to_image(x + size / 2, y + size / 2)
        if left < 0 or top < 0 or right > self.image.shape[1] or bottom > self.image.shape[0]:
            return None
        return self.image[top:bottom, left:right].copy()

    def best_match(self, template: np.ndarray, mask: np.ndarray | None = None) -> tuple[tuple[int, int], float]:
        """Where the middle of template best matches in this capture, and how well (-1 to 1).
        Parts of the template where mask is 0 are ignored."""
        if self.image.shape[0] < template.shape[0] or self.image.shape[1] < template.shape[1]:
            return (self.left, self.top), -1.0

        result = cv2.matchTemplate(self.image, template, cv2.TM_CCOEFF_NORMED, mask=mask)
        result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)  # Masked matching can divide by zero
        _, score, _, (px, py) = cv2.minMaxLoc(result)
        return self.to_screen(px + template.shape[1] / 2, py + template.shape[0] / 2), score


class Screen:
    def __init__(self):
        self._mss = mss.MSS()
        self.bounds = self._mss.monitors[0]  # All monitors combined

    def center(self) -> tuple[int, int]:
        main = self._mss.monitors[1]
        return main["left"] + main["width"] // 2, main["top"] + main["height"] // 2

    def grab(self, left: int, top: int, width: int, height: int) -> Capture:
        # Keep the region on screen
        right = min(left + width, self.bounds["left"] + self.bounds["width"])
        bottom = min(top + height, self.bounds["top"] + self.bounds["height"])
        left = max(left, self.bounds["left"])
        top = max(top, self.bounds["top"])

        shot = self._mss.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
        image = np.ascontiguousarray(np.asarray(shot)[:, :, :3])
        return Capture(image, left, top, shot.width / (right - left))

    def grab_around(self, x: int, y: int, radius: int) -> Capture:
        return self.grab(x - radius, y - radius, radius * 2, radius * 2)

    def best_match(
        self, template: np.ndarray, x: int, y: int, radius: int, mask: np.ndarray | None = None
    ) -> tuple[tuple[int, int], float, Capture]:
        """Where template best matches on screen around (x, y), and how well (-1 to 1)."""
        capture = self.grab_around(x, y, radius + config.TEMPLATE_SIZE // 2)
        return *capture.best_match(template, mask), capture

    def find_template(
        self, template: np.ndarray, x: int, y: int, radius: int, mask: np.ndarray | None = None
    ) -> tuple[int, int] | None:
        """Where the middle of template is on screen, searching around (x, y)."""
        point, score, _ = self.best_match(template, x, y, radius, mask)
        return point if score >= config.MATCH_THRESHOLD else None

    def find_color(self, rgb: tuple[int, int, int], x: int, y: int, radius: int) -> list[tuple[int, int]]:
        """Middles of every highlight of this colour within radius of (x, y), closest first."""
        capture = self.grab_around(x, y, radius)
        bgr = np.array(rgb[::-1], dtype=np.int16)
        mask = np.all(np.abs(capture.image.astype(np.int16) - bgr) <= config.COLOR_TOLERANCE, axis=2)

        # Join up small gaps in outlines so each highlight is one blob
        joined = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8))
        count, labels, _, centroids = cv2.connectedComponentsWithStats(joined)

        found = []
        for label in range(1, count):
            if np.count_nonzero(mask[labels == label]) < config.MIN_HIGHLIGHT_SIZE:
                continue
            point = capture.to_screen(*centroids[label])
            if math.dist(point, (x, y)) <= radius:
                found.append(point)

        return sorted(found, key=lambda point: math.dist(point, (x, y)))
