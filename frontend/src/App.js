import { useState } from 'react';
import '@/App.css';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import UploadManager from './pages/UploadManager';
import BookInventory from './pages/BookInventory';
import InventoryMatching from './pages/InventoryMatching';
import Analytics from './pages/Analytics';
import History from './pages/History';
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
            <Route path="/book-inventory" element={<BookInventory />} />
            <Route path="/matching" element={<InventoryMatching />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </Layout>
      </BrowserRouter>
      <Toaster />
    </div>
  );
}

export default App;