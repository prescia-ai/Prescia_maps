import { useState } from 'react';
import type { Badge, BadgeProgress } from '../types';

interface BadgeDisplayProps {
  badge: Badge;
  earned?: boolean;
  progress?: BadgeProgress | null;
  earnedAt?: string | null;
  size?: 'sm' | 'md' | 'lg';
}

const RARITY_BORDER: Record<string, string> = {
  common: 'border-stone-400',
  uncommon: 'border-green-500',
  rare: 'border-blue-500',
  epic: 'border-purple-500',
  legendary: 'border-amber-400',
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

const SIZE_CLASS: Record<string, string> = {
  sm: 'w-12 h-12',
  md: 'w-16 h-16',
  lg: 'w-24 h-24',
};

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export default function BadgeDisplay({
  badge,
  earned = false,
  progress = null,
  earnedAt = null,
  size = 'md',
}: BadgeDisplayProps) {
  const [hovered, setHovered] = useState(false);

  const borderClass = RARITY_BORDER[badge.rarity] ?? RARITY_BORDER.common;
  const glowClass = earned ? (RARITY_GLOW[badge.rarity] ?? '') : '';
  const sizeClass = SIZE_CLASS[size] ?? SIZE_CLASS.md;
  const rarityLabelClass = RARITY_LABEL[badge.rarity] ?? RARITY_LABEL.common;

  const threshold = progress?.threshold ?? null;
  const currentValue = progress?.current_value ?? 0;
  const progressPct = progress?.progress_pct ?? (earned ? 100 : 0);

  return (
    <div
      className="relative flex flex-col items-center"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Badge image */}
      <div
        className={`${sizeClass} rounded-xl border-2 ${borderClass} ${glowClass} ${glowClass ? 'shadow-md' : ''} overflow-hidden flex items-center justify-center bg-stone-100 transition-transform duration-150 ${hovered ? 'scale-105' : ''}`}
        style={!earned ? { filter: 'grayscale(100%)', opacity: 0.4 } : undefined}
      >
        <img
          src={badge.image_url}
          alt={badge.name}
          className="w-full h-full object-cover"
          draggable={false}
        />
      </div>

      {/* Tooltip */}
      {hovered && (
        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 z-50 w-52 bg-white border border-stone-200 rounded-xl shadow-lg p-3 pointer-events-none">
          <div className="flex items-center justify-between mb-1">
            <span className="text-stone-900 font-semibold text-xs leading-tight">{badge.name}</span>
            <span className={`text-[10px] font-medium capitalize ${rarityLabelClass}`}>{badge.rarity}</span>
          </div>
          <p className="text-stone-500 text-[11px] leading-snug mb-2">{badge.description}</p>
          <div className="flex items-center justify-between text-[10px] text-stone-400 mb-2">
            <span>+{badge.points} pts</span>
            {earned && earnedAt && (
              <span className="text-green-600">Earned {formatDate(earnedAt)}</span>
            )}
          </div>
          {!earned && threshold !== null && threshold > 0 && (
            <div>
              <div className="flex justify-between text-[10px] text-stone-400 mb-0.5">
                <span>Progress</span>
                <span>{currentValue} / {threshold}</span>
              </div>
              <div className="w-full h-1.5 bg-stone-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-500 rounded-full transition-all duration-300"
                  style={{ width: `${Math.min(progressPct, 100)}%` }}
                />
              </div>
            </div>
          )}
          {!earned && (threshold === null || threshold === 0) && (
            <p className="text-[10px] text-stone-400 italic">Not yet unlocked</p>
          )}
          {/* Tooltip arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-white" />
        </div>
      )}
    </div>
  );
}
