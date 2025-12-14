import sqlite3
from pathlib import Path
import re
from datetime import datetime

DB_PATH = Path(__file__).parent / "comedy_images.db"
INDEX_HTML_FILE = Path(__file__).parent / "index.html"
UPCOMING_HTML_FILE = Path(__file__).parent / "upcoming.html"
SHOWS_HTML_FILE = Path(__file__).parent / "shows.html"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_shows_with_images():
    """Fetches all shows that have an associated image."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            i.event_name,
            i.event_date,
            i.local_path,
            v.name as venue_name,
            v.url as venue_url
        FROM images i
        JOIN venues v ON i.venue_id = v.id
        WHERE i.event_name IS NOT NULL AND i.event_name != ''
        ORDER BY i.scraped_at DESC
        LIMIT 50
    """)
    shows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return shows

def extract_title(event_name, max_length=40):
    """Extract a cleaner title from the event name."""
    if not event_name:
        return "Comedy Show"
    
    title = re.sub(r'^(Poster for)\s*', '', event_name, flags=re.IGNORECASE)
    title = re.split(r',| at ', title)[0].strip()

    if len(title) > max_length:
        title = title[:max_length-3] + "..."
    return title

def parse_date(show):
    text_to_search = str(show.get('event_name', '')) + ' ' + str(show.get('event_date', ''))
    
    date_match = re.search(r'(\w{3,9})\s(\d{1,2})', text_to_search, re.IGNORECASE)
    if date_match:
        month_str = date_match.group(1)[:3].upper()
        day_str = date_match.group(2)
        
        try:
            date_obj = datetime.strptime(f"2025 {month_str} {day_str}", "%Y %b %d")
            weekday_str = date_obj.strftime('%A')
        except ValueError:
            weekday_str = ''

        return month_str, day_str, weekday_str

    return 'TBA', '', ''

def generate_featured_show_html(show):
    """Generates the HTML for the featured show section."""
    title = extract_title(show['event_name'], max_length=100)
    image_path = show['local_path'].replace('\\', '/')
    description = extract_title(show['event_name'], max_length=200)

    return f"""
<section class="featured-show-section">
    <h2>Featured Show</h2>
    <div class="featured-show-card">
        <img src="{image_path}" alt="{title}" class="featured-show-image">
        <div class="featured-show-info">
            <h3>{title}</h3>
            <p class="venue">📍 {show['venue_name']}</p>
            <p class="description">{description}</p>
            <a href="{show['venue_url']}" class="btn" target="_blank">Get Tickets</a>
        </div>
    </div>
</section>
"""

def generate_show_html(show):
    """Generates the HTML for a single show item for indexv2.html."""
    title = extract_title(show['event_name'])
    image_path = show['local_path'].replace('\\', '/')

    return f"""
<div class="show-item-v2" style="background-image: url('{image_path}');">
    <div class="show-overlay">
        <h3>{title}</h3>
        <span class="venue">{show['venue_name']}</span>
        <div class="show-details">
            <span class="show-time"></span>
            <a href="{show['venue_url']}" class="btn-v2" target="_blank">Tickets</a>
        </div>
    </div>
</div>
"""

def generate_top_pick_html(show):
    """Generates HTML for a featured-card on upcoming.html."""
    title = extract_title(show['event_name'], max_length=30)
    _, _, time_str = parse_date(show)
    
    return f"""
<div class="featured-card">
    <h3>{title}</h3>
    <p class="schedule">{time_str}</p>
    <p class="venue">📍 {show['venue_name']}</p>
    <p class="description">{extract_title(show['event_name'], 100)}</p>
    <a href="{show['venue_url']}" class="btn" target="_blank">Get Tickets</a>
</div>
"""

def generate_upcoming_event_html(show):
    """Generates HTML for an event-card on upcoming.html."""
    title = extract_title(show['event_name'], max_length=50)
    month, day, weekday = parse_date(show)

    return f"""
<div class="event-card">
    <div class="event-date">
        <span class="month">{month}</span>
        <span class="day">{day}</span>
        <span class="weekday">{weekday}</span>
    </div>
    <div class="event-info">
        <h3>{title}</h3>
        <p class="time">See website for showtimes</p>
        <p class="venue">📍 {show['venue_name']}</p>
        <p class="description">{extract_title(show['event_name'], 120)}</p>
    </div>
    <a href="{show['venue_url']}" class="btn btn-outline" target="_blank">Get Tickets</a>
</div>
"""

def generate_recurring_show_html(show):
    """Generates HTML for a show-item on shows.html."""
    title = extract_title(show['event_name'], max_length=50)
    month, day, weekday = parse_date(show)

    return f"""
<div class="show-item" data-day="{weekday[:3].lower()}" data-price="paid" data-location="east">
    <div class="show-day">
        <span class="day">{weekday[:3].upper()}</span>
        <span class="time"></span>
    </div>
    <div class="show-info">
        <h3>{title}</h3>
        <p class="host">Weekly Showcase</p>
        <p class="venue">📍 {show['venue_name']}</p>
        <p class="description">{extract_title(show['event_name'], 120)}</p>
    </div>
    <a href="{show['venue_url']}" class="btn btn-outline" target="_blank">Get Tickets</a>
</div>
"""

def update_index_page(shows):
    """Updates the indexv2.html file."""
    print("Updating indexv2.html...")
    featured_show = shows[0]
    regular_shows = shows[1:11] 

    featured_show_html = generate_featured_show_html(featured_show)
    show_html_parts = [generate_show_html(show) for show in regular_shows]
    shows_html = "\n".join(show_html_parts)

    with open(INDEX_HTML_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('<!-- FEATURED_SHOW_PLACEHOLDER -->', featured_show_html)
    content = content.replace('<!-- SHOW_LIST_PLACEHOLDER -->', shows_html)

    with open(INDEX_HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully updated indexv2.html.")

def update_upcoming_page(shows):
    """Updates the upcoming.html file."""
    print("Updating upcoming.html...")
    top_picks = shows[:5]
    upcoming_events = shows[5:20]

    top_picks_html = "\n".join([generate_top_pick_html(show) for show in top_picks])
    upcoming_html = "\n".join([generate_upcoming_event_html(show) for show in upcoming_events])

    with open(UPCOMING_HTML_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace('<!-- TOP_PICKS_PLACEHOLDER -->', top_picks_html)
    content = content.replace('<!-- UPCOMING_EVENTS_PLACEHOLDER_CREEK -->', upcoming_html)

    with open(UPCOMING_HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully updated upcoming.html.")

def update_shows_page(shows):
    """Updates the shows.html file."""
    print("Updating shows.html...")
    
    shows_html = "\n".join([generate_recurring_show_html(show) for show in shows])

    with open(SHOWS_HTML_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('<!-- SHOWS_PLACEHOLDER -->', shows_html)

    with open(SHOWS_HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully updated shows.html.")

def main():
    print("Generating HTML for shows...")
    shows = get_all_shows_with_images()

    if not shows:
        print("No shows with images found in the database.")
        return

    update_index_page(shows)
    update_upcoming_page(shows)
    update_shows_page(shows)


if __name__ == "__main__":
    main()
