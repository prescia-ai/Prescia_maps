import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { fetchMyGroups } from '../api/client';
import type { Group } from '../types';

function PrivacyBadge({ privacy }: { privacy: 'public' | 'private' }) {
  if (privacy === 'public') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-600">
        Public
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-stone-100 text-stone-600">
      Private
    </span>
  );
}

function RoleBadge({ role }: { role: string }) {
  if (role === 'owner') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
        Owner
      </span>
    );
  }
  if (role === 'moderator') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-600">
        Moderator
      </span>
    );
  }
  return null;
}

export default function MyGroupsPage() {
  const navigate = useNavigate();
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'My Groups – Prescia Maps';
    fetchMyGroups()
      .then((data: { groups: Group[]; total: number }) => setGroups(data.groups))
      .catch(() => setError('Failed to load groups.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-stone-50 px-4 py-10">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-stone-900">My Groups</h1>
            <p className="text-stone-500 text-sm mt-0.5">Groups you belong to</p>
          </div>
          <button
            onClick={() => navigate('/groups/create')}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-stone-800 hover:bg-stone-700 rounded-xl transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Create Group
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl px-4 py-3 text-sm">{error}</div>
        ) : groups.length === 0 ? (
          <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-10 text-center">
            <div className="text-4xl mb-3">👥</div>
            <h2 className="text-stone-900 font-semibold mb-1">You're not in any groups yet</h2>
            <p className="text-stone-500 text-sm mb-5">Join a community or start your own.</p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={() => navigate('/groups/create')}
                className="px-5 py-2 text-sm font-medium text-white bg-stone-800 hover:bg-stone-700 rounded-xl transition-colors"
              >
                Create a Group
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {groups.map((group) => (
              <Link
                key={group.id}
                to={`/group/${group.slug}`}
                className="block bg-white border border-stone-200 rounded-2xl shadow-sm p-4 hover:border-stone-300 hover:shadow transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-stone-900 truncate">{group.name}</span>
                      <PrivacyBadge privacy={group.privacy} />
                      {group.user_role && <RoleBadge role={group.user_role} />}
                    </div>
                    {group.description && (
                      <p className="text-stone-500 text-sm line-clamp-2">{group.description}</p>
                    )}
                    <p className="text-stone-400 text-xs mt-1.5">
                      {group.member_count} {group.member_count === 1 ? 'member' : 'members'}
                    </p>
                  </div>
                  <svg className="w-4 h-4 text-stone-300 mt-1 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
