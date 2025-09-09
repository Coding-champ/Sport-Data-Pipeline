from typing import Optional
"""
Base classes and utilities for web scraping.
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

import aiohttp
import cloudscraper
from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page, async_playwright

from ...common.http import DEFAULT_UAS, build_headers

# =============================================================================
# 1. SCRAPING CONFIGURATION
# =============================================================================


@dataclass
class ScrapingConfig:
    """Konfiguration für Web Scraping"""

    base_url: str
    selectors: dict[str, str]
    headers: dict[str, str]
    delay_range: tuple = (1, 3)
    max_retries: int = 3
    timeout: int = 30
    use_proxy: bool = False
    proxy_list: Optional[list[str]] = None
    anti_detection: bool = True
    screenshot_on_error: bool = True


# =============================================================================
# 2. ANTI-DETECTION & UTILITIES
# =============================================================================


class AntiDetectionManager:
    """Manager für Anti-Detection-Maßnahmen"""

    def __init__(self):
        self.session_headers = self._generate_headers()

    def _generate_headers(self) -> dict[str, str]:
        """Generiert realistische HTTP Headers"""
        # Reuse shared UA pool and header mixer for consistency
        ua = random.choice(DEFAULT_UAS)
        headers = build_headers(ua, header_randomize=True, accept_json=False)
        # Preserve a few harmless header hints
        headers.update(
            {
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }
        )
        return headers

    async def random_delay(self, delay_range: tuple = (1, 3)):
        """Zufällige Verzögerung"""
        delay = random.uniform(delay_range[0], delay_range[1])
        await asyncio.sleep(delay)


# =============================================================================
# 3. BASE SCRAPER CLASSES
# =============================================================================


class BaseScraper(ABC):
    """Abstrakte Basisklasse für alle Scraper"""

    def __init__(self, config: ScrapingConfig, db_manager, name: str):
        self.config = config
        self.db_manager = db_manager
        self.name = name
        self.logger = logging.getLogger(f"scraper.{name}")
        self.anti_detection = AntiDetectionManager()
        self.session = None  # type: Optional[aiohttp.ClientSession]
        self.scraper = None  # CloudScraper session
        self.cloudscraper = (
            None  # Alias für Kompatibilität zu spezifischen Scraper-Implementierungen
        )

    async def initialize(self):
        """Initialisiert den Scraper"""
        # Aiohttp Session
        connector = aiohttp.TCPConnector(limit=10)
        self.session = aiohttp.ClientSession(
            headers=self.anti_detection.session_headers,
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        )

        # CloudScraper für Cloudflare-geschützte Seiten
        self.scraper = cloudscraper.create_scraper()
        # Kompatibilitäts-Alias, da einige Scraper 'self.cloudscraper' erwarten
        self.cloudscraper = self.scraper

    async def cleanup(self):
        """Räumt Ressourcen auf"""
        if self.session:
            await self.session.close()

    @abstractmethod
    async def scrape_data(self) -> list[dict]:
        """Hauptmethode zum Scrapen von Daten"""
        pass

    async def fetch_page(
        self, url: str, method: str = "GET", data: dict = None, use_cloudscraper: bool = False
    ) -> str:
        """Lädt eine Webseite herunter"""
        for attempt in range(self.config.max_retries):
            try:
                if use_cloudscraper:
                    response = self.scraper.get(url)
                    response.raise_for_status()
                    return response.text
                else:
                    async with self.session.request(method, url, json=data) as response:
                        response.raise_for_status()
                        return await response.text()

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < self.config.max_retries - 1:
                    await self.anti_detection.random_delay((2, 5))
                else:
                    raise

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parst HTML mit BeautifulSoup"""
        return BeautifulSoup(html, "html.parser")

    async def save_to_db(self, table: str, data: list[dict]):
        """Speichert Daten in die Datenbank"""
        if not data:
            return

        await self.db_manager.bulk_insert(table, data, "ON CONFLICT DO NOTHING")


class PlaywrightScraper(BaseScraper):
    """Scraper, der Playwright für dynamische Seiten nutzt"""

    def __init__(self, config: ScrapingConfig, db_manager, name: str):
        super().__init__(config, db_manager, name)
        self.browser = None  # type: Optional[Browser]
        self.page = None  # type: Optional[Page]

    async def initialize(self):
        """Initialisiert Playwright"""
        await super().initialize()
        playwright = await async_playwright().start()
        try:
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
        except Exception as e:
            self.logger.error(f"Playwright initialization failed: {e}")
            # Ensure playwright is stopped if browser launch fails
            await playwright.stop()
            raise

    async def cleanup(self):
        """Räumt Playwright-Ressourcen auf"""
        await super().cleanup()
        if self.page and not self.page.is_closed():
            await self.page.close()
        if self.browser and self.browser.is_connected():
            await self.browser.close()
        # It's good practice to stop the playwright instance if we started it.
        # However, the async_playwright context manager handles this better.
        # For now, we assume the application lifecycle manages stopping playwright.

    async def goto_page(self, url: str, wait_until: str = "domcontentloaded"):
        """Navigiert zu einer Seite"""
        if self.page:
            await self.page.goto(url, wait_until=wait_until)
            await self.anti_detection.random_delay()

    async def take_screenshot(self, path: str):
        """Macht einen Screenshot"""
        if self.page:
            await self.page.screenshot(path=path)
