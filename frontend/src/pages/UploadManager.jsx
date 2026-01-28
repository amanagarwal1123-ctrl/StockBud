import { useState } from 'react';
import axios from 'axios';
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function UploadManager() {
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState({
    purchase: null,
    sale: null,
    opening_stock: null,
    physical_stock: null,
    master_stock: null,
  });
  const [dateRanges, setDateRanges] = useState({
    purchase: { start: '', end: '' },
    sale: { start: '', end: '' },
    physical_stock: { date: '' }
  });

  const handleFileUpload = async (fileType, file) => {
    if (!file) return;

    // Check if date range is required
    if (fileType === 'purchase' || fileType === 'sale') {
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
      'master_stock': 'Master Stock (STOCK 2026) - This will replace your opening stock!'
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
    const formData = new FormData();
    formData.append('file', file);

    try {
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

      const response = await axios.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setUploadedFiles((prev) => ({ ...prev, [fileType]: file.name }));
      toast.success(response.data.message || 'File uploaded successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const FileUploadCard = ({ type, title, description }) => {
    const needsDateRange = type === 'purchase' || type === 'sale';
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

      <Tabs defaultValue="transactions" className="space-y-6">
        <TabsList>
          <TabsTrigger value="master" data-testid="tab-master">
            Master Stock
          </TabsTrigger>
          <TabsTrigger value="transactions" data-testid="tab-transactions">
            Transactions
          </TabsTrigger>
          <TabsTrigger value="physical" data-testid="tab-physical">
            Physical Stock
          </TabsTrigger>
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
            <p className="font-semibold mb-2">Purchase File Columns:</p>
            <p className="text-muted-foreground">
              Date, Type, Refno, Party Name, Item Name, Stamp, Tag.No., Gr.Wt., Net.Wt., Fine Sil., Lbr. Wt/Rs, Dia.Wt., Stn.Wt., Total Pc
            </p>
          </div>
          <div>
            <p className="font-semibold mb-2">Sale File Columns:</p>
            <p className="text-muted-foreground">
              Item Name (or Particular), Gr.Wt., Less (Net Weight), Fine Sil., Fine Total (Labor), Dia.Wt., Stn.Wt., Pc
            </p>
          </div>
          <div>
            <p className="font-semibold mb-2">Physical Inventory Columns:</p>
            <p className="text-muted-foreground">
              Item Name, Stamp, Gross Weight (or Gr.Wt.), Poly Weight, Net Weight (or Net.Wt.)
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}