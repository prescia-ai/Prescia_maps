import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LogHuntModal from './LogHuntModal';
import LockBadge from './LockBadge';
import PaywallModal from './PaywallModal';
import { useAuth } from '../contexts/AuthContext';

type Tab = 'log_hunt' | 'plan_hunt';

interface MapContextMenuProps {
  lat: number;
  lon: number;
  onClose: () => void;
  onHuntSuccess: () => void;
  /** Session-scoped last-used tab, persisted by parent */
  initialTab?: Tab;
  onTabChange?: (tab: Tab) => void;
}

export default function MapContextMenu({
  lat,
  lon,
  onClose,
  onHuntSuccess,
  initialTab = 'log_hunt',
  onTabChange,
}: MapContextMenuProps) {
  const navigate = useNavigate();
  const { isPro, pinCount } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [showPlanPaywall, setShowPlanPaywall] = useState(false);

  // Plan-a-Hunt stub form
  const [planTitle, setPlanTitle] = useState('');
  const [planDate, setPlanDate] = useState('');
  const [planNotes, setPlanNotes] = useState('');

  function selectTab(tab: Tab) {
    if (tab === 'plan_hunt' && !isPro) {
      setShowPlanPaywall(true);
      return;
    }
    setActiveTab(tab);
    onTabChange?.(tab);
  }

  function handleContinueToDraw() {
    onClose();
    const params = new URLSearchParams({ lat: String(lat), lng: String(lon) });
    if (planTitle) params.set('title', planTitle);
    navigate(`/plans/create?${params.toString()}`);
  }

  return (
    <>
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex border-b border-stone-200">
          <button
            onClick={() => selectTab('log_hunt')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'log_hunt'
                ? 'text-stone-900 border-b-2 border-amber-600'
                : 'text-stone-500 hover:text-stone-700'
            }`}
          >
            Log Hunt
            {!isPro && pinCount !== null && (
              <span className="text-xs text-stone-400 font-normal">
                {pinCount}/5
              </span>
            )}
          </button>
          <button
            onClick={() => selectTab('plan_hunt')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'plan_hunt'
                ? 'text-stone-900 border-b-2 border-amber-600'
                : 'text-stone-500 hover:text-stone-700'
            }`}
          >
            Plan a Hunt
            {!isPro && <LockBadge />}
          </button>
          <button
            onClick={onClose}
            className="px-3 py-3 text-stone-400 hover:text-stone-600 transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tab content */}
        {activeTab === 'log_hunt' ? (
          <LogHuntModal
            lat={lat}
            lon={lon}
            onClose={onClose}
            onSuccess={() => {
              onHuntSuccess();
              onClose();
            }}
            embedded
          />
        ) : (
          <div className="p-5 space-y-4">
            <div>
              <p className="text-xs text-stone-500 mb-4">
                Plan a future hunt at{' '}
                <span className="font-mono text-stone-700">
                  {lat.toFixed(5)}, {lon.toFixed(5)}
                </span>
              </p>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">Title</label>
                  <input
                    type="text"
                    value={planTitle}
                    onChange={(e) => setPlanTitle(e.target.value)}
                    placeholder="Name this hunt location…"
                    className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-stone-400"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">
                    Planned Date (optional)
                  </label>
                  <input
                    type="date"
                    value={planDate}
                    onChange={(e) => setPlanDate(e.target.value)}
                    className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-stone-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-stone-700 mb-1">
                    Notes (optional)
                  </label>
                  <textarea
                    value={planNotes}
                    onChange={(e) => setPlanNotes(e.target.value)}
                    rows={2}
                    placeholder="Quick notes…"
                    className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-stone-400 resize-none"
                  />
                </div>
              </div>
            </div>

            <button
              onClick={handleContinueToDraw}
              className="w-full py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
              Continue to draw zone
            </button>
          </div>
        )}
      </div>
    </div>

    <PaywallModal
      open={showPlanPaywall}
      onClose={() => setShowPlanPaywall(false)}
      feature="Hunt Planning"
      description="Plan future hunts on the map, draw zones, and track planned locations."
    />
    </>
  );
}
