# backend/app/main.py

from __future__ import annotations

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Query,
    Header,
    UploadFile,
    File,
    Form,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from pathlib import Path
import uuid
import traceback

from pydantic import BaseModel

from .db import ensure_indexes
from . import schemas
from .security import create_token, decode_token

# ✅ Multi-hash import (updated image_utils.py)
from .image_utils import sha256_bytes, dhash_bytes, phash_bytes, ahash_bytes

from .services import (
    register_user,
    login_user,
    get_user_by_id,
    create_post,
    edit_post_caption,
    delete_post,
    get_feed,
    get_my_posts,
    upsert_badge_application,
    get_badge_status,
    admin_set_status,
    is_user_verified,
    get_verified_usernames,
    backfill_post_hashes,  # optional util (local uploads only)
)

app = FastAPI(title="OG Ecosystem Backend (MongoDB)", version="2.0.0")


# -------------------------
# GLOBAL ERROR HANDLER (helps debugging 500 + keeps JSON)
# -------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Let FastAPI's HTTPException pass through (we handle separately below)
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # Print traceback in terminal for you
    traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
    )


# -------------------------
# CORS
# -------------------------
# ✅ Allow your Vite frontend on localhost or 127.0.0.1 (any port)
# If you want strict ports only, remove allow_origin_regex and keep allow_origins list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://og-badge-insta.netlify.app",
    ],
    allow_origin_regex=r"^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# UPLOADS (LOCAL)
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.on_event("startup")
async def startup():
    await ensure_indexes()


@app.get("/")
def root():
    return {"status": "ok", "service": "og-ecosystem-mongo"}


# -------------------------
# AUTH HELPERS
# -------------------------
async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    u = await get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=401, detail="User not found")

    return u


# -------------------------
# SMALL MODELS
# -------------------------
class PostCreateOut(schemas.PostOut):
    warning: str | None = None


class EditCaptionIn(BaseModel):
    caption: str


# -------------------------
# AUTH ROUTES
# -------------------------
@app.post("/api/auth/register", response_model=schemas.AuthOut)
async def register(payload: schemas.RegisterIn):
    u = await register_user(payload.email, payload.password, payload.username)
    token = create_token({"user_id": str(u["_id"]), "email": u["email"], "username": u["username"]})
    return {
        "token": token,
        "user_id": str(u["_id"]),
        "email": u["email"],
        "username": u["username"],
        "created_at": u["created_at"],
    }


@app.post("/api/auth/login", response_model=schemas.AuthOut)
async def login(payload: schemas.LoginIn):
    u = await login_user(payload.email, payload.password)
    token = create_token({"user_id": str(u["_id"]), "email": u["email"], "username": u["username"]})
    return {
        "token": token,
        "user_id": str(u["_id"]),
        "email": u["email"],
        "username": u["username"],
        "created_at": u["created_at"],
    }


@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    verified = await is_user_verified(str(user["_id"]))
    return {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "username": user["username"],
        "created_at": user["created_at"],
        "verified": verified,
    }


# -------------------------
# POSTS
# -------------------------
@app.post("/api/posts", response_model=PostCreateOut)
async def new_post(
    media: UploadFile = File(...),
    caption: str = Form(""),
    user=Depends(get_current_user),
):
    allowed = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    if media.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only image files allowed (jpg, png, webp)")

    ext = (media.filename or "file.jpg").split(".")[-1].lower()
    if ext == "jpeg":
        ext = "jpg"

    filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = UPLOAD_DIR / filename

    data = await media.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    # ✅ hashes (computed from bytes)
    try:
        media_sha = sha256_bytes(data)
        media_dh = dhash_bytes(data)
        media_ph = phash_bytes(data)
        media_ah = ahash_bytes(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Save file first (if rules block -> we will delete this file)
    save_path.write_bytes(data)

    try:
        res = await create_post(
            user_id=str(user["_id"]),
            username=user["username"],
            media_url=f"/uploads/{filename}",
            media_type="image",
            caption=caption,
            media_sha256=media_sha,
            media_dhash=media_dh,
            media_phash=media_ph,
            media_ahash=media_ah,
        )
    except HTTPException:
        try:
            if save_path.exists():
                save_path.unlink()
        except Exception:
            pass
        raise
    except Exception:
        try:
            if save_path.exists():
                save_path.unlink()
        except Exception:
            pass
        raise

    # ✅ blocked => NOT inserted, so delete uploaded file and return error
    if isinstance(res, dict) and res.get("blocked"):
        try:
            if save_path.exists():
                save_path.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=res.get("warning") or "Post removed by rules.")

    warning = None
    p = res
    if isinstance(res, dict) and "post" in res:
        p = res.get("post")
        warning = res.get("warning")

    if not p:
        try:
            if save_path.exists():
                save_path.unlink()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=warning or "Post removed by rules.")

    verified = await is_user_verified(str(user["_id"]))

    return {
        "id": str(p["_id"]),
        "user_id": p["user_id"],
        "username": p["username"],
        "is_verified": verified,
        "media_url": p["media_url"],
        "media_type": p["media_type"],
        "caption": p.get("caption", ""),
        "created_at": p["created_at"],
        "warning": warning,
    }


@app.put("/api/posts/{post_id}", response_model=PostCreateOut)
async def update_post_caption(
    post_id: str,
    payload: EditCaptionIn,
    user=Depends(get_current_user),
):
    res = await edit_post_caption(
        user_id=str(user["_id"]),
        post_id=post_id,
        new_caption=payload.caption,
    )

    warning = None
    p = res
    deleted = False

    if isinstance(res, dict) and "post" in res:
        p = res.get("post")
        warning = res.get("warning")
        deleted = bool(res.get("deleted", False))

    # ✅ If deleted due to rules => remove file + return error
    if deleted and p:
        media_url = p.get("media_url", "")
        if isinstance(media_url, str) and media_url.startswith("/uploads/"):
            fn = media_url.replace("/uploads/", "").strip()
            file_path = UPLOAD_DIR / fn
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=warning or "Post removed by rules.")

    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    verified = await is_user_verified(str(user["_id"]))

    return {
        "id": str(p["_id"]),
        "user_id": p["user_id"],
        "username": p["username"],
        "is_verified": verified,
        "media_url": p["media_url"],
        "media_type": p["media_type"],
        "caption": p.get("caption", ""),
        "created_at": p["created_at"],
        "warning": warning,
    }


@app.delete("/api/posts/{post_id}")
async def remove_post(post_id: str, user=Depends(get_current_user)):
    p = await delete_post(user_id=str(user["_id"]), post_id=post_id)

    # delete local file (only if it exists locally)
    media_url = p.get("media_url", "")
    if isinstance(media_url, str) and media_url.startswith("/uploads/"):
        fn = media_url.replace("/uploads/", "").strip()
        file_path = UPLOAD_DIR / fn
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass

    return {"ok": True, "deleted_id": post_id}


@app.get("/api/me/posts", response_model=list[schemas.PostOut])
async def my_posts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
):
    verified = await is_user_verified(str(user["_id"]))
    arr = await get_my_posts(user_id=str(user["_id"]), limit=limit, offset=offset)

    out = []
    for p in arr:
        out.append(
            {
                "id": str(p["_id"]),
                "user_id": p["user_id"],
                "username": p["username"],
                "is_verified": verified,
                "media_url": p["media_url"],
                "media_type": p["media_type"],
                "caption": p.get("caption", ""),
                "created_at": p["created_at"],
            }
        )
    return out


@app.get("/api/feed", response_model=list[schemas.PostOut])
async def feed(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    verified_usernames = await get_verified_usernames()
    arr = await get_feed(limit=limit, offset=offset)

    out = []
    for p in arr:
        uname = p["username"]
        out.append(
            {
                "id": str(p["_id"]),
                "user_id": p["user_id"],
                "username": uname,
                "is_verified": uname in verified_usernames,
                "media_url": p["media_url"],
                "media_type": p["media_type"],
                "caption": p.get("caption", ""),
                "created_at": p.get("created_at"),
            }
        )
    return out


# -------------------------
# BADGE
# -------------------------
@app.post("/api/badge/apply", response_model=schemas.BadgeOut)
async def apply_badge(payload: schemas.BadgeApplyIn, user=Depends(get_current_user)):
    doc = await upsert_badge_application(
        user_id=str(user["_id"]),
        username=user["username"],
        payload=payload.model_dump(),
    )
    return {
        "user_id": doc["user_id"],
        "username": doc["username"],
        "brand_display_name": doc["brand_display_name"],
        "product_names": doc.get("product_names", []),
        "gst_ids": doc.get("gst_ids", []),
        "product_name": doc.get("product_name", ""),
        "instagram_handle": doc.get("instagram_handle", ""),
        "legal_proof_type": doc.get("legal_proof_type", "GST"),
        "legal_proof_id": doc.get("legal_proof_id", ""),
        "status": doc.get("status", "PENDING"),
        "admin_note": doc.get("admin_note", ""),
        "eligible": bool(doc.get("eligible", False)),
        "reason": doc.get("reason", ""),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


@app.get("/api/badge/status", response_model=schemas.BadgeOut)
async def badge_status(user=Depends(get_current_user)):
    doc = await get_badge_status(user_id=str(user["_id"]))
    if not doc:
        raise HTTPException(status_code=404, detail="No application found")
    return {
        "user_id": doc["user_id"],
        "username": doc["username"],
        "brand_display_name": doc["brand_display_name"],
        "product_names": doc.get("product_names", []),
        "gst_ids": doc.get("gst_ids", []),
        "product_name": doc.get("product_name", ""),
        "instagram_handle": doc.get("instagram_handle", ""),
        "legal_proof_type": doc.get("legal_proof_type", "GST"),
        "legal_proof_id": doc.get("legal_proof_id", ""),
        "status": doc.get("status", "PENDING"),
        "admin_note": doc.get("admin_note", ""),
        "eligible": bool(doc.get("eligible", False)),
        "reason": doc.get("reason", ""),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# -------------------------
# ADMIN (DEMO)
# -------------------------
@app.post("/api/badge/admin/approve", response_model=schemas.BadgeOut)
async def admin_approve(payload: schemas.AdminDecisionIn):
    doc = await admin_set_status(payload.user_id, "APPROVED", payload.admin_note)
    return {
        "user_id": doc["user_id"],
        "username": doc["username"],
        "brand_display_name": doc["brand_display_name"],
        "product_names": doc.get("product_names", []),
        "gst_ids": doc.get("gst_ids", []),
        "product_name": doc.get("product_name", ""),
        "instagram_handle": doc.get("instagram_handle", ""),
        "legal_proof_type": doc.get("legal_proof_type", "GST"),
        "legal_proof_id": doc.get("legal_proof_id", ""),
        "status": doc.get("status", "PENDING"),
        "admin_note": doc.get("admin_note", ""),
        "eligible": bool(doc.get("eligible", False)),
        "reason": doc.get("reason", ""),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


@app.post("/api/badge/admin/reject", response_model=schemas.BadgeOut)
async def admin_reject(payload: schemas.AdminDecisionIn):
    doc = await admin_set_status(payload.user_id, "REJECTED", payload.admin_note)
    return {
        "user_id": doc["user_id"],
        "username": doc["username"],
        "brand_display_name": doc["brand_display_name"],
        "product_names": doc.get("product_names", []),
        "gst_ids": doc.get("gst_ids", []),
        "product_name": doc.get("product_name", ""),
        "instagram_handle": doc.get("instagram_handle", ""),
        "legal_proof_type": doc.get("legal_proof_type", "GST"),
        "legal_proof_id": doc.get("legal_proof_id", ""),
        "status": doc.get("status", "PENDING"),
        "admin_note": doc.get("admin_note", ""),
        "eligible": bool(doc.get("eligible", False)),
        "reason": doc.get("reason", ""),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


# -------------------------
# OPTIONAL: DEV UTIL (LOCAL uploads only)
# -------------------------
@app.post("/api/dev/backfill-hashes")
async def dev_backfill_hashes():
    """
    Run once after adding sha/dhash/phash/ahash fields to posts.
    This fills media_sha256/media_dhash/media_phash/media_ahash for OLD posts.

    Works ONLY if this server can read the same local /uploads folder.
    If you host images elsewhere (S3/Cloudinary), this won't work.
    """
    return await backfill_post_hashes(str(UPLOAD_DIR))