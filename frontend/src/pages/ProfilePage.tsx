import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Avatar from '../components/Avatar';
import PostCard from '../components/PostCard';
import api from '../api/client';
import { fetchMyPins, fetchUserPins, followUser, unfollowUser, fetchFollowers, fetchFollowing, fetchUserPosts } from '../api/client';
import type { UserPin, PublicProfile, Post, FollowInfo } from '../types';

type ActiveTab = 'activity' | 'hunts' | 'followers';
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

export default function ProfilePage() {
  const { username } = useParams<{ username: string }>();
  const { profile: myProfile } = useAuth();
  const navigate = useNavigate();

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
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (notFound || !publicProfile) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center gap-4 text-center px-4">
        <p className="text-4xl">🔍</p>
        <h1 className="text-xl font-semibold text-white">Profile not found</h1>
        <p className="text-slate-400 text-sm">
          @{username} doesn't exist on Prescia Maps yet.
        </p>
        <button
          onClick={() => navigate('/map')}
          className="mt-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
        >
          ← Back to map
        </button>
      </div>
    );
  }

  const isPrivate = publicProfile.privacy === 'private';

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Top nav bar */}
      <div className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm">
        <div className="max-w-2xl mx-auto flex items-center gap-3 px-4 h-12">
          <button
            onClick={() => navigate('/map')}
            className="text-slate-400 hover:text-white transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Map
          </button>
          <span className="text-slate-600">·</span>
          <span className="text-slate-400 text-sm">Profile</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* ── Profile header ───────────────────────────────────────── */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-6 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <Avatar
                username={publicProfile.username ?? username!}
                displayName={publicProfile.display_name}
                avatarUrl={publicProfile.avatar_url}
                size="xl"
              />
              <div className="min-w-0">
                <h1 className="text-2xl font-bold text-white truncate">
                  @{publicProfile.username ?? username}
                </h1>
                {publicProfile.display_name && (
                  <p className="text-slate-300 text-base leading-tight mt-0.5 truncate">
                    {publicProfile.display_name}
                  </p>
                )}
                {!isPrivate && publicProfile.location && (
                  <p className="flex items-center gap-1 text-slate-400 text-sm mt-1">
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
                className="flex-shrink-0 text-sm text-slate-300 border border-slate-700 hover:border-slate-500 hover:text-white px-4 py-1.5 rounded-xl transition-colors"
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
                    ? 'text-slate-300 border border-slate-700 hover:border-slate-500 hover:text-white'
                    : 'bg-amber-500 hover:bg-amber-400 text-black'
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
            <p className="text-slate-300 text-sm leading-relaxed line-clamp-3">
              {publicProfile.bio}
            </p>
          )}

          {/* Member since */}
          {publicProfile.created_at && (
            <p className="text-slate-500 text-xs">
              Member since {formatMemberSince(publicProfile.created_at)}
            </p>
          )}
        </div>

        {/* ── Private profile notice ───────────────────────────────── */}
        {isPrivate && !isOwnProfile && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-8 flex flex-col items-center gap-3 text-center">
            <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <p className="text-slate-400 text-sm">This profile is private</p>
          </div>
        )}

        {/* ── Stats row ────────────────────────────────────────────── */}
        {(!isPrivate || isOwnProfile) && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl px-6 py-4">
            <div className="flex items-center divide-x divide-slate-800">
              {[
                { label: 'Hunts', value: pins.length },
                { label: 'Followers', value: publicProfile?.followers_count ?? 0 },
                { label: 'Following', value: publicProfile?.following_count ?? 0 },
              ].map((stat) => (
                <div key={stat.label} className="flex-1 flex flex-col items-center py-2 first:pl-0 last:pr-0 px-4">
                  <span className="text-2xl font-semibold text-white">{stat.value}</span>
                  <span className="text-xs text-slate-400 mt-0.5">{stat.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Tabs ─────────────────────────────────────────────────── */}
        {(!isPrivate || isOwnProfile) && (
          <div className="space-y-0">
            {/* Tab bar */}
            <div className="flex border-b border-slate-800">
              {(['activity', 'hunts', 'followers'] as ActiveTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-3 text-sm font-medium capitalize transition-colors ${
                    activeTab === tab
                      ? 'text-white border-b-2 border-blue-500 -mb-px'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="bg-slate-900/50 border border-t-0 border-slate-800 rounded-b-3xl p-6 min-h-[160px]">
              {activeTab === 'activity' && (
                <div className="flex flex-col gap-4">
                  {postsLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
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
                      <svg className="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <p className="text-slate-400 text-sm">No posts yet</p>
                      {isOwnProfile && (
                        <Link to="/feed" className="text-blue-400 text-sm hover:text-blue-300 transition-colors">
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
                      <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : pins.length > 0 ? (
                    <div className="w-full space-y-3">
                      {pins.map((pin) => (
                        <div key={pin.id} className="bg-slate-800/60 border border-slate-700 rounded-2xl p-4 space-y-1.5">
                          <div className="flex items-start justify-between gap-2">
                            <h3 className="text-sm font-semibold text-white leading-tight">{pin.name}</h3>
                            <span className="text-xs text-slate-500 flex-shrink-0">{formatHuntDate(pin.hunt_date)}</span>
                          </div>
                          <div className="flex flex-wrap gap-3 text-xs text-slate-400">
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
                            <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">{pin.notes}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                      <svg className="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <p className="text-slate-400 text-sm">No hunts logged yet</p>
                      {isOwnProfile && (
                        <Link to="/map" className="text-blue-400 text-sm hover:text-blue-300 transition-colors">
                          Head to the map →
                        </Link>
                      )}
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
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'
                        }`}
                      >
                        {sub.charAt(0).toUpperCase() + sub.slice(1)}
                      </button>
                    ))}
                  </div>

                  {followersLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : (followSubTab === 'followers' ? followersList : followingList).length > 0 ? (
                    <div className="space-y-2">
                      {(followSubTab === 'followers' ? followersList : followingList).filter((user) => user.username).map((user) => (
                        <Link
                          key={user.user_id}
                          to={`/profile/${user.username}`}
                          className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-800/60 transition-colors"
                        >
                          <Avatar username={user.username!} displayName={user.display_name} avatarUrl={user.avatar_url} size="sm" />
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-white truncate">@{user.username}</p>
                            {user.display_name && (
                              <p className="text-xs text-slate-400 truncate">{user.display_name}</p>
                            )}
                          </div>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                      <svg className="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <p className="text-slate-400 text-sm">
                        {followSubTab === 'followers' ? 'No followers yet' : 'Not following anyone yet'}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
