"""
Hunt plan endpoints — authenticated users can plan future metal detecting hunts.

Each plan has a drawn zone (polygon/rectangle/circle), metadata, in-zone markers,
a gear checklist, permission info, and optional photo URLs.

All endpoints enforce owner_id == current_user.id; plans not belonging to the
caller return 404 to avoid leaking existence.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from shapely.geometry import shape
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.models.database import HuntPlan, HuntPlanStatus, User, get_db
from app.models.schemas import (
    HuntPlanCreate,
    HuntPlanListResponse,
    HuntPlanMapPin,
    HuntPlanResponse,
    HuntPlanStatusUpdate,
    HuntPlanUpdate,
)

router = APIRouter(prefix="/hunt-plans", tags=["hunt-plans"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PLANNED_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def _parse_planned_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in PLANNED_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Invalid planned_date format: {value!r}. Use ISO 8601.",
    )


def _compute_centroid(area_geojson: dict):
    """Return a PostGIS POINT expression for the centroid of the GeoJSON geometry."""
    try:
        geom_input = area_geojson
        # Handle GeoJSON Feature wrapper
        if geom_input.get("type") == "Feature":
            geom_input = geom_input["geometry"]
        centroid = shape(geom_input).centroid
        return ST_SetSRID(ST_MakePoint(centroid.x, centroid.y), 4326)
    except Exception:
        return None


def _plan_to_response(plan: HuntPlan) -> dict:
    """Convert an ORM HuntPlan to a response dict including geom as {lat, lng}."""
    d = {
        "id": plan.id,
        "owner_id": plan.owner_id,
        "title": plan.title,
        "planned_date": plan.planned_date,
        "site_type": plan.site_type,
        "status": plan.status,
        "notes": plan.notes,
        "geom": None,
        "area_geojson": plan.area_geojson,
        "in_zone_markers": plan.in_zone_markers,
        "gear_checklist": plan.gear_checklist,
        "permission": plan.permission,
        "view_snapshot": plan.view_snapshot,
        "photo_urls": plan.photo_urls,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }
    # Derive centroid from area_geojson for the response
    try:
        geom_input = plan.area_geojson
        if geom_input.get("type") == "Feature":
            geom_input = geom_input["geometry"]
        centroid = shape(geom_input).centroid
        d["geom"] = {"lat": centroid.y, "lng": centroid.x}
    except Exception:
        pass
    return d


def _get_centroid_lat_lng(area_geojson: dict) -> tuple[Optional[float], Optional[float]]:
    """Return (lat, lng) centroid from area_geojson, or (None, None) on failure."""
    try:
        geom_input = area_geojson
        if geom_input.get("type") == "Feature":
            geom_input = geom_input["geometry"]
        centroid = shape(geom_input).centroid
        return centroid.y, centroid.x
    except Exception:
        return None, None


def _require_owner(plan: Optional[HuntPlan], current_user: User) -> HuntPlan:
    if plan is None or plan.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


# ---------------------------------------------------------------------------
# POST /hunt-plans  — create a plan
# ---------------------------------------------------------------------------

@router.post("", response_model=HuntPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: HuntPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plan = HuntPlan(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        title=payload.title,
        area_geojson=payload.area_geojson,
        planned_date=_parse_planned_date(payload.planned_date),
        site_type=payload.site_type,
        status=HuntPlanStatus.idea,
        notes=payload.notes,
        in_zone_markers=payload.in_zone_markers,
        gear_checklist=payload.gear_checklist,
        permission=payload.permission,
        view_snapshot=payload.view_snapshot,
        photo_urls=payload.photo_urls,
        geom=_compute_centroid(payload.area_geojson),
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return _plan_to_response(plan)


# ---------------------------------------------------------------------------
# GET /hunt-plans/me  — list caller's plans
# NOTE: must be defined BEFORE /{plan_id} to avoid routing conflict
# ---------------------------------------------------------------------------

@router.get("/me", response_model=HuntPlanListResponse)
async def list_my_plans(
    q: Optional[str] = Query(None, description="Search in title/notes"),
    sort: str = Query("created_at", pattern=r"^(created_at|updated_at|planned_date|title)$"),
    order: str = Query("desc", pattern=r"^(asc|desc)$"),
    site_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(HuntPlan).where(HuntPlan.owner_id == current_user.id)

    # Exclude archived by default
    if status_filter:
        stmt = stmt.where(HuntPlan.status == HuntPlanStatus(status_filter))
    elif not include_archived:
        stmt = stmt.where(HuntPlan.status != HuntPlanStatus.archived)

    if site_type:
        stmt = stmt.where(HuntPlan.site_type == site_type)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(HuntPlan.title.ilike(pattern), HuntPlan.notes.ilike(pattern))
        )

    # Sorting
    sort_col = {
        "created_at": HuntPlan.created_at,
        "updated_at": HuntPlan.updated_at,
        "planned_date": HuntPlan.planned_date,
        "title": HuntPlan.title,
    }[sort]
    stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    # Count total (without pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    plans = result.scalars().all()

    return {"plans": [_plan_to_response(p) for p in plans], "total": total}


# ---------------------------------------------------------------------------
# GET /hunt-plans/map-pins  — lightweight list for map layer
# NOTE: must be defined BEFORE /{plan_id} to avoid routing conflict
# ---------------------------------------------------------------------------

@router.get("/map-pins", response_model=List[HuntPlanMapPin])
async def get_map_pins(
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    stmt = select(HuntPlan).where(HuntPlan.owner_id == current_user.id)
    if not include_archived:
        stmt = stmt.where(HuntPlan.status != HuntPlanStatus.archived)

    result = await db.execute(stmt)
    plans = result.scalars().all()

    pins = []
    for plan in plans:
        lat, lng = _get_centroid_lat_lng(plan.area_geojson)
        if lat is None:
            continue
        planned_date_str = (
            plan.planned_date.strftime("%Y-%m-%d") if plan.planned_date else None
        )
        notes_preview = (
            (plan.notes[:140] + "…") if plan.notes and len(plan.notes) > 140
            else plan.notes or None
        )
        pins.append({
            "id": plan.id,
            "title": plan.title,
            "lat": lat,
            "lng": lng,
            "status": plan.status,
            "site_type": plan.site_type,
            "area_geojson": plan.area_geojson,
            "planned_date": planned_date_str,
            "notes_preview": notes_preview,
        })
    return pins


# ---------------------------------------------------------------------------
# GET /hunt-plans/{plan_id}  — get single plan
# ---------------------------------------------------------------------------

@router.get("/{plan_id}", response_model=HuntPlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(HuntPlan).where(HuntPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    _require_owner(plan, current_user)
    return _plan_to_response(plan)


# ---------------------------------------------------------------------------
# PUT /hunt-plans/{plan_id}  — full update
# ---------------------------------------------------------------------------

@router.put("/{plan_id}", response_model=HuntPlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    payload: HuntPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(HuntPlan).where(HuntPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    _require_owner(plan, current_user)

    if payload.title is not None:
        plan.title = payload.title
    if payload.area_geojson is not None:
        plan.area_geojson = payload.area_geojson
        plan.geom = _compute_centroid(payload.area_geojson)
    if payload.planned_date is not None:
        plan.planned_date = _parse_planned_date(payload.planned_date) if payload.planned_date else None
    if payload.site_type is not None:
        plan.site_type = payload.site_type
    if payload.notes is not None:
        plan.notes = payload.notes
    if payload.in_zone_markers is not None:
        plan.in_zone_markers = payload.in_zone_markers
    if payload.gear_checklist is not None:
        plan.gear_checklist = payload.gear_checklist
    if payload.permission is not None:
        plan.permission = payload.permission
    if payload.view_snapshot is not None:
        plan.view_snapshot = payload.view_snapshot
    if payload.photo_urls is not None:
        plan.photo_urls = payload.photo_urls

    plan.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(plan)
    return _plan_to_response(plan)


# ---------------------------------------------------------------------------
# DELETE /hunt-plans/{plan_id}  — delete plan
# ---------------------------------------------------------------------------

@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HuntPlan).where(HuntPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    _require_owner(plan, current_user)
    await db.delete(plan)


# ---------------------------------------------------------------------------
# PATCH /hunt-plans/{plan_id}/status  — transition status
# ---------------------------------------------------------------------------

@router.patch("/{plan_id}/status", response_model=HuntPlanResponse)
async def update_plan_status(
    plan_id: uuid.UUID,
    payload: HuntPlanStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(HuntPlan).where(HuntPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    _require_owner(plan, current_user)

    plan.status = payload.status
    plan.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(plan)
    return _plan_to_response(plan)


# ---------------------------------------------------------------------------
# POST /hunt-plans/{plan_id}/duplicate  — clone plan
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/duplicate", response_model=HuntPlanResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(HuntPlan).where(HuntPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    _require_owner(plan, current_user)

    new_plan = HuntPlan(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        title=f"{plan.title} (copy)",
        area_geojson=plan.area_geojson,
        planned_date=plan.planned_date,
        site_type=plan.site_type,
        status=HuntPlanStatus.idea,
        notes=plan.notes,
        in_zone_markers=plan.in_zone_markers,
        gear_checklist=plan.gear_checklist,
        permission=plan.permission,
        view_snapshot=plan.view_snapshot,
        photo_urls=plan.photo_urls,
        geom=_compute_centroid(plan.area_geojson),
    )
    db.add(new_plan)
    await db.flush()
    await db.refresh(new_plan)
    return _plan_to_response(new_plan)


# ---------------------------------------------------------------------------
# GET /hunt-plans/{plan_id}/export.gpx  — GPX export
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/export.gpx")
async def export_gpx(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(select(HuntPlan).where(HuntPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    _require_owner(plan, current_user)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Prescia Maps"',
        '  xmlns="http://www.topografix.com/GPX/1/1"',
        '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '  xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        f'  <metadata><name>{_xml_escape(plan.title)}</name></metadata>',
    ]

    # In-zone markers as waypoints
    if plan.in_zone_markers:
        for marker in plan.in_zone_markers:
            lat = marker.get("lat", 0)
            lng = marker.get("lng", 0)
            name = _xml_escape(marker.get("label") or marker.get("type", "marker"))
            desc = _xml_escape(f"{marker.get('type', '')} — {marker.get('note') or ''}")
            lines.append(f'  <wpt lat="{lat}" lon="{lng}">')
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <desc>{desc}</desc>")
            lines.append("  </wpt>")

    # Polygon as track
    try:
        geom_input = plan.area_geojson
        if geom_input.get("type") == "Feature":
            geom_input = geom_input["geometry"]
        coords = _extract_polygon_coords(geom_input)
        if coords:
            lines.append("  <trk>")
            lines.append(f"    <name>{_xml_escape(plan.title)}</name>")
            lines.append("    <trkseg>")
            for lng, lat in coords:
                lines.append(f'      <trkpt lat="{lat}" lon="{lng}"></trkpt>')
            lines.append("    </trkseg>")
            lines.append("  </trk>")
    except Exception:
        pass

    lines.append("</gpx>")
    gpx_content = "\n".join(lines)

    filename = f"hunt-plan-{plan.id}.gpx"
    return Response(
        content=gpx_content,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xml_escape(s: str) -> str:
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _extract_polygon_coords(geom: dict) -> list:
    """Extract the outer ring coordinates from a GeoJSON Polygon, Rectangle, or Circle."""
    geom_type = geom.get("type", "")
    if geom_type == "Polygon":
        return geom.get("coordinates", [[]])[0]
    elif geom_type == "MultiPolygon":
        coords = geom.get("coordinates", [[[]]])
        return coords[0][0] if coords else []
    # Circle stored as Point with radius — approximate with bounding box
    elif geom_type == "Point":
        coords = geom.get("coordinates", [0, 0])
        # Return just the center point if radius not available
        return [coords]
    return []


# ---------------------------------------------------------------------------
# GET /hunt-plans/{plan_id}/export.pdf  — PDF export
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/export.pdf")
async def export_pdf(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(select(HuntPlan).where(HuntPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    _require_owner(plan, current_user)

    pdf_bytes = _build_pdf(plan)
    filename = f"hunt-plan-{plan.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _fetch_mapbox_static_image(plan: HuntPlan) -> Optional[bytes]:
    """
    Fetch a static map image from the Mapbox Static Images API showing the
    plan's drawn area and in-zone markers.  Returns PNG bytes or None on any
    failure (bad token, network error, oversized URL, etc.).
    """
    import json
    import logging
    from urllib.parse import quote

    import httpx
    from shapely.geometry import mapping, shape

    token = settings.MAPBOX_TOKEN
    if not token:
        return None

    try:
        geom_input = plan.area_geojson or {}
        if geom_input.get("type") == "Feature":
            geom_input = geom_input["geometry"]

        geom = shape(geom_input)

        # Marker colors by in-zone marker type
        _MARKER_COLORS: dict = {
            "dig_target": "00b700",
            "avoid": "f44336",
            "access": "2196f3",
            "already_detected": "9e9e9e",
        }

        def _pin_overlays() -> list:
            pins = []
            if plan.in_zone_markers:
                for m in plan.in_zone_markers:
                    lat = m.get("lat")
                    lng = m.get("lng")
                    if lat is None or lng is None:
                        continue
                    color = _MARKER_COLORS.get(m.get("type", ""), "ff8c00")
                    pins.append(f"pin-s+{color}({lng},{lat})")
            return pins

        def _build_url(simplified_geom) -> str:
            feature = {
                "type": "Feature",
                "geometry": mapping(simplified_geom),
                "properties": {
                    "fill": "#d97706",
                    "fill-opacity": 0.3,
                    "stroke": "#d97706",
                    "stroke-width": 2,
                    "stroke-opacity": 1,
                },
            }
            geojson_overlay = f"geojson({quote(json.dumps(feature, separators=(',', ':')))})"
            overlays = [geojson_overlay] + _pin_overlays()
            overlay_str = ",".join(overlays)
            return (
                f"https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12"
                f"/static/{overlay_str}/auto/600x400@2x"
                f"?access_token={token}&padding=50"
            )

        # Try with light simplification first, then heavier, then centroid fallback
        for tolerance in (0.0001, 0.001, 0.01):
            simplified = geom.simplify(tolerance, preserve_topology=True)
            url = _build_url(simplified)
            if len(url) <= 8000:
                break
        else:
            # Last resort: centroid + zoom (no polygon overlay)
            centroid = geom.centroid
            pins = ",".join(_pin_overlays())
            overlay_str = pins if pins else ""
            if overlay_str:
                url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12"
                    f"/static/{overlay_str}/{centroid.x},{centroid.y},13"
                    f"/600x400@2x?access_token={token}"
                )
            else:
                url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12"
                    f"/static/{centroid.x},{centroid.y},13/600x400@2x"
                    f"?access_token={token}"
                )

        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    except Exception as exc:
        logging.getLogger(__name__).warning("Mapbox static image fetch failed: %s", exc)
        return None


def _build_pdf(plan: HuntPlan) -> bytes:
    """Build a PDF summary of the hunt plan using reportlab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.enums import TA_LEFT
    except ImportError:
        return b"%PDF-1.4 placeholder - reportlab not installed"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(plan.title, styles["Title"]))
    story.append(Spacer(1, 0.1 * inch))

    # Metadata table
    meta_rows = [["Status", plan.status.value.title()]]
    if plan.site_type:
        meta_rows.append(["Site Type", plan.site_type.replace("_", " ").title()])
    if plan.planned_date:
        meta_rows.append(["Planned Date", str(plan.planned_date)[:10]])
    meta_rows.append(["Created", str(plan.created_at)[:10] if plan.created_at else "—"])

    meta_table = Table(meta_rows, colWidths=[1.5 * inch, 4 * inch])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f0")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#fafaf8")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.15 * inch))

    # Static map image (satellite view of the drawn area)
    map_image_bytes = _fetch_mapbox_static_image(plan)
    if map_image_bytes:
        try:
            img_buffer = io.BytesIO(map_image_bytes)
            map_img = Image(img_buffer, width=6.5 * inch, height=(6.5 / 1.5) * inch)
            story.append(map_img)
            story.append(Spacer(1, 0.15 * inch))
        except Exception:
            pass  # skip map image on any rendering error

    # Notes
    if plan.notes:
        story.append(Paragraph("Notes", styles["Heading2"]))
        story.append(Paragraph(plan.notes.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    # Gear checklist
    if plan.gear_checklist:
        story.append(Paragraph("Gear Checklist", styles["Heading2"]))
        for item in plan.gear_checklist:
            checked = "☑" if item.get("checked") else "☐"
            story.append(Paragraph(f"{checked} {item.get('item', '')}", styles["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    # In-zone markers
    if plan.in_zone_markers:
        story.append(Paragraph("In-Zone Markers", styles["Heading2"]))
        marker_data = [["Type", "Label", "Note", "Lat", "Lng"]]
        for m in plan.in_zone_markers:
            marker_data.append([
                m.get("type", ""),
                m.get("label", ""),
                m.get("note") or "",
                str(round(m.get("lat", 0), 5)),
                str(round(m.get("lng", 0), 5)),
            ])
        marker_table = Table(marker_data, colWidths=[1 * inch, 1.3 * inch, 2 * inch, 0.9 * inch, 0.9 * inch])
        marker_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e2")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafaf8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(marker_table)
        story.append(Spacer(1, 0.15 * inch))

    # Permission info
    if plan.permission:
        p = plan.permission
        if any(p.get(k) for k in ("owner_name", "contact", "status", "expiry", "notes")):
            story.append(Paragraph("Permission Info", styles["Heading2"]))
            perm_rows = []
            if p.get("owner_name"):
                perm_rows.append(["Owner / Landowner", p["owner_name"]])
            if p.get("contact"):
                perm_rows.append(["Contact", p["contact"]])
            if p.get("status"):
                perm_rows.append(["Permission Status", p["status"]])
            if p.get("expiry"):
                perm_rows.append(["Expires", p["expiry"]])
            if p.get("notes"):
                perm_rows.append(["Notes", p["notes"]])
            if perm_rows:
                perm_table = Table(perm_rows, colWidths=[1.5 * inch, 4 * inch])
                perm_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f0")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(perm_table)
            story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    return buffer.getvalue()
