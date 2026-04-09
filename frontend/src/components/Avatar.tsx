/**
 * Avatar — deterministic color avatar showing user initials.
 *
 * Props:
 *   username    — used for color selection (always required)
 *   displayName — if provided, first 1-2 initials are taken from this
 *   size        — 'sm' (24px navbar), 'md' (40px lists), 'lg' (64px cards), 'xl' (96px profile)
 */

const PALETTE = [
  'bg-teal-600',
  'bg-indigo-600',
  'bg-rose-600',
  'bg-amber-600',
  'bg-emerald-600',
  'bg-violet-600',
  'bg-sky-600',
  'bg-pink-600',
];

// djb2-inspired polynomial rolling hash — maps a username string to a stable uint32
function hashUsername(username: string): number {
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = (hash * 31 + username.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function getColor(username: string): string {
  return PALETTE[hashUsername(username) % PALETTE.length];
}

function getInitials(username: string, displayName?: string | null): string {
  const source = displayName?.trim() || username;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}

const SIZE_CLASSES: Record<string, string> = {
  sm: 'w-6 h-6 text-[10px]',
  md: 'w-10 h-10 text-sm',
  lg: 'w-16 h-16 text-xl',
  xl: 'w-24 h-24 text-3xl',
};

interface AvatarProps {
  username: string;
  displayName?: string | null;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export default function Avatar({
  username,
  displayName,
  size = 'md',
  className = '',
}: AvatarProps) {
  const color = getColor(username);
  const initials = getInitials(username, displayName);
  const sizeClass = SIZE_CLASSES[size] ?? SIZE_CLASSES.md;

  return (
    <div
      className={`${sizeClass} ${color} rounded-full flex items-center justify-center font-semibold text-white flex-shrink-0 select-none ${className}`}
      aria-label={`Avatar for ${username}`}
    >
      {initials}
    </div>
  );
}
