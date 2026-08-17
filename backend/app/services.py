# backend/app/services.py

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId
from fastapi import HTTPException
import re
from difflib import SequenceMatcher

from .db import users, posts, badge_apps
from .security import hash_password, verify_password
from .gst import is_valid_gstin
from .image_utils import (
    sha256_bytes,
    dhash_bytes,
    phash_bytes,
    ahash_bytes,
    dhash_distance,  # backward-compatible generic distance
)

# -------------------------
# HELPERS
# -------------------------
def _now():
    return datetime.now(timezone.utc)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _norm_product_strict(s: str) -> str:
    # strict-ish normalize for "key" storage
    return (s or "").strip().lower()


def _norm_key_for_similarity(s: str) -> str:
    """
    Normalize for look-alike detection:
      - lowercase
      - remove spaces, hyphens, underscores, dots etc.
      - keep only a-z0-9
    """
    s = (s or "").strip().lower()
    s = re.sub(r"[\s\-_\.]+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _sim(a: str, b: str) -> float:
    """
    Similarity ratio (0..1). Higher => more similar.
    Uses normalized keys to catch look-alikes (heliocare vs helocare, bisleri vs bilseri).
    """
    a2 = _norm_key_for_similarity(a)
    b2 = _norm_key_for_similarity(b)
    if not a2 or not b2:
        return 0.0
    return SequenceMatcher(None, a2, b2).ratio()


# -------------------------
# PRODUCT EXTRACTION
# -------------------------
_PRODUCT_RE = re.compile(r"product\s*name\s*:\s*(.+)", re.IGNORECASE)


def _extract_product_from_caption(caption: str) -> list[str]:
    text = caption or ""
    results: list[str] = []

    def clean_val(val: str) -> str:
        val = (val or "").strip()
        for sep in ["|", ",", ";"]:
            if sep in val:
                val = val.split(sep, 1)[0].strip()
        if val.endswith("."):
            val = val[:-1].strip()
        return val

    for line in text.splitlines():
        m = _PRODUCT_RE.search(line)
        if m:
            v = clean_val(m.group(1))
            if v:
                results.append(v)

    if not results:
        m = _PRODUCT_RE.search(text)
        if m:
            v = clean_val(m.group(1))
            if v:
                results.append(v)

    return results


def _caption_product_keys(caption: str) -> list[str]:
    return [_norm_product_strict(x) for x in _extract_product_from_caption(caption)]


# -------------------------
# AD CHECK
# -------------------------
def _has_ad(caption: str) -> bool:
    t = (caption or "").lower()
    if re.search(r"(^|\s)#?ad(\s|$)", t):
        return True
    if "paid partnership" in t or "sponsored" in t:
        return True
    return False


def _caption_has_any_product_tag(caption: str) -> bool:
    return len(_extract_product_from_caption(caption or "")) > 0
async def _user_has_any_duplicate_image(user_id: str, threshold: int = 12) -> bool:
    """
    Badge eligibility: reject if user posted any image that is a duplicate / near-duplicate
    of an EARLIER image posted by another user.
    Works even if jpg/png differs (uses perceptual hashes).
    """

    cur = posts.find(
        {"user_id": user_id, "media_type": "image"},
        {
            "media_sha256": 1,
            "media_dhash": 1,
            "media_phash": 1,
            "media_ahash": 1,
            "created_at": 1,
        },
    ).limit(2000)

    async for p in cur:
        t = p.get("created_at")
        if not t:
            continue

        # 1) Exact duplicate by sha256 (same bytes)
        sha = p.get("media_sha256")
        if sha:
            earlier = await posts.find_one(
                {
                    "media_sha256": sha,
                    "created_at": {"$lt": t},
                    "user_id": {"$ne": user_id},
                },
                {"_id": 1},
            )
            if earlier:
                return True

        # 2) Near duplicate by perceptual hashes (format independent)
        dh = p.get("media_dhash")
        ph = p.get("media_phash")
        ah = p.get("media_ahash")

        if not dh and not ph and not ah:
            continue

        other_cur = posts.find(
            {
                "user_id": {"$ne": user_id},
                "media_type": "image",
                "created_at": {"$lt": t},  # ONLY earlier posts should count
                "$or": [
                    {"media_dhash": {"$ne": None}},
                    {"media_phash": {"$ne": None}},
                    {"media_ahash": {"$ne": None}},
                ],
            },
            {"media_dhash": 1, "media_phash": 1, "media_ahash": 1},
        ).limit(5000)

        async for op in other_cur:
            try:
                if dh and op.get("media_dhash") and len(dh) == len(op["media_dhash"]):
                    if dhash_distance(dh, op["media_dhash"]) <= threshold:
                        return True

                if ph and op.get("media_phash") and len(ph) == len(op["media_phash"]):
                    if dhash_distance(ph, op["media_phash"]) <= threshold:
                        return True

                if ah and op.get("media_ahash") and len(ah) == len(op["media_ahash"]):
                    if dhash_distance(ah, op["media_ahash"]) <= threshold:
                        return True
            except Exception:
                continue

    return False

# -------------------------
# BADGE VIOLATIONS (NO REVOKE, ONLY STRIKES)
# -------------------------
async def _inc_violation(user_id: str, reason: str) -> None:
    """
    We DO NOT revoke badge now.
    We just store violation count + last_violation_reason.
    """
    await badge_apps.update_one(
        {"user_id": user_id, "status": "APPROVED"},
        {
            "$inc": {"violations": 1},
            "$set": {"last_violation_reason": reason, "updated_at": _now()},
        },
    )


async def _auto_delete_post(user_id: str, post_id: ObjectId, reason: str) -> dict | None:
    """
    Delete the post doc from DB and return deleted post document (for main.py to delete file).
    NOTE: DO NOT increment violations here (to avoid double counting).
    The caller (_enforce_badge_rules_pre_insert) already increments when needed.
    """
    p = await posts.find_one({"_id": post_id})
    if not p:
        return None

    if p.get("user_id") != user_id:
        return None

    await posts.delete_one({"_id": post_id})
    return p

async def _enforce_badge_rules_pre_insert(
    user_id: str,
    caption: str,
    media_type: str,
    media_sha256: str | None,
    media_dhash: str | None,
    media_phash: str | None,
    media_ahash: str | None,
) -> tuple[bool, str | None]:
    """
    Enforcement:
    - Only for APPROVED badge holders:
        * Duplicate / near-duplicate images from other users => auto-delete
        * Product post must contain Ad (if product tag exists)
    - Non-badge users: no auto-delete for duplicate images.
    """
    uploader_approved = await badge_apps.find_one(
        {"user_id": user_id, "status": "APPROVED"},
        {"_id": 1},
    )

    # Only badge holders get strict enforcement
    if uploader_approved:
        # Rule B: exact duplicate (only for approved)
        if media_type == "image" and await _is_duplicate_image_from_other_user(user_id, media_sha256):
            msg = "Post auto-deleted: Duplicate image detected (already exists in another account). Badge is kept."
            await _inc_violation(user_id, msg)
            return (True, msg)

        # Rule C: near-duplicate (only for approved)
        if media_type == "image" and await _is_near_duplicate_from_other_user(
            user_id,
            media_dhash,
            media_phash,
            media_ahash,
            threshold=12,
        ):
            msg = "Post auto-deleted: Near-duplicate image detected (edited/cropped copy). Badge is kept."
            await _inc_violation(user_id, msg)
            return (True, msg)

        # Rule A: Ad required for product-tagged posts (only for approved)
        if _caption_has_any_product_tag(caption) and not _has_ad(caption):
            msg = "Post auto-deleted: Product post must include 'Ad' (or Sponsored/Paid partnership). Badge is kept."
            await _inc_violation(user_id, msg)
            return (True, msg)

    return (False, None)

# -------------------------
# ONE-TIME: BACKFILL HASHES FOR OLD POSTS (LOCAL uploads ONLY)
# -------------------------
async def backfill_post_hashes(upload_dir: str) -> dict:
    """
    For old posts where media_sha256/media_dhash/media_phash/media_ahash are missing,
    compute from /uploads files and update DB.

    NOTE:
    This works only if you have local access to the same /uploads folder.
    If you're using MongoDB Atlas + cloud storage, this cannot read those files.
    """
    base = Path(upload_dir)

    cur = posts.find(
        {
            "media_type": "image",
            "$or": [
                {"media_sha256": None},
                {"media_dhash": None},
                {"media_phash": None},
                {"media_ahash": None},
            ],
            "media_url": {"$regex": r"^/uploads/"},
        },
        {"media_url": 1},
    ).limit(10000)

    updated = 0
    skipped = 0

    async for p in cur:
        url = p.get("media_url", "")
        if not isinstance(url, str) or not url.startswith("/uploads/"):
            skipped += 1
            continue

        fn = url.replace("/uploads/", "").strip()
        fp = base / fn
        if not fp.exists():
            skipped += 1
            continue

        try:
            data = fp.read_bytes()
            sha = sha256_bytes(data)
            dh = dhash_bytes(data)
            ph = phash_bytes(data)
            ah = ahash_bytes(data)
        except Exception:
            skipped += 1
            continue

        await posts.update_one(
            {"_id": p["_id"]},
            {
                "$set": {
                    "media_sha256": sha,
                    "media_dhash": dh,
                    "media_phash": ph,
                    "media_ahash": ah,
                    "updated_at": _now(),
                }
            },
        )
        updated += 1

    return {"ok": True, "updated": updated, "skipped": skipped}


# -------------------------
# USERS
# -------------------------
async def register_user(email: str, password: str, username: str):
    doc = {
        "email": email.lower().strip(),
        "password_hash": hash_password(password),
        "username": username.strip(),
        "created_at": _now(),
    }
    try:
        res = await users.insert_one(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Email already registered")

    doc["_id"] = res.inserted_id
    return doc


async def login_user(email: str, password: str):
    u = await users.find_one({"email": email.lower().strip()})
    if not u:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return u


async def get_user_by_id(user_id: str):
    try:
        return await users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


# -------------------------
# POSTS
# -------------------------
async def create_post(
    user_id: str,
    username: str,
    media_url: str,
    media_type: str,
    caption: str,
    media_sha256: str | None = None,
    media_dhash: str | None = None,
    media_phash: str | None = None,
    media_ahash: str | None = None,
):
    blocked, msg = await _enforce_badge_rules_pre_insert(
        user_id=user_id,
        caption=caption or "",
        media_type=media_type,
        media_sha256=media_sha256,
        media_dhash=media_dhash,
        media_phash=media_phash,
        media_ahash=media_ahash,
    )
    if blocked:
        return {"post": None, "warning": msg, "blocked": True}

    raw_products = _extract_product_from_caption(caption or "")
    product_keys = [_norm_product_strict(x) for x in raw_products if _norm_product_strict(x)]

    doc = {
        "user_id": user_id,
        "username": username,
        "media_url": media_url,
        "media_type": media_type,
        "caption": caption or "",
        "product_names_raw": raw_products,
        "product_keys": product_keys,
        "media_sha256": media_sha256,
        "media_dhash": media_dhash,
        "media_phash": media_phash,
        "media_ahash": media_ahash,
        "created_at": _now(),
        "updated_at": _now(),
    }
    res = await posts.insert_one(doc)
    doc["_id"] = res.inserted_id

    return {"post": doc, "warning": None, "blocked": False}


async def edit_post_caption(user_id: str, post_id: str, new_caption: str):
    try:
        oid = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post id")

    p = await posts.find_one({"_id": oid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    blocked, msg = await _enforce_badge_rules_pre_insert(
        user_id=user_id,
        caption=new_caption or "",
        media_type=p.get("media_type", "image"),
        media_sha256=p.get("media_sha256"),
        media_dhash=p.get("media_dhash"),
        media_phash=p.get("media_phash"),
        media_ahash=p.get("media_ahash"),
    )
    if blocked:
        deleted = await _auto_delete_post(
            user_id,
            oid,
            msg or "Post auto-deleted for rule violation.",
        )
        return {"post": deleted, "warning": msg, "deleted": True}

    raw_products = _extract_product_from_caption(new_caption or "")
    product_keys = [_norm_product_strict(x) for x in raw_products if _norm_product_strict(x)]

    await posts.update_one(
        {"_id": oid},
        {
            "$set": {
                "caption": new_caption or "",
                "product_names_raw": raw_products,
                "product_keys": product_keys,
                "updated_at": _now(),
            }
        },
    )

    updated = await posts.find_one({"_id": oid})
    return {"post": updated, "warning": None, "deleted": False}


async def get_feed(limit: int = 50, offset: int = 0):
    cur = posts.find({}).sort("created_at", -1).skip(offset).limit(limit)
    return [p async for p in cur]


async def get_my_posts(user_id: str, limit: int = 50, offset: int = 0):
    cur = posts.find({"user_id": user_id}).sort("created_at", -1).skip(offset).limit(limit)
    return [p async for p in cur]


async def delete_post(user_id: str, post_id: str):
    try:
        oid = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post id")

    p = await posts.find_one({"_id": oid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    if p.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    await posts.delete_one({"_id": oid})
    return p


# -------------------------
# BADGE RULES
# -------------------------
async def first_registered_user_for_username(username: str):
    cur = users.find({"username": username}).sort("created_at", 1).limit(1)
    arr = [u async for u in cur]
    return arr[0] if arr else None


def _payload_products(payload: dict) -> list[str]:
    """
    Backward compatible:
      - new: payload["product_names"] = ["a", "b"]
      - old: payload["product_name"] = "a"
    """
    arr = payload.get("product_names")
    if isinstance(arr, list):
        out = []
        for x in arr:
            x = (x or "").strip()
            if x:
                out.append(x)
        return out

    single = (payload.get("product_name") or "").strip()
    return [single] if single else []


def _payload_gsts(payload: dict) -> list[str]:
    """
    Backward compatible:
      - new: payload["gst_ids"] = ["..", ".."]
      - old: payload["legal_proof_id"] when legal_proof_type == GST
    """
    arr = payload.get("gst_ids")
    if isinstance(arr, list):
        out = []
        for x in arr:
            x = (x or "").strip()
            if x:
                out.append(x)
        return out

    single = (payload.get("legal_proof_id") or "").strip()
    return [single] if single else []


def _has_internal_lookalike_in_list(keys: list[str], threshold: float = 0.90) -> bool:
    """
    If user submits multiple products, disallow if two submitted products
    are themselves look-alike (to prevent tricking the system).
    """
    clean = [k for k in (keys or []) if k]
    for i in range(len(clean)):
        for j in range(i + 1, len(clean)):
            if clean[i] == clean[j]:
                continue
            if _sim(clean[i], clean[j]) >= threshold:
                return True
    return False


async def _user_has_matching_product_post(user_id: str, target_key: str) -> bool:
    hit = await posts.find_one({"user_id": user_id, "product_keys": target_key}, {"_id": 1})
    if hit:
        return True

    cur = posts.find({"user_id": user_id}, {"caption": 1}).limit(300)
    async for p in cur:
        keys = _caption_product_keys(p.get("caption", ""))
        if target_key in keys:
            return True
    return False


async def _earliest_post_for_product(target_key: str):
    first = (
        await posts.find({"product_keys": target_key}).sort("created_at", 1).limit(1).to_list(1)
    )
    if first:
        return first[0]

    cur = posts.find(
        {"caption": {"$regex": r"product\s*name\s*:", "$options": "i"}},
        {"caption": 1, "user_id": 1, "created_at": 1, "username": 1},
    )
    earliest = None
    async for p in cur:
        keys = _caption_product_keys(p.get("caption", ""))
        if target_key in keys:
            t = p.get("created_at")
            if earliest is None or (t and t < earliest.get("created_at")):
                earliest = p
    return earliest


async def _is_lookalike_of_existing_approved_product(
    user_id: str,
    target_key: str,
    threshold: float = 0.88,
) -> bool:
    """
    Block if target product looks too similar to any already APPROVED product
    owned by another user.
    """
    if not target_key:
        return False

    cur = badge_apps.find(
        {"status": "APPROVED", "user_id": {"$ne": user_id}},
        {"product_key": 1, "product_keys": 1},
    )

    async for b in cur:
        keys: list[str] = []
        if isinstance(b.get("product_keys"), list) and b.get("product_keys"):
            keys.extend([k for k in b.get("product_keys") if k])
        if b.get("product_key"):
            keys.append(b.get("product_key"))

        for k in keys:
            k = (k or "").strip().lower()
            if not k or k == target_key:
                continue

            if _sim(k, target_key) >= threshold:
                return True

    return False


async def is_user_username_owner(user_id: str, username: str, payload: dict) -> tuple[bool, str]:
    brand_in = payload.get("brand_display_name", "")
    if _norm(brand_in) != _norm(username):
        return False, "Not eligible: brand name must match registered username."

    post_count = await posts.count_documents({"user_id": user_id})
    if post_count < 1:
        return False, "Not eligible: you must create at least 1 post before applying."

    # ✅ badge approve avvakudadhu if user copied duplicates from other accounts earlier
    if await _user_has_any_duplicate_image(user_id):
        return False, "Not eligible: you copied a duplicate image from another account. Badge rejected."

    products = _payload_products(payload)
    if not products:
        return False, "Not eligible: at least 1 product name is required."

    product_keys: list[str] = []
    for p in products:
        if len((p or "").strip()) < 2:
            return False, "Not eligible: product name is missing/invalid."
        k = _norm_product_strict(p)
        if k:
            product_keys.append(k)

    # Disallow if within-submission products are lookalikes of each other
    if _has_internal_lookalike_in_list(product_keys, threshold=0.90):
        return False, "Not eligible: submitted products contain spell-alike/look-alike names."

    # Look-alike check against existing approved products (other users)
    for k in product_keys:
        if await _is_lookalike_of_existing_approved_product(user_id, k, threshold=0.88):
            return (
                False,
                "Not eligible: product name looks too similar to an existing approved product (spell-alike/look-alike).",
            )

    # Must have matching caption tag for each submitted product
    for k in product_keys:
        ok = await _user_has_matching_product_post(user_id, k)
        if not ok:
            return (
                False,
                "Not eligible: each submitted product must appear in at least one of your post captions as `product name: <exact product>`.",
            )

    # First poster rule + Ad required on the earliest product post
    for k in product_keys:
        earliest_post = await _earliest_post_for_product(k)
        if not earliest_post:
            return False, "Not eligible: no valid product-tagged post found for one of your products in the system."

        if earliest_post.get("user_id") != user_id:
            return False, "Not eligible: one of your submitted product names was already posted earlier by another account."

        if not _has_ad(earliest_post.get("caption", "")):
            return False, "Not eligible: the first product post for each submitted product must include 'Ad' (or Sponsored/Paid partnership)."

        existing_badge = await badge_apps.find_one(
            {"product_keys": k, "status": "APPROVED", "user_id": {"$ne": user_id}},
            {"user_id": 1},
        )
        if not existing_badge:
            existing_badge = await badge_apps.find_one(
                {"product_key": k, "status": "APPROVED", "user_id": {"$ne": user_id}},
                {"user_id": 1},
            )
        if existing_badge:
            return False, "Not eligible: one of your products already has an approved badge by another account."

    proof_type = (payload.get("legal_proof_type", "GST") or "GST").upper().strip()

    if proof_type == "GST":
        gst_ids = _payload_gsts(payload)
        if not gst_ids:
            return False, "Not eligible: at least 1 GSTIN is required."
        for g in gst_ids:
            if not is_valid_gstin(g):
                return False, "Not eligible: one of the GSTIN values is invalid."
    else:
        proof_id = (payload.get("legal_proof_id") or "").strip()
        if len(proof_id) < 6:
            return False, f"Not eligible: {proof_type} proof ID is missing/invalid."

    first = await first_registered_user_for_username(username)
    if not first:
        return False, "No such username exists"

    if str(first["_id"]) != user_id:
        return False, "Not eligible: this username was registered earlier by another account."

    return True, "Approved: first poster + Ad mentioned + first registered owner + valid proof(s)."


async def upsert_badge_application(user_id: str, username: str, payload: dict):
    eligible, reason = await is_user_username_owner(user_id, username, payload)
    now = _now()

    products = _payload_products(payload)
    product_keys = [_norm_product_strict(p) for p in products if _norm_product_strict(p)]
    primary_product = products[0] if products else ""
    primary_key = product_keys[0] if product_keys else ""

    proof_type = (payload.get("legal_proof_type", "GST") or "GST").upper().strip()
    gst_ids = _payload_gsts(payload) if proof_type == "GST" else []

    new_status = "APPROVED" if eligible else "REJECTED"

    existing = await badge_apps.find_one({"user_id": user_id})
    primary_gst = gst_ids[0] if gst_ids else (payload.get("legal_proof_id") or "")

    if existing:
        await badge_apps.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "username": username,
                    "brand_display_name": payload.get("brand_display_name", username),
                    "product_names": products,
                    "product_keys": product_keys,
                    "gst_ids": gst_ids,
                    "product_name": primary_product,
                    "product_key": primary_key,
                    "instagram_handle": payload.get("instagram_handle", ""),
                    "legal_proof_type": payload.get("legal_proof_type", "GST"),
                    "legal_proof_id": primary_gst,
                    "eligible": eligible,
                    "reason": reason,
                    "status": new_status,
                    "violations": existing.get("violations", 0),
                    "last_violation_reason": existing.get("last_violation_reason", ""),
                    "updated_at": now,
                }
            },
        )
        return await badge_apps.find_one({"user_id": user_id})

    doc = {
        "user_id": user_id,
        "username": username,
        "brand_display_name": payload.get("brand_display_name", username),
        "product_names": products,
        "product_keys": product_keys,
        "gst_ids": gst_ids,
        "product_name": primary_product,
        "product_key": primary_key,
        "instagram_handle": payload.get("instagram_handle", ""),
        "legal_proof_type": payload.get("legal_proof_type", "GST"),
        "legal_proof_id": primary_gst,
        "eligible": eligible,
        "reason": reason,
        "status": new_status,
        "admin_note": "",
        "violations": 0,
        "last_violation_reason": "",
        "created_at": now,
        "updated_at": now,
    }
    await badge_apps.insert_one(doc)
    return doc


async def get_badge_status(user_id: str):
    return await badge_apps.find_one({"user_id": user_id})


async def admin_set_status(user_id: str, status: str, admin_note: str):
    app_doc = await badge_apps.find_one({"user_id": user_id})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Application not found")

    await badge_apps.update_one(
        {"user_id": user_id},
        {"$set": {"status": status, "admin_note": admin_note or "", "updated_at": _now()}},
    )
    return await badge_apps.find_one({"user_id": user_id})


async def is_user_verified(user_id: str) -> bool:
    doc = await badge_apps.find_one({"user_id": user_id, "status": "APPROVED"}, {"_id": 1})
    return bool(doc)


async def get_verified_usernames():
    cur = badge_apps.find({"status": "APPROVED"}, {"username": 1})
    arr = await cur.to_list(length=1000)
    return {d["username"] for d in arr if d.get("username")}
    