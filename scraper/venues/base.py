from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from playwright.async_api import Page

from ..config import PAGE_LOAD_WAIT


class BaseScraper(ABC):
    """Base class for venue-specific scrapers."""

    venue_key: str
    venue_name: str
    venue_url: str
    events_url: str
    image_selectors: List[str]
    event_name_selector: str
    event_date_selector: str

    def __init__(self, config: dict):
        self.venue_name = config["name"]
        self.venue_url = config["url"]
        self.events_url = config["events_url"]
        self.image_selectors = config["image_selectors"]
        self.event_name_selector = config.get("event_name_selector", "")
        self.event_date_selector = config.get("event_date_selector", "")

    async def scrape(self, page: Page) -> List[Dict]:
        """
        Scrape event images from the venue page.
        Returns list of dicts: {"url": str, "event_name": str|None, "event_date": str|None}
        """
        await page.goto(self.events_url, wait_until="networkidle")
        await page.wait_for_timeout(PAGE_LOAD_WAIT)

        await self.handle_pagination(page)

        images = []
        for selector in self.image_selectors:
            found = await self.extract_images(page, selector)
            images.extend(found)

        seen_urls = set()
        unique_images = []
        for img in images:
            if img["url"] not in seen_urls:
                seen_urls.add(img["url"])
                unique_images.append(img)

        return unique_images

    async def handle_pagination(self, page: Page):
        """Override in subclass to handle load more buttons, infinite scroll, etc."""
        pass

    async def extract_images(self, page: Page, selector: str) -> List[Dict]:
        """Extract image URLs and metadata using the given selector."""
        images = []

        elements = await page.query_selector_all(selector)
        for element in elements:
            src = await element.get_attribute("src")
            if not src:
                srcset = await element.get_attribute("srcset")
                if srcset:
                    src = srcset.split(",")[0].split()[0]

            if not src:
                continue

            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = self.venue_url + src

            if not self.is_valid_image_url(src):
                continue

            event_name = await self.get_event_name(element, page)
            event_date = await self.get_event_date(element, page)

            images.append({
                "url": src,
                "event_name": event_name,
                "event_date": event_date,
            })

        return images

    def is_valid_image_url(self, url: str) -> bool:
        """Check if URL looks like a valid event image."""
        url_lower = url.lower()

        skip_patterns = [
            "logo", "icon", "favicon", "avatar", "profile",
            "button", "arrow", "social", "facebook", "twitter",
            "instagram", "youtube", "sprite", "placeholder",
            "1x1", "pixel", "tracking", "analytics",
        ]
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False

        valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        has_valid_ext = any(ext in url_lower for ext in valid_extensions)

        is_cdn = any(cdn in url_lower for cdn in [
            "cdn.", "cloudinary", "imgix", "cloudfront",
            "squarespace", "website-files", "eventbrite"
        ])

        return has_valid_ext or is_cdn

    async def get_event_name(self, img_element, page: Page) -> Optional[str]:
        """Try to extract event name from nearby elements."""
        if not self.event_name_selector:
            return None

        try:
            parent = await img_element.evaluate_handle("el => el.closest('div, article, section, a')")
            if parent:
                name_el = await parent.query_selector(self.event_name_selector)
                if name_el:
                    text = await name_el.inner_text()
                    return text.strip() if text else None
        except Exception:
            pass

        return None

    async def get_event_date(self, img_element, page: Page) -> Optional[str]:
        """Try to extract event date from nearby elements."""
        if not self.event_date_selector:
            return None

        try:
            parent = await img_element.evaluate_handle("el => el.closest('div, article, section, a')")
            if parent:
                date_el = await parent.query_selector(self.event_date_selector)
                if date_el:
                    text = await date_el.inner_text()
                    return text.strip() if text else None
        except Exception:
            pass

        return None
