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
from PIL import Image, ImageDraw, ImageFilter

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "comedy_images.db"
IMAGES_DIR = PROJECT_ROOT / "images"
OUTPUT_DIR = PROJECT_ROOT / "instagram" / "daily_output"

# Base URL for deployed images
WEBSITE_BASE_URL = os.environ.get("WEBSITE_BASE_URL", "https://foe-website.vercel.app")

# Instagram image dimensions (1:1 square)
IG_SIZE = 1080

# Venue logo overlays — keyed by venue display name
VENUE_LOGOS = {
    "Cap City Comedy": PROJECT_ROOT / "images" / "venue_spotlight" / "cap_city.jpg",
}

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

# Venue Instagram handles (for tagging in captions)
VENUE_INSTAGRAMS = {
    "Creek and the Cave": "@creekandcave",
    "Comedy Mothership": "@comedymothership",
    "Cap City Comedy": "@capcitycomedy",
    "The Velveeta Room": "@thevelveetaroom",
    "Vulcan Gas Company": "@vulcanatx",
    "Rozco's Comedy": "@rozcoscomedyclub",
    "East Austin Comedy Club": "@eastaustincomedy",
    "Paramount Theatre": "@paramountaustin",
    "Sunset Strip Comedy": "@sunsetstripatx",
    "Black Rabbit Comedy": "@blackrabbitatx",
    "Gnar Bar": "@gnarbaratx",
    "Speakeasy": "@speakeasyaustin",
}

# Free shows list (synced with regenerate_shows.py)
FREE_SHOWS = {
    'the monday gamble mic', 'dunk tank', 'hood therapy tuesdays', 'hood therapy',
    'open mic night', 'open mic', 'crowd control', 'wild west wednesdays',
    'bear arms: open mic', 'bear arms', 'word up! open mic', 'word up',
    'new joke saturday open mic', 'new joke saturday', 'off the cuff',
    'sunday service', 'the thursday special', 'stand up comedy show',
    'eastside open mic', 'banana phone',
    'the creek and the cave open mic',
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
            v.name as venue_name,
            v.url as venue_url
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

    skipped_unparseable = 0
    for show in all_shows:
        parsed_date = parse_event_date(show['event_date'], target_date)
        if not parsed_date:
            skipped_unparseable += 1
            continue
        if parsed_date.date() == target_date_only:
            todays_shows.append({
                'name': show['event_name'],
                'date': show['event_date'],
                'time': show['show_time'] or 'TBA',
                'image_path': show['local_path'],
                'venue': show['venue_name'],
                'venue_url': show['venue_url'],
                'source_url': show['source_url'],
                'is_free': show['event_name'].lower().strip() in FREE_SHOWS,
            })

    if skipped_unparseable > 0:
        print(f"  Warning: {skipped_unparseable} shows had unparseable dates and were skipped")

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

    # On Sundays, pin Banana Phone as the first image
    if target_date.weekday() == 6:  # Sunday
        for i, show in enumerate(todays_shows):
            if 'banana phone' in show['name'].lower():
                todays_shows.insert(0, todays_shows.pop(i))
                break

    return todays_shows


HASHTAGS = "#austincomedy #atxcomedy #comedyshows #standup #austintx #thingstodoinaustin #atxevents #livecomedy #funnyovereverything"


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
- End with a call to action saying "Link in bio" to direct people to full show listings
- We are a show listing resource, NOT a ticket seller — never say "buy tickets" or include URLs
- Use a different, original opening line every day — never start with the same phrase twice
- Do NOT include hashtags (they will be added separately)
- Do NOT include venue tags (they will be added separately)
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

    caption += "Full show listings -- link in bio"
    return caption


def build_venue_section(shows: List[Dict]) -> str:
    """
    Build a venue tag section from the shows list.
    Deduplicates venues while preserving show order.
    Looks up Instagram handles from VENUE_INSTAGRAMS, falls back to venue website URL.
    """
    seen = set()
    venue_lines = []
    for show in shows:
        venue = show['venue']
        if venue in seen:
            continue
        seen.add(venue)
        handle = VENUE_INSTAGRAMS.get(venue)
        if handle:
            venue_lines.append(handle)
        else:
            # Fall back to venue website URL
            venue_lines.append(show.get('venue_url', venue))
    if not venue_lines:
        return ""
    return "Tonight's venues:\n" + "\n".join(venue_lines)


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
        caption_text = ai_caption
    else:
        # Fall back to template
        print("  Using template caption.")
        caption_text = generate_template_caption(shows, target_date)

    # Build venue section
    venue_section = build_venue_section(shows)

    parts = [caption_text]
    if venue_section:
        parts.append(venue_section)
    parts.append(HASHTAGS)
    return "\n\n".join(parts)


def format_image_for_instagram(src_path: Path) -> Image.Image:
    """
    Format any image into a 1080x1080 square for Instagram.

    The original image is scaled to fit within the square, then centered
    on a blurred, zoomed version of itself that fills the background.
    """
    with Image.open(src_path) as img:
        img = img.convert("RGB")
        w, h = img.size

        # Scale the original to fit within IG_SIZE x IG_SIZE
        scale = min(IG_SIZE / w, IG_SIZE / h)
        fg_w = round(w * scale)
        fg_h = round(h * scale)
        fg = img.resize((fg_w, fg_h), Image.LANCZOS)

        # Sharpen if the image was upscaled (avoids soft/grainy look)
        if scale > 1.0:
            fg = fg.filter(ImageFilter.UnsharpMask(radius=2, percent=100, threshold=3))

        # If the image already fills the square, just return resized
        if fg_w == IG_SIZE and fg_h == IG_SIZE:
            return fg

        # Create blurred background: scale original to cover full square, then blur
        cover_scale = max(IG_SIZE / w, IG_SIZE / h)
        bg_w = round(w * cover_scale)
        bg_h = round(h * cover_scale)
        bg = img.resize((bg_w, bg_h), Image.LANCZOS)

        # Center-crop the background to exact square
        left = (bg_w - IG_SIZE) // 2
        top = (bg_h - IG_SIZE) // 2
        bg = bg.crop((left, top, left + IG_SIZE, top + IG_SIZE))

        # Apply heavy blur
        bg = bg.filter(ImageFilter.GaussianBlur(radius=40))

        # Paste sharp foreground centered on blurred background
        x_offset = (IG_SIZE - fg_w) // 2
        y_offset = (IG_SIZE - fg_h) // 2
        bg.paste(fg, (x_offset, y_offset))

        return bg


def add_venue_logo(img: Image.Image, logo_path: Path) -> Image.Image:
    """
    Overlay a venue logo banner at the bottom of a formatted Instagram image.
    The logo is scaled to full width and placed at the bottom edge.
    """
    with Image.open(logo_path) as logo:
        logo = logo.convert("RGB")
        logo_w, logo_h = logo.size

        # Scale logo to full image width
        scale = IG_SIZE / logo_w
        new_h = round(logo_h * scale)
        logo = logo.resize((IG_SIZE, new_h), Image.LANCZOS)

        # Paste at the bottom
        img = img.copy()
        img.paste(logo, (0, IG_SIZE - new_h))
        return img


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

        # Format every image as 1080x1080 square with blurred background
        try:
            formatted = format_image_for_instagram(src_path)

            # Overlay venue logo if one exists for this venue
            logo_path = VENUE_LOGOS.get(show['venue'])
            if logo_path and logo_path.exists():
                formatted = add_venue_logo(formatted, logo_path)

            dest_path = dest_path.with_suffix(".jpg")
            formatted.save(dest_path, "JPEG", quality=92)
            # Also save alongside original in images/ so it deploys to Vercel
            ig_path = src_path.parent / f"{src_path.stem}_ig.jpg"
            formatted.save(ig_path, "JPEG", quality=92)
            ig_web_path = ig_path.relative_to(PROJECT_ROOT).as_posix()
            web_url = f"{WEBSITE_BASE_URL}/{ig_web_path}"
        except Exception as e:
            print(f"  Warning: Failed to process image for '{show['name']}': {e}")
            continue

        copied_images.append(dest_path)
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
