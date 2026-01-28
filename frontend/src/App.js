import { useState } from 'react';
import '@/App.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
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
import Layout from './components/Layout';
import { Toaster } from '@/components/ui/sonner';

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<UploadManager />} />
            <Route path="/current-stock" element={<CurrentStock />} />
            <Route path="/physical-vs-book" element={<PhysicalStockComparison />} />
            <Route path="/item-mapping" element={<ItemMapping />} />
            <Route path="/mapping-management" element={<MappingManagement />} />
            <Route path="/party-analytics" element={<PartyAnalytics />} />
            <Route path="/profit" element={<ProfitAnalysis />} />
            <Route path="/history" element={<History />} />
            <Route path="/stamps" element={<StampManagement />} />
            <Route path="/item/:itemName" element={<ItemDetail />} />
          </Routes>
        </Layout>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </div>
  );
}

export default App;