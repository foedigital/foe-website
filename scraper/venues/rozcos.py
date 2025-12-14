from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


class RozcosScraper(BaseScraper):
    """Scraper for Rozco's Comedy."""

    venue_key = "rozcos"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    async def handle_pagination(self, page: Page):
        """Handle any pagination."""
        try:
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(1000)
        except Exception:
            pass
