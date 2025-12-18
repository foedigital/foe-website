"""
East Austin Comedy Club Scraper
Scrapes events from https://eastaustincomedy.com/events-2-1
Only includes shows in the next 2 weeks.
"""

import sqlite3
import re
import hashlib
import asyncio
import requests
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)

DB_PATH = 'comedy_images.db'
IMAGES_DIR = Path('images/east_austin_comedy')
VENUE_NAME = 'East Austin Comedy Club'
EVENTS_URL = 'https://eastaustincomedy.com/events-2-1'
BASE_URL = 'https://eastaustincomedy.com'

# Date filtering
TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
TWO_WEEKS_FROM_NOW = TODAY + timedelta(days=14)


def parse_event_date(date_text):
    """Parse date string like 'Friday, December 20, 2024' or 'Dec 20'."""
    if not date_text:
        return None

    # Try full format: "Friday, December 20, 2024"
    try:
        # Remove day name if present
        if ',' in date_text:
            parts = date_text.split(',')
            if len(parts) >= 2:
                date_text = ','.join(parts[1:]).strip()

        date_obj = datetime.strptime(date_text.strip(), "%B %d, %Y")
        return date_obj
    except ValueError:
        pass

    # Try "December 20, 2024"
    try:
        date_obj = datetime.strptime(date_text.strip(), "%B %d, %Y")
        return date_obj
    except ValueError:
        pass

    # Try "Dec 20" format (assume current/next year)
    try:
        date_str = date_text.strip()
        # Try with current year
        date_obj = datetime.strptime(f"{date_str}, 2024", "%b %d, %Y")
        if date_obj < TODAY - timedelta(days=30):
            date_obj = datetime.strptime(f"{date_str}, 2025", "%b %d, %Y")
        return date_obj
    except ValueError:
        pass

    return None


def is_within_two_weeks(date_obj):
    """Check if date is today or within next 2 weeks."""
    if not date_obj:
        return False
    return TODAY <= date_obj <= TWO_WEEKS_FROM_NOW


def format_date_for_display(date_obj):
    """Format date as 'Wednesday, Dec 18' for database storage."""
    if not date_obj:
        return ''
    return date_obj.strftime('%A, %b %d')


def get_day_abbr(date_obj):
    """Get 3-letter day abbreviation."""
    if not date_obj:
        return ''
    return date_obj.strftime('%a').lower()


def download_image(url, save_path):
    """Download image from URL."""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(response.content)
            return True
    except Exception as e:
        print(f"    Error downloading image: {e}")
    return False


def generate_image_filename(event_name, image_url):
    """Generate a unique filename for the image."""
    # Create hash from URL for uniqueness
    url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
    # Clean event name for filename
    clean_name = re.sub(r'[^\w\s-]', '', event_name.lower())
    clean_name = re.sub(r'[\s]+', '_', clean_name)[:30]
    return f"{clean_name}_{url_hash}.jpg"


async def scrape_east_austin():
    """Scrape East Austin Comedy Club events."""
    print("\n" + "="*60)
    print("SCRAPING: East Austin Comedy Club")
    print(f"Date range: {TODAY.strftime('%b %d')} - {TWO_WEEKS_FROM_NOW.strftime('%b %d, %Y')}")
    print("="*60)

    events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            print(f"\n  Fetching {EVENTS_URL}...")
            await page.goto(EVENTS_URL, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)

            # Scroll to load all events
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 1000)')
                await page.wait_for_timeout(1000)

            # Try to navigate to next month if there's a navigation button
            try:
                next_btns = await page.query_selector_all('[class*="next"], [class*="arrow-right"], button:has-text("Next"), a:has-text(">")')
                for btn in next_btns[:2]:  # Try first 2 matching buttons
                    await btn.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

            # Find all event links (exclude ICS calendar downloads)
            event_links = await page.query_selector_all('a[href*="/events-2-1/"]')
            event_urls = set()

            for link in event_links:
                href = await link.get_attribute('href')
                if href and '/events-2-1/' in href and href != '/events-2-1/':
                    # Skip ICS calendar download links
                    if '?format=ical' in href or 'format=ical' in href:
                        continue
                    if not href.startswith('http'):
                        href = BASE_URL + href
                    # Clean the URL - remove any query params
                    href = href.split('?')[0]
                    event_urls.add(href)

            print(f"  Found {len(event_urls)} event links")

            # Scrape each event page
            for event_url in sorted(event_urls):
                try:
                    event = await scrape_event_page(page, event_url)
                    if event and event.get('in_range'):
                        events.append(event)
                        print(f"    + {event['name']}: {event['date_display']} @ {event['time']}")
                    elif event:
                        print(f"    - {event['name']}: {event['date_display']} (outside date range)")
                except Exception as e:
                    print(f"    Error scraping {event_url}: {e}")
                    continue

        finally:
            await context.close()
            await browser.close()

    print(f"\n  Found {len(events)} events in the next 2 weeks")
    return events


async def scrape_event_page(page, event_url):
    """Scrape individual event page."""
    await page.goto(event_url, wait_until='networkidle', timeout=30000)

    event = {
        'name': '',
        'date_display': '',
        'date_obj': None,
        'time': '',
        'image_url': '',
        'event_url': event_url,
        'in_range': False
    }

    # Get event title
    title_el = await page.query_selector('h1, h2.eventitem-title, .event-title')
    if title_el:
        event['name'] = (await title_el.inner_text()).strip()

    # Get event date and time from metadata
    # Squarespace events typically have date/time in list items
    meta_items = await page.query_selector_all('.eventitem-meta-date, .event-date, time')

    for item in meta_items:
        text = await item.inner_text()
        text = text.strip()

        # Check if it's a date (contains month name)
        if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June',
                                            'July', 'August', 'September', 'October', 'November', 'December']):
            event['date_obj'] = parse_event_date(text)
            if event['date_obj']:
                event['date_display'] = format_date_for_display(event['date_obj'])
                event['in_range'] = is_within_two_weeks(event['date_obj'])

        # Check if it's a time (contains AM/PM)
        time_match = re.search(r'(\d{1,2}:\d{2}\s*[AaPp][Mm])', text)
        if time_match and not event['time']:
            event['time'] = time_match.group(1).strip()

    # Try to get date from page text if not found
    if not event['date_obj']:
        page_text = await page.inner_text('body')
        # Look for date patterns
        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{4}', page_text)
        if date_match:
            event['date_obj'] = parse_event_date(date_match.group(0))
            if event['date_obj']:
                event['date_display'] = format_date_for_display(event['date_obj'])
                event['in_range'] = is_within_two_weeks(event['date_obj'])

    # Get event image
    img_el = await page.query_selector('.eventitem-column-thumbnail img, .event-image img, .sqs-image img, article img')
    if img_el:
        src = await img_el.get_attribute('src')
        if src:
            if src.startswith('//'):
                src = 'https:' + src
            event['image_url'] = src

    # Fallback: look for any large image on page
    if not event['image_url']:
        all_imgs = await page.query_selector_all('img')
        for img in all_imgs:
            src = await img.get_attribute('src')
            if src and 'squarespace-cdn' in src and 'logo' not in src.lower():
                if src.startswith('//'):
                    src = 'https:' + src
                event['image_url'] = src
                break

    return event if event['name'] else None


async def save_to_database(events):
    """Save scraped events to the database."""
    print("\n  Saving to database...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure venue exists
    cursor.execute("SELECT id FROM venues WHERE name = ?", (VENUE_NAME,))
    row = cursor.fetchone()

    if not row:
        # Create venue
        cursor.execute("""
            INSERT INTO venues (name, url) VALUES (?, ?)
        """, (VENUE_NAME, BASE_URL))
        venue_id = cursor.lastrowid
        print(f"  Created venue: {VENUE_NAME}")
    else:
        venue_id = row[0]

    # Create images directory
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    for event in events:
        # Generate filename and download image
        if event['image_url']:
            filename = generate_image_filename(event['name'], event['image_url'])
            local_path = IMAGES_DIR / filename

            if not local_path.exists():
                print(f"    Downloading image for: {event['name']}")
                download_image(event['image_url'], local_path)

            # Check if this event already exists
            cursor.execute("""
                SELECT id FROM images
                WHERE venue_id = ? AND event_name = ?
            """, (venue_id, event['name']))

            existing = cursor.fetchone()

            if existing:
                # Update existing
                cursor.execute("""
                    UPDATE images
                    SET event_date = ?, show_time = ?, source_url = ?
                    WHERE id = ?
                """, (event['date_display'], event['time'], event['event_url'], existing[0]))
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO images (venue_id, source_url, local_path, event_name, event_date, show_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    venue_id,
                    event['event_url'],
                    str(local_path),
                    event['name'],
                    event['date_display'],
                    event['time']
                ))

            saved += 1

    conn.commit()
    conn.close()

    print(f"  Saved {saved} events to database")


async def main():
    """Main entry point."""
    print("="*60)
    print(f"East Austin Comedy Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    events = await scrape_east_austin()

    if events:
        await save_to_database(events)
        print("\n" + "="*60)
        print("SCRAPING COMPLETE")
        print("="*60)
        print(f"\nFound {len(events)} shows in the next 2 weeks:")
        for event in events:
            print(f"  - {event['name']}: {event['date_display']} @ {event['time']}")
        print("\nRun 'python regenerate_shows.py' to update the website.")
    else:
        print("\nNo events found in the next 2 weeks.")


if __name__ == '__main__':
    asyncio.run(main())
