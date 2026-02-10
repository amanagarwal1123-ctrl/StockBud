import { useEffect, useState } from 'react';
import axios from 'axios';
import { FileUp, Trash2, Loader2, Calendar } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function HistoricalUpload() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [year, setYear] = useState('2025');
  const [fileType, setFileType] = useState('sale');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  useEffect(() => { fetchSummary(); }, []);

  const fetchSummary = async () => {
    try {
      const res = await axios.get(`${API}/historical/summary`);
      setSummary(res.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const CHUNK_SIZE = 4 * 1024 * 1024; // 4MB per chunk

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const token = localStorage.getItem('token');
      const useChunked = file.size > CHUNK_SIZE;

      if (useChunked) {
        // Chunked upload for large files
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
        const initRes = await axios.post(`${API}/upload/init`, {
          file_type: fileType === 'sale' ? 'historical_sale' : 'historical_purchase',
          year,
          start_date: startDate || null,
          end_date: endDate || null,
          total_chunks: totalChunks,
        }, { timeout: 30000 });
        const uploadId = initRes.data.upload_id;

        for (let i = 0; i < totalChunks; i++) {
          setUploadProgress(`Uploading chunk ${i + 1} of ${totalChunks}...`);
          const start = i * CHUNK_SIZE;
          const end = Math.min(start + CHUNK_SIZE, file.size);
          const chunk = file.slice(start, end);
          const fd = new FormData();
          fd.append('file', chunk, `chunk_${i}`);
          await axios.post(`${API}/upload/chunk/${uploadId}?chunk_index=${i}`, fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120000,
          });
        }

        const finalRes = await axios.post(`${API}/upload/finalize/${uploadId}`, {}, { timeout: 600000 });
        toast.success(finalRes.data.message);
      } else {
        // Direct upload for small files
        const fd = new FormData();
        fd.append('file', file);
        let url = `${API}/historical/upload?file_type=${fileType}&year=${year}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        const res = await axios.post(url, fd, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
          timeout: 600000,
        });
        toast.success(res.data.message);
      }
      fetchSummary();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (yr) => {
    if (!window.confirm(`Delete all historical data for ${yr}?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API}/historical/${yr}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Historical data for ${yr} deleted`);
      fetchSummary();
    } catch (e) { toast.error('Delete failed'); }
  };

  const years = [];
  for (let y = 2018; y <= 2026; y++) years.push(String(y));

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="historical-upload-page">
      <div>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Historical Data Upload</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Upload previous years' sales & purchase files to train the AI seasonal analysis engine.
          This data is stored separately and does NOT affect current stock.
        </p>
      </div>

      <Alert className="border-blue-300 bg-blue-50">
        <FileUp className="h-4 w-4 text-blue-600" />
        <AlertDescription className="text-sm text-blue-800">
          Upload the same format Excel files you use for regular sales/purchases. The AI will analyze seasonal
          patterns across years to predict demand by Hindu calendar festivals (Diwali, Holi, Salakh, etc.)
        </AlertDescription>
      </Alert>

      {/* Upload Form */}
      <Card data-testid="historical-upload-form">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <FileUp className="h-5 w-5 text-blue-500" />Upload Historical File
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 items-end">
            <div>
              <Label className="text-xs">Year</Label>
              <Select value={year} onValueChange={setYear}>
                <SelectTrigger data-testid="hist-year"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {years.map(y => <SelectItem key={y} value={y}>{y}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Type</Label>
              <Select value={fileType} onValueChange={setFileType}>
                <SelectTrigger data-testid="hist-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="sale">Sales</SelectItem>
                  <SelectItem value="purchase">Purchases</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Date From (optional)</Label>
              <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} data-testid="hist-start-date" />
            </div>
            <div>
              <Label className="text-xs">Date To (optional)</Label>
              <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} data-testid="hist-end-date" />
            </div>
            <div>
              <Label className="text-xs">Excel File</Label>
              <Input type="file" accept=".xlsx,.xls" onChange={handleUpload} disabled={uploading} data-testid="hist-file" />
            </div>
          </div>
          {uploading && (
            <div className="flex items-center gap-2 text-blue-600 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />Uploading and parsing...
            </div>
          )}
        </CardContent>
      </Card>

      {/* Uploaded Data Summary */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Uploaded Historical Data</CardTitle>
          <CardDescription>
            {summary?.years?.length > 0
              ? `${summary.years.length} year(s) of historical data uploaded`
              : 'No historical data uploaded yet'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {summary?.years?.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Year</TableHead>
                  <TableHead>Sales</TableHead>
                  <TableHead>Purchases</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.years.map(yr => {
                  const d = summary.summary[yr] || {};
                  return (
                    <TableRow key={yr} data-testid={`hist-row-${yr}`}>
                      <TableCell className="font-bold">{yr}</TableCell>
                      <TableCell>
                        {d.sale ? (
                          <div>
                            <Badge variant="outline" className="text-xs">{d.sale.count} transactions</Badge>
                            <span className="text-xs text-muted-foreground ml-2">{d.sale.total_kg} kg</span>
                          </div>
                        ) : <span className="text-muted-foreground text-xs">No data</span>}
                      </TableCell>
                      <TableCell>
                        {d.purchase ? (
                          <div>
                            <Badge variant="outline" className="text-xs">{d.purchase.count} transactions</Badge>
                            <span className="text-xs text-muted-foreground ml-2">{d.purchase.total_kg} kg</span>
                          </div>
                        ) : <span className="text-muted-foreground text-xs">No data</span>}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(yr)} data-testid={`hist-delete-${yr}`}>
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground text-sm">
              <Calendar className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>Upload previous years' Excel files to enable seasonal AI analysis</p>
              <p className="text-xs mt-1">Supports the same format as your regular sales/purchase files</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
