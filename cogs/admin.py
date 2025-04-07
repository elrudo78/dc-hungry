# cogs/admin.py
# Contains administrative commands for the bot.

import discord
from discord.ext import commands
import logging
import config  # Import shared configuration
from .database import DatabaseCog  # Import the Database Cog

log = logging.getLogger(__name__)


class AdminCog(commands.Cog, name="Admin"):
    """Moderator/Admin level commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_cog: DatabaseCog = self.bot.get_cog(
            "Database")  # Get Database Cog instance

        if not self.db_cog:
            log.error(
                "!!! Database Cog not found. Admin commands may fail! !!!")

    @commands.command(name='resetleaderboard', aliases=['resetlb'])
    @commands.has_role(config.MOD_ROLE_NAME)  # Check for the moderator role
    @commands.guild_only()  # Only in servers
    async def reset_leaderboard(self, ctx: commands.Context):
        """Resets the Unscramble leaderboard (requires 'bot admin' role)."""
        log.warning(
            f"Reset leaderboard command issued by {ctx.author} ({ctx.author.id}) in guild {ctx.guild.id}"
        )

        if not self.db_cog:
            embed = discord.Embed(
                description=
                "❌ Database service is unavailable. Cannot reset leaderboard.",
                color=config.EMBED_COLOR_ERROR)
            await ctx.send(embed=embed)
            return

        try:
            await self.db_cog.reset_leaderboard()

            embed = discord.Embed(
                title="✅ Leaderboard Reset!",
                description=
                f"The Unscramble leaderboard has been successfully cleared by {ctx.author.mention}.",
                color=config.EMBED_COLOR_SUCCESS)
            await ctx.send(embed=embed)
            log.info(f"Leaderboard successfully reset by {ctx.author.name}.")

        except Exception as e:
            log.exception(f"Error processing !resetleaderboard command: {e}")
            embed = discord.Embed(
                description=
                "❌ Oops! Something went wrong trying to reset the leaderboard.",
                color=config.EMBED_COLOR_ERROR)
            await ctx.send(embed=embed)

    # --- Add this new command method ---
    @commands.command(name='stop', aliases=['stopgame', 'cancelgame'])
    @commands.has_role(config.MOD_ROLE_NAME)  # Check for the moderator role
    @commands.guild_only()  # Only in servers
    async def stop_game(self, ctx: commands.Context):
        """Force stops the current Unscramble game in this channel."""

        log.info(
            f"Stop game command issued by {ctx.author} in channel {ctx.channel.id}"
        )
        channel_id = ctx.channel.id

        # --- Access the Unscramble Cog ---
        # It's better practice to get the cog instance when needed
        unscramble_cog = self.bot.get_cog("Unscramble")
        if not unscramble_cog:
            log.error("Unscramble Cog not found when trying to stop game.")
            embed = discord.Embed(
                description="❌ Internal error: Cannot access game module.",
                color=config.EMBED_COLOR_ERROR)
            await ctx.send(embed=embed)
            return

        # --- Check if game exists in that cog's active games ---
        if channel_id in unscramble_cog.active_games:
            game = unscramble_cog.active_games[channel_id]
            word = game.get('word', 'UNKNOWN')  # Get word safely

            log.warning(
                f"Force stopping game in channel {channel_id} by {ctx.author.name}. Word was {word}"
            )

            # --- Cancel the timeout task ---
            if 'timeout_task' in game and game['timeout_task']:
                try:
                    # Only cancel if task exists and is not already done
                    if not game['timeout_task'].done():
                        game['timeout_task'].cancel()
                        log.debug(
                            f"Cancelled timeout task for channel {channel_id} due to stop command."
                        )
                except Exception as e_cancel:
                    log.error(
                        f"Error cancelling task on stop command for {channel_id}: {e_cancel}"
                    )

            # --- Delete game state from the Unscramble Cog ---
            del unscramble_cog.active_games[channel_id]

            # --- Send confirmation ---
            embed = discord.Embed(
                description=
                f"🛑 The Unscramble game has been stopped by {ctx.author.mention}.\nThe word was **{word}**.",
                color=config.EMBED_COLOR_WARNING)
            await ctx.send(embed=embed)

        else:
            # No game active in this channel according to the Unscramble Cog
            embed = discord.Embed(
                description=
                "🤔 No Unscramble game seems to be active in this channel to stop.",
                color=config.EMBED_COLOR_INFO)
            await ctx.send(embed=embed)

    # --- Add other admin commands here later ---
    # Example: !stopgame command
    # @commands.command(name='stopgame')
    # @commands.has_role(config.MOD_ROLE_NAME)
    # @commands.guild_only()
    # async def stop_game(self, ctx: commands.Context):
    #     """Force stops the current Unscramble game in this channel."""
    #     unscramble_cog = self.bot.get_cog("Unscramble")
    #     if unscramble_cog and ctx.channel.id in unscramble_cog.active_games:
    #         game = unscramble_cog.active_games[ctx.channel.id]
    #         word = game['word']
    #         log.warning(f"Force stopping game in channel {ctx.channel.id} by {ctx.author.name}. Word was {word}")
    #         # Cancel timeout task if applicable
    #         if 'timeout_task' in game and game['timeout_task']:
    #              game['timeout_task'].cancel()
    #         del unscramble_cog.active_games[ctx.channel.id]
    #         embed = discord.Embed(description=f"🛑 The game has been stopped by {ctx.author.mention}. The word was **{word}**.", color=config.EMBED_COLOR_WARNING)
    #         await ctx.send(embed=embed)
    #     else:
    #          embed = discord.Embed(description="🤔 No Unscramble game seems to be active in this channel.", color=config.EMBED_COLOR_INFO)
    #          await ctx.send(embed=embed)


# Required setup function
async def setup(bot: commands.Bot):
    # Check dependency
    if bot.get_cog("Database") is None:
        log.critical("Database Cog not loaded. Admin Cog requires it.")
        raise commands.ExtensionFailed("admin", "Database Cog not found.")
    await bot.add_cog(AdminCog(bot))
    log.info("Admin Cog added to bot.")
