import re
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


# Month name mapping
MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class VelveetaScraper(BaseScraper):
    """Scraper for The Velveeta Room - SeatEngine ticketing."""

    venue_key = "velveeta"
    seatengine_url = "https://the-velveeta-room-the-velveeta-room.seatengine.com/"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_date_with_day(self, date_str: str) -> Optional[str]:
        """
        Convert various date formats to 'Saturday, Jan 11' format.
        Handles: 'Jan 11', 'January 11', 'Sat, Jan 11', etc.
        """
        if not date_str:
            return None

        # Remove day names if present
        date_str = re.sub(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s*', '', date_str, flags=re.I)

        # Try to extract month and day
        match = re.search(r'([A-Za-z]{3,9})\s+(\d{1,2})', date_str.strip())
        if not match:
            return None

        month_str = match.group(1)[:3].lower()
        day = int(match.group(2))
        month = MONTH_MAP.get(month_str)

        if not month:
            return None

        year = datetime.now().year
        try:
            date_obj = datetime(year, month, day)
            # If date is in the past, try next year
            if date_obj < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                date_obj = datetime(year + 1, month, day)
            day_name = DAY_NAMES[date_obj.weekday()]
            month_abbrev = month_str.capitalize()
            return f"{day_name}, {month_abbrev} {day}"
        except ValueError:
            return None

    def parse_time(self, text: str) -> Optional[str]:
        """Extract time from text. Format: '8:00 PM'."""
        if not text:
            return None

        match = re.search(r'(\d{1,2}:\d{2})\s*(AM|PM|am|pm)', text)
        if match:
            time_part = match.group(1)
            ampm = match.group(2).upper()
            return f"{time_part} {ampm}"
        return None

    def parse_seatengine_date(self, text: str) -> tuple:
        """
        Parse SeatEngine date format like 'FRI JAN 16 2026, 8:00 PM' or just '8:00 PM'.
        Returns (event_date, show_time) tuple.
        """
        if not text:
            return None, None

        # Clean up the text
        text = " ".join(text.split())

        # Pattern for full date: "FRI JAN 16 2026, 8:00 PM"
        full_match = re.search(
            r'(MON|TUE|WED|THU|FRI|SAT|SUN)\s+([A-Z]{3})\s+(\d{1,2})\s+\d{4},?\s*(\d{1,2}:\d{2}\s*(?:AM|PM))',
            text, re.I
        )
        if full_match:
            day_abbrev = full_match.group(1).upper()
            month_abbrev = full_match.group(2).capitalize()
            day_num = full_match.group(3)
            time_str = full_match.group(4).upper()

            # Convert day abbreviation to full name
            day_map = {'MON': 'Monday', 'TUE': 'Tuesday', 'WED': 'Wednesday',
                       'THU': 'Thursday', 'FRI': 'Friday', 'SAT': 'Saturday', 'SUN': 'Sunday'}
            day_name = day_map.get(day_abbrev, day_abbrev)

            event_date = f"{day_name}, {month_abbrev} {day_num}"
            # Normalize time format
            time_str = re.sub(r'(\d{1,2}:\d{2})\s*(AM|PM)', r'\1 \2', time_str)
            return event_date, time_str

        # Pattern for just time
        time_match = re.search(r'(\d{1,2}:\d{2})\s*(AM|PM)', text, re.I)
        if time_match:
            time_str = f"{time_match.group(1)} {time_match.group(2).upper()}"
            return None, time_str

        return None, None

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape The Velveeta Room shows from SeatEngine."""
        await page.goto(self.seatengine_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Scroll to load all events
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)

        images = []

        # Get all show links and extract data
        links = await page.query_selector_all('a[href*="/shows/"]')
        print(f"    Found {len(links)} show links")

        for link in links:
            try:
                href = await link.get_attribute("href")
                if not href:
                    continue

                # Get show title from nearest heading
                show_title = await link.evaluate('''el => {
                    let node = el;
                    for (let i = 0; i < 10; i++) {
                        if (!node.parentElement) break;
                        node = node.parentElement;
                        const heading = node.querySelector("h2, h3");
                        if (heading) {
                            return heading.innerText.trim();
                        }
                    }
                    return null;
                }''')

                if not show_title:
                    continue

                # Skip phone number heading
                if 'VELV' in show_title or len(show_title) < 3:
                    continue

                # Get date/time from parent text
                date_text = await link.evaluate('el => el.parentElement ? el.parentElement.innerText.trim() : ""')

                # Parse date and time
                event_date, show_time = self.parse_seatengine_date(date_text)

                # Get image from the section
                img_url = await link.evaluate('''el => {
                    let node = el;
                    for (let i = 0; i < 10; i++) {
                        if (!node.parentElement) break;
                        node = node.parentElement;
                        const img = node.querySelector("img");
                        if (img && img.src && img.src.includes("seatengine")) {
                            return img.src;
                        }
                    }
                    return null;
                }''')

                # Build ticket URL
                if href.startswith("/"):
                    ticket_url = f"https://the-velveeta-room-the-velveeta-room.seatengine.com{href}"
                else:
                    ticket_url = href

                images.append({
                    "url": img_url or "",
                    "event_name": show_title,
                    "event_date": event_date,
                    "show_time": show_time,
                    "ticket_url": ticket_url,
                })

            except Exception as e:
                continue

        # Deduplicate by ticket URL (most reliable unique key)
        seen_urls = set()
        unique_images = []
        for img in images:
            url = img.get("ticket_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_images.append(img)
                if img.get("event_date"):
                    print(f"      + {img['event_name']} | {img['event_date']} @ {img['show_time']}")
                else:
                    print(f"      + {img['event_name']} (recurring) @ {img['show_time']}")

        print(f"    Found {len(unique_images)} unique shows")
        return unique_images
