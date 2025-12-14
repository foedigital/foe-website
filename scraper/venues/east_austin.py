from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


class EastAustinScraper(BaseScraper):
    """Scraper for East Austin Comedy Club - Squarespace site."""

    venue_key = "east_austin"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    async def handle_pagination(self, page: Page):
        """Handle Squarespace lazy loading."""
        try:
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(1500)
        except Exception:
            pass
