"""Scraper for Secret Level Comedy - Eventbrite organizer page."""

import json
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import unquote
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES

# Windows uses %#I for no-leading-zero hour; Unix uses %-I
_TIME_FMT = "%#I:%M %p" if os.name == "nt" else "%-I:%M %p"


class SecretLevelScraper(BaseScraper):
    """
    Scraper for Secret Level Productions on Eventbrite.

    Secret Level posts recurring series events (one listing covering multiple dates).
    This scraper:
    1. Loads the organizer page to find event links
    2. Visits each event page and extracts __NEXT_DATA__ JSON (context.basicInfo)
    3. For series events, calls /api/v3/series/{id}/events/ to get child dates
    4. Emits a separate show entry per upcoming date
    """

    venue_key = "secret_level"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape Secret Level events from Eventbrite organizer page."""
        await page.goto(self.events_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Find all event links on the organizer page
        event_urls = await self._get_event_urls(page)
        print(f"    Found {len(event_urls)} event links on organizer page")

        if not event_urls:
            print("    No event links found, trying fallback...")
            event_urls = await self._get_event_urls_fallback(page)
            print(f"    Fallback found {len(event_urls)} event links")

        all_shows = []
        for event_url in event_urls:
            shows = await self._scrape_event_page(page, event_url)
            all_shows.extend(shows)

        # Deduplicate by (name + date + time)
        seen = set()
        unique = []
        for show in all_shows:
            key = (
                (show.get("event_name") or "").lower(),
                show.get("event_date") or "",
                show.get("show_time") or "",
            )
            if key not in seen:
                seen.add(key)
                unique.append(show)

        print(f"    Total: {len(unique)} unique show dates")
        return unique

    async def _get_event_urls(self, page: Page) -> List[str]:
        """Extract event page URLs from the organizer page."""
        links = await page.query_selector_all('a[href*="/e/"]')
        urls = set()
        for link in links:
            href = await link.get_attribute("href")
            if href and "/e/" in href:
                if href.startswith("/"):
                    href = "https://www.eventbrite.com" + href
                base_url = href.split("?")[0]
                urls.add(base_url)
        return list(urls)

    async def _get_event_urls_fallback(self, page: Page) -> List[str]:
        """Fallback: find event links from any anchor tags."""
        all_links = await page.query_selector_all("a")
        urls = set()
        for link in all_links:
            href = await link.get_attribute("href")
            if href and "eventbrite.com/e/" in href:
                base_url = href.split("?")[0]
                urls.add(base_url)
        return list(urls)

    async def _scrape_event_page(self, page: Page, event_url: str) -> List[Dict]:
        """Scrape a single Eventbrite event page for show data."""
        print(f"    Visiting: {event_url}")
        try:
            await page.goto(event_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"      Error loading page: {e}")
            return []

        # Extract __NEXT_DATA__ (Eventbrite's data is under context.basicInfo)
        basic_info, gallery = await self._extract_next_data(page)
        if not basic_info:
            print("      No usable data found, trying JSON-LD fallback...")
            return await self._parse_json_ld(page, event_url)

        event_name = basic_info.get("name", "").strip()
        if not event_name:
            print("      No event name found")
            return []

        # Get image from gallery
        image_url = self._get_gallery_image(gallery)

        is_series = basic_info.get("isSeries", False)
        series_id = basic_info.get("seriesId") or basic_info.get("id")

        if is_series and series_id:
            # Use the v3 API to get all child events in the series
            return await self._fetch_series_events(page, series_id, image_url)
        else:
            # Single event - extract date from basicInfo
            return self._parse_single_event(basic_info, image_url, event_url)

    async def _extract_next_data(self, page: Page) -> tuple:
        """Extract basicInfo and gallery from __NEXT_DATA__."""
        try:
            script_el = await page.query_selector('script#__NEXT_DATA__')
            if not script_el:
                return None, None

            raw = await script_el.inner_text()
            data = json.loads(raw)
            context = data.get("props", {}).get("pageProps", {}).get("context", {})
            return context.get("basicInfo", {}), context.get("gallery", {})
        except Exception as e:
            print(f"      Error extracting __NEXT_DATA__: {e}")
            return None, None

    def _get_gallery_image(self, gallery: dict) -> str:
        """Get the first image URL from the gallery data."""
        if not gallery:
            return ""
        images = gallery.get("images", [])
        if images:
            url = images[0].get("url", "")
            return self._unwrap_eventbrite_image(url)
        return ""

    @staticmethod
    def _unwrap_eventbrite_image(url: str) -> str:
        """Unwrap Eventbrite proxy image URLs to direct CDN URLs.

        Eventbrite wraps images like:
          img.evbuc.com/https%3A%2F%2Fcdn.evbuc.com%2F...?crop=...
        The proxy returns 403 for direct downloads, but the inner
        cdn.evbuc.com URL is freely accessible.
        """
        if not url or "img.evbuc.com/" not in url:
            return url
        # Extract the encoded URL after img.evbuc.com/
        after_host = url.split("img.evbuc.com/", 1)[1]
        # Strip query params (crop, quality, etc.)
        encoded_url = after_host.split("?")[0]
        return unquote(encoded_url)

    async def _fetch_series_events(
        self, page: Page, series_id: str, image_url: str
    ) -> List[Dict]:
        """Fetch child events for a recurring series via the Eventbrite v3 API."""
        now = datetime.now(timezone.utc)
        shows = []

        try:
            api_url = f"/api/v3/series/{series_id}/events/?expand=start,end&page_size=50"
            result = await page.evaluate(
                f'fetch("{api_url}").then(r => r.json()).catch(e => ({{error: e.message}}))'
            )

            if "error" in result:
                print(f"      Series API error: {result['error']}")
                return []

            events = result.get("events", [])
            print(f"      Series API returned {len(events)} child events")

            for evt in events:
                status = evt.get("status", "")
                if status != "live":
                    continue

                name = evt.get("name", {}).get("text", "").strip()
                if not name:
                    continue

                start = evt.get("start", {})
                local_str = start.get("local", "")
                dt = self._parse_datetime(local_str) if local_str else None
                if not dt:
                    continue

                # Only include future dates
                if dt < now.replace(tzinfo=None):
                    continue

                child_url = evt.get("url", "")

                shows.append({
                    "url": image_url,
                    "event_name": name,
                    "event_date": dt.strftime("%A, %b %d"),
                    "show_time": dt.strftime(_TIME_FMT),
                    "ticket_url": child_url or f"https://www.eventbrite.com/e/{evt.get('id', '')}",
                })
                print(f"        + {name} | {dt.strftime('%A, %b %d')} @ {dt.strftime(_TIME_FMT)}")

        except Exception as e:
            print(f"      Error fetching series events: {e}")

        return shows

    def _parse_single_event(
        self, basic_info: dict, image_url: str, event_url: str
    ) -> List[Dict]:
        """Parse a single (non-series) event from basicInfo."""
        now = datetime.now(timezone.utc)
        name = basic_info.get("name", "").strip()

        start = basic_info.get("startDate", {})
        local_str = start.get("local", "") if isinstance(start, dict) else ""
        dt = self._parse_datetime(local_str) if local_str else None

        if not dt or dt < now.replace(tzinfo=None):
            return []

        print(f"      Single event: {name} | {dt.strftime('%A, %b %d')} @ {dt.strftime(_TIME_FMT)}")
        return [{
            "url": image_url,
            "event_name": name,
            "event_date": dt.strftime("%A, %b %d"),
            "show_time": dt.strftime(_TIME_FMT),
            "ticket_url": event_url,
        }]

    def _parse_datetime(self, s: str) -> Optional[datetime]:
        """Parse various datetime string formats from Eventbrite."""
        if not s:
            return None
        # Strip timezone offset for naive parsing
        clean = re.sub(r'[+-]\d{2}(:\d{2})?$', '', s.rstrip("Z"))
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"]:
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                continue
        return None

    async def _parse_json_ld(self, page: Page, event_url: str) -> List[Dict]:
        """Fallback: extract event data from JSON-LD structured data."""
        try:
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                raw = await script.inner_text()
                data = json.loads(raw)

                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") != "Event":
                        continue

                    name = item.get("name", "").strip()
                    if not name:
                        continue

                    image_url = ""
                    img = item.get("image")
                    if isinstance(img, str):
                        image_url = img
                    elif isinstance(img, list) and img:
                        image_url = img[0] if isinstance(img[0], str) else img[0].get("url", "")

                    start = item.get("startDate", "")
                    dt = self._parse_datetime(start) if start else None
                    if dt and dt > datetime.now():
                        return [{
                            "url": image_url,
                            "event_name": name,
                            "event_date": dt.strftime("%A, %b %d"),
                            "show_time": dt.strftime(_TIME_FMT),
                            "ticket_url": event_url,
                        }]

        except Exception as e:
            print(f"      JSON-LD parse error: {e}")
        return []
