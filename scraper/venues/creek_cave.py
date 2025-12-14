import re
from typing import List, Dict
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES, PAGE_LOAD_WAIT


class CreekCaveScraper(BaseScraper):
    """Scraper for Creek and the Cave - uses background-image CSS."""

    venue_key = "creek_cave"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    async def scrape(self, page: Page) -> List[Dict]:
        """Override to handle background-image style extraction."""
        await page.goto(self.events_url, wait_until="networkidle")
        await page.wait_for_timeout(PAGE_LOAD_WAIT)

        # Navigate through multiple months to get more events
        for _ in range(2):
            try:
                next_btn = await page.query_selector('[data-events-nav-next]')
                if next_btn:
                    await next_btn.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        # Go back to current month
        for _ in range(2):
            try:
                prev_btn = await page.query_selector('[data-events-nav-previous]')
                if prev_btn:
                    await prev_btn.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        images = []

        # Extract background-image URLs from event cards
        event_cards = await page.query_selector_all('.event-list-detail-image')
        for card in event_cards:
            style = await card.get_attribute('style') or ''
            match = re.search(r"url\(['\"]?([^'\"]+)['\"]?\)", style)
            if match:
                url = match.group(1)
                if self.is_valid_image_url(url):
                    # Get event name from sibling element
                    event_name = None
                    try:
                        parent = await card.evaluate_handle("el => el.closest('.events-list-detail')")
                        if parent:
                            title_el = await parent.query_selector('.events-list-detail-title')
                            if title_el:
                                event_name = await title_el.inner_text()
                    except Exception:
                        pass

                    # Get event date
                    event_date = None
                    try:
                        day_parent = await card.evaluate_handle("el => el.closest('.events-list-day')")
                        if day_parent:
                            date_el = await day_parent.query_selector('.event-list-detail-date-day')
                            if date_el:
                                event_date = await date_el.inner_text()
                    except Exception:
                        pass

                    images.append({
                        "url": url,
                        "event_name": event_name.strip() if event_name else None,
                        "event_date": event_date.strip() if event_date else None,
                    })

        # Deduplicate
        seen_urls = set()
        unique_images = []
        for img in images:
            if img["url"] not in seen_urls:
                seen_urls.add(img["url"])
                unique_images.append(img)

        return unique_images
