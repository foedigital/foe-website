import sqlite3
import requests
import hashlib
from pathlib import Path

DB_PATH = 'comedy_images.db'

# Bulls Pub image path (already exists)
BULLS_PUB_IMAGE = 'images/bulls_pub/https___cdn.evbuc.com_images_1111179793_2360303401903_1_original.jpg'

# Gnar Bar venue and shows
GNAR_BAR = {
    'name': 'Gnar Bar',
    'url': 'https://gnarbaratx.com/events',
    'logo_url': 'https://gnarbaratx.com/static/images/gnarbar-logo.png'
}

GNAR_BAR_SHOWS = [
    {'name': 'Crowd Control', 'day': 'Monday', 'time': '11pm', 'is_free': True, 'description': 'A crowd-work ONLY comedy show'},
    {'name': 'The Grind', 'day': 'Tuesday', 'time': '9pm', 'is_free': False, 'description': 'Top Austin comedians plus guest appearances'},
    {'name': 'Crowd Control', 'day': 'Wednesday', 'time': '11pm', 'is_free': True, 'description': 'A crowd-work ONLY comedy show'},
    {'name': 'The Grind', 'day': 'Thursday', 'time': '9pm', 'is_free': False, 'description': 'Top Austin comedians plus guest appearances'},
    {'name': 'SHRED', 'day': 'Friday', 'time': '9pm', 'is_free': False, 'description': 'All-star showcase with live music after'},
    {'name': 'SHRED', 'day': 'Saturday', 'time': '9pm', 'is_free': False, 'description': 'All-star showcase with live music after'},
    {'name': 'The Grind', 'day': 'Sunday', 'time': '9pm', 'is_free': False, 'description': 'Top Austin comedians plus guest appearances'},
]

def download_image(url, save_path):
    """Download image from URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Error downloading image: {e}")
        return False

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# === Update Bulls Pub image paths ===
print("Updating Bulls Pub image paths...")
cursor.execute("""
    UPDATE images
    SET local_path = ?
    WHERE venue_id = (SELECT id FROM venues WHERE name = "Bull's Pub")
""", (BULLS_PUB_IMAGE,))
print(f"  Updated {cursor.rowcount} Bulls Pub entries")

# === Add Gnar Bar venue ===
print("\nAdding Gnar Bar venue...")
cursor.execute("SELECT id FROM venues WHERE name = ?", (GNAR_BAR['name'],))
venue_row = cursor.fetchone()

if venue_row:
    gnar_venue_id = venue_row[0]
    print(f"  Gnar Bar already exists with ID {gnar_venue_id}")
else:
    cursor.execute("INSERT INTO venues (name, url) VALUES (?, ?)", (GNAR_BAR['name'], GNAR_BAR['url']))
    gnar_venue_id = cursor.lastrowid
    print(f"  Added Gnar Bar with ID {gnar_venue_id}")

# === Download Gnar Bar logo ===
print("\nDownloading Gnar Bar logo...")
gnar_images_dir = Path('images/gnar_bar')
gnar_images_dir.mkdir(parents=True, exist_ok=True)
gnar_logo_path = gnar_images_dir / 'gnarbar-logo.png'

if not gnar_logo_path.exists():
    if download_image(GNAR_BAR['logo_url'], gnar_logo_path):
        print(f"  Saved logo to {gnar_logo_path}")
    else:
        print("  Failed to download logo")
else:
    print(f"  Logo already exists at {gnar_logo_path}")

# === Add Gnar Bar shows ===
print("\nAdding Gnar Bar shows...")
for show in GNAR_BAR_SHOWS:
    # Create unique source URL for each show/day combo
    source_url = f"{GNAR_BAR['url']}#{show['name'].lower().replace(' ', '-')}-{show['day'].lower()}"
    image_hash = hashlib.md5(source_url.encode()).hexdigest()[:16]
    local_path = 'images/gnar_bar/gnarbar-logo.png'

    # Check if already exists
    cursor.execute("SELECT id FROM images WHERE source_url = ?", (source_url,))
    if cursor.fetchone():
        print(f"  {show['name']} ({show['day']}) already exists")
        continue

    cursor.execute("""
        INSERT INTO images (venue_id, source_url, local_path, event_name, event_date, image_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (gnar_venue_id, source_url, local_path, show['name'], show['day'], image_hash))
    print(f"  Added {show['name']} ({show['day']})")

conn.commit()
conn.close()

print("\n✓ Done!")
print(f"  Bulls Pub: Image updated to {BULLS_PUB_IMAGE}")
print(f"  Gnar Bar: {len(GNAR_BAR_SHOWS)} shows added")
