import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import PostCard from '../components/PostCard';
import Avatar from '../components/Avatar';
import { createPost, fetchGlobalFeed, fetchHomeFeed, uploadPostImages, fetchGoogleStatus } from '../api/client';
import { resizeImage } from '../utils/imageResize';
import type { Post } from '../types';

type FeedTab = 'global' | 'home';

export default function FeedPage() {
  const { user, profile } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<FeedTab>('global');
  const [posts, setPosts] = useState<Post[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const [postContent, setPostContent] = useState('');
  const [postPrivacy, setPostPrivacy] = useState<'public' | 'followers' | 'private'>('public');
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [googleConnected, setGoogleConnected] = useState<boolean | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const PAGE_SIZE = 20;
  const offsetRef = useRef(0);

  const loadFeed = useCallback(
    async (tab: FeedTab, reset: boolean) => {
      if (reset) {
        setLoading(true);
        offsetRef.current = 0;
      } else {
        setLoadingMore(true);
      }

      try {
        const fn = tab === 'home' ? fetchHomeFeed : fetchGlobalFeed;
        const { posts: newPosts, total: t } = await fn(PAGE_SIZE, offsetRef.current);
        setPosts((prev) => (reset ? newPosts : [...prev, ...newPosts]));
        setTotal(t);
        offsetRef.current += newPosts.length;
      } catch (err: any) {
        if (err?.response?.status === 401 && tab === 'home') {
          navigate('/login');
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [navigate],
  );

  useEffect(() => {
    loadFeed(activeTab, true);
  }, [activeTab, loadFeed]);

  // Check Google Drive connection status
  useEffect(() => {
    if (!user) return;
    fetchGoogleStatus()
      .then(({ connected }) => setGoogleConnected(connected))
      .catch(() => setGoogleConnected(false));
  }, [user]);

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    if (selected.length === 0) return;
    const remaining = 4 - pendingFiles.length;
    const toAdd = selected.slice(0, remaining);
    const resized = await Promise.all(toAdd.map((f) => resizeImage(f)));
    setPendingFiles((prev) => [...prev, ...resized]);
    setPreviewUrls((prev) => [...prev, ...resized.map((f) => URL.createObjectURL(f))]);
    // Reset input so same file can be selected again
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function handleRemoveFile(idx: number) {
    URL.revokeObjectURL(previewUrls[idx]);
    setPendingFiles((prev) => prev.filter((_, i) => i !== idx));
    setPreviewUrls((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleCreatePost(e: React.FormEvent) {
    e.preventDefault();
    const content = postContent.trim();
    if (!content || creating) return;
    setCreating(true);
    try {
      const post = await createPost(content, postPrivacy);
      // Upload images if any
      if (pendingFiles.length > 0 && googleConnected) {
        try {
          const { images } = await uploadPostImages(post.id, pendingFiles);
          post.images = images;
        } catch {
          // Image upload failure doesn't block post creation
        }
      }
      setPosts((prev) => [post, ...prev]);
      setTotal((t) => t + 1);
      setPostContent('');
      setShowCreateForm(false);
      previewUrls.forEach((u) => URL.revokeObjectURL(u));
      setPendingFiles([]);
      setPreviewUrls([]);
    } catch {
      // ignore
    } finally {
      setCreating(false);
    }
  }

  function handlePostDeleted(postId: string) {
    setPosts((prev) => prev.filter((p) => p.id !== postId));
    setTotal((t) => Math.max(0, t - 1));
  }

  function handlePostUpdated(updatedPost: Post) {
    setPosts((prev) => prev.map((p) => (p.id === updatedPost.id ? updatedPost : p)));
  }

  const hasMore = posts.length < total;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Top nav */}
      <div className="sticky top-0 z-10 border-b border-slate-800 bg-slate-900/95 backdrop-blur-sm">
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
          <span className="font-semibold text-white text-sm">Community Feed</span>
          <div className="ml-auto flex items-center gap-2">
            {user && (
              <button
                onClick={() => setShowCreateForm((v) => !v)}
                className="flex items-center gap-1 text-xs bg-amber-500 hover:bg-amber-400 text-black font-semibold px-3 py-1.5 rounded-xl transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
                Post
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
        {/* Create post form */}
        {user && showCreateForm && (
          <div className="bg-slate-900/50 border border-slate-700 rounded-2xl p-4">
            <form onSubmit={handleCreatePost} className="space-y-3">
              <div className="flex items-start gap-3">
                <Avatar
                  username={profile?.username ?? user.email ?? 'user'}
                  displayName={profile?.display_name}
                  size="sm"
                />
                <textarea
                  value={postContent}
                  onChange={(e) => setPostContent(e.target.value)}
                  placeholder="Share a find, a spot, or a tip…"
                  maxLength={1000}
                  rows={3}
                  className="flex-1 bg-slate-800/60 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-slate-500 resize-none"
                />
              </div>

              {/* Image previews */}
              {previewUrls.length > 0 && (
                <div className="flex gap-2 pl-9 flex-wrap">
                  {previewUrls.map((url, idx) => (
                    <div key={idx} className="relative w-16 h-16 rounded-lg overflow-hidden flex-shrink-0">
                      <img src={url} alt="" className="w-full h-full object-cover" />
                      <button
                        type="button"
                        onClick={() => handleRemoveFile(idx)}
                        className="absolute top-0.5 right-0.5 bg-black/60 hover:bg-black/80 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px] transition-colors"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between gap-3 pl-9">
                <div className="flex items-center gap-2">
                  <label className="text-xs text-slate-400">Visibility:</label>
                  <select
                    value={postPrivacy}
                    onChange={(e) => setPostPrivacy(e.target.value as typeof postPrivacy)}
                    className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white focus:outline-none"
                  >
                    <option value="public">🌐 Public</option>
                    <option value="followers">👥 Followers</option>
                    <option value="private">🔒 Only me</option>
                  </select>

                  {/* Photo attach button */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                  <button
                    type="button"
                    disabled={pendingFiles.length >= 4 || !googleConnected}
                    title={
                      !googleConnected
                        ? 'Connect Google Drive in profile settings to attach photos'
                        : pendingFiles.length >= 4
                        ? 'Maximum 4 images'
                        : 'Attach photos'
                    }
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 disabled:text-slate-600 disabled:cursor-not-allowed transition-colors px-2 py-1 rounded-lg border border-transparent hover:border-slate-700"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {pendingFiles.length > 0 ? `${pendingFiles.length}/4` : 'Photos'}
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">{postContent.length}/1000</span>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateForm(false);
                      setPostContent('');
                      previewUrls.forEach((u) => URL.revokeObjectURL(u));
                      setPendingFiles([]);
                      setPreviewUrls([]);
                    }}
                    className="text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-xl transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!postContent.trim() || creating}
                    className="text-xs bg-amber-500 hover:bg-amber-400 disabled:bg-slate-700 disabled:text-slate-500 text-black font-semibold px-4 py-1.5 rounded-xl transition-colors"
                  >
                    {creating ? 'Posting…' : 'Post'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        )}

        {/* Tab bar */}
        <div className="flex border-b border-slate-800">
          {(['global', 'home'] as FeedTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => {
                if (tab === 'home' && !user) {
                  navigate('/login');
                  return;
                }
                setActiveTab(tab);
              }}
              className={`flex-1 py-2.5 text-sm font-medium capitalize transition-colors ${
                activeTab === tab
                  ? 'text-white border-b-2 border-amber-400 -mb-px'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab === 'global' ? '🌐 Global' : '🏠 Home'}
            </button>
          ))}
        </div>

        {/* Login prompt for home */}
        {activeTab === 'home' && !user && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-8 flex flex-col items-center gap-3 text-center">
            <span className="text-3xl">🏠</span>
            <p className="text-white font-medium">Your home feed</p>
            <p className="text-slate-400 text-sm">Log in to see posts from people you follow.</p>
            <Link
              to="/login"
              className="mt-1 text-sm bg-amber-500 hover:bg-amber-400 text-black font-semibold px-5 py-2 rounded-xl transition-colors"
            >
              Log in
            </Link>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Empty state */}
        {!loading && posts.length === 0 && (
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-10 flex flex-col items-center gap-3 text-center">
            <span className="text-4xl">⛏️</span>
            <p className="text-white font-medium">No posts yet</p>
            <p className="text-slate-400 text-sm">
              {activeTab === 'home'
                ? 'Follow some detectorists to see their posts here.'
                : 'Be the first to share a find!'}
            </p>
            {user && activeTab === 'global' && (
              <button
                onClick={() => setShowCreateForm(true)}
                className="mt-1 text-sm bg-amber-500 hover:bg-amber-400 text-black font-semibold px-5 py-2 rounded-xl transition-colors"
              >
                Create first post
              </button>
            )}
          </div>
        )}

        {/* Posts list */}
        {!loading && posts.length > 0 && (
          <div className="space-y-3">
            {posts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                onPostDeleted={handlePostDeleted}
                onPostUpdated={handlePostUpdated}
              />
            ))}
          </div>
        )}

        {/* Load more */}
        {hasMore && !loading && (
          <div className="flex justify-center pt-2">
            <button
              onClick={() => loadFeed(activeTab, false)}
              disabled={loadingMore}
              className="text-sm text-slate-400 hover:text-white border border-slate-700 hover:border-slate-500 px-5 py-2 rounded-xl transition-colors"
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
