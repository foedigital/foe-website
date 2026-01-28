"""Scraper for Paramount Theatre / Austin Theatre - comedy shows only."""

import re
from typing import List, Dict, Optional
from playwright.async_api import Page
from .base import BaseScraper
from ..config import VENUES


class ParamountScraper(BaseScraper):
    """
    Scraper for Paramount Theatre (Austin Theatre) comedy shows.

    The site uses Tessitura ticketing with dynamic JavaScript loading.
    Comedy shows are filtered via ?kid=4 parameter.
    Ticket URLs follow pattern: /[production_id] or /[production_id]/[performance_id]
    """

    venue_key = "paramount"

    def __init__(self):
        super().__init__(VENUES[self.venue_key])

    def parse_time(self, text: str) -> Optional[str]:
        """Extract time from text. Format: '7:30 PM' or '8:00 pm'."""
        if not text:
            return None
        match = re.search(r'(\d{1,2}:\d{2})\s*(AM|PM|am|pm)', text)
        if match:
            time_part = match.group(1)
            ampm = match.group(2).upper()
            return f"{time_part} {ampm}"
        return None

    def clean_name(self, name: str) -> str:
        """Clean up event name by removing extra whitespace and trailing punctuation."""
        if not name:
            return ""
        # Split by newlines first and take only the first meaningful part
        lines = [line.strip() for line in name.split('\n') if line.strip() and line.strip() not in [',', '.', '-']]
        if lines:
            name = lines[0]
        # Replace multiple whitespace with single space
        name = " ".join(name.split())
        # Remove trailing commas, periods
        name = name.rstrip(",. ")
        # Remove leading/trailing punctuation
        name = name.strip(",.-: ")
        return name

    async def scrape(self, page: Page) -> List[Dict]:
        """Scrape comedy events from Paramount Theatre."""
        await page.goto(self.events_url, wait_until="networkidle", timeout=60000)

        # Wait longer for dynamic content to load
        await page.wait_for_timeout(8000)

        # Wait for event list to appear
        try:
            await page.wait_for_selector(".tn-prod-list-item", timeout=15000)
        except Exception:
            print("    No events found or page didn't load properly")
            return []

        # Scroll to load all events
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

        images = []

        # Find all event items
        event_elements = await page.query_selector_all(".tn-prod-list-item")
        print(f"    Found {len(event_elements)} event items")

        for event in event_elements:
            try:
                # Get event name - use the h4 heading link which has the main title
                event_name = None
                title_el = await event.query_selector("h4.tn-prod-list-item__property--heading a")
                if title_el:
                    event_name = await title_el.inner_text()
                    if event_name:
                        event_name = self.clean_name(event_name)

                # Fallback to other selectors if h4 didn't work
                if not event_name:
                    title_el = await event.query_selector(".tn-performance-title")
                    if title_el:
                        event_name = await title_el.inner_text()
                        if event_name:
                            event_name = self.clean_name(event_name)

                if not event_name:
                    continue

                # Get event date
                event_date = None
                date_el = await event.query_selector(".tn-prod-list-item__perf-date")
                if date_el:
                    date_text = await date_el.inner_text()
                    if date_text:
                        event_date = date_text.strip()
                        # Clean up multi-line dates
                        event_date = " ".join(event_date.split())

                # Get event time - use the dedicated time element
                show_time = None
                time_el = await event.query_selector(".tn-prod-list-item__perf-time")
                if time_el:
                    time_text = await time_el.inner_text()
                    # Handle format like "7:00PM" (no space)
                    if time_text:
                        time_text = time_text.strip()
                        # Add space before AM/PM if missing
                        time_text = re.sub(r'(\d)(AM|PM)', r'\1 \2', time_text, flags=re.I)
                        show_time = self.parse_time(time_text)

                # If no dedicated time element, try to extract from the full card text
                if not show_time:
                    card_text = await event.inner_text()
                    show_time = self.parse_time(card_text)

                # Get ticket URL
                ticket_url = ""
                link_el = await event.query_selector("a")
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        ticket_url = href
                        if not ticket_url.startswith("http"):
                            ticket_url = f"https://tickets.austintheatre.org{ticket_url}"

                # Get event image
                img_url = ""
                img_el = await event.query_selector("img")
                if img_el:
                    img_url = await img_el.get_attribute("src") or ""

                # Ensure absolute URL for image
                if img_url and img_url.startswith("/"):
                    img_url = f"https://tickets.austintheatre.org{img_url}"

                images.append({
                    "url": img_url,
                    "event_name": event_name,
                    "event_date": event_date,
                    "show_time": show_time,
                    "ticket_url": ticket_url,
                })
                print(f"      + {event_name} | {event_date} @ {show_time or 'NO TIME'}")

            except Exception as e:
                print(f"    Error processing event: {e}")
                continue

        # Deduplicate by event name + date
        seen_keys = set()
        unique_images = []
        for img in images:
            name = img.get("event_name") or ""
            date = img.get("event_date") or ""
            key = f"{name.lower()}|{date}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_images.append(img)

        print(f"    Found {len(unique_images)} unique comedy shows")
        return unique_images
