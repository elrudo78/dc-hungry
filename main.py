# main.py
# Main entry point for the Discord Bot

import discord
from discord.ext import commands
import os
import logging
import asyncio
import config  # Import our configuration file
token = os.environ.get('DISCORD_TOKEN')
if not token:
    raise ValueError("No DISCORD_TOKEN found in environment variables!")

# --- Logging Setup ---
# More robust logging than just print()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s]: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('discord')  # Get the discord logger
logger.setLevel(logging.INFO)  # Set discord logger level if needed
main_log = logging.getLogger(__name__)  # Logger for this main file

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True  # Still need message content for answers
intents.members = True  # Needed for getting member roles easily in checks

# Use commands.Bot instead of discord.Client
bot = commands.Bot(command_prefix=config.COMMAND_PREFIX,
                   intents=intents,
                   case_insensitive=True,
                   help_command=None)  # Commands are not case-sensitive


# --- Bot Events ---
@bot.event
async def on_ready():
    """Runs when the bot connects and is ready."""
    main_log.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    main_log.info(f'Command Prefix: {config.COMMAND_PREFIX}')
    main_log.info(f'Moderator Role: {config.MOD_ROLE_NAME}')
    main_log.info(f'discord.py version: {discord.__version__}')

    # Load Cogs first
    await load_cogs()

    # Set bot activity status after cogs are potentially ready
    activity = discord.Game(name=config.BOT_ACTIVITY_NAME)
    await bot.change_presence(status=discord.Status.online, activity=activity)
    main_log.info("Status: Online, Cogs loaded, Activity set.")
    main_log.info('------ Bot is Ready! ------')


# --- Cog Loading ---
async def load_cogs():
    """Finds and loads all Cog files from the 'cogs' directory."""
    main_log.info("Loading Cogs...")
    loaded_cogs = []
    failed_cogs = []

    # Make sure DatabaseCog is loaded first if others depend on it immediately
    initial_cogs = ['database']  # Add other priority cogs here if needed
    for cog_name in initial_cogs:
        try:
            await bot.load_extension(f'cogs.{cog_name}')
            main_log.info(f"Successfully loaded initial Cog: {cog_name}")
            loaded_cogs.append(cog_name)
        except commands.ExtensionAlreadyLoaded:
            main_log.warning(f"Initial Cog {cog_name} already loaded.")
        except Exception as e:
            main_log.exception(f"Failed to load initial Cog: {cog_name}\n{e}")
            failed_cogs.append(cog_name)

    # Load remaining Cogs
    for filename in os.listdir('./cogs'):
        # Ensure it's a Python file and not already loaded/failed or __init__
        if filename.endswith(
                '.py'
        ) and filename[:
                       -3] not in loaded_cogs and filename[:
                                                           -3] not in failed_cogs and filename != '__init__.py':
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f'cogs.{cog_name}')
                main_log.info(f"Successfully loaded Cog: {cog_name}")
                loaded_cogs.append(cog_name)
            except commands.ExtensionAlreadyLoaded:
                main_log.warning(
                    f"Cog {cog_name} already loaded (likely dependency).")
            except Exception as e:
                main_log.exception(f"Failed to load Cog: {cog_name}\n{e}")
                failed_cogs.append(cog_name)

    main_log.info(
        f"Cog loading complete. Loaded: {len(loaded_cogs)}, Failed: {len(failed_cogs)}"
    )
    if failed_cogs:
        main_log.error(f"Failed Cogs: {', '.join(failed_cogs)}")


# Optional: Command to reload Cogs (requires bot owner check)
@bot.command(name='reload', hidden=True)
@commands.is_owner()  # Only the bot owner (defined by user ID) can use this
async def _reload(ctx, cog_name: str):
    """Reloads a specific Cog."""
    main_log.warning(
        f"Reload command issued for Cog: {cog_name} by {ctx.author}")
    try:
        await bot.reload_extension(f"cogs.{cog_name}")
        await ctx.send(f"✅ Cog '{cog_name}' reloaded successfully.",
                       delete_after=10)
        main_log.info(f"Cog '{cog_name}' reloaded successfully.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"❌ Cog '{cog_name}' is not loaded.", delete_after=10)
    except commands.ExtensionNotFound:
        await ctx.send(f"❌ Cog '{cog_name}' not found.", delete_after=10)
    except Exception as e:
        await ctx.send(f"❌ Failed to reload Cog '{cog_name}':\n```py\n{e}\n```"
                       )
        main_log.exception(f"Failed to reload Cog: {cog_name}")


# Error handler for owner-only commands
@_reload.error
async def reload_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.send("🚫 You are not the owner of this bot.", delete_after=10)
    else:
        main_log.error(f"Error in reload command: {error}")


# --- Running the Bot ---
def run_bot():
    """Loads the token and runs the bot using async context manager."""
    try:
        main_log.info("Attempting to load token and connect...")
        token = os.environ.get(config.DISCORD_TOKEN_ENV_VAR)
        if token is None:
            # Fallback check (keep or remove as needed)
            main_log.warning(
                f"{config.DISCORD_TOKEN_ENV_VAR} not found via os.environ. Trying Replit DB (legacy fallback)..."
            )
            token = db.get(config.DISCORD_TOKEN_ENV_VAR)
            if token is None:
                raise KeyError(config.DISCORD_TOKEN_ENV_VAR)

        if not isinstance(token, str) or not token:
            main_log.critical(
                "Token retrieved is invalid (empty or not a string).")
            raise ValueError("Invalid Token Format")

        # --- NEW: Use bot.start() within an async context for better shutdown ---
        async def runner():
            async with bot:  # Use async context manager - handles setup/teardown including cog_unload
                main_log.info(
                    "Loading initial extensions...")  # Log moved here
                await load_cogs()  # Load cogs within the async context
                main_log.info("Starting bot...")
                await bot.start(token, reconnect=True)

        # Run the async runner function
        # Ensure the loop runs the runner until completion
        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            main_log.warning("Shutdown requested via KeyboardInterrupt.")
        # No explicit finally needed for bot.close() when using 'async with bot:'

    # --- Keep the original startup exception handling ---
    except KeyError:
        main_log.critical("-" * 50)
        main_log.critical(
            f"FATAL ERROR: {config.DISCORD_TOKEN_ENV_VAR} not found in Replit Secrets!"
        )
        main_log.critical(
            "Please go to the Secrets (🔒) tab, add a new secret:")
        main_log.critical(f"  KEY: {config.DISCORD_TOKEN_ENV_VAR}")
        main_log.critical("  VALUE: your_actual_bot_token")
        main_log.critical("-" * 50)
    except ValueError as e:
        main_log.critical("-" * 50)
        main_log.critical(f"FATAL ERROR: Invalid Token - {e}")
        main_log.critical(
            "The token stored seems to be incorrect. Please verify it.")
        main_log.critical("-" * 50)
    except discord.errors.LoginFailure:
        main_log.critical("-" * 50)
        main_log.critical(
            "FATAL ERROR: Improper token passed (Login Failure).")
        main_log.critical(
            "Verify the token in Replit Secrets is correct and hasn't been reset."
        )
        main_log.critical("-" * 50)
    except discord.errors.PrivilegedIntentsRequired:
        main_log.critical("-" * 50)
        main_log.critical("FATAL ERROR: Privileged Intents Required.")
        main_log.critical(
            "Go to discord.com/developers/applications -> Your App -> Bot")
        main_log.critical(
            "Ensure 'MESSAGE CONTENT INTENT' and 'SERVER MEMBERS INTENT' are ENABLED."
        )
        main_log.critical("-" * 50)
    except Exception as e:
        main_log.critical("-" * 50)
        main_log.critical(
            f"AN UNEXPECTED ERROR OCCURRED ON STARTUP/RUNTIME: {type(e).__name__} - {e}"
        )
        main_log.critical(
            traceback.format_exc())  # Add traceback for more detail
        main_log.critical("-" * 50)


# --- MODIFIED: Entry point ---
if __name__ == "__main__":
    # Optional: Add signal handling for more robust shutdown on TERM signals (like Replit stop button)
    # This can be complex to get right with asyncio, start without it.
    run_bot()
