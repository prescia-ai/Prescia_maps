import { useNavigate } from 'react-router-dom';

const PRO_FEATURES = [
  'Hunt Planning',
  'Hunt Logging (unlimited + map pins)',
  'Groups & Events',
  'Pin Submissions',
  'All map layers (1955 aerials, BLM/PAD-US, all 27 site types)',
  'Score Engine',
  'Collection',
];

interface PaywallModalProps {
  open: boolean;
  onClose: () => void;
  feature: string;
  description?: string;
}

export default function PaywallModal({ open, onClose, feature, description }: PaywallModalProps) {
  const navigate = useNavigate();

  if (!open) return null;

  function handleUpgrade() {
    const intent = feature.toLowerCase().replace(/\s+/g, '_');
    navigate(`/profile/settings/subscription?intent=${encodeURIComponent(intent)}`);
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
            <div>
              <h2 className="text-lg font-bold text-stone-900">
                {feature} is a Pro feature
              </h2>
              {description && (
                <p className="text-sm text-stone-500 mt-1">{description}</p>
              )}
            </div>
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

        {/* Feature list */}
        <div className="px-6 py-4">
          <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">
            Everything in Pro
          </p>
          <ul className="space-y-1.5">
            {PRO_FEATURES.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-stone-600">
                <svg
                  className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                {f}
              </li>
            ))}
          </ul>
        </div>

        {/* CTAs */}
        <div className="px-6 pb-6 flex flex-col gap-2">
          <button
            onClick={handleUpgrade}
            className="w-full bg-amber-600 hover:bg-amber-700 text-white font-medium py-2.5 rounded-xl transition-colors text-sm"
          >
            Start 7-day free trial
          </button>
          <button
            onClick={onClose}
            className="w-full text-stone-500 hover:text-stone-700 text-sm py-2 transition-colors"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
