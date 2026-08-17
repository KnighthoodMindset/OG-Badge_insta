from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from . import models


# -------------------------
# POSTS
# -------------------------
def create_post(db: Session, data: dict) -> models.Post:
    post = models.Post(**data)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def get_feed(db: Session, limit: int = 50, offset: int = 0):
    stmt = select(models.Post).order_by(desc(models.Post.created_at)).limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()


def get_user_posts(db: Session, user_id: str, limit: int = 50, offset: int = 0):
    stmt = (
        select(models.Post)
        .where(models.Post.user_id == user_id)
        .order_by(desc(models.Post.created_at))
        .limit(limit)
        .offset(offset)
    )
    return db.execute(stmt).scalars().all()


# -------------------------
# BADGE APPLICATION
# -------------------------
def upsert_badge_application(db: Session, data: dict) -> models.BadgeApplication:
    # one application per user_id
    existing = db.execute(
        select(models.BadgeApplication).where(models.BadgeApplication.user_id == data["user_id"])
    ).scalar_one_or_none()

    if existing:
        # if already approved, keep approved unless admin changes later
        existing.username = data["username"]
        existing.brand_name = data["brand_name"]
        existing.instagram_handle = data.get("instagram_handle", "")
        existing.legal_proof_type = data.get("legal_proof_type", "GST")
        existing.legal_proof_id = data.get("legal_proof_id", "")
        if existing.status != "APPROVED":
            existing.status = "PENDING"
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    app = models.BadgeApplication(**data)
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def get_badge_status(db: Session, user_id: str):
    return db.execute(
        select(models.BadgeApplication).where(models.BadgeApplication.user_id == user_id)
    ).scalar_one_or_none()


def admin_set_status(db: Session, user_id: str, status: str, admin_note: str = ""):
    app = get_badge_status(db, user_id)
    if not app:
        return None
    app.status = status
    app.admin_note = admin_note or ""
    app.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(app)
    return app
