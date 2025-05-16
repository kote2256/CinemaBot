import sys
from bs4 import BeautifulSoup
import requests
import random
import sqlite3
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("parser_log.txt", mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def log_print(message):
    logging.info(message)

# Создаем базу данных
db = sqlite3.connect("films.db")
cur = db.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS movies (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    ORIGIN TEXT,
    NAME TEXT,
    YEAR TEXT,
    DESCRIPTION TEXT,
    PAGE_LINK TEXT,
    POSTER_LINK TEXT,
    KP_RATING REAL,
    IMDB_RATING REAL
)""")
db.commit()

origin_name = "we_lordfilm12_ru"

user_agent_list = [
    'Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 uacq',
    'Mozilla/5.0 (Windows NT 11.0; Win64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5653.214 Safari/537.36'
]

url_base = "https://we.lordfilm12.ru/filmy/"
index_page = 1
max_pages = 512 # 575

while index_page <= max_pages:
    url = f"{url_base}page/{index_page}/" if index_page > 1 else url_base
    user_agent = random.choice(user_agent_list)
    headers = {'User-Agent': user_agent}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        page = BeautifulSoup(response.text, "lxml")

        name_list = []
        year_list = []
        page_link_list = []
        poster_link_list = []
        kp_rating_list = []
        imdb_rating_list = []
        description_list = []

        # Extract movie data from the page
        for film in page.find_all("div", class_="th-item"):
            link_elem = film.find("a", class_="th-in with-mask")
            title_elem = film.find("div", class_="th-title")
            year_elem = film.find("div", class_="th-series")
            poster_elem = film.find("img")
            kp_rating_elem = film.find("div", class_="th-rate-kp")
            imdb_rating_elem = film.find("div", class_="th-rate-imdb")

            if link_elem and title_elem and year_elem and poster_elem:
                name_list.append(title_elem.text.strip())
                year_list.append(year_elem.text.strip())
                page_link_list.append(link_elem.get('href'))
                poster_link_list.append(poster_elem.get('src'))

                # Extract and convert ratings to float, or None if not available
                try:
                    kp_rating = float(kp_rating_elem.find("span").text.strip()) if kp_rating_elem and kp_rating_elem.find("span") else None
                    kp_rating_list.append(kp_rating)
                except (ValueError, AttributeError):
                    kp_rating_list.append(None)

                try:
                    imdb_rating = float(imdb_rating_elem.find("span").text.strip()) if imdb_rating_elem and imdb_rating_elem.find("span") else None
                    imdb_rating_list.append(imdb_rating)
                except (ValueError, AttributeError):
                    imdb_rating_list.append(None)

        min_length = min(len(name_list), len(year_list), len(page_link_list), len(poster_link_list),
                         len(kp_rating_list), len(imdb_rating_list))
        name_list = name_list[:min_length]
        year_list = year_list[:min_length]
        page_link_list = page_link_list[:min_length]
        poster_link_list = poster_link_list[:min_length]
        kp_rating_list = kp_rating_list[:min_length]
        imdb_rating_list = imdb_rating_list[:min_length]

        # Fetch descriptions for each movie
        for link in page_link_list:
            try:
                response = requests.get(link, headers=headers, timeout=10)
                response.raise_for_status()
                page2 = BeautifulSoup(response.text, "lxml")
                description_elem = page2.find("div", class_="fdesc")
                description = description_elem.text.strip() if description_elem else None
                if description:
                    description = ' '.join(description.split())  # Clean up whitespace only if description exists
                description_list.append(description)
            except (requests.RequestException, AttributeError) as e:
                log_print(f"Ошибка при загрузке описания для {link}: {e}")
                description_list.append(None)

        description_list = description_list[:min_length]

        first_id = None
        last_id = None

        # Insert data into database
        for i in range(min_length):
            cur.execute("""INSERT INTO movies (ORIGIN, NAME, YEAR, DESCRIPTION, PAGE_LINK, POSTER_LINK, KP_RATING, IMDB_RATING)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (origin_name, name_list[i], year_list[i], description_list[i],
                         page_link_list[i], poster_link_list[i], kp_rating_list[i], imdb_rating_list[i]))
            if first_id is None:
                first_id = cur.lastrowid
            last_id = cur.lastrowid

        db.commit()

        log_print(f"Страница {index_page} обработана, записано {min_length} фильмов. ID записей: от {first_id} до {last_id}")

        index_page += 1

    except requests.RequestException as e:
        log_print(f"Ошибка при загрузке страницы {url}: {e}")
        break
    except Exception as e:
        log_print(f"Неожиданная ошибка на странице {index_page}: {e}")
        break

log_print("Парсинг завершен")
db.close()
