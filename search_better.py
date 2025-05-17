import asyncio
import os
import random
from datetime import datetime
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def search_films(query: str, savepage: bool = True) -> List[Dict]:
    """
    Asynchronously search for films on kinogo.ec and return up to 15 results.
    Returns a list of dicts: [{name, year, rating_kp, rating_imdb, links, posters}]

    Args:
        query (str): Search query
        savepage (bool): Whether to save the HTML page to temp (./temp) folder
    """
    # Anti-detection user agents
    user_agents = [
        #"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        #"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    ]

    # Configure Chrome options for headless mode with anti-detection
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Headless mode
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
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
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
            """
        })

        # Format the search URL
        search_url = f"https://kinogo.ec/search/{query.replace(' ', '%20')}"
        logger.info(f"Navigating to {search_url}")
        driver.get(search_url)

        # Wait for search results to load (adjust selector based on page structure)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.shortstory"))
        )

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

        # Find search result items (based on sample HTML structure)
        items = soup.select("div.shortstory")[:15]  # Limit to 15 results
        logger.info(f"Found {len(items)} search results")

        for item in items:
            try:
                # Extract name
                name_tag = item.select_one("h2.zagolovki > a")
                name = name_tag.text.strip() if name_tag else "Unknown"

                # Extract year
                year_tag = item.select_one("div.th-item > b:-soup-contains('Год выпуска:')")
                year = year_tag.find_next_sibling(text=True).strip() if year_tag else "N/A"

                # Extract ratings
                kp_tag = item.select_one("span.kp")
                rating_kp = kp_tag.text.replace("KP ", "").strip() if kp_tag else "N/A"

                imdb_tag = item.select_one("span.imdb")
                rating_imdb = imdb_tag.text.replace("IMDB ", "").strip() if imdb_tag else "N/A"

                # Extract link
                link = name_tag["href"] if name_tag and name_tag.get("href") else ""

                # Extract poster
                poster_tag = item.select_one("div.th-img > img")
                poster = poster_tag["src"] if poster_tag and poster_tag.get("src") else ""
                if poster and not poster.startswith("http"):
                    poster = f"https://kinogo.ec{poster}"

                # Append result
                results.append({
                    "name": name,
                    "year": year,
                    "rating_kp": rating_kp,
                    "rating_imdb": rating_imdb,
                    "links": [link] if link else [],
                    "posters": [poster] if poster else []
                })

            except Exception as e:
                logger.warning(f"Error parsing item: {e}")
                continue

    except Exception as e:
        logger.error(f"Error during scraping: {e}")

    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

    return results