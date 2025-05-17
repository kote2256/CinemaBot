import logging
import os
import random
import re
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def search_films(query: str, savepage: bool = False):
    """
    Asynchronously search for films on kinogo.ec and return up to 15 results.
    Returns a list of dicts: [{name, year, rating_kp, rating_imdb, links, posters, description}.Tools used: selenium, bs4

    Args:
        query (str): Search query
        savepage (bool): Whether to save the HTML page to temp (./temp) folder
    """
    # Anti-detection user agents
    user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0", ]

    # Configure Chrome options for headless mode with anti-detection
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")

    # Disable automation flags to avoid detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Set window size to mimic real browser
    chrome_options.add_argument("--window-size=1920,1080")

    # Initialize WebDriver
    service = Service(ChromeDriverManager().install())
    driver = None
    results = []

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Override navigator properties to avoid detection
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.navigator.chrome = {
                    runtime: {},
                };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """})

        # Format the search URL
        search_url = f"http://www.kinogo.ec/search/{query.replace(' ', '%20')}"
        logger.info(f"Navigating to {search_url}")
        driver.get(search_url)

        # Wait for search results to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.shortstory")))

        # Get page source and parse with BeautifulSoup
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        # Save page if requested
        if savepage:
            temp_dir = "./temp"
            os.makedirs(temp_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{temp_dir}/kinogo_search_{timestamp}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info(f"Page saved to {filename}")

        # Find search result items
        items = soup.select("div.shortstory")[:15]
        logger.info(f"Found {len(items)} search results")

        for item in items:
            try:
                # Extract title from shortstory__header
                title_tag = item.select_one("div.shortstory__header h2")
                title = title_tag.text.strip() if title_tag else "Unknown"

                # Extract watch link and poster from shortstory__poster
                watch_link_tag = item.select_one("div.shortstory__poster a")
                watch_link = watch_link_tag["href"] if watch_link_tag and watch_link_tag.get("href") else ""

                poster_tag = item.select_one("div.shortstory__poster img")
                poster = poster_tag["data-src"] if poster_tag and poster_tag.get("data-src") else ""
                if poster and not poster.startswith("http"):
                    poster = f"https://kinogo.ec{poster}"

                # Extract year from shortstory__info-wrapper
                year = None
                year_tag = item.select_one("div.shortstory__info-wrapper div span")
                if year_tag and year_tag.text.strip():
                    year_text = ''.join(filter(lambda x: x.isdigit(), year_tag.text.strip()))
                    # Check if it's a 4-digit number
                    # print(year_text)
                    if re.match(r'^\d{4}$', year_text):
                        year = year_text

                # Extract description from excerpt
                description_tag = item.select_one("div.excerpt")
                description = description_tag.text.strip() if description_tag else ""

                # Extract ratings
                kp_tag = item.select_one("span.kp")
                rating_kp = kp_tag.text.replace("KP ", "").strip() if kp_tag else "N/A"

                imdb_tag = item.select_one("span.imdb")
                rating_imdb = imdb_tag.text.replace("IMDB ", "").strip() if imdb_tag else "N/A"

                # Append result
                results.append({"name": title, "year": year, "rating_kp": rating_kp, "rating_imdb": rating_imdb,
                    "links": [watch_link] if watch_link else [], "posters": [poster] if poster else [],
                    "description": description})

            except Exception as e:
                logger.warning(f"Error parsing item: {e}")
                continue

    except Exception as e:
        logger.error(f"Error during scraping: {e}")

    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

    print(results)

    return results
