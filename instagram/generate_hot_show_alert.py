#!/usr/bin/env python3
"""
Instagram Hot Show Alert Generator for Funny Over Everything

Generates and posts a "Hot Show Alert" carousel featuring hand-picked shows
at a specific venue, padded with additional upcoming ticketed shows as fillers.

Usage:
    python -m instagram.generate_hot_show_alert \
      --venue creek_cave \
      --urls "https://www.creekandcave.com/events/michael-che,https://www.creekandcave.com/events/judgment-day" \
      [--date YYYY-MM-DD] [--generate-only] [--post-only] [--dry-run]
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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from instagram.post_to_instagram import InstagramPoster
from instagram.generate_daily_post import (
    parse_event_date,
    format_image_for_instagram,
    FREE_SHOWS,
    VENUE_LOGOS,
    add_venue_logo,
    get_show_tags,
)

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "comedy_images.db"
OUTPUT_BASE = PROJECT_ROOT / "instagram" / "hot_show_alert_output"

# Base URL for deployed images
WEBSITE_BASE_URL = os.environ.get("WEBSITE_BASE_URL", "https://foe-website.vercel.app")

# Instagram image dimensions (1:1 square)
IG_SIZE = 1080

# Venue config — same keys as venue spotlight
VENUES = {
    "creek_cave": {
        "key": "creek_cave",
        "db_name": "Creek and the Cave",
        "display_name": "Creek and the Cave",
        "instagram": "@creekandcave",
        "website": "creekandcave.com",
    },
    "cap_city": {
        "key": "cap_city",
        "db_name": "Cap City Comedy",
        "display_name": "Cap City Comedy",
        "instagram": "@capcitycomedy",
        "website": "capcitycomedy.com",
    },
    "sunset_strip": {
        "key": "sunset_strip",
        "db_name": "Sunset Strip Comedy",
        "display_name": "Sunset Strip Comedy",
        "instagram": "@sunsetstripatx",
        "website": "sunsetstripatx.com",
    },
    "rozcos": {
        "key": "rozcos",
        "db_name": "Rozco's Comedy",
        "display_name": "Rozco's Comedy",
        "instagram": "@rozcoscomedyclub",
        "website": "rozcoscomedy.com",
    },
    "velveeta": {
        "key": "velveeta",
        "db_name": "The Velveeta Room",
        "display_name": "The Velveeta Room",
        "instagram": "@thevelveetaroom",
        "website": "thevelveetaroom.com",
    },
}

HASHTAGS = "#austincomedy #atxcomedy #comedyshows #standup #austintx #thingstodoinaustin #atxevents #livecomedy #funnyovereverything"


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Show lookup
# ---------------------------------------------------------------------------

def lookup_shows_by_url(urls: List[str]) -> List[Dict]:
    """
    Look up shows in the database by their source_url.
    Returns shows in the same order as the input URLs.
    Warns (but doesn't crash) if a URL isn't found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    shows = []
    for url in urls:
        url = url.strip()
        if not url:
            continue

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
            WHERE i.source_url = ?
            LIMIT 1
        """, (url,))

        row = cursor.fetchone()
        if row:
            shows.append({
                "name": row["event_name"],
                "date": row["event_date"],
                "time": row["show_time"] or "TBA",
                "image_path": row["local_path"],
                "venue": row["venue_name"],
                "source_url": row["source_url"],
                "is_featured": True,
            })
        else:
            print(f"  Warning: URL not found in database: {url}")

    conn.close()
    return shows


def get_filler_shows(
    venue_db_name: str,
    reference_date: datetime,
    exclude_urls: set,
    max_total: int = 10,
    already_have: int = 0,
) -> List[Dict]:
    """
    Fetch upcoming ticketed shows from the same venue to pad the carousel.
    Looks 10 days ahead from reference_date.
    Excludes free shows and already-featured URLs.
    """
    needed = max_total - already_have
    if needed <= 0:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

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
        WHERE v.name = ?
          AND i.event_name IS NOT NULL
        ORDER BY i.show_time
    """, (venue_db_name,))

    all_shows = cursor.fetchall()
    conn.close()

    fillers = []
    seen_names = set()

    for show in all_shows:
        if len(fillers) >= needed:
            break

        # Skip already-featured
        if show["source_url"] in exclude_urls:
            continue

        # Skip free shows
        if show["event_name"] and show["event_name"].lower().strip() in FREE_SHOWS:
            continue

        # Skip duplicates by name
        name_key = show["event_name"].lower().strip() if show["event_name"] else ""
        if name_key in seen_names:
            continue

        # Only include shows within the next 10 days
        parsed = parse_event_date(show["event_date"], reference_date)
        if not parsed:
            continue
        delta = (parsed.date() - reference_date.date()).days
        if delta < 0 or delta > 10:
            continue

        seen_names.add(name_key)
        fillers.append({
            "name": show["event_name"],
            "date": show["event_date"],
            "time": show["show_time"] or "TBA",
            "image_path": show["local_path"],
            "venue": show["venue_name"],
            "source_url": show["source_url"],
            "is_featured": False,
        })

    return fillers


# ---------------------------------------------------------------------------
# Caption generation
# ---------------------------------------------------------------------------

def generate_hot_show_caption(
    venue: Dict, featured: List[Dict], all_shows: List[Dict],
    direction: Optional[str] = None,
) -> str:
    """
    Generate caption with AI intro + show listings.
    Featured shows are marked/highlighted in the listing.
    `direction` is optional free-text guidance for the AI caption tone/content.
    """
    ai_intro = _generate_ai_intro(venue, featured, direction)
    if not ai_intro:
        ai_intro = _template_intro(venue, featured)

    # Build show listing
    listing_lines = []
    for s in all_shows:
        marker = ">>  " if s["is_featured"] else "  "
        listing_lines.append(f"{marker}{s['date']} - {s['name']} ({s['time']})")

    show_listing = "\n".join(listing_lines)

    # Collect comedian/show tags (deduplicated, preserving order)
    all_tags = []
    seen_tags = set()
    for s in all_shows:
        for tag in get_show_tags(s["name"]):
            if tag not in seen_tags:
                seen_tags.add(tag)
                all_tags.append(tag)

    tags_section = " ".join(all_tags) if all_tags else ""

    # Venue credit block — venue comes first
    venue_block = (
        f"Full calendar and tickets at {venue['website']}\n"
        f"{venue['instagram']}"
    )

    # FOE plug — downplayed, we come second
    foe_plug = "Even more shows from even more venues -- link in bio"

    parts = [
        ai_intro,
        show_listing,
        venue_block,
    ]
    if tags_section:
        parts.append(tags_section)
    parts.append(foe_plug)
    parts.append(HASHTAGS)

    return "\n\n".join(parts)


def _template_intro(venue: Dict, featured: List[Dict]) -> str:
    """Static fallback intro when no API key is available."""
    return (
        f"This week at {venue['display_name']} is going to be absolutely stacked.\n\n"
        f"An incredible lineup of {len(featured)} shows you don't want to miss -- "
        f"check out what's coming up:"
    )


def _generate_ai_intro(
    venue: Dict, featured: List[Dict], direction: Optional[str] = None,
) -> Optional[str]:
    """Generate a short AI intro celebrating the venue's week of shows."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set, skipping AI intro.")
        return None

    try:
        import anthropic
    except ImportError:
        print("  anthropic package not installed, skipping AI intro.")
        return None

    show_names = ", ".join(s["name"] for s in featured)

    direction_block = ""
    if direction:
        direction_block = f"\nAdditional direction from the user:\n{direction}\n"

    prompt = f"""Write a short, punchy Instagram intro celebrating an amazing upcoming week of comedy at a venue in Austin, TX.

Venue: {venue['display_name']}
Instagram: {venue['instagram']}
Number of featured shows: {len(featured)}
Featured shows: {show_names}
{direction_block}
Guidelines:
- The vibe is: this week at this club is going to be a BANGER -- an amazing lineup of shows
- Hype up the venue's week as a whole, not just individual shows
- This post is about supporting and celebrating the VENUE -- put them front and center
- Keep it under 300 characters
- Enthusiastic and genuine -- this is about celebrating a stacked week
- Do NOT include hashtags (they will be added separately)
- Do NOT include the venue's Instagram handle (it will be added separately)
- Do NOT include website URLs or "link in bio" (that will be added separately)
- Do NOT use emojis
- Do NOT include show dates or times (they will be listed separately)
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


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

def process_show_images(
    shows: List[Dict], output_dir: Path
) -> Tuple[List[Path], List[str]]:
    """
    Process show flyer images to 1080x1080 and save to output dir.
    Also saves _ig.jpg versions next to originals for Vercel deployment.
    Returns (local_paths, web_urls).
    """
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Clear previous output
    for f in images_dir.glob("*.jpg"):
        f.unlink()

    local_paths = []
    web_urls = []
    seen_hashes = set()

    for i, show in enumerate(shows):
        if not show["image_path"]:
            continue

        # Normalize path separators (DB may store Windows backslashes)
        src_path = PROJECT_ROOT / Path(show["image_path"].replace("\\", "/"))
        if not src_path.exists():
            print(f"  Warning: Image not found: {src_path}")
            continue

        # Skip duplicate images
        image_hash = src_path.stem
        if image_hash in seen_hashes:
            continue
        seen_hashes.add(image_hash)

        try:
            formatted = format_image_for_instagram(src_path)

            # Overlay venue logo if one exists
            logo_path = VENUE_LOGOS.get(show["venue"])
            if logo_path and logo_path.exists():
                formatted = add_venue_logo(formatted, logo_path)

            # Save to output dir
            safe_name = "".join(
                c for c in show["name"][:30].replace(" ", "_")
                if c.isalnum() or c in "._-"
            )
            dest_name = f"{i+1:02d}_{safe_name}.jpg"
            dest_path = images_dir / dest_name
            formatted.save(dest_path, "JPEG", quality=92)

            # Save _ig.jpg next to original for Vercel
            ig_path = src_path.parent / f"{src_path.stem}_ig.jpg"
            formatted.save(ig_path, "JPEG", quality=92)
            ig_web_path = ig_path.relative_to(PROJECT_ROOT).as_posix()
            web_url = f"{WEBSITE_BASE_URL}/{ig_web_path}"

            local_paths.append(dest_path)
            web_urls.append(web_url)
        except Exception as e:
            print(f"  Warning: Failed to process image for '{show['name']}': {e}")
            continue

        # Instagram carousel limit
        if len(local_paths) >= 10:
            print(f"  Note: Limited to 10 images for carousel")
            break

    return local_paths, web_urls


# ---------------------------------------------------------------------------
# Generate & Post
# ---------------------------------------------------------------------------

def do_generate(
    venue: Dict, urls: List[str], reference_date: datetime,
    direction: Optional[str] = None,
) -> Path:
    """
    Generate hot show alert content: look up shows, get fillers, build caption,
    process images. Returns the output directory.
    `direction` is optional free-text guidance for the AI caption.
    """
    date_str = reference_date.strftime("%Y-%m-%d")
    output_dir = OUTPUT_BASE / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nHot Show Alert Generator")
    print(f"Venue: {venue['display_name']} ({venue['key']})")
    print(f"Date: {reference_date.strftime('%A, %B %d, %Y')}")
    print(f"Featured URLs: {len(urls)}")
    print(f"Output: {output_dir}")
    print("-" * 40)

    # Look up featured shows by URL
    print("\nLooking up featured shows in database...")
    featured = lookup_shows_by_url(urls)
    print(f"Found {len(featured)} of {len(urls)} featured shows")
    for s in featured:
        print(f"  - {s['name']} ({s['date']}, {s['time']})")

    if not featured:
        print("\nERROR: No featured shows found in the database.")
        print("Make sure the URLs match source_url values in the images table.")
        sys.exit(1)

    # Get filler shows
    print("\nFetching filler shows...")
    exclude_urls = {s["source_url"] for s in featured}
    fillers = get_filler_shows(
        venue["db_name"], reference_date, exclude_urls,
        max_total=10, already_have=len(featured),
    )
    print(f"Found {len(fillers)} filler shows")
    for s in fillers:
        print(f"  - {s['name']} ({s['date']}, {s['time']})")

    # Combine: featured first (user order), then fillers
    all_shows = featured + fillers

    # Generate caption
    print("\nGenerating caption...")
    caption = generate_hot_show_caption(venue, featured, all_shows, direction)
    caption_path = output_dir / "caption.txt"
    caption_path.write_text(caption, encoding="utf-8")
    print(f"Caption saved to: {caption_path}")

    # Process images
    print("\nProcessing images...")
    local_paths, web_urls = process_show_images(all_shows, output_dir)
    print(f"Processed {len(local_paths)} images")

    # Build summary
    summary = {
        "type": "hot_show_alert",
        "date": reference_date.isoformat(),
        "date_display": reference_date.strftime("%A, %B %d, %Y"),
        "venue_key": venue["key"],
        "venue_name": venue["display_name"],
        "venue_instagram": venue["instagram"],
        "featured_count": len(featured),
        "filler_count": len(fillers),
        "total_shows": len(all_shows),
        "images_count": len(local_paths),
        "image_urls": web_urls,
        "shows": [
            {
                "name": s["name"],
                "date": s["date"],
                "time": s["time"],
                "is_featured": s["is_featured"],
            }
            for s in all_shows
        ],
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

    print(f"\n{'=' * 40}")
    print(f"IMAGES: {len(local_paths)}")
    print("=" * 40)
    for p in local_paths:
        print(f"  - {p.name}")

    return output_dir


def do_post(output_dir: Path, dry_run: bool = False) -> None:
    """
    Read generated content from output_dir and post to Instagram.
    Uses carousel if multiple images, single image if just one.
    """
    caption_path = output_dir / "caption.txt"
    summary_path = output_dir / "summary.json"

    if not caption_path.exists() or not summary_path.exists():
        raise FileNotFoundError(
            f"Generated content not found in {output_dir}. Run --generate-only first."
        )

    caption = caption_path.read_text(encoding="utf-8")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    image_urls = summary["image_urls"]

    print(f"\nHot Show Alert Poster")
    print(f"Venue: {summary['venue_name']}")
    print(f"Images: {len(image_urls)}")
    print(f"Caption: {len(caption)} characters")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 40)

    if dry_run:
        print(f"\n{'=' * 40}")
        print("DRY RUN - No post created")
        for i, url in enumerate(image_urls):
            print(f"  Image {i+1}: {url}")
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

    # Post
    print("\nPosting to Instagram...")
    try:
        if len(image_urls) == 1:
            media_id = poster.post_single_image(image_urls[0], caption)
        else:
            media_id = poster.post_carousel(image_urls, caption)

        print(f"\nPublish returned Media ID: {media_id}")

        # Verify
        print("Verifying post is live...")
        try:
            post_info = poster.verify_published_post(media_id)
            permalink = post_info.get("permalink", "N/A")
            print(f"VERIFIED: Post is live at {permalink}")
        except Exception as verify_err:
            print(f"\nWARNING: Verification failed ({verify_err}) but post was accepted.")
            print(f"Media ID {media_id} is probably live. Check Instagram manually.")
    except Exception as e:
        print(f"\nError posting: {e}")
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate and post a Hot Show Alert to Instagram"
    )
    parser.add_argument(
        "--venue",
        type=str,
        required=True,
        choices=list(VENUES.keys()),
        help="Venue key (creek_cave, cap_city, sunset_strip, rozcos, velveeta)",
    )
    parser.add_argument(
        "--urls",
        type=str,
        required=True,
        help="Comma-separated show URLs to feature",
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
    parser.add_argument(
        "--direction",
        type=str,
        default=None,
        help="Free-text direction for the AI caption (e.g. 'hype up the headliners')",
    )
    args = parser.parse_args()

    # Parse reference date
    if args.date:
        reference_date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        reference_date = datetime.now()

    venue = VENUES[args.venue]
    urls = [u.strip() for u in args.urls.split(",") if u.strip()]
    date_str = reference_date.strftime("%Y-%m-%d")
    output_dir = OUTPUT_BASE / date_str

    if args.post_only:
        do_post(output_dir, dry_run=args.dry_run)
    elif args.generate_only:
        do_generate(venue, urls, reference_date, direction=args.direction)
    else:
        do_generate(venue, urls, reference_date, direction=args.direction)
        do_post(output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
