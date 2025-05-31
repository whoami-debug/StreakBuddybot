import aiosqlite
from datetime import date, datetime, timezone
from typing import List, Tuple, Optional


class Database:
    def __init__(self, db_name: str = "streak_bot.db"):
        self.db_name = db_name

    async def init(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_name) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица сообщений
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    user_id INTEGER,
                    partner_id INTEGER,
                    chat_date DATE,
                    PRIMARY KEY (user_id, partner_id, chat_date),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (partner_id) REFERENCES users(user_id)
                )
            """)
            
            # Таблица пар для стриков
            await db.execute("""
                CREATE TABLE IF NOT EXISTS streak_pairs (
                    user_id INTEGER,
                    partner_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, partner_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (partner_id) REFERENCES users(user_id)
                )
            """)
            
            # Таблица запросов на стрик
            await db.execute("""
                CREATE TABLE IF NOT EXISTS streak_requests (
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (from_user_id, to_user_id),
                    FOREIGN KEY (from_user_id) REFERENCES users(user_id),
                    FOREIGN KEY (to_user_id) REFERENCES users(user_id)
                )
            """)
            
            await db.commit()

    async def add_user(self, user_id: int, username: str):
        """Добавление нового пользователя"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()

    async def get_user_id_by_username(self, username: str) -> Optional[int]:
        """Получение ID пользователя по username"""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT user_id FROM users WHERE username = ?",
                (username,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    async def add_streak_request(self, from_user_id: int, to_user_id: int):
        """Добавление запроса на стрик"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO streak_requests (from_user_id, to_user_id) VALUES (?, ?)",
                (from_user_id, to_user_id)
            )
            await db.commit()

    async def get_streak_request(self, from_user_id: int, to_user_id: int) -> bool:
        """Проверка существования запроса на стрик"""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT 1 FROM streak_requests WHERE from_user_id = ? AND to_user_id = ?",
                (from_user_id, to_user_id)
            ) as cursor:
                result = await cursor.fetchone()
                return bool(result)

    async def remove_streak_request(self, from_user_id: int, to_user_id: int):
        """Удаление запроса на стрик"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "DELETE FROM streak_requests WHERE from_user_id = ? AND to_user_id = ?",
                (from_user_id, to_user_id)
            )
            await db.commit()

    async def add_streak_pair(self, user_id: int, partner_id: int):
        """Добавление пары пользователей для отслеживания стрика"""
        async with aiosqlite.connect(self.db_name) as db:
            # Добавляем в обе стороны
            await db.execute(
                "INSERT OR REPLACE INTO streak_pairs (user_id, partner_id) VALUES (?, ?)",
                (user_id, partner_id)
            )
            await db.execute(
                "INSERT OR REPLACE INTO streak_pairs (user_id, partner_id) VALUES (?, ?)",
                (partner_id, user_id)
            )
            await db.commit()

    async def mark_message(self, user_id: int, partner_id: int, chat_date: date):
        """Отметка сообщения между пользователями"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO messages (user_id, partner_id, chat_date) VALUES (?, ?, ?)",
                (user_id, partner_id, chat_date)
            )
            await db.commit()

    async def check_both_marked(self, user_id: int, partner_id: int, chat_date: date) -> bool:
        """Проверка, отметили ли оба пользователя общение в указанный день"""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("""
                SELECT COUNT(*) FROM messages 
                WHERE (user_id = ? AND partner_id = ? AND chat_date = ?) 
                OR (user_id = ? AND partner_id = ? AND chat_date = ?)
            """, (user_id, partner_id, chat_date, partner_id, user_id, chat_date)) as cursor:
                count = (await cursor.fetchone())[0]
                return count == 2

    async def get_last_chat_date(self, user_id: int, partner_id: int) -> Optional[date]:
        """Получение даты последнего общения между пользователями"""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("""
                SELECT MAX(chat_date) FROM messages 
                WHERE (user_id = ? AND partner_id = ?) 
                OR (user_id = ? AND partner_id = ?)
            """, (user_id, partner_id, partner_id, user_id)) as cursor:
                result = await cursor.fetchone()
                return datetime.strptime(result[0], '%Y-%m-%d').date() if result[0] else None

    async def get_streak_count(self, user_id: int, partner_id: int) -> int:
        """Получение текущего количества дней в стрике"""
        async with aiosqlite.connect(self.db_name) as db:
            today = datetime.now(timezone.utc).date()
            
            # Получаем все даты общения
            async with db.execute("""
                SELECT DISTINCT chat_date 
                FROM messages 
                WHERE ((user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?))
                AND chat_date <= ?
                ORDER BY chat_date DESC
            """, (user_id, partner_id, partner_id, user_id, today)) as cursor:
                dates = [datetime.strptime(row[0], '%Y-%m-%d').date() for row in await cursor.fetchall()]

            if not dates:
                return 0

            # Считаем непрерывную серию
            streak = 0
            current_date = today
            
            for chat_date in dates:
                if (current_date - chat_date).days <= 1:
                    streak += 1
                    current_date = chat_date
                else:
                    break

            return streak

    async def get_user_streaks(self, user_id: int, chat_id: int) -> List[Tuple[str, int]]:
        """Получение списка стриков пользователя"""
        async with aiosqlite.connect(self.db_name) as db:
            # Получаем всех партнеров пользователя
            async with db.execute("""
                SELECT u.username, sp.partner_id
                FROM streak_pairs sp
                JOIN users u ON u.user_id = sp.partner_id
                WHERE sp.user_id = ?
            """, (user_id,)) as cursor:
                partners = await cursor.fetchall()

            result = []
            for username, partner_id in partners:
                streak_count = await self.get_streak_count(user_id, partner_id)
                result.append((username, streak_count))

            return result 