from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)  # demo user id
    username: Mapped[str] = mapped_column(String(64), index=True)

    caption: Mapped[str] = mapped_column(Text, default="")
    media_url: Mapped[str] = mapped_column(Text)  # frontend will store uploaded URL later
    media_type: Mapped[str] = mapped_column(String(16), default="image")  # image | video

    brand_name: Mapped[str] = mapped_column(String(120), default="")
    product_name: Mapped[str] = mapped_column(String(120), default="")
    price: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BadgeApplication(Base):
    __tablename__ = "badge_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), index=True)

    brand_name: Mapped[str] = mapped_column(String(120))
    instagram_handle: Mapped[str] = mapped_column(String(120), default="")

    legal_proof_type: Mapped[str] = mapped_column(String(32), default="GST")
    legal_proof_id: Mapped[str] = mapped_column(String(120), default="")

    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING | APPROVED | REJECTED
    admin_note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
