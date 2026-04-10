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
        <Route path="/setup" element={<ProfileSetupPage />} />
        <Route path="/map" element={<RequireProfile><MapPage /></RequireProfile>} />
        <Route path="/feed" element={<RequireProfile><FeedPage /></RequireProfile>} />
        {/* /profile/settings must come before /profile/:username so "settings" isn't treated as a username */}
        <Route path="/profile/settings" element={<RequireProfile><ProfileSettingsPage /></RequireProfile>} />
        <Route path="/profile/:username" element={<RequireProfile><ProfilePage /></RequireProfile>} />
        <Route path="/submit" element={<RequireProfile><SubmitPinPage /></RequireProfile>} />
        <Route path="/settings/security" element={<RequireProfile><SecuritySettingsPage /></RequireProfile>} />
        <Route path="/admin/submissions/:id" element={<RequireProfile><AdminSubmissionReviewPage /></RequireProfile>} />
        <Route path="/admin/submissions" element={<RequireProfile><AdminSubmissionsPage /></RequireProfile>} />
        <Route path="/" element={<Navigate to="/map" replace />} />
      </Routes>
    </AuthProvider>
  );
}
