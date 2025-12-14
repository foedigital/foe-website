import hashlib
import aiohttp
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse
from PIL import Image
import io

from .config import MIN_IMAGE_WIDTH, MIN_IMAGE_HEIGHT, USER_AGENT

IMAGES_DIR = Path(__file__).parent.parent / "images"


def get_image_extension(url: str, content_type: Optional[str] = None) -> str:
    """Determine image extension from URL or content type."""
    if content_type:
        type_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        if content_type in type_map:
            return type_map[content_type]

    path = urlparse(url).path.lower()
    for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext

    return ".jpg"


def calculate_hash(data: bytes) -> str:
    """Calculate SHA256 hash of image data."""
    return hashlib.sha256(data).hexdigest()


def validate_image(data: bytes) -> Tuple[bool, Optional[Tuple[int, int]]]:
    """Validate image data and check dimensions."""
    try:
        img = Image.open(io.BytesIO(data))
        width, height = img.size
        if width >= MIN_IMAGE_WIDTH and height >= MIN_IMAGE_HEIGHT:
            return True, (width, height)
        return False, (width, height)
    except Exception:
        return False, None


async def download_image(
    url: str,
    venue_name: str,
    session: Optional[aiohttp.ClientSession] = None
) -> Optional[Tuple[bytes, str, str]]:
    """
    Download an image from URL.
    Returns: (image_data, hash, extension) or None if failed.
    """
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        headers = {"User-Agent": USER_AGENT}
        async with session.get(url, headers=headers, timeout=30) as response:
            if response.status != 200:
                return None

            content_type = response.headers.get("Content-Type", "")
            data = await response.read()

            is_valid, dimensions = validate_image(data)
            if not is_valid:
                return None

            image_hash = calculate_hash(data)
            extension = get_image_extension(url, content_type)

            return data, image_hash, extension

    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None
    finally:
        if close_session:
            await session.close()


def save_image(
    data: bytes,
    venue_name: str,
    image_hash: str,
    extension: str
) -> str:
    """Save image data to disk, return relative path."""
    venue_dir = IMAGES_DIR / venue_name.lower().replace(" ", "_").replace("'", "")
    venue_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{image_hash[:16]}{extension}"
    filepath = venue_dir / filename

    with open(filepath, "wb") as f:
        f.write(data)

    return str(filepath.relative_to(IMAGES_DIR.parent))


async def download_and_save(
    url: str,
    venue_name: str,
    session: Optional[aiohttp.ClientSession] = None
) -> Optional[Tuple[str, str]]:
    """
    Download and save an image.
    Returns: (local_path, hash) or None if failed.
    """
    result = await download_image(url, venue_name, session)
    if result is None:
        return None

    data, image_hash, extension = result
    local_path = save_image(data, venue_name, image_hash, extension)

    return local_path, image_hash
