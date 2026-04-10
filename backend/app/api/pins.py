"""
Hunt pin endpoints — authenticated users can log metal detecting hunts.

Each hunt is a personal pin on the map with a date, notes, time spent,
finds count, and privacy setting (public / friends / private).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.models.database import PinImage, User, UserPin, get_db
from app.models.schemas import PinImageResponse, UserPinCreate, UserPinListResponse, UserPinResponse, UserPinUpdate

router = APIRouter(prefix="/pins", tags=["pins"])

HUNT_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def _build_geom(lon: float, lat: float):
    """Return a PostGIS POINT expression for the given coordinates."""
    return ST_SetSRID(ST_MakePoint(lon, lat), 4326)


def _parse_hunt_date(hunt_date_str: str) -> datetime:
    """Parse an ISO 8601 date/datetime string into a datetime object."""
    for fmt in HUNT_DATE_FORMATS:
        try:
            return datetime.strptime(hunt_date_str, fmt)
        except ValueError:
            continue
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Invalid hunt_date format: {hunt_date_str!r}. Use ISO 8601 (e.g. 2024-06-15).",
    )


async def _attach_pin_images(pins: List[UserPin], db) -> List[dict]:
    """Load PinImage rows for each pin and return pin dicts with images attached."""
    if not pins:
        return []
    pin_ids = [p.id for p in pins]
    images_result = await db.execute(
        select(PinImage)
        .where(PinImage.pin_id.in_(pin_ids))
        .order_by(PinImage.position)
    )
    images_map: dict = defaultdict(list)
    for img in images_result.scalars().all():
        images_map[img.pin_id].append(
            PinImageResponse(id=img.id, url=img.url, position=img.position)
        )
    result = []
    for pin in pins:
        pin_dict = UserPinResponse.model_validate(pin).model_dump()
        pin_dict["images"] = images_map.get(pin.id, [])
        result.append(pin_dict)
    return result


# ---------------------------------------------------------------------------
# POST /pins  — create a hunt
# ---------------------------------------------------------------------------

@router.post("", response_model=UserPinResponse, status_code=status.HTTP_201_CREATED)
async def create_pin(
    body: UserPinCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    hunt_date = _parse_hunt_date(body.hunt_date)
    pin = UserPin(
        user_id=current_user.id,
        name=body.name,
        latitude=body.latitude,
        longitude=body.longitude,
        geom=_build_geom(body.longitude, body.latitude),
        hunt_date=hunt_date,
        time_spent=body.time_spent,
        notes=body.notes,
        finds_count=body.finds_count,
        privacy=body.privacy or "public",
    )
    db.add(pin)
    await db.flush()
    await db.refresh(pin)
    results = await _attach_pin_images([pin], db)
    return results[0]


# ---------------------------------------------------------------------------
# GET /pins/me  — list the current user's pins
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserPinListResponse)
async def list_my_pins(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPinListResponse:
    total_result = await db.execute(
        select(func.count()).select_from(UserPin).where(UserPin.user_id == current_user.id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(UserPin)
        .where(UserPin.user_id == current_user.id)
        .order_by(UserPin.hunt_date.desc())
        .limit(limit)
        .offset(offset)
    )
    pins = list(result.scalars().all())
    pin_dicts = await _attach_pin_images(pins, db)
    return UserPinListResponse(pins=pin_dicts, total=total)


# ---------------------------------------------------------------------------
# GET /pins/user/{username}  — list public pins for a given username
# ---------------------------------------------------------------------------

@router.get("/user/{username}", response_model=UserPinListResponse)
async def list_user_pins(
    username: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> UserPinListResponse:
    from app.models.database import User as UserModel

    user_result = await db.execute(
        select(UserModel).where(UserModel.username == username)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    total_result = await db.execute(
        select(func.count()).select_from(UserPin).where(
            UserPin.user_id == user.id,
            UserPin.privacy == "public",
        )
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(UserPin)
        .where(UserPin.user_id == user.id, UserPin.privacy == "public")
        .order_by(UserPin.hunt_date.desc())
        .limit(limit)
        .offset(offset)
    )
    pins = list(result.scalars().all())
    pin_dicts = await _attach_pin_images(pins, db)
    return UserPinListResponse(pins=pin_dicts, total=total)


# ---------------------------------------------------------------------------
# GET /pins/{pin_id}  — get a single pin
# ---------------------------------------------------------------------------

@router.get("/{pin_id}", response_model=UserPinResponse)
async def get_pin(
    pin_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(UserPin).where(UserPin.id == pin_id))
    pin = result.scalar_one_or_none()
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")

    if pin.user_id != current_user.id and pin.privacy != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")

    results = await _attach_pin_images([pin], db)
    return results[0]


# ---------------------------------------------------------------------------
# PUT /pins/{pin_id}  — update a pin (owner only)
# ---------------------------------------------------------------------------

@router.put("/{pin_id}", response_model=UserPinResponse)
async def update_pin(
    pin_id: uuid.UUID,
    body: UserPinUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(UserPin).where(UserPin.id == pin_id, UserPin.user_id == current_user.id)
    )
    pin = result.scalar_one_or_none()
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")

    if body.name is not None:
        pin.name = body.name
    if body.hunt_date is not None:
        pin.hunt_date = _parse_hunt_date(body.hunt_date)
    if body.time_spent is not None:
        pin.time_spent = body.time_spent
    if body.notes is not None:
        pin.notes = body.notes
    if body.finds_count is not None:
        pin.finds_count = body.finds_count
    if body.privacy is not None:
        pin.privacy = body.privacy

    lat_changed = body.latitude is not None
    lon_changed = body.longitude is not None
    if lat_changed:
        pin.latitude = body.latitude
    if lon_changed:
        pin.longitude = body.longitude
    if lat_changed or lon_changed:
        pin.geom = _build_geom(pin.longitude, pin.latitude)

    await db.flush()
    await db.refresh(pin)
    results = await _attach_pin_images([pin], db)
    return results[0]


# ---------------------------------------------------------------------------
# DELETE /pins/{pin_id}  — delete a pin (owner only)
# ---------------------------------------------------------------------------

@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_pin(
    pin_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(UserPin).where(UserPin.id == pin_id, UserPin.user_id == current_user.id)
    )
    pin = result.scalar_one_or_none()
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")

    # Delete associated images from Drive and the database
    images_result = await db.execute(select(PinImage).where(PinImage.pin_id == pin_id))
    images = list(images_result.scalars().all())
    if images:
        try:
            from app.auth.google import _DRIVE_FILES_URL, get_valid_access_token
            import httpx as _httpx
            access_token = await get_valid_access_token(current_user, db)
            for img in images:
                try:
                    async with _httpx.AsyncClient() as client:
                        await client.delete(
                            f"{_DRIVE_FILES_URL}/{img.drive_file_id}",
                            headers={"Authorization": f"Bearer {access_token}"},
                            timeout=30.0,
                        )
                except Exception as exc:
                    import logging as _logging
                    _logging.getLogger(__name__).warning("Failed to delete Drive file %s: %s", img.drive_file_id, exc)
        except Exception as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning("Could not clean up Drive files for pin %s: %s", pin_id, exc)
        for img in images:
            await db.delete(img)

    await db.delete(pin)
