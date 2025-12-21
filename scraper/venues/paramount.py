"""Scraper for Paramount Theatre / Austin Theatre - comedy shows only."""

from typing import List, Dict
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


class ParamountScraper(BaseScraper):
    """
    Scraper for Paramount Theatre (Austin Theatre) comedy shows.

    The site uses Tessitura ticketing with dynamic JavaScript loading.
    Comedy shows are filtered via ?kid=4 parameter.
    Ticket URLs follow pattern: /[production_id] or /[production_id]/[performance_id]
    """

    venue_key = "paramount"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape comedy events from Paramount Theatre."""
        await page.goto(self.events_url, wait_until="networkidle", timeout=60000)

        # Wait longer for dynamic content to load
        await page.wait_for_timeout(8000)

        # Wait for event list to appear
        try:
            await page.wait_for_selector(".tn-prod-list-item", timeout=15000)
        except Exception:
            print("    No events found or page didn't load properly")
            return []

        # Scroll to load all events
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

        images = []

        # Find all event items
        event_elements = await page.query_selector_all(".tn-prod-list-item")
        print(f"    Found {len(event_elements)} event items")

        for event in event_elements:
            try:
                # Get event name
                event_name = None
                title_el = await event.query_selector(".tn-prod-list-item__perf-property--title, .tn-performance-title")
                if title_el:
                    event_name = await title_el.inner_text()
                    if event_name:
                        event_name = event_name.strip()

                if not event_name:
                    continue

                # Get event date
                event_date = None
                date_el = await event.query_selector(".tn-prod-list-item__perf-date")
                if date_el:
                    date_text = await date_el.inner_text()
                    if date_text:
                        event_date = date_text.strip()
                        # Clean up multi-line dates
                        event_date = " ".join(event_date.split())

                # Get ticket URL
                ticket_url = ""
                link_el = await event.query_selector("a")
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        ticket_url = href

                # Get event image
                img_url = ""
                img_el = await event.query_selector("img")
                if img_el:
                    img_url = await img_el.get_attribute("src") or ""

                # Ensure absolute URL for image
                if img_url and img_url.startswith("/"):
                    img_url = f"https://tickets.austintheatre.org{img_url}"

                images.append({
                    "url": img_url,
                    "event_name": event_name,
                    "event_date": event_date,
                    "ticket_url": ticket_url,
                })
                print(f"      + {event_name} ({event_date})")

            except Exception as e:
                print(f"    Error processing event: {e}")
                continue

        # Deduplicate by event name + date
        seen_keys = set()
        unique_images = []
        for img in images:
            name = img.get("event_name") or ""
            date = img.get("event_date") or ""
            key = f"{name.lower()}|{date}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_images.append(img)

        print(f"    Found {len(unique_images)} unique comedy shows")
        return unique_images
