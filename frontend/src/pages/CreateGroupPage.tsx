import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createGroup } from '../api/client';

export default function CreateGroupPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [privacy, setPrivacy] = useState<'public' | 'private'>('public');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'Create Group – Prescia Maps';
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError('Group name is required.');
      return;
    }
    setLoading(true);
    try {
      const group = await createGroup({ name: name.trim(), description: description.trim() || undefined, privacy });
      navigate(`/group/${group.slug}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to create group. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-stone-900">Create a Group</h1>
          <p className="text-stone-500 text-sm mt-1">
            Bring together fellow metal detectorists around a shared interest or location.
          </p>
        </div>

        <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Group Name */}
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5" htmlFor="name">
                Group Name <span className="text-red-500">*</span>
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                placeholder="e.g. Desert Diggers"
                className="w-full border border-stone-200 rounded-xl px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-none focus:border-stone-400 transition-colors"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5" htmlFor="description">
                Description <span className="text-stone-400 font-normal">(optional)</span>
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={1000}
                rows={4}
                placeholder="What is this group about?"
                className="w-full border border-stone-200 rounded-xl px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-none focus:border-stone-400 transition-colors resize-none"
              />
            </div>

            {/* Privacy */}
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5" htmlFor="privacy">
                Privacy
              </label>
              <select
                id="privacy"
                value={privacy}
                onChange={(e) => setPrivacy(e.target.value as 'public' | 'private')}
                className="w-full border border-stone-200 rounded-xl px-3 py-2 text-sm text-stone-900 focus:outline-none focus:border-stone-400 transition-colors bg-white"
              >
                <option value="public">Public — anyone can join</option>
                <option value="private">Private — members require approval</option>
              </select>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
                {error}
              </div>
            )}

            <div className="flex gap-3 pt-1">
              <button
                type="button"
                onClick={() => navigate('/groups')}
                className="flex-1 px-4 py-2 text-sm text-stone-600 border border-stone-200 rounded-xl hover:bg-stone-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-stone-800 hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-colors"
              >
                {loading ? 'Creating…' : 'Create Group'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
