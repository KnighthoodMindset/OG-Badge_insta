from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

# -------------------------
# AUTH
# -------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    username: str = Field(min_length=3, max_length=64)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class AuthOut(BaseModel):
    token: str
    user_id: str
    email: EmailStr
    username: str
    created_at: datetime


# -------------------------
# POSTS
# -------------------------
class PostOut(BaseModel):
    id: str
    user_id: str
    username: str
    is_verified: bool = False
    media_url: str
    media_type: str
    caption: str
    created_at: datetime


# -------------------------
# BADGE APPLY (MULTI PRODUCT + MULTI GST)
# -------------------------
class BadgeApplyIn(BaseModel):
    brand_display_name: str = Field(min_length=2, max_length=120)

    # NEW: multi products
    product_names: List[str] = Field(default_factory=list)

    # OLD (backward compatible)
    product_name: str = ""

    instagram_handle: str = ""

    legal_proof_type: str = "GST"

    # NEW: multi GSTs (only used when legal_proof_type == GST)
    gst_ids: List[str] = Field(default_factory=list)

    # OLD (backward compatible)
    legal_proof_id: str = ""


class BadgeOut(BaseModel):
    user_id: str
    username: str
    brand_display_name: str

    # NEW
    product_names: List[str] = Field(default_factory=list)
    gst_ids: List[str] = Field(default_factory=list)

    # OLD
    product_name: str = ""
    instagram_handle: str
    legal_proof_type: str
    legal_proof_id: str = ""

    # ✅ NEW: violation tracking (badge kept, only posts deleted)
    violations: int = 0
    last_violation_reason: str = ""

    status: str
    admin_note: str
    eligible: bool
    reason: str
    created_at: datetime
    updated_at: datetime


class AdminDecisionIn(BaseModel):
    user_id: str
    admin_note: str = ""