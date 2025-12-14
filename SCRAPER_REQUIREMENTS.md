# ATX Comedy Venue Image Scraper - Requirements

## Overview
Build an automated Python scraper using Playwright to pull event flyer images from Austin comedy venue websites and store them locally with SQLite tracking.

## Target Venues
1. creekandcave.com
2. comedymothership.com
3. thevelveetaroom.com
4. sunsetstripatx.com
5. eastaustincomedy.com
6. rozcoscomedy.com

## Functional Requirements

### What to Scrape
- **Primary**: Event/show flyer images (promotional images for upcoming comedy shows)
- **Metadata**: Event name and date when extractable from the page HTML
- **NOT**: Full event details like times, descriptions, ticket links, or performer lists

### Storage
- **Images**: Save to local filesystem in `images/` directory, organized by venue
- **Database**: SQLite database to track:
  - Source URLs of scraped images
  - Local file paths
  - Image content hashes (SHA256) for deduplication
  - Event name and date (when available)
  - Sync history/logs

### Execution
- **Manual trigger only** - no automated scheduling needed
- CLI interface to run scraper on-demand
- Option to scrape all venues or a specific venue

## Technical Requirements

### Stack
- Python 3.x
- Playwright (for JavaScript-rendered sites)
- SQLite (local database)
- aiohttp (async image downloads)
- Pillow (image validation)

### Key Features
1. **Deduplication**: Use SHA256 hash to prevent storing duplicate images (same image may appear at different URLs)
2. **Modular scrapers**: Each venue has unique HTML structure, so use venue-specific scraper classes
3. **Sync logging**: Track when each venue was last scraped, how many images found/new

## Database Schema

```sql
-- Venues
CREATE TABLE venues (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    last_scraped TIMESTAMP
);

-- Images
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    venue_id INTEGER NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    local_path TEXT NOT NULL,
    event_name TEXT,
    event_date TEXT,
    image_hash TEXT NOT NULL,
    scraped_at TIMESTAMP,
    FOREIGN KEY (venue_id) REFERENCES venues(id)
);

-- Sync history
CREATE TABLE sync_log (
    id INTEGER PRIMARY KEY,
    venue_id INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    images_found INTEGER,
    images_new INTEGER,
    status TEXT,
    error_message TEXT,
    FOREIGN KEY (venue_id) REFERENCES venues(id)
);
```

## Project Structure
```
AtxComedy/
├── scraper/
│   ├── __init__.py
│   ├── main.py           # CLI entry point
│   ├── database.py       # SQLite operations
│   ├── downloader.py     # Image download + hashing
│   ├── config.py         # Venue URLs, selectors
│   └── venues/
│       ├── __init__.py
│       ├── base.py       # Base scraper class
│       └── [venue].py    # One per venue
├── images/               # Downloaded images (gitignored)
├── comedy_images.db      # SQLite database
└── requirements.txt
```

## Usage
```bash
# Scrape all venues
python -m scraper.main --all

# Scrape specific venue
python -m scraper.main --venue creek_cave
```

## Notes
- Playwright is required because many venue sites use JavaScript rendering
- Some sites (Creek & Cave) may require clicking "Load More" buttons
- Image selectors vary by site - each uses different CSS classes/structures
