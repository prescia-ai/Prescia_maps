import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import PostCard from '../components/PostCard';
import Avatar from '../components/Avatar';
import { createPost, fetchGlobalFeed, uploadPostImages, fetchGoogleStatus } from '../api/client';
import { resizeImage } from '../utils/imageResize';
import type { Post } from '../types';

export default function FeedPage() {
  const { user, profile } = useAuth();
  const navigate = useNavigate();

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
  const [imageUploadError, setImageUploadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const PAGE_SIZE = 20;
  const offsetRef = useRef(0);

  const loadFeed = useCallback(
    async (reset: boolean) => {
      if (reset) {
        setLoading(true);
        offsetRef.current = 0;
      } else {
        setLoadingMore(true);
      }

      try {
        const { posts: newPosts, total: t } = await fetchGlobalFeed(PAGE_SIZE, offsetRef.current);
        setPosts((prev) => (reset ? newPosts : [...prev, ...newPosts]));
        setTotal(t);
        offsetRef.current += newPosts.length;
      } catch {
        // ignore
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadFeed(true);
  }, [loadFeed]);

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
          setImageUploadError(null);
        } catch {
          setImageUploadError('Photos failed to upload. Your post was created without images.');
          setTimeout(() => setImageUploadError(null), 8000);
        }
      }
      setPosts((prev) => [post, ...prev]);
      setTotal((t) => t + 1);
      setPostContent('');
      setShowCreateForm(false);
      setCreateError(null);
      setImageUploadError(null);
      previewUrls.forEach((u) => URL.revokeObjectURL(u));
      setPendingFiles([]);
      setPreviewUrls([]);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Failed to create post. Please try again.';
      setCreateError(msg);
      console.error('Create post failed:', err);
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
    <div className="min-h-screen bg-stone-50 text-stone-900">
      {/* Top nav */}
      <div className="sticky top-0 z-10 border-b border-stone-200 bg-white shadow-sm">
        <div className="max-w-2xl mx-auto flex items-center gap-3 px-4 h-12">
          <button
            onClick={() => navigate('/map')}
            className="text-stone-500 hover:text-stone-900 transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Map
          </button>
          <span className="text-stone-300">·</span>
          <span className="font-semibold text-stone-900 text-sm">Community Feed</span>
          <div className="ml-auto flex items-center gap-2">
            {user && (
              <button
                onClick={() => {
                  setShowCreateForm((v) => !v);
                  setCreateError(null);
                }}
                className="flex items-center gap-1 text-xs bg-stone-800 hover:bg-stone-700 text-white font-semibold px-3 py-1.5 rounded-xl transition-colors"
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
          <div className="bg-white border border-stone-200 rounded-2xl p-4 shadow-sm">
            <form onSubmit={handleCreatePost} className="space-y-3">
              {createError && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-red-700 text-sm">
                  {createError}
                </div>
              )}
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
                  className="flex-1 bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-none focus:border-stone-400 resize-none"
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
                  <label className="text-xs text-stone-500">Visibility:</label>
                  <select
                    value={postPrivacy}
                    onChange={(e) => setPostPrivacy(e.target.value as typeof postPrivacy)}
                    className="bg-white border border-stone-200 rounded-lg px-2 py-1 text-xs text-stone-700 focus:outline-none"
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
                    className="flex items-center gap-1 text-xs text-stone-500 hover:text-stone-800 disabled:text-stone-300 disabled:cursor-not-allowed transition-colors px-2 py-1 rounded-lg border border-transparent hover:border-stone-200"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {pendingFiles.length > 0 ? `${pendingFiles.length}/4` : 'Photos'}
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-stone-400">{postContent.length}/1000</span>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateForm(false);
                      setPostContent('');
                      previewUrls.forEach((u) => URL.revokeObjectURL(u));
                      setPendingFiles([]);
                      setPreviewUrls([]);
                    }}
                    className="text-xs text-stone-500 hover:text-stone-800 px-3 py-1.5 rounded-xl transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!postContent.trim() || creating}
                    className="text-xs bg-stone-800 hover:bg-stone-700 disabled:bg-stone-200 disabled:text-stone-400 text-white font-semibold px-4 py-1.5 rounded-xl transition-colors"
                  >
                    {creating ? 'Posting…' : 'Post'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        )}

        {/* Image upload error banner */}
        {imageUploadError && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3 text-amber-800 text-sm flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <span>{imageUploadError}</span>
            </div>
            <button
              onClick={() => setImageUploadError(null)}
              className="text-amber-600 hover:text-amber-800 text-xs ml-2 flex-shrink-0"
            >
              ✕
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Empty state */}
        {!loading && posts.length === 0 && (
          <div className="bg-white border border-stone-200 rounded-2xl p-10 flex flex-col items-center gap-3 text-center shadow-sm">
            <span className="text-4xl">⛏️</span>
            <p className="text-stone-900 font-medium">No posts yet</p>
            <p className="text-stone-500 text-sm">Be the first to share a find!</p>
            {user && (
              <button
                onClick={() => setShowCreateForm(true)}
                className="mt-1 text-sm bg-stone-800 hover:bg-stone-700 text-white font-semibold px-5 py-2 rounded-xl transition-colors"
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
              onClick={() => loadFeed(false)}
              disabled={loadingMore}
              className="text-sm text-stone-600 hover:text-stone-900 border border-stone-300 hover:border-stone-400 px-5 py-2 rounded-xl transition-colors"
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
