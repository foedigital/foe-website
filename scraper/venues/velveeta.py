import re
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


# Month name mapping
MONTH_MAP = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12
}

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class VelveetaScraper(BaseScraper):
    """Scraper for The Velveeta Room - SeatEngine ticketing."""

    venue_key = "velveeta"
    seatengine_url = "https://the-velveeta-room-the-velveeta-room.seatengine.com/"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_date_from_text(self, text: str) -> Optional[str]:
        """
        Parse date from various formats and return 'Day, Mon DD' format.
        Handles: '01/16/2026', 'January 16, 2026', 'Jan 16', etc.
        """
        if not text:
            return None

        # Try MM/DD/YYYY format
        match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3))
            try:
                date_obj = datetime(year, month, day)
                day_name = DAY_NAMES[date_obj.weekday()]
                month_abbrev = date_obj.strftime('%b')
                return f"{day_name}, {month_abbrev} {day}"
            except ValueError:
                pass

        # Try "Month DD, YYYY" or "Month DD YYYY" format
        match = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})', text)
        if match:
            month_str = match.group(1).lower()
            day = int(match.group(2))
            year = int(match.group(3))
            month = MONTH_MAP.get(month_str[:3])
            if month:
                try:
                    date_obj = datetime(year, month, day)
                    day_name = DAY_NAMES[date_obj.weekday()]
                    month_abbrev = date_obj.strftime('%b')
                    return f"{day_name}, {month_abbrev} {day}"
                except ValueError:
                    pass

        return None

    def parse_time_from_text(self, text: str) -> Optional[str]:
        """Extract time from text. Format: '8:00 PM'."""
        if not text:
            return None

        match = re.search(r'(\d{1,2}:\d{2})\s*(AM|PM|am|pm)', text)
        if match:
            time_part = match.group(1)
            ampm = match.group(2).upper()
            return f"{time_part} {ampm}"
        return None

    async def fetch_show_details(self, page: Page, ticket_url: str) -> Dict:
        """Fetch show details from the ticket page."""
        try:
            await page.goto(ticket_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Get page content for parsing
            content = await page.content()

            # Extract show name from h1 or title
            show_name = None
            h1 = await page.query_selector('h1')
            if h1:
                show_name = await h1.inner_text()
                show_name = show_name.strip() if show_name else None

            # If no h1, try the page title
            if not show_name:
                title = await page.title()
                if title and 'Velveeta' not in title:
                    show_name = title.split('|')[0].strip()

            # Extract date - look for common date patterns in the page
            event_date = None
            date_patterns = [
                r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
                r'([A-Z][a-z]+ \d{1,2},? \d{4})',  # Month DD, YYYY
            ]

            page_text = await page.evaluate('() => document.body.innerText')
            for pattern in date_patterns:
                match = re.search(pattern, page_text)
                if match:
                    event_date = self.parse_date_from_text(match.group(1))
                    if event_date:
                        break

            # Extract time
            show_time = self.parse_time_from_text(page_text)

            # Extract image
            img_url = None
            # Try og:image first
            og_img = await page.query_selector('meta[property="og:image"]')
            if og_img:
                img_url = await og_img.get_attribute('content')

            # Fallback to seatengine image
            if not img_url:
                img = await page.query_selector('img[src*="seatengine"]')
                if img:
                    img_url = await img.get_attribute('src')

            return {
                "event_name": show_name,
                "event_date": event_date,
                "show_time": show_time,
                "img_url": img_url
            }

        except Exception as e:
            print(f"      Error fetching {ticket_url}: {e}")
            return {}

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape The Velveeta Room shows from SeatEngine."""
        await page.goto(self.seatengine_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Scroll to load all events
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)

        # Get all unique show URLs
        links = await page.query_selector_all('a[href*="/shows/"]')
        print(f"    Found {len(links)} show links on listing page")

        ticket_urls = set()
        for link in links:
            href = await link.get_attribute("href")
            if href:
                if href.startswith("/"):
                    href = f"https://the-velveeta-room-the-velveeta-room.seatengine.com{href}"
                ticket_urls.add(href)

        print(f"    Found {len(ticket_urls)} unique ticket URLs")
        print(f"    Fetching details from each ticket page...")

        images = []
        for i, ticket_url in enumerate(sorted(ticket_urls)):
            details = await self.fetch_show_details(page, ticket_url)

            if not details.get("event_name"):
                continue

            show_name = details["event_name"]
            event_date = details.get("event_date")
            show_time = details.get("show_time")
            img_url = details.get("img_url", "")

            # Skip if no date found (probably an error page)
            if not event_date:
                print(f"      [--] {show_name} - no date found")
                continue

            images.append({
                "url": img_url or "",
                "event_name": show_name,
                "event_date": event_date,
                "show_time": show_time,
                "ticket_url": ticket_url,
            })
            print(f"      [OK] {show_name} | {event_date} @ {show_time}")

        print(f"    Completed: {len(images)} shows with valid dates")
        return images
