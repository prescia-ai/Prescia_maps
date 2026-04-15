import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Avatar from '../components/Avatar';
import PostCard from '../components/PostCard';
import PhotoGrid from '../components/PhotoGrid';
import ImageLightbox from '../components/ImageLightbox';
import CollectionLightbox from '../components/CollectionLightbox';
import CollectionUploadModal from '../components/CollectionUploadModal';
import api from '../api/client';
import { fetchMyPins, fetchUserPins, followUser, unfollowUser, fetchFollowers, fetchFollowing, fetchUserPosts, fetchCollection, updateCollectionPhoto, deleteCollectionPhoto, fetchUserBadges, checkBadges } from '../api/client';
import type { UserPin, PublicProfile, Post, FollowInfo, CollectionPhoto, Badge, BadgeCategory } from '../types';
import BadgeDisplay from '../components/BadgeDisplay';

type ActiveTab = 'activity' | 'hunts' | 'collection' | 'followers' | 'badges';
type FollowSubTab = 'followers' | 'following';

function formatMemberSince(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function formatHuntDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

const CATEGORY_LABELS: Record<BadgeCategory, string> = {
  hunt_milestone: 'Hunt Milestones',
  finds: 'Finds',
  sites: 'Historic Sites',
  score: 'Scoring',
  community: 'Community Contribution',
  social: 'Social',
  geographic: 'Geographic',
  treasure_trove: 'Treasure Trove',
};

const CATEGORY_ORDER: BadgeCategory[] = ['hunt_milestone', 'finds', 'treasure_trove', 'sites', 'score', 'community', 'social', 'geographic'];

export default function ProfilePage() {
  const { username } = useParams<{ username: string }>();
  const { profile: myProfile } = useAuth();

  const [publicProfile, setPublicProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>('activity');
  const [pins, setPins] = useState<UserPin[]>([]);
  const [pinsLoading, setPinsLoading] = useState(false);
  const [followLoading, setFollowLoading] = useState(false);
  const [userPosts, setUserPosts] = useState<Post[]>([]);
  const [postsLoading, setPostsLoading] = useState(false);
  const [followersList, setFollowersList] = useState<FollowInfo[]>([]);
  const [followingList, setFollowingList] = useState<FollowInfo[]>([]);
  const [followersLoading, setFollowersLoading] = useState(false);
  const [followSubTab, setFollowSubTab] = useState<FollowSubTab>('followers');
  const [huntLightbox, setHuntLightbox] = useState<{ pin: UserPin; index: number } | null>(null);
  const [collectionPhotos, setCollectionPhotos] = useState<CollectionPhoto[]>([]);
  const [collectionTotal, setCollectionTotal] = useState(0);
  const [collectionLoading, setCollectionLoading] = useState(false);
  const [collectionLightboxIndex, setCollectionLightboxIndex] = useState<number | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [userBadges, setUserBadges] = useState<Badge[]>([]);
  const [badgesLoading, setBadgesLoading] = useState(false);

  const isOwnProfile = myProfile?.username === username;

  useEffect(() => {
    if (!username) return;
    setLoading(true);
    setNotFound(false);

    api
      .get<PublicProfile>(`/auth/profile/${username}`)
      .then(({ data }) => setPublicProfile(data))
      .catch((err) => {
        if (err?.response?.status === 404) setNotFound(true);
      })
      .finally(() => setLoading(false));
  }, [username]);

  // Fetch pins whenever profile loads
  useEffect(() => {
    if (!username) return;
    setPinsLoading(true);
    const fetchFn = isOwnProfile
      ? fetchMyPins()
      : fetchUserPins(username);
    fetchFn
      .then(({ pins: p }) => setPins(p))
      .catch(() => setPins([]))
      .finally(() => setPinsLoading(false));
  }, [username, isOwnProfile]);

  // Silently check badges when viewing own profile
  useEffect(() => {
    if (!isOwnProfile || !username) return;

    checkBadges().catch(() => {
      // Badge check failed, non-fatal - suppress error
    });
  }, [isOwnProfile, username]);

  // Fetch user posts when activity tab is active
  useEffect(() => {
    if (!username || activeTab !== 'activity') return;
    setPostsLoading(true);
    fetchUserPosts(username)
      .then(({ posts }) => setUserPosts(posts))
      .catch(() => setUserPosts([]))
      .finally(() => setPostsLoading(false));
  }, [username, activeTab]);

  // Fetch followers/following when followers tab is active
  useEffect(() => {
    if (!username || activeTab !== 'followers') return;
    setFollowersLoading(true);
    if (followSubTab === 'followers') {
      fetchFollowers(username)
        .then(({ users }) => setFollowersList(users))
        .catch(() => setFollowersList([]))
        .finally(() => setFollowersLoading(false));
    } else {
      fetchFollowing(username)
        .then(({ users }) => setFollowingList(users))
        .catch(() => setFollowingList([]))
        .finally(() => setFollowersLoading(false));
    }
  }, [username, activeTab, followSubTab]);

  // Fetch collection photos when collection tab is active
  useEffect(() => {
    if (!username || activeTab !== 'collection') return;
    setCollectionLoading(true);
    fetchCollection(username)
      .then(({ photos, total }) => {
        setCollectionPhotos(photos);
        setCollectionTotal(total);
      })
      .catch(() => {
        setCollectionPhotos([]);
        setCollectionTotal(0);
      })
      .finally(() => setCollectionLoading(false));
  }, [username, activeTab]);

  // Fetch user badges when badges tab is active
  useEffect(() => {
    if (!username || activeTab !== 'badges') return;
    setBadgesLoading(true);
    fetchUserBadges(username)
      .then((badges) => setUserBadges(badges))
      .catch(() => setUserBadges([]))
      .finally(() => setBadgesLoading(false));
  }, [username, activeTab]);

  async function handleFollow() {
    if (!publicProfile || !username) return;
    setFollowLoading(true);
    try {
      if (publicProfile.is_following) {
        await unfollowUser(username);
        setPublicProfile((p) =>
          p ? { ...p, is_following: false, followers_count: Math.max(0, p.followers_count - 1) } : p,
        );
      } else {
        await followUser(username);
        setPublicProfile((p) =>
          p ? { ...p, is_following: true, followers_count: p.followers_count + 1 } : p,
        );
      }
    } catch {
      // ignore
    } finally {
      setFollowLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (notFound || !publicProfile) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 text-center px-4 py-20">
        <p className="text-4xl">🔍</p>
        <h1 className="text-xl font-semibold text-stone-900">Profile not found</h1>
        <p className="text-stone-500 text-sm">
          @{username} doesn't exist on Aurik yet.
        </p>
      </div>
    );
  }

  const isPrivate = publicProfile.privacy === 'private';

  return (
    <div className="text-stone-900">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* ── Google Drive prompt (own profile, not connected) ─────── */}
        {isOwnProfile && !myProfile?.google_connected_at && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3 flex items-center justify-between gap-3 shadow-sm">
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xl flex-shrink-0">☁️</span>
              <div className="min-w-0">
                <p className="text-amber-900 text-sm font-medium">Connect Google Drive</p>
                <p className="text-amber-700 text-xs">Enable photo uploads for hunt logs and your collection.</p>
              </div>
            </div>
            <Link
              to="/profile/settings#google-drive"
              className="flex-shrink-0 text-xs bg-amber-600 hover:bg-amber-500 text-white px-3 py-1.5 rounded-lg transition-colors font-medium"
            >
              Connect
            </Link>
          </div>
        )}

        {/* ── Profile header ───────────────────────────────────────── */}
        <div className="bg-white border border-stone-200 rounded-3xl p-6 space-y-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <Avatar
                username={publicProfile.username ?? username!}
                displayName={publicProfile.display_name}
                avatarUrl={publicProfile.avatar_url}
                size="xl"
              />
              <div className="min-w-0">
                <h1 className="text-2xl font-bold text-stone-900 truncate">
                  @{publicProfile.username ?? username}
                </h1>
                {publicProfile.display_name && (
                  <p className="flex items-center gap-1.5 text-stone-600 text-base leading-tight mt-0.5">
                    <span className="truncate">{publicProfile.display_name}</span>
                    {publicProfile.is_admin && (
                      <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-md bg-blue-100 text-blue-600 text-[10px] font-semibold tracking-wide">
                        ADMIN
                      </span>
                    )}
                  </p>
                )}
                {!isPrivate && publicProfile.location && (
                  <p className="flex items-center gap-1 text-stone-400 text-sm mt-1">
                    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {publicProfile.location}
                  </p>
                )}
              </div>
            </div>

            {/* Edit button (own profile only) */}
            {isOwnProfile && (
              <Link
                to="/profile/settings"
                className="flex-shrink-0 text-sm text-stone-600 border border-stone-300 hover:border-stone-400 hover:text-stone-900 px-4 py-1.5 rounded-xl transition-colors"
              >
                Edit Profile
              </Link>
            )}

            {/* Follow / Unfollow button (other users' profiles) */}
            {!isOwnProfile && myProfile && (
              <button
                onClick={handleFollow}
                disabled={followLoading}
                className={`flex-shrink-0 text-sm px-4 py-1.5 rounded-xl transition-colors font-medium ${
                  publicProfile?.is_following
                    ? 'text-stone-600 border border-stone-300 hover:border-stone-400 hover:text-stone-900'
                    : 'bg-stone-800 hover:bg-stone-700 text-white'
                }`}
              >
                {followLoading
                  ? '…'
                  : publicProfile?.is_following
                  ? 'Following'
                  : 'Follow'}
              </button>
            )}
          </div>

          {/* Bio */}
          {!isPrivate && publicProfile.bio && (
            <p className="text-stone-600 text-sm leading-relaxed line-clamp-3">
              {publicProfile.bio}
            </p>
          )}

          {/* Member since */}
          {publicProfile.created_at && (
            <p className="text-stone-400 text-xs">
              Member since {formatMemberSince(publicProfile.created_at)}
            </p>
          )}
        </div>

        {/* ── Private profile notice ───────────────────────────────── */}
        {isPrivate && !isOwnProfile && (
          <div className="bg-white border border-stone-200 rounded-3xl p-8 flex flex-col items-center gap-3 text-center shadow-sm">
            <svg className="w-8 h-8 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <p className="text-stone-400 text-sm">This profile is private</p>
          </div>
        )}

        {/* ── Stats row ────────────────────────────────────────────── */}
        {(!isPrivate || isOwnProfile) && (
          <div className="bg-white border border-stone-200 rounded-3xl px-6 py-4 shadow-sm">
            <div className="flex items-center divide-x divide-stone-200">
              {[
                { label: 'Hunts', value: pins.length },
                { label: 'Contributed', value: publicProfile?.contributed_pins_count ?? 0 },
                { label: 'Followers', value: publicProfile?.followers_count ?? 0 },
                { label: 'Following', value: publicProfile?.following_count ?? 0 },
              ].map((stat) => (
                <div key={stat.label} className="flex-1 flex flex-col items-center py-2 first:pl-0 last:pr-0 px-4">
                  <span className="text-2xl font-semibold text-stone-900">{stat.value}</span>
                  <span className="text-xs text-stone-400 mt-0.5">{stat.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Tabs ─────────────────────────────────────────────────── */}
        {(!isPrivate || isOwnProfile) && (
          <div className="space-y-0">
            {/* Tab bar */}
            <div role="tablist" className="flex border-b border-stone-200">
              {(['activity', 'hunts', 'collection', 'badges', 'followers'] as ActiveTab[]).map((tab) => (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={activeTab === tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-3 text-sm font-medium capitalize transition-colors ${
                    activeTab === tab
                      ? 'text-amber-700 border-b-2 border-amber-600 -mb-px'
                      : 'text-stone-500 hover:text-stone-700'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="bg-white border border-t-0 border-stone-200 rounded-b-3xl p-6 min-h-[160px] shadow-sm">
              {activeTab === 'activity' && (
                <div className="flex flex-col gap-4">
                  {postsLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : userPosts.length > 0 ? (
                    <div className="space-y-4">
                      {userPosts.map((post) => (
                        <PostCard
                          key={post.id}
                          post={post}
                          onPostDeleted={(id) => setUserPosts((prev) => prev.filter((p) => p.id !== id))}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                      <svg className="w-8 h-8 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <p className="text-stone-400 text-sm">No posts yet</p>
                      {isOwnProfile && (
                        <Link to="/feed" className="text-amber-700 text-sm hover:text-amber-600 transition-colors">
                          Head to the feed →
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              )}
              {activeTab === 'hunts' && (
                <div className="flex flex-col gap-3">
                  {pinsLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : pins.length > 0 ? (
                    <div className="w-full space-y-3">
                      {pins.map((pin) => (
                        <div key={pin.id} className="bg-stone-50 border border-stone-200 rounded-2xl p-4 space-y-1.5">
                          <div className="flex items-start justify-between gap-2">
                            <h3 className="text-sm font-semibold text-stone-900 leading-tight">{pin.name}</h3>
                            <span className="text-xs text-stone-400 flex-shrink-0">{formatHuntDate(pin.hunt_date)}</span>
                          </div>
                          <div className="flex flex-wrap gap-3 text-xs text-stone-500">
                            {pin.time_spent && (
                              <span className="flex items-center gap-1">
                                <span>⏱</span>
                                <span>{pin.time_spent}</span>
                              </span>
                            )}
                            {pin.finds_count != null && (
                              <span className="flex items-center gap-1">
                                <span>🪙</span>
                                <span>{pin.finds_count} find{pin.finds_count !== 1 ? 's' : ''}</span>
                              </span>
                            )}
                          </div>
                          {pin.notes && (
                            <p className="text-xs text-stone-500 line-clamp-2 leading-relaxed">{pin.notes}</p>
                          )}
                          {pin.images && pin.images.length > 0 && (
                            <div className="pt-1">
                              <PhotoGrid
                                images={pin.images}
                                onImageClick={(idx) => setHuntLightbox({ pin, index: idx })}
                              />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                      <svg className="w-8 h-8 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <p className="text-stone-400 text-sm">No hunts logged yet</p>
                      {isOwnProfile && (
                        <Link to="/map" className="text-amber-700 text-sm hover:text-amber-600 transition-colors">
                          Head to the map →
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              )}
              {activeTab === 'collection' && (
                <div className="flex flex-col gap-4">
                  {/* Upload button — only for own profile */}
                  {isOwnProfile && (
                    <div className="flex justify-end">
                      <button
                        onClick={() => setShowUploadModal(true)}
                        disabled={!myProfile?.google_connected_at}
                        className="flex items-center gap-2 text-sm px-4 py-2 rounded-xl bg-stone-800 hover:bg-stone-700 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title={!myProfile?.google_connected_at ? 'Connect Google Drive in profile settings to upload photos' : 'Add a photo to your collection'}
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                        </svg>
                        Add Photo
                      </button>
                    </div>
                  )}

                  {collectionLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : collectionPhotos.length > 0 ? (
                    <div className="grid grid-cols-3 gap-1">
                      {collectionPhotos.map((photo, index) => (
                        <button
                          key={photo.id}
                          onClick={() => setCollectionLightboxIndex(index)}
                          className="aspect-square overflow-hidden rounded-sm hover:opacity-80 transition-opacity"
                        >
                          <img
                            src={photo.url}
                            alt={photo.caption || 'Collection photo'}
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                      <svg className="w-8 h-8 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 001.5-1.5V5.25a1.5 1.5 0 00-1.5-1.5H3.75a1.5 1.5 0 00-1.5 1.5v14.25a1.5 1.5 0 001.5 1.5z" />
                      </svg>
                      <p className="text-stone-400 text-sm">No photos in collection yet</p>
                      {isOwnProfile && (
                        <p className="text-stone-400 text-xs">
                          Add your best finds to showcase them here
                        </p>
                      )}
                    </div>
                  )}

                  {/* Load more */}
                  {collectionPhotos.length < collectionTotal && !collectionLoading && (
                    <div className="flex justify-center">
                      <button
                        onClick={() => {
                          fetchCollection(username!, 30, collectionPhotos.length)
                            .then(({ photos }) => setCollectionPhotos((prev) => [...prev, ...photos]))
                            .catch(() => {});
                        }}
                        className="text-sm text-amber-700 hover:text-amber-600 transition-colors"
                      >
                        Load more
                      </button>
                    </div>
                  )}
                </div>
              )}
              {activeTab === 'followers' && (
                <div className="flex flex-col gap-4">
                  {/* Sub-tab toggle */}
                  <div className="flex gap-2">
                    {(['followers', 'following'] as FollowSubTab[]).map((sub) => (
                      <button
                        key={sub}
                        onClick={() => setFollowSubTab(sub)}
                        className={`px-4 py-1.5 text-sm font-medium rounded-xl transition-colors ${
                          followSubTab === sub
                            ? 'bg-stone-800 text-white'
                            : 'bg-stone-100 text-stone-500 hover:text-stone-700 hover:bg-stone-200'
                        }`}
                      >
                        {sub.charAt(0).toUpperCase() + sub.slice(1)}
                      </button>
                    ))}
                  </div>

                  {followersLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : (followSubTab === 'followers' ? followersList : followingList).length > 0 ? (
                    <div className="space-y-2">
                      {(followSubTab === 'followers' ? followersList : followingList).filter((user) => user.username).map((user) => (
                        <Link
                          key={user.user_id}
                          to={`/profile/${user.username}`}
                          className="flex items-center gap-3 p-3 rounded-xl hover:bg-stone-50 transition-colors"
                        >
                          <Avatar username={user.username!} displayName={user.display_name} avatarUrl={user.avatar_url} size="sm" />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-stone-900 truncate">@{user.username}</p>
                            {user.display_name && (
                              <p className="text-xs text-stone-400 truncate">{user.display_name}</p>
                            )}
                          </div>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                      <svg className="w-8 h-8 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <p className="text-stone-400 text-sm">
                        {followSubTab === 'followers' ? 'No followers yet' : 'Not following anyone yet'}
                      </p>
                    </div>
                  )}
                </div>
              )}
              {activeTab === 'badges' && (
                <div className="flex flex-col gap-6">
                  {badgesLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : userBadges.length > 0 ? (
                    <div className="space-y-6">
                      {CATEGORY_ORDER.map((category) => {
                        const categoryBadges = userBadges.filter((b) => b.category === category);
                        if (categoryBadges.length === 0) return null;

                        return (
                          <div key={category}>
                            <h3 className="text-stone-700 font-semibold text-sm mb-3">
                              {CATEGORY_LABELS[category]}
                            </h3>
                            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-4">
                              {categoryBadges.map((badge) => (
                                <div key={badge.id} className="flex flex-col items-center gap-2">
                                  <BadgeDisplay badge={badge} earned={true} size="lg" />
                                  <p className="text-stone-700 text-xs font-medium text-center leading-tight truncate max-w-full">
                                    {badge.name}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                      <svg className="w-8 h-8 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                      </svg>
                      <p className="text-stone-400 text-sm">No badges earned yet</p>
                      {isOwnProfile && (
                        <Link to="/badges" className="text-amber-700 text-sm hover:text-amber-600 transition-colors">
                          View all badges →
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Hunt photo lightbox */}
      {huntLightbox && huntLightbox.pin.images && huntLightbox.pin.images.length > 0 && (
        <ImageLightbox
          images={huntLightbox.pin.images}
          initialIndex={huntLightbox.index}
          onClose={() => setHuntLightbox(null)}
        />
      )}

      {/* Collection lightbox */}
      {collectionLightboxIndex !== null && collectionPhotos.length > 0 && (
        <CollectionLightbox
          photos={collectionPhotos}
          initialIndex={collectionLightboxIndex}
          isOwner={isOwnProfile}
          onClose={() => setCollectionLightboxIndex(null)}
          onEdit={async (photoId, newCaption) => {
            try {
              const updated = await updateCollectionPhoto(photoId, newCaption);
              setCollectionPhotos((prev) =>
                prev.map((p) => (p.id === photoId ? updated : p))
              );
            } catch {
              // ignore
            }
          }}
          onDelete={async (photoId) => {
            try {
              await deleteCollectionPhoto(photoId);
              const remaining = collectionPhotos.filter((p) => p.id !== photoId);
              setCollectionPhotos(remaining);
              setCollectionTotal((t) => Math.max(0, t - 1));
              if (remaining.length === 0) {
                setCollectionLightboxIndex(null);
              } else if (collectionLightboxIndex !== null && collectionLightboxIndex >= remaining.length) {
                setCollectionLightboxIndex(remaining.length - 1);
              }
            } catch {
              // ignore
            }
          }}
        />
      )}

      {/* Collection upload modal */}
      {showUploadModal && (
        <CollectionUploadModal
          onClose={() => setShowUploadModal(false)}
          onUploaded={(photo) => {
            setCollectionPhotos((prev) => [photo, ...prev]);
            setCollectionTotal((t) => t + 1);
            setShowUploadModal(false);
          }}
        />
      )}
    </div>
  );
}
