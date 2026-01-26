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
  });

  const handleFileUpload = async (fileType, file) => {
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      let endpoint;
      if (fileType === 'opening_stock') {
        endpoint = `${API}/opening-stock/upload`;
      } else if (fileType === 'physical_stock') {
        endpoint = `${API}/physical-stock/upload`;
      } else {
        endpoint = `${API}/transactions/upload/${fileType}`;
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

  const FileUploadCard = ({ type, title, description }) => (
    <Card className="border-border/40 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl">
          <FileSpreadsheet className="h-5 w-5 text-primary" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
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
          <TabsTrigger value="transactions" data-testid="tab-transactions">
            Transactions
          </TabsTrigger>
          <TabsTrigger value="opening" data-testid="tab-opening">
            Opening Stock
          </TabsTrigger>
          <TabsTrigger value="physical" data-testid="tab-physical">
            Physical Stock
          </TabsTrigger>
        </TabsList>

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

        <TabsContent value="opening" className="space-y-6">
          <div className="max-w-2xl">
            <FileUploadCard
              type="opening_stock"
              title="Opening Stock (PREV_STOCK)"
              description="Upload your opening stock Excel file. Duplicate items will be automatically merged."
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