import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../lib/supabase';
import { deleteAccount } from '../api/client';

export default function SecuritySettingsPage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const navigate = useNavigate();

  // Change email
  const [newEmail, setNewEmail] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailSuccess, setEmailSuccess] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);

  // Change password
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  // Delete account
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Redirect if not logged in
  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, user, navigate]);

  if (authLoading || !user) return null;

  async function handleUpdateEmail(e: React.FormEvent) {
    e.preventDefault();
    setEmailError(null);
    setEmailSuccess(false);
    setEmailLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ email: newEmail });
      if (error) throw error;
      setEmailSuccess(true);
      setNewEmail('');
    } catch (err: any) {
      setEmailError(err.message ?? 'Failed to update email');
    } finally {
      setEmailLoading(false);
    }
  }

  async function handleUpdatePassword(e: React.FormEvent) {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(false);
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match');
      return;
    }
    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters');
      return;
    }
    setPasswordLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw error;
      setPasswordSuccess(true);
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordError(err.message ?? 'Failed to update password');
    } finally {
      setPasswordLoading(false);
    }
  }

  async function handleDeleteAccount() {
    const confirmed = window.confirm(
      'Are you sure? This will permanently delete your account and all your data. This cannot be undone.'
    );
    if (!confirmed) return;
    setDeleteError(null);
    setDeleteLoading(true);
    try {
      await deleteAccount();
      await signOut();
      navigate('/login', { replace: true });
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Failed to delete account';
      setDeleteError(msg);
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      {/* Top nav */}
      <div className="sticky top-0 z-10 border-b border-stone-200 bg-white shadow-sm">
        <div className="max-w-2xl mx-auto flex items-center gap-3 px-4 h-12">
          <button
            onClick={() => navigate(-1)}
            className="text-stone-500 hover:text-stone-900 transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>
          <span className="text-stone-300">·</span>
          <span className="font-semibold text-stone-900 text-sm">Account Security</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        {/* Change Email */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm">
          <h2 className="text-stone-900 font-semibold text-base mb-1">Change Email</h2>
          <p className="text-stone-500 text-sm mb-4">
            Your current email is <span className="font-medium text-stone-700">{user.email}</span>.
            A confirmation link will be sent to your new email.
          </p>

          {emailSuccess && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-green-50 border border-green-200 text-green-700 text-sm">
              Check your new email for a confirmation link.
            </div>
          )}
          {emailError && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {emailError}
            </div>
          )}

          <form onSubmit={handleUpdateEmail} className="space-y-3">
            <div>
              <label className="block text-stone-600 text-sm mb-1" htmlFor="newEmail">
                New Email Address
              </label>
              <input
                id="newEmail"
                type="email"
                required
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
                placeholder="new@email.com"
              />
            </div>
            <button
              type="submit"
              disabled={emailLoading}
              className="bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-white font-semibold py-2 px-5 rounded-xl transition-colors text-sm"
            >
              {emailLoading ? 'Sending…' : 'Update Email'}
            </button>
          </form>
        </div>

        {/* Reset Password */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm">
          <h2 className="text-stone-900 font-semibold text-base mb-1">Reset Password</h2>
          <p className="text-stone-500 text-sm mb-4">
            Choose a new password for your account.
          </p>

          {passwordSuccess && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-green-50 border border-green-200 text-green-700 text-sm">
              Password updated successfully.
            </div>
          )}
          {passwordError && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {passwordError}
            </div>
          )}

          <form onSubmit={handleUpdatePassword} className="space-y-3">
            <div>
              <label className="block text-stone-600 text-sm mb-1" htmlFor="newPassword">
                New Password
              </label>
              <input
                id="newPassword"
                type="password"
                required
                minLength={6}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
                placeholder="At least 6 characters"
              />
            </div>
            <div>
              <label className="block text-stone-600 text-sm mb-1" htmlFor="confirmPassword">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
                placeholder="Repeat new password"
              />
            </div>
            <button
              type="submit"
              disabled={passwordLoading}
              className="bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-white font-semibold py-2 px-5 rounded-xl transition-colors text-sm"
            >
              {passwordLoading ? 'Updating…' : 'Update Password'}
            </button>
          </form>
        </div>

        {/* Danger Zone */}
        <div className="bg-white border border-red-200 rounded-2xl p-6 shadow-sm">
          <h2 className="text-red-700 font-semibold text-base mb-1">Danger Zone</h2>
          <p className="text-stone-500 text-sm mb-4">
            Permanently delete your account and all associated data. This action cannot be undone.
          </p>

          {deleteError && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {deleteError}
            </div>
          )}

          <button
            onClick={handleDeleteAccount}
            disabled={deleteLoading}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-semibold py-2 px-5 rounded-xl transition-colors text-sm"
          >
            {deleteLoading ? 'Deleting…' : 'Delete Account'}
          </button>
        </div>
      </div>
    </div>
  );
}
