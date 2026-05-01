import { Lock } from 'lucide-react';

interface LockBadgeProps {
  size?: 'sm' | 'md';
}

export default function LockBadge({ size = 'sm' }: LockBadgeProps) {
  const px = size === 'sm' ? 12 : 16;
  return (
    <Lock
      size={px}
      className="text-stone-500 flex-shrink-0"
      aria-label="Pro feature"
    />
  );
}
