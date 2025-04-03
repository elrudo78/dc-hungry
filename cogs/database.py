# cogs/database.py
# Handles all interactions with the Replit Database with write throttling.

import discord
from discord.ext import commands
from replit import db
import json
import logging
import time # For monotonic timing
import asyncio # For locks and background tasks
import config # Import shared configuration

log = logging.getLogger(__name__)

class DatabaseCog(commands.Cog, name="Database"):
    """Manages database operations (Leaderboard, etc.) with periodic saving."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leaderboard_key = config.LEADERBOARD_DB_KEY
        self.leaderboard = {} # In-memory cache of the leaderboard

        # --- State for Throttled Saving ---
        self._save_lock = asyncio.Lock() # Prevent concurrent saves
        self._dirty = False # Flag to check if save is needed
        self._save_task = None # Placeholder for the background task
        self._save_interval_seconds = 60 # How often to save (e.g., 60 seconds)

        log.info("Database Cog initializing.")
        # Load initial data when cog is loaded
        self._load_leaderboard()

        # Start the periodic save task when the cog loads
        # Use bot.loop which is the running event loop for the bot
        self._save_task = self.bot.loop.create_task(self._periodic_save_task(), name="PeriodicDBSave")
        log.info(f"Periodic database save task scheduled every {self._save_interval_seconds} seconds.")

    # --- Leaderboard Loading ---
    def _load_leaderboard(self):
        """Loads the leaderboard from Replit DB into memory."""
        try:
            raw_data = db.get(self.leaderboard_key)
            if raw_data:
                if isinstance(raw_data, str):
                    self.leaderboard = json.loads(raw_data)
                elif isinstance(raw_data, dict): # Replit DB might store dicts directly
                    self.leaderboard = raw_data
                else:
                    log.warning(f"Leaderboard data in DB key '{self.leaderboard_key}' has unexpected format {type(raw_data)}. Resetting.")
                    self.leaderboard = {}

                # Ensure keys are strings (User IDs) and values are ints (Scores)
                self.leaderboard = {str(k): int(v) for k, v in self.leaderboard.items()}
                log.info(f"Successfully loaded leaderboard with {len(self.leaderboard)} entries from Replit DB.")
            else:
                log.info("No existing leaderboard found in Replit DB. Starting fresh.")
                self.leaderboard = {}
                self._dirty = True # Mark as dirty if we started fresh, to save the empty state
        except json.JSONDecodeError as e:
             log.error(f"Failed to decode JSON from DB key '{self.leaderboard_key}': {e}. Resetting leaderboard.")
             self.leaderboard = {}
             self._dirty = True
             # Optionally try to delete the bad key
             if self.leaderboard_key in db:
                 try:
                     del db[self.leaderboard_key]
                 except Exception as del_e:
                      log.error(f"Failed to delete potentially corrupt DB key {self.leaderboard_key}: {del_e}")
        except Exception as e:
            log.exception(f"ERROR: Failed to load leaderboard from Replit DB: {e}. Resetting.")
            self.leaderboard = {}
            self._dirty = True

    # --- Accessor Methods ---
    async def get_leaderboard_data(self) -> dict:
        """Returns a copy of the current leaderboard data."""
        # Return a copy to prevent accidental modification outside the cog
        return self.leaderboard.copy()

    async def get_score(self, user_id: int) -> int:
         """Gets a user's current score from the in-memory leaderboard."""
         return self.leaderboard.get(str(user_id), 0)

    # --- Update Methods (Memory only, triggers save task) ---
    async def update_score(self, user_id: int, points_to_add: int) -> int:
        """Updates a user's score in memory. Returns the new score."""
        user_id_str = str(user_id)
        current_score = self.leaderboard.get(user_id_str, 0)
        new_score = current_score + points_to_add
        self.leaderboard[user_id_str] = new_score
        self._dirty = True # Mark that data has changed and needs saving
        log.debug(f"Updated score for user {user_id_str}: {current_score} + {points_to_add} -> {new_score} (Memory only)")
        return new_score

    async def reset_leaderboard(self):
        """Clears the leaderboard in memory, deletes from DB, and forces a save."""
        log.warning("Reset leaderboard command received. Clearing data...")
        self.leaderboard = {}
        self._dirty = True # Mark as dirty to ensure empty state is potentially saved
        try:
            if self.leaderboard_key in db:
                del db[self.leaderboard_key]
                log.info(f"Leaderboard key '{self.leaderboard_key}' deleted from Replit DB.")
            else:
                 log.info(f"Leaderboard key '{self.leaderboard_key}' not found in DB for deletion (already clear?).")
        except Exception as e:
             log.exception(f"Error deleting leaderboard key '{self.leaderboard_key}' from DB: {e}")
        log.info("In-memory leaderboard cleared.")
        # Force an immediate save attempt after resetting
        await self.force_save_leaderboard()


    # --- Saving Logic ---
    async def _save_leaderboard(self):
        """Saves the current in-memory leaderboard to Replit DB if dirty."""
        # Ensure only one save operation happens at a time across the bot instance
        async with self._save_lock:
            if not self._dirty:
                log.debug("Skipping save, leaderboard not dirty.")
                return # Nothing to save

            log.info("Attempting to save leaderboard to Replit DB...")
            temp_leaderboard = self.leaderboard.copy() # Save a copy to prevent mid-save modifications issues
            try:
                start_time = time.monotonic()
                # Store as JSON string for robustness
                db[self.leaderboard_key] = json.dumps(temp_leaderboard)
                end_time = time.monotonic()
                duration = end_time - start_time
                log.info(f"Leaderboard successfully saved to Replit DB ({len(temp_leaderboard)} entries, took {duration:.4f}s).")
                # Reset dirty flag ONLY on successful save
                self._dirty = False
            except Exception as e:
                log.exception(f"ERROR: Failed to save leaderboard to Replit DB key '{self.leaderboard_key}': {e}")
                # Do NOT reset dirty flag if save failed, so it tries again next time

    async def force_save_leaderboard(self):
        """Forces an immediate save attempt, mainly for shutdown or critical events."""
        log.warning("Force save leaderboard initiated...")
        # Set dirty flag just in case it wasn't, then call the save method
        self._dirty = True
        await self._save_leaderboard()

    async def _periodic_save_task(self):
        """Runs in the background, periodically saving the leaderboard if needed."""
        await self.bot.wait_until_ready() # Wait until bot is fully connected
        log.info(f"Starting periodic leaderboard save task (interval: {self._save_interval_seconds}s).")
        while not self.bot.is_closed():
            try:
                # Wait for the specified interval
                await asyncio.sleep(self._save_interval_seconds)
                log.debug("Periodic save check...")
                # Only attempt to save if data has changed
                if self._dirty:
                     await self._save_leaderboard()

            except asyncio.CancelledError:
                log.info("Periodic save task cancelled.")
                break # Exit loop if cancelled by cog_unload
            except Exception as e:
                log.exception(f"Error in periodic save task: {e}")
                # Avoid spamming logs on repeated errors, sleep a bit longer before retrying
                await asyncio.sleep(self._save_interval_seconds * 2)
        log.warning("Periodic save task loop finished.")

    # --- Cog Lifecycle Methods ---
    async def cog_unload(self):
         """Clean up the background task when the cog is unloaded/bot shuts down."""
         log.warning("Database Cog unloading. Cancelling save task and forcing final save...")
         if self._save_task:
             self._save_task.cancel()
             try:
                 # Give the cancellation a moment to process if needed
                 await asyncio.wait_for(self._save_task, timeout=5.0)
             except asyncio.TimeoutError:
                 log.error("Periodic save task did not fully cancel within timeout.")
             except asyncio.CancelledError:
                 pass # Expected
             except Exception as e:
                 log.exception(f"Error during save task cancellation: {e}")

         # Attempt a final save
         await self.force_save_leaderboard()
         log.info("Final leaderboard save attempt complete during cog unload.")


# This function is required by discord.py to load the cog
async def setup(bot: commands.Bot):
    await bot.add_cog(DatabaseCog(bot))
    log.info("Database Cog added to bot.")