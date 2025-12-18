"""
Scrape Comedy Mothership shows and add to database.
Excludes sold out shows.
"""

import sqlite3
import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright

DB_PATH = 'comedy_images.db'
MOTHERSHIP_URL = 'https://comedymothership.com/shows'

async def scrape_mothership():
    """Scrape all shows from Comedy Mothership."""
    print("="*60)
    print("SCRAPING: Comedy Mothership")
    print("="*60)

    shows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            print(f"\n  Loading {MOTHERSHIP_URL}...")
            await page.goto(MOTHERSHIP_URL, wait_until='domcontentloaded', timeout=90000)
            await page.wait_for_timeout(5000)  # Wait for dynamic content

            # Get the page content
            content = await page.content()

            # Find all show cards/elements
            # Comedy Mothership typically has show cards with date, name, time, and ticket status
            show_elements = await page.query_selector_all('[class*="show"], [class*="event"], .card, article')

            if not show_elements:
                # Try getting all links that might be shows
                show_elements = await page.query_selector_all('a[href*="/shows/"]')

            print(f"  Found {len(show_elements)} potential show elements")

            # Extract show details from page text
            body_text = await page.inner_text('body')

            # Look for show patterns in the text
            # Mothership shows typically have format like:
            # MONDAY, DEC 15
            # KILL TONY
            # 8:00 PM
            # SOLD OUT or GET TICKETS

            lines = body_text.split('\n')
            current_show = {}

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Check for date pattern like "MONDAY, DEC 15" or "FRIDAY, DEC 19"
                date_match = re.match(r'^(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})(?:,?\s+(\d{4}))?$', line, re.IGNORECASE)
                if date_match:
                    # Save previous show if exists
                    if current_show.get('name'):
                        shows.append(current_show)

                    day = date_match.group(1).capitalize()
                    month = date_match.group(2).capitalize()
                    date_num = date_match.group(3)
                    year = date_match.group(4) or '2025'

                    current_show = {
                        'day': day,
                        'date': f"{month} {date_num}",
                        'name': '',
                        'time': '',
                        'sold_out': False,
                        'url': MOTHERSHIP_URL
                    }
                    continue

                # Check for time pattern like "8:00 PM" or "7:30 PM"
                time_match = re.match(r'^(\d{1,2}:\d{2}\s*(?:AM|PM))$', line, re.IGNORECASE)
                if time_match and current_show:
                    current_show['time'] = time_match.group(1).upper()
                    continue

                # Check for sold out
                if 'SOLD OUT' in line.upper():
                    if current_show:
                        current_show['sold_out'] = True
                    continue

                # Check for ticket button (means available)
                if 'GET TICKETS' in line.upper() or 'BUY TICKETS' in line.upper():
                    continue

                # If we have a date set but no name yet, this might be the show name
                if current_show and current_show.get('day') and not current_show.get('name'):
                    # Skip common non-show text
                    skip_words = ['SHOWS', 'MENU', 'ABOUT', 'CONTACT', 'HOME', 'CART', 'SEARCH',
                                  'COMEDY MOTHERSHIP', 'AUSTIN', 'TEXAS', 'GET TICKETS', 'BUY',
                                  'MAIN ROOM', 'SECRET SHOW', 'THE FAT MAN']
                    if line.upper() not in skip_words and len(line) > 2 and len(line) < 100:
                        current_show['name'] = line
                        continue

            # Don't forget the last show
            if current_show.get('name'):
                shows.append(current_show)

            print(f"\n  Extracted {len(shows)} shows:")
            print("-" * 60)

            available = []
            sold_out_list = []

            for show in shows:
                status = "SOLD OUT" if show['sold_out'] else "Available"
                print(f"  {show['day']:10} {show['date']:8} {show['name'][:30]:30} {show['time']:8} [{status}]")

                if show['sold_out']:
                    sold_out_list.append(show['name'])
                else:
                    available.append(show)

            print("-" * 60)
            print(f"  Available: {len(available)}")
            print(f"  Sold out: {len(sold_out_list)}")

        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

    return [s for s in shows if not s['sold_out']]


def update_database(shows):
    """Add/update shows in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get or create Comedy Mothership venue
    cursor.execute("SELECT id FROM venues WHERE name = 'Comedy Mothership'")
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO venues (name, url) VALUES (?, ?)",
                      ('Comedy Mothership', MOTHERSHIP_URL))
        venue_id = cursor.lastrowid
        print(f"  Created Comedy Mothership venue with ID {venue_id}")
    else:
        venue_id = row[0]

    added = 0
    updated = 0

    for show in shows:
        # Check if show already exists
        cursor.execute("""
            SELECT id, event_date, show_time FROM images
            WHERE venue_id = ? AND LOWER(event_name) LIKE ?
        """, (venue_id, f"%{show['name'].lower()[:15]}%"))

        existing = cursor.fetchone()

        # Build the date string
        date_str = f"{show['day']}, {show['date']}"

        if existing:
            # Update existing show
            cursor.execute("""
                UPDATE images
                SET event_date = ?, show_time = ?
                WHERE id = ?
            """, (date_str, show['time'], existing[0]))
            updated += 1
        else:
            # Add new show
            import hashlib
            source_url = f"{MOTHERSHIP_URL}#{show['name'].lower().replace(' ', '-')}"
            image_hash = hashlib.md5(source_url.encode()).hexdigest()[:16]

            cursor.execute("""
                INSERT INTO images (venue_id, source_url, local_path, event_name, event_date, show_time, image_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (venue_id, source_url, '', show['name'], date_str, show['time'], image_hash))
            added += 1
            print(f"  Added: {show['name']} - {date_str} @ {show['time']}")

    # Mark sold out shows
    cursor.execute("""
        UPDATE images SET event_date = 'SOLD OUT'
        WHERE venue_id = ? AND LOWER(event_name) LIKE '%kill tony%'
    """, (venue_id,))

    conn.commit()
    conn.close()

    print(f"\n  Database updated: {added} added, {updated} updated")


async def main():
    print("="*60)
    print(f"Comedy Mothership Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    shows = await scrape_mothership()

    if shows:
        print("\n" + "="*60)
        print("UPDATING DATABASE")
        print("="*60)
        update_database(shows)

    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(main())
