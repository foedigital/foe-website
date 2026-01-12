import re
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES, PAGE_LOAD_WAIT


# Month name mapping
MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class CreekCaveScraper(BaseScraper):
    """Scraper for Creek and the Cave."""

    venue_key = "creek_cave"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_date_with_day(self, date_str: str) -> Optional[str]:
        """
        Convert 'Jan 11' to 'Saturday, Jan 11' by calculating day of week.
        """
        if not date_str:
            return None

        match = re.match(r'([A-Za-z]{3})\s+(\d{1,2})', date_str.strip())
        if not match:
            return None

        month_str = match.group(1).lower()
        day = int(match.group(2))
        month = MONTH_MAP.get(month_str)

        if not month:
            return None

        # Use current year
        year = datetime.now().year
        try:
            date_obj = datetime(year, month, day)
            day_name = DAY_NAMES[date_obj.weekday()]
            month_abbrev = month_str.capitalize()
            return f"{day_name}, {month_abbrev} {day}"
        except ValueError:
            return None

    def parse_time(self, text: str) -> Optional[str]:
        """
        Extract time from card text. Format: '3:30 pm' -> '3:30 PM'
        """
        if not text:
            return None

        # Look for time pattern in text
        match = re.search(r'(\d{1,2}:\d{2})\s*(am|pm)', text, re.I)
        if match:
            time_part = match.group(1)
            ampm = match.group(2).upper()
            return f"{time_part} {ampm}"
        return None

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape Creek and the Cave events with date, time, and images."""
        await page.goto(self.events_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(PAGE_LOAD_WAIT)

        # Navigate forward to load more events
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

        # Process each day container
        day_containers = await page.query_selector_all('.events-list-day')
        print(f"    Found {len(day_containers)} day containers")

        for day_container in day_containers:
            # Get the date for this day
            date_raw = None
            date_el = await day_container.query_selector('.event-list-detail-date-day')
            if date_el:
                date_raw = await date_el.inner_text()

            # Calculate full date with day of week
            event_date = self.parse_date_with_day(date_raw)

            # Get all events for this day
            events = await day_container.query_selector_all('.events-list-detail')

            for event in events:
                try:
                    # Get event name
                    event_name = None
                    title_el = await event.query_selector('.events-list-detail-title')
                    if title_el:
                        event_name = await title_el.inner_text()
                        event_name = event_name.strip() if event_name else None

                    if not event_name:
                        continue

                    # Get time from card text
                    card_text = await event.inner_text()
                    show_time = self.parse_time(card_text)

                    # Get image from background-image style
                    img_url = None
                    img_container = await event.query_selector('.event-list-detail-image')
                    if img_container:
                        style = await img_container.get_attribute('style') or ''
                        match = re.search(r"url\(['\"]?([^'\"]+)['\"]?\)", style)
                        if match:
                            img_url = match.group(1)
                            if not self.is_valid_image_url(img_url):
                                img_url = None

                    # Create unique ticket URL
                    unique_key = f"{event_name}|{event_date}|{show_time}"
                    url_hash = hashlib.md5(unique_key.encode()).hexdigest()[:8]
                    ticket_url = f"https://www.creekandcave.com/calendar#{url_hash}"

                    images.append({
                        "url": img_url or "",
                        "event_name": event_name,
                        "event_date": event_date,
                        "show_time": show_time,
                        "ticket_url": ticket_url,
                    })

                    if img_url:
                        print(f"      + {event_name} | {event_date} @ {show_time}")
                    else:
                        print(f"      + {event_name} | {event_date} @ {show_time} (no image)")

                except Exception as e:
                    print(f"    Error processing event: {e}")
                    continue

        # Deduplicate by name + date + time
        seen_keys = set()
        unique_images = []
        for img in images:
            key = f"{(img.get('event_name') or '').lower()}|{img.get('event_date')}|{img.get('show_time')}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_images.append(img)

        print(f"    Found {len(unique_images)} unique events")
        return unique_images
