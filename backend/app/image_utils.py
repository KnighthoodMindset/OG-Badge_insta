# backend/app/image_utils.py

import io
import hashlib
from typing import Optional, Dict

from PIL import Image, ImageOps, ImageFile
import imagehash

# -------------------------
# SAFETY + CONSISTENCY
# -------------------------
# Allow loading slightly truncated images (common with social uploads)
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Protect against huge images (decompression bomb)
# (You can tune this if you expect very large images)
Image.MAX_IMAGE_PIXELS = 30_000_000  # ~30 MP

# -------------------------
# STRONGER HASH SETTINGS
# -------------------------
HASH_SIZE = 16  # default 8 -> now 16 (much stronger)

# Optional: downscale before hashing for speed + stability
# Keep None to avoid resizing. If you want, set e.g. 512 or 768.
HASH_MAX_SIDE: Optional[int] = 768


# -------------------------
# SHA256 (Exact Duplicate)
# -------------------------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# -------------------------
# IMAGE LOADER
# -------------------------
def _load_rgb(b: bytes) -> Image.Image:
    """
    Safer loader:
      - fully loads image
      - applies EXIF orientation fix
      - converts to RGB for stable hashing
      - optional resize for hashing stability/speed
    """
    img = Image.open(io.BytesIO(b))
    img.load()

    # Fix orientation (important for perceptual hashes)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Normalize mode
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        # keep grayscale allowed, but convert to RGB for consistent hashing
        img = img.convert("RGB")

    # Optional resize
    if HASH_MAX_SIDE and max(img.size) > HASH_MAX_SIDE:
        img.thumbnail((HASH_MAX_SIDE, HASH_MAX_SIDE), Image.Resampling.LANCZOS)

    return img


# -------------------------
# MULTI PERCEPTUAL HASHES
# -------------------------
def dhash_bytes(b: bytes) -> str:
    img = _load_rgb(b)
    return str(imagehash.dhash(img, hash_size=HASH_SIZE))


def phash_bytes(b: bytes) -> str:
    img = _load_rgb(b)
    return str(imagehash.phash(img, hash_size=HASH_SIZE))


def ahash_bytes(b: bytes) -> str:
    img = _load_rgb(b)
    return str(imagehash.average_hash(img, hash_size=HASH_SIZE))


def compute_hashes_bytes(b: bytes) -> Dict[str, str]:
    """
    Convenience helper: returns all hashes + sha256 in one shot.
    Useful if you want to store multiple hashes per post.
    """
    return {
        "sha256": sha256_bytes(b),
        "dhash": dhash_bytes(b),
        "phash": phash_bytes(b),
        "ahash": ahash_bytes(b),
    }


# -------------------------
# DISTANCE FUNCTIONS
# -------------------------
def hash_distance(h1: str, h2: str) -> int:
    """
    Generic distance for hex hashes produced by imagehash.
    Smaller => more similar.
    """
    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)


# Backward compatible alias (your services.py currently imports dhash_distance)
def dhash_distance(h1: str, h2: str) -> int:
    return hash_distance(h1, h2)


def is_near_duplicate(h1: str, h2: str, threshold: int = 12) -> bool:
    """
    Works for dhash/phash/ahash.

    Threshold guide (hash_size=16):
      0  => exact
      6  => very strict
      10 => strict
      12 => moderate
      15 => relaxed
    """
    try:
        return hash_distance(h1, h2) <= threshold
    except Exception:
        return False


def any_near_duplicate(
    dh1: Optional[str],
    dh2: Optional[str],
    ph1: Optional[str],
    ph2: Optional[str],
    ah1: Optional[str],
    ah2: Optional[str],
    *,
    dhash_threshold: int = 12,
    phash_threshold: int = 12,
    ahash_threshold: int = 12,
) -> bool:
    """
    Stronger "near duplicate" check using multiple perceptual hashes.
    Returns True if ANY of the provided hash pairs are near-duplicates.

    Use this when you store multiple hashes and want robust detection.
    """
    try:
        if dh1 and dh2 and is_near_duplicate(dh1, dh2, threshold=dhash_threshold):
            return True
        if ph1 and ph2 and is_near_duplicate(ph1, ph2, threshold=phash_threshold):
            return True
        if ah1 and ah2 and is_near_duplicate(ah1, ah2, threshold=ahash_threshold):
            return True
        return False
    except Exception:
        return False