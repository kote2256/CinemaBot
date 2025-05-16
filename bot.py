import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import aiosqlite
import asyncio
import aiohttp
from aiogram.exceptions import TelegramBadRequest
from search import search_films

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv("TOKEN"))  # Токен берётся из переменной окружения
dp = Dispatcher()

# --- Функции работы с базой данных ---

async def init_db():
    """Инициализация базы данных SQLite с таблицами history и stats."""
    async with aiosqlite.connect('bot.db') as db:
        # Таблица истории поисков
        await db.execute('''CREATE TABLE IF NOT EXISTS history
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             user_id INTEGER,
                             query TEXT,
                             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        # Таблица статистики предложенных фильмов
        await db.execute('''CREATE TABLE IF NOT EXISTS stats
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             user_id INTEGER,
                             film_id TEXT,
                             title TEXT,
                             count INTEGER DEFAULT 1)''')
        await db.commit()

# --- Асинхронная функция получения информации о фильме ---

'''async def get_film_info(query):
    """Асинхронная заглушка для получения информации о фильме с имитацией сетевого запроса."""
    async with aiohttp.ClientSession() as session:
        # Имитация асинхронного сетевого запроса (например, к API)
        await asyncio.sleep(1)  # Задержка для демонстрации асинхронности
        if "not found" in query.lower():
            return None
        return {
            'id': '123',  # Уникальный идентификатор фильма
            'title': query,  # Название фильма (в заглушке повторяет запрос)
            'rating': 8.5,  # Рейтинг фильма
            'poster': 'https://www.alleycat.org/wp-content/uploads/2019/03/FELV-cat.jpg',
            'links': ['https://example.com/watch1', 'https://example.com/watch2']  # Ссылки для просмотра
        }

# async def get_film_info(query):
    """Поиск информации о фильме в базе данных films.db по названию."""
    async with aiosqlite.connect('films.db') as db:
        async with db.execute("""
            SELECT ID, NAME, KP_RATING, POSTER_LINK, PAGE_LINK
            FROM movies
            WHERE NAME LIKE ?
            ORDER BY KP_RATING DESC
            LIMIT 1
        """, (f'%{query}%',)) as cursor:
            row = await cursor.fetchone()

    if row:
        return {
            'id': str(row[0]),
            'title': row[1],
            'rating': row[2] if row[2] is not None else "N/A",
            'poster': row[3] if row[3] else 'https://via.placeholder.com/300x450.png?text=No+Poster',
            'links': [row[4]] if row[4] else []
        }
    return None'''

# --- Вспомогательные функции для отображения данных ---

async def show_history(message: types.Message, user_id: int):
    """Отображение всей истории поисков без пагинации."""
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute("SELECT query, timestamp FROM history WHERE user_id = ? ORDER BY timestamp DESC",
                             (user_id,)) as cursor:
            rows = await cursor.fetchall()

    # Формирование текста сообщения
    text = "Search history:\n" if rows else "No search history."
    for row in rows:
        text += f"{row[1]}: {row[0]}\n"

    await message.reply(text)

async def show_stats(message: types.Message, user_id: int):
    """Отображение всей статистики предложенных фильмов без пагинации."""
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute("SELECT title, count FROM stats WHERE user_id = ? ORDER BY count DESC",
                             (user_id,)) as cursor:
            rows = await cursor.fetchall()

    # Формирование текста сообщения
    text = "Film statistics:\n" if rows else "No statistics available."
    for row in rows:
        text += f"{row[0]}: {row[1]} times\n"

    await message.reply(text)

# --- Обработчики команд ---

@dp.message(Command('start'))
async def start_command(message: types.Message):
    """Обработчик команды /start."""
    await message.reply("Welcome to the movie search bot! You can search for movies and series by sending their names.")

@dp.message(Command('help'))
async def help_command(message: types.Message):
    """Обработчик команды /help."""
    help_text = (
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/history - Show search history\n"
        "/stats - Show film statistics\n"
        "Send a movie or series name to search for it."
    )
    await message.reply(help_text)

@dp.message(Command('history'))
async def history_command(message: types.Message):
    """Обработчик команды /history."""
    user_id = message.from_user.id
    await show_history(message, user_id)

@dp.message(Command('stats'))
async def stats_command(message: types.Message):
    """Обработчик команды /stats."""
    user_id = message.from_user.id
    await show_stats(message, user_id)

# --- Обработчик текстовых сообщений (поиск) ---

@dp.message()
async def search_film(message: types.Message):
    """Обработка текстовых сообщений как асинхронных поисковых запросов."""
    query = message.text
    user_id = message.from_user.id

    # Отправка сообщения "Searching..."
    searching_message = await message.reply(f"Searching {query}")

    # Новый асинхронный поиск фильмов через парсер
    films = await search_films(query)

    if films:
        reply_text = ""
        for film in films:
            links_text = film['links'][0] if film['links'] else 'No link'
            poster_text = film['posters'][0] if film['posters'] else 'No poster'
            reply_text += (
                f"<b>{film['name']}</b> ({film['year']})\n"
                f"KP: {film['rating_kp'] if film['rating_kp'] is not None else 'N/A'} | "
                f"IMDB: {film['rating_imdb'] if film['rating_imdb'] is not None else 'N/A'}\n"
                f"<a href='{links_text}'>Player page</a> | "
                f"<a href='{poster_text}'>Poster</a>\n\n"
            )
        await bot.edit_message_text(
            text=reply_text,
            chat_id=searching_message.chat.id,
            message_id=searching_message.message_id,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    else:
        # Если фильм не найден, редактируем сообщение
        await bot.edit_message_text(
            text="Film not found.",
            chat_id=searching_message.chat.id,
            message_id=searching_message.message_id
        )

# --- Запуск бота ---

# Регистрация функции инициализации базы данных при запуске
dp.startup.register(init_db)

if __name__ == '__main__':
    # Запуск бота с использованием asyncio
    asyncio.run(dp.start_polling(bot))
