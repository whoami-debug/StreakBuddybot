import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, List
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.enums import ChatType
from aiogram.types import Message, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from aiohttp import web

from database import Database
from config import BOT_TOKEN, WEBAPP_URL

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

# Путь к веб-приложению
WEBAPP_PATH = Path(__file__).parent / "webapp"

# Создаем веб-сервер
routes = web.RouteTableDef()

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
            description="Запустить бота и получить инструкции"
        ),
        BotCommand(
            command="webapp",
            description="Открыть удобный интерфейс для отслеживания общения"
        ),
        BotCommand(
            command="streaks",
            description="Показать текущие серии общения"
        ),
        BotCommand(
            command="help",
            description="Показать справку по использованию бота"
        )
    ]
    await bot.set_my_commands(commands)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or str(message.from_user.id)
    )
    
    # Создаем кнопку для открытия веб-приложения
    webapp_button = InlineKeyboardButton(
        text="📱 Открыть удобный интерфейс",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[webapp_button]])
    
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "👋 Привет! Я бот для отслеживания общения.\n\n"
            "📱 Теперь у меня есть удобный веб-интерфейс:\n"
            "• Выбирайте друзей из контактов\n"
            "• Отмечайте общение одним нажатием\n"
            "• Следите за статистикой\n\n"
            "Нажмите на кнопку ниже, чтобы начать:",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            "✨ Бот активирован в этой группе!\n\n"
            "• Я буду отслеживать общение между участниками\n"
            "• Серия общения засчитывается, когда два участника пишут в один день\n"
            "• Используйте /streaks чтобы увидеть свои серии общения"
        )

@dp.message(Command("webapp"))
async def cmd_webapp(message: Message):
    """Открывает веб-интерфейс бота"""
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

@dp.message(lambda message: message.web_app_data is not None)
async def handle_webapp_data(message: Message):
    """Обработчик данных от веб-приложения"""
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        
        if action == 'mark_today':
            # Отмечаем общение за сегодня
            user_id = message.from_user.id
            today = datetime.now(timezone.utc).date()
            
            # Получаем список активных собеседников
            streaks = await db.get_user_streaks(user_id, user_id)  # Используем user_id как chat_id
            for username, _ in streaks:
                partner_id = await db.get_user_id_by_username(username)
                if partner_id:
                    await db.mark_message(user_id, partner_id, today)
            
            await message.answer("✅ Общение за сегодня отмечено!")
            
        elif action == 'select_user':
            # Здесь будет логика выбора пользователя из контактов
            pass
            
    except json.JSONDecodeError:
        await message.answer("❌ Произошла ошибка при обработке данных.")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Показывает справку по использованию бота"""
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "📖 Справка по использованию бота\n\n"
            "🤝 Как начать общение:\n"
            "1. Напишите /chat @username вашего собеседника\n"
            "2. Попросите собеседника написать /chat @ваш_username\n"
            "3. Готово! Теперь просто пишите боту каждый день\n\n"
            "📊 Как считаются стрики:\n"
            "• День засчитывается, если оба собеседника написали боту\n"
            "• Если пропустить день - стрик сбрасывается\n"
            "• Можно общаться с несколькими людьми одновременно\n\n"
            "📱 Доступные команды:\n"
            "/chat @username - начать отслеживать общение\n"
            "/streaks - показать текущие серии общения\n"
            "/help - показать эту справку\n\n"
            "🎯 Советы:\n"
            "• Пишите боту каждый день для поддержания стрика\n"
            "• Следите за уведомлениями о новых достижениях\n"
            "• В группах бот работает автоматически"
        )
    else:
        await message.answer(
            "📖 Справка по использованию бота в группах\n\n"
            "• Бот автоматически отслеживает общение участников\n"
            "• Стрик засчитывается, когда два участника пишут в один день\n"
            "• Используйте /streaks для просмотра ваших серий общения\n"
            "• При пропуске дня стрик сбрасывается"
        )

@dp.message(Command("chat"))
async def cmd_chat(message: Message, command: CommandObject):
    """Установка собеседника для отслеживания общения"""
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
    
    # Добавляем пользователя в словарь собеседников
    if user_id not in dm_partners:
        dm_partners[user_id] = {}
    
    dm_partners[user_id][target_username] = None  # None означает, что мы ещё не знаем ID пользователя
    
    await message.answer(
        f"✅ Отлично! Я буду отслеживать ваше общение с @{target_username}.\n\n"
        f"📝 Инструкция:\n"
        f"1. Просто пишите мне сообщения каждый день\n"
        f"2. Попросите @{target_username} написать:\n"
        f"   /chat @{message.from_user.username or str(user_id)}\n\n"
        f"🎯 Стрик начнёт считаться, когда вы оба напишете мне в один день!"
    )

@dp.message(Command("streaks"))
async def cmd_streaks(message: Message):
    """Показывает текущие серии общения пользователя"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Добавляем пользователя, если его еще нет
    await db.add_user(
        user_id=user_id,
        username=message.from_user.username or str(user_id)
    )
    
    streaks = await db.get_user_streaks(user_id, chat_id)
    if not streaks:
        await message.answer(
            "📊 У вас пока нет активных серий общения в этом чате.\n\n"
            "• В личке: используйте /chat @username\n"
            "• В группе: просто общайтесь каждый день"
        )
        return

    response = "📊 Ваши текущие серии общения:\n\n"
    for username, streak in streaks:
        days_word = get_days_word(streak)
        response += f"• @{username}: {streak} {days_word} подряд\n"
    
    # В группе отвечаем с тегом пользователя
    if message.chat.type != ChatType.PRIVATE:
        user_mention = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        response = f"{user_mention}, вот ваша статистика:\n\n" + response.strip()
    
    await message.answer(response.strip())

@dp.message()
async def handle_message(message: Message):
    """Обработчик всех остальных сообщений"""
    # Игнорируем служебные сообщения в группах
    if message.chat.type != ChatType.PRIVATE and (
        message.new_chat_members is not None or 
        message.left_chat_member is not None or
        message.new_chat_title is not None or
        message.new_chat_photo is not None or
        message.delete_chat_photo is not None or
        message.group_chat_created is not None or
        message.supergroup_chat_created is not None or
        message.channel_chat_created is not None or
        message.message_auto_delete_timer_changed is not None or
        message.pinned_message is not None
    ):
        return

    user_id = message.from_user.id
    username = message.from_user.username or str(user_id)
    chat_id = message.chat.id
    
    # Добавляем пользователя, если его еще нет
    await db.add_user(user_id, username)
    
    # Обработка личных сообщений
    if message.chat.type == ChatType.PRIVATE:
        if user_id in dm_partners and dm_partners[user_id]:
            today = datetime.now(timezone.utc).date()
            
            # Проверяем каждого собеседника
            for partner_username, partner_id in dm_partners[user_id].items():
                if partner_id is not None:  # Пропускаем неподтверждённых собеседников
                    await db.mark_message(user_id, partner_id, today)
                    
                    # Проверяем общение
                    streak_updates = await db.check_streaks(user_id, partner_id, today)
                    for other_username, streak, is_new_streak in streak_updates:
                        if is_new_streak:
                            days_word = get_days_word(streak)
                            await message.answer(
                                f"🎉 Поздравляем!\n"
                                f"Вы и @{other_username} общаетесь уже {streak} {days_word} подряд!"
                            )
    
    # Обработка групповых сообщений
    else:
        # Отмечаем сообщение на сегодня
        today = datetime.now(timezone.utc).date()
        await db.mark_message(user_id, chat_id, today)
        
        # Проверяем общение с другими пользователями
        streak_updates = await db.check_streaks(user_id, chat_id, today)
        
        for other_username, streak, is_new_streak in streak_updates:
            if is_new_streak:
                user_mention = f"@{username}" if username != str(user_id) else message.from_user.first_name
                other_mention = f"@{other_username}"
                days_word = get_days_word(streak)
                await message.answer(
                    f"🎉 {user_mention} и {other_mention} общаются уже {streak} {days_word} подряд!"
                )

async def main():
    """Главная функция запуска бота"""
    await db.init()
    # Устанавливаем команды бота
    await setup_bot_commands()
    
    # Запускаем веб-сервер
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 