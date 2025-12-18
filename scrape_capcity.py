"""
Scrape Cap City Comedy Club shows and add to database.
Handles headliner pages with multiple show times.
"""

import sqlite3
import asyncio
import aiohttp
import re
import hashlib
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

DB_PATH = 'comedy_images.db'
CAPCITY_BASE = 'https://www.capcitycomedy.com'
CAPCITY_CALENDAR = f'{CAPCITY_BASE}/calendar'
IMAGE_DIR = 'images/cap_city_comedy'

async def download_image(session, url, local_path):
    """Download an image from URL."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                content = await response.read()
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(content)
                print(f"    Downloaded: {os.path.basename(local_path)}")
                return True
    except Exception as e:
        print(f"    Failed to download image: {e}")
    return False


async def scrape_capcity():
    """Scrape all shows from Cap City Comedy Club."""
    print("="*60)
    print("SCRAPING: Cap City Comedy Club")
    print("="*60)

    shows = []
    os.makedirs(IMAGE_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            # Step 1: Get all event links from calendar
            print(f"\n  Loading calendar: {CAPCITY_CALENDAR}")
            await page.goto(CAPCITY_CALENDAR, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)

            # Find all event links (like /events/121668)
            event_links = await page.query_selector_all('a[href*="/events/"]')
            event_urls = set()
            for link in event_links:
                href = await link.get_attribute('href')
                if href and '/events/' in href and not href.endswith('/events/'):
                    if not href.startswith('http'):
                        href = CAPCITY_BASE + href
                    event_urls.add(href)

            print(f"  Found {len(event_urls)} event pages")

            # Calculate date cutoff (10 days from now)
            cutoff_date = datetime.now() + timedelta(days=10)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # Step 2: Visit each event page to get show details
            async with aiohttp.ClientSession() as session:
                for event_url in sorted(event_urls):
                    try:
                        print(f"\n  Scraping event: {event_url}")
                        await page.goto(event_url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(2000)

                        # Get performer name from h1 or title
                        performer_name = ''
                        title_elem = await page.query_selector('h1')
                        if title_elem:
                            performer_name = await title_elem.inner_text()
                            performer_name = performer_name.strip()
                            # Clean up name - remove "Special Event:" prefix
                            performer_name = re.sub(r'^Special Event:\s*', '', performer_name, flags=re.IGNORECASE)
                            performer_name = performer_name.strip()

                        if not performer_name:
                            print(f"    Skipping - no performer name found")
                            continue

                        # Skip private events, workshops, and generic page titles
                        skip_keywords = ['private', 'workshop', 'upcoming events', 'calendar']
                        if any(kw in performer_name.lower() for kw in skip_keywords):
                            print(f"    Skipping: {performer_name}")
                            continue

                        # Get performer image - look for headshot/talent images specifically
                        image_url = ''
                        # Priority 1: Look for talent headshots
                        img_selectors_priority = [
                            'img[src*="talent/headshots"]',
                            'img[src*="headshot"]',
                            'img[src*="/talent/"]',
                        ]
                        for selector in img_selectors_priority:
                            img_elem = await page.query_selector(selector)
                            if img_elem:
                                img_src = await img_elem.get_attribute('src')
                                if img_src:
                                    image_url = img_src
                                    break

                        # Priority 2: Find any non-header seatengine image
                        if not image_url:
                            imgs = await page.query_selector_all('img')
                            for img in imgs:
                                src = await img.get_attribute('src')
                                if src and 'seatengine' in src and 'header' not in src:
                                    image_url = src
                                    break

                        if image_url and not image_url.startswith('http'):
                            image_url = CAPCITY_BASE + image_url

                        # Get all show times - look for links to /shows/ pages
                        show_links = await page.query_selector_all('a[href*="/shows/"]')

                        # Get page text for parsing dates/times
                        page_text = await page.inner_text('body')

                        # Find all date/time patterns in the page
                        # Cap City uses two formats:
                        # 1. "Thu, Dec 18, 2025" with times on separate lines
                        # 2. "12/21/2025 7:00 PM" - date and time together
                        date_pattern = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s*(\d{4})'
                        date_pattern2 = r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}:\d{2}\s*(?:AM|PM))'
                        time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM))'

                        # Find all dates and times from the "CLICK SHOWTIME" section
                        # Split text to find showtime section (between CLICK SHOWTIME and performer bio)
                        showtime_section = ''
                        if 'CLICK SHOWTIME' in page_text:
                            showtime_idx = page_text.find('CLICK SHOWTIME')
                            # Find where the performer name/bio starts (usually in caps after the times)
                            # Look for SPECIAL EVENT: or the performer name in caps
                            remaining_text = page_text[showtime_idx:]

                            # Find the end of the showtime section by looking for performer name pattern
                            # The performer name is usually all caps or starts with "SPECIAL EVENT:"
                            lines = remaining_text.split('\n')
                            section_lines = []
                            found_times = False
                            for line in lines:
                                line_stripped = line.strip()
                                # Check if this is a date/time line
                                if re.search(date_pattern, line_stripped) or re.search(time_pattern, line_stripped):
                                    section_lines.append(line)
                                    found_times = True
                                elif found_times and len(line_stripped) > 5:
                                    # If we've found times and now hit a non-time line, stop
                                    # But skip empty lines
                                    if not re.search(r'^\s*$', line_stripped):
                                        break
                            showtime_section = '\n'.join(section_lines)

                        # Parse dates and their associated times
                        matches = []

                        if showtime_section:
                            # Parse the showtime section lines
                            lines = showtime_section.split('\n')
                            current_date = None
                            for line in lines:
                                line = line.strip()
                                # Check if this line contains a date
                                date_match = re.search(date_pattern, line)
                                if date_match:
                                    current_date = date_match.groups()
                                # Check if this line contains times
                                time_matches = re.findall(time_pattern, line)
                                if time_matches and current_date:
                                    for time_val in time_matches:
                                        matches.append((*current_date, time_val))
                        # Try alternate date format (12/21/2025 7:00 PM) if no matches found
                        if not matches:
                            alt_matches = re.findall(date_pattern2, page_text)
                            for m in alt_matches:
                                # m = (month, day, year, time)
                                month_num, day, year, time_val = m
                                # Convert month number to short name
                                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                                month_idx = int(month_num) - 1
                                if 0 <= month_idx < 12:
                                    month_str = month_names[month_idx]
                                    # Get day of week
                                    try:
                                        dt = datetime.strptime(f"{year}-{month_num}-{day}", "%Y-%m-%d")
                                        day_abbr = dt.strftime('%a')  # Mon, Tue, etc.
                                        matches.append((day_abbr, month_str, day, year, time_val))
                                    except:
                                        pass

                        if not matches:
                            print(f"    No show times found")
                            continue

                        # Also get show URLs
                        show_urls = []
                        for link in show_links:
                            href = await link.get_attribute('href')
                            if href and '/shows/' in href:
                                if not href.startswith('http'):
                                    href = CAPCITY_BASE + href
                                if href not in show_urls:
                                    show_urls.append(href)

                        print(f"    Found {len(matches)} show times, {len(show_urls)} ticket links")

                        # Match dates with show URLs
                        for i, match in enumerate(matches):
                            day_name, month, day, year, time_str = match
                            year = year or '2025'

                            # Parse the date (month is abbreviated like Dec, Jan, etc.)
                            try:
                                show_date = datetime.strptime(f"{month} {day} {year}", "%b %d %Y")
                            except:
                                continue

                            # Skip if past cutoff or in the past
                            if show_date > cutoff_date:
                                print(f"      Skipping (past 10 days): {month} {day}")
                                continue
                            if show_date < today:
                                print(f"      Skipping (past): {month} {day}")
                                continue

                            # Format date string
                            date_str = f"{day_name.capitalize()}, {month[:3]} {day}"
                            time_str = time_str.strip().upper()

                            # Get corresponding show URL (try to match by index)
                            show_url = show_urls[i] if i < len(show_urls) else (show_urls[0] if show_urls else event_url)

                            show = {
                                'name': performer_name,
                                'date': date_str,
                                'day': day_name[:3].upper(),
                                'time': time_str,
                                'url': show_url,
                                'image_url': image_url,
                                'event_url': event_url
                            }
                            shows.append(show)
                            print(f"      Added: {performer_name} - {date_str} @ {time_str}")

                    except Exception as e:
                        print(f"    Error scraping event: {e}")
                        continue

                # Step 3: Download images for all shows
                print("\n" + "="*60)
                print("DOWNLOADING IMAGES")
                print("="*60)

                downloaded_images = {}
                for show in shows:
                    if show['image_url'] and show['image_url'] not in downloaded_images:
                        # Create filename from performer name
                        safe_name = re.sub(r'[^\w\s-]', '', show['name'].lower())
                        safe_name = re.sub(r'[\s]+', '_', safe_name)[:30]
                        image_hash = hashlib.md5(show['image_url'].encode()).hexdigest()[:8]

                        # Determine extension
                        ext = '.jpg'
                        if '.png' in show['image_url'].lower():
                            ext = '.png'

                        local_path = f"{IMAGE_DIR}/{safe_name}_{image_hash}{ext}"

                        if not os.path.exists(local_path):
                            success = await download_image(session, show['image_url'], local_path)
                            if success:
                                downloaded_images[show['image_url']] = local_path
                        else:
                            print(f"    Already exists: {os.path.basename(local_path)}")
                            downloaded_images[show['image_url']] = local_path

                # Update shows with local image paths
                for show in shows:
                    if show['image_url'] in downloaded_images:
                        show['local_image'] = downloaded_images[show['image_url']]
                    else:
                        show['local_image'] = ''

        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

    return shows


def update_database(shows):
    """Add/update shows in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get or create Cap City Comedy venue
    cursor.execute("SELECT id FROM venues WHERE name = 'Cap City Comedy'")
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO venues (name, url) VALUES (?, ?)",
                      ('Cap City Comedy', CAPCITY_CALENDAR))
        venue_id = cursor.lastrowid
        print(f"  Created Cap City Comedy venue with ID {venue_id}")
    else:
        venue_id = row[0]

    # Clear existing Cap City shows
    cursor.execute('DELETE FROM images WHERE venue_id = ?', (venue_id,))
    print(f"  Cleared existing Cap City shows")

    added = 0

    for show in shows:
        # Create unique hash for this specific show (name + date + time)
        unique_key = f"{show['name']}_{show['date']}_{show['time']}"
        image_hash = hashlib.md5(unique_key.encode()).hexdigest()[:16]

        local_path = show.get('local_image', '')

        # Make source_url unique by appending the show time
        unique_url = f"{show['url']}#{show['date'].replace(' ', '_').replace(',', '')}_{show['time'].replace(' ', '').replace(':', '')}"

        cursor.execute("""
            INSERT INTO images (venue_id, source_url, local_path, event_name, event_date, show_time, image_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (venue_id, unique_url, local_path, show['name'], show['date'], show['time'], image_hash))
        added += 1

    conn.commit()
    conn.close()

    print(f"\n  Database updated: {added} shows added")
    return added


async def main():
    print("="*60)
    print(f"Cap City Comedy Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    shows = await scrape_capcity()

    if shows:
        print("\n" + "="*60)
        print("UPDATING DATABASE")
        print("="*60)
        update_database(shows)

        print("\n" + "="*60)
        print("SHOWS FOUND:")
        print("="*60)
        for show in shows:
            img_status = "Y" if show.get('local_image') else "N"
            print(f"  [{img_status}] {show['name']} - {show['date']} @ {show['time']}")
    else:
        print("\n  No shows found")

    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(main())
