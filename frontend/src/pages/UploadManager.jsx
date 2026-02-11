import { useState } from 'react';
import axios from 'axios';
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function UploadManager() {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState({
    purchase: null,
    sale: null,
    opening_stock: null,
    physical_stock: null,
    master_stock: null,
    branch_transfer: null,
  });
  const [dateRanges, setDateRanges] = useState({
    purchase: { start: '', end: '' },
    sale: { start: '', end: '' },
    branch_transfer: { start: '', end: '' },
    physical_stock: { date: '' }
  });

  const CHUNK_SIZE = 768 * 1024; // 768KB per chunk — stays under deployment proxy limits

  const pollUploadStatus = async (uploadId) => {
    for (let attempt = 0; attempt < 120; attempt++) { // Max ~10 minutes
      await new Promise(r => setTimeout(r, 5000)); // Poll every 5s
      const res = await axios.get(`${API}/upload/status/${uploadId}`, { timeout: 10000 });
      if (res.data.status === 'complete') return res;
      if (res.data.status === 'error') throw new Error(res.data.detail || 'Processing failed');
      setUploadProgress(`Processing on server... (${attempt * 5}s elapsed)`);
    }
    throw new Error('Processing timed out');
  };

  const uploadChunked = async (fileType, file) => {
    const range = dateRanges[fileType] || {};
    // 1. Init upload session
    setUploadProgress('Initializing upload...');
    const initRes = await axios.post(`${API}/upload/init`, {
      file_type: fileType,
      start_date: range.start || null,
      end_date: range.end || null,
      verification_date: fileType === 'physical_stock' ? dateRanges.physical_stock?.date : null,
      total_chunks: Math.ceil(file.size / CHUNK_SIZE),
    }, { timeout: 30000 });
    const uploadId = initRes.data.upload_id;
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    // 2. Send chunks
    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);
      const fd = new FormData();
      fd.append('file', chunk, `chunk_${i}`);
      setUploadProgress(`Uploading chunk ${i + 1} of ${totalChunks}...`);
      await axios.post(`${API}/upload/chunk/${uploadId}?chunk_index=${i}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
    }

    // 3. Finalize — kicks off background processing
    setUploadProgress('Processing file on server...');
    await axios.post(`${API}/upload/finalize/${uploadId}`, {}, { timeout: 30000 });

    // 4. Poll for completion
    return await pollUploadStatus(uploadId);
  };

  const handleFileUpload = async (fileType, file) => {
    if (!file) return;

    // Check if date range is required
    if (fileType === 'purchase' || fileType === 'sale' || fileType === 'branch_transfer') {
      const range = dateRanges[fileType];
      if (!range.start || !range.end) {
        toast.error('Please select date range for this transaction file');
        return;
      }
    }

    if (fileType === 'physical_stock') {
      if (!dateRanges.physical_stock.date) {
        toast.error('Please select verification date for physical stock');
        return;
      }
    }

    // Confirmation dialog
    const fileTypeNames = {
      'opening_stock': 'Opening Stock (PREV_STOCK)',
      'purchase': 'Purchase Transactions',
      'sale': 'Sale Transactions',
      'physical_stock': 'Physical Stock (CURRENT_STOCK)',
      'master_stock': 'Master Stock (STOCK 2026) - This will replace your opening stock!',
      'branch_transfer': 'Branch Issue/Receive (MMI Jewelly)'
    };

    let confirmMessage = `Are you sure you want to upload ${fileTypeNames[fileType]}?\n\nFile: ${file.name}\n\n`;
    
    if (fileType === 'purchase' || fileType === 'sale') {
      const range = dateRanges[fileType];
      confirmMessage += `Date Range: ${range.start} to ${range.end}\n\nThis will REPLACE all ${fileType} transactions in this date range.`;
    } else if (fileType === 'physical_stock') {
      confirmMessage += `Verification Date: ${dateRanges.physical_stock.date}`;
    } else {
      confirmMessage += `This will ${fileType === 'opening_stock' || fileType === 'master_stock' ? 'replace all existing data' : 'add new transactions'}.`;
    }

    const confirmed = window.confirm(confirmMessage);
    if (!confirmed) return;

    setUploading(true);
    setUploadProgress('Preparing upload...');

    try {
      let response;
      const useChunked = file.size > CHUNK_SIZE && fileType !== 'master_stock';

      if (useChunked) {
        response = await uploadChunked(fileType, file);
      } else {
        // Small file — direct upload
        setUploadProgress('Uploading file...');
        const formData = new FormData();
        formData.append('file', file);
        let endpoint;
        if (fileType === 'opening_stock') {
          endpoint = `${API}/opening-stock/upload`;
        } else if (fileType === 'physical_stock') {
          endpoint = `${API}/physical-stock/upload?verification_date=${dateRanges.physical_stock.date}`;
        } else if (fileType === 'master_stock') {
          endpoint = `${API}/master-stock/upload`;
        } else {
          const range = dateRanges[fileType];
          endpoint = `${API}/transactions/upload/${fileType}?start_date=${range.start}&end_date=${range.end}`;
        }
        response = await axios.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 600000,
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total);
              setUploadProgress(pct < 100 ? `Uploading: ${pct}%` : 'Processing file on server...');
            }
          },
        });
      }

      setUploadedFiles((prev) => ({ ...prev, [fileType]: file.name }));
      toast.success(response.data.message || 'File uploaded successfully!');
    } catch (error) {
      const msg = error.message || error.response?.data?.detail || error.code === 'ECONNABORTED' ? 'Upload timed out.' : 'Upload failed';
      toast.error(msg);
    } finally {
      setUploading(false);
      setUploadProgress('');
    }
  };

  const FileUploadCard = ({ type, title, description }) => {
    const needsDateRange = type === 'purchase' || type === 'sale' || type === 'branch_transfer';
    const needsDate = type === 'physical_stock';

    return (
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
            {title}
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Date Range Selector for Transactions */}
          {needsDateRange && (
            <div className="grid grid-cols-2 gap-3 pb-3 border-b">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  From Date *
                </label>
                <Input
                  type="date"
                  value={dateRanges[type]?.start || ''}
                  onChange={(e) => setDateRanges(prev => ({
                    ...prev,
                    [type]: { ...prev[type], start: e.target.value }
                  }))}
                  className="text-sm"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  To Date *
                </label>
                <Input
                  type="date"
                  value={dateRanges[type]?.end || ''}
                  onChange={(e) => setDateRanges(prev => ({
                    ...prev,
                    [type]: { ...prev[type], end: e.target.value }
                  }))}
                  className="text-sm"
                  required
                />
              </div>
            </div>
          )}

          {/* Single Date for Physical Stock */}
          {needsDate && (
            <div className="pb-3 border-b">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Verification Date *
              </label>
              <Input
                type="date"
                value={dateRanges.physical_stock?.date || ''}
                onChange={(e) => setDateRanges(prev => ({
                  ...prev,
                  physical_stock: { date: e.target.value }
                }))}
                className="text-sm"
                required
              />
            </div>
          )}

          <label
            htmlFor={`${type}-upload`}
            className="upload-zone flex flex-col items-center justify-center gap-3 cursor-pointer border-2 border-dashed border-muted-foreground/25 rounded-xl p-12 hover:border-primary/50 transition-all bg-muted/5"
            data-testid={`upload-zone-${type}`}
          >
            {uploadedFiles[type] ? (
              <>
                <CheckCircle2 className="h-12 w-12 text-emerald-600" />
                <div className="text-center">
                  <p className="font-medium text-sm">{uploadedFiles[type]}</p>
                  <p className="text-xs text-muted-foreground mt-1">Click to upload another file</p>
                </div>
              </>
            ) : (
              <>
                <Upload className="h-12 w-12 text-muted-foreground" />
                <div className="text-center">
                  <p className="font-medium text-sm">Click to upload or drag and drop</p>
                  <p className="text-xs text-muted-foreground mt-1">Excel files (.xlsx, .xls)</p>
                </div>
              </>
            )}
            <input
            id={`${type}-upload`}
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={(e) => handleFileUpload(type, e.target.files[0])}
            disabled={uploading}
          />
        </label>
      </CardContent>
    </Card>
    );
  };

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="upload-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight" data-testid="upload-title">
          Upload Files
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Upload your purchase, sale, and physical inventory Excel files
        </p>
      </div>

      {uploading && uploadProgress && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-primary/10 border border-primary/20" data-testid="upload-progress">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm font-medium">{uploadProgress}</span>
        </div>
      )}

      <Tabs defaultValue="transactions" className="space-y-6">
        <TabsList>
          <TabsTrigger value="master">Master Stock</TabsTrigger>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
          <TabsTrigger value="branch">Branch Transfer</TabsTrigger>
          <TabsTrigger value="physical">Physical Stock</TabsTrigger>
        </TabsList>

        <TabsContent value="master" className="space-y-6">
          <div className="max-w-2xl">
            <FileUploadCard
              type="master_stock"
              title="Master Stock (STOCK 2026)"
              description="Upload your FINAL verified stock with definitive item names and stamps. This replaces opening stock and becomes the reference for all future transactions."
            />
          </div>
        </TabsContent>

        <TabsContent value="transactions" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <FileUploadCard
              type="purchase"
              title="Purchase File"
              description="Upload your purchase transactions Excel file"
            />
            <FileUploadCard
              type="sale"
              title="Sale File"
              description="Upload your sale transactions Excel file"
            />
          </div>
        </TabsContent>

        <TabsContent value="branch" className="space-y-6">
          <div className="max-w-2xl">
            <FileUploadCard
              type="branch_transfer"
              title="Branch Issue/Receive (MMI Jewelly)"
              description="Upload branch transfer file. I=Issue (stock out), R=Receive (stock in). No profit calculation."
            />
          </div>
        </TabsContent>

        <TabsContent value="physical" className="space-y-6">
          <div className="max-w-2xl">
            <FileUploadCard
              type="physical_stock"
              title="Physical Stock (CURRENT_STOCK)"
              description="Upload your physical count Excel file to compare with book stock. System will show differences."
            />
          </div>
        </TabsContent>
      </Tabs>

      {/* Instructions */}
      <Card className="border-border/40 shadow-sm bg-muted/30">
        <CardHeader>
          <CardTitle className="text-xl flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-primary" />
            File Format Guidelines
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div>
            <p className="font-semibold mb-2">Master Stock (STOCK 2026):</p>
            <p className="text-muted-foreground">Item Name, Stamp, Gross weight, Net Weight</p>
          </div>
          
          <div>
            <p className="font-semibold mb-2">Branch Transfer (Issue/Receive):</p>
            <p className="text-muted-foreground">Date, Type (I/R), Lnarr (item name), Gr.Wt., Net.Wt.</p>
            <p className="text-xs text-orange-600 mt-1">Skip OPENING BALANCE and Totals rows</p>
          </div>

          <div>
            <p className="font-semibold mb-2">Purchase File:</p>
            <p className="text-muted-foreground">Date, Type, Party Name, Item Name, Gr.Wt., Net.Wt., Tunch, Total</p>
          </div>

          <div>
            <p className="font-semibold mb-2">Sale File:</p>
            <p className="text-muted-foreground">Date, Type, Party Name, Item Name, Gr.Wt., Gold Std. (Net), Tunch, Total</p>
          </div>

          <div>
            <p className="font-semibold mb-2">Physical Stock:</p>
            <p className="text-muted-foreground">Item Name, Stamp, Gross Weight, Net Weight</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}