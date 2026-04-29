import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { createSubmission } from '../api/client';

const LOCATION_TYPES = [
  'battle',
  'town',
  'mine',
  'camp',
  'railroad_stop',
  'trail',
  'structure',
  'event',
  'church',
  'stagecoach_stop',
  'locale',
  'trading_post',
  'pony_express',
  'abandoned_church',
  'abandoned_fairground',
  'historic_brothel',
];

const DESC_MAX = 500;

export default function SubmitPinPage() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [pinType, setPinType] = useState('');
  const [suggestedType, setSuggestedType] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [dateEra, setDateEra] = useState('');
  const [description, setDescription] = useState('');
  const [sourceReference, setSourceReference] = useState('');
  const [tags, setTags] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user === null) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, user, navigate]);

  const isOtherType = pinType === '__other__';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const lat = parseFloat(latitude);
    const lon = parseFloat(longitude);
    if (isNaN(lat) || lat < -90 || lat > 90) {
      setError('Latitude must be between -90 and 90.');
      return;
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      setError('Longitude must be between -180 and 180.');
      return;
    }

    setSubmitting(true);
    try {
      await createSubmission({
        name,
        pin_type: isOtherType ? null : pinType || null,
        suggested_type: isOtherType ? suggestedType || null : null,
        latitude: lat,
        longitude: lon,
        date_era: dateEra || null,
        description: description || null,
        source_reference: sourceReference || null,
        tags: tags || null,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Submission failed. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 flex flex-col items-center text-center gap-6">
        <div className="w-16 h-16 bg-green-100 border border-green-200 rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <h2 className="text-xl font-semibold text-stone-900 mb-2">Submitted!</h2>
          <p className="text-stone-500 text-sm leading-relaxed max-w-sm">
            Your pin has been submitted! We'll review it and add it to the map if approved.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-stone-900 mb-1">Submit a Historical Pin</h1>
      <p className="text-stone-500 text-sm mb-6">
        Know a spot that should be on the map? Submit it for review.
      </p>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="bg-white border border-stone-200 rounded-3xl p-6 space-y-5 shadow-sm">

            {/* Location Name */}
            <div className="space-y-1.5">
              <label htmlFor="name" className="block text-sm font-medium text-stone-700">
                Location Name <span className="text-red-500">*</span>
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value.slice(0, 200))}
                required
                maxLength={200}
                placeholder="e.g. Miller's Crossing Battleground"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
              />
            </div>

            {/* Pin Type */}
            <div className="space-y-1.5">
              <label htmlFor="pinType" className="block text-sm font-medium text-stone-700">
                Pin Type
              </label>
              <select
                id="pinType"
                value={pinType}
                onChange={(e) => setPinType(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 text-sm focus:outline-none focus:border-stone-400 transition-colors"
              >
                <option value="">-- Select a type --</option>
                {LOCATION_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </option>
                ))}
                <option value="__other__">Other / Suggest New Type</option>
              </select>
            </div>

            {/* Suggested type (shown when Other selected) */}
            {isOtherType && (
              <div className="space-y-1.5">
                <label htmlFor="suggestedType" className="block text-sm font-medium text-stone-700">
                  Suggested Type Name
                </label>
                <input
                  id="suggestedType"
                  type="text"
                  value={suggestedType}
                  onChange={(e) => setSuggestedType(e.target.value.slice(0, 100))}
                  maxLength={100}
                  placeholder="e.g. tavern, fort, powder house"
                  className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
                />
              </div>
            )}

            {/* Coordinates */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="latitude" className="block text-sm font-medium text-stone-700">
                  Latitude <span className="text-red-500">*</span>
                </label>
                <input
                  id="latitude"
                  type="number"
                  step="any"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  required
                  placeholder="e.g. 38.8977"
                  className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="longitude" className="block text-sm font-medium text-stone-700">
                  Longitude <span className="text-red-500">*</span>
                </label>
                <input
                  id="longitude"
                  type="number"
                  step="any"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  required
                  placeholder="e.g. -77.0365"
                  className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
                />
              </div>
            </div>
            <p className="text-xs text-stone-400 -mt-2">
              💡 Tip: Note coordinates from the map page first
            </p>

            {/* Date / Era */}
            <div className="space-y-1.5">
              <label htmlFor="dateEra" className="block text-sm font-medium text-stone-700">
                Date / Era
              </label>
              <input
                id="dateEra"
                type="text"
                value={dateEra}
                onChange={(e) => setDateEra(e.target.value.slice(0, 100))}
                maxLength={100}
                placeholder="e.g. 1840s, Civil War, 1860-1870"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
              />
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="description" className="block text-sm font-medium text-stone-700">
                  Description
                </label>
                <span className={`text-xs ${description.length > DESC_MAX * 0.9 ? 'text-amber-600' : 'text-stone-400'}`}>
                  {description.length}/{DESC_MAX}
                </span>
              </div>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value.slice(0, DESC_MAX))}
                rows={4}
                placeholder="Describe the historical significance of this location..."
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors resize-none"
              />
            </div>

            {/* Source / Reference */}
            <div className="space-y-1.5">
              <label htmlFor="sourceReference" className="block text-sm font-medium text-stone-700">
                Source / Reference
              </label>
              <input
                id="sourceReference"
                type="text"
                value={sourceReference}
                onChange={(e) => setSourceReference(e.target.value)}
                placeholder="URL, book, county records, etc."
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
              />
            </div>

            {/* Tags */}
            <div className="space-y-1.5">
              <label htmlFor="tags" className="block text-sm font-medium text-stone-700">
                Tags
              </label>
              <input
                id="tags"
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="comma-separated tags"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 rounded-2xl transition-colors flex items-center justify-center gap-2 text-sm"
          >
            {submitting ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Submitting…
              </>
            ) : (
              'Submit for Review'
            )}
          </button>

          <div className="text-center">
            <Link to="/map" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">
              Cancel
            </Link>
          </div>
        </form>
    </div>
  );
}
