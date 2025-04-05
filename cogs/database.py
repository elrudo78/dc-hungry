# COMPLETELY REPLACE WITH THIS CODE
import sqlite3
import logging
from discord.ext import commands, tasks

class Database(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect('leaderboard.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        self.save_task = self.auto_save.start()
        self.logger = logging.getLogger(__name__)

    def _init_db(self):
        """Initialize database tables"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS leaderboard (
                user_id TEXT PRIMARY KEY,
                score INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()

    def get_leaderboard(self):
        """Retrieve entire leaderboard"""
        self.cursor.execute("SELECT user_id, score FROM leaderboard")
        return {row[0]: row[1] for row in self.cursor.fetchall()}

    def update_score(self, user_id, points):
        """Update a user's score atomically"""
        try:
            self.cursor.execute('''
                INSERT INTO leaderboard (user_id, score)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET score = score + ?
            ''', (str(user_id), points, points))
            self.conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to update score: {e}")

    @tasks.loop(seconds=60)
    async def auto_save(self):
        """Periodic commit as backup"""
        try:
            self.conn.commit()
            self.logger.info("Auto-saved leaderboard")
        except Exception as e:
            self.logger.error(f"Auto-save failed: {e}")

    def cog_unload(self):
        """Cleanup on cog unload"""
        self.auto_save.cancel()
        self.conn.close()
        self.logger.info("Database connection closed")

async def setup(bot):
    await bot.add_cog(Database(bot))
