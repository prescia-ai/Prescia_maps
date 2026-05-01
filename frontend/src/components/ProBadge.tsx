interface ProBadgeProps {
  size?: 'sm' | 'md' | 'lg';
}

const SIZE_PX: Record<NonNullable<ProBadgeProps['size']>, number> = {
  sm: 12,
  md: 16,
  lg: 20,
};

export default function ProBadge({ size = 'md' }: ProBadgeProps) {
  const px = SIZE_PX[size];

  return (
    <span
      title="Prescia Pro"
      aria-label="Prescia Pro"
      className="inline-flex items-center flex-shrink-0"
    >
      <svg
        width={px}
        height={px}
        viewBox="0 0 24 24"
        fill="currentColor"
        className="text-amber-500"
        aria-hidden="true"
      >
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
      </svg>
    </span>
  );
}
