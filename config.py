"""
config.py — Configuration constants for the Discord Poll Bot.

Contains embed colors, emoji mappings, default values, and styling constants.
"""

import discord

# ──────────────────────────────────────────────
#  Embed Colors
# ──────────────────────────────────────────────
COLOR_PRIMARY = discord.Color.from_rgb(88, 101, 242)    # Blurple — active polls
COLOR_SUCCESS = discord.Color.from_rgb(87, 242, 135)    # Green  — poll completed
COLOR_WARNING = discord.Color.from_rgb(254, 231, 92)    # Yellow — warnings
COLOR_DANGER  = discord.Color.from_rgb(237, 66, 69)     # Red    — errors / ended early
COLOR_ADMIN   = discord.Color.from_rgb(235, 69, 158)    # Pink   — admin panel
COLOR_INFO    = discord.Color.from_rgb(69, 179, 235)    # Cyan   — informational

# ──────────────────────────────────────────────
#  Button Emoji & Style Mappings
# ──────────────────────────────────────────────
# Emojis assigned to answer options (up to 10)
OPTION_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# Button styles cycled across options for visual variety
BUTTON_STYLES = [
    discord.ButtonStyle.primary,    # Blurple
    discord.ButtonStyle.success,    # Green
    discord.ButtonStyle.secondary,  # Grey
    discord.ButtonStyle.primary,
    discord.ButtonStyle.success,
]

# ──────────────────────────────────────────────
#  Defaults
# ──────────────────────────────────────────────
DEFAULT_POLL_DURATION_MINUTES = 5
MAX_POLL_DURATION_MINUTES = 10080   # 7 days
MIN_POLL_DURATION_MINUTES = 1
MAX_OPTIONS = 10                    # Discord limits rows; 10 buttons max (2 rows of 5)

# ──────────────────────────────────────────────
#  Formatting
# ──────────────────────────────────────────────
BAR_FULL  = "█"
BAR_EMPTY = "░"
BAR_LENGTH = 12   # Characters in the progress bar

# ──────────────────────────────────────────────
#  Poll Check Interval (seconds)
# ──────────────────────────────────────────────
POLL_CHECK_INTERVAL = 15   # How often the background task checks for expired polls
COUNTDOWN_UPDATE_INTERVAL = 30  # How often the live countdown embed is refreshed
