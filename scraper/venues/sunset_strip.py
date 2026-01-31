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
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
}

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class SunsetStripScraper(BaseScraper):
    """Scraper for Sunset Strip Comedy - SquadUP events."""

    venue_key = "sunset_strip"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse date formats:
        - 'Sunday, Jan 11, 2026' -> 'Sunday, Jan 11'
        - 'Jan 15' -> 'Wednesday, Jan 15'
        - 'January 15' -> 'Wednesday, Jan 15'
        """
        if not date_str:
            return None

        # Clean up the date string
        date_str = date_str.strip()

        # Check if it already has day name (e.g., "Sunday, Jan 11, 2026")
        day_match = re.match(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Za-z]+)\s+(\d{1,2})', date_str, re.I)
        if day_match:
            day_name = day_match.group(1).capitalize()
            month_str = day_match.group(2)[:3].capitalize()
            day_num = day_match.group(3)
            return f"{day_name}, {month_str} {day_num}"

        # Try to extract month and day (e.g., "Jan 15")
        match = re.search(r'([A-Za-z]+)\s+(\d{1,2})', date_str)
        if not match:
            return None

        month_str = match.group(1).lower()
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
            month_abbrev = month_str[:3].capitalize()
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

    # SquadUP API endpoint for Sunset Strip events
    SQUADUP_API_URL = "https://www.squadup.com/api/v3/events?user_ids=9086799&page_size=800&additional_attr=sold_out&include=custom_fields"

    @staticmethod
    def _upscale_filepicker_url(url: str, width: int = 1080) -> str:
        """
        Transform a Filepicker CDN URL to request a larger image via their
        server-side convert endpoint.  SquadUP only stores 600px originals;
        this lets Filestack upscale to 1080px *before* JPEG compression,
        avoiding a decode→upscale→re-encode quality loss in our pipeline.
        """
        if not url or 'cdn.filepicker.io/api/file/' not in url:
            return url
        # Append /convert?w=1080 to the handle URL
        return f"{url.rstrip('/')}/convert?w={width}"

    async def _fetch_api_image_map(self, page: Page) -> Dict[str, str]:
        """
        Fetch the SquadUP API via the page context to build a mapping of
        event name -> image URL (upscaled to 1080px via Filestack CDN).
        """
        image_map = {}
        try:
            data = await page.evaluate("""async (url) => {
                const resp = await fetch(url);
                return await resp.json();
            }""", self.SQUADUP_API_URL)

            events = data if isinstance(data, list) else data.get('data', data.get('events', []))
            for evt in events:
                name = evt.get('name', '')
                image = evt.get('image') or {}
                img_url = image.get('default_url', '')
                if name and img_url:
                    image_map[name] = self._upscale_filepicker_url(img_url)
            print(f"    SquadUP API: found {len(image_map)} event posters (1080px upscale)")
        except Exception as e:
            print(f"    SquadUP API failed, falling back to HTML scraping: {e}")
        return image_map

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape Sunset Strip Comedy shows from SquadUP."""
        await page.goto(self.events_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Fetch full poster URLs from the SquadUP API
        api_image_map = await self._fetch_api_image_map(page)

        # Scroll to load all events
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1500)

        images = []

        # Find all event boxes
        event_boxes = await page.query_selector_all('.squadup-checkout-event-box')
        print(f"    Found {len(event_boxes)} event boxes")

        for box in event_boxes:
            try:
                # Get event name
                event_name = None
                name_el = await box.query_selector('.event-name')
                if name_el:
                    event_name = await name_el.inner_text()
                    event_name = event_name.strip() if event_name else None

                if not event_name:
                    continue

                # Get date and time from .start-at element
                # Format: <span>Sunday, Jan 11, 2026</span>,&nbsp;<span>7:00 PM</span>
                event_date = None
                show_time = None
                start_el = await box.query_selector('.start-at')
                if start_el:
                    # Get both spans
                    spans = await start_el.query_selector_all('span')
                    if len(spans) >= 2:
                        date_text = await spans[0].inner_text()
                        time_text = await spans[1].inner_text()
                        event_date = self.parse_date(date_text)
                        show_time = self.parse_time(time_text)
                    elif len(spans) == 1:
                        # Fallback: try to parse the full text
                        full_text = await start_el.inner_text()
                        event_date = self.parse_date(full_text)
                        show_time = self.parse_time(full_text)

                # Get image — prefer the full poster from the API
                img_url = api_image_map.get(event_name)
                if not img_url:
                    # Fallback: scrape thumbnail from HTML widget
                    img_el = await box.query_selector('.squadup-checkout-flyer-image')
                    if img_el:
                        style = await img_el.get_attribute('style') or ''
                        match = re.search(r"url\(['\"]?([^'\"]+)['\"]?\)", style)
                        if match:
                            img_url = match.group(1)
                        else:
                            img_url = await img_el.get_attribute('src')

                # Get ticket URL from data-squadup-event-id
                ticket_url = None
                event_id = await box.get_attribute('data-squadup-event-id')
                if event_id:
                    ticket_url = f"https://www.sunsetstripatx.com/?event-id={event_id}"
                else:
                    # Fallback: generate unique URL
                    unique_key = f"{event_name}|{event_date}|{show_time}"
                    url_hash = hashlib.md5(unique_key.encode()).hexdigest()[:8]
                    ticket_url = f"https://www.sunsetstripatx.com/events#{url_hash}"

                images.append({
                    "url": img_url or "",
                    "event_name": event_name,
                    "event_date": event_date,
                    "show_time": show_time,
                    "ticket_url": ticket_url,
                })
                print(f"      + {event_name} | {event_date or 'NO DATE'} @ {show_time or 'NO TIME'}")

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

        print(f"    Found {len(unique_images)} unique shows")
        return unique_images
