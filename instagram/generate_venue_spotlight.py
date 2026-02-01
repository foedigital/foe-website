#!/usr/bin/env python3
"""
Instagram Venue Spotlight Generator for Funny Over Everything

Generates and posts a weekly venue spotlight featuring one Austin comedy venue
with their weekend show listings. Rotates through 5 venues deterministically
based on ISO week number.

Usage:
    python -m instagram.generate_venue_spotlight [--venue KEY] [--date YYYY-MM-DD] [--generate-only] [--post-only] [--dry-run]
"""

import sqlite3
import os
import sys
import argparse
import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageFilter

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from instagram.post_to_instagram import InstagramPoster

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "comedy_images.db"
VENUE_PHOTOS_DIR = PROJECT_ROOT / "images" / "venue_spotlight"
OUTPUT_BASE = PROJECT_ROOT / "instagram" / "venue_spotlight_output"

# Base URL for deployed images
WEBSITE_BASE_URL = os.environ.get("WEBSITE_BASE_URL", "https://foe-website.vercel.app")

# Instagram image dimensions (1:1 square)
IG_SIZE = 1080

# Venue rotation list — order matters, index = ISO_week % 5
VENUE_ROTATION = [
    {
        "key": "creek_cave",
        "db_name": "Creek and the Cave",
        "display_name": "Creek and the Cave",
        "instagram": "@creekandcave",
        "photo": "creek_cave.jpg",
    },
    {
        "key": "cap_city",
        "db_name": "Cap City Comedy",
        "display_name": "Cap City Comedy",
        "instagram": "@capcitycomedy",
        "photo": "cap_city.jpg",
    },
    {
        "key": "sunset_strip",
        "db_name": "Sunset Strip Comedy",
        "display_name": "Sunset Strip Comedy",
        "instagram": "@sunsetstripatx",
        "photo": "sunset_strip.jpg",
    },
    {
        "key": "rozcos",
        "db_name": "Rozco's Comedy",
        "display_name": "Rozco's Comedy",
        "instagram": "@rozcoscomedyclub",
        "photo": "rozcos.png",
    },
    {
        "key": "velveeta",
        "db_name": "The Velveeta Room",
        "display_name": "The Velveeta Room",
        "instagram": "@thevelveetaroom",
        "photo": "velveeta.jpg",
    },
]

VENUE_BY_KEY = {v["key"]: v for v in VENUE_ROTATION}

HASHTAGS = "#austincomedy #atxcomedy #comedyshows #standup #austintx #thingstodoinaustin #atxevents #livecomedy #funnyovereverything #venuespotlight"


# ---------------------------------------------------------------------------
# Copied from generate_daily_post.py (for full isolation)
# ---------------------------------------------------------------------------

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
            if parsed.year == 1900:
                parsed = parsed.replace(year=current_year)
            return parsed
        except ValueError:
            continue

    return None


def format_image_for_instagram(src_path: Path) -> Image.Image:
    """
    Format any image into a 1080x1080 square for Instagram.

    The original image is scaled to fit within the square, then centered
    on a blurred, zoomed version of itself that fills the background.
    """
    with Image.open(src_path) as img:
        img = img.convert("RGB")
        w, h = img.size

        scale = min(IG_SIZE / w, IG_SIZE / h)
        fg_w = round(w * scale)
        fg_h = round(h * scale)
        fg = img.resize((fg_w, fg_h), Image.LANCZOS)

        if fg_w == IG_SIZE and fg_h == IG_SIZE:
            return fg

        cover_scale = max(IG_SIZE / w, IG_SIZE / h)
        bg_w = round(w * cover_scale)
        bg_h = round(h * cover_scale)
        bg = img.resize((bg_w, bg_h), Image.LANCZOS)

        left = (bg_w - IG_SIZE) // 2
        top = (bg_h - IG_SIZE) // 2
        bg = bg.crop((left, top, left + IG_SIZE, top + IG_SIZE))

        bg = bg.filter(ImageFilter.GaussianBlur(radius=40))

        x_offset = (IG_SIZE - fg_w) // 2
        y_offset = (IG_SIZE - fg_h) // 2
        bg.paste(fg, (x_offset, y_offset))

        return bg


# ---------------------------------------------------------------------------
# Venue spotlight logic
# ---------------------------------------------------------------------------

def get_current_venue(override_key: Optional[str] = None, reference_date: Optional[datetime] = None) -> Dict:
    """
    Pick venue from rotation based on ISO week number, or use override.
    """
    if override_key:
        if override_key not in VENUE_BY_KEY:
            valid = ", ".join(VENUE_BY_KEY.keys())
            raise ValueError(f"Unknown venue key: {override_key}. Valid keys: {valid}")
        return VENUE_BY_KEY[override_key]

    if reference_date is None:
        reference_date = datetime.now()

    iso_week = reference_date.isocalendar()[1]
    index = iso_week % len(VENUE_ROTATION)
    return VENUE_ROTATION[index]


def get_weekend_shows(venue_db_name: str, reference_date: datetime) -> Dict[str, List[Dict]]:
    """
    Query DB for Thu-Sun shows at the given venue.
    Returns dict keyed by date string, each value a list of shows sorted by time.
    """
    # Build list of weekend dates: Thu, Fri, Sat, Sun
    weekend_dates = []
    for offset in range(4):
        d = reference_date + timedelta(days=offset)
        weekend_dates.append(d)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            i.event_name,
            i.event_date,
            i.show_time,
            i.local_path,
            v.name as venue_name
        FROM images i
        JOIN venues v ON i.venue_id = v.id
        WHERE v.name = ?
          AND i.event_name IS NOT NULL
        ORDER BY i.show_time
    """, (venue_db_name,))

    all_shows = cursor.fetchall()
    conn.close()

    shows_by_day: Dict[str, List[Dict]] = {}

    for target in weekend_dates:
        target_date_only = target.date()
        day_key = target.strftime("%A, %b %-d") if sys.platform != "win32" else target.strftime("%A, %b %#d")
        day_shows = []

        for show in all_shows:
            parsed = parse_event_date(show["event_date"], reference_date)
            if parsed and parsed.date() == target_date_only:
                day_shows.append({
                    "name": show["event_name"],
                    "date": show["event_date"],
                    "time": show["show_time"] or "TBA",
                    "image_path": show["local_path"],
                    "venue": show["venue_name"],
                })

        # Sort by time
        def parse_time(t):
            if not t or t == "TBA":
                return (24, 0)
            try:
                parsed_t = datetime.strptime(t, "%I:%M %p")
                return (parsed_t.hour, parsed_t.minute)
            except ValueError:
                return (24, 0)

        day_shows.sort(key=lambda x: parse_time(x["time"]))

        if day_shows:
            shows_by_day[day_key] = day_shows

    return shows_by_day


def generate_spotlight_caption(venue: Dict, shows_by_day: Dict[str, List[Dict]]) -> str:
    """
    Generate venue spotlight caption with AI intro + show listings.
    """
    total_shows = sum(len(s) for s in shows_by_day.values())

    # Try AI intro
    ai_intro = _generate_ai_intro(venue, total_shows)
    if not ai_intro:
        ai_intro = f"This week's venue spotlight: {venue['display_name']} -- one of Austin's best comedy rooms."

    # Build show listing
    if shows_by_day:
        listing_parts = []
        for day, shows in shows_by_day.items():
            lines = [f"{day}:"]
            for s in shows:
                lines.append(f"  {s['time']} - {s['name']}")
            listing_parts.append("\n".join(lines))
        show_listing = "\n\n".join(listing_parts)
    else:
        show_listing = f"Check back soon for upcoming shows at {venue['display_name']}!"

    # Assemble full caption
    parts = [
        ai_intro,
        show_listing,
        f"Full show listings -- link in bio",
        venue["instagram"],
        HASHTAGS,
    ]

    return "\n\n".join(parts)


def _generate_ai_intro(venue: Dict, total_shows: int) -> Optional[str]:
    """Generate a short AI intro for the venue using Anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set, skipping AI intro.")
        return None

    try:
        import anthropic
    except ImportError:
        print("  anthropic package not installed, skipping AI intro.")
        return None

    prompt = f"""Write a short, engaging Instagram intro for a weekly comedy venue spotlight in Austin, TX.

Venue: {venue['display_name']}
Instagram: {venue['instagram']}
Weekend shows: {total_shows}

Guidelines:
- Keep it under 200 characters
- Highlight what makes this venue special as a comedy room
- Be enthusiastic but not over-the-top
- Do NOT include hashtags (they will be added separately)
- Do NOT include the venue's Instagram handle (it will be added separately)
- Do NOT use emojis
- Write ONLY the intro text, nothing else"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        intro = message.content[0].text.strip()
        print(f"  AI intro generated ({len(intro)} chars)")
        return intro
    except Exception as e:
        print(f"  AI intro failed: {e}")
        traceback.print_exc()
        return None


def process_venue_image(venue: Dict, output_dir: Path) -> Tuple[Path, str]:
    """
    Format venue hero image to 1080x1080 and save to output dir.
    Returns (local_path, web_url).
    """
    src_path = VENUE_PHOTOS_DIR / venue["photo"]
    if not src_path.exists():
        raise FileNotFoundError(f"Venue photo not found: {src_path}")

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    formatted = format_image_for_instagram(src_path)
    dest_name = f"{venue['key']}_spotlight.jpg"
    dest_path = images_dir / dest_name
    formatted.save(dest_path, "JPEG", quality=92)

    # Also save an _ig version next to the source so Vercel deploys it
    ig_path = VENUE_PHOTOS_DIR / f"{venue['key']}_ig.jpg"
    formatted.save(ig_path, "JPEG", quality=92)

    web_url = f"{WEBSITE_BASE_URL}/images/venue_spotlight/{venue['key']}_ig.jpg"

    return dest_path, web_url


# ---------------------------------------------------------------------------
# Generate & Post
# ---------------------------------------------------------------------------

def do_generate(venue: Dict, reference_date: datetime) -> Path:
    """
    Generate spotlight content: caption, summary, formatted image.
    Returns the output directory.
    """
    date_str = reference_date.strftime("%Y-%m-%d")
    output_dir = OUTPUT_BASE / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nVenue Spotlight Generator")
    print(f"Venue: {venue['display_name']} ({venue['key']})")
    print(f"Date: {reference_date.strftime('%A, %B %d, %Y')}")
    print(f"Output: {output_dir}")
    print("-" * 40)

    # Get weekend shows
    print("\nFetching weekend shows from database...")
    shows_by_day = get_weekend_shows(venue["db_name"], reference_date)
    total = sum(len(s) for s in shows_by_day.values())
    print(f"Found {total} shows across {len(shows_by_day)} days")

    for day, shows in shows_by_day.items():
        print(f"  {day}: {len(shows)} shows")

    # Generate caption
    print("\nGenerating caption...")
    caption = generate_spotlight_caption(venue, shows_by_day)
    caption_path = output_dir / "caption.txt"
    caption_path.write_text(caption, encoding="utf-8")
    print(f"Caption saved to: {caption_path}")

    # Process venue image
    print("\nProcessing venue image...")
    image_path, image_url = process_venue_image(venue, output_dir)
    print(f"Image saved to: {image_path}")
    print(f"Image URL: {image_url}")

    # Build summary
    all_shows = []
    for day, shows in shows_by_day.items():
        for s in shows:
            all_shows.append({
                "name": s["name"],
                "time": s["time"],
                "day": day,
            })

    summary = {
        "type": "venue_spotlight",
        "date": reference_date.isoformat(),
        "date_display": reference_date.strftime("%A, %B %d, %Y"),
        "venue_key": venue["key"],
        "venue_name": venue["display_name"],
        "venue_instagram": venue["instagram"],
        "total_shows": total,
        "days_with_shows": len(shows_by_day),
        "image_url": image_url,
        "shows": all_shows,
    }

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary saved to: {summary_path}")

    # Preview
    print(f"\n{'=' * 40}")
    print("CAPTION PREVIEW:")
    print("=" * 40)
    print(caption[:600])
    if len(caption) > 600:
        print(f"... ({len(caption)} total characters)")

    return output_dir


def do_post(output_dir: Path, dry_run: bool = False) -> None:
    """
    Read generated content from output_dir and post to Instagram.
    """
    caption_path = output_dir / "caption.txt"
    summary_path = output_dir / "summary.json"

    if not caption_path.exists() or not summary_path.exists():
        raise FileNotFoundError(
            f"Generated content not found in {output_dir}. Run --generate-only first."
        )

    caption = caption_path.read_text(encoding="utf-8")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    image_url = summary["image_url"]

    print(f"\nVenue Spotlight Poster")
    print(f"Venue: {summary['venue_name']}")
    print(f"Image URL: {image_url}")
    print(f"Caption: {len(caption)} characters")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 40)

    if dry_run:
        print(f"\n{'=' * 40}")
        print("DRY RUN - No post created")
        print(f"Would post image: {image_url}")
        print(f"Caption preview:\n{caption[:300]}")
        if len(caption) > 300:
            print(f"... ({len(caption)} total chars)")
        return

    # Get credentials
    access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")

    if not access_token or not account_id:
        print("Error: Missing environment variables")
        print("Required:")
        print("  INSTAGRAM_ACCESS_TOKEN")
        print("  INSTAGRAM_ACCOUNT_ID")
        sys.exit(1)

    poster = InstagramPoster(access_token, account_id)

    # Verify account
    print("\nVerifying account access...")
    try:
        account_info = poster.get_account_info()
        print(f"  Account: @{account_info.get('username', 'unknown')}")
    except Exception as e:
        print(f"  Error verifying account: {e}")
        sys.exit(1)

    # Post single image
    print("\nPosting to Instagram...")
    try:
        media_id = poster.post_single_image(image_url, caption)
        print(f"\nSuccess! Media ID: {media_id}")
    except Exception as e:
        print(f"\nError posting: {e}")
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate and post weekly venue spotlight to Instagram"
    )
    parser.add_argument(
        "--venue",
        type=str,
        choices=list(VENUE_BY_KEY.keys()),
        help="Override venue selection (default: auto-rotate by week)",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Reference date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate content, do not post",
    )
    parser.add_argument(
        "--post-only",
        action="store_true",
        help="Only post previously generated content",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview posting without actually posting",
    )
    args = parser.parse_args()

    # Parse reference date
    if args.date:
        reference_date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        reference_date = datetime.now()

    # Pick venue
    venue = get_current_venue(args.venue, reference_date)
    date_str = reference_date.strftime("%Y-%m-%d")
    output_dir = OUTPUT_BASE / date_str

    if args.post_only:
        do_post(output_dir, dry_run=args.dry_run)
    elif args.generate_only:
        do_generate(venue, reference_date)
    else:
        # Both generate and post
        do_generate(venue, reference_date)
        do_post(output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
