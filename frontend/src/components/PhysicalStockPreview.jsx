import { useState, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { Check, CheckCheck, Download, AlertTriangle, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import axios from 'axios';
import { exportToCSV } from '../utils/exportCSV';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function DeltaBadge({ value, suffix = 'kg' }) {
  if (Math.abs(value) < 0.001) return <span className="text-muted-foreground font-mono text-xs">0.000</span>;
  const isPos = value > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 font-mono text-xs ${isPos ? 'text-emerald-600' : 'text-red-600'}`}>
      {isPos ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
      {isPos ? '+' : ''}{value.toFixed(3)} {suffix}
    </span>
  );
}

export default function PhysicalStockPreview({ open, onClose, previewData }) {
  const [rows, setRows] = useState([]);
  const [applying, setApplying] = useState(null); // null | 'single' | 'all'

  // Sync rows when previewData changes
  useState(() => {
    if (previewData?.preview_rows) {
      setRows(previewData.preview_rows);
    }
  }, [previewData]);

  // Recalculate when previewData opens
  useMemo(() => {
    if (open && previewData?.preview_rows) {
      setRows(previewData.preview_rows);
    }
  }, [open, previewData]);

  const verificationDate = previewData?.verification_date || '';
  const updateMode = previewData?.update_mode || 'gross_only';

  const pendingRows = rows.filter(r => r.status === 'pending');
  const approvedRows = rows.filter(r => r.status === 'approved');
  const unmatchedRows = rows.filter(r => r.status === 'unmatched');

  const summaryGrDelta = pendingRows.reduce((s, r) => s + (r.gr_delta || 0), 0);
  const summaryNetDelta = pendingRows.reduce((s, r) => s + (r.net_delta || 0), 0);

  const applyItems = async (itemsToApply) => {
    try {
      const payload = {
        items: itemsToApply.map(r => ({
          item_name: r.item_name,
          new_gr_wt: r.new_gr_wt,
          new_net_wt: r.new_net_wt,
          update_mode: r.update_mode,
        })),
        verification_date: verificationDate,
      };
      const res = await axios.post(`${API}/physical-stock/apply-updates`, payload);
      return res.data;
    } catch (err) {
      throw new Error(err.response?.data?.detail || 'Apply failed');
    }
  };

  const handleApproveSingle = async (itemName) => {
    const row = rows.find(r => r.item_name === itemName && r.status === 'pending');
    if (!row) return;
    setApplying('single');
    try {
      await applyItems([row]);
      setRows(prev => prev.map(r =>
        r.item_name === itemName && r.status === 'pending' ? { ...r, status: 'approved' } : r
      ));
      toast.success(`Updated ${itemName}`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setApplying(null);
    }
  };

  const handleApproveAll = async () => {
    if (pendingRows.length === 0) return;
    setApplying('all');
    try {
      await applyItems(pendingRows);
      setRows(prev => prev.map(r =>
        r.status === 'pending' ? { ...r, status: 'approved' } : r
      ));
      toast.success(`Updated ${pendingRows.length} items`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setApplying(null);
    }
  };

  const handleExport = () => {
    const exportData = rows.map(r => ({
      'Item Name': r.item_name,
      'Stamp': r.stamp || '',
      'Mode': r.update_mode,
      'Old Gross (kg)': (r.old_gr_wt / 1000).toFixed(3),
      'New Gross (kg)': (r.new_gr_wt / 1000).toFixed(3),
      'Gross Delta (kg)': (r.gr_delta / 1000).toFixed(3),
      'Old Net (kg)': (r.old_net_wt / 1000).toFixed(3),
      'New Net (kg)': (r.new_net_wt / 1000).toFixed(3),
      'Net Delta (kg)': (r.net_delta / 1000).toFixed(3),
      'Status': r.status,
    }));
    exportToCSV(exportData, `physical-stock-preview-${verificationDate}`);
  };

  const gToKg = (g) => (g / 1000).toFixed(3);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-[95vw] max-h-[90vh] overflow-hidden flex flex-col" data-testid="physical-stock-preview-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Physical Stock Update Preview
            <Badge variant="outline" className="ml-2">{updateMode === 'gross_only' ? 'Gross Only' : 'Gross + Net'}</Badge>
          </DialogTitle>
          <DialogDescription>
            Verification date: {verificationDate} — Review changes before applying
          </DialogDescription>
        </DialogHeader>

        {/* Summary bar */}
        <div className="flex flex-wrap gap-3 text-sm border rounded-lg p-3 bg-muted/30" data-testid="preview-summary">
          <div>Pending: <strong>{pendingRows.length}</strong></div>
          <div>Approved: <strong className="text-emerald-600">{approvedRows.length}</strong></div>
          <div>Unmatched: <strong className="text-red-600">{unmatchedRows.length}</strong></div>
          <div className="ml-auto flex gap-3">
            <span>Gross delta: <DeltaBadge value={summaryGrDelta / 1000} /></span>
            {updateMode === 'gross_and_net' && (
              <span>Net delta: <DeltaBadge value={summaryNetDelta / 1000} /></span>
            )}
          </div>
        </div>

        {/* Action bar */}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={handleApproveAll}
            disabled={pendingRows.length === 0 || applying !== null}
            data-testid="approve-all-btn"
          >
            <CheckCheck className="h-4 w-4 mr-1" />
            {applying === 'all' ? 'Applying...' : `Approve All (${pendingRows.length})`}
          </Button>
          <Button size="sm" variant="outline" onClick={handleExport} data-testid="export-preview-btn">
            <Download className="h-4 w-4 mr-1" />
            Export CSV
          </Button>
        </div>

        {/* Table */}
        <div className="overflow-auto flex-1 border rounded-lg">
          <Table>
            <TableHeader className="sticky top-0 bg-background z-10">
              <TableRow>
                <TableHead className="min-w-[200px]">Item Name</TableHead>
                <TableHead>Stamp</TableHead>
                <TableHead className="text-right">Old Gross (kg)</TableHead>
                <TableHead className="text-right">New Gross (kg)</TableHead>
                <TableHead className="text-right">Gross Delta</TableHead>
                {updateMode === 'gross_and_net' && (
                  <>
                    <TableHead className="text-right">Old Net (kg)</TableHead>
                    <TableHead className="text-right">New Net (kg)</TableHead>
                    <TableHead className="text-right">Net Delta</TableHead>
                  </>
                )}
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, idx) => (
                <TableRow key={idx} className={row.status === 'unmatched' ? 'bg-red-50 dark:bg-red-950/20' : row.status === 'approved' ? 'bg-emerald-50 dark:bg-emerald-950/20' : ''}>
                  <TableCell className="font-medium text-sm">{row.item_name}</TableCell>
                  <TableCell><Badge variant="outline" className="text-xs">{row.stamp || '—'}</Badge></TableCell>
                  <TableCell className="text-right font-mono text-sm">{gToKg(row.old_gr_wt)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{gToKg(row.new_gr_wt)}</TableCell>
                  <TableCell className="text-right"><DeltaBadge value={row.gr_delta / 1000} /></TableCell>
                  {updateMode === 'gross_and_net' && (
                    <>
                      <TableCell className="text-right font-mono text-sm">{gToKg(row.old_net_wt)}</TableCell>
                      <TableCell className="text-right font-mono text-sm">{gToKg(row.new_net_wt)}</TableCell>
                      <TableCell className="text-right"><DeltaBadge value={row.net_delta / 1000} /></TableCell>
                    </>
                  )}
                  <TableCell>
                    {row.status === 'pending' && <Badge className="bg-amber-500 text-xs">Pending</Badge>}
                    {row.status === 'approved' && <Badge className="bg-emerald-600 text-xs">Approved</Badge>}
                    {row.status === 'unmatched' && (
                      <Badge variant="destructive" className="text-xs">
                        <AlertTriangle className="h-3 w-3 mr-1" />Unmatched
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {row.status === 'pending' && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleApproveSingle(row.item_name)}
                        disabled={applying !== null}
                        data-testid={`approve-row-${idx}`}
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                    )}
                    {row.status === 'approved' && <Check className="h-4 w-4 text-emerald-600" />}
                    {row.status === 'unmatched' && <Minus className="h-4 w-4 text-muted-foreground" />}
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={updateMode === 'gross_and_net' ? 10 : 7} className="text-center py-8 text-muted-foreground">
                    No preview data
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );
}
