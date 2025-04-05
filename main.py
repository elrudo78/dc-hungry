import os
import traceback
import asyncio
import discord
from discord.ext import commands
from config import (  # <-- ADD THIS IMPORT
    TIME_LIMIT_SECONDS,
    HINT_PENALTY_POINTS,
    LEADERBOARD_DB_KEY,
    EMBED_COLOR,
    MOD_ROLE_NAME
)

try:
    print("Attempting to load token and connect...")
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        raise ValueError("""
        ERROR: DISCORD_TOKEN not found!
        Add it to GitHub Secrets:
        1. Repo Settings → Secrets → Codespaces
        2. New secret: DISCORD_TOKEN = your_bot_token
        """)

    # Keep your original intents setup
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(
        command_prefix='!',
        intents=intents,
        help_command=None  # Preserves your custom help command
    )

    @bot.event
    async def on_ready():
        """Original on_ready logic"""
        print(f'We have logged in as {bot.user}')
        print(f'Bot ID: {bot.user.id}')
        print('Status: Online, ready!')

    async def load_extensions():
        """Load all cogs exactly as before"""
        await bot.load_extension("cogs.database")
        await bot.load_extension("cogs.unscramble")
        await bot.load_extension("cogs.error_handler")
        await bot.load_extension("cogs.admin")
        await bot.load_extension("cogs.general")
        print("All cogs loaded successfully")

    async def runner():
        """Startup with error handling"""
        await load_extensions()
        await bot.start(token)

    # Preserve original error handling
    async def run_bot():
        try:
            await runner()
        except discord.errors.LoginFailure:
            print("-" * 50)
            print("FATAL ERROR: Invalid bot token!")
            print("-" * 50)
        except Exception as e:
            print("-" * 50)
            print(f"FATAL ERROR: {type(e).__name__} - {e}")
            print("Traceback:")
            print(traceback.format_exc())
            print("-" * 50)

    # Start the bot
    asyncio.run(run_bot())

except Exception as e:
    print("-" * 50)
    print(f"STARTUP ERROR: {type(e).__name__} - {e}")
    print("-" * 50)
    raise
