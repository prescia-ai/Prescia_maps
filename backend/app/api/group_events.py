"""
Group Events endpoints — moderators and owners can create/edit/delete events.
Members can RSVP to events. Event pins are visible only to group members.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, optional_user
from app.models.database import Group, GroupEvent, GroupEventRsvp, GroupMember, User, get_db
from app.models.schemas import (
    EventPinResponse,
    GroupEventCreate,
    GroupEventListResponse,
    GroupEventResponse,
    GroupEventUpdate,
)

router = APIRouter(prefix="/groups", tags=["group-events"])
events_router = APIRouter(prefix="/events", tags=["group-events"])

EVENT_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_event_date(date_str: str) -> datetime:
    """Parse an ISO 8601 date/datetime string into a datetime object."""
    for fmt in EVENT_DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Invalid date format: {date_str!r}. Use ISO 8601 (e.g. 2024-06-15T14:00:00Z).",
    )


async def _is_mod_or_owner(group_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> bool:
    """Return True if the user is an active moderator or owner of the group."""
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.status == "active",
            GroupMember.role.in_(["owner", "moderator"]),
        )
    )
    return result.scalar_one_or_none() is not None


async def _is_active_member(group_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> bool:
    """Return True if the user is an active member (any role) of the group."""
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.status == "active",
        )
    )
    return result.scalar_one_or_none() is not None


async def _enrich_events(
    events: List[GroupEvent],
    db: AsyncSession,
    current_user_id: Optional[uuid.UUID] = None,
) -> List[dict]:
    """
    Enrich a list of GroupEvent ORM rows with group_name, group_slug,
    created_by_username, rsvp_count, and user_has_rsvpd.
    """
    if not events:
        return []

    event_ids = [e.id for e in events]
    group_ids = list({e.group_id for e in events})
    creator_ids = list({e.created_by for e in events})

    # Fetch groups
    groups_result = await db.execute(select(Group).where(Group.id.in_(group_ids)))
    groups_map = {g.id: g for g in groups_result.scalars().all()}

    # Fetch creators
    creators_result = await db.execute(select(User).where(User.id.in_(creator_ids)))
    creators_map = {u.id: u for u in creators_result.scalars().all()}

    # Fetch RSVP counts
    rsvp_counts_result = await db.execute(
        select(GroupEventRsvp.event_id, func.count().label("cnt"))
        .where(GroupEventRsvp.event_id.in_(event_ids))
        .group_by(GroupEventRsvp.event_id)
    )
    rsvp_counts_map = {row.event_id: row.cnt for row in rsvp_counts_result}

    # Fetch user RSVPs
    user_rsvp_set: set = set()
    if current_user_id is not None:
        user_rsvps_result = await db.execute(
            select(GroupEventRsvp.event_id).where(
                GroupEventRsvp.event_id.in_(event_ids),
                GroupEventRsvp.user_id == current_user_id,
            )
        )
        user_rsvp_set = {row.event_id for row in user_rsvps_result}

    result = []
    for event in events:
        group = groups_map.get(event.group_id)
        creator = creators_map.get(event.created_by)
        enriched = GroupEventResponse.model_validate(event).model_dump()
        enriched["group_name"] = group.name if group else None
        enriched["group_slug"] = group.slug if group else None
        enriched["created_by_username"] = creator.username if creator else None
        enriched["rsvp_count"] = rsvp_counts_map.get(event.id, 0)
        enriched["user_has_rsvpd"] = event.id in user_rsvp_set
        result.append(enriched)
    return result


def _upcoming_filter(query):
    """Apply the 'upcoming' filter: event_date >= now OR event_end_date >= now."""
    now = datetime.utcnow()
    return query.where(
        (GroupEvent.event_date >= now)
        | (
            (GroupEvent.event_end_date.isnot(None))
            & (GroupEvent.event_end_date >= now)
        )
    )


def _past_filter(query):
    """Apply the 'past' filter: opposite of upcoming."""
    now = datetime.utcnow()
    return query.where(
        (GroupEvent.event_date < now)
        & (
            (GroupEvent.event_end_date.is_(None))
            | (GroupEvent.event_end_date < now)
        )
    )


# ---------------------------------------------------------------------------
# POST /groups/{slug}/events — Create event
# ---------------------------------------------------------------------------

@router.post(
    "/{slug}/events",
    response_model=GroupEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group_event(
    slug: str,
    body: GroupEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_result = await db.execute(select(Group).where(Group.slug == slug))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    if not await _is_mod_or_owner(group.id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Only moderators and owners can create events.")

    event_date = _parse_event_date(body.event_date)
    event_end_date = _parse_event_date(body.event_end_date) if body.event_end_date else None

    event = GroupEvent(
        group_id=group.id,
        created_by=current_user.id,
        name=body.name,
        description=body.description,
        latitude=body.latitude,
        longitude=body.longitude,
        event_date=event_date,
        event_end_date=event_end_date,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)

    enriched = await _enrich_events([event], db, current_user.id)
    return enriched[0]


# ---------------------------------------------------------------------------
# GET /groups/{slug}/events — List events
# ---------------------------------------------------------------------------

@router.get("/{slug}/events", response_model=GroupEventListResponse)
async def list_group_events(
    slug: str,
    filter: str = Query(default="upcoming", pattern="^(upcoming|past|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(optional_user),
):
    group_result = await db.execute(select(Group).where(Group.slug == slug))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    if group.privacy == "private":
        if current_user is None or not await _is_active_member(group.id, current_user.id, db):
            raise HTTPException(status_code=403, detail="You must be a member to view this group's events.")

    q = select(GroupEvent).where(GroupEvent.group_id == group.id)

    if filter == "upcoming":
        q = _upcoming_filter(q).order_by(GroupEvent.event_date.asc())
    elif filter == "past":
        q = _past_filter(q).order_by(GroupEvent.event_date.desc())
    else:  # all
        q = q.order_by(GroupEvent.event_date.desc())

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    events_result = await db.execute(q.offset(offset).limit(limit))
    events = events_result.scalars().all()

    current_user_id = current_user.id if current_user else None
    enriched = await _enrich_events(list(events), db, current_user_id)
    return {"events": enriched, "total": total}


# ---------------------------------------------------------------------------
# GET /groups/{slug}/events/{event_id} — Get single event
# ---------------------------------------------------------------------------

@router.get("/{slug}/events/{event_id}", response_model=GroupEventResponse)
async def get_group_event(
    slug: str,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(optional_user),
):
    group_result = await db.execute(select(Group).where(Group.slug == slug))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    if group.privacy == "private":
        if current_user is None or not await _is_active_member(group.id, current_user.id, db):
            raise HTTPException(status_code=403, detail="You must be a member to view this group's events.")

    event_result = await db.execute(
        select(GroupEvent).where(
            GroupEvent.id == event_id,
            GroupEvent.group_id == group.id,
        )
    )
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    current_user_id = current_user.id if current_user else None
    enriched = await _enrich_events([event], db, current_user_id)
    return enriched[0]


# ---------------------------------------------------------------------------
# PUT /groups/{slug}/events/{event_id} — Update event
# ---------------------------------------------------------------------------

@router.put("/{slug}/events/{event_id}", response_model=GroupEventResponse)
async def update_group_event(
    slug: str,
    event_id: uuid.UUID,
    body: GroupEventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_result = await db.execute(select(Group).where(Group.slug == slug))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    if not await _is_mod_or_owner(group.id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Only moderators and owners can edit events.")

    event_result = await db.execute(
        select(GroupEvent).where(
            GroupEvent.id == event_id,
            GroupEvent.group_id == group.id,
        )
    )
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    if body.name is not None:
        event.name = body.name
    if body.description is not None:
        event.description = body.description
    if body.latitude is not None:
        event.latitude = body.latitude
    if body.longitude is not None:
        event.longitude = body.longitude
    if body.event_date is not None:
        event.event_date = _parse_event_date(body.event_date)
    if body.event_end_date is not None:
        event.event_end_date = _parse_event_date(body.event_end_date)

    await db.flush()
    await db.refresh(event)

    enriched = await _enrich_events([event], db, current_user.id)
    return enriched[0]


# ---------------------------------------------------------------------------
# DELETE /groups/{slug}/events/{event_id} — Delete event
# ---------------------------------------------------------------------------

@router.delete("/{slug}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group_event(
    slug: str,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_result = await db.execute(select(Group).where(Group.slug == slug))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    if not await _is_mod_or_owner(group.id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Only moderators and owners can delete events.")

    event_result = await db.execute(
        select(GroupEvent).where(
            GroupEvent.id == event_id,
            GroupEvent.group_id == group.id,
        )
    )
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    # Delete RSVPs first
    rsvps_result = await db.execute(
        select(GroupEventRsvp).where(GroupEventRsvp.event_id == event_id)
    )
    for rsvp in rsvps_result.scalars().all():
        await db.delete(rsvp)

    await db.delete(event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# POST /groups/{slug}/events/{event_id}/rsvp — Toggle RSVP
# ---------------------------------------------------------------------------

@router.post("/{slug}/events/{event_id}/rsvp")
async def toggle_event_rsvp(
    slug: str,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group_result = await db.execute(select(Group).where(Group.slug == slug))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    if not await _is_active_member(group.id, current_user.id, db):
        raise HTTPException(status_code=403, detail="You must be an active member to RSVP.")

    event_result = await db.execute(
        select(GroupEvent).where(
            GroupEvent.id == event_id,
            GroupEvent.group_id == group.id,
        )
    )
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    existing_result = await db.execute(
        select(GroupEventRsvp).where(
            GroupEventRsvp.event_id == event_id,
            GroupEventRsvp.user_id == current_user.id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        rsvpd = False
    else:
        rsvp = GroupEventRsvp(event_id=event_id, user_id=current_user.id)
        db.add(rsvp)
        rsvpd = True

    await db.flush()

    count_result = await db.execute(
        select(func.count()).select_from(GroupEventRsvp).where(GroupEventRsvp.event_id == event_id)
    )
    rsvp_count = count_result.scalar_one()

    return {"rsvpd": rsvpd, "rsvp_count": rsvp_count}


# ---------------------------------------------------------------------------
# GET /events/map-pins — Upcoming event pins for current user's groups
# ---------------------------------------------------------------------------

@events_router.get("/map-pins", response_model=List[EventPinResponse])
async def get_event_map_pins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get all groups the user is an active member of
    membership_result = await db.execute(
        select(GroupMember.group_id).where(
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    group_ids = [row.group_id for row in membership_result]

    if not group_ids:
        return []

    # Query upcoming events for those groups
    now = datetime.utcnow()
    events_q = select(GroupEvent).where(
        GroupEvent.group_id.in_(group_ids),
        (GroupEvent.event_date >= now)
        | (
            (GroupEvent.event_end_date.isnot(None))
            & (GroupEvent.event_end_date >= now)
        ),
    )
    events_result = await db.execute(events_q)
    events = events_result.scalars().all()

    if not events:
        return []

    event_ids = [e.id for e in events]
    all_group_ids = list({e.group_id for e in events})

    # Fetch groups
    groups_result = await db.execute(select(Group).where(Group.id.in_(all_group_ids)))
    groups_map = {g.id: g for g in groups_result.scalars().all()}

    # Fetch RSVP counts
    rsvp_counts_result = await db.execute(
        select(GroupEventRsvp.event_id, func.count().label("cnt"))
        .where(GroupEventRsvp.event_id.in_(event_ids))
        .group_by(GroupEventRsvp.event_id)
    )
    rsvp_counts_map = {row.event_id: row.cnt for row in rsvp_counts_result}

    # Fetch user RSVPs
    user_rsvps_result = await db.execute(
        select(GroupEventRsvp.event_id).where(
            GroupEventRsvp.event_id.in_(event_ids),
            GroupEventRsvp.user_id == current_user.id,
        )
    )
    user_rsvp_set = {row.event_id for row in user_rsvps_result}

    pins = []
    for event in events:
        group = groups_map.get(event.group_id)
        if not group:
            continue
        pins.append(
            EventPinResponse(
                id=event.id,
                group_id=event.group_id,
                group_name=group.name,
                group_slug=group.slug,
                name=event.name,
                latitude=event.latitude,
                longitude=event.longitude,
                event_date=event.event_date,
                event_end_date=event.event_end_date,
                rsvp_count=rsvp_counts_map.get(event.id, 0),
                user_has_rsvpd=event.id in user_rsvp_set,
            )
        )
    return pins
