# cogs/general.py
# Contains general purpose commands like help, leaderboard viewing.

import discord
from discord.ext import commands
import logging
import config  # Import shared configuration
from .database import DatabaseCog  # Import the Database Cog

log = logging.getLogger(__name__)


class GeneralCog(commands.Cog, name="General"):
    """General informational commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_cog: DatabaseCog = self.bot.get_cog(
            "Database")  # Get Database Cog instance

        if not self.db_cog:
            log.error(
                "!!! Database Cog not found. General commands depending on it may fail! !!!"
            )

    @commands.command(name='leaderboard', aliases=['lb'])
    @commands.has_role(
        config.MOD_ROLE_NAME)  # Or remove this line if anyone can view
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context):
        """Displays the Unscramble leaderboard."""
        log.info(
            f"Leaderboard command issued by {ctx.author} in guild {ctx.guild.id}"
        )

        if not self.db_cog:
            embed = discord.Embed(
                description=
                "❌ Database service is unavailable. Cannot fetch leaderboard.",
                color=config.EMBED_COLOR_ERROR)
            await ctx.send(embed=embed)
            return

        leaderboard_data = await self.db_cog.get_leaderboard_data()

        if not leaderboard_data:
            embed = discord.Embed(
                description=
                "📜 The leaderboard is empty! Play some rounds first.",
                color=config.EMBED_COLOR_INFO)
            await ctx.send(embed=embed)
            return

        # Sort leaderboard by score descending
        sorted_leaderboard = sorted(leaderboard_data.items(),
                                    key=lambda item: item[1],
                                    reverse=True)

        embed = discord.Embed(title="🏆 Unscramble Leaderboard 🏆",
                              color=config.EMBED_COLOR_INFO)
        lb_text = ""
        rank = 1
        entries_to_show = 10  # Show top 10

        for user_id_key, score in sorted_leaderboard[:entries_to_show]:
            user_display_name = f"Unknown User ({user_id_key})"  # Default display
            try:
                user = await self.bot.fetch_user(int(user_id_key))
                user_display_name = user.display_name if hasattr(
                    user, 'display_name') else user.name
            except discord.NotFound:
                log.warning(f"Leaderboard: User ID {user_id_key} not found.")
            except (ValueError, TypeError):
                log.warning(
                    f"Leaderboard: Invalid user ID format '{user_id_key}'.")
            except Exception as e:
                log.exception(
                    f"Leaderboard: Error fetching user {user_id_key}: {e}")

            # Add entry with rank
            lb_text += f"`{rank}.` {user_display_name}: **{score}** points\n"  # Added rank number
            rank += 1

        if not lb_text:
            lb_text = "Could not display leaderboard entries."

        embed.description = lb_text
        embed.set_footer(
            text=
            f"Showing top {min(entries_to_show, len(sorted_leaderboard))} players."
        )
        await ctx.send(embed=embed)

    # --- Add this new help command method ---
    @commands.command(name='help', aliases=['h', 'commands'])
    @commands.has_role(
        config.MOD_ROLE_NAME)  # Or remove this line if anyone can view
    @commands.guild_only()  # Keep it in guilds for simplicity
    async def help_command(self, ctx: commands.Context):
        """Shows this help message listing available commands."""

        log.info(
            f"Help command requested by {ctx.author} in guild {ctx.guild.id}")

        embed = discord.Embed(title="🍔 Hungry Bot Help 🍔",
                              description="Here are the commands you can use:",
                              color=config.EMBED_COLOR_DEFAULT)
        embed.set_thumbnail(
            url=self.bot.user.display_avatar.url)  # Use bot's avatar

        # --- Commands List ---
        # Add fields for each command. Adjust descriptions and roles as needed.

        embed.add_field(
            name=f"`{config.COMMAND_PREFIX}unscramble` (or `us`)",
            value=
            f"Starts a new Unscramble game.\n*Requires '{config.MOD_ROLE_NAME}' role.*",
            inline=False  # Each command on its own line
        )

        embed.add_field(
            name=f"`{config.COMMAND_PREFIX}leaderboard` (or `lb`)",
            value=
            f"Shows the top players in Unscramble.\n*Requires '{config.MOD_ROLE_NAME}' role.*",  # Adjust role if lb is for everyone
            inline=False)
        embed.add_field(
            name=f"`{config.COMMAND_PREFIX}stop` (or `stopgame`)",
            value=
            f"Force-stops the current Unscramble game in the channel.\n*Requires '{config.MOD_ROLE_NAME}' role.*",
            inline=False)
        embed.add_field(
            name=f"`{config.COMMAND_PREFIX}resetleaderboard` (or `resetlb`)",
            value=
            f"Clears all Unscramble scores.\n*Requires '{config.MOD_ROLE_NAME}' role.*",
            inline=False)
        embed.add_field(name=f"`{config.COMMAND_PREFIX}help` (or `h`)",
                        value="Shows this help message.",
                        inline=False)

        # --- Footer ---
        embed.set_footer(text="Let the games begin!")

        await ctx.send(embed=embed)

    # --- Add !help command here later ---
    # @commands.command(name='help')
    # async def help_command(self, ctx: commands.Context):
    #      embed = discord.Embed(title="Bot Help", color=config.EMBED_COLOR_DEFAULT)
    #      embed.add_field(name=f"{config.COMMAND_PREFIX}unscramble / us", value="Starts a new Unscramble game (requires 'bot admin' role).", inline=False)
    #      embed.add_field(name=f"{config.COMMAND_PREFIX}hint", value="Get a hint for the current game (requires 'bot admin' role, costs points).", inline=False)
    #      embed.add_field(name=f"{config.COMMAND_PREFIX}leaderboard / lb", value="Shows the top players (requires 'bot admin' role).", inline=False)
    #      embed.add_field(name=f"{config.COMMAND_PREFIX}resetleaderboard / resetlb", value="Clears the leaderboard (requires 'bot admin' role).", inline=False)
    #      # Add more commands as needed
    #      await ctx.send(embed=embed)

    # --- Add !rank command here later ---
    # @commands.command(name='rank')
    # @commands.guild_only()
    # async def rank_command(self, ctx: commands.Context, member: discord.Member = None):
    #     """Checks your Unscramble rank and score, or another member's."""
    #     target_user = member or ctx.author # Check specified member or message author
    #     if not self.db_cog: ... # Handle DB error
    #     score = await self.db_cog.get_score(target_user.id)
    #     leaderboard_data = await self.db_cog.get_leaderboard_data()
    #     sorted_leaderboard = sorted(leaderboard_data.items(), key=lambda item: item[1], reverse=True)
    #     user_rank = -1
    #     for i, (user_id_key, s) in enumerate(sorted_leaderboard):
    #          if str(target_user.id) == user_id_key:
    #              user_rank = i + 1
    #              break
    #     # Create and send embed with score and rank


# Required setup function
async def setup(bot: commands.Bot):
    # Check dependency
    if bot.get_cog("Database") is None:
        log.critical("Database Cog not loaded. General Cog requires it.")
        raise commands.ExtensionFailed("general", "Database Cog not found.")
    await bot.add_cog(GeneralCog(bot))
    log.info("General Cog added to bot.")
