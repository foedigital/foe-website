"""
Scrape Vulcan Gas Company comedy shows and add to database.
Filters for comedy shows only (ticketsauce.com tickets).
Fetches images from ticketsauce event pages.
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
VULCAN_BASE = 'https://www.vulcanatx.com'
VULCAN_URL = VULCAN_BASE + '/'
IMAGE_DIR = 'images/vulcan_gas_company'

# Keywords to exclude (non-comedy events)
EXCLUDED_KEYWORDS = [
    "bingo", "loco", "dj", "edm", "wreckno", "super future",
    "dose of sound", "electronic", "rave"
]


def is_comedy_show(title: str, ticket_url: str) -> bool:
    """
    Determine if an event is a comedy show.
    Primary filter: Ticket URL must contain vulcanatx.ticketsauce.com
    Secondary filter: Title must not contain excluded keywords
    """
    if not ticket_url or "vulcanatx.ticketsauce.com" not in ticket_url.lower():
        return False

    title_lower = title.lower() if title else ""
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in title_lower:
            return False

    return True


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


async def get_ticketsauce_image(page, ticket_url):
    """Fetch the event image from a ticketsauce event page."""
    try:
        await page.goto(ticket_url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(2000)

        # Try to find event image - look for cloudinary images which are the event posters
        img_selectors = [
            'img[src*="cloudinary"][src*="image"]',
            'img[src*="eventservice"]',
            'img[alt*="Logo"]',
            'img[alt*="logo"]',
            '.event-image img',
            '[class*="event"] img',
        ]

        for selector in img_selectors:
            img = await page.query_selector(selector)
            if img:
                src = await img.get_attribute('src')
                if src and 'cloudinary' in src and 'partner-logos' not in src:
                    return src

        # Fallback: try og:image meta tag
        og_image = await page.query_selector('meta[property="og:image"]')
        if og_image:
            content = await og_image.get_attribute('content')
            if content:
                return content

        # Last resort: find any large cloudinary image
        all_imgs = await page.query_selector_all('img[src*="cloudinary"]')
        for img in all_imgs:
            src = await img.get_attribute('src')
            if src and 'partner-logos' not in src and 'icon' not in src.lower():
                return src

    except Exception as e:
        print(f"      Error fetching image from {ticket_url}: {e}")

    return None


async def scrape_vulcan():
    """Scrape all comedy shows from Vulcan Gas Company."""
    print("="*60)
    print("SCRAPING: Vulcan Gas Company")
    print("="*60)

    shows = []
    os.makedirs(IMAGE_DIR, exist_ok=True)

    # Calculate date cutoff (10 days from now)
    cutoff_date = datetime.now() + timedelta(days=10)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            print(f"\n  Loading: {VULCAN_URL}")
            await page.goto(VULCAN_URL, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)

            # Scroll to load all events
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            # Find all event containers
            event_elements = await page.query_selector_all(".w-dyn-item")
            print(f"  Found {len(event_elements)} event containers")

            # First pass: collect all comedy shows
            comedy_shows = []

            for event in event_elements:
                try:
                    # Get ticket link
                    ticket_url = ""
                    ticket_link = await event.query_selector('a[href*="ticketsauce"]')
                    if ticket_link:
                        ticket_url = await ticket_link.get_attribute("href") or ""

                    # Get event title
                    event_name = None
                    title_el = await event.query_selector(".event-name")
                    if title_el:
                        event_name = await title_el.inner_text()
                        if event_name:
                            event_name = event_name.strip()

                    # Skip if not a comedy show
                    if not is_comedy_show(event_name, ticket_url):
                        continue

                    # Get event month, date, day, and time
                    month_el = await event.query_selector(".event-month")
                    date_el = await event.query_selector(".event-date")
                    day_el = await event.query_selector(".event-day")
                    time_el = await event.query_selector(".event-time")

                    month = ""
                    day_num = ""
                    day_of_week = ""
                    event_time = ""

                    if month_el:
                        month = (await month_el.inner_text() or "").strip()
                    if date_el:
                        day_num = (await date_el.inner_text() or "").strip()
                    if day_el:
                        day_of_week = (await day_el.inner_text() or "").strip()
                    if time_el:
                        event_time = (await time_el.inner_text() or "").strip()

                    # Parse the date to check if within range
                    if month and day_num:
                        try:
                            month_cap = month.capitalize()[:3]
                            year = 2025
                            current_month = datetime.now().month
                            month_num = datetime.strptime(month_cap, "%b").month
                            if month_num < current_month:
                                year = 2026

                            show_date = datetime.strptime(f"{month_cap} {day_num} {year}", "%b %d %Y")

                            if show_date > cutoff_date:
                                print(f"    Skipping (past 10 days): {event_name} - {month} {day_num}")
                                continue
                            if show_date < today:
                                print(f"    Skipping (past): {event_name} - {month} {day_num}")
                                continue
                        except Exception:
                            pass

                    date_str = f"{day_of_week}, {month.capitalize()} {day_num}" if day_of_week else f"{month.capitalize()} {day_num}"
                    time_str = event_time.upper() if event_time else ""

                    comedy_shows.append({
                        'name': event_name,
                        'date': date_str,
                        'day': day_of_week[:3].upper() if day_of_week else "",
                        'time': time_str,
                        'url': ticket_url,
                        'image_url': ""
                    })
                    print(f"    + Comedy: {event_name} - {date_str} @ {time_str}")

                except Exception as e:
                    print(f"    Error processing event: {e}")
                    continue

            # Second pass: fetch images from ticketsauce pages
            if comedy_shows:
                print(f"\n  Fetching images from ticketsauce pages...")

                for show in comedy_shows:
                    if show['url']:
                        print(f"    Fetching image for: {show['name']}")
                        image_url = await get_ticketsauce_image(page, show['url'])
                        if image_url:
                            show['image_url'] = image_url
                            print(f"      Found: {image_url[:60]}...")
                        else:
                            print(f"      No image found")

            shows = comedy_shows

            # Download images
            if any(s.get('image_url') for s in shows):
                print("\n" + "="*60)
                print("DOWNLOADING IMAGES")
                print("="*60)

                async with aiohttp.ClientSession() as session:
                    downloaded_images = {}
                    for show in shows:
                        if show['image_url'] and show['image_url'] not in downloaded_images:
                            safe_name = re.sub(r'[^\w\s-]', '', show['name'].lower())
                            safe_name = re.sub(r'[\s]+', '_', safe_name)[:30]
                            image_hash = hashlib.md5(show['image_url'].encode()).hexdigest()[:8]

                            # Determine extension from URL
                            ext = '.jpg'
                            if '.png' in show['image_url'].lower():
                                ext = '.png'
                            elif '.webp' in show['image_url'].lower():
                                ext = '.webp'

                            local_path = f"{IMAGE_DIR}/{safe_name}_{image_hash}{ext}"

                            if not os.path.exists(local_path):
                                success = await download_image(session, show['image_url'], local_path)
                                if success:
                                    downloaded_images[show['image_url']] = local_path
                            else:
                                print(f"    Already exists: {os.path.basename(local_path)}")
                                downloaded_images[show['image_url']] = local_path

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

    # Get or create Vulcan Gas Company venue
    cursor.execute("SELECT id FROM venues WHERE name = 'Vulcan Gas Company'")
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO venues (name, url) VALUES (?, ?)",
                      ('Vulcan Gas Company', VULCAN_URL))
        venue_id = cursor.lastrowid
        print(f"  Created Vulcan Gas Company venue with ID {venue_id}")
    else:
        venue_id = row[0]

    # Clear existing Vulcan shows
    cursor.execute('DELETE FROM images WHERE venue_id = ?', (venue_id,))
    print(f"  Cleared existing Vulcan Gas Company shows")

    added = 0

    for show in shows:
        unique_key = f"{show['name']}_{show['date']}_{show['time']}"
        image_hash = hashlib.md5(unique_key.encode()).hexdigest()[:16]

        local_path = show.get('local_image', '')

        date_slug = show['date'].replace(' ', '_').replace(',', '')
        time_slug = show['time'].replace(' ', '').replace(':', '')
        unique_url = f"{show['url']}#{date_slug}_{time_slug}"

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
    print(f"Vulcan Gas Company Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    shows = await scrape_vulcan()

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
        print("\n  No comedy shows found within the next 10 days")

    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(main())
