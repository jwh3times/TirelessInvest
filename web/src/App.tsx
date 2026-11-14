import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { needsPassword, useAuth } from "./lib/auth";
import { AdminPage } from "./pages/AdminPage";
import { BacktestPage } from "./pages/BacktestPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LabPage } from "./pages/LabPage";
import { LoginPage } from "./pages/LoginPage";
import { SetPasswordPage } from "./pages/SetPasswordPage";

export function App() {
  const { session, loading, me, meError } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  if (!session) return <LoginPage />;
  if (needsPassword(session.user)) return <SetPasswordPage />;
  if (meError)
    return (
      <div className="center">
        <p className="error">Could not reach the API: {meError.message}</p>
      </div>
    );
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LabPage />} />
        <Route path="backtests" element={<HistoryPage />} />
        <Route path="backtests/:id" element={<BacktestPage />} />
        <Route
          path="admin"
          element={me?.is_admin ? <AdminPage /> : <Navigate to="/" replace />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
