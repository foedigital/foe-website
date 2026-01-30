#!/usr/bin/env python3
"""
Instagram Daily Post Generator for Funny Over Everything

Generates daily Instagram content including:
- Collected show flyer images
- Formatted caption with show times and venues
- Optional collage for days with many shows

Usage:
    python -m instagram.generate_daily_post [--date YYYY-MM-DD] [--output-dir PATH]
"""

import sqlite3
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import shutil
import json
import traceback

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "comedy_images.db"
IMAGES_DIR = PROJECT_ROOT / "images"
OUTPUT_DIR = PROJECT_ROOT / "instagram" / "daily_output"

# Base URL for deployed images
WEBSITE_BASE_URL = "https://funnyovereverything.com"

# Venue display names (cleaned up for Instagram)
VENUE_DISPLAY_NAMES = {
    "creek-and-the-cave": "Creek and the Cave",
    "comedy-mothership": "Comedy Mothership",
    "cap-city-comedy": "Cap City Comedy",
    "the-velveeta-room": "The Velveeta Room",
    "vulcan-gas-company": "Vulcan Gas Company",
    "rozcos-comedy": "Rozco's Comedy",
    "east-austin-comedy-club": "East Austin Comedy Club",
    "paramount-theatre": "Paramount Theatre",
    "sunset-strip-comedy": "Sunset Strip Comedy",
    "black-rabbit-comedy": "Black Rabbit Comedy",
    "gnar-bar": "Gnar Bar",
    "speakeasy": "Speakeasy",
    "pop-up": "Pop-Up Show",
}

# Free shows list (from regenerate_shows.py)
FREE_SHOWS = {
    'the monday gamble mic', 'dunk tank', 'hood therapy tuesdays', 'hood therapy',
    'open mic night', 'open mic', 'crowd control', 'wild west wednesdays',
    'bear arms: open mic', 'bear arms', 'word up! open mic', 'word up',
    'new joke saturday open mic', 'new joke saturday', 'off the cuff',
    'sunday service', 'the thursday special', 'stand up comedy show',
    'eastside open mic',
}


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_event_date(date_str: str, target_date: datetime) -> Optional[datetime]:
    """
    Parse event date string and check if it matches target date.
    Handles formats like "Tuesday, Jan 27", "Jan 27", "January 27, 2026"
    """
    if not date_str:
        return None

    date_str = date_str.strip()
    current_year = target_date.year

    # Try various date formats
    formats = [
        "%A, %b %d",      # "Tuesday, Jan 27"
        "%a, %b %d",      # "Tue, Jan 27"
        "%B %d, %Y",      # "January 27, 2026"
        "%b %d, %Y",      # "Jan 27, 2026"
        "%b %d",          # "Jan 27"
        "%B %d",          # "January 27"
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            # If no year in format, use target year
            if parsed.year == 1900:
                parsed = parsed.replace(year=current_year)
            return parsed
        except ValueError:
            continue

    return None


def get_todays_shows(target_date: datetime) -> List[Dict]:
    """
    Fetch all shows for the target date from the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all shows with their venue info
    cursor.execute("""
        SELECT
            i.event_name,
            i.event_date,
            i.show_time,
            i.local_path,
            i.source_url,
            v.name as venue_name
        FROM images i
        JOIN venues v ON i.venue_id = v.id
        WHERE i.event_name IS NOT NULL
        ORDER BY i.show_time
    """)

    all_shows = cursor.fetchall()
    conn.close()

    # Filter to target date
    target_date_only = target_date.date()
    todays_shows = []

    for show in all_shows:
        parsed_date = parse_event_date(show['event_date'], target_date)
        if parsed_date and parsed_date.date() == target_date_only:
            todays_shows.append({
                'name': show['event_name'],
                'date': show['event_date'],
                'time': show['show_time'] or 'TBA',
                'image_path': show['local_path'],
                'venue': show['venue_name'],
                'source_url': show['source_url'],
                'is_free': show['event_name'].lower().strip() in FREE_SHOWS,
            })

    # Sort by time
    def parse_time(t):
        if not t or t == 'TBA':
            return (24, 0)
        try:
            parsed = datetime.strptime(t, "%I:%M %p")
            return (parsed.hour, parsed.minute)
        except:
            return (24, 0)

    todays_shows.sort(key=lambda x: parse_time(x['time']))

    return todays_shows


HASHTAGS = "#austincomedy #atxcomedy #comedyshows #standup #austintx #thingstodoinaustin #atxevents #livecomedy"


def generate_ai_caption(shows: List[Dict], target_date: datetime) -> Optional[str]:
    """
    Generate an engaging Instagram caption using the Anthropic API.
    Returns None if the API key is not set or the call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set, skipping AI caption.")
        return None

    try:
        import anthropic
    except ImportError:
        print("  anthropic package not installed, skipping AI caption.")
        return None

    date_str = target_date.strftime("%A, %B %d")
    total_shows = len(shows)
    free_count = sum(1 for s in shows if s['is_free'])

    # Build show info for the prompt
    show_lines = []
    for s in shows:
        free_tag = " (FREE)" if s['is_free'] else ""
        show_lines.append(f"- {s['name']} at {s['venue']}, {s['time']}{free_tag}")
    show_info = "\n".join(show_lines)

    prompt = f"""Write a short, engaging Instagram caption for a daily comedy show listing in Austin, TX.

Date: {date_str}
Total shows: {total_shows}
Free shows: {free_count}

Shows:
{show_info}

Guidelines:
- Keep it under 300 characters (before hashtags)
- Be enthusiastic but not over-the-top
- Mention the number of shows and highlight any free ones
- Include a call to action pointing to funnyovereverything.com for full listings and tickets
- Do NOT include hashtags (they will be added separately)
- Do NOT use emojis
- Write ONLY the caption text, nothing else"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        caption_text = message.content[0].text.strip()
        print(f"  AI caption generated ({len(caption_text)} chars)")
        return caption_text
    except Exception as e:
        print(f"  AI caption failed: {e}")
        traceback.print_exc()
        return None


def generate_template_caption(shows: List[Dict], target_date: datetime) -> str:
    """
    Generate a static template caption (fallback when AI is unavailable).
    """
    date_str = target_date.strftime("%A, %B %d")

    caption = f"Comedy in Austin - {date_str}\n"
    caption += "=" * 30 + "\n\n"

    if not shows:
        caption += "No shows found for today. Check back tomorrow!\n"
        return caption

    by_venue = {}
    for show in shows:
        venue = show['venue']
        if venue not in by_venue:
            by_venue[venue] = []
        by_venue[venue].append(show)

    for venue, venue_shows in by_venue.items():
        caption += f"{venue}\n"
        for show in venue_shows:
            time_str = show['time']
            free_tag = " [FREE]" if show['is_free'] else ""
            caption += f"  {time_str} - {show['name']}{free_tag}\n"
        caption += "\n"

    total_shows = len(shows)
    free_count = sum(1 for s in shows if s['is_free'])

    caption += f"{total_shows} shows tonight"
    if free_count > 0:
        caption += f" ({free_count} FREE!)"
    caption += "\n\n"

    caption += "Full listings & tickets: funnyovereverything.com"
    return caption


def generate_caption(shows: List[Dict], target_date: datetime) -> str:
    """
    Generate Instagram caption with all shows for the day.
    Tries AI generation first, falls back to static template.
    """
    if not shows:
        return "No shows found for today. Check back tomorrow!\n\n" + HASHTAGS

    # Try AI caption first
    ai_caption = generate_ai_caption(shows, target_date)
    if ai_caption:
        return ai_caption + "\n\n" + HASHTAGS

    # Fall back to template
    print("  Using template caption.")
    template = generate_template_caption(shows, target_date)
    return template + "\n\n" + HASHTAGS


def copy_images_to_output(shows: List[Dict], output_dir: Path) -> Tuple[List[Path], List[str]]:
    """
    Copy show images to output directory, renamed for easy ordering.
    Returns tuple of (local paths, web URLs).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous output
    for f in output_dir.glob("*.jpg"):
        f.unlink()
    for f in output_dir.glob("*.png"):
        f.unlink()
    for f in output_dir.glob("*.webp"):
        f.unlink()

    copied_images = []
    image_urls = []
    seen_hashes = set()

    for i, show in enumerate(shows):
        if not show['image_path']:
            continue

        # Normalize path separators for cross-platform (DB may store Windows backslashes)
        src_path = PROJECT_ROOT / Path(show['image_path'].replace('\\', '/'))
        if not src_path.exists():
            print(f"  Warning: Image not found: {src_path}")
            continue

        # Skip duplicates (same image used for multiple shows)
        image_hash = src_path.stem
        if image_hash in seen_hashes:
            continue
        seen_hashes.add(image_hash)

        # Copy with numbered prefix for ordering
        ext = src_path.suffix
        dest_name = f"{i+1:02d}_{show['venue'].replace(' ', '_')}_{show['name'][:30].replace(' ', '_')}{ext}"
        dest_name = "".join(c for c in dest_name if c.isalnum() or c in '._-')
        dest_path = output_dir / dest_name

        shutil.copy2(src_path, dest_path)
        copied_images.append(dest_path)

        # Build web URL from original path (e.g., images/venue/hash.jpg)
        # Convert backslashes to forward slashes for URL
        web_path = show['image_path'].replace('\\', '/')
        web_url = f"{WEBSITE_BASE_URL}/{web_path}"
        image_urls.append(web_url)

        # Instagram carousel limit is 10
        if len(copied_images) >= 10:
            print(f"  Note: Limited to 10 images for carousel (had {len(shows)} shows)")
            break

    return copied_images, image_urls


def generate_summary(shows: List[Dict], images: List[Path], image_urls: List[str], target_date: datetime) -> Dict:
    """Generate summary data for the daily post."""
    return {
        'date': target_date.isoformat(),
        'date_display': target_date.strftime("%A, %B %d, %Y"),
        'total_shows': len(shows),
        'free_shows': sum(1 for s in shows if s['is_free']),
        'venues': list(set(s['venue'] for s in shows)),
        'images_count': len(images),
        'image_urls': image_urls,  # Public URLs for Instagram API
        'shows': [
            {
                'name': s['name'],
                'venue': s['venue'],
                'time': s['time'],
                'is_free': s['is_free'],
            }
            for s in shows
        ]
    }


def main():
    parser = argparse.ArgumentParser(description='Generate daily Instagram post content')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--output-dir', type=str, help='Output directory for images and caption')
    args = parser.parse_args()

    # Parse target date
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        target_date = datetime.now()

    # Set output directory
    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir = output_dir / target_date.strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nInstagram Content Generator")
    print(f"Date: {target_date.strftime('%A, %B %d, %Y')}")
    print(f"Output: {output_dir}")
    print("-" * 40)

    # Get shows
    print("\nFetching shows from database...")
    shows = get_todays_shows(target_date)
    print(f"Found {len(shows)} shows")

    if not shows:
        print("\nNo shows found for this date.")
        print("Try a different date with --date YYYY-MM-DD")
        return

    # Generate caption
    print("\nGenerating caption...")
    caption = generate_caption(shows, target_date)
    caption_path = output_dir / "caption.txt"
    caption_path.write_text(caption, encoding='utf-8')
    print(f"Caption saved to: {caption_path}")

    # Copy images
    print("\nCopying images...")
    images, image_urls = copy_images_to_output(shows, output_dir / "images")
    print(f"Copied {len(images)} images")

    # Generate summary JSON (includes public URLs for Instagram API)
    summary = generate_summary(shows, images, image_urls, target_date)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f"Summary saved to: {summary_path}")

    # Print preview
    print("\n" + "=" * 40)
    print("CAPTION PREVIEW:")
    print("=" * 40)
    print(caption[:500])
    if len(caption) > 500:
        print(f"... ({len(caption)} total characters)")

    print("\n" + "=" * 40)
    print("IMAGES:")
    print("=" * 40)
    for img in images[:5]:
        print(f"  - {img.name}")
    if len(images) > 5:
        print(f"  ... and {len(images) - 5} more")

    print(f"\nContent ready in: {output_dir}")
    print("You can now post these images with the caption to Instagram!")


if __name__ == "__main__":
    main()
