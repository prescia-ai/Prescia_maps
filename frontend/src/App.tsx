import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProfileSetupPage from './pages/ProfileSetupPage';
import MapPage from './pages/MapPage';
import ProfilePage from './pages/ProfilePage';
import ProfileSettingsPage from './pages/ProfileSettingsPage';
import SecuritySettingsPage from './pages/SecuritySettingsPage';
import SubscriptionSettingsPage from './pages/SubscriptionSettingsPage';
import SubmitPinPage from './pages/SubmitPinPage';
import AdminSubmissionsPage from './pages/AdminSubmissionsPage';
import AdminSubmissionReviewPage from './pages/AdminSubmissionReviewPage';
import FeedPage from './pages/FeedPage';
import GroupPage from './pages/GroupPage';
import CreateGroupPage from './pages/CreateGroupPage';
import MyGroupsPage from './pages/MyGroupsPage';
import BadgesPage from './pages/BadgesPage';
import AppLayout from './components/AppLayout';
import MyPlansPage from './pages/MyPlansPage';
import CreatePlanPage from './pages/CreatePlanPage';
import PlanDetailPage from './pages/PlanDetailPage';
import { useParams } from 'react-router-dom';

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

/**
 * Redirects free-tier users to the subscription settings page with an
 * intent query parameter so the page can show a contextual upgrade message.
 * Pro users and admins pass through normally.
 */
function RequireSubscription({
  tier = "pro",
  intent,
  children,
}: {
  tier?: "pro";
  intent: string;
  children: React.ReactNode;
}) {
  const { isPro, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  void tier;
  if (!isPro) {
    const params = new URLSearchParams({ intent });
    return <Navigate to={`/profile/settings/subscription?${params.toString()}`} replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

function EditPlanPageWrapper() {
  const { id } = useParams<{ id: string }>();
  return <CreatePlanPage planId={id} />;
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
        <Route path="/profile/settings/subscription" element={<AppLayout><RequireProfile><SubscriptionSettingsPage /></RequireProfile></AppLayout>} />
        <Route path="/profile/settings" element={<AppLayout><RequireProfile><ProfileSettingsPage /></RequireProfile></AppLayout>} />
        <Route path="/profile/:username" element={<AppLayout><RequireProfile><ProfilePage /></RequireProfile></AppLayout>} />
        <Route path="/submit" element={<AppLayout><RequireProfile><RequireSubscription tier="pro" intent="submit"><SubmitPinPage /></RequireSubscription></RequireProfile></AppLayout>} />
        <Route path="/settings/security" element={<AppLayout><RequireProfile><SecuritySettingsPage /></RequireProfile></AppLayout>} />
        <Route path="/admin/submissions/:id" element={<AppLayout><RequireProfile><AdminSubmissionReviewPage /></RequireProfile></AppLayout>} />
        <Route path="/admin/submissions" element={<AppLayout><RequireProfile><AdminSubmissionsPage /></RequireProfile></AppLayout>} />
        <Route path="/groups/create" element={<AppLayout><RequireProfile><RequireSubscription tier="pro" intent="groups"><CreateGroupPage /></RequireSubscription></RequireProfile></AppLayout>} />
        <Route path="/groups" element={<AppLayout><RequireProfile><RequireSubscription tier="pro" intent="groups"><MyGroupsPage /></RequireSubscription></RequireProfile></AppLayout>} />
        <Route path="/group/:slug" element={<AppLayout><RequireProfile><RequireSubscription tier="pro" intent="groups"><GroupPage /></RequireSubscription></RequireProfile></AppLayout>} />
        <Route path="/badges" element={<AppLayout><RequireProfile><BadgesPage /></RequireProfile></AppLayout>} />
        {/* Hunt Plans routes — Pro only */}
        <Route path="/plans/create" element={<RequireProfile><RequireSubscription tier="pro" intent="plans"><CreatePlanPage /></RequireSubscription></RequireProfile>} />
        <Route path="/plans/:id/edit" element={<RequireProfile><RequireSubscription tier="pro" intent="plans"><EditPlanPageWrapper /></RequireSubscription></RequireProfile>} />
        <Route path="/plans/:id" element={<RequireProfile><RequireSubscription tier="pro" intent="plans"><PlanDetailPage /></RequireSubscription></RequireProfile>} />
        <Route path="/plans" element={<RequireProfile><RequireSubscription tier="pro" intent="plans"><MyPlansPage /></RequireSubscription></RequireProfile>} />
        <Route path="/" element={<Navigate to="/map" replace />} />
      </Routes>
    </AuthProvider>
  );
}
