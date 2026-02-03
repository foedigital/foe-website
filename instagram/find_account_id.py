#!/usr/bin/env python3
"""
Find your Instagram Business Account ID.

This script queries the Facebook Graph API to find the Instagram Business
Account linked to your Facebook Page. You need this ID to post via the
Instagram Graph API.

Prerequisites:
- A Facebook Page linked to your Instagram Business/Creator account
- A long-lived access token with permissions:
  - instagram_basic
  - pages_read_engagement

Usage:
    python instagram/find_account_id.py --token YOUR_ACCESS_TOKEN

Or set the environment variable:
    export INSTAGRAM_ACCESS_TOKEN=your_token
    python instagram/find_account_id.py
"""

import argparse
import os
import sys
import requests

GRAPH_API_BASE = "https://graph.facebook.com/v22.0"


def find_instagram_account_id(access_token: str) -> None:
    """Query the Graph API to find the Instagram Business Account ID."""

    # Step 1: Get Facebook Pages the user manages
    print("Fetching your Facebook Pages...")
    response = requests.get(
        f"{GRAPH_API_BASE}/me/accounts",
        params={"access_token": access_token},
    )

    if response.status_code != 200:
        error = response.json().get("error", {})
        print(f"Error fetching pages: {error.get('message', response.text)}")
        sys.exit(1)

    pages = response.json().get("data", [])
    if not pages:
        print("No Facebook Pages found for this token.")
        print("Make sure your token has the 'pages_read_engagement' permission.")
        sys.exit(1)

    print(f"Found {len(pages)} Facebook Page(s):\n")

    # Step 2: Check each page for a linked Instagram Business Account
    found = False
    for page in pages:
        page_name = page.get("name", "Unknown")
        page_id = page["id"]
        print(f"  Page: {page_name} (ID: {page_id})")

        ig_response = requests.get(
            f"{GRAPH_API_BASE}/{page_id}",
            params={
                "fields": "instagram_business_account",
                "access_token": access_token,
            },
        )

        if ig_response.status_code != 200:
            print(f"    Could not query this page for Instagram account.")
            continue

        ig_data = ig_response.json().get("instagram_business_account")
        if ig_data:
            ig_id = ig_data["id"]
            print(f"    -> Instagram Business Account ID: {ig_id}")

            # Get Instagram account details
            detail_response = requests.get(
                f"{GRAPH_API_BASE}/{ig_id}",
                params={
                    "fields": "username,account_type,media_count",
                    "access_token": access_token,
                },
            )
            if detail_response.status_code == 200:
                details = detail_response.json()
                print(f"       Username: @{details.get('username', 'unknown')}")
                print(f"       Type: {details.get('account_type', 'unknown')}")
                print(f"       Posts: {details.get('media_count', 'unknown')}")

            found = True
            print(f"\n{'='*50}")
            print(f"Add this as your INSTAGRAM_ACCOUNT_ID secret:")
            print(f"  {ig_id}")
            print(f"{'='*50}")
        else:
            print(f"    No Instagram Business Account linked to this page.")

    if not found:
        print("\nNo Instagram Business Account found.")
        print("Make sure:")
        print("  1. Your Instagram account is a Business or Creator account")
        print("  2. It is linked to one of your Facebook Pages")
        print("  3. Your access token has 'instagram_basic' permission")


def main():
    parser = argparse.ArgumentParser(
        description="Find your Instagram Business Account ID"
    )
    parser.add_argument(
        "--token",
        type=str,
        help="Facebook/Instagram access token (or set INSTAGRAM_ACCESS_TOKEN env var)",
    )
    args = parser.parse_args()

    access_token = args.token or os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if not access_token:
        print("Error: No access token provided.")
        print("Use --token YOUR_TOKEN or set INSTAGRAM_ACCESS_TOKEN env var.")
        sys.exit(1)

    find_instagram_account_id(access_token)


if __name__ == "__main__":
    main()
