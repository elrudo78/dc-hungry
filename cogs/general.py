import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = discord.utils.utcnow()

    @commands.command()
    async def help(self, ctx):
        """Show all available commands"""
        embed = discord.Embed(
            title="🍔 Hungry Bot Help",
            description="**Game Commands:**\n"
                        "`!unscramble` - Start new game\n"
                        "`!hint` - Get a hint\n"
                        "`!leaderboard` - Show top scores\n\n"
                        "**Admin Commands:**\n"
                        "`!resetleaderboard` - Clear scores\n"
                        "`!stop` - Stop current game\n"
                        "`!reload <cog>` - Reload cog\n",
            color=0x00ff00
        )
        embed.set_footer(text=f"Online since {self.start_time.strftime('%Y-%m-%d %H:%M UTC')}")
        await ctx.send(embed=embed)

    @commands.command()
    async def ping(self, ctx):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000, 2)
        await ctx.send(f"🏓 Pong! {latency}ms")

    @commands.command(name="commands")
    async def command_list(self, ctx):
        """List all commands with descriptions"""
        command_info = []
        for cog in self.bot.cogs.values():
            for cmd in cog.get_commands():
                command_info.append(f"**{cmd.name}**: {cmd.help or 'No description'}")

        embed = discord.Embed(
            title="📜 Command List",
            description="\n".join(command_info),
            color=0x0099ff
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def stats(self, ctx):
        """Show bot statistics"""
        guild_count = len(self.bot.guilds)
        user_count = len(self.bot.users)
        uptime = discord.utils.utcnow() - self.start_time

        embed = discord.Embed(
            title="📊 Bot Stats",
            description=f"**Servers:** {guild_count}\n"
                        f"**Users:** {user_count}\n"
                        f"**Uptime:** {str(uptime).split('.')[0]}",
            color=0xff9900
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))
