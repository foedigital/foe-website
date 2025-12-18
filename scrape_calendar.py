"""
ATX Comedy Calendar Scraper
Extracts accurate show dates, days, and times from venue calendars.
Uses Playwright to handle dynamically loaded content.
"""

import sqlite3
import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright

DB_PATH = 'comedy_images.db'

# Venue calendar configurations
VENUE_CALENDARS = {
    'creek_and_cave': {
        'name': 'Creek and the Cave',
        'calendar_url': 'https://www.creekandcave.com/calendar',
        'scraper': 'creek_calendar'
    },
    'rozcos': {
        'name': "Rozco's Comedy",
        'calendar_url': 'https://rozcoscomedyclub.simpletix.com/',
        'scraper': 'simpletix_calendar'
    }
}


def parse_date_string(date_str):
    """Parse various date formats and return (date_obj, day_name, formatted_date)."""
    if not date_str:
        return None, None, None

    # Clean up the string
    date_str = date_str.strip()

    # Try various formats
    formats = [
        '%B %d, %Y',      # December 18, 2024
        '%b %d, %Y',      # Dec 18, 2024
        '%m/%d/%Y',       # 12/18/2024
        '%m/%d/%y',       # 12/18/24
        '%Y-%m-%d',       # 2024-12-18
        '%A, %B %d',      # Wednesday, December 18
        '%a, %b %d',      # Wed, Dec 18
    ]

    for fmt in formats:
        try:
            # Add current year if not present
            test_str = date_str
            if '%Y' not in fmt and '%y' not in fmt:
                test_str = f"{date_str}, {datetime.now().year}"
                fmt = fmt + ', %Y'

            dt = datetime.strptime(test_str, fmt)
            day_name = dt.strftime('%A')  # Full day name
            formatted = dt.strftime('%b %d')  # "Dec 18"
            return dt, day_name, formatted
        except ValueError:
            continue

    return None, None, None


def parse_time_string(time_str):
    """Normalize time string to consistent format."""
    if not time_str:
        return None

    time_str = time_str.strip().upper()

    # Match patterns like "8:00 PM", "8PM", "8:00PM", "20:00"
    match = re.search(r'(\d{1,2}):?(\d{2})?\s*(AM|PM)?', time_str, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = match.group(2) or '00'
        ampm = match.group(3) or ''

        if not ampm:
            # Assume PM for evening shows
            ampm = 'PM' if hour < 12 or hour >= 6 else 'AM'

        return f"{hour}:{minute} {ampm}"

    return time_str


async def scrape_creek_calendar():
    """Scrape Creek and Cave calendar for show dates and times."""
    print("\n" + "="*60)
    print("SCRAPING: Creek and the Cave Calendar")
    print("="*60)

    shows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            print(f"\n  Loading calendar page...")
            await page.goto(VENUE_CALENDARS['creek_and_cave']['calendar_url'],
                          wait_until='networkidle', timeout=60000)

            # Wait for calendar content to load
            await page.wait_for_timeout(3000)

            # Look for show cards/items in the calendar
            # Creek and Cave uses various selectors for shows
            show_selectors = [
                '.shows_card',
                '.event-card',
                '.calendar-event',
                '.show-item',
                '[class*="event"]',
                '[class*="show"]'
            ]

            show_elements = []
            for selector in show_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"  Found {len(elements)} elements with selector: {selector}")
                    show_elements.extend(elements)
                    break

            if not show_elements:
                # Try getting all text content and parsing it
                print("  No show cards found, extracting page content...")
                content = await page.content()

                # Look for embedded calendar data
                # Many sites embed JSON data for calendars
                json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', content)
                if json_match:
                    print("  Found embedded calendar data")

            # Extract show details from each element
            for elem in show_elements:
                try:
                    text = await elem.inner_text()

                    # Try to extract structured data
                    name_elem = await elem.query_selector('h2, h3, h4, .title, .event-title, .show-name')
                    date_elem = await elem.query_selector('.date, .event-date, time, [class*="date"]')
                    time_elem = await elem.query_selector('.time, .event-time, [class*="time"]')

                    show_name = await name_elem.inner_text() if name_elem else ''
                    date_text = await date_elem.inner_text() if date_elem else ''
                    time_text = await time_elem.inner_text() if time_elem else ''

                    if show_name:
                        _, day, formatted_date = parse_date_string(date_text)
                        normalized_time = parse_time_string(time_text)

                        shows.append({
                            'name': show_name.strip(),
                            'date': formatted_date,
                            'day': day,
                            'time': normalized_time,
                            'raw_text': text[:200]
                        })
                        print(f"    {show_name}: {day}, {formatted_date} @ {normalized_time}")

                except Exception as e:
                    print(f"    Error extracting show: {e}")
                    continue

            # If we still don't have shows, let's try a different approach
            # Get all links to event pages
            if not shows:
                print("\n  Trying to extract from event links...")
                event_links = await page.query_selector_all('a[href*="/events/"]')

                seen_urls = set()
                for link in event_links:
                    href = await link.get_attribute('href')
                    if href and href not in seen_urls:
                        seen_urls.add(href)

                        # Get the text near this link
                        parent = await link.query_selector('xpath=..')
                        if parent:
                            text = await parent.inner_text()
                            link_text = await link.inner_text()
                            print(f"    Event: {link_text[:50]}... -> {href}")

                print(f"\n  Found {len(seen_urls)} unique event links")

                # Now let's scrape each event page for detailed info
                for i, url in enumerate(sorted(seen_urls)):
                    full_url = url if url.startswith('http') else f"https://www.creekandcave.com{url}"
                    print(f"  [{i+1}/{len(seen_urls)}] ", end='')
                    show = await scrape_creek_event_page(page, full_url)
                    if show:
                        shows.append(show)

        except Exception as e:
            print(f"  Error: {e}")
        finally:
            await browser.close()

    return shows


async def scrape_creek_event_page(page, url):
    """Scrape a single Creek and Cave event page for date/time info."""
    try:
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(1000)

        show = {
            'name': '',
            'date': '',
            'day': '',
            'time': '',
            'url': url
        }

        # Get show name from h1
        h1 = await page.query_selector('h1')
        if h1:
            show['name'] = (await h1.inner_text()).strip()

        # Get the full page text to search for date/time patterns
        body_text = await page.inner_text('body')

        # Look for date patterns in the text
        date_patterns = [
            r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})',
            r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})',
            r'(\d{1,2}/\d{1,2}/\d{2,4})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, body_text, re.IGNORECASE)
            if match:
                date_str = match.group(0)
                _, day, formatted = parse_date_string(date_str)
                if day:
                    show['day'] = day
                    show['date'] = formatted
                    break

        # Look for time patterns
        time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))', body_text)
        if time_match:
            show['time'] = parse_time_string(time_match.group(1))

        if show['name']:
            print(f"    {show['name']}: {show['day']}, {show['date']} @ {show['time']}")
            return show

        return None

    except Exception as e:
        print(f"    Error scraping {url}: {e}")
        return None


async def scrape_simpletix_calendar():
    """Scrape SimpleTix calendar for Rozco's shows."""
    print("\n" + "="*60)
    print("SCRAPING: Rozco's Comedy Calendar (SimpleTix)")
    print("="*60)

    shows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(VENUE_CALENDARS['rozcos']['calendar_url'],
                          wait_until='networkidle', timeout=60000)

            # SimpleTix shows events with dates in the URL/text
            event_links = await page.query_selector_all('a[href*="simpletix.com/e/"]')

            for link in event_links:
                href = await link.get_attribute('href')
                text = await link.inner_text()

                if href:
                    # Extract date from URL (format: 12-18-show-name)
                    url_match = re.search(r'/(\d{1,2})-(\d{1,2})-([^/]+)', href)
                    if url_match:
                        month, day, slug = url_match.groups()
                        # Determine year (assume current or next year)
                        year = datetime.now().year
                        try:
                            date_obj = datetime(year, int(month), int(day))
                            if date_obj < datetime.now():
                                date_obj = datetime(year + 1, int(month), int(day))

                            show_name = slug.replace('-', ' ').title()
                            # Remove time suffix like "7pm", "9pm"
                            show_name = re.sub(r'\s*\d{1,2}\s*pm\s*$', '', show_name, flags=re.IGNORECASE)

                            shows.append({
                                'name': show_name.strip(),
                                'date': date_obj.strftime('%b %d'),
                                'day': date_obj.strftime('%A'),
                                'time': '',  # Will get from page
                                'url': href
                            })
                        except:
                            pass

            print(f"  Found {len(shows)} dated events")

            # Consolidate by show name, keeping all dates
            by_name = {}
            for show in shows:
                name = show['name'].lower()
                if name not in by_name:
                    by_name[name] = []
                by_name[name].append(show)

            print(f"  Consolidated to {len(by_name)} unique shows")
            for name, instances in by_name.items():
                dates = [s['date'] for s in instances[:3]]
                print(f"    {instances[0]['name']}: {', '.join(dates)}...")

        except Exception as e:
            print(f"  Error: {e}")
        finally:
            await browser.close()

    return shows


def update_database(shows, venue_name):
    """Update database with scraped show data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get venue ID
    cursor.execute("SELECT id FROM venues WHERE name = ?", (venue_name,))
    row = cursor.fetchone()
    if not row:
        print(f"  Venue '{venue_name}' not found")
        conn.close()
        return

    venue_id = row[0]
    updated = 0
    already_updated = set()  # Track which shows we've already updated

    for show in shows:
        if not show.get('name'):
            continue

        # Skip if we've already updated this show (for recurring shows with multiple dates)
        show_key = show['name'].lower()[:20]
        if show_key in already_updated:
            continue

        # Find matching show in database
        cursor.execute("""
            SELECT id, event_name, event_date, show_time
            FROM images
            WHERE venue_id = ? AND LOWER(event_name) LIKE ?
        """, (venue_id, f"%{show['name'].lower()[:15]}%"))

        rows = cursor.fetchall()

        for row in rows:
            img_id, current_name, current_date, current_time = row

            # Only update if we have new data - don't overwrite with empty values
            new_day = show.get('day', '')
            new_date_part = show.get('date', '')
            new_time = show.get('time', '')

            # Build the date string
            if new_day and new_date_part:
                new_date = f"{new_day}, {new_date_part}"
            elif new_day:
                new_date = new_day
            elif new_date_part:
                new_date = new_date_part
            else:
                new_date = current_date  # Keep existing

            # Don't overwrite time with empty value
            if not new_time:
                new_time = current_time

            # Only update if there's actual new data
            if new_date and new_date != current_date:
                cursor.execute("UPDATE images SET event_date = ? WHERE id = ?", (new_date, img_id))
                print(f"  Updated: {current_name}")
                print(f"    Date: {current_date} -> {new_date}")
                updated += 1
                already_updated.add(show_key)

            if new_time and new_time != current_time:
                cursor.execute("UPDATE images SET show_time = ? WHERE id = ?", (new_time, img_id))
                if show_key not in already_updated:
                    print(f"  Updated: {current_name}")
                print(f"    Time: {current_time} -> {new_time}")
                if show_key not in already_updated:
                    updated += 1
                    already_updated.add(show_key)

    conn.commit()
    conn.close()
    print(f"  Total updated: {updated}")


async def main():
    """Main entry point."""
    print("="*60)
    print(f"ATX Comedy Calendar Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Scrape Creek and Cave
    creek_shows = await scrape_creek_calendar()
    if creek_shows:
        update_database(creek_shows, "Creek and the Cave")

    # Scrape Rozco's
    rozco_shows = await scrape_simpletix_calendar()
    if rozco_shows:
        update_database(rozco_shows, "Rozco's Comedy")

    print("\n" + "="*60)
    print("COMPLETE - Run 'python regenerate_shows.py' to update website")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(main())
