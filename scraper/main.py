#!/usr/bin/env python3
"""
ATX Comedy Venue Image Scraper

Usage:
    python -m scraper.main --all              # Scrape all venues
    python -m scraper.main --venue creek_cave # Scrape specific venue
    python -m scraper.main --list             # List available venues
    python -m scraper.main --status           # Show recent sync status
"""

import argparse
import asyncio
import aiohttp
from typing import Optional

from playwright.async_api import async_playwright

from .database import (
    init_db,
    get_or_create_venue,
    update_venue_last_scraped,
    image_exists,
    hash_exists,
    add_image,
    start_sync_log,
    complete_sync_log,
    get_recent_syncs,
)
from .downloader import download_and_save
from .config import VENUES, USER_AGENT
from .venues import SCRAPERS


async def scrape_venue(venue_key: str, browser) -> dict:
    """Scrape a single venue and return stats."""
    if venue_key not in SCRAPERS:
        print(f"Unknown venue: {venue_key}")
        return {"status": "error", "message": f"Unknown venue: {venue_key}"}

    config = VENUES[venue_key]
    scraper_class = SCRAPERS[venue_key]
    scraper = scraper_class()

    venue_id = get_or_create_venue(config["name"], config["url"])
    log_id = start_sync_log(venue_id)

    print(f"\nScraping {config['name']}...")
    print(f"  URL: {config['events_url']}")

    images_found = 0
    images_new = 0
    error_message = None

    try:
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        images = await scraper.scrape(page)
        images_found = len(images)
        print(f"  Found {images_found} images")

        async with aiohttp.ClientSession() as session:
            for img in images:
                url = img["url"]

                if image_exists(url):
                    continue

                result = await download_and_save(url, config["name"], session)
                if result is None:
                    continue

                local_path, image_hash = result

                existing_path = hash_exists(image_hash)
                if existing_path:
                    continue

                # Use ticket_url as source_url if available (for proper ticket linking)
                # Otherwise fall back to image URL
                stored_url = img.get("ticket_url") or url

                add_image(
                    venue_id=venue_id,
                    source_url=stored_url,
                    local_path=local_path,
                    image_hash=image_hash,
                    event_name=img.get("event_name"),
                    event_date=img.get("event_date"),
                )
                images_new += 1
                print(f"  + New: {img.get('event_name') or url[:50]}...")

        await context.close()
        update_venue_last_scraped(venue_id)
        status = "success"

    except Exception as e:
        error_message = str(e)
        status = "failed"
        print(f"  Error: {error_message}")

    complete_sync_log(log_id, images_found, images_new, status, error_message)
    print(f"  Done: {images_new} new images saved")

    return {
        "venue": config["name"],
        "status": status,
        "images_found": images_found,
        "images_new": images_new,
        "error": error_message,
    }


async def scrape_all(browser) -> list:
    """Scrape all venues."""
    results = []
    for venue_key in SCRAPERS.keys():
        result = await scrape_venue(venue_key, browser)
        results.append(result)
    return results


def list_venues():
    """List all available venues."""
    print("\nAvailable venues:")
    print("-" * 40)
    for key, config in VENUES.items():
        print(f"  {key:15} - {config['name']}")
    print()


def show_status():
    """Show recent sync status."""
    syncs = get_recent_syncs(limit=20)
    if not syncs:
        print("\nNo sync history found.")
        return

    print("\nRecent sync history:")
    print("-" * 70)
    print(f"{'Venue':<25} {'Status':<10} {'Found':<8} {'New':<8} {'Time'}")
    print("-" * 70)

    for sync in syncs:
        time_str = sync.get("completed_at", sync.get("started_at", ""))[:19]
        print(
            f"{sync['venue_name']:<25} "
            f"{sync['status']:<10} "
            f"{sync.get('images_found', 0):<8} "
            f"{sync.get('images_new', 0):<8} "
            f"{time_str}"
        )
    print()


async def main():
    parser = argparse.ArgumentParser(
        description="ATX Comedy Venue Image Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--venue", "-v",
        help="Scrape a specific venue (use --list to see options)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Scrape all venues"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available venues"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show recent sync status"
    )

    args = parser.parse_args()

    init_db()

    if args.list:
        list_venues()
        return

    if args.status:
        show_status()
        return

    if not args.venue and not args.all:
        parser.print_help()
        return

    print("Starting ATX Comedy Image Scraper...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        if args.all:
            results = await scrape_all(browser)
        elif args.venue:
            results = [await scrape_venue(args.venue, browser)]

        await browser.close()

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    total_found = 0
    total_new = 0
    for r in results:
        total_found += r.get("images_found", 0)
        total_new += r.get("images_new", 0)
        status_icon = "[OK]" if r["status"] == "success" else "[FAIL]"
        print(f"{status_icon} {r['venue']}: {r.get('images_new', 0)} new images")

    print("-" * 50)
    print(f"Total: {total_found} found, {total_new} new images saved")


if __name__ == "__main__":
    asyncio.run(main())
