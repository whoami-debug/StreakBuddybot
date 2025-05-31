import asyncio
import logging
import json
from datetime import datetime, timezone, date
from typing import Optional, Dict, List, Set, Tuple
from pathlib import Path
from collections import defaultdict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.enums import ChatType
from aiogram.types import Message, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from aiohttp import web
import aiosqlite
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from database import Database
from config import BOT_TOKEN, WEBAPP_URL

# Настройка логирования с более подробным форматом
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
# dp = Dispatcher() # Уберем инициализацию dp здесь, сделаем в main
db = Database()

# Путь к веб-приложению
WEBAPP_PATH = Path(__file__).parent / "webapp"

# Создаем веб-сервер
routes = web.RouteTableDef()

# Кеш для отслеживания активности в группах
# {chat_id: {user_id}} - кто писал сегодня
group_activity_today: Dict[int, Set[int]] = defaultdict(set)
# {chat_id: {(user1_id, user2_id)}} - каким парам уже отправили уведомление о стрике сегодня
notified_streaks_today: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)

# Переменная для хранения текущей даты, чтобы сбрасывать кеш раз в сутки
current_bot_date: Optional[date] = None

async def reset_daily_caches_if_new_day():
    """Сбрасывает кеши, если наступил новый день."""
    global current_bot_date, group_activity_today, notified_streaks_today
    today = datetime.now(timezone.utc).date()
    if current_bot_date != today:
        logger.info(f"Новый день ({today})! Сбрасываем ежедневные кеши.")
        group_activity_today.clear()
        notified_streaks_today.clear()
        current_bot_date = today

@routes.get('/')
async def serve_webapp(request):
    return web.FileResponse(WEBAPP_PATH / 'index.html')

# Словарь для хранения собеседников в личных сообщениях
# Формат: {user_id: {partner_username: partner_id}}
dm_partners: Dict[int, Dict[str, int]] = {}

def get_days_word(days: int) -> str:
    """Возвращает правильное склонение слова 'день'"""
    if days % 100 in [11, 12, 13, 14]:
        return "дней"
    if days % 10 == 1:
        return "день"
    if days % 10 in [2, 3, 4]:
        return "дня"
    return "дней"

async def setup_bot_commands():
    """Установка команд бота для меню"""
    commands = [
        BotCommand(
            command="start",
            description="🚀 Начать отслеживать общение с друзьями"
        ),
        BotCommand(
            command="webapp",
            description="📱 Открыть стильный веб-интерфейс"
        ),
        BotCommand(
            command="streaks",
            description="🔥 Показать ваши серии общения"
        ),
        BotCommand(
            command="reset",
            description="🔄 Сбросить стрик: /reset @username"
        ),
        BotCommand(
            command="help",
            description="💡 Подробная инструкция по использованию"
        )
    ]
    await bot.set_my_commands(commands)

# УБИРАЕМ ДЕКОРАТОРЫ, ТАК КАК РЕГИСТРАЦИЯ В MAIN
async def cmd_start(message: Message, command: Optional[CommandObject] = None): # Добавил CommandObject для консистентности, хотя CommandStart не передает его
    await reset_daily_caches_if_new_day()
    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or str(message.from_user.id)
    )
    
    # Создаем кнопку для открытия веб-приложения
    webapp_button = InlineKeyboardButton(
        text="📱 Открыть веб-интерфейс",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[webapp_button]])
    
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "🌟 Добро пожаловать в Streak Buddy!\n\n"
            "Я помогу вам отслеживать регулярность общения с друзьями и близкими. "
            "Каждый день общения увеличивает вашу серию (стрик), а пропуск дня сбрасывает её.\n\n"
            "📱 <b>Что нового:</b>\n"
            "• Современный веб-интерфейс\n"
            "• Мгновенные уведомления\n"
            "• Автоматическое отслеживание в группах\n"
            "• Красивая статистика общения\n\n"
            "🎯 <b>Как начать:</b>\n"
            "1. Добавьте друга через /chat @username\n"
            "2. Общайтесь каждый день\n"
            "3. Следите за своими достижениями\n\n"
            "Нажмите на кнопку ниже, чтобы открыть удобный интерфейс:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "✨ <b>Streak Buddy активирован в этой группе!</b>\n\n"
            "🤝 <b>Как это работает:</b>\n"
            "• Бот автоматически отслеживает общение участников\n"
            "• Стрик засчитывается, когда два человека пишут в один день\n"
            "• Используйте /streaks чтобы увидеть свои серии общения\n"
            "• Пропуск дня сбрасывает стрик\n\n"
            "💫 Общайтесь регулярно и побейте рекорд группы!",
            parse_mode="HTML"
        )

async def cmd_webapp(message: Message, command: Optional[CommandObject] = None):
    await reset_daily_caches_if_new_day()
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("⚠️ Эта команда работает только в личных сообщениях с ботом.")
        return
    
    webapp_button = InlineKeyboardButton(
        text="📱 Открыть интерфейс",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[webapp_button]])
    
    await message.answer(
        "Нажмите на кнопку ниже, чтобы открыть удобный интерфейс для отслеживания общения:",
        reply_markup=keyboard
    )

async def cmd_chat(message: Message, command: CommandObject):
    await reset_daily_caches_if_new_day()
    if message.chat.type != ChatType.PRIVATE:
        await message.answer(
            "⚠️ Эта команда работает только в личных сообщениях с ботом."
        )
        return

    if not command.args:
        await message.answer(
            "ℹ️ Пожалуйста, укажите username пользователя.\n"
            "Пример: /chat @username"
        )
        return

    user_id = message.from_user.id
    target_username = command.args.strip('@')
    
    # Проверяем, что пользователь не пытается добавить сам себя
    if message.from_user.username and target_username == message.from_user.username:
        await message.answer("❌ Вы не можете добавить сами себя.")
        return
    
    # Получаем ID целевого пользователя
    target_id = await db.get_user_id_by_username(target_username)
    if not target_id:
        await message.answer(
            f"❌ Пользователь @{target_username} еще не использовал бота.\n"
            "Попросите его сначала запустить бота командой /start"
        )
        return

    # Проверяем, есть ли уже запрос на стрик
    existing_request = await db.get_streak_request(user_id, target_id)
    if existing_request:
        await message.answer(
            f"✋ Вы уже отправили запрос на стрик пользователю @{target_username}.\n"
            "Ожидайте подтверждения!"
        )
        return

    # Добавляем запрос на стрик
    await db.add_streak_request(user_id, target_id)
    
    # Отправляем уведомление целевому пользователю
    accept_button = InlineKeyboardButton(
        text="✅ Принять",
        callback_data=f"accept_streak:{user_id}"
    )
    decline_button = InlineKeyboardButton(
        text="❌ Отклонить",
        callback_data=f"decline_streak:{user_id}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[accept_button, decline_button]])
    
    await bot.send_message(
        target_id,
        f"👋 Пользователь @{message.from_user.username} хочет отслеживать общение с вами!\n\n"
        "Вы можете принять или отклонить запрос:",
        reply_markup=keyboard
    )
    
    await message.answer(
        f"✅ Запрос на отслеживание общения отправлен пользователю @{target_username}.\n"
        "Я сообщу, когда он примет или отклонит запрос!"
    )

async def process_streak_request(callback_query: types.CallbackQuery):
    await reset_daily_caches_if_new_day()
    action, user_id_str = callback_query.data.split(":")
    from_user_id = int(user_id_str)
    to_user_id = callback_query.from_user.id
    
    if action == "accept_streak":
        # Добавляем пользователей друг другу
        await db.add_streak_pair(from_user_id, to_user_id)
        
        from_user_chat = await bot.get_chat(from_user_id)
        to_user_username = callback_query.from_user.username or str(to_user_id)

        # Уведомляем обоих пользователей
        await bot.send_message(
            from_user_id,
            f"🎉 @{to_user_username} принял ваш запрос на отслеживание общения!\n"
            "Теперь вы можете отмечать общение каждый день."
        )
        
        await callback_query.message.edit_text(
            "✅ Вы приняли запрос на отслеживание общения.\n"
            f"Теперь вы будете отслеживать общение с @{from_user_chat.username or str(from_user_id)}"
        )
        
    else:  # decline_streak
        to_user_username = callback_query.from_user.username or str(to_user_id)
        await bot.send_message(
            from_user_id,
            f"😔 @{to_user_username} отклонил ваш запрос на отслеживание общения."
        )
        
        await callback_query.message.edit_text(
            "❌ Вы отклонили запрос на отслеживание общения."
        )
    
    # Удаляем запрос
    await db.remove_streak_request(from_user_id, to_user_id)

async def send_streaks_data(user_id: int, is_webapp_request: bool = False):
    """Отправка данных о стриках в веб-интерфейс"""
    if not is_webapp_request:
        return
        
    streaks = await db.get_user_streaks(user_id, user_id) 
    streak_data = []
    for username, count in streaks:
        partner_id = await db.get_user_id_by_username(username)
        if partner_id:
            last_chat = await db.get_last_chat_date(user_id, partner_id)
            today = datetime.now(timezone.utc).date()
            
            if last_chat:
                days_diff = (today - last_chat).days
                last_chat_text = (
                    "Сегодня" if days_diff == 0 and count > 0 else # Добавил count > 0, чтобы "Сегодня" было только для активных
                    "Вчера" if days_diff == 1 and count > 0 else
                    last_chat.strftime("%d.%m.%Y") if count > 0 else "Нет активного стрика"
                )
            else:
                last_chat_text = "Нет общения"
            
            streak_data.append({
                'username': username,
                'partner_id': partner_id, # Добавляем partner_id для использования в WebApp
                'count': count,
                'last_chat': last_chat_text
            })
    
    # Отправляем данные в веб-приложение через специальное сообщение боту
    # (предполагаем, что веб-приложение слушает эти сообщения или бот как-то их передает)
    # Это должно быть реализовано через Telegram WebApp API (window.Telegram.WebApp.sendData)
    # или через другой механизм, если бот и веб-сервер могут общаться напрямую.
    # Для простоты пока оставим отправку сообщения пользователю, как было.
    # В реальном сценарии, данные лучше передавать напрямую в WebApp.
    
    # Вместо отправки сообщения пользователю, мы должны отправить данные в WebApp.
    # Это делается вызовом метода JavaScript в WebApp, если WebApp запрашивает данные.
    # Если это пуш от бота, то это сложнее. 
    # Пока что, когда WebApp запрашивает 'get_streaks', мы просто отвечаем ему данными.
    # А когда 'mark_today', мы отвечаем сообщением о статусе.
    
    # Если это ответ на get_streaks, то WebApp ожидает данные.
    # Мы можем отправить их как JSON строку в web_app_data при ответе на запрос от WebApp.
    # Однако, функция send_message не позволяет напрямую ответить на web_app_data.
    # Поэтому, если это is_webapp_request от action 'get_streaks', 
    # то данные должны были быть отправлены в handle_webapp_data.
    # Эта функция send_streaks_data может быть упрощена до простого получения данных
    # и использоваться внутри handle_webapp_data.
    
    # Для действия 'mark_today', после обработки, мы можем отправить обновленные данные:
    if is_webapp_request: # Только если это был запрос от webapp
        # logger.info(f"WebApp: Preparing to send updated streak data to user {user_id}: {streak_data}")
        # Это все еще не идеально, т.к. мы шлем сообщение в чат, а не напрямую в WebApp.
        # Правильный способ - WebApp должен сам запросить обновление после действия.
        pass # Не будем слать сообщение из этой функции, пусть handle_webapp_data решает

async def handle_webapp_data(message: Message):
    """Обработчик данных от веб-приложения"""
    await reset_daily_caches_if_new_day()
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        user_id = message.from_user.id
        
        if action == 'mark_today':
            partner_id_to_mark = data.get('partner_id')
            if not partner_id_to_mark:
                await message.answer("Ошибка: не указан ID партнера для отметки.")
                return

            today = datetime.now(timezone.utc).date()
            status_msg, streak_updated = await db.mark_webapp_interaction(user_id, int(partner_id_to_mark), today)
            
            await message.answer(status_msg) # Сообщаем пользователю результат

            # Если стрик обновился или просто для актуальности, попросим WebApp обновить данные
            # Это можно сделать, отправив специальный ответ или просто положившись, 
            # что WebApp сам запросит обновление после действия.
            # Для простоты, WebApp должен будет сам сделать запрос get_streaks после этого.
            # Либо, если мы хотим пушить, это требует другой архитектуры.
            # Пока оставим так: WebApp после mark_today может сам запросить get_streaks.
            if streak_updated: # Если стрик реально обновился, можно дополнительно уведомить
                logger.info(f"WebApp: Streak updated for {user_id} with {partner_id_to_mark} via webapp mark.")
                # Можно отправить команду WebApp обновиться, если есть такой механизм
                # Например, через ответное сообщение с определенным payload,
                # который WebApp отлавливает. Но это усложнение.

        elif action == 'get_streaks':
            streaks = await db.get_user_streaks(user_id, user_id) # user_id как chat_id для всех стриков
            streak_data_for_webapp = []
            for username, count in streaks:
                partner_id = await db.get_user_id_by_username(username)
                if partner_id:
                    last_chat_dt = await db.get_last_chat_date(user_id, partner_id)
                    today_dt = datetime.now(timezone.utc).date()
                    last_chat_text = "Нет общения"
                    if last_chat_dt:
                        days_diff = (today_dt - last_chat_dt).days
                        last_chat_text = (
                            "Сегодня" if days_diff == 0 and count > 0 else
                            "Вчера" if days_diff == 1 and count > 0 else
                            last_chat_dt.strftime("%d.%m.%Y") if count > 0 else "Нет активного стрика"
                        )
                    
                    streak_data_for_webapp.append({
                        'username': username,
                        'partner_id': partner_id, 
                        'count': count,
                        'last_chat': last_chat_text
                    })
            # Отправляем данные обратно в WebApp
            # Это стандартный способ ответа на getData запросы WebApp
            try:
                await bot.answer_web_app_query(
                    web_app_query_id=message.web_app_data.query_id, 
                    result=types.InlineQueryResultArticle(
                        id=str(user_id) + "_streaks",
                        title="Streaks Data",
                        input_message_content=types.InputTextMessageContent(
                            message_text=json.dumps({"streaks": streak_data_for_webapp, "source": "bot_response"})
                        )
                    )
                )
                logger.info(f"WebApp: Sent streaks data to WebApp for user {user_id} via answer_web_app_query.")
            except Exception as e:
                logger.error(f"WebApp: Error sending data via answer_web_app_query: {e}", exc_info=True)
                await message.answer("Не удалось отправить данные в веб-интерфейс. Попробуйте обновить его.")

        elif action == 'select_user':
            target_username = data.get('username')
            if target_username:
                # Эмулируем команду /chat
                command = CommandObject(command='chat', args=f'@{target_username}')
                await cmd_chat(message, command)
                # После добавления пользователя отправляем обновленные данные
                await send_streaks_data(message.from_user.id, is_webapp_request=True)
            
    except json.JSONDecodeError:
        await message.answer("❌ Произошла ошибка при обработке данных.")

async def handle_message(message: Message):
    """Обработчик всех остальных сообщений"""
    await reset_daily_caches_if_new_day()
    
    user_id = message.from_user.id
    username = message.from_user.username or str(user_id)
    chat_id = message.chat.id
    today = datetime.now(timezone.utc).date()

    logger.info(f"Сообщение от {username} ({user_id}) в чате {chat_id} ({message.chat.type})")

    # Игнорируем сообщения не от пользователей или служебные в группах
    if not message.from_user or message.from_user.is_bot:
        logger.info("Сообщение от бота или не от пользователя, игнорируем.")
        return

    if message.chat.type != ChatType.PRIVATE and (
        message.new_chat_members or 
        message.left_chat_member or
        message.new_chat_title or
        message.new_chat_photo or
        message.delete_chat_photo or
        message.group_chat_created or
        message.supergroup_chat_created or
        message.channel_chat_created or
        message.message_auto_delete_timer_changed or
        message.pinned_message
    ):
        logger.info("Служебное сообщение в группе, игнорируем.")
        return

    # Добавляем пользователя в базу данных
    await db.add_user(user_id, username)
    logger.info(f"Пользователь {username} ({user_id}) добавлен/обновлен в базе.")

    # Обработка только сообщений в группах и супергруппах
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        logger.info("Сообщение не в группе/супергруппе, пропускаем обработку стриков.")
        return

    # Обновляем активность пользователя в чате
    group_activity_today[chat_id].add(user_id)
    logger.info(f"Пользователь {username} ({user_id}) отмечен активным в чате {chat_id}. Активные: {group_activity_today[chat_id]}")

    # Получаем список всех активных пользователей в этом чате сегодня
    active_users_in_chat = list(group_activity_today[chat_id])
    
    if len(active_users_in_chat) < 2:
        logger.info("Менее двух активных пользователей в чате, стрики невозможны.")
        return

    logger.info(f"Обработка пар для чата {chat_id}. Активные пользователи: {active_users_in_chat}")

    # Перебираем все уникальные пары активных пользователей
    for i in range(len(active_users_in_chat)):
        for j in range(i + 1, len(active_users_in_chat)):
            user1_id = active_users_in_chat[i]
            user2_id = active_users_in_chat[j]

            # Сортируем ID, чтобы ключ для notified_streaks_today был консистентным
            pair_key = tuple(sorted((user1_id, user2_id)))

            logger.info(f"Processing pair: {pair_key} in chat {chat_id}")

            # Убеждаемся, что пара для стрика существует, если нет - создаем
            await db.add_streak_pair(user1_id, user2_id) # Создаст симметричную пару, если ее нет
            logger.info(f"Ensured streak_pair exists for {pair_key}")
            
            streak_before = await db.get_streak_count(user1_id, user2_id) # Стрик симметричен
            logger.info(f"Streak BEFORE for {pair_key}: {streak_before}")

            # Вызываем mark_message для КАЖДОГО из участников пары.
            # Внутренняя логика mark_message обновит стрик только если ОБА направления активны сегодня.
            # Если текущий отправитель (message.from_user.id) равен user1_id, то его сообщение уже записано.
            # Если он равен user2_id, то его сообщение тоже.
            # Нам нужно, чтобы mark_message была вызвана для обеих "перспектив" пары.
            
            # Если сообщение пришло от user1_id, то его mark_message вызовется с (user1_id, user2_id, today)
            # Если сообщение пришло от user2_id, то его mark_message вызовется с (user2_id, user1_id, today)
            # Но нам нужно обработать пару (user1_id, user2_id) целиком.
            
            # Логика такая: mark_message(A,B) записывает сообщение A->B 
            # и если есть B->A, то обновляет стрик для A-B.
            await db.mark_message(user1_id, user2_id, today, chat_id) # Передаем chat_id как chat_id_context
            await db.mark_message(user2_id, user1_id, today, chat_id) # Передаем chat_id как chat_id_context
            
            # После вызова mark_message для обеих "перспектив", стрик должен быть актуален.
            # Проверяем, действительно ли оба пользователя отметились сегодня В ЭТОМ ЧАТЕ
            if await db.check_both_marked(user1_id, user2_id, today, chat_id): # Передаем chat_id как chat_id_context
                logger.info(f"Pair {pair_key} confirmed as both marked today in chat {chat_id}.")
                streak_after = await db.get_streak_count(user1_id, user2_id)
                logger.info(f"Streak AFTER for {pair_key}: {streak_after}")

                if streak_after > streak_before and pair_key not in notified_streaks_today[chat_id]:
                    logger.info(f"Streak for {pair_key} increased ({streak_before} -> {streak_after}). Sending notification.")
                    
                    user1_username = await db.get_username_by_id(user1_id) or str(user1_id)
                    user2_username = await db.get_username_by_id(user2_id) or str(user2_id)
                    
                    user1_mention = f"@{user1_username}" if not user1_username.startswith('@') else user1_username
                    user2_mention = f"@{user2_username}" if not user2_username.startswith('@') else user2_username

                    days_word = get_days_word(streak_after)
                    
                    message_text = f"🎯 {user1_mention} и {user2_mention} начали новую серию общения!"
                    if streak_before > 0 : # Если стрик уже был, значит он продлен
                        streak_emoji = "🔥" if streak_after >= 7 else "✨" if streak_after >= 3 else "⭐️"
                        message_text = f"{streak_emoji} {user1_mention} и {user2_mention} продлили стрик!\nВаша серия: {streak_after} {days_word} подряд"

                    await message.answer(message_text)
                    notified_streaks_today[chat_id].add(pair_key)
                    logger.info(f"Notification sent for {pair_key}. Added to notified_streaks_today.")

                    if streak_after in [3, 7, 14, 30, 50, 100]:
                        achievement_emoji = "🏆" if streak_after >= 30 else "🎉"
                        await message.answer(
                            f"{achievement_emoji} Поздравляем! {streak_after} {days_word} общения - это достижение!"
                        )
                elif pair_key in notified_streaks_today[chat_id]:
                     logger.info(f"Notification for {pair_key} already sent today.")
                elif streak_after <= streak_before:
                    logger.info(f"Streak for {pair_key} did not increase ({streak_before} -> {streak_after}). No notification needed.")
            else:
                logger.info(f"Pair {pair_key} NOT confirmed as both marked today. No streak update or notification based on this message.")


async def cmd_reset(message: Message, command: CommandObject):
    """Сброс стрика с конкретным пользователем"""
    await reset_daily_caches_if_new_day()
    if not command.args:
        await message.answer(
            "ℹ️ <b>Как сбросить стрик:</b>\n"
            "1. Используйте команду /reset @username\n"
            "2. Стрик и история общения будут удалены\n"
            "3. Начните общение заново, чтобы создать новый стрик",
            parse_mode="HTML"
        )
        return

    user_id = message.from_user.id
    target_username = command.args.strip('@')
    
    # Получаем ID целевого пользователя
    target_id = await db.get_user_id_by_username(target_username)
    if not target_id:
        await message.answer(
            f"❌ Пользователь @{target_username} не найден в базе данных."
        )
        return

    # Проверяем текущий стрик перед сбросом
    current_streak = await db.get_streak_count(user_id, target_id)
    if current_streak == 0:
        await message.answer(
            f"ℹ️ У вас нет активного стрика с @{target_username}."
        )
        return
    
    # Сбрасываем стрик
    if await db.reset_streak(user_id, target_id):
        days_word = get_days_word(current_streak)
        
        # Уведомляем инициатора сброса
        await message.answer(
            f"🔄 <b>Стрик сброшен</b>\n\n"
            f"• Собеседник: @{target_username}\n"
            f"• Серия общения была: {current_streak} {days_word}\n"
            f"• История общения удалена\n\n"
            "Начните общаться снова, чтобы создать новый стрик!",
            parse_mode="HTML"
        )
        
        # Уведомляем второго пользователя
        try:
            await bot.send_message(
                target_id,
                f"❗️ <b>@{message.from_user.username} сбросил стрик общения с вами</b>\n\n"
                f"• Ваша серия была: {current_streak} {days_word}\n"
                f"• История общения удалена\n\n"
                "Начните общаться снова, чтобы создать новый стрик!",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о сбросе стрика: {e}", exc_info=True)
    else:
        await message.answer(
            "❌ Произошла ошибка при сбросе стрика. Попробуйте позже."
        )

async def cmd_help(message: Message, command: Optional[CommandObject] = None):
    """Показывает справку по использованию бота"""
    await reset_daily_caches_if_new_day()
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "🌟 <b>Streak Buddy - Ваш помощник в общении</b>\n\n"
            "🤝 <b>Основные команды:</b>\n"
            "/chat @username - Начать отслеживать общение\n"
            "/streaks - Посмотреть текущие серии общения\n"
            "/reset @username - Сбросить стрик с пользователем\n"
            "/webapp - Открыть веб-интерфейс\n\n"
            "📊 <b>Как работают стрики:</b>\n"
            "• День засчитывается при общении обоих собеседников\n"
            "• Пропуск дня сбрасывает серию\n"
            "• Можно поддерживать стрики с разными людьми\n"
            "• Бот автоматически считает дни в группах\n\n"
            "💡 <b>Советы:</b>\n"
            "• Используйте веб-интерфейс для удобного отслеживания\n"
            "• Отмечайте общение каждый день\n"
            "• Следите за уведомлениями о достижениях\n"
            "• Соревнуйтесь с друзьями в длине стрика\n\n"
            "🎯 <b>Особые функции:</b>\n"
            "• Автоматическое определение общения в группах\n"
            "• Красивая статистика в веб-интерфейсе\n"
            "• Уведомления о новых рекордах\n"
            "• Возможность сброса стрика при необходимости",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "✨ <b>Streak Buddy в групповых чатах</b>\n\n"
            "🤝 <b>Как это работает:</b>\n"
            "• Бот автоматически отслеживает общение участников\n"
            "• Стрик засчитывается при общении двух людей в один день\n"
            "• Серия сбрасывается при пропуске дня\n\n"
            "📊 <b>Доступные команды:</b>\n"
            "• /streaks - Посмотреть ваши серии общения\n"
            "• /reset @username - Сбросить стрик с пользователем\n"
            "• /help - Показать эту справку\n\n"
            "💫 <b>Советы для групп:</b>\n"
            "• Общайтесь каждый день для поддержания стрика\n"
            "• Следите за уведомлениями о достижениях\n"
            "• Соревнуйтесь с другими участниками\n"
            "• Используйте веб-интерфейс для удобного просмотра",
            parse_mode="HTML"
        )

async def cmd_streaks(message: Message, command: Optional[CommandObject] = None):
    """Показывает текущие серии общения пользователя"""
    # НЕОТЛОЖНОЕ ЛОГИРОВАНИЕ ВХОДА В ФУНКЦИЮ
    logger.critical(f"!!! CMD_STREAKS HANDLER ENTERED by {message.from_user.id} in chat {message.chat.id} !!!") 
    
    await reset_daily_caches_if_new_day()
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or str(user_id)
    logger.info(f"CMD: /streaks received from {username} ({user_id}) in chat {chat_id}")

    try:
        # Временно отправим очень простое сообщение для теста
        # await message.answer(f"Тест /streaks для {username}! Получаю данные...")
        # logger.info(f"CMD: /streaks - Sent initial test message to {username}")

        await db.add_user(
            user_id=user_id,
            username=username
        )
        logger.info(f"CMD: /streaks - User {username} ({user_id}) ensured in DB.")
        
        streaks = await db.get_user_streaks(user_id, chat_id)
        logger.info(f"CMD: /streaks - Fetched streaks for {username} ({user_id}) in chat {chat_id}: {streaks}")

        if not streaks:
            logger.info(f"CMD: /streaks - No active streaks for {username} ({user_id}) in chat {chat_id}.")
            response_text = "🌱 <b>У вас пока нет активных серий общения в этом чате</b>\n\n"
            if message.chat.type == ChatType.PRIVATE:
                webapp_button = InlineKeyboardButton(
                    text="📱 Открыть веб-интерфейс",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[webapp_button]])
                response_text += (
                    "💫 <b>Как начать:</b>\n"
                    "• Используйте /chat @username чтобы добавить собеседника (в личном чате с ботом)\n"
                    "• Общайтесь каждый день для поддержания стрика\n"
                    "• Следите за прогрессом в веб-интерфейсе\n\n"
                    "Нажмите на кнопку ниже, чтобы открыть веб-интерфейс и увидеть все свои стрики:"
                )
                await message.answer(response_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                response_text += (
                     "💫 <b>Как начать:</b>\n"
                    "• Просто общайтесь в группе каждый день с другими участниками\n"
                    "• Бот автоматически отследит ваши стрики в этой группе\n"
                    "• Следите за уведомлениями о достижениях"
                )
                await message.answer(response_text, parse_mode="HTML")
            return

        response_lines = []
        # Сортируем стрики по убыванию перед отображением
        sorted_streaks = sorted(streaks, key=lambda x: x[1], reverse=True)

        for partner_username, streak_count in sorted_streaks:
            days_word = get_days_word(streak_count)
            # partner_mention = f"@{partner_username}" if partner_username and not partner_username.startswith('@') else partner_username
            # Более надежное формирование упоминания:
            if partner_username:
                partner_mention = f"@{partner_username}" if not partner_username.startswith('@') else partner_username
            else:
                partner_mention = "(неизвестный партнер)" # На случай если username почему-то None

            if streak_count > 0:
                fire_emoji = "🔥" if streak_count >= 7 else "✨" if streak_count >= 3 else "⭐️"
                response_lines.append(f"{fire_emoji} {partner_mention}: {streak_count} {days_word}")
            else:
                response_lines.append(f"💤 {partner_mention}: нет активного стрика") # Этот случай не должен возникать, если get_user_streaks возвращает только >0
        
        response_text = "🔥 <b>Ваши серии общения:</b>\n\n" + "\n".join(response_lines)
        
        if message.chat.type != ChatType.PRIVATE:
            user_mention = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
            response_text = f"📊 Статистика пользователя {user_mention}:\n\n" + response_text
        
        # Добавляем мотивационное сообщение
        # Проверяем оригинальный список streaks, а не sorted_streaks, для эффективности
        if any(s[1] >= 7 for s in streaks):
            response_text += "\n\n🎉 <b>Отличная работа! Продолжайте общаться!</b>"
        elif any(s[1] >= 3 for s in streaks):
            response_text += "\n\n💫 <b>Хороший старт! Не пропускайте дни!</b>"
        elif streaks: # Если список streaks не пустой, но нет тех, кто >= 3
            response_text += "\n\n💪 <b>Начало положено! Общайтесь каждый день!</b>"
        # Если streaks пуст, это сообщение не добавится, т.к. мы вышли раньше
        
        logger.info(f"CMD: /streaks - Sending response to {username} ({user_id}):\n{response_text}")
        await message.answer(response_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"CMD: /streaks - Error processing /streaks for {username} ({user_id}): {e}", exc_info=True)
        await message.answer("🚫 Ой, что-то пошло не так при показе ваших стриков. Попробуйте еще раз позже.")

async def main():
    """Главная функция запуска бота"""
    global current_bot_date
    current_bot_date = datetime.now(timezone.utc).date()
    logger.info(f"Бот запускается. Текущая дата: {current_bot_date}")

    # Инициализация Dispatcher с MemoryStorage (хорошая практика)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    await db.init()
    await setup_bot_commands() # Установка команд в меню Telegram

    # РЕГИСТРАЦИЯ ХЕНДЛЕРОВ
    # Командные хендлеры регистрируем ПЕРВЫМИ
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_webapp, Command("webapp"))
    dp.message.register(cmd_chat, Command("chat"))
    dp.message.register(cmd_reset, Command("reset"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_streaks, Command("streaks")) # <<< Наш проблемный хендлер

    # Хендлер для данных из WebApp
    dp.message.register(handle_webapp_data, lambda message: message.web_app_data is not None)

    # Хендлер для колбэков (запросы на стрик)
    dp.callback_query.register(process_streak_request, lambda c: c.data.startswith(("accept_streak:", "decline_streak:")))

    # Общий обработчик сообщений регистрируем ПОСЛЕДНИМ
    # Он будет срабатывать, только если ни один из предыдущих хендлеров не подошел
    dp.message.register(handle_message) 

    logger.info("Хендлеры зарегистрированы.")

    # Запускаем веб-сервер (если он все еще нужен, если нет - можно убрать)
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    logger.info("Веб-сервер запущен на http://localhost:8080")
    
    # Запускаем бота
    logger.info("Запуск polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта.")

if __name__ == "__main__":
    asyncio.run(main()) 