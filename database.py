import aiosqlite
from datetime import date, datetime, timezone
from typing import List, Tuple, Optional, Any
import logging

# logger = logging.getLogger(__name__) # Используем глобальный логгер из bot.py или настраиваем свой
# Для простоты пока оставим так, но лучше передавать logger или использовать getLogger(__name__)

class Database:
    def __init__(self, db_name: str = "streak_bot.db"):
        self.db_name = db_name
        self.logger = logging.getLogger(__name__ + ".database") # Логгер для этого класса

    async def init(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_name) as db:
            # Проверяем и добавляем столбец balance в таблицу users, если его нет
            async with db.execute("PRAGMA table_info(users)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            if 'balance' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
                self.logger.info("DB: Added 'balance' column to 'users' table.")
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    balance INTEGER DEFAULT 0, -- Добавлено здесь для новых БД
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    partner_id INTEGER,
                    chat_date DATE,
                    chat_id_context INTEGER, -- НОВОЕ ПОЛЕ: ID чата, где было сообщение
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, partner_id, chat_date, chat_id_context), -- Обновляем UNIQUE constraint
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (partner_id) REFERENCES users(user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS streak_pairs (
                    user_id INTEGER,
                    partner_id INTEGER,
                    last_streak_date DATE,
                    streak_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, partner_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (partner_id) REFERENCES users(user_id)
                )
            """)
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS webapp_daily_marks (
                    marker_id INTEGER,
                    marked_partner_id INTEGER,
                    mark_date DATE,
                    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (marker_id, marked_partner_id, mark_date),
                    FOREIGN KEY (marker_id) REFERENCES users(user_id),
                    FOREIGN KEY (marked_partner_id) REFERENCES users(user_id)
                )
            """)
            # Новая таблица для заморозок
            await db.execute("""
                CREATE TABLE IF NOT EXISTS streak_freezes (
                    user_id INTEGER NOT NULL,
                    partner_id INTEGER NOT NULL,
                    freeze_end_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, partner_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (partner_id) REFERENCES users(user_id)
                )
            """)
            await db.commit()
            self.logger.info("База данных инициализирована/проверена (с users.balance и streak_freezes).")

    async def add_user(self, user_id: int, username: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()
            # self.logger.info(f"DB: User {username} ({user_id}) added/updated.") # Может быть слишком много логов

    async def get_user_id_by_username(self, username: str) -> Optional[int]:
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT user_id FROM users WHERE username = ?", (username,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    async def get_username_by_id(self, user_id: int) -> Optional[str]:
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    if result:
                        # self.logger.info(f"DB: Username for {user_id} is {result[0]}")
                        return result[0]
                    else:
                        self.logger.warning(f"DB: Username for {user_id} not found")
                        return None
        except Exception as e:
            self.logger.error(f"DB: Error in get_username_by_id for {user_id}: {e}", exc_info=True)
            return None

    async def add_streak_request(self, from_user_id: int, to_user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT OR REPLACE INTO streak_requests (from_user_id, to_user_id) VALUES (?, ?)", (from_user_id, to_user_id))
            await db.commit()

    async def get_streak_request(self, from_user_id: int, to_user_id: int) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT 1 FROM streak_requests WHERE from_user_id = ? AND to_user_id = ?", (from_user_id, to_user_id)) as cursor:
                return bool(await cursor.fetchone())

    async def remove_streak_request(self, from_user_id: int, to_user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("DELETE FROM streak_requests WHERE from_user_id = ? AND to_user_id = ?", (from_user_id, to_user_id))
            await db.commit()

    async def add_streak_pair(self, user_id: int, partner_id: int):
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute("SELECT 1 FROM streak_pairs WHERE (user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?)", (user_id, partner_id, partner_id, user_id)) as cursor:
                    if await cursor.fetchone():
                        self.logger.info(f"DB: Streak pair {user_id}-{partner_id} already exists.")
                        return
                await db.execute("INSERT INTO streak_pairs (user_id, partner_id, streak_count, last_streak_date) VALUES (?, ?, 0, NULL)", (user_id, partner_id))
                await db.execute("INSERT INTO streak_pairs (user_id, partner_id, streak_count, last_streak_date) VALUES (?, ?, 0, NULL)", (partner_id, user_id))
                await db.commit()
                self.logger.info(f"DB: Created new streak pair {user_id}-{partner_id}")
        except Exception as e:
            self.logger.error(f"DB: Error in add_streak_pair for {user_id}-{partner_id}: {e}", exc_info=True)

    async def _update_streak_state(self, db: Any, user_id1: int, user_id2: int, interaction_date: date) -> bool:
        """
        Внутренний метод для обновления состояния стрика для пары.
        Возвращает True, если стрик был изменен (увеличен, сброшен), иначе False.
        """
        try:
            async with db.execute("SELECT last_streak_date, streak_count FROM streak_pairs WHERE user_id = ? AND partner_id = ?", (user_id1, user_id2)) as cursor_streak:
                streak_info = await cursor_streak.fetchone()
            
            if not streak_info:
                self.logger.error(f"DB: _update_streak_state - Streak pair {user_id1}-{user_id2} not found! Assuming new pair setup error or data inconsistency.")
                # Если пары нет, ее должен был создать add_streak_pair. Если мы здесь, то что-то не так.
                # Не будем создавать пару здесь, чтобы не маскировать проблему.
                return False

            last_streak_dt_str, current_streak = streak_info
            current_streak = current_streak or 0
            last_streak_dt = datetime.strptime(last_streak_dt_str, '%Y-%m-%d').date() if last_streak_dt_str else None

            if last_streak_dt == interaction_date:
                self.logger.info(f"DB: _update_streak_state - Interaction for {user_id1}-{user_id2} on {interaction_date} already processed. Streak: {current_streak}")
                return False # Уже обработано для этой даты

            new_streak = current_streak
            updated_streak_date = last_streak_dt # По умолчанию не меняем, если не выполняются условия ниже

            if not last_streak_dt: # Первый стрик
                new_streak = 1
                updated_streak_date = interaction_date
                self.logger.info(f"DB: _update_streak_state - Starting new streak for {user_id1}-{user_id2} to 1 on {interaction_date}")
            elif (interaction_date - last_streak_dt).days == 1: # Продолжение
                new_streak = current_streak + 1
                updated_streak_date = interaction_date
                self.logger.info(f"DB: _update_streak_state - Continuing streak for {user_id1}-{user_id2} to {new_streak} on {interaction_date}")
            elif (interaction_date - last_streak_dt).days > 1: # Пропуск, сброс
                new_streak = 1
                updated_streak_date = interaction_date
                self.logger.info(f"DB: _update_streak_state - Streak reset for {user_id1}-{user_id2}. New streak: 1 on {interaction_date}")
            elif interaction_date < last_streak_dt: # Сообщение из прошлого, не должно влиять на будущий стрик
                self.logger.info(f"DB: _update_streak_state - Interaction date {interaction_date} is older than last_streak_dt {last_streak_dt} for {user_id1}-{user_id2}. No update.")
                return False # Не обновляем, если дата взаимодействия раньше последней даты стрика
            else: # Это случай interaction_date == last_streak_dt, уже покрыт выше.
                  # Или какая-то другая непредвиденная логика дат. Оставляем без изменений.
                self.logger.warning(f"DB: _update_streak_state - Unhandled date condition for {user_id1}-{user_id2}. Interaction: {interaction_date}, Last: {last_streak_dt}. No update.")
                return False

            if new_streak != current_streak or updated_streak_date != last_streak_dt:
                iso_date = updated_streak_date.isoformat() if updated_streak_date else None
                await db.execute("UPDATE streak_pairs SET last_streak_date = ?, streak_count = ? WHERE user_id = ? AND partner_id = ?", (iso_date, new_streak, user_id1, user_id2))
                await db.execute("UPDATE streak_pairs SET last_streak_date = ?, streak_count = ? WHERE user_id = ? AND partner_id = ?", (iso_date, new_streak, user_id2, user_id1))
                self.logger.info(f"DB: _update_streak_state - Updated streak_pairs for {user_id1}-{user_id2} to count {new_streak}, date {iso_date}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"DB: Error in _update_streak_state for {user_id1}-{user_id2} on {interaction_date}: {e}", exc_info=True)
            return False

    async def mark_message(self, user_id: int, partner_id: int, chat_date: date, chat_id_context: int):
        """Отметка сообщения и обновление стрика, если выполнены условия."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO messages (user_id, partner_id, chat_date, chat_id_context) VALUES (?, ?, ?, ?)",
                    (user_id, partner_id, chat_date, chat_id_context)
                )
                self.logger.info(f"DB: mark_message - Recorded message from {user_id} to {partner_id} on {chat_date} in chat {chat_id_context}")

                async with db.execute("""
                    SELECT 1 FROM messages 
                    WHERE user_id = ? AND partner_id = ? AND chat_date = ? AND chat_id_context = ?
                """, (partner_id, user_id, chat_date, chat_id_context)) as cursor_partner_message:
                    partner_also_messaged_today_in_this_chat = await cursor_partner_message.fetchone()

                if partner_also_messaged_today_in_this_chat:
                    self.logger.info(f"DB: mark_message - Confirmed two-way interaction for {user_id}-{partner_id} on {chat_date} in chat {chat_id_context}. Attempting to update streak state.")
                    await self._update_streak_state(db, user_id, partner_id, chat_date) # Используем новый внутренний метод
                else:
                    self.logger.info(f"DB: mark_message - One-way interaction for {user_id} towards {partner_id} on {chat_date} in chat {chat_id_context}. No streak update yet.")
                await db.commit()
        except Exception as e:
            self.logger.error(f"DB: Error in mark_message for {user_id}-{partner_id} on {chat_date} in {chat_id_context}: {e}", exc_info=True)

    async def mark_webapp_interaction(self, user_id: int, partner_id: int, mark_date: date) -> Tuple[str, bool]:
        status_message = "Произошла ошибка при обработке вашего запроса."
        streak_updated_flag = False
        try:
            async with aiosqlite.connect(self.db_name) as db:
                # Проверяем, не подтвержден ли уже стрик за эту дату
                async with db.execute("SELECT last_streak_date FROM streak_pairs WHERE user_id = ? AND partner_id = ?", (user_id, partner_id)) as csp:
                    sp_info = await csp.fetchone()
                if sp_info and sp_info[0] and datetime.strptime(sp_info[0], '%Y-%m-%d').date() == mark_date:
                    status_message = "Общение за сегодня уже подтверждено и стрик обновлен ранее."
                    self.logger.info(f"DB: mark_webapp_interaction - Streak for {user_id}-{partner_id} on {mark_date} already confirmed in streak_pairs.")
                    return status_message, False

                # Добавляем отметку текущего пользователя
                await db.execute("INSERT OR IGNORE INTO webapp_daily_marks (marker_id, marked_partner_id, mark_date) VALUES (?, ?, ?)", (user_id, partner_id, mark_date))
                self.logger.info(f"DB: mark_webapp_interaction - User {user_id} marked interaction with {partner_id} for {mark_date}.")

                # Проверяем, есть ли ответная отметка от партнера
                async with db.execute("SELECT 1 FROM webapp_daily_marks WHERE marker_id = ? AND marked_partner_id = ? AND mark_date = ?", (partner_id, user_id, mark_date)) as cursor_partner_mark:
                    partner_also_marked = await cursor_partner_mark.fetchone()

                if partner_also_marked:
                    self.logger.info(f"DB: mark_webapp_interaction - Reciprocal mark found for {user_id}-{partner_id} on {mark_date}. Attempting to update streak state.")
                    updated = await self._update_streak_state(db, user_id, partner_id, mark_date)
                    if updated:
                        status_message = "Стрик обновлен! Вы оба отметили общение сегодня через веб-интерфейс."
                        streak_updated_flag = True
                        # Удаляем обработанные отметки
                        await db.execute("DELETE FROM webapp_daily_marks WHERE mark_date = ? AND ((marker_id = ? AND marked_partner_id = ?) OR (marker_id = ? AND marked_partner_id = ?))", 
                                         (mark_date, user_id, partner_id, partner_id, user_id))
                        self.logger.info(f"DB: mark_webapp_interaction - Processed and deleted webapp_daily_marks for {user_id}-{partner_id} on {mark_date}.")
                    else:
                        # _update_streak_state вернул False, значит стрик уже был обновлен за эту дату или не изменился
                        status_message = "Общение за сегодня уже было учтено ранее."
                        # Можно также удалить отметки, если они все еще там, чтобы не висели
                        await db.execute("DELETE FROM webapp_daily_marks WHERE mark_date = ? AND ((marker_id = ? AND marked_partner_id = ?) OR (marker_id = ? AND marked_partner_id = ?))", 
                                         (mark_date, user_id, partner_id, partner_id, user_id))
                        self.logger.info(f"DB: mark_webapp_interaction - _update_streak_state returned False for {user_id}-{partner_id} on {mark_date}. Marks cleaned up.")
                else:
                    status_message = "Ваша отметка сохранена. Ожидаем подтверждения от партнера."
                
                await db.commit()
            return status_message, streak_updated_flag
        except Exception as e:
            self.logger.error(f"DB: Error in mark_webapp_interaction for {user_id}-{partner_id} on {mark_date}: {e}", exc_info=True)
            # В случае ошибки пытаемся откатить транзакцию, если соединение еще живо
            if db.is_connected(): 
                await db.rollback()
            return "Произошла ошибка при сохранении вашей отметки. Попробуйте позже.", False

    async def check_both_marked(self, user_id: int, partner_id: int, chat_date: date, chat_id_context: int) -> bool:
        """Проверка, отметились ли оба пользователя сообщениями в указанный день В УКАЗАННОМ ЧАТЕ."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                # Проверяем сообщение от user_id к partner_id
                async with db.execute("SELECT 1 FROM messages WHERE user_id = ? AND partner_id = ? AND chat_date = ? AND chat_id_context = ?", (user_id, partner_id, chat_date, chat_id_context)) as c1:
                    msg1_exists = await c1.fetchone()
                # Проверяем сообщение от partner_id к user_id
                async with db.execute("SELECT 1 FROM messages WHERE user_id = ? AND partner_id = ? AND chat_date = ? AND chat_id_context = ?", (partner_id, user_id, chat_date, chat_id_context)) as c2:
                    msg2_exists = await c2.fetchone()
                
                both_marked = bool(msg1_exists and msg2_exists)
                self.logger.info(f"DB: check_both_marked for {user_id}-{partner_id} on {chat_date} in chat {chat_id_context}: {both_marked} (msg1: {bool(msg1_exists)}, msg2: {bool(msg2_exists)})")
                return both_marked
        except Exception as e:
            self.logger.error(f"DB: Error in check_both_marked for {user_id}-{partner_id}, date {chat_date}, chat {chat_id_context}: {e}", exc_info=True)
            return False

    async def get_streak_count(self, user_id: int, partner_id: int) -> int:
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute("SELECT streak_count FROM streak_pairs WHERE user_id = ? AND partner_id = ?", (user_id, partner_id)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"DB: Error in get_streak_count for {user_id}-{partner_id}: {e}", exc_info=True)
            return 0

    async def get_user_streaks(self, current_user_id: int, current_chat_id: int) -> List[Tuple[int, str, int]]:
        """Получение списка стриков пользователя.
        Возвращает список кортежей (partner_id, partner_username, streak_count).
        Если current_chat_id это ID группы, то фильтрует стрики по активности в этой группе.
        """
        streaks_to_show: List[Tuple[int, str, int]] = []
        try:
            async with aiosqlite.connect(self.db_name) as db:
                # 1. Получаем все глобальные стрики пользователя
                async with db.execute("""
                    SELECT u.user_id, u.username, sp.streak_count
                    FROM streak_pairs sp
                    JOIN users u ON u.user_id = sp.partner_id
                    WHERE sp.user_id = ? AND sp.streak_count > 0 
                    ORDER BY sp.streak_count DESC
                """, (current_user_id,)) as cursor:
                    all_global_streaks = await cursor.fetchall()
                
                self.logger.info(f"DB: get_user_streaks - Found {len(all_global_streaks)} global streaks for user {current_user_id}.")

                # 2. Фильтруем в зависимости от типа чата
                # Если current_chat_id == current_user_id, это сигнал, что запрос из ЛС/webapp (показываем все)
                # Иначе, это ID группы, и мы должны фильтровать.
                is_group_context = current_chat_id != current_user_id 

                if not is_group_context:
                    self.logger.info(f"DB: get_user_streaks - Private context (chat_id={current_chat_id}), showing all global streaks.")
                    for partner_id, partner_username, streak_count in all_global_streaks:
                        streaks_to_show.append((partner_id, partner_username, streak_count))
                else:
                    self.logger.info(f"DB: get_user_streaks - Group context (chat_id={current_chat_id}), filtering streaks.")
                    for partner_id, partner_username, streak_count in all_global_streaks:
                        # Проверяем, было ли взаимодействие current_user_id с partner_id в current_chat_id
                        async with db.execute("""
                            SELECT 1 FROM messages 
                            WHERE chat_id_context = ? AND 
                                  ((user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?))
                            LIMIT 1
                        """, (current_chat_id, current_user_id, partner_id, partner_id, current_user_id)) as msg_cursor:
                            interaction_in_this_chat = await msg_cursor.fetchone()
                        
                        if interaction_in_this_chat:
                            self.logger.info(f"DB: get_user_streaks - Streak with {partner_username} ({partner_id}) IS relevant to group {current_chat_id}.")
                            streaks_to_show.append((partner_id, partner_username, streak_count))
                        else:
                            self.logger.info(f"DB: get_user_streaks - Streak with {partner_username} ({partner_id}) NOT relevant to group {current_chat_id} (no messages).")
            
            self.logger.info(f"DB: get_user_streaks for user {current_user_id} in chat {current_chat_id} returning: {streaks_to_show}")
            return streaks_to_show
        except Exception as e:
            self.logger.error(f"DB: Error in get_user_streaks for user {current_user_id}, chat {current_chat_id}: {e}", exc_info=True)
            return []

    async def get_last_chat_date(self, user_id: int, partner_id: int) -> Optional[date]:
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT last_streak_date FROM streak_pairs WHERE user_id = ? AND partner_id = ?", (user_id, partner_id)) as cursor:
                result = await cursor.fetchone()
                return datetime.strptime(result[0], '%Y-%m-%d').date() if result and result[0] else None

    async def reset_streak(self, user_id: int, partner_id: int) -> bool:
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute("SELECT streak_count FROM streak_pairs WHERE user_id = ? AND partner_id = ?", (user_id, partner_id)) as cursor:
                    if not await cursor.fetchone(): return False # Нет такого стрика
                
                await db.execute("UPDATE streak_pairs SET streak_count = 0, last_streak_date = NULL WHERE (user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?)", (user_id, partner_id, partner_id, user_id))
                # Удаляем сообщения только между этими пользователями, но ВЕЗДЕ, т.к. стрик глобальный.
                # Если нужно удалять только из контекста чата, логика reset усложнится.
                await db.execute("DELETE FROM messages WHERE (user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?)", (user_id, partner_id, partner_id, user_id))
                await db.execute("DELETE FROM webapp_daily_marks WHERE ((marker_id = ? AND marked_partner_id = ?) OR (marker_id = ? AND marked_partner_id = ?))", (user_id, partner_id, partner_id, user_id)) # Также чистим webapp_daily_marks
                await db.commit()
                self.logger.info(f"DB: Streak reset for {user_id}-{partner_id}, including webapp marks.")
                return True
        except Exception as e:
            self.logger.error(f"DB: Error in reset_streak for {user_id}-{partner_id}: {e}", exc_info=True)
            return False 

    async def reset_inactive_streaks(self, current_date: date):
        """
        Сбрасывает streak_count на 0 для пар, где последнее взаимодействие
        было не вчера и не сегодня (т.е. пропущено более одного дня),
        ЕСЛИ СТРИК НЕ ЗАМОРОЖЕН.
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                # Выбираем user_id, partner_id, last_streak_date, streak_count
                async with db.execute("SELECT user_id, partner_id, last_streak_date, streak_count FROM streak_pairs WHERE streak_count > 0") as cursor:
                    active_streaks = await cursor.fetchall()
                
                count_reset = 0
                for user_id, partner_id, last_streak_dt_str, streak_count in active_streaks:
                    # Проверяем активную заморозку ПЕРЕД любыми действиями
                    active_freeze_end_date = await self.get_active_freeze(user_id, partner_id, current_date)
                    if active_freeze_end_date:
                        self.logger.info(f"DB: reset_inactive_streaks - Streak for {user_id}-{partner_id} is frozen until {active_freeze_end_date}. Skipping reset.")
                        continue # Пропускаем сброс, если стрик заморожен

                    if not last_streak_dt_str: # Если даты нет, но стрик > 0 - это аномалия, сбрасываем
                        self.logger.warning(f"DB: reset_inactive_streaks - Anomaly: streak_count > 0 ({streak_count}) but no last_streak_date for {user_id}-{partner_id}. Resetting.")
                        await db.execute("UPDATE streak_pairs SET streak_count = 0 WHERE user_id = ? AND partner_id = ?", (user_id, partner_id))
                        await db.execute("UPDATE streak_pairs SET streak_count = 0 WHERE user_id = ? AND partner_id = ?", (partner_id, user_id))
                        count_reset += 1
                        continue

                    last_streak_dt = datetime.strptime(last_streak_dt_str, '%Y-%m-%d').date()
                    
                    # Если последнее взаимодействие было не вчера и не сегодня, то стрик сбрасывается
                    # (current_date - last_streak_dt).days == 1 означает, что последнее общение было вчера - это ОК
                    # (current_date - last_streak_dt).days == 0 означает, что последнее общение было сегодня - это ОК
                    if (current_date - last_streak_dt).days > 1:
                        self.logger.info(f"DB: reset_inactive_streaks - Resetting streak for {user_id}-{partner_id}. Last streak: {last_streak_dt}, Current date: {current_date}, Old count: {streak_count}")
                        await db.execute("UPDATE streak_pairs SET streak_count = 0 WHERE user_id = ? AND partner_id = ?", (user_id, partner_id))
                        # Обновляем и симметричную пару
                        await db.execute("UPDATE streak_pairs SET streak_count = 0 WHERE user_id = ? AND partner_id = ?", (partner_id, user_id))
                        count_reset += 1
                
                if count_reset > 0:
                    await db.commit()
                    self.logger.info(f"DB: reset_inactive_streaks - Successfully reset {count_reset} inactive streaks.")
                else:
                    self.logger.info(f"DB: reset_inactive_streaks - No streaks to reset.")
        except Exception as e:
            self.logger.error(f"DB: Error in reset_inactive_streaks for date {current_date}: {e}", exc_info=True) 

    # --- Функции для баланса и заморозки стриков ---

    async def get_user_balance(self, user_id: int) -> int:
        """Получает текущий баланс пользователя."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"DB: Error getting balance for user {user_id}: {e}", exc_info=True)
            return 0 # Возвращаем 0 в случае ошибки, чтобы не блокировать операции

    async def update_user_balance(self, user_id: int, amount_change: int, allow_negative: bool = False) -> bool:
        """Обновляет баланс пользователя. amount_change может быть положительным (начисление) или отрицательным (списание)."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                current_balance = await self.get_user_balance(user_id) # Получаем текущий баланс через существующий метод
                
                if not allow_negative and (current_balance + amount_change < 0):
                    self.logger.warning(f"DB: Failed to update balance for user {user_id}. Change {amount_change} would result in negative balance ({current_balance + amount_change}).")
                    return False
                
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount_change, user_id))
                await db.commit()
                self.logger.info(f"DB: Updated balance for user {user_id} by {amount_change}. New balance: {current_balance + amount_change}")
                return True
        except Exception as e:
            self.logger.error(f"DB: Error updating balance for user {user_id}: {e}", exc_info=True)
            return False

    async def add_streak_freeze(self, user_id: int, partner_id: int, freeze_end_date: date) -> bool:
        """Добавляет или обновляет заморозку стрика для пары."""
        try:
            iso_freeze_end_date = freeze_end_date.isoformat()
            async with aiosqlite.connect(self.db_name) as db:
                # INSERT OR REPLACE, чтобы обновить существующую заморозку, если она есть
                await db.execute("INSERT OR REPLACE INTO streak_freezes (user_id, partner_id, freeze_end_date) VALUES (?, ?, ?)", 
                                 (user_id, partner_id, iso_freeze_end_date))
                # Симметричная запись для партнера, если мы хотим, чтобы заморозка была видна обоим
                # Это вопрос дизайна: замораживает один, но действует для обоих? Пока да.
                await db.execute("INSERT OR REPLACE INTO streak_freezes (user_id, partner_id, freeze_end_date) VALUES (?, ?, ?)", 
                                 (partner_id, user_id, iso_freeze_end_date))
                await db.commit()
                self.logger.info(f"DB: Added/Updated streak freeze for pair {user_id}-{partner_id} until {iso_freeze_end_date}.")
                return True
        except Exception as e:
            self.logger.error(f"DB: Error adding streak freeze for {user_id}-{partner_id}: {e}", exc_info=True)
            return False

    async def get_active_freeze(self, user_id: int, partner_id: int, current_date: date) -> Optional[date]:
        """Проверяет, активна ли заморозка для пары на указанную current_date."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                async with db.execute("SELECT freeze_end_date FROM streak_freezes WHERE user_id = ? AND partner_id = ?", (user_id, partner_id)) as cursor:
                    result = await cursor.fetchone()
                    if result and result[0]:
                        freeze_end_dt = datetime.strptime(result[0], '%Y-%m-%d').date()
                        if freeze_end_dt >= current_date:
                            return freeze_end_dt # Заморозка активна
                        else:
                            # Заморозка истекла, можно её удалить для очистки
                            self.logger.info(f"DB: Stale freeze record found for {user_id}-{partner_id} (ended {freeze_end_dt}). Removing.")
                            await self.remove_streak_freeze(user_id, partner_id) # Вызовем удаление
                            return None
                    return None
        except Exception as e:
            self.logger.error(f"DB: Error checking active freeze for {user_id}-{partner_id}: {e}", exc_info=True)
            return None

    async def remove_streak_freeze(self, user_id: int, partner_id: int):
        """Удаляет запись о заморозке стрика для пары."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("DELETE FROM streak_freezes WHERE user_id = ? AND partner_id = ?", (user_id, partner_id))
                await db.execute("DELETE FROM streak_freezes WHERE user_id = ? AND partner_id = ?", (partner_id, user_id)) # Симметрично
                await db.commit()
                self.logger.info(f"DB: Removed streak freeze for pair {user_id}-{partner_id}.")
        except Exception as e:
            self.logger.error(f"DB: Error removing streak freeze for {user_id}-{partner_id}: {e}", exc_info=True) 