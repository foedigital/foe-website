"""
ATX Comedy Show Scraper v2
Accurately extracts show data from ticketing platforms using Playwright and structured data.
Focuses on date/time accuracy by parsing JSON-LD schema and page content.

Key strategy for accuracy:
1. For recurring shows, look for "Every [Day]" patterns in descriptions
2. Use startDate from JSON-LD schema as fallback
3. Extract show name directly from show title
4. Consolidate multiple instances of the same show to their recurring day
"""

import sqlite3
import json
import re
import hashlib
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from collections import defaultdict

# Try to import playwright, provide helpful message if not installed
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)

DB_PATH = 'comedy_images.db'
IMAGES_DIR = Path('images')

# Venue configurations
VENUES = {
    'creek_and_cave': {
        'name': 'Creek and the Cave',
        'website_url': 'https://www.creekandcave.com/',
        'ticketing_url': 'https://www.showclix.com/venue/creekandcave',
        'event_base_url': 'https://www.showclix.com/event/',
        'scraper': 'showclix'
    },
    'rozcos': {
        'name': "Rozco's Comedy",
        'ticketing_url': 'https://rozcoscomedyclub.simpletix.com/',
        'event_base_url': 'https://www.simpletix.com/e/',
        'scraper': 'simpletix'
    },
    'velveeta': {
        'name': 'The Velveeta Room',
        'ticketing_url': 'https://www.thevelveetaroom.com/',
        'event_base_url': 'https://www.thevelveetaroom.com/velv/',
        'scraper': 'velveeta'
    },
    'mothership': {
        'name': 'Comedy Mothership',
        'ticketing_url': 'https://comedymothership.com/shows',
        'event_base_url': 'https://comedymothership.com/shows/',
        'scraper': 'mothership'
    }
}

# Known recurring show patterns - used for validation and name normalization
# Format: partial_name_match -> (day, time)
KNOWN_RECURRING_SHOWS = {
    # Creek and Cave
    'monday gamble': ('Monday', '8:00 PM'),
    'clocked out': ('Monday', '10:00 PM'),
    'new joke monday': ('Monday', '11:00 PM'),
    'gimmick mic': ('Monday', '11:00 PM'),
    'dunk tank': ('Tuesday', '8:00 PM'),
    'optimum noctis': ('Tuesday', '8:00 PM'),
    'hood therapy': ('Tuesday', '10:00 PM'),
    'off the cuff': ('Wednesday', '8:00 PM'),
    'absolute show': ('Wednesday', '8:00 PM'),
    'the forge': ('Wednesday', '10:00 PM'),
    'wild west': ('Wednesday', '10:00 PM'),
    'comedians on the rise': ('Wednesday', '10:00 PM'),
    'bear arms': ('Thursday', '8:00 PM'),
    'gator tales': ('Thursday', '8:00 PM'),
    'unscripted': ('Thursday', '10:00 PM'),
    'word up': ('Thursday', '10:00 PM'),
    'big naturals': ('Friday', '8:00 PM'),
    'roast battle': ('Friday', '11:00 PM'),
    'laughs with the staff': ('Friday', '10:00 PM'),
    'new joke saturday': ('Saturday', '6:00 PM'),
    'creek featured': ('Saturday', '8:00 PM'),
    'main course': ('Saturday', '8:00 PM'),
    'freaky': ('Saturday', '11:00 PM'),
    "writers' room": ('Sunday', '6:00 PM'),
    'writers room': ('Sunday', '6:00 PM'),
    'creek open mic': ('Sunday', '8:00 PM'),
    'banana phone': ('Sunday', '10:00 PM'),
    # Rozco's
    'eastside open mic': ('Wednesday', '9:00 PM'),
    'best of austin': ('Thursday', '7:00 PM'),
    'candlelight': ('Thursday', '9:00 PM'),
    'friday night laughs': ('Friday', None),
    'new faces': ('Saturday', '7:00 PM'),
    'austin all-star': ('Saturday', None),
    'tuesday gigante': ('Tuesday', '8:00 PM'),
    'sweet sunday': ('Sunday', '7:00 PM'),
}

# Day name to abbreviation mapping
DAY_ABBR = {
    'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
    'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
}

def get_day_abbr(day_name):
    """Convert full day name to 3-letter abbreviation."""
    if not day_name:
        return ''
    return DAY_ABBR.get(day_name.lower(), day_name.lower()[:3])

def parse_schema_datetime(dt_str):
    """Parse ISO datetime from JSON-LD schema."""
    if not dt_str:
        return None, None

    try:
        # Handle formats like "2025-12-17T20:00:00-06:00"
        # Remove timezone for simpler parsing
        dt_str = re.sub(r'[+-]\d{2}:\d{2}$', '', dt_str)
        dt = datetime.fromisoformat(dt_str)

        day = dt.strftime('%A')  # Full day name
        time = dt.strftime('%I:%M %p').lstrip('0')  # "8:00 PM"

        return day, time
    except Exception as e:
        print(f"  Error parsing datetime '{dt_str}': {e}")
        return None, None

def extract_day_from_description(text):
    """Extract day of week from event description (e.g., 'Every Tuesday')."""
    if not text:
        return None

    text_lower = text.lower()

    # Look for patterns like "Every Tuesday", "Every Wednesday night"
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        if f'every {day}' in text_lower:
            return day.capitalize()
        if f'{day} night' in text_lower:
            return day.capitalize()
        if f'{day}s' in text_lower:  # "Tuesdays", "Wednesdays"
            return day.capitalize()

    return None


def get_known_show_info(show_name):
    """Look up known recurring show info by name."""
    if not show_name:
        return None, None

    name_lower = show_name.lower()

    for pattern, (day, time) in KNOWN_RECURRING_SHOWS.items():
        if pattern in name_lower:
            return day, time

    return None, None


def normalize_show_name(name):
    """Remove date prefixes from show names (e.g., '12/17 Eastside Open Mic' -> 'Eastside Open Mic')."""
    if not name:
        return name

    # Remove date prefixes like "12/17 ", "1/15 "
    cleaned = re.sub(r'^\d{1,2}/\d{1,2}\s+', '', name)

    # Remove time suffixes like " 7pm", " 9Pm"
    cleaned = re.sub(r'\s+\d{1,2}\s*[AaPp][Mm]\s*$', '', cleaned)

    return cleaned.strip()

def extract_time_from_text(text):
    """Extract time from text (e.g., '8:00 PM', '10pm')."""
    if not text:
        return None

    # Pattern for times like "8:00 PM", "10:30 pm", "8PM"
    patterns = [
        r'(\d{1,2}:\d{2}\s*[AaPp][Mm])',  # 8:00 PM
        r'(\d{1,2}\s*[AaPp][Mm])',         # 8PM, 10 pm
        r'(\d{1,2}:\d{2})\s*(pm|am)',      # 8:00 pm
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            time_str = match.group(0).strip()
            # Normalize format
            time_str = re.sub(r'\s+', ' ', time_str)
            time_str = time_str.upper().replace('PM', ' PM').replace('AM', ' AM')
            time_str = re.sub(r'\s+', ' ', time_str).strip()
            if ':' not in time_str:
                time_str = time_str.replace(' PM', ':00 PM').replace(' AM', ':00 AM')
            return time_str

    return None


class ShowScraper:
    """Base scraper class with common functionality."""

    def __init__(self, browser):
        self.browser = browser
        self.context = None
        self.page = None

    async def setup(self):
        """Create browser context and page."""
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()

    async def cleanup(self):
        """Close browser context."""
        if self.context:
            await self.context.close()

    async def get_json_ld(self, page=None):
        """Extract JSON-LD structured data from page."""
        page = page or self.page
        scripts = await page.query_selector_all('script[type="application/ld+json"]')
        data = []
        for script in scripts:
            try:
                content = await script.inner_text()
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    data.extend(parsed)
                else:
                    data.append(parsed)
            except:
                continue
        return data


class ShowClixScraper(ShowScraper):
    """Scraper for ShowClix (Creek and the Cave)."""

    async def scrape_venue(self, website_url, ticketing_url):
        """Scrape all shows from Creek and Cave website, following links to ShowClix."""
        print(f"\n  Fetching venue calendar: {website_url}calendar...")

        # First, get the calendar page to find all event links
        await self.page.goto(website_url + 'calendar', wait_until='networkidle', timeout=60000)

        internal_event_urls = set()
        showclix_urls = set()

        # Look for internal event page links (/events/show-name)
        all_links = await self.page.query_selector_all('a[href*="/events/"]')
        for link in all_links:
            href = await link.get_attribute('href')
            if href and '/events/' in href:
                if not href.startswith('http'):
                    href = 'https://www.creekandcave.com' + href
                internal_event_urls.add(href)

        print(f"  Found {len(internal_event_urls)} event pages")

        # Visit each event page to find ShowClix ticket links
        for event_page in sorted(internal_event_urls):
            try:
                await self.page.goto(event_page, wait_until='networkidle', timeout=30000)

                # Look for ShowClix links on event page
                showclix_links = await self.page.query_selector_all('a[href*="showclix.com"]')
                for link in showclix_links:
                    href = await link.get_attribute('href')
                    if href and '/event/' in href:
                        showclix_urls.add(href)

            except Exception as e:
                print(f"    Error visiting {event_page}: {e}")
                continue

        print(f"  Found {len(showclix_urls)} ShowClix ticket links")

        # Deduplicate by event slug
        unique_events = {}
        for url in showclix_urls:
            slug = url.split('/event/')[-1].split('?')[0]
            if slug not in unique_events:
                unique_events[slug] = url

        print(f"  Unique events: {len(unique_events)}")

        shows = []
        for slug, url in sorted(unique_events.items()):
            show = await self.scrape_event(url)
            if show:
                shows.append(show)

        return shows

    async def scrape_event(self, event_url):
        """Scrape individual event page for accurate date/time."""
        try:
            slug = event_url.split('/')[-1]
            print(f"    Scraping: {slug}")
            await self.page.goto(event_url, wait_until='networkidle', timeout=30000)

            # Extract JSON-LD schema data (most reliable)
            json_ld = await self.get_json_ld()

            show = {
                'name': '',
                'day': '',
                'time': '',
                'url': event_url,
                'source': 'showclix'
            }

            description = ''
            schema_day = None
            schema_time = None

            # Find Event schema
            for item in json_ld:
                if item.get('@type') == 'Event':
                    show['name'] = item.get('name', '')
                    description = item.get('description', '')

                    # Get start date/time from schema
                    start_date = item.get('startDate', '')
                    schema_day, schema_time = parse_schema_datetime(start_date)
                    break

            # Fallback: try to get from page content
            if not show['name']:
                title = await self.page.query_selector('h1')
                if title:
                    show['name'] = await title.inner_text()

            # Get full page text for pattern matching
            page_text = await self.page.inner_text('body')

            # Priority 1: Check known recurring shows list
            known_day, known_time = get_known_show_info(show['name'])
            if known_day:
                show['day'] = known_day
                if known_time:
                    show['time'] = known_time
                print(f"      -> {show['name']}: {show['day']} @ {show['time']} (from known shows)")
                return show

            # Priority 2: Look for "Every [Day]" pattern in description/page
            recurring_day = extract_day_from_description(description) or extract_day_from_description(page_text)
            if recurring_day:
                show['day'] = recurring_day
            elif schema_day:
                show['day'] = schema_day

            # Get time from schema or page
            if schema_time:
                show['time'] = schema_time
            else:
                show['time'] = extract_time_from_text(page_text) or ''

            if show['name']:
                print(f"      -> {show['name']}: {show['day']} @ {show['time']}")
                return show

            return None

        except Exception as e:
            print(f"    Error scraping {event_url}: {e}")
            return None


class SimpleTixScraper(ShowScraper):
    """Scraper for SimpleTix (Rozco's Comedy)."""

    async def scrape_venue(self, venue_url):
        """Scrape all shows from SimpleTix venue page."""
        print(f"\n  Fetching {venue_url}...")
        await self.page.goto(venue_url, wait_until='networkidle', timeout=60000)

        # Get all event links
        event_links = await self.page.query_selector_all('a[href*="simpletix.com/e/"]')
        event_urls = set()

        for link in event_links:
            href = await link.get_attribute('href')
            if href:
                if not href.startswith('http'):
                    href = 'https://www.simpletix.com' + href
                event_urls.add(href)

        print(f"  Found {len(event_urls)} event links")

        # Scrape events and consolidate by normalized name
        shows_by_name = defaultdict(list)

        for url in sorted(event_urls):
            show = await self.scrape_event(url)
            if show:
                # Normalize the name to group date-specific instances
                normalized = normalize_show_name(show['name'])
                shows_by_name[normalized.lower()].append(show)

        # Consolidate: for each unique show, pick the best data
        final_shows = []
        for normalized_name, instances in shows_by_name.items():
            best = instances[0]
            best['name'] = normalize_show_name(best['name'])

            # Check known shows for accurate day/time
            known_day, known_time = get_known_show_info(best['name'])
            if known_day:
                best['day'] = known_day
            if known_time:
                best['time'] = known_time

            print(f"  Consolidated: {best['name']} -> {best['day']} @ {best['time']} ({len(instances)} instances)")
            final_shows.append(best)

        return final_shows

    async def scrape_event(self, event_url):
        """Scrape individual SimpleTix event page."""
        try:
            event_slug = event_url.split('/')[-1].split('-tickets')[0]
            print(f"    Scraping: {event_slug[:40]}...")

            await self.page.goto(event_url, wait_until='networkidle', timeout=30000)

            show = {
                'name': '',
                'day': '',
                'time': '',
                'url': event_url,
                'source': 'simpletix'
            }

            # Try to get title
            title = await self.page.query_selector('h1, .event-title, .title')
            if title:
                show['name'] = (await title.inner_text()).strip()

            # Get page text for day/time extraction
            page_text = await self.page.inner_text('body')

            # Check JSON-LD first for structured data
            json_ld = await self.get_json_ld()
            schema_day = None
            schema_time = None
            for item in json_ld:
                if item.get('@type') == 'Event':
                    if not show['name']:
                        show['name'] = item.get('name', '')
                    start_date = item.get('startDate', '')
                    schema_day, schema_time = parse_schema_datetime(start_date)
                    break

            # Priority 1: Known shows list
            known_day, known_time = get_known_show_info(show['name'])
            if known_day:
                show['day'] = known_day
                if known_time:
                    show['time'] = known_time
                return show

            # Priority 2: Look for recurring patterns in text
            recurring_day = extract_day_from_description(page_text)
            if recurring_day:
                show['day'] = recurring_day
            elif schema_day:
                show['day'] = schema_day

            # Get time
            if schema_time:
                show['time'] = schema_time
            else:
                show['time'] = extract_time_from_text(page_text) or ''

            return show if show['name'] else None

        except Exception as e:
            print(f"    Error scraping {event_url}: {e}")
            return None


async def update_database(shows, venue_name):
    """Update the database with scraped show data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get venue ID
    cursor.execute("SELECT id FROM venues WHERE name = ?", (venue_name,))
    row = cursor.fetchone()
    if not row:
        print(f"  Venue '{venue_name}' not found in database")
        conn.close()
        return

    venue_id = row[0]
    updated = 0

    for show in shows:
        if not show['name']:
            continue

        # Try to find matching show in database
        cursor.execute("""
            SELECT id, event_name, event_date, show_time
            FROM images
            WHERE venue_id = ? AND LOWER(event_name) LIKE ?
        """, (venue_id, f"%{show['name'].lower()[:20]}%"))

        rows = cursor.fetchall()

        for row in rows:
            image_id, current_name, current_date, current_time = row

            new_date = show['day'] if show['day'] else current_date
            new_time = show['time'] if show['time'] else current_time

            # Only update if we have new data
            if new_date != current_date or new_time != current_time:
                cursor.execute("""
                    UPDATE images
                    SET event_date = ?, show_time = ?
                    WHERE id = ?
                """, (new_date, new_time, image_id))

                print(f"  Updated: {current_name}")
                print(f"    Day: {current_date} -> {new_date}")
                print(f"    Time: {current_time} -> {new_time}")
                updated += 1

    conn.commit()
    conn.close()

    print(f"  Total updated: {updated} shows")


async def scrape_showclix():
    """Scrape Creek and the Cave from ShowClix."""
    print("\n" + "="*60)
    print("SCRAPING: Creek and the Cave (ShowClix)")
    print("="*60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        scraper = ShowClixScraper(browser)
        await scraper.setup()

        try:
            shows = await scraper.scrape_venue(
                VENUES['creek_and_cave']['website_url'],
                VENUES['creek_and_cave']['ticketing_url']
            )
            await update_database(shows, VENUES['creek_and_cave']['name'])
        finally:
            await scraper.cleanup()
            await browser.close()


async def scrape_simpletix():
    """Scrape Rozco's Comedy from SimpleTix."""
    print("\n" + "="*60)
    print("SCRAPING: Rozco's Comedy (SimpleTix)")
    print("="*60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        scraper = SimpleTixScraper(browser)
        await scraper.setup()

        try:
            shows = await scraper.scrape_venue(VENUES['rozcos']['ticketing_url'])
            await update_database(shows, VENUES['rozcos']['name'])
        finally:
            await scraper.cleanup()
            await browser.close()


async def validate_data():
    """Validate scraped data for accuracy."""
    print("\n" + "="*60)
    print("VALIDATING DATA")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check for shows missing day
    cursor.execute("""
        SELECT i.event_name, v.name as venue
        FROM images i
        JOIN venues v ON i.venue_id = v.id
        WHERE i.event_name IS NOT NULL
        AND (i.event_date IS NULL OR i.event_date = '')
    """)

    missing_day = cursor.fetchall()
    if missing_day:
        print(f"\n  Shows missing day ({len(missing_day)}):")
        for name, venue in missing_day[:10]:
            print(f"    - {name} ({venue})")

    # Check for shows missing time
    cursor.execute("""
        SELECT i.event_name, v.name as venue
        FROM images i
        JOIN venues v ON i.venue_id = v.id
        WHERE i.event_name IS NOT NULL
        AND (i.show_time IS NULL OR i.show_time = '')
    """)

    missing_time = cursor.fetchall()
    if missing_time:
        print(f"\n  Shows missing time ({len(missing_time)}):")
        for name, venue in missing_time[:10]:
            print(f"    - {name} ({venue})")

    conn.close()

    if not missing_day and not missing_time:
        print("  All shows have day and time data!")


async def main():
    """Main entry point."""
    print("="*60)
    print(f"ATX Comedy Scraper v2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Scrape each venue
    await scrape_showclix()
    await scrape_simpletix()

    # Validate data
    await validate_data()

    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print("\nRun 'python regenerate_shows.py' to update the website.")


if __name__ == '__main__':
    asyncio.run(main())
