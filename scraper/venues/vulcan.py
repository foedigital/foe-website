"""Scraper for Vulcan Gas Company - filters for comedy shows only."""

import re
from typing import List, Dict, Optional
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


# Day abbreviation to full name mapping
DAY_MAP = {
    'mon': 'Monday', 'tue': 'Tuesday', 'wed': 'Wednesday',
    'thu': 'Thursday', 'fri': 'Friday', 'sat': 'Saturday', 'sun': 'Sunday'
}

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

    def format_time(self, time_str: str) -> Optional[str]:
        """Format time string to standard format like '8:00 PM'."""
        if not time_str:
            return None
        # Clean up and standardize
        time_str = time_str.strip().upper()
        # Handle formats like "8:00 pm" -> "8:00 PM"
        match = re.match(r'(\d{1,2}:\d{2})\s*(AM|PM)', time_str, re.I)
        if match:
            return f"{match.group(1)} {match.group(2).upper()}"
        return time_str

    def format_date(self, day_abbrev: str, month: str, date: str) -> Optional[str]:
        """Format date to standard format like 'Tuesday, Jan 13'."""
        if not month or not date:
            return None

        # Convert day abbreviation to full name
        day_lower = day_abbrev.lower().strip() if day_abbrev else ""
        day_name = DAY_MAP.get(day_lower, day_abbrev)

        # Capitalize month properly (JAN -> Jan)
        month_cap = month.strip().capitalize()
        date_num = date.strip()

        if day_name:
            return f"{day_name}, {month_cap} {date_num}"
        return f"{month_cap} {date_num}"

    async def fetch_image_from_ticket_page(self, page: Page, ticket_url: str) -> Optional[str]:
        """Fetch the event poster image from the ticketsauce page."""
        try:
            await page.goto(ticket_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Try to find the main event image
            # Check og:image meta tag first (most reliable)
            og_image = await page.query_selector('meta[property="og:image"]')
            if og_image:
                img_url = await og_image.get_attribute("content")
                if img_url:
                    return img_url

            # Try to find main event image
            img_selectors = [
                'img[alt*="Logo"]',
                'img[alt*="logo"]',
                '.event-image img',
                '.poster img',
                'main img',
                'article img',
            ]

            for selector in img_selectors:
                img = await page.query_selector(selector)
                if img:
                    src = await img.get_attribute("src")
                    if src and "cloudinary" in src:
                        return src

            # Fallback: find any cloudinary image
            all_imgs = await page.query_selector_all('img[src*="cloudinary"]')
            if all_imgs:
                src = await all_imgs[0].get_attribute("src")
                if src:
                    return src

        except Exception as e:
            print(f"      Error fetching image from {ticket_url}: {e}")

        return None

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape comedy events from Vulcan Gas Company."""
        await page.goto(self.events_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Scroll to load all events
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

        events_data = []

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

                # Get event month, date, day, and time separately
                month_el = await event.query_selector(".event-month")
                date_el = await event.query_selector(".event-date")
                day_el = await event.query_selector(".event-day")
                time_el = await event.query_selector(".event-time")

                month = await month_el.inner_text() if month_el else ""
                date = await date_el.inner_text() if date_el else ""
                day = await day_el.inner_text() if day_el else ""
                time_raw = await time_el.inner_text() if time_el else ""

                # Format date and time properly
                event_date = self.format_date(day, month, date)
                show_time = self.format_time(time_raw)

                if event_name:
                    events_data.append({
                        "event_name": event_name,
                        "event_date": event_date,
                        "show_time": show_time,
                        "ticket_url": ticket_url,
                    })
                    print(f"      + Comedy: {event_name} | {event_date} @ {show_time}")

            except Exception as e:
                print(f"    Error processing event: {e}")
                continue

        # Deduplicate by event name + date + time
        seen_keys = set()
        unique_events = []
        for evt in events_data:
            key = f"{(evt.get('event_name') or '').lower()}|{evt.get('event_date')}|{evt.get('show_time')}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_events.append(evt)

        print(f"    Found {len(unique_events)} unique comedy shows")

        # Now fetch images from ticket pages
        print(f"    Fetching poster images from ticket pages...")
        images = []
        for evt in unique_events:
            ticket_url = evt.get("ticket_url", "")
            img_url = await self.fetch_image_from_ticket_page(page, ticket_url)

            images.append({
                "url": img_url or "",
                "event_name": evt["event_name"],
                "event_date": evt["event_date"],
                "show_time": evt["show_time"],
                "ticket_url": ticket_url,
            })

            if img_url:
                print(f"      [OK] Got image for {evt['event_name']}")
            else:
                print(f"      [--] No image for {evt['event_name']}")

        print(f"    Completed: {len(images)} comedy shows with images")
        return images
