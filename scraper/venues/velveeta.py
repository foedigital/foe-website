from typing import List, Dict
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


class VelveetaScraper(BaseScraper):
    """Scraper for The Velveeta Room - Wix site."""

    venue_key = "velveeta"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    async def scrape(self, page: Page) -> List[Dict]:
        """Override to handle Wix site and filter for poster images."""
        await page.goto(self.events_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        # Scroll to load lazy images
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)

        images = []

        # Find all Wix images
        img_elements = await page.query_selector_all("img[src*='wixstatic']")
        for img in img_elements:
            src = await img.get_attribute("src")
            alt = await img.get_attribute("alt") or ""

            if not src:
                continue

            # Skip logos, icons, and non-poster images
            alt_lower = alt.lower()
            if any(skip in alt_lower for skip in ["logo", "icon", "instagram", "background", "sky", "stars"]):
                continue

            # Prioritize images with "poster" in alt text, but include others from gallery
            if not self.is_valid_image_url(src):
                continue

            # Extract event name from alt text if available
            event_name = alt if alt and "poster" in alt_lower else None

            images.append({
                "url": src,
                "event_name": event_name,
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
