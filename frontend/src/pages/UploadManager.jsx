import { useState, useRef } from 'react';
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle, Calendar, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useUpload } from '../context/UploadContext';
import PhysicalStockPreview from '../components/PhysicalStockPreview';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function UploadManager() {
  const { uploads, enqueueUpload } = useUpload();
  const [uploadedFiles, setUploadedFiles] = useState({});
  const [masterDateRange, setMasterDateRange] = useState({ start: '', end: '' });
  const [dateRanges, setDateRanges] = useState({
    purchase: { start: '', end: '' },
    sale: { start: '', end: '' },
    branch_transfer: { start: '', end: '' },
    physical_stock: { date: '' }
  });

  // Physical stock preview state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Pending file for confirmation (non-physical types)
  const [pendingFile, setPendingFile] = useState(null); // { fileType, file }

  const uploadingTypes = new Set(
    uploads.filter(u => u.status === 'uploading' || u.status === 'queued' || u.status === 'processing').map(u => u.fileType)
  );

  const applyMasterDates = () => {
    if (!masterDateRange.start || !masterDateRange.end) {
      toast.error('Please select both master dates first');
      return;
    }
    setDateRanges(prev => ({
      ...prev,
      purchase: { start: masterDateRange.start, end: masterDateRange.end },
      sale: { start: masterDateRange.start, end: masterDateRange.end },
      branch_transfer: { start: masterDateRange.start, end: masterDateRange.end },
    }));
    toast.success(`Date range applied: ${masterDateRange.start} to ${masterDateRange.end}`);
  };

  // Called when a file is selected — deterministic, no confirm-in-onChange
  const handleFileSelected = (fileType, file) => {
    if (!file) return;

    // Validate dates
    if (fileType === 'purchase' || fileType === 'sale' || fileType === 'branch_transfer') {
      const range = dateRanges[fileType];
      if (!range.start || !range.end) {
        toast.error('Please select date range for this transaction file');
        return;
      }
    }
    if (fileType === 'physical_stock' && !dateRanges.physical_stock.date) {
      toast.error('Please select verification date for physical stock');
      return;
    }

    if (fileType === 'physical_stock') {
      // Physical stock goes through preview flow
      handlePhysicalStockPreview(file);
    } else {
      // Other types: set pending for confirmation
      setPendingFile({ fileType, file });
    }
  };

  // Physical stock: upload for preview (no DB mutation)
  const handlePhysicalStockPreview = async (file) => {
    setPreviewLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const vDate = dateRanges.physical_stock?.date || '';
      const res = await axios.post(`${API}/physical-stock/upload-preview?verification_date=${vDate}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      setPreviewData(res.data);
      setPreviewOpen(true);
      setUploadedFiles(prev => ({ ...prev, physical_stock: file.name }));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Preview failed');
    } finally {
      setPreviewLoading(false);
    }
  };

  // Confirm and enqueue a non-physical upload
  const confirmUpload = () => {
    if (!pendingFile) return;
    const { fileType, file } = pendingFile;
    enqueueUpload(fileType, file, dateRanges);
    setUploadedFiles(prev => ({ ...prev, [fileType]: file.name }));
    setPendingFile(null);
  };

  const cancelUpload = () => {
    setPendingFile(null);
  };

  const fileTypeNames = {
    'opening_stock': 'Opening Stock (PREV_STOCK)',
    'purchase': 'Purchase Transactions',
    'sale': 'Sale Transactions',
    'physical_stock': 'Physical Stock (CURRENT_STOCK)',
    'master_stock': 'Master Stock (STOCK 2026)',
    'branch_transfer': 'Branch Issue/Receive (MMI Jewelly)'
  };

  const FileUploadCard = ({ type, title, description }) => {
    const isTypeUploading = uploadingTypes.has(type);
    const needsDateRange = type === 'purchase' || type === 'sale' || type === 'branch_transfer';
    const needsDate = type === 'physical_stock';
    const isPhysicalLoading = type === 'physical_stock' && previewLoading;
    const fileRef = useRef(null);

    const onFileChange = (e) => {
      const file = e.target.files?.[0];
      e.target.value = '';
      if (file) handleFileSelected(type, file);
    };

    return (
      <Card className="border-border/40 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
            {title}
          </CardTitle>
          <CardDescription className="text-xs">{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {needsDateRange && (
            <div className="grid grid-cols-2 gap-3 pb-3 border-b">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">From Date *</label>
                <Input type="date" value={dateRanges[type]?.start || ''} onChange={(e) => setDateRanges(prev => ({ ...prev, [type]: { ...prev[type], start: e.target.value } }))} className="text-sm h-9" data-testid={`date-start-${type}`} required />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">To Date *</label>
                <Input type="date" value={dateRanges[type]?.end || ''} onChange={(e) => setDateRanges(prev => ({ ...prev, [type]: { ...prev[type], end: e.target.value } }))} className="text-sm h-9" data-testid={`date-end-${type}`} required />
              </div>
            </div>
          )}
          {needsDate && (
            <div className="pb-3 border-b">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Verification Date *</label>
              <Input type="date" value={dateRanges.physical_stock?.date || ''} onChange={(e) => setDateRanges(prev => ({ ...prev, physical_stock: { date: e.target.value } }))} className="text-sm h-9" required />
            </div>
          )}
          <div
            onClick={() => { if (!isTypeUploading && !isPhysicalLoading) fileRef.current?.click(); }}
            className={`upload-zone flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-8 transition-all ${(isTypeUploading || isPhysicalLoading) ? 'border-muted-foreground/10 bg-muted/20 cursor-not-allowed opacity-50' : 'border-muted-foreground/25 cursor-pointer hover:border-primary/50 bg-muted/5'}`}
            data-testid={`upload-zone-${type}`}
          >
            {isPhysicalLoading ? (
              <>
                <Loader2 className="h-10 w-10 text-primary animate-spin" />
                <p className="font-medium text-sm">Generating preview...</p>
              </>
            ) : uploadedFiles[type] ? (
              <>
                <CheckCircle2 className="h-10 w-10 text-emerald-600" />
                <div className="text-center">
                  <p className="font-medium text-sm">{uploadedFiles[type]}</p>
                  <p className="text-xs text-muted-foreground mt-1">Click to upload another file</p>
                </div>
              </>
            ) : (
              <>
                <Upload className="h-10 w-10 text-muted-foreground" />
                <div className="text-center">
                  <p className="font-medium text-sm">Click to upload or drag and drop</p>
                  <p className="text-xs text-muted-foreground mt-1">Excel files (.xlsx, .xls)</p>
                </div>
              </>
            )}
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              onChange={onFileChange}
              disabled={isTypeUploading || isPhysicalLoading}
              data-testid={`file-input-${type}`}
            />
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6" data-testid="upload-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight" data-testid="upload-title">Upload Files</h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">Upload your purchase, sale, and physical inventory Excel files</p>
      </div>

      <Tabs defaultValue="transactions" className="space-y-6">
        <TabsList>
          <TabsTrigger value="master">Master Stock</TabsTrigger>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
          <TabsTrigger value="branch">Branch Transfer</TabsTrigger>
          <TabsTrigger value="physical">Physical Stock</TabsTrigger>
        </TabsList>

        <TabsContent value="master" className="space-y-6">
          <div className="max-w-2xl">
            <FileUploadCard type="master_stock" title="Master Stock (STOCK 2026)" description="Upload your FINAL verified stock with definitive item names and stamps. This replaces opening stock and becomes the reference for all future transactions." />
          </div>
        </TabsContent>
        <TabsContent value="transactions" className="space-y-6">
          <Card className="border-primary/20 bg-primary/5" data-testid="master-date-card">
            <CardContent className="p-4">
              <div className="flex flex-col sm:flex-row items-start sm:items-end gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-primary shrink-0">
                  <Calendar className="h-4 w-4" />
                  Master Date Range
                </div>
                <div className="grid grid-cols-2 gap-3 flex-1 w-full sm:w-auto">
                  <Input type="date" value={masterDateRange.start} onChange={(e) => setMasterDateRange(prev => ({ ...prev, start: e.target.value }))} className="text-sm h-9 bg-background" data-testid="master-date-start" />
                  <Input type="date" value={masterDateRange.end} onChange={(e) => setMasterDateRange(prev => ({ ...prev, end: e.target.value }))} className="text-sm h-9 bg-background" data-testid="master-date-end" />
                </div>
                <Button size="sm" onClick={applyMasterDates} className="h-9 shrink-0" data-testid="apply-master-dates">
                  Apply to All
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-2">Set once, applies to Purchase, Sale, and Branch Transfer. You can still change individual dates below.</p>
            </CardContent>
          </Card>
          <div className="grid gap-3 sm:gap-6 grid-cols-1 md:grid-cols-2">
            <FileUploadCard type="purchase" title="Purchase File" description="Upload your purchase transactions Excel file" />
            <FileUploadCard type="sale" title="Sale File" description="Upload your sale transactions Excel file" />
          </div>
        </TabsContent>
        <TabsContent value="branch" className="space-y-6">
          <div className="max-w-2xl">
            <FileUploadCard type="branch_transfer" title="Branch Issue/Receive (MMI Jewelly)" description="Upload branch transfer file. I=Issue (stock out), R=Receive (stock in). No profit calculation." />
          </div>
        </TabsContent>
        <TabsContent value="physical" className="space-y-6">
          <div className="max-w-2xl">
            <FileUploadCard
              type="physical_stock"
              title="Physical Stock (Partial Update)"
              description="Upload physical stock file to preview and selectively approve changes. Accepts: Item Name + Gross Weight, or Item Name + Gross Weight + Net Weight. Items not in the file stay unchanged."
            />
          </div>
        </TabsContent>
      </Tabs>

      <Card className="border-border/40 shadow-sm bg-muted/30">
        <CardHeader>
          <CardTitle className="text-xl flex items-center gap-2"><AlertCircle className="h-5 w-5 text-primary" />File Format Guidelines</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div><p className="font-semibold mb-2">Master Stock (STOCK 2026):</p><p className="text-muted-foreground">Item Name, Stamp, Gross weight, Net Weight</p></div>
          <div><p className="font-semibold mb-2">Branch Transfer (Issue/Receive):</p><p className="text-muted-foreground">Date, Type (I/R), Lnarr (item name), Gr.Wt., Net.Wt.</p><p className="text-xs text-orange-600 mt-1">Skip OPENING BALANCE and Totals rows</p></div>
          <div><p className="font-semibold mb-2">Purchase File:</p><p className="text-muted-foreground">Date, Type, Party Name, Item Name, Gr.Wt., Net.Wt., Tunch, Total</p></div>
          <div><p className="font-semibold mb-2">Sale File:</p><p className="text-muted-foreground">Date, Type, Party Name, Item Name, Gr.Wt., Gold Std. (Net), Tunch, Total</p></div>
          <div>
            <p className="font-semibold mb-2">Physical Stock (Partial Update):</p>
            <p className="text-muted-foreground">Accepted formats (Stamp is always optional):</p>
            <ul className="text-xs text-muted-foreground list-disc ml-4 mt-1 space-y-0.5">
              <li><strong>2 columns:</strong> Item Name, Gross Weight — updates gross only, net preserved</li>
              <li><strong>3 columns:</strong> Item Name, Gross Weight, Net Weight — updates both</li>
              <li><strong>4 columns:</strong> Item Name, Stamp, Gross Weight, Net Weight</li>
            </ul>
            <p className="text-xs text-muted-foreground mt-1">Headers accepted: Gr.Wt. / Gross Wt / Gross Weight | Net.Wt. / Net Wt / Net Weight / Gold Std.</p>
            <p className="text-xs text-orange-600 mt-1">Items not in the file remain unchanged. Unmatched items are shown but blocked from apply.</p>
          </div>
        </CardContent>
      </Card>

      {/* Confirmation dialog for non-physical uploads */}
      {pendingFile && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center" data-testid="upload-confirm-overlay">
          <Card className="w-full max-w-md mx-4" data-testid="upload-confirm-dialog">
            <CardHeader>
              <CardTitle>Confirm Upload</CardTitle>
              <CardDescription>
                {fileTypeNames[pendingFile.fileType] || pendingFile.fileType}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm">File: <strong>{pendingFile.file.name}</strong></p>
              {(pendingFile.fileType === 'purchase' || pendingFile.fileType === 'sale' || pendingFile.fileType === 'branch_transfer') && (
                <p className="text-sm">
                  Date Range: {dateRanges[pendingFile.fileType]?.start} to {dateRanges[pendingFile.fileType]?.end}
                  <br /><span className="text-xs text-muted-foreground">Only dates present in the file will be replaced.</span>
                </p>
              )}
              {(pendingFile.fileType === 'opening_stock' || pendingFile.fileType === 'master_stock') && (
                <p className="text-sm text-orange-600">This will replace all existing data.</p>
              )}
              <div className="flex gap-2 justify-end pt-2">
                <Button variant="outline" size="sm" onClick={cancelUpload} data-testid="upload-cancel-btn">Cancel</Button>
                <Button size="sm" onClick={confirmUpload} data-testid="upload-confirm-btn">Upload</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Physical stock preview modal */}
      <PhysicalStockPreview
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        previewData={previewData}
      />
    </div>
  );
}
