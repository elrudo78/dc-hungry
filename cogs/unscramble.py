# cogs/unscramble.py
# Contains the logic and commands for the Unscramble game.

import discord
from discord.ext import commands
import random
import time
import asyncio # For sleep and task management
import logging
import config # Import shared configuration
from .database import DatabaseCog # Import the Database Cog relative to this file

log = logging.getLogger(__name__)

class UnscrambleCog(commands.Cog, name="Unscramble"):
    """Commands and logic for the Unscramble game"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games = {} # { channel_id: game_data_dict }
        self.food_words = []   # Loaded words
        self.db_cog: DatabaseCog = self.bot.get_cog("Database") # Get the Database Cog instance

        if not self.db_cog:
            log.error("!!! Database Cog not found. Unscramble game might not save scores correctly! !!!")
            # Optionally raise an exception or handle this more gracefully

        self._load_words()
        log.info("Unscramble Cog initialized.")

    def _load_words(self):
        """Loads words from the configured file."""
        try:
            with open(config.WORDS_FILENAME, "r") as f:
                self.food_words = [line.strip().upper() for line in f if line.strip()]
            if not self.food_words:
                log.warning(f"Word file '{config.WORDS_FILENAME}' is empty or contains no valid words. Using default.")
                self.food_words = ["DEFAULT"]
            log.info(f"Successfully loaded {len(self.food_words)} words from '{config.WORDS_FILENAME}'.")
        except FileNotFoundError:
            log.error(f"Word file '{config.WORDS_FILENAME}' not found! Using default word.")
            self.food_words = ["DEFAULT"]
        except Exception as e:
            log.exception(f"Failed to load words from '{config.WORDS_FILENAME}': {e}. Using default.")
            self.food_words = ["DEFAULT"]

    def _create_hint_string(self, word, revealed_indices):
        """Creates the hint string with underscores for hidden letters."""
        hint_display = []
        for i, letter in enumerate(word):
            if i in revealed_indices:
                hint_display.append(f"**{letter}**") # Bold revealed letters
            else:
                hint_display.append("\\_") # Use escaped underscore for display
        return " ".join(hint_display)

    # --- Helper for potential asyncio timeout task ---
    # <-- ADD THIS ENTIRE METHOD DEFINITION -->
    async def _game_timeout_task(self, channel: discord.TextChannel, channel_id: int, game_start_time: float, correct_word: str):
        """Background task to handle automatic game timeout."""
        try:
            # Wait for the configured time limit
            await asyncio.sleep(config.TIME_LIMIT_SECONDS)

            # --- CRITICAL Check: Is the *exact same* game still active? ---
            # Retrieve potentially updated game state directly before acting
            current_game_data = self.active_games.get(channel_id)

            # Check if a game exists AND if its start time matches the one this task was created for
            if current_game_data and current_game_data['start_time'] == game_start_time:
                # If start times match, this specific game timed out without being won/stopped.
                log.info(f"[Timeout Task] Game in channel {channel_id} timed out. Word was {correct_word}.")

                embed = discord.Embed(
                    title="⏱️ Time's Up!",
                    description=f"Aww, time ran out! Nobody guessed the word.\n"
                                f"The word was **{correct_word}**.\n\n"
                                f"Start a new game with `{config.COMMAND_PREFIX}unscramble`!",
                    color=config.EMBED_COLOR_ERROR
                )

                try:
                    # Send timeout message to the original channel
                    await channel.send(embed=embed)
                except discord.NotFound:
                    log.warning(f"[Timeout Task] Channel {channel_id} not found when sending timeout message.")
                except discord.Forbidden:
                    log.warning(f"[Timeout Task] No permission to send timeout message in channel {channel_id}.")
                except Exception as e:
                    log.exception(f"[Timeout Task] Error sending timeout message to {channel_id}: {e}")

                # Clean up game state - Timeout deletion responsibility moves HERE
                del self.active_games[channel_id]
                log.info(f"[Timeout Task] Game state for channel {channel_id} cleared due to timeout.")
            else:
                # Game ended before timeout (win/stop) or a newer game started. Task does nothing.
                log.debug(f"[Timeout Task] Game in channel {channel_id} ended or changed before timeout fired. Task finished.")

        except asyncio.CancelledError:
            # This is expected if the game ends early and we cancel the task
            log.debug(f"[Timeout Task] Timeout task for channel {channel_id} was cancelled successfully.")
        except Exception as e:
            # Catch any other unexpected errors in the task itself
            log.exception(f"[Timeout Task] An unexpected error occurred in the timeout task for channel {channel_id}: {e}")
    # <-- END OF METHOD DEFINITION -->

    # --- Game Command ---
    @commands.command(name='unscramble', aliases=['us'])
    @commands.has_role(config.MOD_ROLE_NAME) # Use decorator for permission check
    @commands.guild_only() # Ensure command is not used in DMs
    async def unscramble(self, ctx: commands.Context):
        """Starts a new Unscramble game in this channel."""
        channel_id = ctx.channel.id

        # Check for existing game / stuck game
        if channel_id in self.active_games:
            game_start_time = self.active_games[channel_id]['start_time']
            if time.time() - game_start_time > config.STUCK_GAME_TIMEOUT_SECONDS:
                log.warning(f"Clearing stuck game in channel {channel_id}.")
                embed = discord.Embed(description=f"🧹 It looks like the previous game was left unfinished. Starting a new one!", color=config.EMBED_COLOR_WARNING)
                await ctx.send(embed=embed)
                # Properly clean up any potential running tasks for the old game (if using asyncio tasks)
                # <-- ADD TASK CANCELLATION FOR STUCK GAME HERE -->
                old_game_data = self.active_games.get(channel_id)
                if old_game_data and 'timeout_task' in old_game_data and old_game_data['timeout_task']:
                    try:
                        if not old_game_data['timeout_task'].done(): # Only cancel if not already finished
                            old_game_data['timeout_task'].cancel()
                            log.debug(f"Cancelled timeout task for stuck game in {channel_id}")
                    except Exception as e_cancel:
                         log.error(f"Error cancelling stuck game task for {channel_id}: {e_cancel}")
                # <-- END OF ADDED BLOCK -->
                
                if 'timeout_task' in self.active_games[channel_id]:
                    self.active_games[channel_id]['timeout_task'].cancel()
                del self.active_games[channel_id]
                # Continue to start new game below
            else:
                embed = discord.Embed(
                    title="⏳ Game in Progress!",
                    description=f"A game is already running! Guess this word: **{self.active_games[channel_id]['scrambled']}**",
                    color=config.EMBED_COLOR_WARNING
                )
                await ctx.send(embed=embed)
                return # Stop if active game exists

        if not self.food_words:
            embed = discord.Embed(description="❌ Error: No words loaded to start the game.", color=config.EMBED_COLOR_ERROR)
            await ctx.send(embed=embed)
            return

        log.info(f"Received '!unscramble' from {ctx.author} in channel {channel_id}")

        try:
            original_word = random.choice(self.food_words)
            if not original_word: # Should not happen if list has items, but safety
                 original_word = "DEFAULT"

            scrambled_word = original_word
            if len(original_word) > 1:
                word_letters = list(original_word)
                retry_count = 0
                while scrambled_word == original_word and retry_count < 5:
                    random.shuffle(word_letters)
                    scrambled_word = "".join(word_letters)
                    retry_count += 1

            current_time = time.time()
            game_data = {
                "word": original_word,
                "scrambled": scrambled_word,
                "start_time": current_time,
                "hints_given": 0,
                "revealed_indices": set(),
                "hint_requested_by": set(),
                 "message": ctx.message # Store context message maybe?
                # Add 'timeout_task': None here if using asyncio tasks later
            }
            self.active_games[channel_id] = game_data

            embed = discord.Embed(
                title="🧩 New Unscramble Challenge!",
                description=f"Alright {ctx.author.mention}, unscramble this food word:\n\n"
                            f"# **{scrambled_word}**\n\n"
                            f"You have **{config.TIME_LIMIT_SECONDS} seconds!** Type your answer.\n"
                            f"Use `{config.COMMAND_PREFIX}hint` for help (costs {config.HINT_PENALTY_POINTS} points!).",
                color=config.EMBED_COLOR_DEFAULT
            )
            await ctx.send(embed=embed)
            log.info(f"Game started in {channel_id}. Word: '{original_word}', Scrambled: '{scrambled_word}'")

            # --- Timeout Handling (Simple version within on_message check) ---
            # More advanced: Use asyncio.create_task(self._game_timeout(ctx, channel_id, current_time))
            # and store the task in game_data to cancel it if game ends early.
            # <-- ADD THIS BLOCK STARTING HERE -->
            try:
                # Use current_time (which is game['start_time']) for comparison
                timeout_task = asyncio.create_task(
                    self._game_timeout_task(ctx.channel, channel_id, current_time, original_word),
                    name=f"UnscrambleTimeout-{channel_id}" # Optional task name
                )
                # Store the task in the game data dict
                self.active_games[channel_id]['timeout_task'] = timeout_task
                log.debug(f"Timeout task created for game in channel {channel_id}")
            except Exception as e_task:
                 log.exception(f"Failed to create timeout task for channel {channel_id}: {e_task}")
                 # Game will proceed but might not auto-timeout if task creation failed
            # <-- ADD THIS BLOCK ENDING HERE -->
        
        except Exception as e:
            log.exception(f"Error processing !unscramble command: {e}")
            embed = discord.Embed(description="❌ Oops! Something went wrong starting the game.", color=config.EMBED_COLOR_ERROR)
            await ctx.send(embed=embed)
            if channel_id in self.active_games:
                del self.active_games[channel_id]


    # --- Hint Command ---
    @commands.command(name='hint')
    @commands.has_role(config.MOD_ROLE_NAME) # Only mods can request hint? Or anyone? Let's keep it mod for now as per previous logic. Change if needed.
    @commands.guild_only()
    async def hint(self, ctx: commands.Context):
        """Provides a hint for the current game (costs points)."""
        channel_id = ctx.channel.id
        user_id = str(ctx.author.id)

        if channel_id not in self.active_games:
            embed = discord.Embed(description=f"🤔 No game active here. Start one with `{config.COMMAND_PREFIX}unscramble`.", color=config.EMBED_COLOR_WARNING)
            await ctx.send(embed=embed)
            return

        game = self.active_games[channel_id]
        original_word = game["word"]

        # Calculate max hints (allow at least 1 if word len > 1)
        max_hints = max(1, len(original_word) // 2) if len(original_word) > 1 else 0

        if game["hints_given"] >= max_hints:
            embed = discord.Embed(description=f"😅 No more hints available for this word (max {max_hints})!", color=config.EMBED_COLOR_INFO)
            await ctx.send(embed=embed)
            return

        # Mark user requesting hint only once per game win potential
        if user_id not in game["hint_requested_by"]:
             game["hint_requested_by"].add(user_id)
             log.info(f"User {user_id} requested a hint for game in {channel_id}.")

        # Find an index to reveal
        available_indices = [i for i in range(len(original_word)) if i not in game["revealed_indices"]]
        if not available_indices: # Safety check
             embed = discord.Embed(description=f"😅 All possible letters already revealed!", color=discord.EMBED_COLOR_INFO)
             await ctx.send(embed=embed)
             return

        index_to_reveal = random.choice(available_indices)
        game["revealed_indices"].add(index_to_reveal)
        game["hints_given"] += 1 # Increment total hints given for this word

        hint_display_string = self._create_hint_string(original_word, game["revealed_indices"])

        embed = discord.Embed(
             title="💡 Hint!",
             description=f"Okay {ctx.author.mention}, here's hint #{game['hints_given']} for **{game['scrambled']}**:\n\n"
                         f"# {hint_display_string}\n\n"
                         f"Costs {config.HINT_PENALTY_POINTS} points if you win!",
             color=config.EMBED_COLOR_HINT
        )
        await ctx.send(embed=embed)
        log.info(f"Hint given for '{original_word}' in {channel_id}. Revealed index: {index_to_reveal}. Total hints: {game['hints_given']}")


    # --- Listener for Game Answers and Timeouts ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for messages to check for game answers or timeouts."""
        # Ignore messages from the bot itself or DMs
        if message.author == self.bot.user or not message.guild:
            return

        channel_id = message.channel.id

        # Check if a game is active in this channel
        if channel_id in self.active_games:
            # Ignore commands while checking for answers
            if message.content.startswith(config.COMMAND_PREFIX):
                return

            game = self.active_games[channel_id]
            correct_word = game["word"]
            start_time = game["start_time"]
            user_id = str(message.author.id)
            user_name = message.author.display_name

            # --- Check for Correct Answer ---
            if message.content.strip().upper() == correct_word:
                time_taken = time.time() - start_time
                log.info(f"Correct answer '{message.content}' from {user_name} ({user_id}) in {channel_id} after {time_taken:.2f}s")

                # Calculate points and penalty
                points_earned = 0
                hint_penalty_applied = 0

                if time_taken <= config.TIME_LIMIT_SECONDS:
                    # Base points based on speed
                    if time_taken <= 2: points_earned = 100
                    elif time_taken <= 5: points_earned = 75
                    else: points_earned = 50

                    # Apply hint penalty if this user requested a hint
                    if user_id in game["hint_requested_by"]:
                        hint_penalty_applied = config.HINT_PENALTY_POINTS * game["hints_given"]
                        points_earned = max(0, points_earned - hint_penalty_applied) # Ensure non-negative
                        log.info(f"Applying hint penalty of {hint_penalty_applied} for user {user_id} (total hints: {game['hints_given']})")

                    # Update score using Database Cog
                    new_total_score = 0
                    if self.db_cog:
                         new_total_score = await self.db_cog.update_score(message.author.id, points_earned)
                    else:
                         log.error(f"Database Cog not available, cannot update score for {user_id}")


                    # Create win embed
                    win_message = (
                        f"You unscrambled **{correct_word}** in **{time_taken:.2f}** seconds!\n"
                        f"You earned **{points_earned}** points."
                    )
                    if hint_penalty_applied > 0:
                        win_message += f" (after a {hint_penalty_applied} point hint penalty)"

                    win_embed = discord.Embed(
                        title=f"🎉 Correct, {user_name}! 🎉",
                        description=win_message,
                        color=config.EMBED_COLOR_SUCCESS
                    )
                    if self.db_cog:
                        win_embed.add_field(name="Your Total Score", value=f"**{new_total_score}** points")
                    else:
                         win_embed.set_footer(text="Score could not be saved (DB Error).")

                    await message.channel.send(embed=win_embed)

                    # <-- ADD THIS BLOCK -->
                    # Cancel the timeout task as the game is won
                    if 'timeout_task' in game and game['timeout_task']:
                        try:
                            # Check if task is already done before cancelling
                            if not game['timeout_task'].done():
                                game['timeout_task'].cancel()
                                log.debug(f"Cancelled timeout task for channel {channel_id} due to win.")
                        except Exception as e_cancel:
                             log.error(f"Error cancelling task on win for {channel_id}: {e_cancel}")
                    # <-- END ADDED BLOCK -->
                    
                    # Clean up game state
                    del self.active_games[channel_id]
                    log.info(f"Game in channel {channel_id} ended. Winner: {user_id}")
                    # Cancel timeout task if using asyncio tasks

                else: # Correct word, but too late
                    embed = discord.Embed(
                        title="⏰ Too Slow!",
                        description=f"Yes, {user_name}, the word was **{correct_word}**!\n"
                                    f"But you took **{time_taken:.2f}s** (limit was {config.TIME_LIMIT_SECONDS}s).\n"
                                    f"No points this time, faster next round! 💨",
                        color=config.EMBED_COLOR_WARNING
                    )
                    await message.channel.send(embed=embed)
                    # <-- ADD THIS BLOCK -->
                    # Cancel the timeout task as the game ended (too slow)
                    if 'timeout_task' in game and game['timeout_task']:
                         try:
                             # Check if task is already done before cancelling
                             if not game['timeout_task'].done():
                                  game['timeout_task'].cancel()
                                  log.debug(f"Cancelled timeout task for channel {channel_id} due to late answer.")
                         except Exception as e_cancel:
                              log.error(f"Error cancelling task on late answer for {channel_id}: {e_cancel}")
                    # <-- END ADDED BLOCK -->
                    del self.active_games[channel_id] # End game
                    log.info(f"Game in channel {channel_id} ended. Correct but too late by {user_id}")
                    # Cancel timeout task if using asyncio tasks


            
    # --- Helper for potential asyncio timeout task ---
    # async def _game_timeout(self, ctx: commands.Context, channel_id: int, game_start_time: float):
    #     """Handles the game timeout after the duration."""
    #     await asyncio.sleep(config.TIME_LIMIT_SECONDS)
    #     # Check if game still exists and hasn't been won already
    #     if channel_id in self.active_games and self.active_games[channel_id]['start_time'] == game_start_time:
    #         game = self.active_games[channel_id]
    #         correct_word = game["word"]
    #         log.info(f"[Async Task] Game in channel {channel_id} timed out. Word was {correct_word}.")
    #         embed = discord.Embed(...) # Create timeout embed
    #         try:
    #             await ctx.channel.send(embed=embed) # Use original context channel
    #         except Exception as e:
    #              log.exception(f"Error sending timeout message via task: {e}")
    #         del self.active_games[channel_id]


# Required setup function for the cog
async def setup(bot: commands.Bot):
    # Check if DatabaseCog is loaded before adding this cog
    db_cog = bot.get_cog("Database")
    if db_cog is None:
        log.critical("Database Cog is not loaded. Unscramble Cog requires it. Aborting load.")
        raise commands.ExtensionFailed(name="unscramble", message="Database Cog not found.")
    else:
        await bot.add_cog(UnscrambleCog(bot))
        log.info("Unscramble Cog added to bot.")