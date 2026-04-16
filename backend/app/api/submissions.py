"""
Community pin submission endpoints.

Users can submit historical pins for admin review.  Admins can list, edit,
approve, reject, and export submissions.  Approved submissions are written
to the existing ``locations`` table.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_admin
from app.auth.deps import get_current_user
from app.models.database import Location, LocationType, PinSubmission, User, get_db
from app.models.schemas import (
    PinSubmissionAdminUpdate,
    PinSubmissionCreate,
    PinSubmissionListResponse,
    PinSubmissionResponse,
)
from app.services.notification_service import create_notification

router = APIRouter(tags=["submissions"])


def _build_geom(lon: float, lat: float):
    """Return a PostGIS POINT expression for the given coordinates."""
    return ST_SetSRID(ST_MakePoint(lon, lat), 4326)


def _try_parse_year(date_era: str | None) -> int | None:
    """Attempt to extract a 4-digit year integer from a date/era string."""
    if not date_era:
        return None
    import re
    match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", date_era)
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

@router.post("/submissions", response_model=PinSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    body: PinSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinSubmission:
    """Create a new community pin submission (authenticated users)."""
    submission = PinSubmission(
        submitter_id=current_user.id,
        submitter_username=current_user.username,
        name=body.name,
        pin_type=body.pin_type,
        suggested_type=body.suggested_type,
        latitude=body.latitude,
        longitude=body.longitude,
        date_era=body.date_era,
        description=body.description,
        source_reference=body.source_reference,
        tags=body.tags,
        status="pending",
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    return submission


@router.get("/submissions/me", response_model=PinSubmissionListResponse)
async def list_my_submissions(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinSubmissionListResponse:
    """List the current user's own submissions."""
    base_query = select(PinSubmission).where(PinSubmission.submitter_id == current_user.id)
    count_query = select(func.count()).select_from(PinSubmission).where(
        PinSubmission.submitter_id == current_user.id
    )

    if status_filter:
        base_query = base_query.where(PinSubmission.status == status_filter)
        count_query = count_query.where(PinSubmission.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(PinSubmission.submitted_at.desc()).limit(limit).offset(offset)
    )
    submissions = result.scalars().all()
    return PinSubmissionListResponse(submissions=list(submissions), total=total)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.get("/admin/submissions/export")
async def export_approved_submissions(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export all approved submissions as a JSON file."""
    result = await db.execute(
        select(PinSubmission).where(PinSubmission.status == "approved")
    )
    submissions = result.scalars().all()

    export_data = [
        {
            "name": s.name,
            "type": s.pin_type,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "year": _try_parse_year(s.date_era),
            "description": s.description,
            "source": f"community:{s.submitter_username}",
            "confidence": 0.70,
        }
        for s in submissions
    ]

    content = json.dumps(export_data, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="community_pins_export.json"'},
    )


@router.get("/admin/submissions", response_model=PinSubmissionListResponse)
async def list_admin_submissions(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PinSubmissionListResponse:
    """List all submissions (admin only)."""
    base_query = select(PinSubmission)
    count_query = select(func.count()).select_from(PinSubmission)

    if status_filter:
        base_query = base_query.where(PinSubmission.status == status_filter)
        count_query = count_query.where(PinSubmission.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(PinSubmission.submitted_at.desc()).limit(limit).offset(offset)
    )
    submissions = result.scalars().all()
    return PinSubmissionListResponse(submissions=list(submissions), total=total)


@router.get("/admin/submissions/{submission_id}", response_model=PinSubmissionResponse)
async def get_admin_submission(
    submission_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PinSubmission:
    """Get a single submission with all fields (admin only)."""
    result = await db.execute(
        select(PinSubmission).where(PinSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


@router.put("/admin/submissions/{submission_id}", response_model=PinSubmissionResponse)
async def update_admin_submission(
    submission_id: uuid.UUID,
    body: PinSubmissionAdminUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PinSubmission:
    """Update a submission's fields and optionally approve or reject it (admin only)."""
    result = await db.execute(
        select(PinSubmission).where(PinSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    # Apply field edits
    if body.name is not None:
        submission.name = body.name
    if body.pin_type is not None:
        submission.pin_type = body.pin_type
    if body.suggested_type is not None:
        submission.suggested_type = body.suggested_type
    if body.latitude is not None:
        submission.latitude = body.latitude
    if body.longitude is not None:
        submission.longitude = body.longitude
    if body.date_era is not None:
        submission.date_era = body.date_era
    if body.description is not None:
        submission.description = body.description
    if body.source_reference is not None:
        submission.source_reference = body.source_reference
    if body.tags is not None:
        submission.tags = body.tags
    if body.admin_notes is not None:
        submission.admin_notes = body.admin_notes
    if body.rejection_reason is not None:
        submission.rejection_reason = body.rejection_reason

    # Handle status change
    if body.status is not None and body.status != submission.status:
        if body.status == "approved":
            # Validate pin_type is set and is a valid LocationType
            pin_type_value = submission.pin_type
            if not pin_type_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="pin_type must be set to a valid location type before approving",
                )
            try:
                loc_type = LocationType(pin_type_value)
            except ValueError:
                valid = [e.value for e in LocationType]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pin_type '{pin_type_value}'. Valid types: {valid}",
                )

            # Create a Location row
            year = _try_parse_year(submission.date_era)
            location = Location(
                name=submission.name,
                type=loc_type,
                latitude=submission.latitude,
                longitude=submission.longitude,
                year=year,
                description=submission.description,
                source=f"community:{submission.submitter_username}",
                confidence=0.70,
                geom=_build_geom(submission.longitude, submission.latitude),
            )
            db.add(location)
            submission.reviewed_at = datetime.now(timezone.utc)
            # Notify the submitter that their submission was approved
            await create_notification(
                db,
                type="submission_approved",
                user_id=submission.submitter_id,
                actor_id=admin.id,
                ref_id=str(submission_id),
            )

        elif body.status == "rejected":
            submission.reviewed_at = datetime.now(timezone.utc)

        submission.status = body.status

    await db.flush()
    # Commit here, before sending the response, so any newly-created Location
    # row is durable and visible to follow-up queries fired by the client
    # immediately after receiving the 200.  Without this explicit commit the
    # session is committed by get_db's generator cleanup, which runs *after*
    # the HTTP response has already been sent (standard ASGI teardown order).
    # That timing gap causes the client's cache-invalidation refetch to see no
    # new pin, and a silent commit error would permanently lose the row.
    await db.commit()
    await db.refresh(submission)
    return submission
