import re
import json
from datetime import datetime
from typing import List, Dict, Optional
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class RozcosScraper(BaseScraper):
    """Scraper for Rozco's Comedy - SimpleTix ticketing."""

    venue_key = "rozcos"
    simpletix_url = "https://rozcoscomedyclub.simpletix.com/"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_listing_datetime(self, text: str) -> tuple:
        """
        Parse date/time from SimpleTix listing page format (already local time).
        Input:  '1/30/2026 7:00 PM - 8:30 PM'
        Output: (datetime_obj, 'Friday, Jan 30', '7:00 PM')
        Returns a 3-tuple: (date_obj, date_display, time_display)
        """
        if not text:
            return None, None, None

        # Normalize whitespace: replace narrow no-break space (\u202f) and
        # other unicode spaces with regular spaces
        clean = re.sub(r'[\u00a0\u202f\u2009\u2007\u200a]', ' ', text.strip())

        # Match "M/D/YYYY H:MM AM/PM"
        match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}:\d{2}\s*[APap][Mm])', clean)
        if not match:
            return None, None, None

        month = int(match.group(1))
        day = int(match.group(2))
        year = int(match.group(3))
        time_str = match.group(4).strip().upper()
        # Normalize any remaining weird spaces in time
        time_str = re.sub(r'\s+', ' ', time_str)

        try:
            date_obj = datetime(year, month, day)
            day_name = DAY_NAMES[date_obj.weekday()]
            month_abbrev = date_obj.strftime('%b')
            date_display = f"{day_name}, {month_abbrev} {day}"
            return date_obj, date_display, time_str
        except ValueError:
            return None, None, None

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape Rozco's Comedy shows from SimpleTix listing page."""
        print(f"    Loading SimpleTix listing: {self.simpletix_url}")
        await page.goto(self.simpletix_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Scroll to load all events
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Parse event data directly from listing page HTML (local times, no UTC issues)
        event_links = await page.query_selector_all('a[href*="simpletix.com/e/"]')
        print(f"    Found {len(event_links)} event links on listing page")

        # Collect event info from listing page
        events = []
        skipped_past = 0
        seen_urls = set()
        for link in event_links:
            href = await link.get_attribute("href")
            if not href or href in seen_urls:
                continue
            if not href.startswith("http"):
                href = f"https://www.simpletix.com{href}"
            seen_urls.add(href)

            # Skip events marked as "Event is Over"
            full_text = await link.inner_text()
            full_clean = re.sub(r'[\u00a0\u202f]', ' ', full_text).lower()
            if 'event is over' in full_clean or 'past event' in full_clean:
                skipped_past += 1
                continue

            # Get event name from <h4>
            h4 = await link.query_selector('h4')
            event_name = None
            if h4:
                event_name = (await h4.inner_text()).strip()

            # Get date/time from <li> inside <ul>
            date_obj = None
            event_date = None
            show_time = None
            li = await link.query_selector('ul li')
            if li:
                li_text = (await li.inner_text()).strip()
                date_obj, event_date, show_time = self.parse_listing_datetime(li_text)

            # Skip events before today
            if date_obj and date_obj < today:
                skipped_past += 1
                continue

            if event_name:
                # Normalize unicode spaces and strip date prefixes like "1/30 "
                event_name = re.sub(r'[\u00a0\u202f\u2009\u2007\u200a]', ' ', event_name)
                event_name = re.sub(r'^\d{1,2}/\d{1,2}\s+', '', event_name).strip()

            events.append({
                "ticket_url": href,
                "event_name": event_name,
                "event_date": event_date,
                "show_time": show_time,
            })

        print(f"    Parsed {len(events)} upcoming events (skipped {skipped_past} past)")

        # Visit each event page to get poster image
        images = []
        for evt in events:
            img_url = await self._fetch_event_image(page, evt["ticket_url"])

            if not evt["event_name"]:
                continue

            images.append({
                "url": img_url or "",
                "event_name": evt["event_name"],
                "event_date": evt["event_date"],
                "show_time": evt["show_time"],
                "ticket_url": evt["ticket_url"],
            })
            print(f"      + {evt['event_name']} | {evt['event_date'] or 'NO DATE'} @ {evt['show_time'] or 'NO TIME'}")

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

    async def _fetch_event_image(self, page: Page, ticket_url: str) -> Optional[str]:
        """Visit a SimpleTix event page and extract the poster image URL."""
        try:
            await page.goto(ticket_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Try JSON-LD image field
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                try:
                    content = await script.inner_text()
                    data = json.loads(content)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get('@type') == 'Event':
                            img = item.get('image', '')
                            if isinstance(img, list):
                                img = img[0] if img else ''
                            if img:
                                return img
                except (json.JSONDecodeError, Exception):
                    continue

            # Fallback: CDN img tag
            img_el = await page.query_selector('img[src*="cdn.simpletix.com"]')
            if img_el:
                return await img_el.get_attribute('src')

            # Fallback: og:image
            og_img = await page.query_selector('meta[property="og:image"]')
            if og_img:
                return await og_img.get_attribute('content')

            return None
        except Exception as e:
            print(f"      Error fetching image from {ticket_url}: {e}")
            return None
