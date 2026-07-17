import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Scale, ArrowUpRight, ArrowDownRight, Anchor, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { formatDateTime } from '../utils/dateFormat';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TYPE_LABELS = {
  sale: 'Sale', sale_return: 'Sale Return',
  purchase: 'Purchase', purchase_return: 'Purchase Return',
  issue: 'Issue', receive: 'Receive',
};

const kindOf = (types) => {
  if (types.includes('purchase')) return { label: 'Purchases', cls: 'bg-emerald-100 text-emerald-800' };
  if (types.includes('sale')) return { label: 'Sales', cls: 'bg-blue-100 text-blue-800' };
  return { label: 'Branch Transfer', cls: 'bg-amber-100 text-amber-800' };
};

const fmtKg = (v) => `${v > 0 ? '+' : ''}${v.toFixed(3)} kg`;

export default function StockAudit() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { isAdmin } = useAuth();

  const fetchAudit = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/stock-audit/uploads`);
      setData(res.data);
    } catch (e) {
      console.error('Error fetching stock audit:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (isAdmin) fetchAudit(); }, [isAdmin]);

  if (!isAdmin) return null;

  return (
    <div className="space-y-6" data-testid="stock-audit-page">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Stock Movement Audit</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Exact net-stock effect of every upload — what was added, what was replaced, and the resulting change.
            Sale, Sale Return, Purchase, Purchase Return, Issue and Receive are all counted.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAudit} data-testid="stock-audit-refresh-btn">
          <RefreshCw className="h-4 w-4 mr-2" /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium text-muted-foreground">Uploads Shown</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold" data-testid="stock-audit-upload-count">{data?.uploads?.length ?? '—'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium text-muted-foreground">Combined Net Movement</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold font-mono ${(data?.total_net_change_kg ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}
               data-testid="stock-audit-total-movement">
              {data ? fmtKg(data.total_net_change_kg) : '—'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
              <Anchor className="h-3.5 w-3.5" /> Opening Stock Anchor
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold font-mono" data-testid="stock-audit-anchor-date">{data?.anchor_date || 'Not set'}</p>
            <p className="text-xs text-muted-foreground mt-1">Transactions on/before this date don't affect stock</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg"><Scale className="h-5 w-5" /> Upload Impact History</CardTitle>
          <CardDescription>Net Change = effect of new rows − effect of the old rows they replaced (for the same dates)</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Loading audit trail...</p>
          ) : !data?.uploads?.length ? (
            <p className="text-sm text-muted-foreground py-8 text-center">No uploads found</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Uploaded At</TableHead>
                    <TableHead className="text-xs">Data</TableHead>
                    <TableHead className="text-xs">Voucher Dates</TableHead>
                    <TableHead className="text-xs text-right">Rows In / Replaced</TableHead>
                    <TableHead className="text-xs">Type Breakdown (net kg)</TableHead>
                    <TableHead className="text-xs text-right">Net Change</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.uploads.map((u) => {
                    const kind = kindOf(u.types);
                    return (
                      <TableRow key={u.batch_id} data-testid={`stock-audit-row-${u.batch_id.slice(0, 8)}`}>
                        <TableCell className="text-xs whitespace-nowrap">{formatDateTime(u.uploaded_at)}</TableCell>
                        <TableCell><Badge className={`${kind.cls} hover:${kind.cls}`}>{kind.label}</Badge></TableCell>
                        <TableCell className="text-xs font-mono whitespace-nowrap">
                          {u.date_min === u.date_max ? u.date_min : `${u.date_min} → ${u.date_max}`}
                        </TableCell>
                        <TableCell className="text-xs text-right font-mono whitespace-nowrap">
                          {u.rows_inserted.toLocaleString()} / {u.rows_replaced.toLocaleString()}
                          {u.rows_before_anchor > 0 && (
                            <span className="block text-[10px] text-muted-foreground">
                              {u.rows_before_anchor.toLocaleString()} before anchor (not counted)
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(u.by_type).map(([t, v]) => (
                              <span key={t}
                                className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${v.net_kg >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
                                {TYPE_LABELS[t] || t}: {fmtKg(v.net_kg)}
                              </span>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap">
                          <span className={`inline-flex items-center gap-1 font-mono font-semibold text-sm ${u.net_change_kg >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            {u.net_change_kg >= 0 ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
                            {fmtKg(u.net_change_kg)}
                          </span>
                          {u.rows_replaced > 0 && (
                            <span className="block text-[10px] text-muted-foreground font-mono">
                              new {fmtKg(u.inserted_net_kg)} − old {fmtKg(u.replaced_net_kg)}
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
