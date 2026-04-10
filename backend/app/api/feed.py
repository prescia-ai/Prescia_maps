"""
Feed endpoints — posts, comments, and reactions.

Routes (all mounted under /api/v1 in main.py):
  POST   /posts                              — create a post
  GET    /feed                               — global feed (public posts)
  GET    /feed/home                          — home feed (followed users, auth required)
  GET    /posts/user/{username}              — list posts by a specific user
  GET    /posts/{post_id}                    — single post
  DELETE /posts/{post_id}                    — delete own post
  GET    /posts/{post_id}/comments           — list comments
  POST   /posts/{post_id}/comments           — add a comment
  DELETE /posts/{post_id}/comments/{cid}     — delete own comment
  PUT    /posts/{post_id}/react              — toggle / switch reaction
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, optional_user
from app.models.database import (
    Post,
    PostComment,
    PostImage,
    PostReaction,
    User,
    UserFollow,
    get_db,
)
from app.models.schemas import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    PostCreate,
    PostImageResponse,
    PostListResponse,
    PostResponse,
    ReactRequest,
)

router = APIRouter(tags=["feed"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMPTY_REACTIONS: Dict[str, int] = {"gold": 0, "bullseye": 0, "shovel": 0, "fire": 0}


async def _build_post_responses(
    posts: List[Post],
    db: AsyncSession,
    current_user_id: Optional[uuid.UUID] = None,
) -> List[PostResponse]:
    """
    Enrich a list of Post ORM objects with author info, reaction counts,
    comment counts, and the current user's own reaction.

    Uses 4 additional queries (O(1) regardless of page size).
    """
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    author_ids = list({p.author_id for p in posts})

    # -- Authors ----------------------------------------------------------
    author_rows = await db.execute(select(User).where(User.id.in_(author_ids)))
    authors: Dict[uuid.UUID, User] = {u.id: u for u in author_rows.scalars().all()}

    # -- Reaction counts --------------------------------------------------
    reaction_rows = await db.execute(
        select(PostReaction.post_id, PostReaction.reaction_type, func.count().label("cnt"))
        .where(PostReaction.post_id.in_(post_ids))
        .group_by(PostReaction.post_id, PostReaction.reaction_type)
    )
    reactions_map: Dict[uuid.UUID, Dict[str, int]] = defaultdict(lambda: dict(_EMPTY_REACTIONS))
    for row in reaction_rows:
        reactions_map[row.post_id][row.reaction_type] = row.cnt

    # -- Comment counts ---------------------------------------------------
    comment_count_rows = await db.execute(
        select(PostComment.post_id, func.count().label("cnt"))
        .where(PostComment.post_id.in_(post_ids))
        .group_by(PostComment.post_id)
    )
    comment_count_map: Dict[uuid.UUID, int] = {row.post_id: row.cnt for row in comment_count_rows}

    # -- My reactions -----------------------------------------------------
    my_reaction_map: Dict[uuid.UUID, Optional[str]] = {}
    if current_user_id is not None:
        my_rows = await db.execute(
            select(PostReaction.post_id, PostReaction.reaction_type)
            .where(
                PostReaction.post_id.in_(post_ids),
                PostReaction.user_id == current_user_id,
            )
        )
        for row in my_rows:
            my_reaction_map[row.post_id] = row.reaction_type

    # -- Images -----------------------------------------------------------
    images_rows = await db.execute(
        select(PostImage)
        .where(PostImage.post_id.in_(post_ids))
        .order_by(PostImage.position)
    )
    images_map: Dict[uuid.UUID, list] = defaultdict(list)
    for img in images_rows.scalars().all():
        images_map[img.post_id].append(PostImageResponse(id=img.id, url=img.url, position=img.position))

    return [
        PostResponse(
            id=post.id,
            author_id=post.author_id,
            author_username=authors[post.author_id].username if post.author_id in authors else None,
            author_display_name=authors[post.author_id].display_name if post.author_id in authors else None,
            author_avatar_url=authors[post.author_id].avatar_url if post.author_id in authors else None,
            content=post.content,
            privacy=post.privacy,
            created_at=post.created_at,
            comment_count=comment_count_map.get(post.id, 0),
            reactions=reactions_map.get(post.id, dict(_EMPTY_REACTIONS)),
            my_reaction=my_reaction_map.get(post.id),
            images=images_map.get(post.id, []),
        )
        for post in posts
    ]


# ---------------------------------------------------------------------------
# POST /posts — create a post
# ---------------------------------------------------------------------------

@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    """Create a new feed post for the authenticated user."""
    post = Post(
        author_id=current_user.id,
        content=body.content,
        privacy=body.privacy or "public",
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    responses = await _build_post_responses([post], db, current_user.id)
    return responses[0]


# ---------------------------------------------------------------------------
# GET /feed — global feed (public posts, newest first)
# ---------------------------------------------------------------------------

@router.get("/feed", response_model=PostListResponse)
async def global_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> PostListResponse:
    """Return the most recent public posts from all users."""
    total_result = await db.execute(
        select(func.count()).select_from(Post).where(Post.privacy == "public")
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Post)
        .where(Post.privacy == "public")
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    posts = list(result.scalars().all())
    current_user_id = current_user.id if current_user else None
    post_responses = await _build_post_responses(posts, db, current_user_id)
    return PostListResponse(posts=post_responses, total=total)


# ---------------------------------------------------------------------------
# GET /feed/home — home feed (posts from followed users, auth required)
# ---------------------------------------------------------------------------

@router.get("/feed/home", response_model=PostListResponse)
async def home_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostListResponse:
    """
    Return posts from users the current user follows (plus their own posts).

    Includes "public" and "followers" privacy posts from followed users,
    and all non-private posts from the user themselves.
    """
    # IDs of users we follow
    following_result = await db.execute(
        select(UserFollow.following_id).where(UserFollow.follower_id == current_user.id)
    )
    following_ids = [row for row in following_result.scalars().all()]
    # Include own posts
    visible_author_ids = following_ids + [current_user.id]

    base_filter = (
        Post.author_id.in_(visible_author_ids),
        Post.privacy.in_(["public", "followers"]),
    )

    total_result = await db.execute(
        select(func.count()).select_from(Post).where(*base_filter)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Post)
        .where(*base_filter)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    posts = list(result.scalars().all())
    post_responses = await _build_post_responses(posts, db, current_user.id)
    return PostListResponse(posts=post_responses, total=total)


# ---------------------------------------------------------------------------
# GET /posts/user/{username} — list posts by a specific user
# ---------------------------------------------------------------------------

@router.get("/posts/user/{username}", response_model=PostListResponse)
async def user_posts(
    username: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> PostListResponse:
    """
    Return posts authored by *username*, filtered by privacy rules:

    - Viewer is the author → all posts (public, followers, private).
    - Viewer is authenticated and follows the author → public + followers posts.
    - Otherwise (anonymous or not following) → public posts only.
    """
    # Resolve the target user
    author_result = await db.execute(select(User).where(User.username == username))
    author = author_result.scalar_one_or_none()
    if author is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Determine which privacy levels the viewer may see
    if current_user is not None and current_user.id == author.id:
        # Own profile — see everything
        privacy_filter = Post.author_id == author.id
    elif current_user is not None:
        # Check if viewer follows the author
        follow_result = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user.id,
                UserFollow.following_id == author.id,
            )
        )
        is_following = follow_result.scalar_one_or_none() is not None
        if is_following:
            privacy_filter = (Post.author_id == author.id) & Post.privacy.in_(["public", "followers"])
        else:
            privacy_filter = (Post.author_id == author.id) & (Post.privacy == "public")
    else:
        # Anonymous viewer
        privacy_filter = (Post.author_id == author.id) & (Post.privacy == "public")

    total_result = await db.execute(
        select(func.count()).select_from(Post).where(privacy_filter)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Post)
        .where(privacy_filter)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    posts = list(result.scalars().all())
    current_user_id = current_user.id if current_user else None
    post_responses = await _build_post_responses(posts, db, current_user_id)
    return PostListResponse(posts=post_responses, total=total)


# ---------------------------------------------------------------------------
# GET /posts/{post_id} — single post
# ---------------------------------------------------------------------------

@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: uuid.UUID,
    current_user: Optional[User] = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    """Return a single post by ID."""
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Respect privacy
    if post.privacy == "private":
        if current_user is None or current_user.id != post.author_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    current_user_id = current_user.id if current_user else None
    responses = await _build_post_responses([post], db, current_user_id)
    return responses[0]


# ---------------------------------------------------------------------------
# DELETE /posts/{post_id} — delete own post
# ---------------------------------------------------------------------------

@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a post owned by the current user."""
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.author_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Cascade delete comments and reactions
    comments_result = await db.execute(select(PostComment).where(PostComment.post_id == post_id))
    for c in comments_result.scalars().all():
        await db.delete(c)

    reactions_result = await db.execute(select(PostReaction).where(PostReaction.post_id == post_id))
    for r in reactions_result.scalars().all():
        await db.delete(r)

    # Delete associated images from Drive and the database
    images_result = await db.execute(select(PostImage).where(PostImage.post_id == post_id))
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
            _logging.getLogger(__name__).warning("Could not clean up Drive files for post %s: %s", post_id, exc)
        for img in images:
            await db.delete(img)

    await db.delete(post)


# ---------------------------------------------------------------------------
# GET /posts/{post_id}/comments — list comments
# ---------------------------------------------------------------------------

@router.get("/posts/{post_id}/comments", response_model=CommentListResponse)
async def list_comments(
    post_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    """Return paginated comments for a post."""
    # Ensure post exists
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    if post_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    total_result = await db.execute(
        select(func.count()).select_from(PostComment).where(PostComment.post_id == post_id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(PostComment)
        .where(PostComment.post_id == post_id)
        .order_by(PostComment.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    comments = list(result.scalars().all())

    # Load authors
    author_ids = list({c.author_id for c in comments})
    authors: Dict[uuid.UUID, User] = {}
    if author_ids:
        author_rows = await db.execute(select(User).where(User.id.in_(author_ids)))
        authors = {u.id: u for u in author_rows.scalars().all()}

    comment_responses = [
        CommentResponse(
            id=c.id,
            post_id=c.post_id,
            author_id=c.author_id,
            author_username=authors[c.author_id].username if c.author_id in authors else None,
            author_display_name=authors[c.author_id].display_name if c.author_id in authors else None,
            author_avatar_url=authors[c.author_id].avatar_url if c.author_id in authors else None,
            content=c.content,
            created_at=c.created_at,
        )
        for c in comments
    ]
    return CommentListResponse(comments=comment_responses, total=total)


# ---------------------------------------------------------------------------
# POST /posts/{post_id}/comments — add a comment
# ---------------------------------------------------------------------------

@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    post_id: uuid.UUID,
    body: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Add a comment to a post."""
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    if post_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comment = PostComment(
        post_id=post_id,
        author_id=current_user.id,
        content=body.content,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        author_username=current_user.username,
        author_display_name=current_user.display_name,
        author_avatar_url=current_user.avatar_url,
        content=comment.content,
        created_at=comment.created_at,
    )


# ---------------------------------------------------------------------------
# DELETE /posts/{post_id}/comments/{comment_id} — delete own comment
# ---------------------------------------------------------------------------

@router.delete(
    "/posts/{post_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_comment(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment owned by the current user (or post owner can delete any comment)."""
    result = await db.execute(
        select(PostComment).where(
            PostComment.id == comment_id,
            PostComment.post_id == post_id,
        )
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # Allow comment author or post author to delete
    if comment.author_id != current_user.id:
        post_result = await db.execute(
            select(Post).where(Post.id == post_id, Post.author_id == current_user.id)
        )
        if post_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised")

    await db.delete(comment)


# ---------------------------------------------------------------------------
# PUT /posts/{post_id}/react — toggle / switch reaction
# ---------------------------------------------------------------------------

@router.put("/posts/{post_id}/react", response_model=PostResponse)
async def react_to_post(
    post_id: uuid.UUID,
    body: ReactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    """
    Toggle or switch the current user's reaction on a post.

    - If no existing reaction: add the new reaction.
    - If the same reaction already exists: remove it (toggle off).
    - If a different reaction exists: replace it.

    Returns the updated post response.
    """
    # Ensure post exists and is accessible
    post_result = await db.execute(select(Post).where(Post.id == post_id))
    post = post_result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    existing_result = await db.execute(
        select(PostReaction).where(
            PostReaction.user_id == current_user.id,
            PostReaction.post_id == post_id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is None:
        # No existing reaction — add new one
        reaction = PostReaction(
            user_id=current_user.id,
            post_id=post_id,
            reaction_type=body.reaction_type,
        )
        db.add(reaction)
    elif existing.reaction_type == body.reaction_type:
        # Same reaction — toggle off
        await db.delete(existing)
    else:
        # Different reaction — replace
        existing.reaction_type = body.reaction_type

    await db.flush()
    responses = await _build_post_responses([post], db, current_user.id)
    return responses[0]
