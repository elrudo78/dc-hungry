import discord
import asyncio
from discord.ext import commands
from discord import app_commands

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game_manager = bot.get_cog("Unscramble").game_manager if bot.get_cog("Unscramble") else None

    @commands.command()
    @commands.has_role("bot admin")
    async def stop(self, ctx):
        """Force stop current game in this channel"""
        if not self.game_manager:
            return await ctx.send("❌ Game system not loaded!")
        
        if ctx.channel.id in self.game_manager.active_games:
            del self.game_manager.active_games[ctx.channel.id]
            await ctx.send("✅ Game stopped!")
        else:
            await ctx.send("❌ No active game here!")

    @commands.command()
    @commands.has_role("bot admin")
    async def cancelhints(self, ctx):
        """Cancel scheduled hint tasks"""
        if not self.game_manager:
            return await ctx.send("❌ Game system not loaded!")
        
        game_data = self.game_manager.active_games.get(ctx.channel.id)
        if game_data and "hint_tasks" in game_data:
            for task in game_data["hint_tasks"]:
                task.cancel()
            await ctx.send("✅ Hint tasks canceled!")
        else:
            await ctx.send("❌ No active hints!")

    @commands.command()
    @commands.has_role("bot admin")
    async def resetleaderboard(self, ctx):
        """Reset entire leaderboard (SQLite version)"""
        db_cog = self.bot.get_cog("Database")
        if not db_cog:
            return await ctx.send("❌ Database system not loaded!")
        
        try:
            db_cog.cursor.execute("DELETE FROM leaderboard")
            db_cog.conn.commit()
            await ctx.send("✅ Leaderboard wiped clean!")
        except Exception as e:
            await ctx.send(f"❌ Failed to reset: {str(e)}")

    @commands.command()
    @commands.has_role("bot admin")
    async def reload(self, ctx, cog: str):
        """Reload a cog dynamically"""
        try:
            await self.bot.reload_extension(f"cogs.{cog.lower()}")
            await ctx.send(f"✅ Reloaded `{cog}` cog!")
        except Exception as e:
            await ctx.send(f"❌ Reload failed: {str(e)}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
