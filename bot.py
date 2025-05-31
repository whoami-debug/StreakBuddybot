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

@dp.callback_query(lambda c: c.data.startswith(("accept_streak:", "decline_streak:")))
async def process_streak_request(callback_query: types.CallbackQuery):
    """Обработка ответа на запрос стрика"""
    action, user_id = callback_query.data.split(":")
    user_id = int(user_id)
    target_id = callback_query.from_user.id
    
    if action == "accept_streak":
        # Добавляем пользователей друг другу
        await db.add_streak_pair(user_id, target_id)
        
        # Уведомляем обоих пользователей
        await bot.send_message(
            user_id,
            f"🎉 @{callback_query.from_user.username} принял ваш запрос на отслеживание общения!\n"
            "Теперь вы можете отмечать общение каждый день."
        )
        
        await callback_query.message.edit_text(
            "✅ Вы приняли запрос на отслеживание общения.\n"
            f"Теперь вы будете отслеживать общение с @{(await bot.get_chat(user_id)).username}"
        )
        
    else:  # decline_streak
        await bot.send_message(
            user_id,
            f"😔 @{callback_query.from_user.username} отклонил ваш запрос на отслеживание общения."
        )
        
        await callback_query.message.edit_text(
            "❌ Вы отклонили запрос на отслеживание общения."
        )
    
    # Удаляем запрос
    await db.remove_streak_request(user_id, target_id)

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
            streaks = await db.get_user_streaks(user_id, user_id)
            for username, streak in streaks:
                partner_id = await db.get_user_id_by_username(username)
                if partner_id:
                    await db.mark_message(user_id, partner_id, today)
                    
                    # Проверяем, отметил ли партнер общение
                    if await db.check_both_marked(user_id, partner_id, today):
                        # Уведомляем обоих пользователей
                        streak_count = await db.get_streak_count(user_id, partner_id)
                        days_word = get_days_word(streak_count)
                        
                        for uid in [user_id, partner_id]:
                            partner = await bot.get_chat(partner_id if uid == user_id else user_id)
                            await bot.send_message(
                                uid,
                                f"✨ Вы и @{partner.username} отметили общение сегодня!\n"
                                f"Ваша серия: {streak_count} {days_word} подряд 🎉"
                            )
            
            # Отправляем обновленные данные в веб-интерфейс
            await send_streaks_data(message.from_user.id)
            
        elif action == 'get_streaks':
            # Отправляем актуальные данные о стриках
            await send_streaks_data(message.from_user.id)
            
        elif action == 'select_user':
            # Обработка выбора пользователя из веб-интерфейса
            target_username = data.get('username')
            if target_username:
                # Эмулируем команду /chat
                command = CommandObject(command='chat', args=f'@{target_username}')
                await cmd_chat(message, command)
                # После добавления пользователя отправляем обновленные данные
                await send_streaks_data(message.from_user.id)
            
    except json.JSONDecodeError:
        await message.answer("❌ Произошла ошибка при обработке данных.")

async def send_streaks_data(user_id: int):
    """Отправка данных о стриках в веб-интерфейс"""
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
                    "Сегодня" if days_diff == 0 else
                    "Вчера" if days_diff == 1 else
                    last_chat.strftime("%d.%m.%Y")
                )
            else:
                last_chat_text = "Нет общения"
            
            streak_data.append({
                'username': username,
                'count': count,
                'last_chat': last_chat_text
            })
    
    # Отправляем данные в формате, который ожидает веб-интерфейс
    await bot.send_message(
        user_id,
        json.dumps({
            'streaks': streak_data
        })
    )

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