import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProfileSetupPage from './pages/ProfileSetupPage';
import MapPage from './pages/MapPage';

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/setup" element={<ProfileSetupPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/" element={<Navigate to="/map" replace />} />
      </Routes>
    </AuthProvider>
  );
}
