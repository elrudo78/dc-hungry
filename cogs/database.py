import sqlite3
import json
import logging
from discord.ext import commands, tasks

class Database(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.leaderboard = {}
        self.dirty = False  # Track unsaved changes
        self.logger = logging.getLogger(__name__)
        self.conn = sqlite3.connect('leaderboard.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        self.save_task = self.auto_save.start()

    def _init_db(self):
        """Initialize database structure"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS leaderboard (
                    user_id TEXT PRIMARY KEY,
                    score INTEGER DEFAULT 0
                )
            ''')
            self.conn.commit()
            self._load_leaderboard()
            self.logger.info("Database initialized")
        except Exception as e:
            self.logger.error(f"Database init failed: {e}")
            raise

    def _load_leaderboard(self):
        """Load entire leaderboard from SQLite"""
        try:
            self.cursor.execute("SELECT user_id, score FROM leaderboard")
            self.leaderboard = {str(row[0]): row[1] for row in self.cursor.fetchall()}
            self.logger.info(f"Loaded {len(self.leaderboard)} entries")
        except Exception as e:
            self.logger.error(f"Load failed: {e}")
            self.leaderboard = {}

    def get_leaderboard(self):
        """Return current leaderboard copy"""
        return self.leaderboard.copy()

    def update_score(self, user_id, points):
        """Update score with dirty flag tracking"""
        try:
            user_id = str(user_id)
            current = self.leaderboard.get(user_id, 0)
            new_score = max(0, current + points)
            
            # Update memory
            self.leaderboard[user_id] = new_score
            self.dirty = True
            
            # Queue SQL update
            self.cursor.execute('''
                INSERT OR REPLACE INTO leaderboard (user_id, score)
                VALUES (?, ?)
            ''', (user_id, new_score))
            
        except Exception as e:
            self.logger.error(f"Score update failed: {e}")

    @tasks.loop(seconds=60)
    async def auto_save(self):
        """Periodic save with dirty check"""
        if self.dirty:
            try:
                self.conn.commit()
                self.dirty = False
                self.logger.info("Auto-saved leaderboard")
            except Exception as e:
                self.logger.error(f"Auto-save failed: {e}")

    def force_save(self):
        """Immediate save (for admin commands)"""
        try:
            self.conn.commit()
            self.dirty = False
            self.logger.info("Force-saved leaderboard")
            return True
        except Exception as e:
            self.logger.error(f"Force save failed: {e}")
            return False

    def cog_unload(self):
        """Cleanup on bot shutdown"""
        self.auto_save.cancel()
        if self.dirty:
            self.force_save()
        self.conn.close()
        self.logger.info("Database connection closed")

async def setup(bot):
    await bot.add_cog(Database(bot))
