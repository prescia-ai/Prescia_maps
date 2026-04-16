"""
Google OAuth2 API endpoints.

GET    /google/auth-url       — Returns the Google consent URL (requires JWT auth).
GET    /google/callback       — OAuth2 callback (browser redirect from Google, no JWT).
GET    /google/status         — Check connection status.
POST   /google/disconnect     — Disconnect Google Drive.
POST   /google/upload-avatar  — Upload a profile picture to Google Drive.
DELETE /google/avatar         — Remove the profile picture.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.auth.deps import get_current_user
from app.auth.google import (
    _DRIVE_FILES_URL,
    build_google_auth_url,
    encrypt_token,
    ensure_aurik_folder,
    exchange_code_for_tokens,
    fetch_google_user_email,
    get_valid_access_token,
    upload_file_to_drive,
)
from app.config import settings
from app.models.database import Post, PinImage, PostImage, User, UserPin, CollectionPhoto, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google", tags=["google"])


@router.get("/auth-url")
async def get_google_auth_url(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Return the Google OAuth2 consent-screen URL for the current user.

    The user's ID is encoded in the ``state`` parameter so the callback
    can identify which user is connecting their Google account.
    """
    state = str(current_user.id)
    url = build_google_auth_url(state)
    return {"url": url}


@router.get("/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the Google OAuth2 callback after the user grants consent.

    This endpoint is not protected by JWT — it is a browser redirect from
    Google's consent screen.  The ``state`` parameter carries the user's ID
    so we can look them up in the database.

    On success:  redirects to ``{FRONTEND_URL}/profile/settings?google=connected``
    On failure:  redirects to ``{FRONTEND_URL}/profile/settings?google=error``
    """
    error_redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/profile/settings?google=error",
        status_code=302,
    )
    success_redirect = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/profile/settings?google=connected",
        status_code=302,
    )

    # ------------------------------------------------------------------
    # 1. Look up the user identified by the state parameter.
    # ------------------------------------------------------------------
    try:
        user_id = uuid.UUID(state)
    except (ValueError, AttributeError):
        return error_redirect

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return error_redirect

    # ------------------------------------------------------------------
    # 2. Exchange the authorization code for tokens.
    # ------------------------------------------------------------------
    try:
        token_data = await exchange_code_for_tokens(code)
    except HTTPException:
        return error_redirect

    access_token: str | None = token_data.get("access_token")
    refresh_token: str | None = token_data.get("refresh_token")

    if not access_token:
        return error_redirect

    # ------------------------------------------------------------------
    # 3. Fetch the connected Google account email.
    # ------------------------------------------------------------------
    try:
        google_email = await fetch_google_user_email(access_token)
    except HTTPException:
        return error_redirect

    # ------------------------------------------------------------------
    # 4. Persist the tokens and metadata on the User row.
    #    If no refresh_token was returned (happens on re-auth without
    #    prompt=consent), keep the existing one.
    # ------------------------------------------------------------------
    try:
        if refresh_token:
            user.google_refresh_token = encrypt_token(refresh_token)
        user.google_connected_at = datetime.now(timezone.utc)
        user.google_email = google_email
        await db.commit()
    except Exception:
        await db.rollback()
        return error_redirect

    return success_redirect


@router.get("/status")
async def google_drive_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the Google Drive connection status for the current user.

    If connected, also verifies the token is still valid and ensures the
    Aurik folder exists.
    """
    if not current_user.google_refresh_token:
        return {
            "connected": False,
            "google_email": None,
            "connected_at": None,
            "has_folder": False,
        }

    # Try to get a valid access token and verify the folder exists.
    has_folder = False
    try:
        access_token = await get_valid_access_token(current_user, db)
        await ensure_aurik_folder(access_token, user=current_user, db=db)
        has_folder = True
    except HTTPException:
        # Token revoked or Drive unavailable — has_folder stays False.
        # get_valid_access_token clears Google fields on revocation.
        pass

    # After get_valid_access_token, the user may have been disconnected
    # (fields cleared) if the refresh token was revoked.
    if not current_user.google_refresh_token:
        return {
            "connected": False,
            "google_email": None,
            "connected_at": None,
            "has_folder": False,
        }

    connected_at = current_user.google_connected_at
    return {
        "connected": True,
        "google_email": current_user.google_email,
        "connected_at": connected_at.isoformat() if connected_at else None,
        "has_folder": has_folder,
    }


@router.post("/disconnect")
async def google_drive_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Disconnect Google Drive for the current user.

    Clears all Google-related fields on the User row.
    """
    current_user.google_refresh_token = None
    current_user.google_connected_at = None
    current_user.google_email = None
    current_user.google_folder_id = None
    await db.flush()
    return {"status": "disconnected"}


# ---------------------------------------------------------------------------
# POST /google/upload-avatar — upload a profile picture to Google Drive
# ---------------------------------------------------------------------------

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 MB
_DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
_DRIVE_PERMISSIONS_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/permissions"
_DRIVE_FILES_METADATA_URL = "https://www.googleapis.com/drive/v3/files/{file_id}"


def _extract_drive_file_id(image_url: str) -> str | None:
    """Extract the Google Drive file ID from a Drive image URL.

    Handles both formats:
    - https://drive.google.com/thumbnail?id={file_id}&sz=w400-h400
    - https://lh3.googleusercontent.com/d/{file_id}=s400
    """
    if "drive.google.com/thumbnail" in image_url:
        for part in image_url.split("&"):
            if part.startswith("id=") or "?id=" in part:
                return part.split("id=")[-1]
    if "lh3.googleusercontent.com/d/" in image_url:
        # Format: https://lh3.googleusercontent.com/d/{file_id}=s400
        path = image_url.split("/d/")[-1]
        # Strip size suffix (everything from "=" onward)
        return path.split("=")[0]
    return None


def _build_lh3_url(file_id: str, size_suffix: str = "=s800") -> str:
    """Construct a lh3.googleusercontent.com CDN URL for a Drive file."""
    return f"https://lh3.googleusercontent.com/d/{file_id}{size_suffix}"


async def _fetch_lh3_url(access_token: str, file_id: str, size_suffix: str = "=s800") -> str:
    """Fetch the stable lh3 CDN URL for a Drive file via the thumbnailLink field.

    Makes a lightweight metadata request to the Drive API to obtain the
    ``thumbnailLink`` (which is an ``lh3.googleusercontent.com`` URL), strips
    its size suffix, and appends the requested ``size_suffix``.

    Falls back to constructing the URL directly from the file ID if the API
    call fails or the field is missing — the constructed URL is equivalent and
    works as long as the file is publicly readable.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _DRIVE_FILES_METADATA_URL.format(file_id=file_id),
                params={"fields": "thumbnailLink"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
        if resp.status_code == 200:
            thumbnail_link = resp.json().get("thumbnailLink", "")
            if thumbnail_link and "lh3.googleusercontent.com" in thumbnail_link:
                # Strip any existing size suffix (e.g. "=s220") and apply desired one
                base = thumbnail_link.split("=")[0]
                return f"{base}{size_suffix}"
    except Exception as exc:
        logger.warning("Failed to fetch thumbnailLink for file %s: %s", file_id, exc)

    # Fallback: construct the lh3 URL directly from the file ID
    return _build_lh3_url(file_id, size_suffix)


def _migrate_drive_url_to_lh3(url: str, size_suffix: str = "=s400") -> str | None:
    """Convert an old drive.google.com/thumbnail URL to lh3 format.

    Returns the converted URL if conversion was possible, or ``None`` if the
    URL is already in the new format or doesn't match the old pattern.
    """
    if not url or "drive.google.com/thumbnail" not in url:
        return None
    file_id = _extract_drive_file_id(url)
    if not file_id:
        return None
    return _build_lh3_url(file_id, size_suffix)


@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a profile picture to Google Drive and save the public URL."""
    # 1. Validate file type
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")

    # Read file contents and validate size
    contents = await file.read()
    if len(contents) > _MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image must be smaller than 2MB")

    # Determine file extension from content type
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map.get(content_type, "jpg")
    file_name = f"avatar_{current_user.id}.{ext}"

    # 2. Get a valid access token
    access_token = await get_valid_access_token(current_user, db)

    # 3. Ensure the Aurik folder exists
    folder_id = await ensure_aurik_folder(access_token, user=current_user, db=db)

    # 4. Delete old avatar if one exists
    if current_user.avatar_url:
        old_file_id = _extract_drive_file_id(current_user.avatar_url)
        if old_file_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.delete(
                        f"{_DRIVE_FILES_URL}/{old_file_id}",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
            except Exception as exc:
                logger.warning("Failed to delete old avatar file %s: %s", old_file_id, exc)

    # 5. Upload the file to Google Drive using multipart upload
    metadata = json.dumps({"name": file_name, "parents": [folder_id]}).encode()
    boundary = "aurik_avatar_boundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode() + metadata + (
        f"\r\n--{boundary}\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + contents + f"\r\n--{boundary}--".encode()

    async with httpx.AsyncClient() as client:
        upload_resp = await client.post(
            f"{_DRIVE_UPLOAD_URL}?uploadType=multipart&fields=id",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            content=body,
            timeout=60.0,
        )

    if upload_resp.status_code not in (200, 201):
        logger.error("Drive upload failed: %s %s", upload_resp.status_code, upload_resp.text)
        raise HTTPException(status_code=502, detail="Failed to upload image to Google Drive")

    file_id = upload_resp.json().get("id")
    if not file_id:
        raise HTTPException(status_code=502, detail="Google Drive did not return a file ID")

    # 6. Make the file publicly readable
    async with httpx.AsyncClient() as client:
        perm_resp = await client.post(
            _DRIVE_PERMISSIONS_URL.format(file_id=file_id),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"role": "reader", "type": "anyone"},
            timeout=30.0,
        )
    if perm_resp.status_code not in (200, 201):
        logger.warning("Failed to set public permission on file %s: %s", file_id, perm_resp.text)

    # 7. Fetch the stable lh3 CDN URL for the uploaded file
    avatar_url = await _fetch_lh3_url(access_token, file_id, size_suffix="=s400")

    # 8. Save the URL on the User row
    current_user.avatar_url = avatar_url
    await db.flush()

    # 9. Return the response
    return {"avatar_url": avatar_url, "file_id": file_id}


# ---------------------------------------------------------------------------
# DELETE /google/avatar — remove the profile picture
# ---------------------------------------------------------------------------

@router.delete("/avatar")
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove the user's profile picture from Google Drive and clear the stored URL."""
    if not current_user.avatar_url:
        return {"status": "no_avatar"}

    # Try to delete the file from Drive
    file_id = _extract_drive_file_id(current_user.avatar_url)
    if file_id:
        try:
            access_token = await get_valid_access_token(current_user, db)
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{_DRIVE_FILES_URL}/{file_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
        except Exception as exc:
            logger.warning("Failed to delete avatar file %s from Drive: %s", file_id, exc)

    # Clear the URL on the User row
    current_user.avatar_url = None
    await db.flush()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# POST /google/upload-post-images — attach images to a feed post
# ---------------------------------------------------------------------------

_EXT_MAP = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@router.post("/upload-post-images")
async def upload_post_images(
    post_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload 1–4 images to attach to a feed post."""
    if not (1 <= len(files) <= 4):
        raise HTTPException(status_code=400, detail="You can attach 1 to 4 images")

    # Validate post_id format
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post_id format")

    # Validate and read all files first
    file_data: List[Tuple[bytes, str]] = []
    for f in files:
        ct = f.content_type or ""
        if ct not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")
        contents = await f.read()
        if len(contents) > _MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail="Image must be smaller than 2MB")
        file_data.append((contents, ct))

    # Verify post ownership
    post_result = await db.execute(select(Post).where(Post.id == post_uuid))
    post = post_result.scalar_one_or_none()
    if post is None or post.author_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check no existing images
    count_result = await db.execute(
        select(func.count()).select_from(PostImage).where(PostImage.post_id == post_uuid)
    )
    if count_result.scalar_one() > 0:
        raise HTTPException(status_code=400, detail="Post already has images. Delete existing images first.")

    access_token = await get_valid_access_token(current_user, db)
    folder_id = await ensure_aurik_folder(access_token, user=current_user, db=db)

    created_images: List[PostImage] = []
    for i, (contents, ct) in enumerate(file_data):
        ext = _EXT_MAP.get(ct, "jpg")
        file_name = f"post_{post_id}_{i}.{ext}"
        file_id = await upload_file_to_drive(access_token, folder_id, file_name, contents, ct)
        img_url = await _fetch_lh3_url(access_token, file_id, size_suffix="=s800")
        img = PostImage(
            post_id=post_uuid,
            drive_file_id=file_id,
            url=img_url,
            position=i,
        )
        db.add(img)
        created_images.append(img)

    await db.flush()
    for img in created_images:
        await db.refresh(img)

    return {
        "images": [
            {"id": str(img.id), "url": img.url, "position": img.position}
            for img in created_images
        ]
    }


# ---------------------------------------------------------------------------
# POST /google/upload-pin-images — attach images to a hunt pin
# ---------------------------------------------------------------------------

@router.post("/upload-pin-images")
async def upload_pin_images(
    pin_id: str = Form(...),
    files: List[UploadFile] = File(...),
    add_to_collection: str = Form("false"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload 1–4 images to attach to a hunt pin."""
    if not (1 <= len(files) <= 4):
        raise HTTPException(status_code=400, detail="You can attach 1 to 4 images")

    # Validate pin_id format
    try:
        pin_uuid = uuid.UUID(pin_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pin_id format")

    # Validate and read all files first
    file_data: List[Tuple[bytes, str]] = []
    for f in files:
        ct = f.content_type or ""
        if ct not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")
        contents = await f.read()
        if len(contents) > _MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail="Image must be smaller than 2MB")
        file_data.append((contents, ct))

    # Verify pin ownership
    pin_result = await db.execute(select(UserPin).where(UserPin.id == pin_uuid))
    pin = pin_result.scalar_one_or_none()
    if pin is None or pin.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pin not found")

    # Check no existing images
    count_result = await db.execute(
        select(func.count()).select_from(PinImage).where(PinImage.pin_id == pin_uuid)
    )
    if count_result.scalar_one() > 0:
        raise HTTPException(status_code=400, detail="Pin already has images. Delete existing images first.")

    access_token = await get_valid_access_token(current_user, db)
    folder_id = await ensure_aurik_folder(access_token, user=current_user, db=db)

    created_images: List[PinImage] = []
    for i, (contents, ct) in enumerate(file_data):
        ext = _EXT_MAP.get(ct, "jpg")
        file_name = f"pin_{pin_id}_{i}.{ext}"
        file_id = await upload_file_to_drive(access_token, folder_id, file_name, contents, ct)
        img_url = await _fetch_lh3_url(access_token, file_id, size_suffix="=s800")
        img = PinImage(
            pin_id=pin_uuid,
            drive_file_id=file_id,
            url=img_url,
            position=i,
        )
        db.add(img)
        created_images.append(img)

    await db.flush()
    for img in created_images:
        await db.refresh(img)

    # Optionally copy photos to collection
    if add_to_collection.lower() in ("true", "1", "yes"):
        for img in created_images:
            collection_photo = CollectionPhoto(
                user_id=current_user.id,
                drive_file_id=img.drive_file_id,
                url=img.url,
                caption=None,
            )
            db.add(collection_photo)
        await db.flush()

    return {
        "images": [
            {"id": str(img.id), "url": img.url, "position": img.position}
            for img in created_images
        ]
    }


# ---------------------------------------------------------------------------
# DELETE /google/post-images/{post_id} — delete all images for a post
# ---------------------------------------------------------------------------

@router.delete("/post-images/{post_id}")
async def delete_post_images(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete all images attached to a post (and remove Drive files)."""
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post_id format")

    post_result = await db.execute(select(Post).where(Post.id == post_uuid))
    post = post_result.scalar_one_or_none()
    if post is None or post.author_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found")

    images_result = await db.execute(
        select(PostImage).where(PostImage.post_id == post_uuid)
    )
    images = list(images_result.scalars().all())

    if images:
        try:
            access_token = await get_valid_access_token(current_user, db)
            for img in images:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.delete(
                            f"{_DRIVE_FILES_URL}/{img.drive_file_id}",
                            headers={"Authorization": f"Bearer {access_token}"},
                            timeout=30.0,
                        )
                except Exception as exc:
                    logger.warning("Failed to delete Drive file %s: %s", img.drive_file_id, exc)
        except HTTPException as exc:
            logger.warning("Could not get access token for Drive cleanup: %s", exc.detail)

    for img in images:
        await db.delete(img)

    return {"status": "deleted", "count": len(images)}


# ---------------------------------------------------------------------------
# DELETE /google/pin-images/{pin_id} — delete all images for a pin
# ---------------------------------------------------------------------------

@router.delete("/pin-images/{pin_id}")
async def delete_pin_images(
    pin_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete all images attached to a hunt pin (and remove Drive files)."""
    try:
        pin_uuid = uuid.UUID(pin_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pin_id format")

    pin_result = await db.execute(select(UserPin).where(UserPin.id == pin_uuid))
    pin = pin_result.scalar_one_or_none()
    if pin is None or pin.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pin not found")

    images_result = await db.execute(
        select(PinImage).where(PinImage.pin_id == pin_uuid)
    )
    images = list(images_result.scalars().all())

    if images:
        try:
            access_token = await get_valid_access_token(current_user, db)
            for img in images:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.delete(
                            f"{_DRIVE_FILES_URL}/{img.drive_file_id}",
                            headers={"Authorization": f"Bearer {access_token}"},
                            timeout=30.0,
                        )
                except Exception as exc:
                    logger.warning("Failed to delete Drive file %s: %s", img.drive_file_id, exc)
        except HTTPException as exc:
            logger.warning("Could not get access token for Drive cleanup: %s", exc.detail)

    for img in images:
        await db.delete(img)

    return {"status": "deleted", "count": len(images)}
