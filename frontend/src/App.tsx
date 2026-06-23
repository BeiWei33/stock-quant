import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/auth';
import LoginPage from './pages/Login';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/Dashboard';
import SignalsPage from './pages/Signals';
import PositionsPage from './pages/Positions';
import BacktestPage from './pages/Backtest';
import MonitoringPage from './pages/Monitoring';
import TasksPage from './pages/Tasks';
import KLinePage from './pages/KLine';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="signals" element={<SignalsPage />} />
        <Route path="positions" element={<PositionsPage />} />
        <Route path="backtest" element={<BacktestPage />} />
        <Route path="kline" element={<KLinePage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="tasks" element={<TasksPage />} />
      </Route>
    </Routes>
  );
}

export default App;
