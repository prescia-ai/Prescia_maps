import { useState, useEffect } from 'react';
import { createGroupEvent, updateGroupEvent } from '../api/client';
import type { GroupEvent } from '../types';

interface CreateEventModalProps {
  groupSlug: string;
  event?: GroupEvent;
  onClose: () => void;
  onSuccess: () => void;
}

function toDatetimeLocal(isoString: string | null): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return '';
  }
}

export default function CreateEventModal({ groupSlug, event, onClose, onSuccess }: CreateEventModalProps) {
  const isEdit = !!event;

  const [name, setName] = useState(event?.name ?? '');
  const [description, setDescription] = useState(event?.description ?? '');
  const [eventDate, setEventDate] = useState(toDatetimeLocal(event?.event_date ?? null));
  const [eventEndDate, setEventEndDate] = useState(toDatetimeLocal(event?.event_end_date ?? null));
  const [latitude, setLatitude] = useState(event ? String(event.latitude) : '');
  const [longitude, setLongitude] = useState(event ? String(event.longitude) : '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Event name is required.');
      return;
    }
    if (!eventDate) {
      setError('Start date & time is required.');
      return;
    }
    if (!latitude || !longitude) {
      setError('Latitude and longitude are required.');
      return;
    }
    const lat = parseFloat(latitude);
    const lon = parseFloat(longitude);
    if (isNaN(lat) || isNaN(lon)) {
      setError('Latitude and longitude must be valid numbers.');
      return;
    }
    if (eventEndDate && eventEndDate < eventDate) {
      setError('End date cannot be before start date.');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        latitude: lat,
        longitude: lon,
        event_date: new Date(eventDate).toISOString(),
        event_end_date: eventEndDate ? new Date(eventEndDate).toISOString() : undefined,
      };

      if (isEdit && event) {
        await updateGroupEvent(groupSlug, event.id, payload);
      } else {
        await createGroupEvent(groupSlug, payload);
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-stone-100">
          <h2 className="text-base font-semibold text-stone-900">
            {isEdit ? 'Edit Event' : 'Create Event'}
          </h2>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-stone-700 transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* Event Name */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Event Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
              required
              className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm text-stone-700 focus:outline-none focus:border-stone-500 transition-colors"
              placeholder="Name your event"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={2000}
              rows={3}
              className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm text-stone-700 focus:outline-none focus:border-stone-500 transition-colors resize-none"
              placeholder="Optional description"
            />
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Start Date &amp; Time</label>
              <input
                type="datetime-local"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
                required
                className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm text-stone-700 focus:outline-none focus:border-stone-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">End Date &amp; Time (optional)</label>
              <input
                type="datetime-local"
                value={eventEndDate}
                onChange={(e) => setEventEndDate(e.target.value)}
                min={eventDate || undefined}
                className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm text-stone-700 focus:outline-none focus:border-stone-500 transition-colors"
              />
            </div>
          </div>

          {/* Coordinates */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Latitude</label>
              <input
                type="number"
                step="any"
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                required
                className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm text-stone-700 focus:outline-none focus:border-stone-500 transition-colors"
                placeholder="e.g. 39.7392"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1">Longitude</label>
              <input
                type="number"
                step="any"
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                required
                className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm text-stone-700 focus:outline-none focus:border-stone-500 transition-colors"
                placeholder="e.g. -104.9903"
              />
            </div>
          </div>
          <p className="text-xs text-stone-400 -mt-2">Tip: Right-click on the map to get coordinates</p>

          {/* Error */}
          {error && (
            <p className="text-red-500 text-sm">{error}</p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-60 text-white py-2.5 rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {loading && (
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            )}
            {isEdit ? 'Save Changes' : 'Create Event'}
          </button>
        </form>
      </div>
    </div>
  );
}
