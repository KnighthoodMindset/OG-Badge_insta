from motor.motor_asyncio import AsyncIOMotorClient
from .config import MONGO_URI, MONGO_DB

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]

users = db["users"]
posts = db["posts"]
badge_apps = db["badge_apps"]

async def ensure_indexes():
    # users
    await users.create_index("email", unique=True)
    await users.create_index("username")          # NOT unique (duplicates allowed)
    await users.create_index("created_at")

    # posts
    await posts.create_index("username")
    await posts.create_index("user_id")
    await posts.create_index("created_at")

    # ✅ NOT unique (duplicates allowed)
    await posts.create_index("media_sha256", sparse=True)

    # helpful
    await posts.create_index("media_dhash", sparse=True)
    await posts.create_index("product_keys")

    # badge applications (one per user)
    await badge_apps.create_index("user_id", unique=True)
    await badge_apps.create_index("username")
    await badge_apps.create_index("status")
    await badge_apps.create_index("created_at")

    # product-wise checks
    await badge_apps.create_index("product_key")   # old
    await badge_apps.create_index("product_keys")  # ✅ new (multi array)

    # ✅ violations tracking
    await badge_apps.create_index("violations")

    # allow only ONE APPROVED per username
    await badge_apps.create_index(
        [("username", 1)],
        unique=True,
        partialFilterExpression={"status": "APPROVED"},
        name="uniq_approved_username"
    )