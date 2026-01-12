import re
import hashlib
import urllib.parse
from typing import List, Dict
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


class MothershipScraper(BaseScraper):
    """Scraper for Comedy Mothership - Next.js site with event cards."""

    venue_key = "mothership"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_card_text(self, text: str):
        """
        Parse card text to extract date, name, and time.

        Card text format:
        Line 1: "SUNDAY, JAN 11" (day + date)
        Line 2: "WHITNEY CUMMINGS" (event name)
        Line 3: "8:00 PM - 10:00 PM" (time range)
        """
        if not text:
            return None, None, None

        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            return None, None, None

        # Line 1: Date (e.g., "SUNDAY, JAN 11")
        event_date = None
        date_line = lines[0]
        # Match pattern: DAY, MON DD
        date_match = re.match(r'^(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+([A-Z]{3})\s+(\d{1,2})$', date_line, re.I)
        if date_match:
            day_name = date_match.group(1).capitalize()
            month = date_match.group(2).capitalize()
            day_num = date_match.group(3)
            event_date = f"{day_name}, {month} {day_num}"

        # Line 2: Event name
        event_name = lines[1] if len(lines) > 1 else None

        # Line 3: Time (e.g., "8:00 PM - 10:00 PM") - extract start time
        show_time = None
        if len(lines) > 2:
            time_line = lines[2]
            time_match = re.match(r'^(\d{1,2}:\d{2}\s*(?:AM|PM))', time_line, re.I)
            if time_match:
                show_time = time_match.group(1).upper()

        return event_date, event_name, show_time

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape Comedy Mothership shows with date, name, and time."""
        await page.goto(self.events_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)

        # Scroll to load more content
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

        images = []

        # Find all event cards
        cards = await page.query_selector_all("[class*='EventCard_eventCard']")
        print(f"    Found {len(cards)} event cards")

        for card in cards:
            try:
                # Get full card text to parse
                card_text = await card.inner_text()
                event_date, event_name, show_time = self.parse_card_text(card_text)

                # Skip if missing essential data
                if not event_name:
                    continue

                # Find the image in this card
                img_url = None
                img = await card.query_selector("img")
                if img:
                    src = await img.get_attribute("src")
                    if src and "default-event" not in src:
                        # Decode Next.js image URL
                        if "/_next/image?url=" in src:
                            parsed = urllib.parse.urlparse(src)
                            query = urllib.parse.parse_qs(parsed.query)
                            if "url" in query:
                                src = urllib.parse.unquote(query["url"][0])
                        if self.is_valid_image_url(src):
                            img_url = src

                # Skip cards without images
                if not img_url:
                    continue

                # Create unique ticket URL using event details
                unique_key = f"{event_name}|{event_date}|{show_time}"
                url_hash = hashlib.md5(unique_key.encode()).hexdigest()[:8]
                ticket_url = f"https://comedymothership.com/shows#{url_hash}"

                images.append({
                    "url": img_url,
                    "event_name": event_name,
                    "event_date": event_date,
                    "show_time": show_time,
                    "ticket_url": ticket_url,
                })
                print(f"      + {event_name} | {event_date} @ {show_time}")

            except Exception as e:
                print(f"    Error processing card: {e}")
                continue

        # Deduplicate by name + date + time
        seen_keys = set()
        unique_images = []
        for img in images:
            key = f"{(img.get('event_name') or '').lower()}|{img.get('event_date')}|{img.get('show_time')}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_images.append(img)

        print(f"    Found {len(unique_images)} unique shows")
        return unique_images
