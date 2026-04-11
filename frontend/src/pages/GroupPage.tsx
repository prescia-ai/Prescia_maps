import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Avatar from '../components/Avatar';
import {
  fetchGroup,
  fetchGroupMembers,
  fetchGroupRequests,
  joinGroup,
  leaveGroup,
  updateGroup,
  approveGroupRequest,
  denyGroupRequest,
  kickGroupMember,
  changeGroupMemberRole,
  inviteToGroup,
} from '../api/client';
import type { Group, GroupMember } from '../types';

type ActiveTab = 'feed' | 'members' | 'events';

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
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700 font-medium">
        Owner
      </span>
    );
  }
  if (role === 'moderator') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-600 font-medium">
        Mod
      </span>
    );
  }
  return null;
}

export default function GroupPage() {
  const { slug } = useParams<{ slug: string }>();
  const { profile } = useAuth();
  const navigate = useNavigate();

  const [group, setGroup] = useState<Group | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>('members');

  const [members, setMembers] = useState<GroupMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);

  const [requests, setRequests] = useState<GroupMember[]>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);

  const [actionLoading, setActionLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Edit form state
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editPrivacy, setEditPrivacy] = useState<'public' | 'private'>('public');
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Invite state
  const [inviteUsername, setInviteUsername] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<string | null>(null);

  const isModOrOwner = group?.user_role === 'owner' || group?.user_role === 'moderator';
  const isOwner = group?.user_role === 'owner';

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setNotFound(false);
    fetchGroup(slug)
      .then((data: Group) => {
        setGroup(data);
        setEditName(data.name);
        setEditDescription(data.description ?? '');
        setEditPrivacy(data.privacy);
      })
      .catch((err: any) => {
        if (err?.response?.status === 404) setNotFound(true);
      })
      .finally(() => setLoading(false));
  }, [slug]);

  // Load members when members tab active
  useEffect(() => {
    if (!group || activeTab !== 'members') return;
    setMembersLoading(true);
    fetchGroupMembers(group.slug)
      .then((data: { members: GroupMember[]; total: number }) => setMembers(data.members))
      .catch(() => setMembers([]))
      .finally(() => setMembersLoading(false));
  }, [group, activeTab]);

  // Load requests when settings open and group is private + mod/owner
  useEffect(() => {
    if (!group || !showSettings || !isModOrOwner || group.privacy !== 'private') return;
    setRequestsLoading(true);
    fetchGroupRequests(group.slug)
      .then((data: { members: GroupMember[]; total: number }) => setRequests(data.members))
      .catch(() => setRequests([]))
      .finally(() => setRequestsLoading(false));
  }, [group, showSettings, isModOrOwner]);

  async function handleJoin() {
    if (!group) return;
    setActionLoading(true);
    try {
      await joinGroup(group.slug);
      const updated = await fetchGroup(group.slug);
      setGroup(updated);
    } catch {
      // silent
    } finally {
      setActionLoading(false);
    }
  }

  async function handleLeave() {
    if (!group) return;
    setActionLoading(true);
    try {
      await leaveGroup(group.slug);
      const updated = await fetchGroup(group.slug);
      setGroup(updated);
    } catch {
      // silent
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSaveSettings() {
    if (!group) return;
    setEditLoading(true);
    setEditError(null);
    try {
      const updated: Group = await updateGroup(group.slug, {
        name: editName.trim() || undefined,
        description: editDescription.trim() || undefined,
        privacy: editPrivacy,
      });
      setGroup(updated);
      // If slug changed, navigate to new slug
      if (updated.slug !== group.slug) {
        navigate(`/group/${updated.slug}`, { replace: true });
      }
      setShowSettings(false);
    } catch (err: any) {
      setEditError(err?.response?.data?.detail ?? 'Failed to save settings.');
    } finally {
      setEditLoading(false);
    }
  }

  async function handleApprove(username: string) {
    if (!group) return;
    try {
      await approveGroupRequest(group.slug, username);
      setRequests((prev) => prev.filter((r) => r.username !== username));
      const updated = await fetchGroup(group.slug);
      setGroup(updated);
    } catch {
      // silent
    }
  }

  async function handleDeny(username: string) {
    if (!group) return;
    try {
      await denyGroupRequest(group.slug, username);
      setRequests((prev) => prev.filter((r) => r.username !== username));
    } catch {
      // silent
    }
  }

  async function handleKick(username: string) {
    if (!group) return;
    try {
      await kickGroupMember(group.slug, username);
      setMembers((prev) => prev.filter((m) => m.username !== username));
      const updated = await fetchGroup(group.slug);
      setGroup(updated);
    } catch {
      // silent
    }
  }

  async function handleChangeRole(username: string, role: string) {
    if (!group) return;
    try {
      await changeGroupMemberRole(group.slug, username, role);
      setMembers((prev) =>
        prev.map((m) =>
          m.username === username ? { ...m, role: role as GroupMember['role'] } : m
        )
      );
    } catch {
      // silent
    }
  }

  async function handleInvite() {
    if (!group || !inviteUsername.trim()) return;
    setInviteLoading(true);
    setInviteMessage(null);
    try {
      await inviteToGroup(group.slug, inviteUsername.trim());
      setInviteMessage(`Invited ${inviteUsername.trim()} successfully.`);
      setInviteUsername('');
      const updated = await fetchGroup(group.slug);
      setGroup(updated);
    } catch (err: any) {
      setInviteMessage(err?.response?.data?.detail ?? 'Failed to invite user.');
    } finally {
      setInviteLoading(false);
    }
  }

  // Determine if members tab is accessible (private group members only)
  const canSeeTabs =
    group &&
    (group.privacy === 'public' || group.is_member);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
      </div>
    );
  }

  if (notFound || !group) {
    return (
      <div className="min-h-screen bg-stone-50 flex flex-col items-center justify-center px-4">
        <div className="text-4xl mb-3">🔍</div>
        <h1 className="text-stone-900 font-bold text-xl mb-1">Group not found</h1>
        <p className="text-stone-500 text-sm">This group doesn't exist or has been deleted.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50 px-4 py-10">
      <div className="max-w-2xl mx-auto space-y-4">
        {/* Header Card */}
        <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <h1 className="text-2xl font-bold text-stone-900">{group.name}</h1>
                <PrivacyBadge privacy={group.privacy} />
              </div>
              {group.description && (
                <p className="text-stone-600 text-sm mt-1">{group.description}</p>
              )}
              <p className="text-stone-400 text-sm mt-2">
                {group.member_count} {group.member_count === 1 ? 'member' : 'members'}
              </p>
            </div>

            {/* Action button */}
            <div className="flex-shrink-0 flex gap-2">
              {isModOrOwner && (
                <button
                  onClick={() => setShowSettings((v) => !v)}
                  className="flex items-center justify-center w-8 h-8 text-stone-500 hover:text-stone-800 hover:bg-stone-100 rounded-lg transition-colors"
                  title="Group Settings"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>
              )}

              {!group.is_member && !isModOrOwner && (
                <button
                  onClick={handleJoin}
                  disabled={actionLoading}
                  className="px-4 py-1.5 text-sm font-medium text-white bg-stone-800 hover:bg-stone-700 disabled:opacity-50 rounded-xl transition-colors"
                >
                  {actionLoading ? '…' : group.privacy === 'public' ? 'Join Group' : 'Request to Join'}
                </button>
              )}

              {group.is_member && !isOwner && (
                <button
                  onClick={handleLeave}
                  disabled={actionLoading}
                  className="px-4 py-1.5 text-sm font-medium text-stone-700 border border-stone-300 hover:bg-stone-50 disabled:opacity-50 rounded-xl transition-colors"
                >
                  {actionLoading ? '…' : 'Leave Group'}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && isModOrOwner && (
          <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6 space-y-6">
            <h2 className="text-lg font-semibold text-stone-900">Group Settings</h2>

            {/* Edit group */}
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-stone-700">Edit Group</h3>
              <div>
                <label className="block text-xs text-stone-500 mb-1">Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  maxLength={100}
                  className="w-full border border-stone-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-stone-400 transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs text-stone-500 mb-1">Description</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  maxLength={1000}
                  rows={3}
                  className="w-full border border-stone-200 rounded-xl px-3 py-2 text-sm resize-none focus:outline-none focus:border-stone-400 transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs text-stone-500 mb-1">Privacy</label>
                <select
                  value={editPrivacy}
                  onChange={(e) => setEditPrivacy(e.target.value as 'public' | 'private')}
                  className="w-full border border-stone-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:border-stone-400 transition-colors"
                >
                  <option value="public">Public</option>
                  <option value="private">Private</option>
                </select>
              </div>
              {editError && (
                <p className="text-red-600 text-xs">{editError}</p>
              )}
              <button
                onClick={handleSaveSettings}
                disabled={editLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-stone-800 hover:bg-stone-700 disabled:opacity-50 rounded-xl transition-colors"
              >
                {editLoading ? 'Saving…' : 'Save Changes'}
              </button>
            </div>

            {/* Invite user */}
            <div className="space-y-2 border-t border-stone-100 pt-4">
              <h3 className="text-sm font-medium text-stone-700">Invite a User</h3>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inviteUsername}
                  onChange={(e) => setInviteUsername(e.target.value)}
                  placeholder="Username"
                  className="flex-1 border border-stone-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-stone-400 transition-colors"
                />
                <button
                  onClick={handleInvite}
                  disabled={inviteLoading || !inviteUsername.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-stone-800 hover:bg-stone-700 disabled:opacity-50 rounded-xl transition-colors"
                >
                  {inviteLoading ? '…' : 'Invite'}
                </button>
              </div>
              {inviteMessage && (
                <p className="text-xs text-stone-500">{inviteMessage}</p>
              )}
            </div>

            {/* Pending requests (private groups) */}
            {group.privacy === 'private' && (
              <div className="border-t border-stone-100 pt-4 space-y-2">
                <h3 className="text-sm font-medium text-stone-700">Pending Join Requests</h3>
                {requestsLoading ? (
                  <div className="flex justify-center py-4">
                    <div className="w-4 h-4 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
                  </div>
                ) : requests.length === 0 ? (
                  <p className="text-stone-400 text-sm">No pending requests.</p>
                ) : (
                  <div className="space-y-2">
                    {requests.map((req) => (
                      <div key={String(req.user_id)} className="flex items-center gap-3 py-2">
                        <Avatar
                          username={req.username ?? ''}
                          displayName={req.display_name ?? undefined}
                          avatarUrl={req.avatar_url ?? undefined}
                          size="sm"
                        />
                        <span className="flex-1 text-sm text-stone-800">{req.username}</span>
                        <button
                          onClick={() => req.username && handleApprove(req.username)}
                          className="px-3 py-1 text-xs font-medium text-white bg-stone-800 hover:bg-stone-700 rounded-lg transition-colors"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => req.username && handleDeny(req.username)}
                          className="px-3 py-1 text-xs font-medium text-stone-600 border border-stone-200 hover:bg-stone-50 rounded-lg transition-colors"
                        >
                          Deny
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Manage members */}
            <div className="border-t border-stone-100 pt-4 space-y-2">
              <h3 className="text-sm font-medium text-stone-700">Manage Members</h3>
              {members.length === 0 ? (
                <p className="text-stone-400 text-sm">Load the Members tab first to manage members.</p>
              ) : (
                <div className="space-y-2">
                  {members.map((m) => {
                    const isSelf = m.username === profile?.username;
                    const isTargetOwner = m.role === 'owner';
                    return (
                      <div key={String(m.user_id)} className="flex items-center gap-2 py-1.5">
                        <Avatar
                          username={m.username ?? ''}
                          displayName={m.display_name ?? undefined}
                          avatarUrl={m.avatar_url ?? undefined}
                          size="sm"
                        />
                        <span className="flex-1 text-sm text-stone-800 truncate">{m.username}</span>
                        <RoleBadge role={m.role} />
                        {isOwner && !isTargetOwner && !isSelf && (
                          <>
                            {m.role === 'member' && (
                              <button
                                onClick={() => m.username && handleChangeRole(m.username, 'moderator')}
                                className="px-2 py-1 text-xs text-stone-600 border border-stone-200 hover:bg-stone-50 rounded-lg transition-colors"
                              >
                                Make Mod
                              </button>
                            )}
                            {m.role === 'moderator' && (
                              <button
                                onClick={() => m.username && handleChangeRole(m.username, 'member')}
                                className="px-2 py-1 text-xs text-stone-600 border border-stone-200 hover:bg-stone-50 rounded-lg transition-colors"
                              >
                                Demote
                              </button>
                            )}
                          </>
                        )}
                        {!isTargetOwner && !isSelf && (
                          !(group.user_role === 'moderator' && m.role === 'moderator') && (
                            <button
                              onClick={() => m.username && handleKick(m.username)}
                              className="px-2 py-1 text-xs text-red-600 border border-red-200 hover:bg-red-50 rounded-lg transition-colors"
                            >
                              Kick
                            </button>
                          )
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Private group gate */}
        {group.privacy === 'private' && !group.is_member && (
          <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-8 text-center">
            <div className="text-3xl mb-2">🔒</div>
            <h2 className="text-stone-900 font-semibold mb-1">This is a private group</h2>
            <p className="text-stone-500 text-sm">
              Request to join to see this group's content and members.
            </p>
          </div>
        )}

        {/* Tabs (visible for public groups or members of private groups) */}
        {canSeeTabs && (
          <>
            <div className="flex gap-1 bg-stone-100 rounded-2xl p-1">
              {(['feed', 'members', 'events'] as ActiveTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-1.5 text-xs font-medium rounded-xl capitalize transition-colors ${
                    activeTab === tab
                      ? 'bg-white text-stone-900 shadow-sm'
                      : 'text-stone-500 hover:text-stone-700'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Feed tab */}
            {activeTab === 'feed' && (
              <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-8 text-center">
                <div className="text-3xl mb-2">📰</div>
                <h2 className="text-stone-900 font-semibold mb-1">Group feed coming soon</h2>
                <p className="text-stone-500 text-sm">Posts shared within this group will appear here in a future update.</p>
              </div>
            )}

            {/* Members tab */}
            {activeTab === 'members' && (
              <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-4">
                {membersLoading ? (
                  <div className="flex justify-center py-8">
                    <div className="w-5 h-5 border-2 border-stone-300 border-t-stone-700 rounded-full animate-spin" />
                  </div>
                ) : members.length === 0 ? (
                  <p className="text-stone-400 text-sm text-center py-8">No members found.</p>
                ) : (
                  <div className="divide-y divide-stone-100">
                    {members.map((m) => (
                      <div key={String(m.user_id)} className="flex items-center gap-3 py-3">
                        <Avatar
                          username={m.username ?? ''}
                          displayName={m.display_name ?? undefined}
                          avatarUrl={m.avatar_url ?? undefined}
                          size="sm"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-medium text-stone-800 truncate">{m.username}</span>
                            <RoleBadge role={m.role} />
                          </div>
                          {m.display_name && (
                            <p className="text-xs text-stone-400 truncate">{m.display_name}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Events tab */}
            {activeTab === 'events' && (
              <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-8 text-center">
                <div className="text-3xl mb-2">📅</div>
                <h2 className="text-stone-900 font-semibold mb-1">Group events coming soon</h2>
                <p className="text-stone-500 text-sm">Hunt events organized by this group will appear here in a future update.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
