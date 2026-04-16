import { useEffect, useRef, useState, useCallback } from 'react';
import { fetchNotifications, markNotificationsRead } from '../api/client';
import type { Notification } from '../types';

const POLL_INTERVAL_MS = 30_000;

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function notificationLabel(type: string): string {
  switch (type) {
    case 'post_like': return '👍 Like';
    case 'post_comment': return '💬 Comment';
    case 'submission_approved': return '✅ Approved';
    case 'badge_earned': return '🏅 Badge';
    case 'group_invite': return '📨 Group Invite';
    case 'group_join': return '🤝 Group Join';
    default: return '🔔 Notification';
  }
}

export default function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const loadNotifications = useCallback(async () => {
    try {
      const result = await fetchNotifications(20, 0);
      setUnreadCount(result.unread_count);
      setNotifications(result.notifications);
    } catch {
      // silently ignore polling errors
    }
  }, []);

  // Initial load + 30-second polling
  useEffect(() => {
    loadNotifications();
    const id = setInterval(loadNotifications, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [loadNotifications]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Close dropdown on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  async function handleMarkOne(notification: Notification) {
    if (notification.read) return;
    try {
      await markNotificationsRead([notification.id]);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notification.id ? { ...n, read: true } : n)),
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // ignore
    }
  }

  async function handleMarkAll() {
    const unreadIds = notifications.filter((n) => !n.read).map((n) => n.id);
    if (unreadIds.length === 0) return;
    try {
      await markNotificationsRead(unreadIds);
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch {
      // ignore
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex items-center justify-center w-8 h-8 rounded-lg text-stone-600 hover:text-stone-900 hover:bg-stone-100 transition-colors"
        aria-label="Notifications"
      >
        {/* Bell icon */}
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* Unread badge */}
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-4 px-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-80 bg-white border border-stone-200 rounded-xl shadow-lg z-50 flex flex-col max-h-96">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-stone-100">
            <span className="text-xs font-semibold text-stone-700">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAll}
                className="text-xs text-amber-700 hover:text-amber-900 font-medium transition-colors"
              >
                Mark all as read
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-stone-400">No notifications yet</div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleMarkOne(n)}
                  className={`w-full text-left flex items-start gap-2.5 px-3 py-2.5 hover:bg-stone-50 transition-colors border-b border-stone-50 last:border-0 ${
                    n.read ? 'opacity-60' : ''
                  }`}
                >
                  {/* Unread indicator */}
                  <span
                    className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      n.read ? 'bg-transparent' : 'bg-red-500'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="text-xs font-medium text-stone-700">{notificationLabel(n.type)}</span>
                    </div>
                    <p className="text-xs text-stone-600 leading-snug truncate">
                      {n.message ??
                        (n.actor_username
                          ? `${n.actor_display_name ?? n.actor_username} triggered a notification`
                          : 'You have a new notification')}
                    </p>
                    <span className="text-[10px] text-stone-400 mt-0.5 block">{formatRelativeTime(n.created_at)}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
