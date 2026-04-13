import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProfileSetupPage from './pages/ProfileSetupPage';
import MapPage from './pages/MapPage';
import ProfilePage from './pages/ProfilePage';
import ProfileSettingsPage from './pages/ProfileSettingsPage';
import SecuritySettingsPage from './pages/SecuritySettingsPage';
import SubmitPinPage from './pages/SubmitPinPage';
import AdminSubmissionsPage from './pages/AdminSubmissionsPage';
import AdminSubmissionReviewPage from './pages/AdminSubmissionReviewPage';
import FeedPage from './pages/FeedPage';
import GroupPage from './pages/GroupPage';
import CreateGroupPage from './pages/CreateGroupPage';
import MyGroupsPage from './pages/MyGroupsPage';
import BadgesPage from './pages/BadgesPage';
import AppLayout from './components/AppLayout';

/**
 * Wraps protected routes so that authenticated users who haven't yet
 * completed profile setup are redirected to /setup.
 * Unauthenticated users are allowed through (individual pages handle their own auth guards).
 */
function RequireProfile({ children }: { children: React.ReactNode }) {
  const { user, profile, loading } = useAuth();
  if (loading) return null;
  // Logged in but no username yet → force profile setup
  if (user && profile !== null && !profile.username) {
    return <Navigate to="/setup" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/setup" element={<AppLayout><ProfileSetupPage /></AppLayout>} />
        <Route path="/map" element={<RequireProfile><MapPage /></RequireProfile>} />
        <Route path="/feed" element={<AppLayout><RequireProfile><FeedPage /></RequireProfile></AppLayout>} />
        {/* /profile/settings must come before /profile/:username so "settings" isn't treated as a username */}
        <Route path="/profile/settings" element={<AppLayout><RequireProfile><ProfileSettingsPage /></RequireProfile></AppLayout>} />
        <Route path="/profile/:username" element={<AppLayout><RequireProfile><ProfilePage /></RequireProfile></AppLayout>} />
        <Route path="/submit" element={<AppLayout><RequireProfile><SubmitPinPage /></RequireProfile></AppLayout>} />
        <Route path="/settings/security" element={<AppLayout><RequireProfile><SecuritySettingsPage /></RequireProfile></AppLayout>} />
        <Route path="/admin/submissions/:id" element={<AppLayout><RequireProfile><AdminSubmissionReviewPage /></RequireProfile></AppLayout>} />
        <Route path="/admin/submissions" element={<AppLayout><RequireProfile><AdminSubmissionsPage /></RequireProfile></AppLayout>} />
        <Route path="/groups/create" element={<AppLayout><RequireProfile><CreateGroupPage /></RequireProfile></AppLayout>} />
        <Route path="/groups" element={<AppLayout><RequireProfile><MyGroupsPage /></RequireProfile></AppLayout>} />
        <Route path="/group/:slug" element={<AppLayout><RequireProfile><GroupPage /></RequireProfile></AppLayout>} />
        <Route path="/badges" element={<AppLayout><RequireProfile><BadgesPage /></RequireProfile></AppLayout>} />
        <Route path="/" element={<Navigate to="/map" replace />} />
      </Routes>
    </AuthProvider>
  );
}
