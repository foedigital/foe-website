#!/usr/bin/env python3
"""
Instagram Graph API Poster for Funny Over Everything

Posts daily comedy show content to Instagram using the Graph API.
Supports single images and carousel posts (up to 10 images).

Prerequisites:
1. Instagram Business or Creator account
2. Facebook Page linked to Instagram account
3. Meta Developer App with Instagram Graph API access
4. Long-lived access token with permissions:
   - instagram_basic
   - instagram_content_publish
   - pages_read_engagement

Environment Variables Required:
- INSTAGRAM_ACCESS_TOKEN: Your long-lived access token
- INSTAGRAM_ACCOUNT_ID: Your Instagram Business Account ID

Usage:
    python -m instagram.post_to_instagram [--date YYYY-MM-DD] [--dry-run]
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "instagram" / "daily_output"

# Instagram Graph API base URL
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"

# Image hosting - images need to be publicly accessible URLs
# You'll need to either:
# 1. Use your Vercel deployment URLs
# 2. Upload to a CDN/image host
# 3. Use a service like Cloudinary
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "https://funnyovereverything.com")


class InstagramPoster:
    """Handles posting content to Instagram via Graph API."""

    def __init__(self, access_token: str, account_id: str):
        self.access_token = access_token
        self.account_id = account_id
        self.api_base = GRAPH_API_BASE

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make a request to the Graph API."""
        url = f"{self.api_base}/{endpoint}"
        params = kwargs.get('params', {})
        params['access_token'] = self.access_token
        kwargs['params'] = params

        response = requests.request(method, url, **kwargs)

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            raise Exception(f"API Error {response.status_code}: {error_data}")

        return response.json()

    def get_account_info(self) -> Dict:
        """Get Instagram account information."""
        return self._make_request('GET', self.account_id, params={
            'fields': 'id,username,media_count'
        })

    def create_media_container(self, image_url: str, caption: str = None,
                                is_carousel_item: bool = False) -> str:
        """
        Create a media container for a single image.
        Returns the container ID.
        """
        params = {
            'image_url': image_url,
        }

        if is_carousel_item:
            params['is_carousel_item'] = 'true'
        elif caption:
            params['caption'] = caption

        result = self._make_request('POST', f"{self.account_id}/media", params=params)
        return result['id']

    def create_carousel_container(self, children_ids: List[str], caption: str) -> str:
        """
        Create a carousel container from multiple media containers.
        Returns the carousel container ID.
        """
        params = {
            'media_type': 'CAROUSEL',
            'children': ','.join(children_ids),
            'caption': caption,
        }

        result = self._make_request('POST', f"{self.account_id}/media", params=params)
        return result['id']

    def check_container_status(self, container_id: str) -> Tuple[str, Optional[str]]:
        """
        Check the status of a media container.
        Returns (status, error_message).
        Status can be: EXPIRED, ERROR, FINISHED, IN_PROGRESS, PUBLISHED
        """
        result = self._make_request('GET', container_id, params={
            'fields': 'status_code,status'
        })
        return result.get('status_code', 'UNKNOWN'), result.get('status')

    def wait_for_container(self, container_id: str, timeout: int = 60) -> bool:
        """
        Wait for a container to be ready for publishing.
        Returns True if ready, False if error/timeout.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            status, message = self.check_container_status(container_id)

            if status == 'FINISHED':
                return True
            elif status == 'ERROR':
                print(f"  Container error: {message}")
                return False
            elif status == 'EXPIRED':
                print(f"  Container expired")
                return False

            time.sleep(2)

        print(f"  Timeout waiting for container")
        return False

    def publish_container(self, container_id: str) -> str:
        """
        Publish a media container.
        Returns the published media ID.
        """
        result = self._make_request('POST', f"{self.account_id}/media_publish", params={
            'creation_id': container_id
        })
        return result['id']

    def post_single_image(self, image_url: str, caption: str) -> str:
        """Post a single image with caption."""
        print(f"Creating media container...")
        container_id = self.create_media_container(image_url, caption=caption)

        print(f"Waiting for processing...")
        if not self.wait_for_container(container_id):
            raise Exception("Failed to process image")

        print(f"Publishing...")
        media_id = self.publish_container(container_id)
        return media_id

    def post_carousel(self, image_urls: List[str], caption: str) -> str:
        """Post a carousel with multiple images."""
        if len(image_urls) < 2:
            raise ValueError("Carousel requires at least 2 images")
        if len(image_urls) > 10:
            print(f"Warning: Limiting to 10 images (had {len(image_urls)})")
            image_urls = image_urls[:10]

        # Create containers for each image
        print(f"Creating {len(image_urls)} media containers...")
        children_ids = []
        for i, url in enumerate(image_urls):
            print(f"  Image {i+1}/{len(image_urls)}: {url[:50]}...")
            container_id = self.create_media_container(url, is_carousel_item=True)
            children_ids.append(container_id)
            time.sleep(1)  # Rate limiting

        # Wait for all containers to be ready
        print(f"Waiting for processing...")
        for i, container_id in enumerate(children_ids):
            if not self.wait_for_container(container_id):
                raise Exception(f"Failed to process image {i+1}")

        # Create carousel container
        print(f"Creating carousel...")
        carousel_id = self.create_carousel_container(children_ids, caption)

        if not self.wait_for_container(carousel_id):
            raise Exception("Failed to create carousel")

        # Publish
        print(f"Publishing carousel...")
        media_id = self.publish_container(carousel_id)
        return media_id


def get_public_image_urls(images_dir: Path, base_url: str) -> List[str]:
    """
    Convert local image paths to public URLs.

    The images need to be accessible via public URL for Instagram to fetch them.
    This assumes images are deployed to your website.
    """
    urls = []

    # Get sorted list of images
    image_files = sorted(images_dir.glob("*.*"))

    for img_path in image_files:
        if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
            # Extract original image path from the renamed file
            # Files are named like: 01_Venue_Name_Show_Name.jpg
            # We need to find the original path in the database or construct URL

            # For now, we'll use a simpler approach - read from summary.json
            # which has the original show data
            urls.append(img_path)

    return urls


def load_daily_content(date_str: str) -> Tuple[str, List[Path], List[str], Dict]:
    """Load generated content for a specific date."""
    date_dir = OUTPUT_DIR / date_str

    if not date_dir.exists():
        raise FileNotFoundError(f"No content found for {date_str}. Run generate_daily_post.py first.")

    # Load caption
    caption_path = date_dir / "caption.txt"
    if not caption_path.exists():
        raise FileNotFoundError(f"Caption not found: {caption_path}")
    caption = caption_path.read_text(encoding='utf-8')

    # Load images
    images_dir = date_dir / "images"
    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")

    images = sorted(images_dir.glob("*.*"))
    images = [p for p in images if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']]

    # Load summary (contains public image URLs)
    summary_path = date_dir / "summary.json"
    summary = {}
    image_urls = []
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        image_urls = summary.get('image_urls', [])

    return caption, images, image_urls, summary


def construct_image_urls(images: List[Path], summary: Dict, base_url: str) -> List[str]:
    """
    Construct public URLs for images.

    Uses the original image paths from the database (stored in the show data)
    to create URLs pointing to the deployed website.
    """
    # For this to work, we need to map back to original paths
    # The images on the website are at paths like:
    # https://funnyovereverything.com/images/creek_and_the_cave/abc123.jpg

    # Since we renamed files, we need to look them up differently
    # For now, let's use a workaround: re-query the database for today's shows

    # Actually, the simplest approach is to serve images from a different source
    # or upload them to a hosting service

    # For initial implementation, we'll construct URLs assuming images
    # are accessible at a known path
    urls = []

    # Read from the renamed files and construct approximate URLs
    # This is a placeholder - in production you'd want to:
    # 1. Upload images to Cloudinary/S3/etc
    # 2. Or use the original paths from the database

    for img in images:
        # The image filename contains venue and show info
        # We could look this up, but for now we'll note this needs enhancement
        urls.append(str(img))  # Placeholder - needs public URL

    return urls


def upload_to_cloudinary(image_path: Path) -> str:
    """
    Upload image to Cloudinary and return public URL.
    Requires CLOUDINARY_URL environment variable.

    This is optional - only needed if images aren't publicly accessible.
    """
    cloudinary_url = os.environ.get('CLOUDINARY_URL')
    if not cloudinary_url:
        raise ValueError("CLOUDINARY_URL not set")

    # Parse cloudinary URL
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(cloudinary_url=cloudinary_url)

    result = cloudinary.uploader.upload(str(image_path))
    return result['secure_url']


def main():
    parser = argparse.ArgumentParser(description='Post daily content to Instagram')
    parser.add_argument('--date', type=str, help='Date to post (YYYY-MM-DD), defaults to today')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be posted without posting')
    parser.add_argument('--use-cloudinary', action='store_true', help='Upload images to Cloudinary first')
    args = parser.parse_args()

    # Get credentials from environment
    access_token = os.environ.get('INSTAGRAM_ACCESS_TOKEN')
    account_id = os.environ.get('INSTAGRAM_ACCOUNT_ID')

    if not args.dry_run and (not access_token or not account_id):
        print("Error: Missing environment variables")
        print("Required:")
        print("  INSTAGRAM_ACCESS_TOKEN - Your long-lived access token")
        print("  INSTAGRAM_ACCOUNT_ID - Your Instagram Business Account ID")
        print("\nUse --dry-run to test without credentials")
        sys.exit(1)

    # Determine date
    if args.date:
        target_date = args.date
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print(f"\nInstagram Poster")
    print(f"Date: {target_date}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("-" * 40)

    # Load content
    try:
        caption, images, image_urls, summary = load_daily_content(target_date)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nRun the generator first:")
        print(f"  python -m instagram.generate_daily_post --date {target_date}")
        sys.exit(1)

    print(f"\nLoaded content:")
    print(f"  Shows: {summary.get('total_shows', 'unknown')}")
    print(f"  Images: {len(images)}")
    print(f"  Image URLs: {len(image_urls)}")
    print(f"  Caption: {len(caption)} characters")

    # Preview
    print(f"\n{'='*40}")
    print("CAPTION PREVIEW:")
    print('='*40)
    print(caption[:300])
    if len(caption) > 300:
        print(f"... ({len(caption)} total chars)")

    print(f"\n{'='*40}")
    print("IMAGES:")
    print('='*40)
    for i, img in enumerate(images[:5]):
        url = image_urls[i] if i < len(image_urls) else "No URL"
        print(f"  - {img.name}")
        print(f"    URL: {url}")
    if len(images) > 5:
        print(f"  ... and {len(images) - 5} more")

    if args.dry_run:
        print(f"\n{'='*40}")
        print("DRY RUN - No post created")
        print("To post for real, run without --dry-run flag")
        print("Make sure INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID are set")
        return

    # Get public URLs for images
    print(f"\nPreparing images...")

    if args.use_cloudinary:
        print("Uploading to Cloudinary...")
        image_urls = []
        for img in images:
            url = upload_to_cloudinary(img)
            image_urls.append(url)
            print(f"  Uploaded: {url}")
    elif not image_urls:
        print("\nERROR: No image URLs found in summary.json")
        print("Make sure to regenerate the content:")
        print(f"  python -m instagram.generate_daily_post --date {target_date}")
        sys.exit(1)
    else:
        print(f"Using {len(image_urls)} URLs from funnyovereverything.com")

    # Create poster and post
    poster = InstagramPoster(access_token, account_id)

    # Verify account access
    print(f"\nVerifying account access...")
    try:
        account_info = poster.get_account_info()
        print(f"  Account: @{account_info.get('username', 'unknown')}")
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)

    # Post content
    print(f"\nPosting to Instagram...")
    try:
        if len(image_urls) == 1:
            media_id = poster.post_single_image(image_urls[0], caption)
        else:
            media_id = poster.post_carousel(image_urls, caption)

        print(f"\nSuccess! Media ID: {media_id}")
        print(f"View at: https://www.instagram.com/p/{media_id}/")

    except Exception as e:
        print(f"\nError posting: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
