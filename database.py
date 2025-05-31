import aiosqlite
from datetime import date
from typing import List, Tuple, Optional


class Database:
    def __init__(self, db_name: str = "streaks.db"):
        self.db_name = db_name

    async def init(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_name) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL
                )
            """)

            # Таблица сообщений (добавлен chat_id)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    user_id INTEGER,
                    chat_id INTEGER,
                    message_date DATE,
                    PRIMARY KEY (user_id, chat_id, message_date),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # Таблица серий общения (добавлен chat_id)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS streaks (
                    user_id1 INTEGER,
                    user_id2 INTEGER,
                    chat_id INTEGER,
                    current_streak INTEGER DEFAULT 0,
                    last_date DATE,
                    PRIMARY KEY (user_id1, user_id2, chat_id),
                    FOREIGN KEY (user_id1) REFERENCES users(user_id),
                    FOREIGN KEY (user_id2) REFERENCES users(user_id)
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

    async def mark_message(self, user_id: int, chat_id: int, message_date: date):
        """Отметить сообщение от пользователя"""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO messages (user_id, chat_id, message_date) VALUES (?, ?, ?)",
                (user_id, chat_id, message_date)
            )
            await db.commit()

    async def check_streaks(
            self, user_id: int, chat_id: int, today: date
    ) -> List[Tuple[str, int, bool]]:
        """Проверить и обновить серии общения"""
        result = []
        async with aiosqlite.connect(self.db_name) as db:
            # Получаем всех пользователей, которые писали сегодня в этом чате
            async with db.execute(
                    """
                    SELECT DISTINCT u.user_id, u.username 
                    FROM messages m1
                    JOIN users u ON m1.user_id = u.user_id
                    WHERE m1.message_date = ? 
                    AND m1.chat_id = ?
                    AND m1.user_id != ?
                    AND EXISTS (
                        SELECT 1 
                        FROM messages m2 
                        WHERE m2.user_id = ?
                        AND m2.chat_id = ?
                        AND m2.message_date = ?
                        AND m2.user_id != m1.user_id
                    )
                    """,
                    (today, chat_id, user_id, user_id, chat_id, today)
            ) as cursor:
                other_users = await cursor.fetchall()

            for other_id, other_username in other_users:
                # Убедимся, что user_id1 < user_id2 для консистентности
                min_id = min(user_id, other_id)
                max_id = max(user_id, other_id)

                # Проверяем существующую серию
                async with db.execute(
                        """
                        SELECT current_streak, last_date
                        FROM streaks
                        WHERE user_id1 = ? AND user_id2 = ? AND chat_id = ?
                        """,
                        (min_id, max_id, chat_id)
                ) as cursor:
                    streak_data = await cursor.fetchone()

                current_streak = 0
                is_new_streak = False

                if streak_data:
                    current_streak, last_date = streak_data
                    last_date = date.fromisoformat(last_date)

                    # Если последняя дата была вчера, увеличиваем серию
                    if (today - last_date).days == 1:
                        current_streak += 1
                        is_new_streak = True
                    # Если был пропуск или это сегодняшний день снова, сбрасываем серию
                    elif (today - last_date).days > 1:
                        current_streak = 1
                        is_new_streak = True
                    # Если это тот же день, не обновляем streak
                    elif (today - last_date).days == 0:
                        is_new_streak = False
                else:
                    # Новая серия
                    current_streak = 1
                    is_new_streak = True

                if is_new_streak:
                    # Обновляем серию только если это новый стрик
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO streaks 
                        (user_id1, user_id2, chat_id, current_streak, last_date)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (min_id, max_id, chat_id, current_streak, today)
                    )

                result.append((other_username, current_streak, is_new_streak))

            await db.commit()
        return result

    async def get_user_streaks(self, user_id: int, chat_id: int) -> List[Tuple[str, int]]:
        """Получить все активные серии пользователя в конкретном чате"""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                    """
                    SELECT 
                        CASE 
                            WHEN s.user_id1 = ? THEN u2.username
                            ELSE u1.username
                        END as other_username,
                        s.current_streak
                    FROM streaks s
                    JOIN users u1 ON s.user_id1 = u1.user_id
                    JOIN users u2 ON s.user_id2 = u2.user_id
                    WHERE (s.user_id1 = ? OR s.user_id2 = ?)
                    AND s.chat_id = ?
                    ORDER BY s.current_streak DESC
                    """,
                    (user_id, user_id, user_id, chat_id)
            ) as cursor:
                return await cursor.fetchall()

    async def get_user_id_by_username(self, username: str) -> Optional[int]:
        """Получить ID пользователя по его username"""
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                "SELECT user_id FROM users WHERE username = ?",
                (username,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None 