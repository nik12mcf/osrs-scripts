"""Settings you might want to tweak."""

from pathlib import Path

COURSES_DIR = Path("courses")

# Stopping: press this key (pynput key name), or move the mouse into the top-left corner of the screen
STOP_KEY = "esc"
STOP_CORNER_SIZE = 5  # Pixels

# The game window has to be in front, so nothing covers it and clicks don't land in other apps.
# It counts as the game if the app or window name contains one of these.
GAME_WINDOW_NAMES = ("runelite", "runescape", "osrs")

# Step matching. Each step saves a picture of the screen around where you clicked,
# and the script looks for that picture before clicking.
TEMPLATE_SIZE = 80  # Square size in pixels
MATCH_THRESHOLD = 0.85  # How closely the screen has to match (0-1)
SEARCH_RADIUS = 200  # How far from the recorded spot to look
READY_MAX_OFFSET = 25  # The step has to be this close to where it was recorded to count as "landed"
STABLE_FRAMES = 3  # Matches in a row in the same place before clicking, so we don't click while moving
RESYNC_TIMEOUT = 10  # Seconds to look for any step after a fall

# The mouse changes what's under it: RuneLite draws a tooltip beside it and darkens the
# highlight it's over, and the game draws a cross where you click. So pictures are taken
# with the mouse out of the way: while recording, from a recent screenshot taken before
# the mouse reached the spot, and while running, by moving the mouse away while waiting.
TOOLTIP_SIZE = (200, 50)  # How far right and down from the mouse its effects can reach
RECORD_FRAME_RADIUS = 300  # Size of the recent screenshots kept around the mouse
RECORD_FRAMES = 50  # How many to keep
RECORD_FRAME_INTERVAL = 0.06  # Seconds between them
RECORD_FRAME_AGE = 0.05  # Use a screenshot at least this many seconds older than the click
SAME_SCENE_THRESHOLD = 0.8  # How alike two screenshots must be to count as the camera not having moved
DOUBLE_CLICK_TIME = 1.2  # A second click this soon on the same spot is ignored
DOUBLE_CLICK_DISTANCE = 30

# Marks of grace, found by the RuneLite Agility plugin's highlight colour
COLLECT_MARKS = True
MARK_COLOR = (255, 0, 255)  # RGB, match "Mark highlight color" in the plugin
COLOR_TOLERANCE = 12  # Per channel
MIN_HIGHLIGHT_SIZE = 15  # Ignore specks smaller than this many pixels
MARK_MAX_DISTANCE = 350  # Only grab marks this close to your character
MARK_SEARCH_RADIUS = 500  # How far to look for the next step after grabbing a mark

# Breaks
BREAK_CHANCE = 1 / 15  # Chance of a break after each lap
BREAK_SECONDS = (5, 30)
