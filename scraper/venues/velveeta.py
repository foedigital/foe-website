import re
import json
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


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
VALID_DAYS = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}

WIX_MEDIA_BASE = "https://static.wixstatic.com/media/"


class VelveetaScraper(BaseScraper):
    """Scraper for The Velveeta Room — Wix website with high-quality posters."""

    venue_key = "velveeta"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_day_and_date(self, day_text: str, date_text: str) -> Optional[str]:
        """
        Combine day name and date into 'Day, Mon DD' format.
        day_text: 'Friday' or 'Sunday'
        date_text: 'Jan 30' or 'Feb 14'
        """
        if not day_text or not date_text:
            return None

        day_clean = day_text.strip().capitalize()
        date_clean = date_text.strip()

        # Validate day name
        if day_clean.lower() not in VALID_DAYS:
            return None

        # Parse month and day from date_text (e.g., "Jan 30", "Feb 14")
        match = re.match(r'([A-Za-z]+)\s+(\d{1,2})', date_clean)
        if match:
            month_abbrev = match.group(1)[:3].capitalize()
            day_num = match.group(2)
            return f"{day_clean}, {month_abbrev} {day_num}"

        return None

    def normalize_time(self, time_text: str) -> Optional[str]:
        """
        Normalize time to 'H:MM PM' format.
        '8 PM' -> '8:00 PM', '10:30 PM' -> '10:30 PM', '8 & 10 PM' -> '8:00 PM'
        """
        if not time_text:
            return None

        text = time_text.strip().upper()

        # Handle dual times: "8 & 10 PM" — take the first time
        # Search for the first occurrence of a time pattern
        match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', text)
        if match:
            return f"{match.group(1)}:{match.group(2)} {match.group(3)}"

        # No minutes: "8 PM", "8 & 10 PM" — grab first number before AM/PM
        match = re.search(r'(\d{1,2})\s*(?:&\s*\d{1,2}\s*)?(AM|PM)', text)
        if match:
            return f"{match.group(1)}:00 {match.group(2)}"

        return None

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape The Velveeta Room shows from the Wix website."""
        print(f"    Loading Wix website: {self.events_url}")
        await page.goto(self.events_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)

        # Scroll to load all repeater items
        for _ in range(8):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1500)

        # Scroll back to top to ensure all items are rendered
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(2000)

        # Find all repeater list items
        items = await page.query_selector_all('[role="listitem"]')
        print(f"    Found {len(items)} repeater items")

        images = []
        for item in items:
            try:
                show = await self._extract_show_from_item(item)
                if show:
                    images.append(show)
                    print(f"      + {show['event_name']} | {show.get('event_date', 'NO DATE')} @ {show.get('show_time', 'NO TIME')}")
            except Exception as e:
                print(f"      Error processing repeater item: {e}")
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

    def _extract_name_from_alt(self, alt: str) -> Optional[str]:
        """
        Extract show name from img alt text.
        Pattern: 'Poster for {NAME} at [The/the] Velveeta Room...'
        """
        if not alt:
            return None
        match = re.match(r'Poster for (.+?) at [Tt]he Velveeta Room', alt)
        if match:
            return match.group(1).strip()
        return None

    def _extract_name_from_slug(self, slug: str) -> Optional[str]:
        """
        Extract show name from /velv/ URL slug.
        e.g. 'arielle-isaac-norman' -> 'Arielle Isaac Norman'
        """
        if not slug:
            return None
        # Strip date suffixes: jan302026, feb2026, jan30, feb62026, etc.
        clean = re.sub(r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{0,2}\d{4}$', '', slug)
        clean = re.sub(r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\d{1,2}$', '', clean)
        # Strip trailing numeric/alpha junk (e.g., cocktails1bbb)
        clean = re.sub(r'\d+[a-z]*$', '', clean)
        clean = clean.strip('-')
        if not clean:
            return None
        # Convert hyphens to spaces and title-case
        return clean.replace('-', ' ').title()

    async def _extract_show_from_item(self, item) -> Optional[Dict]:
        """Extract show data from a single Wix repeater listitem."""
        # --- Image ---
        img_url = None
        alt_text = ""

        # Try wow-image with data-image-info (contains raw image URI)
        wow_img = await item.query_selector('wow-image')
        if wow_img:
            data_info = await wow_img.get_attribute('data-image-info')
            if data_info:
                try:
                    info = json.loads(data_info)
                    image_data = info.get('imageData', info)
                    uri = image_data.get('uri', '')
                    if uri:
                        img_url = f"{WIX_MEDIA_BASE}{uri}"
                except (json.JSONDecodeError, Exception):
                    pass

        # Get alt text from the rendered img tag (more reliable than data-image-info)
        img_el = await item.query_selector('img[src*="wixstatic"]')
        if img_el:
            alt_text = (await img_el.get_attribute('alt') or '').strip()
            # Fallback image URL from src
            if not img_url:
                src = await img_el.get_attribute('src')
                if src:
                    uri_match = re.search(r'/media/([^/]+)', src)
                    if uri_match:
                        img_url = f"{WIX_MEDIA_BASE}{uri_match.group(1)}"
                    else:
                        img_url = src

        # --- Show name ---
        event_name = self._extract_name_from_alt(alt_text)

        # Fallback: extract from MORE INFO link slug
        if not event_name:
            more_info = await item.query_selector('a[href*="/velv/"]')
            if more_info:
                href = await more_info.get_attribute('href') or ''
                slug = href.rstrip('/').split('/')[-1]
                event_name = self._extract_name_from_slug(slug)

        # --- Day / Date / Time from h2 elements ---
        day_text = None
        date_text = None
        time_text = None

        h2_elements = await item.query_selector_all('h2')
        for h2 in h2_elements:
            text = (await h2.inner_text()).strip()
            if not text:
                continue

            # Classify the h2 content
            if text.lower() in VALID_DAYS:
                day_text = text
            elif re.match(r'[A-Za-z]+\s+\d{1,2}$', text):
                # "Jan 30", "Feb 14"
                date_text = text
            elif re.search(r'\d{1,2}(:\d{2})?\s*(AM|PM|am|pm)', text):
                # "8 PM", "10:30 PM", "8 & 10 PM"
                time_text = text

        event_date = self.parse_day_and_date(day_text, date_text)
        # For dual times like "8 & 10 PM", take the first time
        show_time = self.normalize_time(time_text)

        # --- Ticket URL ---
        ticket_url = None
        ticket_link = await item.query_selector('a[href*="seatengine"]')
        if ticket_link:
            ticket_url = await ticket_link.get_attribute('href')

        if not ticket_url:
            more_info = await item.query_selector('a[href*="/velv/"]')
            if more_info:
                href = await more_info.get_attribute('href')
                if href:
                    if href.startswith('/'):
                        href = f"https://www.thevelveetaroom.com{href}"
                    ticket_url = href

        if not event_name and not img_url:
            return None

        return {
            "url": img_url or "",
            "event_name": event_name or "Unknown Show",
            "event_date": event_date,
            "show_time": show_time,
            "ticket_url": ticket_url or "https://www.thevelveetaroom.com",
        }
