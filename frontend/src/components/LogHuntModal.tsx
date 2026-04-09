import { useState } from 'react';
import { createPin } from '../api/client';

interface LogHuntModalProps {
  lat: number;
  lon: number;
  onClose: () => void;
  onSuccess: () => void;
}

export default function LogHuntModal({ lat, lon, onClose, onSuccess }: LogHuntModalProps) {
  const today = new Date().toISOString().split('T')[0];

  const [name, setName] = useState('');
  const [latitude, setLatitude] = useState(String(lat));
  const [longitude, setLongitude] = useState(String(lon));
  const [huntDate, setHuntDate] = useState(today);
  const [timeSpent, setTimeSpent] = useState('');
  const [notes, setNotes] = useState('');
  const [findsCount, setFindsCount] = useState('');
  const [privacy, setPrivacy] = useState<'public' | 'private'>('public');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const notesLength = notes.length;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const parsedLat = parseFloat(latitude);
    const parsedLon = parseFloat(longitude);
    if (isNaN(parsedLat) || isNaN(parsedLon)) {
      setError('Invalid latitude or longitude.');
      return;
    }

    setIsSubmitting(true);
    try {
      await createPin({
        name: name.trim(),
        latitude: parsedLat,
        longitude: parsedLon,
        hunt_date: huntDate,
        time_spent: timeSpent.trim() || null,
        notes: notes.trim() || null,
        finds_count: findsCount !== '' ? parseInt(findsCount, 10) : null,
        privacy,
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to log hunt.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-md flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <h2 className="text-white font-semibold text-base">Log Hunt</h2>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {/* Location Name */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Location Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Old Miller Farm"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          {/* Coordinates */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Latitude *</label>
              <input
                type="number"
                required
                step="any"
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Longitude *</label>
              <input
                type="number"
                required
                step="any"
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors font-mono"
              />
            </div>
          </div>

          {/* Date Hunted */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Date Hunted *</label>
            <input
              type="date"
              required
              value={huntDate}
              onChange={(e) => setHuntDate(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          {/* Time Spent & Finds Count */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Time Spent</label>
              <input
                type="text"
                value={timeSpent}
                onChange={(e) => setTimeSpent(e.target.value)}
                placeholder="2 hours"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Finds Count</label>
              <input
                type="number"
                min={0}
                value={findsCount}
                onChange={(e) => setFindsCount(e.target.value)}
                placeholder="0"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>
          </div>

          {/* Notes */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium text-slate-400">Notes</label>
              <span className={`text-xs ${notesLength > 480 ? 'text-amber-400' : 'text-slate-500'}`}>
                {notesLength}/500
              </span>
            </div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
              rows={3}
              placeholder="What did you find?"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors resize-none"
            />
          </div>

          {/* Privacy */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Privacy</label>
            <select
              value={privacy}
              onChange={(e) => setPrivacy(e.target.value as 'public' | 'private')}
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
            >
              <option value="public">Public</option>
              <option value="private">Private</option>
            </select>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2"
          >
            {isSubmitting && (
              <span className="w-3.5 h-3.5 border border-white border-t-transparent rounded-full animate-spin inline-block" />
            )}
            {isSubmitting ? 'Logging…' : 'Log Hunt'}
          </button>
        </div>
      </div>
    </div>
  );
}
