"""Venue configuration for the ATX Comedy scraper."""

VENUES = {
    "creek_cave": {
        "name": "Creek and the Cave",
        "url": "https://www.creekandcave.com",
        "events_url": "https://www.creekandcave.com/calendar",
        "image_selectors": [
            ".shows_card img",
            ".collection_item_load_more img",
        ],
        "event_name_selector": ".shows_card h2, .shows_card h3",
        "event_date_selector": ".shows_card .date, .shows_card time",
    },
    "mothership": {
        "name": "Comedy Mothership",
        "url": "https://comedymothership.com",
        "events_url": "https://comedymothership.com/shows",
        "image_selectors": [
            "[class*='EventCard_imageWrapper'] img",
            "[class*='EventCard'] img",
        ],
        "event_name_selector": "[class*='EventCard_title'], h2, h3",
        "event_date_selector": "[class*='EventCard_date'], time",
    },
    "velveeta": {
        "name": "The Velveeta Room",
        "url": "https://www.thevelveetaroom.com",
        "events_url": "https://www.thevelveetaroom.com",
        "image_selectors": [
            "wow-image img",
            "[class*='MazNVa'] img",
            "img[src*='wixstatic'][alt*='Poster']",
        ],
        "event_name_selector": "",
        "event_date_selector": "",
    },
    "sunset_strip": {
        "name": "Sunset Strip Comedy",
        "url": "https://www.sunsetstripatx.com",
        "events_url": "https://www.sunsetstripatx.com/events",
        "image_selectors": [
            ".sqs-block-image img",
            ".summary-thumbnail img",
            ".eventlist-column-thumbnail img",
        ],
        "event_name_selector": ".eventlist-title, .summary-title, h2",
        "event_date_selector": ".eventlist-meta-date, time.event-date",
    },
    "east_austin": {
        "name": "East Austin Comedy Club",
        "url": "https://eastaustincomedy.com",
        "events_url": "https://eastaustincomedy.com/events-2-1",
        "image_selectors": [
            ".sqs-block-image img",
            ".fe-block img",
            ".fluidImageOverlay img",
        ],
        "event_name_selector": "h2, h3, .event-title",
        "event_date_selector": "time, .date",
    },
    "rozcos": {
        "name": "Rozco's Comedy",
        "url": "https://www.rozcoscomedy.com",
        "events_url": "https://www.rozcoscomedy.com/events",
        "image_selectors": [
            ".event img",
            ".sqs-block-image img",
            "[class*='event'] img",
        ],
        "event_name_selector": ".event-title, h2, h3",
        "event_date_selector": ".event-date, time",
    },
    "vulcan": {
        "name": "Vulcan Gas Company",
        "url": "https://www.vulcanatx.com",
        "events_url": "https://www.vulcanatx.com/",
        "image_selectors": [
            ".event img",
            "[class*='event'] img",
            ".w-dyn-item img",
        ],
        "event_name_selector": "h2, h3, h4, .event-title",
        "event_date_selector": ".event-date, time",
    },
    "paramount": {
        "name": "Paramount Theatre",
        "url": "https://tickets.austintheatre.org",
        "events_url": "https://tickets.austintheatre.org/events?kid=4",
        "image_selectors": [
            ".tn-event-listing-item img",
            ".tn-event-listing-item__image img",
        ],
        "event_name_selector": ".tn-event-listing-item__name, .tn-name",
        "event_date_selector": ".tn-event-listing-item__date, .tn-date-time",
    },
}

MIN_IMAGE_WIDTH = 200
MIN_IMAGE_HEIGHT = 200

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

REQUEST_TIMEOUT = 30000
PAGE_LOAD_WAIT = 3000
