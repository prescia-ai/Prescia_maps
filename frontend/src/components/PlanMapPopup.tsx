import { useNavigate } from 'react-router-dom';
import type { HuntPlanMapPin, HuntPlanStatus } from '../types';

const STATUS_COLORS: Record<HuntPlanStatus, string> = {
  idea:     'bg-stone-100 text-stone-600',
  planned:  'bg-blue-100 text-blue-700',
  done:     'bg-green-100 text-green-700',
  archived: 'bg-stone-200 text-stone-500',
};

const SITE_TYPE_LABELS: Record<string, string> = {
  dirt:      'Dirt',
  beach:     'Beach',
  water:     'Water',
  park:      'Park',
  yard:      'Yard',
  club_hunt: 'Club Hunt',
};

function formatPlannedDate(dateStr: string | null): string {
  if (!dateStr) return 'No date set';
  try {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

interface PlanMapPopupProps {
  pin: HuntPlanMapPin;
  onClose?: () => void;
}

export default function PlanMapPopup({ pin, onClose }: PlanMapPopupProps) {
  const navigate = useNavigate();

  return (
    <div className="min-w-[180px] max-w-[220px]">
      <div className="flex items-start justify-between gap-1 mb-1">
        <strong className="text-sm font-semibold text-stone-900 leading-tight">{pin.title}</strong>
        <span
          className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide flex-shrink-0 ${STATUS_COLORS[pin.status]}`}
        >
          {pin.status}
        </span>
      </div>

      {pin.site_type && (
        <p className="text-[11px] text-stone-500 mb-0.5">
          {SITE_TYPE_LABELS[pin.site_type] ?? pin.site_type}
        </p>
      )}

      <p className="text-[11px] text-stone-500 mb-1">
        {formatPlannedDate(pin.planned_date)}
      </p>

      {pin.notes_preview && (
        <p className="text-[11px] text-stone-600 leading-snug mb-1 line-clamp-3">
          {pin.notes_preview}
        </p>
      )}

      <button
        onClick={() => {
          onClose?.();
          navigate(`/plans/${pin.id}`);
        }}
        className="mt-1 w-full py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded-lg transition-colors"
      >
        Open Plan
      </button>
      <button
        onClick={() => {
          onClose?.();
          navigate(`/plans/${pin.id}/edit`);
        }}
        className="mt-1 w-full py-1.5 border border-amber-600 text-amber-700 hover:bg-amber-50 text-xs font-medium rounded-lg transition-colors"
      >
        Edit
      </button>
    </div>
  );
}
