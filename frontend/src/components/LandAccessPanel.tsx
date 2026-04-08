import { useState } from 'react';
import type { LandAccessResponse, LandAccessStatus } from '../types';

interface LandAccessPanelProps {
  data: LandAccessResponse | null;
  isLoading: boolean;
  isError: boolean;
  onClose: () => void;
  onOverride: (areaCode: string, status: 'allowed' | 'off_limits', notes: string) => void;
}

const STATUS_CONFIG: Record<LandAccessStatus, { emoji: string; label: string; color: string; bg: string }> = {
  allowed:        { emoji: '🟢', label: 'Public — OK to Detect',   color: 'text-green-400',  bg: 'bg-green-900/40' },
  private_permit: { emoji: '🟡', label: 'Private — Permit Required', color: 'text-yellow-400', bg: 'bg-yellow-900/40' },
  off_limits:     { emoji: '🔴', label: 'Off Limits',               color: 'text-red-400',    bg: 'bg-red-900/40' },
  unsure:         { emoji: '🟠', label: 'Unsure — Verify First',    color: 'text-orange-400', bg: 'bg-orange-900/40' },
};

function getStatusConfig(status: LandAccessStatus) {
  return STATUS_CONFIG[status] ?? STATUS_CONFIG.unsure;
}

export default function LandAccessPanel({
  data,
  isLoading,
  isError,
  onClose,
  onOverride,
}: LandAccessPanelProps) {
  const [overrideNotes, setOverrideNotes] = useState('');

  if (isLoading) {
    return (
      <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl w-80 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            📍 Land Access Info
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors" aria-label="Close">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <span className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          Checking land access…
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl w-80 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            📍 Land Access Info
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors" aria-label="Close">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p className="text-sm text-red-400">Unable to retrieve land access data for this location.</p>
      </div>
    );
  }

  const cfg = getStatusConfig(data.status as LandAccessStatus);
  const confidencePct = Math.round(data.confidence * 100);

  return (
    <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl w-80 overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-4 pb-3 border-b border-slate-700/50">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          📍 Land Access Info
        </h3>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors flex-shrink-0" aria-label="Close">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3 custom-scrollbar overflow-y-auto max-h-96">
        {/* Area name */}
        {data.unit_name && (
          <div>
            <span className="text-xs text-slate-500 uppercase tracking-wide">Area</span>
            <p className="text-sm text-white font-medium">{data.unit_name}</p>
          </div>
        )}

        {/* Details grid */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          {data.managing_agency && (
            <div>
              <span className="text-slate-500">Agency</span>
              <p className="text-slate-300">{data.managing_agency}</p>
            </div>
          )}
          {data.designation && (
            <div>
              <span className="text-slate-500">Designation</span>
              <p className="text-slate-300">{data.designation}</p>
            </div>
          )}
          {data.state && (
            <div>
              <span className="text-slate-500">State</span>
              <p className="text-slate-300">{data.state}</p>
            </div>
          )}
          {data.gap_status != null && (
            <div>
              <span className="text-slate-500">GAP Status</span>
              <p className="text-slate-300">{data.gap_status}</p>
            </div>
          )}
        </div>

        {/* Status badge */}
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${cfg.bg}`}>
          <span className="text-lg">{cfg.emoji}</span>
          <div>
            <p className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</p>
            <p className="text-xs text-slate-400">Confidence: {confidencePct}%</p>
          </div>
        </div>

        {/* Area code */}
        <div className="text-xs">
          <span className="text-slate-500">Area Code: </span>
          <span className="text-slate-300 font-mono">{data.area_code}</span>
        </div>

        {/* Reason */}
        {data.reason && (
          <p className="text-xs text-slate-400 leading-relaxed">{data.reason}</p>
        )}

        {/* Metadata */}
        <div className="flex justify-between text-xs text-slate-500">
          {data.last_verified && (
            <span>Verified: {new Date(data.last_verified).toLocaleDateString()}</span>
          )}
          <span>Source: {data.source}</span>
        </div>

        {/* Unsure areas — override buttons */}
        {data.status === 'unsure' && (
          <div className="border-t border-slate-700/50 pt-3 space-y-2">
            <p className="text-xs text-orange-400">
              ⚠️ Rules vary for this type of land. Contact the managing agency before detecting.
            </p>
            <p className="text-xs text-slate-400">🔧 Know the answer? Update this area:</p>
            <input
              type="text"
              placeholder="Notes (e.g. called park office)"
              value={overrideNotes}
              onChange={(e) => setOverrideNotes(e.target.value)}
              className="w-full px-2 py-1.5 text-xs bg-slate-800 border border-slate-600 rounded text-slate-300 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <div className="flex gap-2">
              <button
                onClick={() => onOverride(data.area_code, 'allowed', overrideNotes)}
                className="flex-1 px-2 py-1.5 text-xs font-medium bg-green-900/50 text-green-400 rounded hover:bg-green-900/70 transition-colors"
              >
                ✓ Mark as OK
              </button>
              <button
                onClick={() => onOverride(data.area_code, 'off_limits', overrideNotes)}
                className="flex-1 px-2 py-1.5 text-xs font-medium bg-red-900/50 text-red-400 rounded hover:bg-red-900/70 transition-colors"
              >
                ✕ Mark Off Limits
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
