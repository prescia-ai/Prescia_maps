import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import BadgeDisplay from '../components/BadgeDisplay';
import { fetchMyBadgeProgress, fetchBadges } from '../api/client';
import type { BadgeProgress, Badge } from '../types';

const CATEGORY_LABELS: Record<string, string> = {
  hunt_milestone: '🎯 Hunt Milestones',
  finds: '💎 Finds',
  sites: '🏛️ Historic Sites',
  score: '⭐ Scoring',
};

const CATEGORY_ORDER = ['hunt_milestone', 'finds', 'sites', 'score'];

export default function BadgesPage() {
  const { user } = useAuth();
  const [progress, setProgress] = useState<BadgeProgress[]>([]);
  const [allBadges, setAllBadges] = useState<Badge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        if (user) {
          const data = await fetchMyBadgeProgress();
          setProgress(data);
        } else {
          const data = await fetchBadges();
          setAllBadges(data);
        }
      } catch {
        setError('Failed to load badges. Please try again.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [user]);

  // Group by category
  const grouped: Record<string, BadgeProgress[]> = {};
  const allGrouped: Record<string, Badge[]> = {};

  if (user) {
    for (const item of progress) {
      const cat = item.badge.category;
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(item);
    }
  } else {
    for (const badge of allBadges) {
      const cat = badge.category;
      if (!allGrouped[cat]) allGrouped[cat] = [];
      allGrouped[cat].push(badge);
    }
  }

  const totalEarned = progress.filter((p) => p.earned).length;
  const totalBadges = user ? progress.length : allBadges.length;

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-stone-900">Achievement Badges</h1>
          <p className="text-stone-500 text-sm mt-1">
            Earn badges by logging hunts, recording finds, and visiting historic sites.
          </p>
          {user && !loading && (
            <div className="mt-3 inline-flex items-center gap-2 bg-white border border-stone-200 rounded-xl px-4 py-2 shadow-sm">
              <span className="text-amber-600 font-bold text-lg">{totalEarned}</span>
              <span className="text-stone-400 text-sm">/ {totalBadges} earned</span>
            </div>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <span className="w-6 h-6 border-2 border-stone-400 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-10">
            {CATEGORY_ORDER.map((cat) => {
              if (user) {
                const items = grouped[cat] ?? [];
                if (items.length === 0) return null;
                const earnedInCat = items.filter((i) => i.earned).length;
                return (
                  <section key={cat}>
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-base font-semibold text-stone-700">
                        {CATEGORY_LABELS[cat] ?? cat}
                      </h2>
                      <span className="text-xs text-stone-400 bg-stone-100 px-2 py-0.5 rounded-full">
                        {earnedInCat} / {items.length}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-6">
                      {items.map((item) => (
                        <div key={item.badge.id} className="flex flex-col items-center gap-2">
                          <BadgeDisplay
                            badge={item.badge}
                            earned={item.earned}
                            progress={
                              item.current_value != null
                                ? { current_value: item.current_value, threshold: item.threshold }
                                : null
                            }
                            earnedAt={item.earned_at}
                            size="lg"
                          />
                          <span className="text-[11px] text-stone-500 text-center leading-tight">
                            {item.badge.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  </section>
                );
              } else {
                const items = allGrouped[cat] ?? [];
                if (items.length === 0) return null;
                return (
                  <section key={cat}>
                    <h2 className="text-base font-semibold text-stone-700 mb-4">
                      {CATEGORY_LABELS[cat] ?? cat}
                    </h2>
                    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-6">
                      {items.map((badge) => (
                        <div key={badge.id} className="flex flex-col items-center gap-2">
                          <BadgeDisplay badge={badge} earned={false} size="lg" />
                          <span className="text-[11px] text-stone-500 text-center leading-tight">
                            {badge.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  </section>
                );
              }
            })}
          </div>
        )}

        {!loading && !error && totalBadges === 0 && (
          <div className="text-center py-20 text-stone-400">
            <p className="text-4xl mb-3">🏅</p>
            <p className="text-sm">No badges found. Start logging hunts to earn your first badge!</p>
          </div>
        )}
      </div>
    </div>
  );
}
