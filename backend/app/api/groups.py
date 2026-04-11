"""
Group endpoints — authenticated users can create and join groups.

Groups have two privacy levels:
- "public"  — anyone can join, members list is public.
- "private" — join requests require approval, members list is restricted.

Roles within a group: "owner", "moderator", "member".
Membership status: "active" or "pending" (pending = awaiting approval for private groups).
"""

from __future__ import annotations

import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, optional_user
from app.models.database import Group, GroupMember, User, get_db
from app.models.schemas import (
    GroupCreate,
    GroupInvite,
    GroupListResponse,
    GroupMemberListResponse,
    GroupMemberResponse,
    GroupResponse,
    GroupSearchResult,
    GroupUpdate,
)

router = APIRouter(prefix="/groups", tags=["groups"])


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a group name to a URL-safe slug."""
    slug = name.lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug or "group"


async def _unique_slug(base: str, db: AsyncSession, exclude_id: Optional[uuid.UUID] = None) -> str:
    """Return a unique slug, appending -2, -3, … if the base is taken."""
    candidate = base
    counter = 2
    while True:
        q = select(Group).where(Group.slug == candidate)
        if exclude_id is not None:
            q = q.where(Group.id != exclude_id)
        result = await db.execute(q)
        existing = result.scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


# ---------------------------------------------------------------------------
# Response building helpers
# ---------------------------------------------------------------------------

async def _member_count(group_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(GroupMember)
        .where(GroupMember.group_id == group_id, GroupMember.status == "active")
    )
    return result.scalar_one()


async def _get_membership(
    group_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Optional[GroupMember]:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _build_group_response(
    group: Group, db: AsyncSession, current_user: Optional[User] = None
) -> dict:
    count = await _member_count(group.id, db)
    is_member = False
    user_role = None
    pending_request = False
    if current_user is not None:
        membership = await _get_membership(group.id, current_user.id, db)
        if membership is not None:
            if membership.status == "active":
                is_member = True
                user_role = membership.role
            elif membership.status == "pending":
                pending_request = True
    return GroupResponse(
        id=group.id,
        name=group.name,
        slug=group.slug,
        description=group.description,
        privacy=group.privacy,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=count,
        is_member=is_member,
        user_role=user_role,
        pending_request=pending_request,
    ).model_dump()


# ---------------------------------------------------------------------------
# POST /groups — create a group
# ---------------------------------------------------------------------------

@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    base_slug = _slugify(body.name)
    slug = await _unique_slug(base_slug, db)

    group = Group(
        name=body.name,
        slug=slug,
        description=body.description,
        privacy=body.privacy,
        created_by=current_user.id,
    )
    db.add(group)
    await db.flush()

    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="owner",
        status="active",
    )
    db.add(member)
    await db.flush()
    await db.refresh(group)

    return GroupResponse(
        id=group.id,
        name=group.name,
        slug=group.slug,
        description=group.description,
        privacy=group.privacy,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=1,
        is_member=True,
        user_role="owner",
    ).model_dump()


# ---------------------------------------------------------------------------
# GET /groups/search?q= — search groups (public)
# ---------------------------------------------------------------------------

@router.get("/search", response_model=List[GroupSearchResult])
async def search_groups(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    like_q = f"%{q}%"
    result = await db.execute(
        select(Group)
        .where(
            Group.name.ilike(like_q) | Group.description.ilike(like_q)
        )
        .limit(20)
    )
    groups = result.scalars().all()
    out = []
    for g in groups:
        count = await _member_count(g.id, db)
        out.append(
            GroupSearchResult(
                id=g.id,
                name=g.name,
                slug=g.slug,
                description=g.description,
                privacy=g.privacy,
                member_count=count,
            ).model_dump()
        )
    return out


# ---------------------------------------------------------------------------
# GET /groups/my — list the current user's groups
# ---------------------------------------------------------------------------

@router.get("/my", response_model=GroupListResponse)
async def list_my_groups(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupListResponse:
    # Find all group IDs where the user is an active member
    mem_result = await db.execute(
        select(GroupMember.group_id)
        .where(
            GroupMember.user_id == current_user.id,
            GroupMember.status == "active",
        )
    )
    group_ids = [row[0] for row in mem_result.all()]

    total = len(group_ids)

    if not group_ids:
        return GroupListResponse(groups=[], total=0)

    paginated_ids = group_ids[offset: offset + limit]
    groups_result = await db.execute(
        select(Group).where(Group.id.in_(paginated_ids))
    )
    groups = groups_result.scalars().all()

    out = []
    for g in groups:
        resp = await _build_group_response(g, db, current_user)
        out.append(resp)

    return GroupListResponse(groups=out, total=total)


# ---------------------------------------------------------------------------
# GET /groups/{slug} — get a group profile (public, optional auth)
# ---------------------------------------------------------------------------

@router.get("/{slug}", response_model=GroupResponse)
async def get_group(
    slug: str,
    current_user: Optional[User] = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    return await _build_group_response(group, db, current_user)


# ---------------------------------------------------------------------------
# PUT /groups/{slug} — update a group (owner or moderator only)
# ---------------------------------------------------------------------------

@router.put("/{slug}", response_model=GroupResponse)
async def update_group(
    slug: str,
    body: GroupUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    membership = await _get_membership(group.id, current_user.id, db)
    if membership is None or membership.role not in ("owner", "moderator") or membership.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if body.name is not None:
        group.name = body.name
        base_slug = _slugify(body.name)
        group.slug = await _unique_slug(base_slug, db, exclude_id=group.id)
    if body.description is not None:
        group.description = body.description
    if body.privacy is not None:
        group.privacy = body.privacy

    await db.flush()
    await db.refresh(group)
    return await _build_group_response(group, db, current_user)


# ---------------------------------------------------------------------------
# DELETE /groups/{slug} — delete a group (owner only)
# ---------------------------------------------------------------------------

@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_group(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    membership = await _get_membership(group.id, current_user.id, db)
    if membership is None or membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete this group")

    # Delete all member rows
    members_result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group.id)
    )
    for m in members_result.scalars().all():
        await db.delete(m)

    await db.delete(group)


# ---------------------------------------------------------------------------
# POST /groups/{slug}/join — join or request to join a group
# ---------------------------------------------------------------------------

@router.post("/{slug}/join")
async def join_group(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    existing = await _get_membership(group.id, current_user.id, db)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member or request pending")

    new_status = "active" if group.privacy == "public" else "pending"
    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="member",
        status=new_status,
    )
    db.add(member)
    await db.flush()

    message = "Joined group" if new_status == "active" else "Join request sent"
    return {"message": message}


# ---------------------------------------------------------------------------
# POST /groups/{slug}/leave — leave a group
# ---------------------------------------------------------------------------

@router.post("/{slug}/leave", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def leave_group(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    membership = await _get_membership(group.id, current_user.id, db)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member")

    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner cannot leave the group. Delete the group or transfer ownership first.",
        )

    await db.delete(membership)


# ---------------------------------------------------------------------------
# GET /groups/{slug}/members — list members
# ---------------------------------------------------------------------------

def _role_order(role: str) -> int:
    return {"owner": 0, "moderator": 1, "member": 2}.get(role, 3)


async def _build_member_responses(
    members: List[GroupMember], db: AsyncSession
) -> List[dict]:
    if not members:
        return []
    user_ids = [m.user_id for m in members]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    out = []
    for m in members:
        u = users_map.get(m.user_id)
        out.append(
            GroupMemberResponse(
                user_id=m.user_id,
                username=u.username if u else None,
                display_name=u.display_name if u else None,
                avatar_url=u.avatar_url if u else None,
                role=m.role,
                joined_at=m.joined_at,
            ).model_dump()
        )
    return out


@router.get("/{slug}/members", response_model=GroupMemberListResponse)
async def list_group_members(
    slug: str,
    current_user: Optional[User] = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> GroupMemberListResponse:
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    if group.privacy == "private":
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Members list is private")
        membership = await _get_membership(group.id, current_user.id, db)
        if membership is None or membership.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Members list is private")

    members_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.status == "active",
        )
    )
    members = sorted(members_result.scalars().all(), key=lambda m: (_role_order(m.role), ""))
    out = await _build_member_responses(members, db)
    return GroupMemberListResponse(members=out, total=len(out))


# ---------------------------------------------------------------------------
# GET /groups/{slug}/requests — list pending join requests (mod/owner only)
# ---------------------------------------------------------------------------

@router.get("/{slug}/requests", response_model=GroupMemberListResponse)
async def list_join_requests(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupMemberListResponse:
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    membership = await _get_membership(group.id, current_user.id, db)
    if membership is None or membership.role not in ("owner", "moderator") or membership.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    pending_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.status == "pending",
        )
    )
    members = list(pending_result.scalars().all())
    out = await _build_member_responses(members, db)
    return GroupMemberListResponse(members=out, total=len(out))


# ---------------------------------------------------------------------------
# Shared helper: look up a member by username
# ---------------------------------------------------------------------------

async def _find_member_by_username(
    group: Group, username: str, db: AsyncSession
) -> tuple[User, GroupMember]:
    user_result = await db.execute(select(User).where(User.username == username))
    target_user = user_result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = await _get_membership(group.id, target_user.id, db)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    return target_user, membership


# ---------------------------------------------------------------------------
# POST /groups/{slug}/members/{username}/approve
# ---------------------------------------------------------------------------

@router.post("/{slug}/members/{username}/approve", response_model=GroupMemberResponse)
async def approve_join_request(
    slug: str,
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    actor = await _get_membership(group.id, current_user.id, db)
    if actor is None or actor.role not in ("owner", "moderator") or actor.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    target_user, membership = await _find_member_by_username(group, username, db)
    if membership.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending request")

    membership.status = "active"
    await db.flush()

    return GroupMemberResponse(
        user_id=target_user.id,
        username=target_user.username,
        display_name=target_user.display_name,
        avatar_url=target_user.avatar_url,
        role=membership.role,
        joined_at=membership.joined_at,
    ).model_dump()


# ---------------------------------------------------------------------------
# POST /groups/{slug}/members/{username}/deny
# ---------------------------------------------------------------------------

@router.post("/{slug}/members/{username}/deny", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def deny_join_request(
    slug: str,
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    actor = await _get_membership(group.id, current_user.id, db)
    if actor is None or actor.role not in ("owner", "moderator") or actor.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    target_user, membership = await _find_member_by_username(group, username, db)
    if membership.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending request")

    await db.delete(membership)


# ---------------------------------------------------------------------------
# POST /groups/{slug}/members/{username}/kick
# ---------------------------------------------------------------------------

@router.post("/{slug}/members/{username}/kick", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def kick_member(
    slug: str,
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    actor = await _get_membership(group.id, current_user.id, db)
    if actor is None or actor.role not in ("owner", "moderator") or actor.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    target_user, membership = await _find_member_by_username(group, username, db)

    # Moderators cannot kick owners or other moderators
    if actor.role == "moderator" and membership.role in ("owner", "moderator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Moderators can only kick regular members")

    if membership.role == "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot kick the group owner")

    await db.delete(membership)


# ---------------------------------------------------------------------------
# PUT /groups/{slug}/members/{username}/role — change a member's role
# ---------------------------------------------------------------------------

@router.put("/{slug}/members/{username}/role", response_model=GroupMemberResponse)
async def change_member_role(
    slug: str,
    username: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    new_role = body.get("role")
    if new_role not in ("moderator", "member"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="role must be 'moderator' or 'member'")

    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    actor = await _get_membership(group.id, current_user.id, db)
    if actor is None or actor.role != "owner" or actor.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can change roles")

    target_user, membership = await _find_member_by_username(group, username, db)

    if membership.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the owner's role")

    membership.role = new_role
    await db.flush()

    return GroupMemberResponse(
        user_id=target_user.id,
        username=target_user.username,
        display_name=target_user.display_name,
        avatar_url=target_user.avatar_url,
        role=membership.role,
        joined_at=membership.joined_at,
    ).model_dump()


# ---------------------------------------------------------------------------
# POST /groups/{slug}/invite — invite a user (mod/owner only)
# ---------------------------------------------------------------------------

@router.post("/{slug}/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    slug: str,
    body: GroupInvite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Group).where(Group.slug == slug))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    actor = await _get_membership(group.id, current_user.id, db)
    if actor is None or actor.role not in ("owner", "moderator") or actor.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    user_result = await db.execute(select(User).where(User.username == body.username))
    target_user = user_result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await _get_membership(group.id, target_user.id, db)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member or has a pending request")

    member = GroupMember(
        group_id=group.id,
        user_id=target_user.id,
        role="member",
        status="active",
    )
    db.add(member)
    await db.flush()

    return {"message": f"Invited {body.username} to the group"}
