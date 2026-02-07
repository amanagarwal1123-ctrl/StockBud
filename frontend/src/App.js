import { useState } from 'react';
import '@/App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import UploadManager from './pages/UploadManager';
import CurrentStock from './pages/CurrentStock';
import PartyAnalytics from './pages/PartyAnalytics';
import ProfitAnalysis from './pages/ProfitAnalysis';
import History from './pages/History';
import ItemDetail from './pages/ItemDetail';
import StampManagement from './pages/StampManagement';
import PhysicalStockComparison from './pages/PhysicalStockComparison';
import ItemMapping from './pages/ItemMapping';
import MappingManagement from './pages/MappingManagement';
import PurchaseRates from './pages/PurchaseRates';
import UserManagement from './pages/UserManagement';
import ExecutiveStockEntry from './pages/ExecutiveStockEntry';
import ManagerApprovals from './pages/ManagerApprovals';
import Notifications from './pages/Notifications';
import PolytheneEntry from './pages/PolytheneEntry';
import PolytheneManagement from './pages/PolytheneManagement';
import ActivityLog from './pages/ActivityLog';
import ItemBufferManagement from './pages/ItemBufferManagement';
import OrderManagement from './pages/OrderManagement';
import DataVisualization from './pages/DataVisualization';
import StampAssignments from './pages/StampAssignments';
import Login from './pages/Login';
import Layout from './components/Layout';
import { Toaster } from '@/components/ui/sonner';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading, user } = useAuth();
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // Role-based redirects from root
  if (window.location.pathname === '/') {
    if (user?.role === 'polythene_executive') {
      return <Navigate to="/polythene-entry" replace />;
    } else if (user?.role === 'executive') {
      return <Navigate to="/executive-entry" replace />;
    } else if (user?.role === 'manager') {
      return <Navigate to="/physical-vs-book" replace />;
    }
  }
  
  return children;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <Layout>
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="/upload" element={<UploadManager />} />
                      <Route path="/current-stock" element={<CurrentStock />} />
                      <Route path="/physical-vs-book" element={<PhysicalStockComparison />} />
                      <Route path="/item-mapping" element={<ItemMapping />} />
                      <Route path="/mapping-management" element={<MappingManagement />} />
                      <Route path="/purchase-rates" element={<PurchaseRates />} />
                      <Route path="/party-analytics" element={<PartyAnalytics />} />
                      <Route path="/profit" element={<ProfitAnalysis />} />
                      <Route path="/history" element={<History />} />
                      <Route path="/stamps" element={<StampManagement />} />
                      <Route path="/users" element={<UserManagement />} />
                      <Route path="/executive-entry" element={<ExecutiveStockEntry />} />
                      <Route path="/polythene-entry" element={<PolytheneEntry />} />
                      <Route path="/polythene-management" element={<PolytheneManagement />} />
                      <Route path="/approvals" element={<ManagerApprovals />} />
                      <Route path="/notifications" element={<Notifications />} />
                      <Route path="/activity-log" element={<ActivityLog />} />
                      <Route path="/item/:itemName" element={<ItemDetail />} />
                    </Routes>
                  </Layout>
                </ProtectedRoute>
              }
            />
          </Routes>
          <Toaster richColors position="top-right" />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
