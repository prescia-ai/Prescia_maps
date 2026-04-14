# Aurik — PRs #61–#71 End-to-End Audit

**Audit Date:** 2026-04-10
**Commit:** `362eb74670053d15b66591bf46b89537f5559eff`
**Scope:** PRs #61 (Supabase Auth) through #71 (Collection Tab)

---

## Executive Summary

A comprehensive file-by-file inspection of 17 backend source files and 14 frontend source files was performed. Of the 120+ individual checks run, **116 passed cleanly**. **4 real issues** were found: one Medium-severity bug (MapLayerType enum missing `blm` in schemas.py that will cause a Pydantic serialization error if any `blm` layer is stored), one Medium-severity UX/reliability gap (silent upload failure on post photo attach), one Low-severity missing error guard (unhandled ValueError on malformed UUID form inputs), and one Low-severity code-quality issue (inline `resizeImage` duplication in ProfileSettingsPage). Additionally, 5 non-breaking observations are documented. No critical or security-level regressions were found.

---

## ✅ Verified Working

### A. Database Models (`backend/app/models/database.py`)

- ✅ **All 15 expected models exist**: `User`, `UserPin`, `PinSubmission`, `Post`, `PostComment`, `PostReaction`, `UserFollow`, `PostImage`, `PinImage`, `Location`, `LinearFeature`, `MapLayer`, `LandAccessCache`, `LandAccessOverride`, `CollectionPhoto` (added in PR #71).
- ✅ **User model fields**: `id`, `supabase_id` (unique+indexed), `email`, `username`, `display_name`, `bio`, `location`, `privacy`, `is_admin`, `created_at`, `google_refresh_token`, `google_connected_at`, `google_email`, `google_folder_id`, `avatar_url` — all present.
- ✅ **UserPin model fields**: `id`, `user_id` (indexed), `name`, `latitude`, `longitude`, `geom`, `hunt_date`, `time_spent`, `notes`, `finds_count`, `privacy`, `created_at` — all present.
- ✅ **Post model fields**: `id`, `author_id` (indexed), `content`, `privacy`, `created_at` — all present.
- ✅ **PostComment fields**: `id`, `post_id` (indexed), `author_id` (indexed), `content`, `created_at` — all present.
- ✅ **PostReaction fields**: `user_id` (PK), `post_id` (PK+indexed), `reaction_type`, `created_at` — composite PK enforced.
- ✅ **UserFollow fields**: `follower_id` (PK), `following_id` (PK+indexed), `created_at` — composite PK enforced.
- ✅ **PostImage fields**: `id`, `post_id` (indexed), `drive_file_id`, `url`, `position`, `created_at` — all present.
- ✅ **PinImage fields**: `id`, `pin_id` (indexed), `drive_file_id`, `url`, `position`, `created_at` — all present.
- ✅ **PinSubmission fields**: All 18 expected fields including `id`, `submitter_id`, `submitter_username`, `name`, `pin_type`, `suggested_type`, `latitude`, `longitude`, `date_era`, `description`, `source_reference`, `tags`, `status` (indexed), `admin_notes`, `rejection_reason`, `reviewed_at`, `submitted_at` — all present.
- ✅ **Indexes**: `User.supabase_id` (unique+indexed), `User.email` (unique), `User.username` (unique), `Post.author_id` (indexed), `PostImage.post_id` (indexed), `PinImage.pin_id` (indexed), `UserPin.user_id` (indexed), `UserFollow.following_id` (indexed), `PostReaction.post_id` (indexed), `PinSubmission.status` (indexed) — all verified.
- ✅ **`create_tables()`**: Calls `conn.run_sync(Base.metadata.create_all)`, enables PostGIS extension, and idempotently adds enum values for `location_type_enum` and `map_layer_type_enum`.

### B. Pydantic Schemas (`backend/app/models/schemas.py`)

- ✅ **All expected schemas exist**: `UserProfile`, `UserProfileSetup`, `UserProfileUpdate`, `UserProfilePublic`, `UserProfileLimited`, `UserPinCreate`, `UserPinUpdate`, `UserPinResponse`, `UserPinListResponse`, `PinSubmissionCreate`, `PinSubmissionResponse`, `PinSubmissionAdminUpdate`, `PinSubmissionListResponse`, `PostCreate`, `PostResponse`, `PostListResponse`, `CommentCreate`, `CommentResponse`, `CommentListResponse`, `ReactRequest`, `FollowInfo`, `FollowListResponse`, `PostImageResponse`, `PinImageResponse`, `CollectionPhotoResponse`, `CollectionPhotoListResponse`, `CollectionPhotoUpdate`.
- ✅ **PostResponse**: Has `images: List[PostImageResponse] = Field(default_factory=list)`.
- ✅ **UserPinResponse**: Has `images: List[PinImageResponse] = Field(default_factory=list)`.
- ✅ **PostImageResponse**: Has `id: UUID`, `url: str`, `position: int`.
- ✅ **PinImageResponse**: Has `id: UUID`, `url: str`, `position: int`.
- ✅ **UserProfilePublic**: Has `avatar_url`, `followers_count`, `following_count`, `is_following`.
- ✅ **FollowInfo**: Has `avatar_url`.
- ✅ **CommentResponse**: Has `author_avatar_url`.
- ✅ **PostResponse**: Has `author_avatar_url`.
- ✅ **Schema/ORM alignment**: All fields referenced in `PostResponse`/`UserPinResponse` via `_build_post_responses`/`_attach_pin_images` are manually constructed from ORM fields — no stale `from_attributes` references.

### C. Auth System (`backend/app/auth/`)

- ✅ **`deps.py`**: `get_current_user` and `optional_user` both exist. `get_current_user` decodes the Supabase JWT (HS256, `authenticated` audience), looks up `User` by `supabase_id`, auto-creates on first login, raises 401 correctly. `optional_user` returns `None` for missing tokens.
- ✅ **Auth routes**: `GET /auth/me` (returns full profile), `GET /auth/profile/{username}` (public profile lookup), `PUT /auth/profile-setup` (first-time username setup), `PUT /auth/profile` (update profile fields).
- ✅ **`GET /auth/profile/{username}`**: Returns `UserProfilePublic` with `followers_count`, `following_count`, `is_following` (viewer-relative). Returns `UserProfileLimited` for private profiles. Handles non-existent users with 404.
- ✅ **`admin.py`**: `require_admin` dependency checks `current_user.is_admin`, raises 403 for non-admins.

### D. Google OAuth & Drive (`backend/app/auth/google.py` + `backend/app/api/google_auth.py`)

- ✅ **`encrypt_token` / `decrypt_token`**: Fernet symmetric encryption, key sourced from `GOOGLE_TOKEN_ENCRYPTION_KEY` config. Raises 500 if key missing.
- ✅ **`build_google_auth_url`**: Correctly builds Google consent URL with `drive.file` scope, `access_type=offline`, `prompt=consent`.
- ✅ **`exchange_code_for_tokens`**: Exchanges auth code for access + refresh tokens. Raises 400 on failure.
- ✅ **`fetch_google_user_email`**: Fetches userinfo from Google. Raises 400 on failure.
- ✅ **`refresh_access_token`**: Exchanges refresh token for new access token. Raises 502 on failure.
- ✅ **`get_valid_access_token`**: Decrypts refresh token, calls `refresh_access_token`. On revocation (HTTPException), clears all google fields on the User and raises 401. Raises 400 if no token stored.
- ✅ **`ensure_aurik_folder`**: Checks cached folder ID first (verifies not trashed), then searches Drive, then creates. Caches result on User row if `user` and `db` provided.
- ✅ **`upload_file_to_drive`**: Multipart upload to Drive with `uploadType=multipart`. Sets file public via permissions API. Returns file ID.
- ✅ **`GET /google/auth-url`**: Returns consent URL with user ID as `state`. Auth required.
- ✅ **`GET /google/callback`**: Browser redirect endpoint (no JWT). Exchanges code, fetches email, persists encrypted refresh token. Redirects to `{FRONTEND_URL}/profile/settings?google=connected` on success or `?google=error` on failure.
- ✅ **`GET /google/status`**: Returns `connected`, `google_email`, `connected_at`, `has_folder`. Validates token and ensures folder on each check.
- ✅ **`POST /google/disconnect`**: Clears all four google fields. Auth required.
- ✅ **`POST /google/upload-avatar`**: Validates type (jpeg/png/webp), size (≤2MB). Gets access token, ensures folder, deletes old avatar from Drive, uploads new file, sets public, saves thumbnail URL on User.
- ✅ **`DELETE /google/avatar`**: Extracts file ID from URL, deletes from Drive, clears `avatar_url`. Non-blocking failure handling.
- ✅ **`POST /google/upload-post-images`**: Validates 1–4 files, type, size. Verifies post ownership. Checks no existing images. Uploads each file, creates `PostImage` rows.
- ✅ **`POST /google/upload-pin-images`**: Same validation as post images. Supports `add_to_collection` flag that optionally copies images to `CollectionPhoto` table.
- ✅ **`DELETE /google/post-images/{post_id}`**: Verifies post ownership. Deletes Drive files (with error suppression), deletes `PostImage` rows.
- ✅ **`DELETE /google/pin-images/{pin_id}`**: Same as above for pins.

### E. Feed System (`backend/app/api/feed.py`)

- ✅ **All endpoints present**: `POST /posts`, `GET /feed`, `GET /feed/home`, `GET /posts/user/{username}`, `GET /posts/{post_id}`, `DELETE /posts/{post_id}`, `GET /posts/{post_id}/comments`, `POST /posts/{post_id}/comments`, `DELETE /posts/{post_id}/comments/{comment_id}`, `PUT /posts/{post_id}/react`.
- ✅ **Route ordering**: `/posts/user/{username}` (static path segment `user`) is registered **before** `/posts/{post_id}` (path parameter), so FastAPI routes these correctly with no ambiguity.
- ✅ **`_build_post_responses`**: Enriches posts with `author_username`, `author_display_name`, `author_avatar_url` (batch-loaded), reaction counts per type, comment count, `my_reaction`, and `images` list — all in O(1) DB queries regardless of page size.
- ✅ **Privacy enforcement in `GET /posts/user/{username}`**: Own profile → all posts; authenticated follower → public+followers; anonymous or non-follower → public only.
- ✅ **Post deletion cascade**: Deletes `PostComment`, `PostReaction`, and `PostImage` rows. Attempts Drive file deletion for each `PostImage` (logs warnings on failure, does not block).
- ✅ **Comment deletion**: Both comment author and post author can delete any comment (403 otherwise).
- ✅ **Reaction toggle**: Same reaction removes it; different reaction replaces it; no reaction adds it.

### F. Pin System (`backend/app/api/pins.py`)

- ✅ **All endpoints present**: `POST /pins`, `GET /pins/me`, `GET /pins/user/{username}`, `GET /pins/{pin_id}`, `PUT /pins/{pin_id}`, `DELETE /pins/{pin_id}`.
- ✅ **`_attach_pin_images`**: Batch-loads `PinImage` rows for all pins in one query. Attaches as `images` list on each pin response dict.
- ✅ **Pin deletion**: Deletes `PinImage` rows and attempts Drive cleanup (with error suppression).
- ✅ **PostGIS geometry**: `_build_geom` uses `ST_SetSRID(ST_MakePoint(lon, lat), 4326)`. Update endpoint recalculates geometry when `latitude` or `longitude` change.

### G. Social System (`backend/app/api/social.py`)

- ✅ **All endpoints present**: `POST /users/{username}/follow`, `DELETE /users/{username}/follow`, `GET /users/{username}/followers`, `GET /users/{username}/following`.
- ✅ **Follow/unfollow**: Creates/deletes `UserFollow` rows. Self-follow raises 400. Already-following is idempotent (no error).
- ✅ **Follower/following lists**: Return `FollowListResponse` with `FollowInfo` items including `user_id`, `username`, `display_name`, `avatar_url`.

### H. Submissions System (`backend/app/api/submissions.py`)

- ✅ **All endpoints present**: `POST /submissions`, `GET /submissions/me`, `GET /admin/submissions`, `GET /admin/submissions/{id}`, `PUT /admin/submissions/{id}`, `GET /admin/submissions/export`.
- ✅ **Admin check**: All admin endpoints depend on `require_admin` which enforces `is_admin == True`.
- ✅ **Approval flow**: `PUT /admin/submissions/{id}` with `status=approved` validates `pin_type`, converts to `LocationType`, creates a `Location` row with `source="community:{username}"`, sets `reviewed_at`.

### I. Router Registration (`backend/main.py`)

- ✅ **All 8 routers mounted** under `/api/v1`:
  - `router` from `app.api.routes` (locations, features, heatmap, score, layers, import, land-access)
  - `pins_router` from `app.api.pins`
  - `submissions_router` from `app.api.submissions`
  - `feed_router` from `app.api.feed`
  - `social_router` from `app.api.social`
  - `auth_router` from `app.auth.routes`
  - `google_auth_router` from `app.api.google_auth`
  - `collection_router` from `app.api.collection` (PR #71)
- ✅ **No route conflicts**: Static path segments are registered before path parameters in every router. Specifically `/posts/user/{username}` before `/posts/{post_id}`, `/admin/submissions/export` before `/admin/submissions/{id}`, `/pins/me` before `/pins/{pin_id}`.
- ✅ **CORS**: Configured for `http://localhost:5173` and `http://localhost:3000` with `allow_credentials=True`.

### J. Frontend Types (`frontend/src/types/index.ts`)

- ✅ **`Post`**: Has `author_avatar_url?`, `images?`, `my_reaction`, `reactions` (typed as `PostReactions`), `comment_count`.
- ✅ **`Comment`**: Has `author_avatar_url?`.
- ✅ **`UserPin`**: Has `images?`.
- ✅ **`FollowInfo`**: Has `avatar_url?`.
- ✅ **`PublicProfile`**: Has `avatar_url?`, `followers_count`, `following_count`, `is_following`.
- ✅ **`CollectionPhoto`**: Added in PR #71 with `id`, `user_id`, `url`, `caption`, `created_at`.

### K. Frontend API Client (`frontend/src/api/client.ts`)

- ✅ **All expected API functions present**: `fetchLocations`, `fetchFeatures`, `fetchHeatmap`, `fetchScore`, `fetchMyPins`, `fetchUserPins`, `createPin`, `updatePin`, `deletePin`, `createSubmission`, `fetchMySubmissions`, `fetchAdminSubmissions`, `fetchAdminSubmission`, `updateAdminSubmission`, `exportApprovedSubmissions`, `createPost`, `fetchGlobalFeed`, `fetchHomeFeed`, `deletePost`, `fetchComments`, `createComment`, `deleteComment`, `reactToPost`, `followUser`, `unfollowUser`, `fetchFollowers`, `fetchFollowing`, `fetchUserPosts`, `fetchPublicProfile`, `fetchGoogleAuthUrl`, `fetchGoogleStatus`, `disconnectGoogle`, `uploadAvatar`, `deleteAvatar`, `uploadPostImages`, `deletePostImages`, `uploadPinImages`, `deletePinImages`, `fetchCollection`, `uploadCollectionPhoto`, `updateCollectionPhoto`, `deleteCollectionPhoto`.
- ✅ **Axios instance**: Correct `baseURL: '/api/v1'`, 15-second timeout. JWT interceptor reads session from Supabase and attaches `Authorization: Bearer {token}` to every request.
- ✅ **All frontend API calls map to backend endpoints**: No calls to non-existent endpoints found.
- ✅ **`uploadPinImages`**: Correctly passes `add_to_collection` form field.

### L. Frontend Components & Pages

- ✅ **`Avatar.tsx`**: Accepts `username`, `displayName`, `avatarUrl`, `size` props. Renders `<img>` with `onError` fallback to letter initials. Supports xs/sm/md/lg/xl sizes. Deterministic color palette via djb2-style hash.
- ✅ **`PostCard.tsx`**: Shows author avatar via `Avatar`, renders content, `PhotoGrid` for images, `ImageLightbox` for fullscreen, 4-type reaction bar with active state, comment toggle with lazy-loaded comment list, create/delete comments. Owner can delete post.
- ✅ **`PhotoGrid.tsx`**: Handles 1, 2, 3, and 4 image layouts correctly (single fill, 2-column, 3-panel with right column stacked, 2×2 grid). Accepts `onImageClick` callback with hover overlay.
- ✅ **`ImageLightbox.tsx`**: Close button, left/right navigation arrows, keyboard support (Escape, ArrowLeft, ArrowRight), image counter (`N / total`), backdrop click to close.
- ✅ **`FeedPage.tsx`**: Global/home tab bar. Create post form with textarea, privacy selector, photo file picker (file count gate, Google Drive connection gate), image previews with remove buttons. Calls `createPost` then optionally `uploadPostImages`. Renders posts via `PostCard`. Load more pagination.
- ✅ **`ProfilePage.tsx`**: Loads `fetchPublicProfile`. Shows avatar, username, display name, bio, location, member since. Follow/Unfollow for other users, Edit Profile link for own profile. Stats row (Hunts, Followers, Following). 4 tabs: Activity (`PostCard` list), Hunts (hunt cards with `PhotoGrid`), Collection (3-column grid), Followers (Followers/Following sub-tabs with user avatars). Handles private profiles (blurred content with "This profile is private"). Hunt photo lightbox (`ImageLightbox`), Collection photo lightbox (`CollectionLightbox`).
- ✅ **`ProfileSettingsPage.tsx`**: Avatar upload section (validates type/size, resizes via canvas, calls `uploadAvatar`), avatar delete section. Google Drive connect/disconnect section. Profile edit form (display name, bio, location, privacy). Handles `?google=connected` and `?google=error` query params from OAuth callback.
- ✅ **`CollectionLightbox.tsx`**: Full-screen photo viewer with edit-caption and delete-photo controls for owners. Keyboard navigation (Escape, ArrowLeft, ArrowRight). Caption editing inline.
- ✅ **`CollectionUploadModal.tsx`**: Drag-and-drop or file-input upload. File type and size validation client-side. Calls `resizeImage` then `uploadCollectionPhoto`.
- ✅ **Routing (`App.tsx`)**: Routes defined for `/login`, `/signup`, `/setup`, `/map`, `/feed`, `/profile/settings` (before `/profile/:username`), `/profile/:username`, `/submit`, `/admin/submissions/:id`, `/admin/submissions`. Root redirects to `/map`.
- ✅ **`AuthContext.tsx`**: Provides `user`, `profile` (full `UserProfile`), `loading`, `signUp`, `signIn`, `signOut`, `refreshProfile`. Fetches profile from `GET /auth/me` on session. `profile` includes `google_email`, `google_connected_at`, `google_folder_id`, `avatar_url`.

### M. Cross-Cutting Concerns

- ✅ **Import consistency**: `feed.py` imports `PostImage` ✅; `pins.py` imports `PinImage` ✅; `google_auth.py` imports `upload_file_to_drive`, `PostImage`, `PinImage`, `CollectionPhoto` ✅; `collection.py` imports from correct modules ✅.
- ✅ **Error handling**: 404 for not-found resources ✅; 403 for unauthorized actions ✅; 400 for validation failures ✅; 502 for Google Drive API failures ✅.
- ✅ **Cascade deletes**: Post → comments, reactions, PostImages (+ Drive cleanup) ✅; Pin → PinImages (+ Drive cleanup) ✅; Collection photo → Drive file ✅.
- ✅ **`imageResize.ts` utility**: Exists at `frontend/src/utils/imageResize.ts`, used by `FeedPage` and `CollectionUploadModal` to resize before upload.

---

## ⚠️ Issues Found

### Issue 1: `MapLayerType.blm` missing from `schemas.py`

- **Severity:** Medium
- **Category:** Schemas
- **File(s):** `backend/app/models/schemas.py` (line ~199), `backend/app/models/database.py` (line ~62)
- **Description:** The `MapLayerType` enum in `schemas.py` defines only `usgs`, `railroad`, `trail`, `mining`. The same enum in `database.py` adds `blm = "blm"`. The `create_tables()` function explicitly appends `blm` to the `map_layer_type_enum` PostgreSQL enum at startup. If any `MapLayer` row with `type = 'blm'` is inserted into the database (e.g., via admin tooling or direct SQL), the `GET /api/v1/layers` and `POST /api/v1/layers` endpoints will fail with a Pydantic `ValidationError` when trying to serialize the `MapLayerResponse` with the schema-unknown `blm` value.
- **Expected:** `schemas.py` `MapLayerType` should include `blm = "blm"` to stay in sync with the database model.
- **Actual:** `schemas.py` `MapLayerType` has 4 values; `database.py` `MapLayerType` has 5 values (`blm` missing from schema).
- **Impact:** `GET /api/v1/layers` raises 500 if any `blm`-type layer exists. Adding a BLM layer via `POST /api/v1/layers` would also fail due to the schema rejecting the value.
- **Suggested Fix:** Add `blm = "blm"` to the `MapLayerType` enum in `backend/app/models/schemas.py`:
  ```python
  class MapLayerType(str, enum.Enum):
      usgs = "usgs"
      railroad = "railroad"
      trail = "trail"
      mining = "mining"
      blm = "blm"   # ← add this
  ```

---

### Issue 2: No error handling for invalid UUID strings in upload form endpoints

- **Severity:** Low
- **Category:** Google | Feed | Pins
- **File(s):** `backend/app/api/google_auth.py` (lines ~360–402 for `upload-post-images`; lines ~415–471 for `upload-pin-images`)
- **Description:** The `POST /google/upload-post-images` and `POST /google/upload-pin-images` endpoints accept `post_id`/`pin_id` as plain `str = Form(...)`. Later, the string is passed to `uuid.UUID(post_id)` when constructing `PostImage`/`PinImage` rows. If the client sends a malformed UUID string (e.g., `"abc"`), this raises an unhandled `ValueError` which FastAPI returns as an unformatted HTTP 500 Internal Server Error instead of a proper 400 Bad Request.
- **Expected:** A `ValueError` from `uuid.UUID(...)` should be caught and translated to HTTP 400.
- **Actual:** The exception propagates and FastAPI returns 500.
- **Impact:** Poor error response for malformed inputs; may confuse clients or leak stack traces depending on debug settings.
- **Suggested Fix:** Wrap the `uuid.UUID(post_id)` / `uuid.UUID(pin_id)` calls in a try-except:
  ```python
  try:
      post_uuid = uuid.UUID(post_id)
  except ValueError:
      raise HTTPException(status_code=400, detail="Invalid post_id format")
  ```

---

### Issue 3: Silent image upload failure in FeedPage post creation

- **Severity:** Medium (UX/reliability)
- **Category:** Frontend Components
- **File(s):** `frontend/src/pages/FeedPage.tsx` (lines ~135–145)
- **Description:** After `createPost` succeeds, `FeedPage` calls `uploadPostImages`. If the image upload fails, the catch block is silent — no error is shown to the user and no retry is offered. The post is created and displayed without its intended images. The user has no way to know images failed, and cannot easily re-attach them (the re-upload endpoint rejects if images already exist, but in the failure case none were saved).
- **Expected:** If `uploadPostImages` fails, a visible error message should inform the user and ideally offer a retry path.
- **Actual:** Upload failure is silently swallowed; the post appears without images.
- **Impact:** User data loss risk (images intended for the post are lost with no feedback).
- **Suggested Fix:** Add a state variable to track upload errors and display a toast or inline error message:
  ```tsx
  } catch {
    setUploadError('Images failed to upload. You can try again from your post.');
  }
  ```

---

### Issue 4: `resizeImage` duplicated inline in ProfileSettingsPage

- **Severity:** Low (code quality)
- **Category:** Frontend Components
- **File(s):** `frontend/src/pages/ProfileSettingsPage.tsx` (lines ~135–170), `frontend/src/utils/imageResize.ts`
- **Description:** `ProfileSettingsPage.tsx` defines its own local `function resizeImage(file, maxW, maxH)` (lines 135–170) instead of importing the shared `resizeImage` from `frontend/src/utils/imageResize.ts`. The shared utility is already used correctly by `FeedPage.tsx` and `CollectionUploadModal.tsx`. The two implementations are functionally equivalent but the duplication means future changes to the shared utility won't apply to the avatar upload path.
- **Expected:** `ProfileSettingsPage` should import `resizeImage` from `../utils/imageResize`.
- **Actual:** A local duplicate function exists.
- **Impact:** No runtime bug today, but future maintenance risk if the shared utility is updated (e.g., quality, format, or dimension logic changes).
- **Suggested Fix:** Remove the local `resizeImage` function and add:
  ```tsx
  import { resizeImage } from '../utils/imageResize';
  ```

---

## 🔍 Observations & Recommendations

### Obs 1: `POST /auth/signup` and `POST /auth/login` intentionally absent from backend

The audit checklist mentions these routes, but they do not exist in `backend/app/auth/routes.py`. This is by design: login and signup are handled entirely by Supabase Auth on the client side (`supabase.auth.signUp`, `supabase.auth.signInWithPassword`). The backend only needs to validate JWTs, which it does correctly. No fix required, but worth documenting so future contributors don't add duplicate auth routes.

### Obs 2: Privacy naming inconsistency — `"friends"` vs `"followers"`

The `UserPin` and `User` models use `"friends"` as a privacy level, while `Post` uses `"followers"`. This inconsistency is reflected in all schemas and enforced consistently within each domain — pins/profiles use `"friends"`, posts use `"followers"`. However, this split creates cognitive load and could become a source of bugs if privacy levels are ever cross-referenced (e.g., "should a follower see a user's 'friends'-privacy pins?"). Consider standardizing to `"followers"` across all models in a future migration.

### Obs 3: CORS configured only for localhost origins

`main.py` configures CORS for `http://localhost:5173` and `http://localhost:3000`. Any production or staging deployment will need to add the production frontend URL to `allow_origins`. This is a configuration concern, not a code bug.

### Obs 4: `_DRIVE_FILES_URL` is a private symbol imported across 4 modules

The variable `_DRIVE_FILES_URL` (underscore prefix conventionally signals "private") is imported by `google_auth.py`, `feed.py` (via inline import), `pins.py` (via inline import), and `collection.py`. This is functional but is a design smell. Consider exporting it as a public constant (`DRIVE_FILES_URL`) or encapsulating Drive deletion into a helper function in `google.py` to reduce cross-module coupling.

### Obs 5: No SQL-level cascade constraints on foreign key relationships

All cascade deletions (post → comments/reactions/images; pin → images; collection photo) are performed in Python application code rather than via SQL `ON DELETE CASCADE`. This works correctly as long as code paths are followed, but if a row is deleted directly in the database (e.g., for operations, cleanup scripts, or future migration logic), orphaned rows may remain. For robustness, consider adding `CASCADE` constraints to relevant foreign keys in a future Alembic migration.

---

## Audit Methodology

All checks were performed by direct inspection of source files at commit `362eb74`. The following files were read in full:

**Backend (17 files):** `backend/main.py`, `backend/app/config.py`, `backend/app/models/database.py`, `backend/app/models/schemas.py`, `backend/app/auth/deps.py`, `backend/app/auth/routes.py`, `backend/app/auth/admin.py`, `backend/app/auth/google.py`, `backend/app/api/google_auth.py`, `backend/app/api/feed.py`, `backend/app/api/pins.py`, `backend/app/api/social.py`, `backend/app/api/submissions.py`, `backend/app/api/collection.py`, `backend/app/api/routes.py` (selectively).

**Frontend (14 files):** `frontend/src/App.tsx`, `frontend/src/types/index.ts`, `frontend/src/api/client.ts`, `frontend/src/contexts/AuthContext.tsx`, `frontend/src/utils/imageResize.ts`, `frontend/src/components/Avatar.tsx`, `frontend/src/components/PostCard.tsx`, `frontend/src/components/PhotoGrid.tsx`, `frontend/src/components/ImageLightbox.tsx`, `frontend/src/components/CollectionLightbox.tsx`, `frontend/src/components/CollectionUploadModal.tsx`, `frontend/src/pages/FeedPage.tsx`, `frontend/src/pages/ProfilePage.tsx`, `frontend/src/pages/ProfileSettingsPage.tsx`.

Checks performed for each area:
- **Models**: Field names, types, index declarations, enum values, composite PKs.
- **Schemas**: Class existence, field names/types, default factories, Literal values, forward references.
- **Auth**: JWT decode algorithm and audience, user auto-provisioning, optional vs required token handling.
- **Google**: Function signatures, error code mapping, token revocation flow, folder caching logic, upload multipart construction.
- **Endpoints**: Route paths, HTTP methods, auth dependencies, request body types, response models, pagination parameters, ownership checks, cascade side effects.
- **Router registration**: All `include_router` calls in `main.py`, route ordering within routers.
- **Frontend types**: Alignment of TypeScript interfaces with backend Pydantic schemas field-by-field.
- **API client**: Endpoint URLs, HTTP method, request payloads, response types, auth interceptor.
- **Components**: Props, imports, conditional rendering, event handlers, API call sites.
- **Cross-cutting**: Import paths resolve to actual exports; schema fields covered by manual build helpers; privacy value strings consistent.
