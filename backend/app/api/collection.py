"""
Collection API endpoints.

GET    /collection/{username}  — List a user's curated collection photos.
POST   /collection             — Upload a photo to the current user's collection.
PUT    /collection/{photo_id}  — Edit a collection photo's caption.
DELETE /collection/{photo_id}  — Delete a collection photo.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

import httpx

from app.auth.deps import get_current_user, optional_user
from app.auth.google import (
    _DRIVE_FILES_URL,
    ensure_prescia_folder,
    get_valid_access_token,
    upload_file_to_drive,
)
from app.api.google_auth import _ALLOWED_IMAGE_TYPES, _EXT_MAP, _MAX_IMAGE_SIZE
from app.models.database import CollectionPhoto, User, get_db
from app.models.schemas import (
    CollectionPhotoListResponse,
    CollectionPhotoResponse,
    CollectionPhotoUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collection", tags=["collection"])


# ---------------------------------------------------------------------------
# GET /collection/{username} — list a user's collection photos
# ---------------------------------------------------------------------------

@router.get("/{username}", response_model=CollectionPhotoListResponse)
async def list_collection(
    username: str,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionPhotoListResponse:
    """Return paginated collection photos for a user, newest first."""
    from app.models.database import User as UserModel

    result = await db.execute(
        select(UserModel).where(UserModel.username == username)
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Respect privacy: private profiles are only visible to the owner
    if target_user.privacy == "private":
        is_owner = current_user is not None and current_user.id == target_user.id
        if not is_owner:
            return CollectionPhotoListResponse(photos=[], total=0)

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(CollectionPhoto).where(
            CollectionPhoto.user_id == target_user.id
        )
    )
    total = count_result.scalar_one()

    # Paginated photos
    photos_result = await db.execute(
        select(CollectionPhoto)
        .where(CollectionPhoto.user_id == target_user.id)
        .order_by(CollectionPhoto.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    photos = list(photos_result.scalars().all())

    return CollectionPhotoListResponse(
        photos=[
            CollectionPhotoResponse(
                id=photo.id,
                user_id=photo.user_id,
                url=photo.url,
                caption=photo.caption,
                created_at=photo.created_at,
            )
            for photo in photos
        ],
        total=total,
    )


# ---------------------------------------------------------------------------
# POST /collection — upload a photo to own collection
# ---------------------------------------------------------------------------

@router.post("", response_model=CollectionPhotoResponse, status_code=status.HTTP_201_CREATED)
async def upload_collection_photo(
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionPhotoResponse:
    """Upload a single photo to the current user's collection."""
    # 1. Validate file type and size
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")

    contents = await file.read()
    if len(contents) > _MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image must be smaller than 2MB")

    # 2. Get access token and folder
    access_token = await get_valid_access_token(current_user, db)
    folder_id = await ensure_prescia_folder(access_token, user=current_user, db=db)

    # 3. Upload to Drive
    ext = _EXT_MAP.get(content_type, "jpg")
    file_name = f"collection_{current_user.id}_{uuid.uuid4().hex}.{ext}"
    file_id = await upload_file_to_drive(access_token, folder_id, file_name, contents, content_type)

    # 4. Create DB row
    photo = CollectionPhoto(
        user_id=current_user.id,
        drive_file_id=file_id,
        url=f"https://drive.google.com/thumbnail?id={file_id}&sz=w800-h800",
        caption=caption,
    )
    db.add(photo)
    await db.flush()
    await db.refresh(photo)

    return CollectionPhotoResponse(
        id=photo.id,
        user_id=photo.user_id,
        url=photo.url,
        caption=photo.caption,
        created_at=photo.created_at,
    )


# ---------------------------------------------------------------------------
# PUT /collection/{photo_id} — edit a collection photo's caption
# ---------------------------------------------------------------------------

@router.put("/{photo_id}", response_model=CollectionPhotoResponse)
async def update_collection_photo(
    photo_id: uuid.UUID,
    body: CollectionPhotoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollectionPhotoResponse:
    """Update the caption of a collection photo owned by the current user."""
    result = await db.execute(
        select(CollectionPhoto).where(CollectionPhoto.id == photo_id)
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    if photo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this photo")

    photo.caption = body.caption
    await db.flush()
    await db.refresh(photo)

    return CollectionPhotoResponse(
        id=photo.id,
        user_id=photo.user_id,
        url=photo.url,
        caption=photo.caption,
        created_at=photo.created_at,
    )


# ---------------------------------------------------------------------------
# DELETE /collection/{photo_id} — delete a collection photo
# ---------------------------------------------------------------------------

@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection_photo(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a collection photo and its corresponding Drive file."""
    result = await db.execute(
        select(CollectionPhoto).where(CollectionPhoto.id == photo_id)
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    if photo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this photo")

    # Try to delete Drive file (non-blocking)
    try:
        access_token = await get_valid_access_token(current_user, db)
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{_DRIVE_FILES_URL}/{photo.drive_file_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )
    except Exception as exc:
        logger.warning("Failed to delete Drive file %s: %s", photo.drive_file_id, exc)

    await db.delete(photo)
