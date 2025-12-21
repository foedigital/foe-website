#!/usr/bin/env python3
"""
Master orchestration script for ATX Comedy Show scraping.

Runs all scrapers and regenerates HTML files.
Used by GitHub Actions for automated daily updates.

Usage:
    python run_all_scrapers.py
"""

import subprocess
import sys
from datetime import datetime


def run_command(description, command):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(command)}")

    result = subprocess.run(command, capture_output=False)

    if result.returncode != 0:
        print(f"WARNING: {description} exited with code {result.returncode}")
        return False
    return True


def main():
    print("="*60)
    print(f"ATX Comedy Show Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    success_count = 0
    total_count = 3

    # Step 1: Run modern scraper module (7 venues)
    if run_command(
        "Step 1/3: Running modern scraper (7 venues)",
        [sys.executable, "-m", "scraper.main", "--all"]
    ):
        success_count += 1

    # Step 2: Run Cap City Comedy scraper (standalone)
    if run_command(
        "Step 2/3: Running Cap City Comedy scraper",
        [sys.executable, "scrape_capcity.py"]
    ):
        success_count += 1

    # Step 3: Regenerate HTML files
    if run_command(
        "Step 3/3: Regenerating HTML files",
        [sys.executable, "regenerate_shows.py"]
    ):
        success_count += 1

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print("="*60)
    print(f"Completed: {success_count}/{total_count} steps successful")

    if success_count == total_count:
        print("All scrapers and HTML generation completed successfully!")
        return 0
    else:
        print("Some steps had warnings - check output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
