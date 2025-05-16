import aiohttp
from bs4 import BeautifulSoup
import os
import time

async def search_films(query: str, savepage: bool = False):
    """
    Asynchronously search for films on kinogo.ec and return up to 15 results.
    Returns a list of dicts: [{name, year, rating_kp, rating_imdb, links, posters}]
    """
    search_url = f"https://www.kinogo.ec/search/{query.replace(' ', '%20')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.kinogo.ec/",
        "Origin": "https://www.kinogo.ec"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, headers=headers) as response:
            if response.status != 200:
                print(f"Failed to fetch page: {response.status}")
                return []

            html = await response.text()
            if savepage:
                os.makedirs("temp", exist_ok=True)
                fn = f"temp/search_{query.replace(' ', '_')}_{int(time.time())}.html"
                with open(fn, "w", encoding="utf-8") as f:
                    f.write(html)

            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all("div", class_="shortstory", limit=15)
            films = []

            for item in items:
                # --- Title & Link ---
                a = item.select_one(".shortstory__title a")
                link = a["href"] if a else "N/A"
                if link != "N/A" and not link.startswith("http"):
                    link = "https://kinogo.ec" + link
                title_text = a.get_text(strip=True) if a else "N/A"
                # strip off trailing year in parentheses if present
                name = title_text.rsplit(" (", 1)[0]

                # --- Poster ---
                img = item.select_one(".shortstory__poster img")
                poster = img["data-src"] or img["src"] if img else "N/A"
                if poster != "N/A" and poster.startswith("/"):
                    poster = "https://kinogo.ec" + poster

                # --- Year ---
                year = "N/A"
                for span in item.select(".shortstory__info span"):
                    b = span.find("b")
                    if b and "Год выпуска" in b.text:
                        # the year is in the <a> right after the <b>
                        a_year = span.find("a")
                        year = a_year.text.strip() if a_year else "N/A"
                        break

                # --- Ratings ---
                kp = item.select_one(".film__rating .kp")
                rating_kp = kp.text.split()[1] if kp else "N/A"
                imdb = item.select_one(".film__rating .imdb")
                rating_imdb = imdb.text.split()[1] if imdb else "N/A"

                films.append({
                    "name": name,
                    "year": year,
                    "rating_kp": rating_kp,
                    "rating_imdb": rating_imdb,
                    "links": [link],
                    "posters": [poster]
                })

            return films
