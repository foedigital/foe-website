"""Scraper for Vulcan Gas Company - filters for comedy shows only."""

import re
from typing import List, Dict
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


# Keywords to exclude (non-comedy events)
EXCLUDED_KEYWORDS = [
    "bingo", "loco", "dj", "edm", "wreckno", "super future",
    "dose of sound", "electronic", "rave"
]


class VulcanScraper(BaseScraper):
    """
    Scraper for Vulcan Gas Company.

    Filters for comedy shows only by:
    1. Primary filter: Only include events with ticket links to vulcanatx.ticketsauce.com
    2. Secondary filter: Exclude events with non-comedy keywords in the title
    """

    venue_key = "vulcan"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def is_comedy_show(self, title: str, ticket_url: str) -> bool:
        """
        Determine if an event is a comedy show.

        Primary filter: Ticket URL must contain vulcanatx.ticketsauce.com
        Secondary filter: Title must not contain excluded keywords
        """
        # Primary filter: must use ticketsauce
        if not ticket_url or "vulcanatx.ticketsauce.com" not in ticket_url.lower():
            return False

        # Secondary filter: check for excluded keywords
        title_lower = title.lower() if title else ""
        for keyword in EXCLUDED_KEYWORDS:
            if keyword in title_lower:
                return False

        return True

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape comedy events from Vulcan Gas Company."""
        await page.goto(self.events_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Scroll to load all events
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

        images = []

        # Find all event containers using the actual site structure
        event_elements = await page.query_selector_all(".w-dyn-item")
        print(f"    Found {len(event_elements)} event containers")

        for event in event_elements:
            try:
                # Get ticket link from .event-ctas
                ticket_url = ""
                ticket_link = await event.query_selector('a[href*="ticketsauce"]')
                if ticket_link:
                    ticket_url = await ticket_link.get_attribute("href") or ""

                # Get event title from .event-name
                event_name = None
                title_el = await event.query_selector(".event-name")
                if title_el:
                    event_name = await title_el.inner_text()
                    if event_name:
                        event_name = event_name.strip()

                # Skip if not a comedy show (no ticketsauce link or has excluded keywords)
                if not self.is_comedy_show(event_name, ticket_url):
                    continue

                # Get event month and date
                event_date = None
                month_el = await event.query_selector(".event-month")
                date_el = await event.query_selector(".event-date")
                day_el = await event.query_selector(".event-day")

                if month_el and date_el:
                    month = await month_el.inner_text()
                    date = await date_el.inner_text()
                    if month and date:
                        event_date = f"{month.strip()} {date.strip()}"

                # Get event day and time
                event_time = None
                time_el = await event.query_selector(".event-time")
                if time_el:
                    event_time = await time_el.inner_text()
                    if event_time:
                        event_time = event_time.strip()

                # Get day of week
                day_of_week = None
                if day_el:
                    day_of_week = await day_el.inner_text()
                    if day_of_week:
                        day_of_week = day_of_week.strip()

                # Combine date info
                if event_date:
                    if day_of_week:
                        event_date = f"{day_of_week}, {event_date}"
                    if event_time:
                        event_date = f"{event_date} @ {event_time}"

                # Get event image
                img_url = ""
                img_el = await event.query_selector("img")
                if img_el:
                    img_url = await img_el.get_attribute("src") or ""
                    if not img_url:
                        img_url = await img_el.get_attribute("data-src") or ""

                # Check for background-image on event wrapper
                if not img_url:
                    wrapper = await event.query_selector(".event-wrapper, [class*='image']")
                    if wrapper:
                        style = await wrapper.get_attribute("style") or ""
                        match = re.search(r"url\(['\"]?([^'\"]+)['\"]?\)", style)
                        if match:
                            img_url = match.group(1)

                # Ensure absolute URL
                if img_url and img_url.startswith("/"):
                    img_url = self.venue_url + img_url

                if event_name:
                    images.append({
                        "url": img_url,
                        "event_name": event_name,
                        "event_date": event_date,
                        "ticket_url": ticket_url,
                    })
                    print(f"      + Comedy: {event_name} ({event_date})")

            except Exception as e:
                print(f"    Error processing event: {e}")
                continue

        # Deduplicate by event name (keep unique shows, but allow recurring with diff dates)
        seen_keys = set()
        unique_images = []
        for img in images:
            # Use name + date as key to allow same show on different dates
            name = img.get("event_name") or ""
            date = img.get("event_date") or ""
            key = f"{name.lower()}|{date}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_images.append(img)

        print(f"    Found {len(unique_images)} comedy shows")
        return unique_images
