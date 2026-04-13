import { useEffect, useState } from 'react';
import { fetchMyBadgeProgress } from '../api/client';
import type { BadgeProgress, BadgeCategory } from '../types';
import BadgeDisplay from '../components/BadgeDisplay';
import { useAuth } from '../contexts/AuthContext';

const CATEGORY_LABELS: Record<BadgeCategory, string> = {
  hunt_milestone: 'Hunt Milestones',
  finds: 'Finds',
  sites: 'Historic Sites',
  score: 'Scoring',
  community: 'Community Contribution',
  social: 'Social',
  geographic: 'Geographic',
};

const CATEGORY_ORDER: BadgeCategory[] = ['hunt_milestone', 'finds', 'sites', 'score', 'community', 'social', 'geographic'];

export default function BadgesPage() {
  const { user } = useAuth();
  const [progress, setProgress] = useState<BadgeProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    fetchMyBadgeProgress()
      .then(setProgress)
      .catch(() => setError('Failed to load badge progress.'))
      .finally(() => setLoading(false));
  }, [user]);

  const byCategory = CATEGORY_ORDER.reduce<Record<string, BadgeProgress[]>>((acc, cat) => {
    acc[cat] = progress.filter((p) => p.badge.category === cat);
    return acc;
  }, {});

  const totalEarned = progress.filter((p) => p.earned).length;
  const total = progress.length;

  return (
    <div className="min-h-screen bg-stone-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-stone-900 font-bold text-2xl mb-1">Achievement Badges</h1>
          <p className="text-stone-500 text-sm">
            Earn badges by logging hunts, recording finds, and visiting historic sites.
          </p>
          {!loading && total > 0 && (
            <div className="mt-3 inline-flex items-center gap-2 bg-white border border-stone-200 rounded-full px-4 py-1.5">
              <span className="text-stone-900 font-semibold text-sm">{totalEarned}</span>
              <span className="text-stone-400 text-sm">/ {total} earned</span>
              <div className="w-24 h-1.5 bg-stone-100 rounded-full overflow-hidden ml-1">
                <div
                  className="h-full bg-amber-500 rounded-full"
                  style={{ width: total > 0 ? `${Math.round((totalEarned / total) * 100)}%` : '0%' }}
                />
              </div>
            </div>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <span className="w-6 h-6 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-10">
            {CATEGORY_ORDER.map((category) => {
              const items = byCategory[category] ?? [];
              if (items.length === 0) return null;
              const earnedInCategory = items.filter((p) => p.earned).length;

              return (
                <section key={category}>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-stone-800 font-semibold text-base">
                      {CATEGORY_LABELS[category]}
                    </h2>
                    <span className="text-stone-400 text-xs">
                      {earnedInCategory} / {items.length} earned
                    </span>
                  </div>

                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-6">
                    {items.map((item) => (
                      <div key={item.badge.id} className="flex flex-col items-center gap-2">
                        <BadgeDisplay
                          badge={item.badge}
                          earned={item.earned}
                          progress={item}
                          earnedAt={item.earned_at}
                          size="lg"
                        />
                        <div className="text-center">
                          <p className="text-stone-700 text-xs font-medium leading-tight truncate max-w-[5rem]">
                            {item.badge.name}
                          </p>
                          {item.earned ? (
                            <p className="text-green-600 text-[10px]">Earned</p>
                          ) : (
                            <>
                              {(item.badge.criteria?.type === 'hunt_count' || item.badge.criteria?.type === 'finds_count') ? (
                                <p className="text-stone-400 text-[10px]">
                                  {item.current_value} / {item.threshold}
                                </p>
                              ) : (
                                <p className="text-stone-300 text-[10px]">Locked</p>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}

        {!loading && !error && !user && (
          <div className="text-center py-20">
            <p className="text-stone-500 text-sm">Log in to view your badge progress.</p>
          </div>
        )}
      </div>
    </div>
  );
}
