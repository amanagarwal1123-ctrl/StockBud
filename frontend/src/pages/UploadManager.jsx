import { useState } from 'react';
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useUpload } from '../context/UploadContext';

export default function UploadManager() {
  const { uploads, startUpload } = useUpload();
  const [uploadedFiles, setUploadedFiles] = useState({});
  const [dateRanges, setDateRanges] = useState({
    purchase: { start: '', end: '' },
    sale: { start: '', end: '' },
    branch_transfer: { start: '', end: '' },
    physical_stock: { date: '' }
  });

  const isUploading = uploads.some(u => u.status === 'uploading');

  const handleFileUpload = async (fileType, file) => {
    if (!file) return;

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

    if (!window.confirm(confirmMessage)) return;

    try {
      await startUpload(fileType, file, dateRanges);
      setUploadedFiles(prev => ({ ...prev, [fileType]: file.name }));
    } catch {
      // Error already handled in context
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
          {needsDateRange && (
            <div className="grid grid-cols-2 gap-3 pb-3 border-b">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">From Date *</label>
                <Input type="date" value={dateRanges[type]?.start || ''} onChange={(e) => setDateRanges(prev => ({ ...prev, [type]: { ...prev[type], start: e.target.value } }))} className="text-sm" required />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">To Date *</label>
                <Input type="date" value={dateRanges[type]?.end || ''} onChange={(e) => setDateRanges(prev => ({ ...prev, [type]: { ...prev[type], end: e.target.value } }))} className="text-sm" required />
              </div>
            </div>
          )}
          {needsDate && (
            <div className="pb-3 border-b">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Verification Date *</label>
              <Input type="date" value={dateRanges.physical_stock?.date || ''} onChange={(e) => setDateRanges(prev => ({ ...prev, physical_stock: { date: e.target.value } }))} className="text-sm" required />
            </div>
          )}
          <label htmlFor={isUploading ? undefined : `${type}-upload`} className={`upload-zone flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-12 transition-all ${isUploading ? 'border-muted-foreground/10 bg-muted/20 cursor-not-allowed opacity-50' : 'border-muted-foreground/25 cursor-pointer hover:border-primary/50 bg-muted/5'}`} data-testid={`upload-zone-${type}`}>
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
            <input id={`${type}-upload`} type="file" accept=".xlsx,.xls" className="hidden" onChange={(e) => handleFileUpload(type, e.target.files[0])} disabled={isUploading} />
          </label>
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
          <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-2">
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
            <FileUploadCard type="physical_stock" title="Physical Stock (CURRENT_STOCK)" description="Upload your physical count Excel file to compare with book stock. System will show differences." />
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
          <div><p className="font-semibold mb-2">Physical Stock:</p><p className="text-muted-foreground">Item Name, Stamp, Gross Weight, Net Weight</p></div>
        </CardContent>
      </Card>
    </div>
  );
}
