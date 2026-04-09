import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProfileSetupPage from './pages/ProfileSetupPage';
import MapPage from './pages/MapPage';
import ProfilePage from './pages/ProfilePage';
import ProfileSettingsPage from './pages/ProfileSettingsPage';
import SubmitPinPage from './pages/SubmitPinPage';
import AdminSubmissionsPage from './pages/AdminSubmissionsPage';
import AdminSubmissionReviewPage from './pages/AdminSubmissionReviewPage';
import FeedPage from './pages/FeedPage';

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/setup" element={<ProfileSetupPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/feed" element={<FeedPage />} />
        {/* /profile/settings must come before /profile/:username so "settings" isn't treated as a username */}
        <Route path="/profile/settings" element={<ProfileSettingsPage />} />
        <Route path="/profile/:username" element={<ProfilePage />} />
        <Route path="/submit" element={<SubmitPinPage />} />
        <Route path="/admin/submissions/:id" element={<AdminSubmissionReviewPage />} />
        <Route path="/admin/submissions" element={<AdminSubmissionsPage />} />
        <Route path="/" element={<Navigate to="/map" replace />} />
      </Routes>
    </AuthProvider>
  );
}
