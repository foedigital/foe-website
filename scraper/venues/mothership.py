from typing import List, Dict
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


class MothershipScraper(BaseScraper):
    """Scraper for Comedy Mothership - Next.js site with slow load."""

    venue_key = "mothership"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    async def scrape(self, page: Page) -> List[Dict]:
        """Override to handle slow loading and Next.js image URLs."""
        await page.goto(self.events_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)  # Extra time for JS rendering

        # Scroll to load more content
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

        images = []

        # Find event card images
        img_elements = await page.query_selector_all("[class*='EventCard'] img")
        for img in img_elements:
            src = await img.get_attribute("src")
            if not src:
                continue

            # Skip default placeholder images
            if "default-event" in src:
                continue

            # Decode Next.js image URL to get actual source
            if "/_next/image?url=" in src:
                import urllib.parse
                parsed = urllib.parse.urlparse(src)
                query = urllib.parse.parse_qs(parsed.query)
                if "url" in query:
                    src = urllib.parse.unquote(query["url"][0])

            if not self.is_valid_image_url(src):
                continue

            # Get event name from card
            event_name = None
            try:
                card = await img.evaluate_handle("el => el.closest('[class*=\"EventCard_eventCard\"]')")
                if card:
                    title_el = await card.query_selector("[class*='EventCard_title'], h3, h4")
                    if title_el:
                        event_name = await title_el.inner_text()
            except Exception:
                pass

            images.append({
                "url": src,
                "event_name": event_name.strip() if event_name else None,
                "event_date": None,
            })

        # Deduplicate
        seen_urls = set()
        unique_images = []
        for img in images:
            if img["url"] not in seen_urls:
                seen_urls.add(img["url"])
                unique_images.append(img)

        return unique_images
