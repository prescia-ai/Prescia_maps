import type { Badge } from '../types';

const RARITY_BORDER: Record<string, string> = {
  common: 'ring-stone-300',
  uncommon: 'ring-green-400',
  rare: 'ring-blue-400',
  epic: 'ring-purple-500',
  legendary: 'ring-amber-400',
};

const RARITY_GLOW: Record<string, string> = {
  common: '',
  uncommon: 'shadow-green-200',
  rare: 'shadow-blue-200',
  epic: 'shadow-purple-200',
  legendary: 'shadow-amber-200',
};

const RARITY_LABEL: Record<string, string> = {
  common: 'text-stone-500',
  uncommon: 'text-green-600',
  rare: 'text-blue-600',
  epic: 'text-purple-600',
  legendary: 'text-amber-600',
};

const SIZE_MAP = {
  sm: 'w-12 h-12',
  md: 'w-16 h-16',
  lg: 'w-24 h-24',
};

interface BadgeDisplayProps {
  badge: Badge;
  earned?: boolean;
  progress?: { current_value: number | null; threshold: number | null } | null;
  earnedAt?: string | null;
  size?: 'sm' | 'md' | 'lg';
}

export default function BadgeDisplay({
  badge,
  earned = false,
  progress = null,
  earnedAt = null,
  size = 'md',
}: BadgeDisplayProps) {
  const borderClass = RARITY_BORDER[badge.rarity] ?? 'ring-stone-300';
  const glowClass = earned ? (RARITY_GLOW[badge.rarity] ?? '') : '';
  const sizeClass = SIZE_MAP[size] ?? SIZE_MAP.md;

  const hasProgress =
    !earned &&
    progress?.current_value != null &&
    progress?.threshold != null &&
    progress.threshold > 0;
  const progressPct = hasProgress
    ? Math.min(100, Math.round(((progress!.current_value ?? 0) / (progress!.threshold ?? 1)) * 100))
    : 0;

  function formatDate(dateStr: string | null) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  return (
    <div className="group relative flex flex-col items-center gap-1">
      {/* Badge image */}
      <div
        className={`
          ${sizeClass} rounded-full ring-2 ${borderClass}
          ${glowClass && `shadow-lg ${glowClass}`}
          overflow-hidden flex-shrink-0 relative
          transition-transform duration-150 group-hover:scale-105
        `}
      >
        <img
          src={badge.image_url}
          alt={badge.name}
          className={`w-full h-full object-cover ${!earned ? 'grayscale opacity-40' : ''}`}
          draggable={false}
        />
      </div>

      {/* Progress bar (unearned badges with numeric criteria) */}
      {hasProgress && size !== 'sm' && (
        <div className="w-full max-w-[4rem] h-1 bg-stone-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-500 rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      )}

      {/* Tooltip */}
      <div
        className="
          absolute bottom-full mb-2 left-1/2 -translate-x-1/2
          w-52 bg-white border border-stone-200 rounded-xl shadow-xl
          p-3 z-50 pointer-events-none
          opacity-0 group-hover:opacity-100
          transition-opacity duration-150
        "
      >
        <p className={`text-xs font-semibold capitalize ${RARITY_LABEL[badge.rarity] ?? 'text-stone-600'}`}>
          {badge.rarity}
        </p>
        <p className="text-sm font-bold text-stone-900 mt-0.5">{badge.name}</p>
        {badge.description && (
          <p className="text-xs text-stone-500 mt-1 leading-snug">{badge.description}</p>
        )}
        <p className="text-xs text-amber-600 font-medium mt-1.5">+{badge.points} pts</p>
        {earned && earnedAt && (
          <p className="text-xs text-stone-400 mt-1">Earned {formatDate(earnedAt)}</p>
        )}
        {hasProgress && (
          <div className="mt-2">
            <div className="flex justify-between text-[10px] text-stone-400 mb-0.5">
              <span>Progress</span>
              <span>{progress!.current_value} / {progress!.threshold}</span>
            </div>
            <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded-full"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
