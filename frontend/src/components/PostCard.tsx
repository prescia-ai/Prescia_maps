import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Avatar from './Avatar';
import PhotoGrid from './PhotoGrid';
import ImageLightbox from './ImageLightbox';
import ProBadge from './ProBadge';
import {
  reactToPost,
  fetchComments,
  createComment,
  deleteComment,
  deletePost,
} from '../api/client';
import type { Post, Comment, ReactionType } from '../types';

interface PostCardProps {
  post: Post;
  onPostDeleted?: (postId: string) => void;
  onPostUpdated?: (post: Post) => void;
}

const REACTIONS: { type: ReactionType; emoji: string; label: string }[] = [
  { type: 'gold', emoji: '🪙', label: 'Great find!' },
  { type: 'bullseye', emoji: '🎯', label: 'Spot on' },
  { type: 'shovel', emoji: '⛏️', label: "I'd dig there" },
  { type: 'fire', emoji: '🔥', label: "That's awesome" },
];

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function PostCard({ post, onPostDeleted, onPostUpdated }: PostCardProps) {
  const { profile } = useAuth();
  const [currentPost, setCurrentPost] = useState<Post>(post);
  const [reactingTo, setReactingTo] = useState<ReactionType | null>(null);
  const [showComments, setShowComments] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsLoaded, setCommentsLoaded] = useState(false);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentInput, setCommentInput] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const isOwner = profile?.id === currentPost.author_id;

  async function handleReact(type: ReactionType) {
    if (!profile) return;
    setReactingTo(type);
    try {
      const updated = await reactToPost(currentPost.id, type);
      setCurrentPost(updated);
      onPostUpdated?.(updated);
    } catch {
      // ignore
    } finally {
      setReactingTo(null);
    }
  }

  async function handleToggleComments() {
    if (!showComments && !commentsLoaded) {
      setCommentsLoading(true);
      try {
        const { comments: loaded } = await fetchComments(currentPost.id);
        setComments(loaded);
        setCommentsLoaded(true);
      } catch {
        // ignore
      } finally {
        setCommentsLoading(false);
      }
    }
    setShowComments((v) => !v);
  }

  async function handleSubmitComment(e: React.FormEvent) {
    e.preventDefault();
    const text = commentInput.trim();
    if (!text || submittingComment) return;
    setSubmittingComment(true);
    try {
      const comment = await createComment(currentPost.id, text);
      setComments((prev) => [...prev, comment]);
      setCurrentPost((p) => ({ ...p, comment_count: p.comment_count + 1 }));
      setCommentInput('');
    } catch {
      // ignore
    } finally {
      setSubmittingComment(false);
    }
  }

  async function handleDeleteComment(commentId: string) {
    try {
      await deleteComment(currentPost.id, commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
      setCurrentPost((p) => ({ ...p, comment_count: Math.max(0, p.comment_count - 1) }));
    } catch {
      // ignore
    }
  }

  async function handleDeletePost() {
    if (!window.confirm('Delete this post?')) return;
    setDeleting(true);
    try {
      await deletePost(currentPost.id);
      onPostDeleted?.(currentPost.id);
    } catch {
      setDeleting(false);
    }
  }

  const displayName =
    currentPost.author_display_name ||
    (currentPost.author_username ? `@${currentPost.author_username}` : 'Unknown');

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-4 space-y-3 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <Avatar
            username={currentPost.author_username ?? 'user'}
            displayName={currentPost.author_display_name}
            avatarUrl={currentPost.author_avatar_url}
            size="sm"
          />
          <div className="min-w-0">
            {currentPost.author_username ? (
              <div className="flex items-center gap-1">
                <Link
                  to={`/profile/${currentPost.author_username}`}
                  className="text-sm font-semibold text-stone-900 hover:text-amber-700 transition-colors truncate"
                >
                  {displayName}
                </Link>
                {currentPost.author_is_pro && <ProBadge size="sm" />}
              </div>
            ) : (
              <span className="text-sm font-semibold text-stone-900 truncate block">{displayName}</span>
            )}
            {currentPost.author_username && (
              <span className="text-xs text-stone-400 truncate block">
                @{currentPost.author_username}
              </span>
            )}
            {currentPost.group_name && currentPost.group_slug && (
              <span className="text-xs text-stone-400 truncate block">
                in{' '}
                <Link
                  to={`/group/${currentPost.group_slug}`}
                  className="text-stone-500 hover:text-stone-700 font-medium"
                >
                  {currentPost.group_name}
                </Link>
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-stone-400">{timeAgo(currentPost.created_at)}</span>
          {isOwner && (
            <button
              onClick={handleDeletePost}
              disabled={deleting}
              className="text-stone-300 hover:text-red-500 transition-colors p-1 rounded"
              title="Delete post"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <p className="text-stone-700 text-sm leading-relaxed whitespace-pre-wrap break-words">
        {currentPost.content}
      </p>

      {/* Photo grid */}
      {currentPost.images && currentPost.images.length > 0 && (
        <PhotoGrid
          images={currentPost.images}
          onImageClick={(idx) => setLightboxIndex(idx)}
        />
      )}

      {/* Lightbox */}
      {lightboxIndex !== null && currentPost.images && currentPost.images.length > 0 && (
        <ImageLightbox
          images={currentPost.images}
          initialIndex={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}

      {/* Reaction bar */}
      <div className="flex items-center gap-1 pt-1">
        {REACTIONS.map(({ type, emoji, label }) => {
          const count = currentPost.reactions[type] ?? 0;
          const isActive = currentPost.my_reaction === type;
          const isLoading = reactingTo === type;
          return (
            <button
              key={type}
              onClick={() => handleReact(type)}
              disabled={!profile || isLoading}
              title={profile ? label : 'Log in to react'}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all ${
                isActive
                  ? 'bg-amber-100 text-amber-700 border border-amber-300'
                  : 'bg-stone-100 text-stone-500 hover:bg-stone-200 hover:text-stone-700 border border-transparent'
              } ${!profile ? 'cursor-default opacity-70' : ''}`}
            >
              <span className={isLoading ? 'animate-bounce' : ''}>{emoji}</span>
              {count > 0 && <span>{count}</span>}
            </button>
          );
        })}

        {/* Comment toggle */}
        <button
          onClick={handleToggleComments}
          className="ml-auto flex items-center gap-1 text-xs text-stone-400 hover:text-stone-700 transition-colors px-2 py-1"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <span>{currentPost.comment_count}</span>
        </button>
      </div>

      {/* Comments section */}
      {showComments && (
        <div className="border-t border-stone-100 pt-3 space-y-3">
          {commentsLoading ? (
            <div className="flex justify-center py-2">
              <div className="w-5 h-5 border-2 border-stone-300 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : comments.length === 0 ? (
            <p className="text-xs text-stone-400 text-center py-1">No comments yet</p>
          ) : (
            <div className="space-y-2">
              {comments.map((c) => (
                <div key={c.id} className="flex items-start gap-2 group">
                  <Avatar
                    username={c.author_username ?? 'user'}
                    displayName={c.author_display_name}
                    avatarUrl={c.author_avatar_url}
                    size="xs"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="bg-stone-50 rounded-xl px-3 py-2">
                      <span className="inline-flex items-center gap-1 mr-1.5">
                        <span className="text-xs font-semibold text-stone-700">
                          {c.author_display_name || (c.author_username ? `@${c.author_username}` : 'User')}
                        </span>
                        {c.author_is_pro && <ProBadge size="sm" />}
                      </span>
                      <span className="text-xs text-stone-600 break-words">{c.content}</span>
                    </div>
                    <span className="text-[10px] text-stone-400 ml-2">{timeAgo(c.created_at)}</span>
                  </div>
                  {(profile?.id === c.author_id || isOwner) && (
                    <button
                      onClick={() => handleDeleteComment(c.id)}
                      className="opacity-0 group-hover:opacity-100 text-stone-300 hover:text-red-500 transition-all p-0.5 flex-shrink-0 mt-1"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Comment input */}
          {profile && (
            <form onSubmit={handleSubmitComment} className="flex items-center gap-2">
              <Avatar username={profile.username ?? 'user'} displayName={profile.display_name} size="xs" />
              <input
                type="text"
                value={commentInput}
                onChange={(e) => setCommentInput(e.target.value)}
                placeholder="Add a comment…"
                maxLength={500}
                className="flex-1 bg-stone-50 border border-stone-200 rounded-xl px-3 py-1.5 text-xs text-stone-900 placeholder-stone-400 focus:outline-none focus:border-stone-400"
              />
              <button
                type="submit"
                disabled={!commentInput.trim() || submittingComment}
                className="text-xs text-amber-700 hover:text-amber-600 disabled:text-stone-300 font-medium transition-colors px-1"
              >
                Post
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
