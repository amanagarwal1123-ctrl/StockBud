import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import * as XLSX from 'xlsx';
import { FileUp, Trash2, Loader2, Calendar } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const BATCH_SIZE = 2000; // rows per batch sent to server

// Detect the header row in sheet data (mirrors server logic)
function detectHeaderAndData(sheetData) {
  const headerKeywords = ['item name', 'particular', 'party name', 'lnarr'];
  let headerIdx = 0;

  const limit = Math.min(20, sheetData.length);
  for (let i = 0; i < limit; i++) {
    const rowStr = (sheetData[i] || []).map(v => String(v ?? '').toLowerCase()).join(' ');
    if (headerKeywords.some(kw => rowStr.includes(kw))) {
      headerIdx = i;
      break;
    }
  }

  const headers = (sheetData[headerIdx] || []).map(v => String(v ?? '').trim());
  const dataRows = sheetData.slice(headerIdx + 1);
  return { headers, dataRows };
}

export default function HistoricalUpload() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [phase, setPhase] = useState(''); // 'reading' | 'sending' | ''
  const [progressPct, setProgressPct] = useState(0);
  const [progressMsg, setProgressMsg] = useState('');
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

  const handleUpload = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setPhase('reading');
    setProgressPct(0);
    setProgressMsg('Reading Excel file in browser...');

    try {
      // ---- STEP 1: Read & parse Excel in the browser ----
      const arrayBuffer = await file.arrayBuffer();
      const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1);
      setProgressMsg(`Parsing ${fileSizeMB} MB Excel file...`);

      const workbook = XLSX.read(arrayBuffer, { type: 'array', cellDates: false, cellText: true, raw: false });
      const sheetName = workbook.SheetNames[0];
      const sheet = workbook.Sheets[sheetName];

      // Convert to 2D array (all strings)
      const sheetData = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '', raw: false });

      const { headers, dataRows } = detectHeaderAndData(sheetData);
      const totalRows = dataRows.length;

      if (totalRows === 0) {
        toast.error('No data rows found in the file');
        return;
      }

      setProgressMsg(`Found ${totalRows.toLocaleString()} rows. Sending to server...`);
      setPhase('sending');

      // ---- STEP 2: Send rows to server in batches ----
      const batchId = crypto.randomUUID ? crypto.randomUUID() : `batch-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const totalBatches = Math.ceil(totalRows / BATCH_SIZE);
      const apiFileType = fileType === 'sale' ? 'historical_sale' : 'historical_purchase';
      let totalInserted = 0;

      for (let b = 0; b < totalBatches; b++) {
        const start = b * BATCH_SIZE;
        const end = Math.min(start + BATCH_SIZE, totalRows);
        const batchRows = dataRows.slice(start, end);
        const isFinal = (b === totalBatches - 1);
        const pct = Math.round(((b + 1) / totalBatches) * 100);

        setProgressPct(pct);
        setProgressMsg(`Sending batch ${b + 1} of ${totalBatches} (${pct}%) — ${totalInserted.toLocaleString()} records saved`);

        const res = await axios.post(`${API}/upload/client-batch`, {
          file_type: apiFileType,
          batch_id: batchId,
          year,
          headers,
          rows: batchRows,
          batch_index: b,
          is_final: isFinal,
        }, { timeout: 0 });

        totalInserted = res.data.total_so_far || totalInserted + (res.data.batch_records || 0);

        if (isFinal && res.data.message) {
          toast.success(res.data.message);
        }
      }

      setProgressMsg(`Done! ${totalInserted.toLocaleString()} records uploaded.`);
      fetchSummary();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Upload failed';
      toast.error(detail, { duration: 10000 });
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
      setPhase('');
      setProgressPct(0);
      setProgressMsg('');
      e.target.value = '';
    }
  }, [fileType, year]);

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
            <div className="space-y-3 pt-2" data-testid="upload-progress-section">
              {phase === 'reading' && (
                <div className="flex items-center gap-2 text-blue-600 text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>{progressMsg}</span>
                </div>
              )}
              {phase === 'sending' && (
                <>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-blue-700 font-medium flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading records...
                    </span>
                    <span className="text-blue-600 font-mono font-bold" data-testid="upload-percent">{progressPct}%</span>
                  </div>
                  <Progress value={progressPct} className="h-3" data-testid="upload-progress-bar" />
                  <p className="text-xs text-muted-foreground" data-testid="upload-detail">{progressMsg}</p>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

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
