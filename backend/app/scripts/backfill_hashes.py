import os
from pathlib import Path
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import MONGO_URI, MONGO_DB
from app.image_utils import sha256_bytes, dhash_bytes

UPLOADS = Path(__file__).resolve().parents[2] / "uploads"  # backend/uploads

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
posts = db["posts"]

def file_path_from_media_url(media_url: str) -> Path | None:
    if not media_url or not isinstance(media_url, str):
        return None
    if not media_url.startswith("/uploads/"):
        return None
    name = media_url.replace("/uploads/", "").strip()
    if not name:
        return None
    return UPLOADS / name

async def main():
    cur = posts.find(
        {
            "media_type": "image",
            "$or": [{"media_sha256": None}, {"media_dhash": None}],
        },
        {"media_url": 1, "media_sha256": 1, "media_dhash": 1},
    )

    updated = 0
    skipped = 0

    async for p in cur:
        path = file_path_from_media_url(p.get("media_url"))
        if not path or not path.exists():
            skipped += 1
            continue

        try:
            data = path.read_bytes()
            sha = sha256_bytes(data)
            dh = dhash_bytes(data)
        except Exception:
            skipped += 1
            continue

        await posts.update_one(
            {"_id": p["_id"]},
            {"$set": {"media_sha256": sha, "media_dhash": dh}},
        )
        updated += 1

    print("DONE")
    print("updated:", updated)
    print("skipped:", skipped)

if __name__ == "__main__":
    asyncio.run(main())