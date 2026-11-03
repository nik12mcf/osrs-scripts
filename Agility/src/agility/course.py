"""Recorded courses, saved as a folder with course.json and a picture per step."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Step:
    x: int
    y: int
    delay: float  # Seconds it took to reach the next step while recording
    template: np.ndarray  # What the screen around (x, y) looked like when it was ready to click
    # If the picture had to be taken with the mouse on the spot, this hides the tooltip (0 = ignore)
    # and the run hovers on the spot so the rest looks the same
    mask: np.ndarray | None = None

    @property
    def hovered(self) -> bool:
        return self.mask is not None


@dataclass
class Course:
    steps: list[Step] = field(default_factory=list)
    player: tuple[int, int] | None = None  # Where your character is on screen at the start


def save(course: Course, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    for old in [*folder.glob("obstacle_*.png"), *folder.glob("step_*.png")]:
        old.unlink()

    steps = []
    for i, step in enumerate(course.steps, start=1):
        image = f"step_{i:02}.png"
        picture = step.template if step.mask is None else np.dstack([step.template, step.mask])  # Mask as transparency
        cv2.imwrite(str(folder / image), picture)
        steps.append({"x": step.x, "y": step.y, "delay": round(step.delay, 3), "image": image})

    data = {"player": course.player, "steps": steps}
    (folder / "course.json").write_text(json.dumps(data, indent=2))


def load(folder: Path) -> Course:
    data = json.loads((folder / "course.json").read_text())
    if "steps" not in data:
        raise ValueError(f"{folder} was recorded with an older version, record it again")

    steps = []
    for item in data["steps"]:
        picture = cv2.imread(str(folder / item["image"]), cv2.IMREAD_UNCHANGED)
        if picture is None:
            raise FileNotFoundError(folder / item["image"])
        template, mask = (picture[:, :, :3], picture[:, :, 3]) if picture.shape[2] == 4 else (picture, None)
        steps.append(Step(item["x"], item["y"], item["delay"], np.ascontiguousarray(template), mask))

    player = tuple(data["player"]) if data.get("player") else None
    return Course(steps, player)
