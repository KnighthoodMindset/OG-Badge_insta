import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import ReelsPage from "./pages/ReelsPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import ApplyBadgePage from "./pages/ApplyBadgePage.jsx";
import { useAuth } from "./auth.jsx"; // ✅ change here

function Protected({ children }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/auth" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/auth" element={<AuthPage />} />

      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/reels" element={<ReelsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/apply" element={<ApplyBadgePage />} />
      </Route>

      <Route path="*" element={<Navigate to="/auth" replace />} />

    </Routes>
  );
}
