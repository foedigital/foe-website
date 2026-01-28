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

        # Switch to calendar view (month view) using JavaScript
        await page.evaluate('''
            () => {
                const monthOption = document.querySelector(".events-dropwdown-option[data-id='month']");
                if (monthOption) {
                    monthOption.style.display = 'block';
                    monthOption.click();
                }
            }
        ''')
        await page.wait_for_timeout(3000)

        images = []

        # Navigate through multiple weeks to get more events
        weeks_to_scrape = 4  # Scrape current + 3 more weeks
        for week_num in range(weeks_to_scrape):
            # Get current month/year from calendar header
            current_month = None
            header = await page.query_selector('.events-calendar-nav-header, .events-calendar-header-label')
            if header:
                header_text = await header.inner_text()
                month_year_match = re.match(r'([A-Za-z]+)\s+(\d{4})', header_text)
                if month_year_match:
                    current_month = month_year_match.group(1)[:3]

            # Scrape calendar view - get days with events
            calendar_days = await page.query_selector_all('.events-calendar-day.has-events')
            if week_num == 0:
                print(f"    Found {len(calendar_days)} days with events in calendar view")

            for day_el in calendar_days:
                try:
                    # Get the date from the day label
                    date_label = await day_el.query_selector('.events-calendar-day-label')
                    date_num = await date_label.inner_text() if date_label else None

                    # Get events in this day
                    event_details = await day_el.query_selector_all('.events-event-detail')

                    for event in event_details:
                        try:
                            # Get event name
                            title_el = await event.query_selector('.events-event-detail-title')
                            event_name = await title_el.inner_text() if title_el else None
                            if not event_name:
                                continue
                            event_name = event_name.strip()

                            # Get time
                            time_el = await event.query_selector('.events-event-detail-time-show-time')
                            show_time = None
                            if time_el:
                                time_text = await time_el.inner_text()
                                show_time = self.parse_time(time_text)

                            # Get ticket URL from ShowClix link
                            ticket_link = await event.query_selector('a[href*="showclix"]')
                            ticket_url = await ticket_link.get_attribute('href') if ticket_link else None
                            if not ticket_url:
                                # Fall back to event page link
                                event_link = await event.query_selector('a[href*="/events/"]')
                                if event_link:
                                    href = await event_link.get_attribute('href')
                                    ticket_url = f"https://www.creekandcave.com{href}" if href.startswith('/') else href

                            # Get image
                            img_el = await event.query_selector('.events-event-detail-image-img')
                            img_url = None
                            if img_el:
                                img_url = await img_el.get_attribute('src')
                                if img_url and not self.is_valid_image_url(img_url):
                                    img_url = None

                            # Parse the full date
                            event_date = None
                            if date_num and current_month:
                                event_date = self.parse_date_with_day(f"{current_month} {date_num}")

                            if not ticket_url:
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

                            print(f"      + {event_name} | {event_date} @ {show_time}")

                        except Exception as e:
                            continue

                except Exception as e:
                    continue

            # Navigate to next week (click next button)
            if week_num < weeks_to_scrape - 1:
                try:
                    next_btn = await page.query_selector('[data-events-nav-next], .events-nav-arrow.next')
                    if next_btn:
                        await next_btn.click()
                        await page.wait_for_timeout(2000)
                except Exception:
                    pass

        # If calendar view didn't work, fall back to list view
        if not images:
            print("    Calendar view failed, falling back to list view")
            # Reload page for list view
            await page.goto(self.events_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(PAGE_LOAD_WAIT)

        # Process each day container (list view) - only if calendar view didn't get events
        day_containers = await page.query_selector_all('.events-list-day') if not images else []
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
