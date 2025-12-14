"""
ATX Comedy Show Scraper
Fetches upcoming shows from Austin comedy venues and updates the website.
Run manually or via GitHub Actions on a schedule.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
import os

# Venue URLs
VENUES = {
    'creek_and_cave': {
        'name': 'Creek and the Cave',
        'url': 'https://www.creekandcave.com/',
        'address': '611 E 7th St',
        'location': 'east'
    },
    'east_austin_comedy': {
        'name': 'East Austin Comedy Club',
        'url': 'https://eastaustincomedy.com/',
        'address': '2505 E 6th St',
        'location': 'east'
    },
    'velveeta_room': {
        'name': 'The Velveeta Room',
        'url': 'https://www.thevelveetaroom.com/',
        'address': '521 E 6th St',
        'location': 'dirty6th'
    },
    'sunset_strip': {
        'name': 'Sunset Strip ATX',
        'url': 'https://www.sunsetstripatx.com/',
        'address': '214 E 6th St',
        'location': 'dirty6th'
    },
    'comedy_mothership': {
        'name': 'Comedy Mothership',
        'url': 'https://comedymothership.com/',
        'address': '509 E 6th St',
        'location': 'dirty6th'
    },
    'rozcoz': {
        'name': "Rozco's Comedy",
        'url': 'https://www.rozcoscomedy.com/',
        'address': '1805 E 7th St',
        'location': 'east'
    }
}

def fetch_page(url, timeout=30):
    """Fetch a webpage and return BeautifulSoup object."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def scrape_creek_and_cave():
    """Scrape upcoming shows from Creek and the Cave."""
    shows = []
    soup = fetch_page(VENUES['creek_and_cave']['url'])

    if not soup:
        return shows

    # Look for show listings - Creek uses various class patterns
    show_elements = soup.find_all(['div', 'article'], class_=re.compile(r'(show|event|performance)', re.I))

    for element in show_elements:
        try:
            title_elem = element.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'(title|name)', re.I))
            date_elem = element.find(['span', 'div', 'time'], class_=re.compile(r'(date|time)', re.I))

            if title_elem:
                show = {
                    'title': title_elem.get_text(strip=True),
                    'venue': VENUES['creek_and_cave']['name'],
                    'venue_url': VENUES['creek_and_cave']['url'],
                    'date': date_elem.get_text(strip=True) if date_elem else 'TBA',
                    'location': VENUES['creek_and_cave']['location']
                }
                shows.append(show)
        except Exception as e:
            print(f"Error parsing show element: {e}")
            continue

    return shows

def scrape_all_venues():
    """Scrape shows from all venues."""
    all_shows = []

    print("Scraping Creek and the Cave...")
    all_shows.extend(scrape_creek_and_cave())

    # Add more venue scrapers as needed
    # print("Scraping East Austin Comedy...")
    # all_shows.extend(scrape_east_austin())

    return all_shows

def generate_event_card_html(show):
    """Generate HTML for a single event card."""
    # Parse date if possible, otherwise use placeholder
    try:
        # Try to extract month and day
        date_str = show.get('date', 'TBA')
        month = 'TBA'
        day = '--'
        weekday = ''

        # Common date patterns
        date_match = re.search(r'(\w+)\s+(\d{1,2})', date_str)
        if date_match:
            month = date_match.group(1)[:3]
            day = date_match.group(2)
    except:
        month = 'TBA'
        day = '--'
        weekday = ''

    return f'''
            <div class="event-card">
                <div class="event-date">
                    <span class="month">{month}</span>
                    <span class="day">{day}</span>
                    <span class="weekday">{weekday}</span>
                </div>
                <div class="event-info">
                    <h3>{show['title']}</h3>
                    <p class="time">{show.get('time', 'See website for times')}</p>
                    <p class="venue">📍 {show['venue']}</p>
                    <p class="description">{show.get('description', '')}</p>
                </div>
                <a href="{show['venue_url']}" class="btn btn-outline" target="_blank">Get Tickets</a>
            </div>
'''

def update_upcoming_html(shows):
    """Update the upcoming.html file with scraped shows."""
    upcoming_file = os.path.join(os.path.dirname(__file__), 'upcoming.html')

    if not os.path.exists(upcoming_file):
        print("upcoming.html not found!")
        return False

    with open(upcoming_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the section to update (between markers if we add them)
    # For now, just log what we found
    print(f"Found {len(shows)} shows to potentially add")

    # In a full implementation, we would:
    # 1. Parse the existing HTML
    # 2. Find the events section
    # 3. Update with new shows while preserving featured/top picks
    # 4. Write back to file

    return True

def save_shows_json(shows):
    """Save scraped shows to a JSON file for reference."""
    output_file = os.path.join(os.path.dirname(__file__), 'scraped_shows.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'last_updated': datetime.now().isoformat(),
            'shows': shows
        }, f, indent=2)

    print(f"Saved {len(shows)} shows to scraped_shows.json")

def main():
    """Main entry point."""
    print(f"ATX Comedy Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # Scrape all venues
    shows = scrape_all_venues()

    print(f"\nTotal shows found: {len(shows)}")

    # Save to JSON for reference
    save_shows_json(shows)

    # Update HTML (when fully implemented)
    # update_upcoming_html(shows)

    print("\nScraping complete!")

if __name__ == '__main__':
    main()
