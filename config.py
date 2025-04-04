# config.py
# Central configuration for the bot

import discord

# --- Core Settings ---
COMMAND_PREFIX = "!"
DISCORD_TOKEN_ENV_VAR = "DISCORD_TOKEN"  # Name of the secret in Replit Secrets

# --- Role Settings ---
MOD_ROLE_NAME = "bot admin"  # Role required for admin/game-starting commands

# --- Unscramble Game Settings ---
WORDS_FILENAME = "words.txt"
TIME_LIMIT_SECONDS = 60
#HINT_PENALTY_POINTS = 10
# Add this new config variable:
HINT_SCHEDULE_SECONDS = [20, 35, 45]  # Times (from start) hints should appear
STUCK_GAME_TIMEOUT_SECONDS = 300  # How long before !unscramble clears an old game

# --- Database Settings ---
LEADERBOARD_DB_KEY = "unscramble_leaderboard"

# --- Embed Settings ---
EMBED_COLOR_DEFAULT = discord.Color.blue()  # 0x0099ff
EMBED_COLOR_SUCCESS = discord.Color.green()
EMBED_COLOR_ERROR = discord.Color.red()
EMBED_COLOR_WARNING = discord.Color.orange()
EMBED_COLOR_INFO = discord.Color.gold()
EMBED_COLOR_HINT = discord.Color.blurple()  # Or use EMBED_COLOR_DEFAULT

# --- Bot Activity ---
BOT_ACTIVITY_NAME = f"{COMMAND_PREFIX}unscramble | {COMMAND_PREFIX}help"  # Example, will be set later
