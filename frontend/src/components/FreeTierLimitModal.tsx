import { useNavigate } from 'react-router-dom';

interface FreeTierLimitModalProps {
  open: boolean;
  onClose: () => void;
}

export default function FreeTierLimitModal({ open, onClose }: FreeTierLimitModalProps) {
  const navigate = useNavigate();

  if (!open) return null;

  function handleUpgrade() {
    navigate('/profile/settings/subscription?intent=hunt_logging');
    onClose();
  }

  function handleManageHunts() {
    navigate('/collection');
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-stone-100">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-lg font-bold text-stone-900">
              You've reached your free hunt log limit
            </h2>
            <button
              onClick={onClose}
              className="text-stone-400 hover:text-stone-600 transition-colors mt-0.5 flex-shrink-0"
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-4">
          <p className="text-sm text-stone-600">
            Free accounts can keep up to <strong>5 hunt logs</strong>. Delete an old log to add a
            new one — or upgrade to Pro for unlimited logging plus map pins, planning, and more.
          </p>
        </div>

        {/* CTAs */}
        <div className="px-6 pb-6 flex flex-col gap-2">
          <button
            onClick={handleUpgrade}
            className="w-full bg-amber-600 hover:bg-amber-700 text-white font-medium py-2.5 rounded-xl transition-colors text-sm"
          >
            Upgrade to Pro
          </button>
          <button
            onClick={handleManageHunts}
            className="w-full bg-stone-100 hover:bg-stone-200 text-stone-700 font-medium py-2.5 rounded-xl transition-colors text-sm"
          >
            Manage my hunts
          </button>
          <button
            onClick={onClose}
            className="w-full text-stone-400 hover:text-stone-600 text-sm py-1.5 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
