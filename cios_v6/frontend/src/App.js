import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './hooks/useAuth';
import LoginPage        from './pages/LoginPage';
import DashboardPage    from './pages/DashboardPage';
import PatientListPage  from './pages/PatientListPage';
import PatientDetailPage from './pages/PatientDetailPage';
import AIInsightsPage   from './pages/AIInsightsPage';
import ReportsPage      from './pages/ReportsPage';
import AdminPage        from './pages/AdminPage';
import MessagingPage    from './pages/MessagingPage';
import ReferralsPage    from './pages/ReferralsPage';
import Layout           from './components/Layout';

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: { background:'#0B1E3D', color:'#fff', border:'1px solid #0EA5E930' },
            success: { style: { border:'1px solid #22C55E40' } },
            error:   { style: { border:'1px solid #DC262640' } },
          }}
        />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index             element={<DashboardPage />} />
            <Route path="patients"   element={<PatientListPage />} />
            <Route path="patients/:id" element={<PatientDetailPage />} />
            <Route path="ai-insights"  element={<AIInsightsPage />} />
            <Route path="reports"      element={<ReportsPage />} />
            <Route path="messaging"    element={<MessagingPage />} />
            <Route path="referrals"    element={<ReferralsPage />} />
            <Route path="admin"        element={<AdminPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
