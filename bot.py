import asyncio
import os

import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from search import search_films

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv("TOKEN"))  # Токен берётся из переменной окружения
dp = Dispatcher()


# --- Функции работы с базой данных ---

async def init_db():
    '''Инициализация базы данных SQLite с таблицами history и stats.'''
    async with aiosqlite.connect('bot.db') as db:
        # Таблица истории поисков
        await db.execute('''CREATE TABLE IF NOT EXISTS history
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             user_id INTEGER,
                             query TEXT,
                             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        # Таблица статистики предложенных фильмов с уникальным ограничением
        await db.execute('''CREATE TABLE IF NOT EXISTS stats
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             user_id INTEGER,
                             title TEXT,
                             count INTEGER DEFAULT 1,
                             UNIQUE(user_id, title))''')
        await db.commit()


# --- Вспомогательные функции для отображения данных ---

async def show_history(message: types.Message, user_id: int):
    # Отображение истории поисков
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute("SELECT query, timestamp FROM history WHERE user_id = ? ORDER BY timestamp DESC",
                              (user_id,)) as cursor:
            rows = await cursor.fetchall()

    text = "История поиска:\n" if rows else "🥲 Вы пока ничего не искали."
    for row in rows[:20]:
        # text += f"{row[1]}: {row[0]}\n"
        text += f"<code>{row[0]}</code>\n"

    await message.reply(text, parse_mode="HTML")


async def show_stats(message: types.Message, user_id: int):
    # Отображение статистики предложенных фильмов
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute("SELECT title, count FROM stats WHERE user_id = ? ORDER BY count DESC",
                              (user_id,)) as cursor:
            rows = await cursor.fetchall()

    text = "Статистика фильмов в результатах поиска:\n" if rows else "🥲 Вы пока ничего не искали."
    for row in rows[:20]:
        text += f"<code>{row[0]}</code>: {row[1]} раз(а)\n"

    await message.reply(text, parse_mode='HTML')


# --- Обработчики команд ---

@dp.message(Command('start'))
async def start_command(message: types.Message):

    welcome_text = (
        "<b>Добро пожаловать!</b>\n\n"
        "Чтобы найти фильм, просто отправьте его название - поисковый алгоритм предложит найденные фильмы и сериалы. \n"
        "Список команд доступен с помощью /help. "
        "После успешного поиска бот отправит альбом постеров с подписями к фильмам. Приятного просмотра!\n\n"
        "<i>Важно: ссылки на найденный фильм или сериал ведут на сторонний сайт. "
        "Для наилучшего результата рекомендуется иметь блокировщик рекламы, к примеру, uBlock Origin, "
        "и проверить несколько плееров представленных на сайте.</i>"
    )

    await message.reply(welcome_text, parse_mode='HTML')


@dp.message(Command('help'))
async def help_command(message: types.Message):
    help_text = ("Команды:\n"
                 "/start - Запуск бота\n"
                 "/help -Справка (это сообщение)\n"
                 "/history - История поиска\n"
                 "/stats - Статистика фильмов по поиску\n"
                 "Чтобы найти фильм, просто отправьте его название")
    await message.reply(help_text)


@dp.message(Command('history'))
async def history_command(message: types.Message):
    user_id = message.from_user.id
    await show_history(message, user_id)


@dp.message(Command('stats'))
async def stats_command(message: types.Message):
    user_id = message.from_user.id
    await show_stats(message, user_id)


# --- Обработчик текстовых сообщений (поиск) ---

from aiogram.types import InputMediaPhoto


@dp.message()
async def search_film(message: types.Message):
    """Обработка текстовых сообщений как асинхронных поисковых запросов и отправка send_media_group."""

    RES_CNT = 5  # Кол-во результатов в поске, max=10

    query = message.text
    user_id = message.from_user.id

    # Логируем запрос в истории
    async with aiosqlite.connect('bot.db') as db:
        await db.execute("INSERT INTO history (user_id, query) VALUES (?, ?)", (user_id, query))
        await db.commit()

    searching = await message.reply(f"🔍 Ищу «{query}»...")
    films = await search_films(query)

    if not films:
        await bot.edit_message_text(text="❌ Ничего не найдено.", chat_id=searching.chat.id,
            message_id=searching.message_id)
        return

    # Собираем mediagroup и обновляем статистику
    media = []
    for film in films[:RES_CNT]:
        poster = film['posters'][0] if film['posters'] else None
        if poster:
            caption = (f"<b>{film['name']}</b>\n"
                       f"⭐ KP: {film['rating_kp'] or 'N/A'} | 🎬 IMDB: {film['rating_imdb'] or 'N/A'}\n"
                       f"<b>Год:</b> {film['year']}\n"
                       f"<a href=\"{film['links'][0] if film['links'] else '#'}\">Ссылка на плеер</a>\n"
                       f"<b>Описание:</b> {film['description'] if film['description'] else ''}"
                       )
            media.append(InputMediaPhoto(media=poster, caption=caption, parse_mode='HTML'))

    # Заменяем сообщение «ищем»
    await bot.edit_message_text(text="🐈 Вот что я нашёл:", chat_id=searching.chat.id, message_id=searching.message_id)

    # Отправляем mediagroup
    if media:
        await bot.send_media_group(chat_id=message.chat.id, media=media)
    else:
        await message.reply("😥 К сожалению, нет доступных постеров для отправки.")

    # Обновляем БД по найденым фильмам
    film_titles = [film['name'] for film in films[:RES_CNT]]
    async with aiosqlite.connect('bot.db') as db:
        for title in film_titles:
            await db.execute("""
                INSERT INTO stats (user_id, title, count) VALUES (?, ?, 1) ON CONFLICT(user_id, title) DO UPDATE SET count = count + 1
            """, (user_id, title))
        await db.commit()


# --- Запуск бота ---

# Регистрация функции инициализации базы данных при запуске
dp.startup.register(init_db)

if __name__ == '__main__':
    # Запуск бота с использованием asyncio
    asyncio.run(dp.start_polling(bot))
