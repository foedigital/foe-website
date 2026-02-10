import sqlite3
from datetime import datetime, timedelta
import re
from pathlib import Path

# Date filtering - only include shows within the next 10 days
TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
CURRENT_YEAR = TODAY.year
TWO_WEEKS_FROM_NOW = TODAY + timedelta(days=10)

def parse_show_date(event_date):
    """Parse event_date string and return a datetime object or None."""
    if not event_date:
        return None

    # Handle formats like "Tuesday, Dec 16" or "Wednesday, Dec 24"
    date_str = event_date
    if ', ' in event_date:
        date_str = event_date.split(', ')[1]  # Get "Dec 16" part

    # Skip if it's just a day name like "Tuesday"
    if date_str in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        return None

    # Try to parse with full year already included (e.g., "January 15, 2026")
    try:
        date_obj = datetime.strptime(date_str, "%B %d, %Y")
        return date_obj
    except ValueError:
        pass

    # Try to parse "Dec 15" or "Dec 16" format with current year
    try:
        date_obj = datetime.strptime(f"{CURRENT_YEAR} {date_str}", "%Y %b %d")
        return date_obj
    except ValueError:
        pass

    # Try with full month name
    try:
        date_obj = datetime.strptime(f"{CURRENT_YEAR} {date_str}", "%Y %B %d")
        return date_obj
    except ValueError:
        pass

    return None

def is_show_in_date_range(event_date):
    """Check if show date is today or within the next 2 weeks."""
    parsed_date = parse_show_date(event_date)

    # If we can't parse the date, include the show (it might be a recurring show)
    if parsed_date is None:
        return True

    # Check if the show is today or in the future (within 2 weeks)
    return TODAY <= parsed_date <= TWO_WEEKS_FROM_NOW

# Known free shows (scraped from venue websites)
FREE_SHOWS = [
    # Creek and Cave free shows
    'the monday gamble mic',
    'monday gamble',
    'monday night gimmick mic',
    'gimmick mic',
    'dunk tank',
    'hood therapy',
    'off the cuff',
    'wild west wednesdays',
    'bear arms',
    'word up',
    'new joke saturday',
    'new joke monday',
    'the creek and the cave open mic',
    'creek open mic',
    # Note: removed generic 'open mic' - Cap City open mic is $5
    'banana phone',
    'writers room',
    # Gnar Bar - only Crowd Control is free (pay what you want)
    'crowd control',
]

# Shows that are sold out (will be updated by scraper)
SOLD_OUT_SHOWS = []

# Correct day mappings for Creek and Cave shows
# VERIFIED from ShowClix on 2025-12-16
CREEK_CAVE_DAYS = {
    # Monday (verified)
    'the monday gamble mic': 'Monday',
    'clocked out comedy': 'Monday',
    'new joke monday': 'Monday',
    'monday night gimmick mic': 'Monday',
    # Tuesday (verified)
    'dunk tank': 'Tuesday',
    'optimum noctis': 'Tuesday',
    'hood therapy tuesdays': 'Tuesday',
    # Wednesday (verified)
    'off the cuff': 'Wednesday',
    'absolute show': 'Wednesday',
    'the forge': 'Wednesday',
    'wild west wednesdays': 'Wednesday',
    'comedians on the rise': 'Wednesday',
    # Thursday (verified)
    'bear arms: open mic': 'Thursday',
    'bear arms open mic': 'Thursday',
    'gator tales': 'Thursday',
    'unscripted: a tag team comedy show': 'Thursday',
    'unscripted': 'Thursday',
    'word up! open mic': 'Thursday',
    'word up open mic': 'Thursday',
    # Friday (verified)
    'show us the big naturals': 'Friday',
    'roast battle: austin': 'Friday',
    'roast battle austin': 'Friday',
    'laughs with the staff': 'Friday',
    # Saturday (verified)
    'new joke saturday open mic': 'Saturday',
    'new joke saturday': 'Saturday',
    'creek featured': 'Saturday',
    'main course comedy': 'Saturday',
    'freaky': 'Saturday',
    'christmas at the creek': 'Saturday',
    'christmas at the creek!': 'Saturday',
    # Sunday (verified)
    "writers' room": 'Sunday',
    'writers room': 'Sunday',
    'the creek and the cave open mic': 'Sunday',
    'banana phone': 'Sunday',
    # Special events (date-specific)
    'algonauts': 'Monday',
    'the roast of santa': 'Tuesday',
    'king of the creek': 'Tuesday',
    'comedy powered by bilt': 'Monday',
    'the roast of 2025': 'Tuesday',
    "lukas mccrary's nye comedy spectacular": 'Wednesday',
}

# Velveeta Room day mappings (for recurring shows without specific dates)
VELVEETA_DAYS = {
    # Weekly recurring shows
    'cocktails and comedy': 'Sunday',
    'cocktails and comedy!': 'Sunday',
    'the hump': 'Wednesday',
    'the hump!': 'Wednesday',
    'power bomb': 'Monday',
    'power bomb!': 'Monday',
    'powerbomb': 'Monday',
    'powerbomb!': 'Monday',
    'ladies night': 'Wednesday',
    'ladies night!': 'Wednesday',
    'austin all-stars': 'Thursday',
    'austin all-stars!': 'Thursday',
    'all-star weekend': 'Friday',
    'all-star weekend!': 'Friday',
    'timeless comedy': 'Friday',
    # Other shows
    'the joke of painting': 'Friday',
    'velveeta room wrestling': 'Saturday',
    'the christmas hangover comedy show': 'Friday',
    'arielle isaac norman': 'Saturday',
    'joe begley': 'Saturday',
    'mike macrae': 'Friday',
    'doug mellard': 'Saturday',
}

# Creek and Cave event URL mappings
CREEK_CAVE_URLS = {
    'the monday gamble mic': '/events/the-monday-gamble-mic',
    'clocked out comedy': '/events/clocked-out-comedy',
    'new joke monday': '/events/new-joke-monday',
    'monday night gimmick mic': '/events/monday-night-gimmick-mic',
    'dunk tank': '/events/dunk-tank-mic',
    'optimum noctis': '/events/optimumnoctis',
    'hood therapy tuesdays': '/events/hood-therapy-tuesdays',
    'off the cuff': '/events/off-the-cuff',
    'absolute show': '/events/absolute-show-',
    'the forge': '/events/the-forge',
    'wild west wednesdays': '/events/wild-west-wednesdays',
    'bear arms: open mic': '/events/bear-arms-open-mic',
    'bear arms open mic': '/events/bear-arms-open-mic',
    'gator tales': '/events/gator-tales',
    'unscripted: a tag team comedy show': '/events/unscripted-comedy',
    'unscripted': '/events/unscripted-comedy',
    'word up! open mic': '/events/word-up-open-mic',
    'word up open mic': '/events/word-up-open-mic',
    'creek featured': '/events/creekfeat',
    'show us the big naturals': '/events/show-us-the-big-naturals',
    'new joke saturday open mic': '/events/new-joke-saturday',
    'new joke saturday': '/events/new-joke-saturday',
    'christmas at the creek': '/events/christmas-at-the-creek',
    'christmas at the creek!': '/events/christmas-at-the-creek',
    'christmas': '/events/christmas-at-the-creek',
    'main course comedy': '/events/main-course-comedy',
    'freaky': '/events/freaky-comedy',
    "writers' room": '/events/writersroom',
    'writers room': '/events/writersroom',
    'the creek and the cave open mic': '/events/creek-mic',
    'banana phone': '/events/banana-phone',
    'laughs with the staff': '/events/laughs-with-the-staff',
    'algonauts': '/events/algonauts',
    'the roast of santa': '/events/the-roast-of-santa',
    'king of the creek': '/events/king-of-the-creek',
    'roast battle: austin': '/events/roast-battle-austin',
    'roast battle austin': '/events/roast-battle-austin',
    'comedians on the rise': '/events/comedians-on-the-rise',
    'comedy powered by bilt': '/events/bilt-comedy',
    'the roast of 2025': '/events/the-roast-of-2025',
    "lukas mccrary's nye comedy spectacular": '/events/lukas-mccrary-nye',
}

# Velveeta Room URL mappings (scraped from website)
VELVEETA_URLS = {
    'cocktails and comedy': '/velv/cocktails-and-comedy7',
    'the hump': '/velv/the-hump5',
    'the joke of painting': '/velv/the-joke-of-painting',
    'velveeta room wrestling': '/velv/vrw-comedy-championship',
    'the christmas hangover comedy show': '/velv/the-christmas-hangover2',
    'christmas hangover': '/velv/the-christmas-hangover2',
    'timeless comedy': '/velv/timeless-comedy1',
    'powerbomb': '/velv/powerbomb7',
    'powerbomb!': '/velv/powerbomb7',
    'power bomb': '/velv/power-bombd29',
    'austin all stars': '/velv/austin-all-stars345g',
    'austin all-stars': '/velv/austin-all-stars345g',
}

# Rozco's Comedy day mappings
# VERIFIED from SimpleTix on 2025-12-16
ROZCOS_DAYS = {
    'austin all-star comedy': 'Saturday',  # Also runs Tuesdays
    'eastside open mic': 'Wednesday',  # FIXED: was Tuesday
    'best of austin comedy': 'Thursday',  # FIXED: was Wednesday
    'candlelight comedy': 'Thursday',  # FIXED: was Wednesday
    'friday night laughs': 'Friday',
    'new faces of austin comedy': 'Saturday',
    'tuesday gigante': 'Tuesday',
    'kill or spill': 'Monday',
    'lez be friends': 'Monday',
    'dressed to kill': 'Saturday',
    'your new favorite comic': 'Thursday',
    'the filthy show': 'Saturday',
    'circus fire': 'Saturday',
    'sweet sunday comedy': 'Sunday',
}

# Rozco's Comedy free shows
ROZCOS_FREE_SHOWS = [
    'eastside open mic',
]

# Speakeasy day mappings
SPEAKEASY_DAYS = {
    'the thursday special': 'Thursday',
    'sunday service': 'Sunday',
}

# Speakeasy URL mappings (Eventbrite direct ticket links)
SPEAKEASY_URLS = {
    'the thursday special': 'https://www.eventbrite.com/e/the-thursday-special-tickets-1042163919337',
    'sunday service': 'https://www.eventbrite.com/e/sunday-service-stand-up-comedy-show-tickets-1308986797749',
}

# Pop Up venues (Bull's Pub, Gnar Bar, Speakeasy, Secret Level)
POP_UP_VENUES = ["bull's pub", "gnar bar", "speakeasy", "secret level"]

# Venue location descriptions for tooltips
VENUE_DESCRIPTIONS = {
    'cap city comedy': 'Austin\'s premier comedy club since 1986',
    'comedy mothership': '&quot;the house that DMT built&quot; - Kyle Kinane',
    'creek and the cave': 'Located just off Dirty 6th.. Beware of bears',
    'the velveeta room': 'Historic club next door to Esther\'s Follies on 6th',
    'rozco\'s comedy': 'East Austin\'s neighborhood comedy spot',
    'east austin comedy club': 'BYOB comedy on East 6th - non-stop laughs!',
    'vulcan gas company': 'Historic 6th Street venue - comedy, music &amp; more',
    'black rabbit comedy': 'Underground comedy in Austin',
    'pop up': 'Every bar\'s a comedy club in ATX',
    'secret level': 'Secret comedy pop-ups across ATX',
}

# Cap City Comedy URL
CAPCITY_URL = 'https://www.capcitycomedy.com/calendar'

# Rozco's Comedy URL mappings (SimpleTix direct ticket links)
ROZCOS_URLS = {
    'austin all-star comedy': 'https://www.simpletix.com/e/austin-all-star-comedy-tickets-249886',
    'eastside open mic': 'https://www.simpletix.com/e/12-17-eastside-open-mic-tickets-245381',
    'best of austin comedy': 'https://www.simpletix.com/e/12-18-best-of-austin-comedy-tickets-245375',
    'candlelight comedy': 'https://www.simpletix.com/e/12-18-candlelight-comedy-tickets-245384',
    'friday night laughs': 'https://www.simpletix.com/e/12-19-friday-night-laughs-7pm-tickets-249044',
    'new faces of austin comedy': 'https://www.simpletix.com/e/new-faces-of-austin-comedy-tickets-248564',
    'tuesday gigante': 'https://www.simpletix.com/e/tuesday-gigante-tickets-248656',
    'kill or spill': 'https://www.simpletix.com/e/12-9-kill-or-spill-tickets-240508',
    'lez be friends': 'https://www.simpletix.com/e/12-2-lez-be-friends-comedy-blind-dating-sh-tickets-244863',
    'dressed to kill': 'https://www.simpletix.com/e/dressed-to-kill-halloween-party-tickets-238205',
    'your new favorite comic': 'https://www.simpletix.com/e/10-16-your-new-favorite-comic-tickets-237530',
    'the filthy show': 'https://www.simpletix.com/e/the-filthy-show-tickets-246504',
    'circus fire': 'https://www.simpletix.com/e/11-1-circus-fire-stand-up-comedy-show-tickets-240102',
    'sweet sunday comedy': 'https://www.simpletix.com/e/sweet-sunday-comedy-tickets-241384',
}

# Venue base URLs
MOTHERSHIP_URL = 'https://comedymothership.com/shows'
BULLS_PUB_URL = 'https://www.eventbrite.com/e/stand-up-comedy-show-bulls-pub-wedsthursat-at-830pm-tickets-1039732296287'
GNAR_BAR_URL = 'https://gnarbaratx.com/events'
ROZCOS_URL = 'https://rozcoscomedyclub.simpletix.com/'
EAST_AUSTIN_URL = 'https://eastaustincomedy.com/'
VULCAN_URL = 'https://www.vulcanatx.com/'
BLACK_RABBIT_URL = 'https://www.eventbrite.com/e/black-rabbit-underground-comedy-tickets-1442073413399'
SECRET_LEVEL_URL = 'https://www.eventbrite.com/o/secret-level-productions-45772952383'

def is_free_show(name, venue):
    name_lower = name.lower()
    venue_lower = venue.lower()

    # Bulls Pub is always free
    if "bull" in venue_lower:
        return True

    # Speakeasy shows are always free
    if "speakeasy" in venue_lower:
        return True

    # Check against free shows list
    for free in FREE_SHOWS:
        if free in name_lower:
            return True

    # Check Rozco's free shows
    if 'rozco' in venue_lower:
        for free in ROZCOS_FREE_SHOWS:
            if free in name_lower:
                return True

    return False

def is_sold_out(name, venue):
    """Check if a show is sold out."""
    name_lower = name.lower()
    for sold_out_show in SOLD_OUT_SHOWS:
        if sold_out_show.lower() in name_lower:
            return True
    return False

def get_correct_day(show_name, venue_name, event_date):
    """Get the correct day of week for a show."""
    name_lower = show_name.lower().strip()
    venue_lower = venue_name.lower()

    # PRIORITY 1: If event_date contains scraped day (e.g., "Wednesday, Dec 24"), use it
    if event_date:
        # Check for format "Wednesday, Dec 24"
        if ', ' in event_date:
            day_part = event_date.split(', ')[0]
            if day_part in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                return day_part

        # Check if event_date is just a day name
        if event_date in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            return event_date

    # PRIORITY 2: Use hardcoded mappings as fallback for venues without scraped dates

    # Creek and Cave - use hardcoded mappings
    if 'creek' in venue_lower:
        if name_lower in CREEK_CAVE_DAYS:
            return CREEK_CAVE_DAYS[name_lower]
        # Try partial match
        for key, day in CREEK_CAVE_DAYS.items():
            if key in name_lower or name_lower in key:
                return day

    # Velveeta Room - use hardcoded mappings
    if 'velveeta' in venue_lower:
        if name_lower in VELVEETA_DAYS:
            return VELVEETA_DAYS[name_lower]
        for key, day in VELVEETA_DAYS.items():
            if key in name_lower or name_lower in key:
                return day

    # Rozco's Comedy - use hardcoded mappings
    if 'rozco' in venue_lower:
        if name_lower in ROZCOS_DAYS:
            return ROZCOS_DAYS[name_lower]
        for key, day in ROZCOS_DAYS.items():
            if key in name_lower or name_lower in key:
                return day

    # Speakeasy - use hardcoded mappings
    if 'speakeasy' in venue_lower:
        if name_lower in SPEAKEASY_DAYS:
            return SPEAKEASY_DAYS[name_lower]
        for key, day in SPEAKEASY_DAYS.items():
            if key in name_lower or name_lower in key:
                return day

    # Mothership - extract day from event name
    if 'mothership' in venue_lower:
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            if day.upper() in show_name.upper():
                return day

    return event_date or ''

def get_day_from_date(date_str):
    if not date_str:
        return ''
    day_map = {
        'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
        'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
    }
    date_lower = date_str.lower()
    if date_lower in day_map:
        return day_map[date_lower]
    # Try with current year first
    try:
        date_obj = datetime.strptime(f"{CURRENT_YEAR} {date_str}", "%Y %b %d")
        return date_obj.strftime('%a').lower()
    except:
        pass
    # Try with full month name
    try:
        date_obj = datetime.strptime(f"{CURRENT_YEAR} {date_str}", "%Y %B %d")
        return date_obj.strftime('%a').lower()
    except:
        return ''

def get_day_from_name(name):
    name_upper = name.upper()
    days = {
        'MONDAY': 'mon', 'TUESDAY': 'tue', 'WEDNESDAY': 'wed',
        'THURSDAY': 'thu', 'FRIDAY': 'fri', 'SATURDAY': 'sat', 'SUNDAY': 'sun'
    }
    for day_name, day_abbr in days.items():
        if day_name in name_upper:
            return day_abbr
    return ''

def venue_to_id(venue_name):
    return venue_name.lower().replace(' ', '-').replace("'", '').replace('&', 'and')

def is_popup_venue(venue_name):
    """Check if venue should be grouped under Pop Up category."""
    venue_lower = venue_name.lower()
    for popup in POP_UP_VENUES:
        if popup in venue_lower:
            return True
    return False

def get_filter_venue_id(venue_name):
    """Get the venue ID for filtering (Pop Up venues use 'pop-up')."""
    if is_popup_venue(venue_name):
        return 'pop-up'
    return venue_to_id(venue_name)

def extract_show_name_from_poster(text):
    if not text:
        return None
    match = re.search(r'Poster for ([^,]+)', text)
    if match:
        return match.group(1).strip()
    return text

def get_event_url(show_name, venue_name, venue_base_url, source_url=''):
    name_lower = show_name.lower().strip()

    # For Cap City, use the source_url from the database (specific ticket page)
    if 'cap city' in venue_name.lower() and source_url:
        # Remove the hash fragment we added for uniqueness
        clean_url = source_url.split('#')[0]
        return clean_url

    if 'creek' in venue_name.lower():
        # Use Creek website URL from scraper if available (preferred)
        if source_url and 'creekandcave.com/events/' in source_url:
            return source_url
        # Fall back to hardcoded mapping
        if name_lower in CREEK_CAVE_URLS:
            return 'https://www.creekandcave.com' + CREEK_CAVE_URLS[name_lower]
        for key, path in CREEK_CAVE_URLS.items():
            if key in name_lower or name_lower in key:
                return 'https://www.creekandcave.com' + path
        # Fall back to ShowClix ticket URL
        if source_url and 'showclix.com' in source_url:
            return source_url
        slug = re.sub(r'[^\w\s-]', '', name_lower)
        slug = re.sub(r'[\s_]+', '-', slug).strip('-')
        return f'https://www.creekandcave.com/events/{slug}'

    elif 'mothership' in venue_name.lower():
        return MOTHERSHIP_URL

    elif 'velveeta' in venue_name.lower():
        # Use the SeatEngine ticket URL from the scraper
        if source_url and 'seatengine.com' in source_url:
            return source_url
        # Fallback to hardcoded URLs
        if name_lower in VELVEETA_URLS:
            return 'https://www.thevelveetaroom.com' + VELVEETA_URLS[name_lower]
        for key, path in VELVEETA_URLS.items():
            if key in name_lower or name_lower in key:
                return 'https://www.thevelveetaroom.com' + path
        slug = re.sub(r'[^\w\s]', '', name_lower).replace(' ', '')
        return f'https://www.thevelveetaroom.com/velv/{slug}'

    elif 'bull' in venue_name.lower():
        return BULLS_PUB_URL

    elif 'gnar' in venue_name.lower():
        return GNAR_BAR_URL

    elif 'rozco' in venue_name.lower():
        # Use the per-show SimpleTix ticket URL from the scraper
        if source_url and 'simpletix.com' in source_url:
            return source_url
        return ROZCOS_URL

    elif 'speakeasy' in venue_name.lower():
        if name_lower in SPEAKEASY_URLS:
            return SPEAKEASY_URLS[name_lower]
        for key, url in SPEAKEASY_URLS.items():
            if key in name_lower or name_lower in key:
                return url
        return 'https://www.eventbrite.com'

    elif 'cap city' in venue_name.lower():
        return CAPCITY_URL

    elif 'east austin' in venue_name.lower():
        return EAST_AUSTIN_URL

    elif 'vulcan' in venue_name.lower():
        # Use the source_url from scraper (ticketsauce ticket page)
        if source_url:
            # Remove the hash fragment we added for uniqueness
            clean_url = source_url.split('#')[0]
            return clean_url
        return VULCAN_URL

    elif 'sunset' in venue_name.lower():
        # Use the source_url from scraper (SquadUP event-id ticket page)
        if source_url and 'event-id=' in source_url:
            return source_url
        return 'https://www.sunsetstripatx.com/events'

    elif 'paramount' in venue_name.lower():
        # Use the source_url from scraper (specific ticket page)
        if source_url:
            return source_url
        return 'https://tickets.austintheatre.org/events?kid=4'

    elif 'black rabbit' in venue_name.lower():
        return BLACK_RABBIT_URL

    elif 'secret level' in venue_name.lower():
        if source_url and 'eventbrite.com' in source_url:
            return source_url
        return SECRET_LEVEL_URL

    return venue_base_url

# Get show data from database
conn = sqlite3.connect('comedy_images.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("""
    SELECT i.event_name, i.event_date, i.local_path, i.show_time, i.source_url, v.name as venue_name, v.url as venue_url
    FROM images i
    JOIN venues v ON i.venue_id = v.id
    WHERE i.event_name IS NOT NULL AND i.event_name != ''
    ORDER BY v.name, i.event_name
""")

shows = []
seen = set()
venues = set()

for row in cursor.fetchall():
    name = row['event_name'].strip()
    event_date = row['event_date'] or ''

    # Skip shows that are in the past or more than 2 weeks out
    if not is_show_in_date_range(event_date):
        continue

    clean_name = name
    if '\n' in name:
        parts = name.split('\n')
        clean_name = parts[1].strip() if len(parts) > 1 else parts[0].strip()
    if 'Poster for' in name:
        extracted = extract_show_name_from_poster(name)
        if extracted:
            clean_name = extracted

    venue = row['venue_name']
    show_time = row['show_time'] or ''
    source_url = row['source_url'] or ''

    # For venues with same show on multiple days/times, include date+time in key
    if 'bull' in venue.lower() or 'gnar' in venue.lower() or 'cap city' in venue.lower() or 'secret level' in venue.lower():
        key = (clean_name.lower(), venue, event_date, show_time)
    else:
        key = (clean_name.lower(), venue)

    if key in seen:
        continue
    seen.add(key)

    # Use correct day mappings first, then fall back to date parsing
    correct_day = get_correct_day(clean_name, venue, event_date)
    day = ''
    if correct_day:
        # Check if correct_day is actually a day name (not a month)
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        correct_day_lower = correct_day.lower()
        if correct_day_lower in day_names or any(correct_day_lower.startswith(d) for d in day_names):
            day = correct_day[:3].lower()  # Convert to 'mon', 'tue', etc.
        else:
            # correct_day is a date like "Jan 29", need to calculate the day
            day = get_day_from_date(correct_day) or get_day_from_name(name)

    # If still no day, try to parse from event_date or calculate from date
    if not day:
        day = get_day_from_date(event_date) or get_day_from_name(name)

    # Last resort: if we have a date like "Jan 29", calculate the day of week
    if not day and event_date:
        parsed = parse_show_date(event_date)
        if parsed:
            day = parsed.strftime('%a').lower()
    is_free = is_free_show(clean_name, venue)
    sold_out = is_sold_out(clean_name, venue)
    venues.add(venue)
    event_url = get_event_url(clean_name, venue, row['venue_url'], source_url)

    image_path = row['local_path'].replace('\\', '/')
    has_image = Path(image_path).exists()

    shows.append({
        'name': clean_name,
        'date': event_date,
        'time': show_time,
        'image': image_path if has_image else '',
        'venue': venue,
        'venue_id': get_filter_venue_id(venue),
        'url': event_url,
        'day': day,
        'is_free': is_free,
        'is_sold_out': sold_out,
        'has_image': has_image
    })

conn.close()

# Sort shows chronologically by actual date
def get_date_for_sort(show):
    """Get a sortable date value from show data. Shows closest to today come first."""
    event_date = show.get('date', '')

    # Try to parse the actual date
    parsed = parse_show_date(event_date)
    if parsed:
        return parsed

    # If no specific date, use day of week mapping to estimate next occurrence
    day_abbr = show.get('day', '')
    if day_abbr:
        days_order = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        day_abbr = day_abbr.lower()
        if day_abbr in days_order:
            target_day = days_order.index(day_abbr)
            today = datetime.now()
            current_day = today.weekday()
            days_ahead = (target_day - current_day) % 7
            if days_ahead == 0:
                # If it's today, check if the show time has passed
                days_ahead = 0
            return today + timedelta(days=days_ahead)

    # Fallback: put shows without dates at the end
    return datetime.max

def parse_time_for_sort(time_str):
    """Convert time string to sortable value."""
    if not time_str:
        return 99
    try:
        # Handle formats like "8:00 PM", "10:30 PM", "12:00 AM"
        time_str = time_str.strip().upper()
        if 'AM' in time_str:
            hour = int(time_str.split(':')[0])
            if hour == 12:
                hour = 0
        else:  # PM
            hour = int(time_str.split(':')[0])
            if hour != 12:
                hour += 12
        return hour
    except:
        return 99

# Sort shows chronologically: first by date, then by time, then by name
shows.sort(key=lambda s: (get_date_for_sort(s), parse_time_for_sort(s['time']), s['name']))

# Generate venue filter buttons (group Pop Up venues together)
filter_venues = set()
for v in venues:
    if is_popup_venue(v):
        filter_venues.add('Pop Up')
    else:
        filter_venues.add(v)

def get_venue_tooltip(venue_name):
    """Get tooltip description for a venue."""
    key = venue_name.lower()
    if key in VENUE_DESCRIPTIONS:
        return VENUE_DESCRIPTIONS[key]
    return ''

venue_buttons = []
for v in sorted(filter_venues):
    tooltip = get_venue_tooltip(v)
    tooltip_attr = f' title="{tooltip}"' if tooltip else ''
    if v == 'Pop Up':
        venue_buttons.append(f'<button class="filter-btn venue-btn popup-btn" data-filter="venue" data-value="pop-up"{tooltip_attr}>{v}</button>')
    else:
        venue_buttons.append(f'<button class="filter-btn venue-btn" data-filter="venue" data-value="{venue_to_id(v)}"{tooltip_attr}>{v}</button>')

# Helper function to get next occurrence of a day
def get_next_date_for_day(day_abbr):
    """Calculate the next occurrence of a given day of the week."""
    if not day_abbr:
        return ''

    days_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
    day_lower = day_abbr.lower()[:3]

    if day_lower not in days_map:
        return ''

    target_day = days_map[day_lower]
    today = datetime.now()
    today_weekday = today.weekday()

    # Calculate days until next occurrence (0 = today if it's that day)
    days_ahead = (target_day - today_weekday) % 7
    next_date = today + timedelta(days=days_ahead)

    return next_date.strftime('%b %d')  # e.g., "Dec 16"

# Generate show cards HTML
show_cards = []
for show in shows:
    # Check if this is a special "See All Shows" entry
    is_see_all = 'see all shows' in show['name'].lower()

    # Parse the date field which may contain "Wednesday, Dec 24" or just "Wednesday" or "Dec 24"
    event_date = show['date'] or ''
    day_abbr = show['day'].upper() if show['day'] else ''
    date_part = ''

    # Special handling for "See All Shows" entries
    if is_see_all:
        day_abbr = 'ALL'
        date_part = 'Multiple Dates'
    else:
        # Extract date part from combined format like "Wednesday, Dec 24"
        if ', ' in event_date:
            parts = event_date.split(', ', 1)
            date_part = parts[1] if len(parts) > 1 else ''
        elif event_date and event_date not in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            # It's just a date like "Dec 24"
            date_part = event_date

        # If no date part but we have a day, calculate the next occurrence
        if not date_part and day_abbr:
            date_part = get_next_date_for_day(day_abbr)

    # Create the day badge (orange bubble with abbreviated day)
    day_badge = f'<span class="day-badge">{day_abbr}</span>' if day_abbr else ''

    # Create the date text (plain text next to the badge)
    date_html = f'<span class="date-text">{date_part}</span>' if date_part else ''

    free_class = ' is-free' if show['is_free'] else ''
    sold_out_class = ' is-sold-out' if show['is_sold_out'] else ''
    price_data = 'free' if show['is_free'] else 'paid'
    no_image_class = ' no-image' if not show['has_image'] else ''
    bg_style = f"background-image: url('{show['image']}');" if show['has_image'] else ''

    time_html = f'<span class="show-time">{show["time"]}</span>' if show['time'] else ''

    card = f'''            <a href="{show['url']}" class="show-card{free_class}{sold_out_class}{no_image_class}" data-day="{show['day']}" data-price="{price_data}" data-venue="{show['venue_id']}" style="{bg_style}" target="_blank">
                <div class="show-card-content">
                    <div class="show-date-info">{day_badge}{date_html}</div>
                    <h3>{show['name']}</h3>
                    <span class="venue">{show['venue']}{time_html}</span>
                </div>
            </a>'''
    show_cards.append(card)

# Build HTML
html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shows - ATX Comedy</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="apple-touch-icon" href="/favicon.svg">
    <link rel="stylesheet" href="styles.css">
    <style>
        .filters {{
            background: rgba(20, 20, 20, 0.9);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 40px;
            backdrop-filter: blur(10px);
            border: 1px solid #2a2a2a;
        }}
        .filters h3 {{
            color: #f05a28;
            margin-bottom: 20px;
            font-size: 1.3rem;
        }}
        .filter-group {{
            margin-bottom: 20px;
        }}
        .filter-group:last-child {{
            margin-bottom: 0;
        }}
        .filter-group label.group-label {{
            display: block;
            color: #fff;
            font-weight: bold;
            margin-bottom: 12px;
            font-size: 1rem;
        }}
        .filter-options {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .filter-btn {{
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.2);
            color: #ccc;
            padding: 10px 18px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.95rem;
        }}
        .filter-btn:hover {{
            border-color: #f05a28;
            color: #f05a28;
        }}
        .venue-btn {{
            position: relative;
        }}
        .venue-btn[title]:hover::after {{
            content: attr(title);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.9);
            color: #fff;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: bold;
            white-space: nowrap;
            z-index: 100;
            margin-bottom: 8px;
            border: 1px solid #f05a28;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }}
        .venue-btn[title]:hover::before {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 6px solid transparent;
            border-top-color: #f05a28;
            margin-bottom: 2px;
            z-index: 100;
        }}
        .popup-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f05a28 100%);
            border: 2px solid #fff;
            color: #fff;
            font-weight: bold;
            animation: popupGlow 2s ease-in-out infinite;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }}
        .popup-btn:hover {{
            transform: scale(1.05);
            box-shadow: 0 0 20px rgba(118, 75, 162, 0.6);
            color: #fff;
            border-color: #fff;
        }}
        @keyframes popupGlow {{
            0%, 100% {{ box-shadow: 0 0 5px rgba(118, 75, 162, 0.4); }}
            50% {{ box-shadow: 0 0 15px rgba(118, 75, 162, 0.8), 0 0 25px rgba(240, 90, 40, 0.4); }}
        }}
        .filter-btn.active {{
            background: #f05a28;
            border-color: #f05a28;
            color: #fff;
            font-weight: bold;
        }}
        .clear-filters {{
            background: transparent;
            border: 2px solid #ff6b6b;
            color: #ff6b6b;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 15px;
        }}
        .clear-filters:hover {{
            background: #ff6b6b;
            color: #fff;
        }}
        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: #888;
            display: none;
        }}
        .no-results h3 {{
            color: #f05a28;
            margin-bottom: 10px;
        }}
        .show-card.hidden {{
            display: none;
        }}
        .show-date-info {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        .date-text {{
            color: #fff;
            font-size: 0.9rem;
            font-weight: 500;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
        }}
        .show-time {{
            color: #f05a28;
            font-size: 0.9rem;
            font-weight: 600;
            margin-left: 8px;
        }}
        .show-card.is-free::after {{
            content: 'FREE';
            position: absolute;
            top: 15px;
            left: 15px;
            background: #e74c3c;
            color: #fff;
            font-size: 1.1rem;
            font-weight: 900;
            width: 70px;
            height: 70px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transform: rotate(-15deg);
            border: 4px solid #fff;
            box-shadow: 0 4px 20px rgba(231, 76, 60, 0.6);
            z-index: 10;
            letter-spacing: 1px;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        }}
        .show-card.is-sold-out::before {{
            content: 'SOLD OUT';
            position: absolute;
            top: 15px;
            right: 15px;
            background: #333;
            color: #fff;
            font-size: 0.9rem;
            font-weight: 900;
            width: 80px;
            height: 80px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            transform: rotate(15deg);
            border: 4px solid #ff0000;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.8);
            z-index: 10;
            letter-spacing: 1px;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            line-height: 1.1;
        }}
        .show-card.is-sold-out {{
            opacity: 0.7;
        }}
        .show-card.no-image {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        }}
        @media (max-width: 768px) {{
            .filter-options {{
                gap: 8px;
            }}
            .filter-btn {{
                padding: 8px 14px;
                font-size: 0.85rem;
            }}
            .show-card.is-free::after {{
                width: 60px;
                height: 60px;
                font-size: 0.9rem;
            }}
        }}
    </style>
</head>
<body>
    <!-- Scroll Progress Bar -->
    <div class="scroll-progress" id="scroll-progress"></div>

    <!-- Custom Cursor (desktop only) -->
    <div class="custom-cursor" id="custom-cursor"></div>

    <!-- SVG Filter for wavy border effect -->
    <svg style="position: absolute; width: 0; height: 0;">
        <defs>
            <filter id="wavy">
                <feTurbulence type="turbulence" baseFrequency="0.02 0.05" numOctaves="2" result="turbulence">
                    <animate attributeName="baseFrequency" dur="3s" values="0.02 0.05;0.03 0.06;0.02 0.05" repeatCount="indefinite"/>
                </feTurbulence>
                <feDisplacementMap in="SourceGraphic" in2="turbulence" scale="8" xChannelSelector="R" yChannelSelector="G"/>
            </filter>
        </defs>
    </svg>
    <header>
        <nav>
            <button class="nav-toggle" aria-label="Menu">
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
            </button>
            <a href="index.html" class="logo">
                <img src="images/logo.jpg" alt="Funny Over Everything" class="logo-img">
                <div class="logo-text">
                    <span class="logo-main">Funny Over Everything</span>
                    <span class="logo-atx">ATX</span>
                </div>
            </a>
            <a href="https://www.instagram.com/foeatx/" class="nav-instagram" target="_blank" aria-label="Instagram">
                <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>
            </a>
            <div class="nav-menu">
                <ul class="nav-links">
                    <li><a href="index.html">Home</a></li>
                    <li><a href="shows.html" class="active">Shows</a></li>
                    <li><a href="resources.html">Resources</a></li>
                </ul>
                <div class="nav-social">
                    <a href="https://www.instagram.com/foeatx/" target="_blank">Instagram (@foeatx)</a>
                    <a href="mailto:foeatx@gmail.com">foeatx@gmail.com</a>
                </div>
            </div>
        </nav>
    </header>

    <section class="hero-animated">
        <div class="hero-wavy-bg"></div>
        <div class="hero-wavy-bg hero-wavy-bg-2"></div>
        <div class="hero-overlay"></div>
        <div class="hero-content">
            <h1>Find Your Show Here!</h1>
        </div>
    </section>

    <!-- Infinite Marquee -->
    <div class="marquee-container">
        <div class="marquee-content">
            <span class="highlight">COMEDY</span><span>&#8734;</span>
            <span class="highlight">AUSTIN</span><span>&#8734;</span>
            <span class="highlight">LAUGHS</span><span>&#8734;</span>
            <span>CREEK & CAVE</span><span>&#8734;</span>
            <span>MOTHERSHIP</span><span>&#8734;</span>
            <span>CAP CITY</span><span>&#8734;</span>
            <span>VELVEETA ROOM</span><span>&#8734;</span>
            <span>VULCAN</span><span>&#8734;</span>
            <span class="highlight">COMEDY</span><span>&#8734;</span>
            <span class="highlight">AUSTIN</span><span>&#8734;</span>
            <span class="highlight">LAUGHS</span><span>&#8734;</span>
            <span>CREEK & CAVE</span><span>&#8734;</span>
            <span>MOTHERSHIP</span><span>&#8734;</span>
            <span>CAP CITY</span><span>&#8734;</span>
            <span>VELVEETA ROOM</span><span>&#8734;</span>
            <span>VULCAN</span><span>&#8734;</span>
        </div>
    </div>

    <section class="featured-section">
        <h2 class="ribbon-title">Shows in ATX</h2>

        <div class="filters">
            <h3>Filter Shows</h3>
            <div class="filter-group">
                <label class="group-label">Price</label>
                <div class="filter-options" id="price-filters">
                    <button class="filter-btn" data-filter="price" data-value="free">Free Shows</button>
                </div>
            </div>
            <div class="filter-group">
                <label class="group-label">Day of Week</label>
                <div class="filter-options" id="day-filters">
                    <button class="filter-btn" data-filter="day" data-value="mon">Mon</button>
                    <button class="filter-btn" data-filter="day" data-value="tue">Tue</button>
                    <button class="filter-btn" data-filter="day" data-value="wed">Wed</button>
                    <button class="filter-btn" data-filter="day" data-value="thu">Thu</button>
                    <button class="filter-btn" data-filter="day" data-value="fri">Fri</button>
                    <button class="filter-btn" data-filter="day" data-value="sat">Sat</button>
                    <button class="filter-btn" data-filter="day" data-value="sun">Sun</button>
                </div>
            </div>
            <div class="filter-group">
                <label class="group-label">Venue</label>
                <div class="filter-options" id="venue-filters">
                    {chr(10).join('                    ' + btn for btn in venue_buttons)}
                </div>
            </div>
            <button class="clear-filters" onclick="clearAllFilters()">Clear All Filters</button>
        </div>

        <div class="no-results" id="no-results">
            <h3>No shows found</h3>
            <p>Try adjusting your filters to find more shows.</p>
        </div>

        <div class="show-list" id="show-list">
{chr(10).join(show_cards)}
        </div>
    </section>

    <section class="add-show-cta">
        <p>Want to add your show to this page? Shoot me an email!</p>
        <a href="mailto:foeatx@gmail.com" class="btn email-btn">foeatx@gmail.com</a>
    </section>

    <footer>
        <p>Funny Over Everything</p>
        <p style="margin-top: 20px; font-size: 0.9rem;">&copy; 2024 Funny Over Everything. All rights reserved.</p>
    </footer>

    <script>
        const filterBtns = document.querySelectorAll('.filter-btn');
        const showCards = document.querySelectorAll('.show-card');
        const noResults = document.getElementById('no-results');
        // Multi-select arrays for day and venue, single value for price
        let activeFilters = {{ day: [], price: null, venue: [] }};

        filterBtns.forEach(btn => {{
            btn.addEventListener('click', () => {{
                const filterType = btn.dataset.filter;
                const filterValue = btn.dataset.value;

                if (filterType === 'price') {{
                    // Price stays single-select
                    if (btn.classList.contains('active')) {{
                        btn.classList.remove('active');
                        activeFilters.price = null;
                    }} else {{
                        btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                        activeFilters.price = filterValue;
                    }}
                }} else {{
                    // Day and venue are multi-select
                    if (btn.classList.contains('active')) {{
                        btn.classList.remove('active');
                        activeFilters[filterType] = activeFilters[filterType].filter(v => v !== filterValue);
                    }} else {{
                        btn.classList.add('active');
                        activeFilters[filterType].push(filterValue);
                    }}
                }}
                applyFilters();
            }});
        }});

        function applyFilters() {{
            let visibleCount = 0;
            showCards.forEach(card => {{
                let show = true;
                // Day filter - show if no days selected OR card's day is in selected days
                if (activeFilters.day.length > 0 && !activeFilters.day.includes(card.dataset.day)) show = false;
                // Price filter - single select
                if (activeFilters.price && card.dataset.price !== activeFilters.price) show = false;
                // Venue filter - show if no venues selected OR card's venue is in selected venues
                if (activeFilters.venue.length > 0 && !activeFilters.venue.includes(card.dataset.venue)) show = false;
                if (show) {{
                    card.classList.remove('hidden');
                    visibleCount++;
                }} else {{
                    card.classList.add('hidden');
                }}
            }});
            noResults.style.display = visibleCount === 0 ? 'block' : 'none';
        }}

        function clearAllFilters() {{
            filterBtns.forEach(btn => btn.classList.remove('active'));
            activeFilters = {{ day: [], price: null, venue: [] }};
            applyFilters();
        }}
    </script>

    <!-- CDN Scripts -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@studio-freight/lenis@1.0.42/dist/lenis.min.js"></script>

    <script>
    // Initialize Lenis Smooth Scrolling
    const lenis = new Lenis({{
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        smooth: true,
        smoothTouch: false,
    }});

    function raf(time) {{
        lenis.raf(time);
        requestAnimationFrame(raf);
    }}
    requestAnimationFrame(raf);

    // Scroll Progress Bar
    const scrollProgressBar = document.getElementById('scroll-progress');
    window.addEventListener('scroll', () => {{
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = (scrollTop / docHeight) * 100;
        scrollProgressBar.style.width = scrollPercent + '%';
    }});

    // Custom Cursor (Desktop Only)
    const customCursor = document.getElementById('custom-cursor');
    if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {{
        document.addEventListener('mousemove', (e) => {{
            customCursor.style.left = e.clientX + 'px';
            customCursor.style.top = e.clientY + 'px';
            customCursor.classList.add('visible');
        }});

        document.addEventListener('mouseleave', () => {{
            customCursor.classList.remove('visible');
        }});

        const interactiveElements = document.querySelectorAll('a, button, .show-card, .btn, .filter-btn');
        interactiveElements.forEach(el => {{
            el.addEventListener('mouseenter', () => customCursor.classList.add('hover'));
            el.addEventListener('mouseleave', () => customCursor.classList.remove('hover'));
        }});
    }}

    // Add glow-hover and card-lift to show cards
    document.querySelectorAll('.show-card').forEach(card => {{
        card.classList.add('glow-hover', 'card-lift');
    }});

    // Hamburger menu toggle
    document.querySelector('.nav-toggle').addEventListener('click', function() {{
        this.classList.toggle('active');
        document.querySelector('.nav-menu').classList.toggle('active');
    }});
    </script>
</body>
</html>'''

with open('shows.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Created shows.html with {len(shows)} shows!")
print(f"Venues: {', '.join(sorted(venues))}")
print(f"Free shows: {sum(1 for s in shows if s['is_free'])}")
print(f"Paid shows: {sum(1 for s in shows if not s['is_free'])}")

# ============================================
# UPDATE INDEX.HTML FEATURED SHOWS
# ============================================

def generate_featured_show_card(show):
    """Generate a show-item-v2 card for the homepage."""
    day_abbr = show['day'].upper() if show['day'] else ''

    # Get date part
    event_date = show['date'] or ''
    date_part = ''
    if ', ' in event_date:
        parts = event_date.split(', ', 1)
        date_part = parts[1] if len(parts) > 1 else ''
    elif event_date and event_date not in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        date_part = event_date
    if not date_part and day_abbr:
        date_part = get_next_date_for_day(day_abbr)

    time_html = f' <span class="time-text">{show["time"]}</span>' if show['time'] else ''
    bg_style = f"background-image: url('{show['image']}');" if show['has_image'] else ''

    return f'''<div class="show-item-v2 card-lift glow-hover" data-tilt data-tilt-max="8" data-tilt-speed="400" data-tilt-glare data-tilt-max-glare="0.2" style="{bg_style}">
    <div class="show-overlay">
        <div class="show-date-info"><span class="day-badge">{day_abbr}</span><span class="date-text">{date_part}</span></div>
        <h3>{show['name']}</h3>
        <span class="venue">{show['venue']}{time_html}</span>
        <div class="show-details">
            <a href="{show['url']}" class="btn-v2 magnetic-btn btn-ripple" target="_blank">Tickets</a>
        </div>
    </div>
</div>'''

# Get top 5 shows with images for featured section (prioritize variety of venues)
featured_shows = []
venues_used = set()
for show in shows:
    if show['has_image'] and 'see all' not in show['name'].lower():
        # Try to get variety of venues
        if show['venue'] not in venues_used or len(featured_shows) < 5:
            featured_shows.append(show)
            venues_used.add(show['venue'])
        if len(featured_shows) >= 5:
            break

# If we don't have 5 yet, fill with any shows that have images
if len(featured_shows) < 5:
    for show in shows:
        if show['has_image'] and show not in featured_shows and 'see all' not in show['name'].lower():
            featured_shows.append(show)
            if len(featured_shows) >= 5:
                break

# Generate featured show cards HTML
featured_cards = [generate_featured_show_card(show) for show in featured_shows[:5]]
featured_html = '\n\n'.join(featured_cards)

# Read current index.html
try:
    with open('index.html', 'r', encoding='utf-8') as f:
        index_content = f.read()

    # Find and replace the featured shows section
    # Pattern: from '<div class="show-list stagger-children">' to the closing '</div>' before '</div></div></section>'
    import re
    pattern = r'(<div class="show-list stagger-children">)\s*(.*?)\s*(</div>\s*</div>\s*</section>\s*<section class="faq-section)'

    replacement = f'''\\1

{featured_html}

            \\3'''

    new_content = re.sub(pattern, replacement, index_content, flags=re.DOTALL)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Updated index.html with {len(featured_shows[:5])} featured shows!")
except Exception as e:
    print(f"Warning: Could not update index.html - {e}")
