import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog';
import { PackageX, ArrowUp, ArrowDown, RotateCcw, Trash2, ArchiveRestore, AlertTriangle, Sparkles } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const fmtDate = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : '—');
const INF = Number.POSITIVE_INFINITY;

const COLS = [
  { key: 'item_name', label: 'Item', align: 'left' },
  { key: 'stock_net_kg', label: 'Stock (kg)', align: 'right' },
  { key: 'first_purchase', label: 'First Purchase', align: 'right' },
  { key: 'observed_days', label: 'Days', align: 'right' },
  { key: 'total_net_sales_kg', label: 'Net Sales (kg)', align: 'right' },
  { key: 'avg_monthly_sale_kg', label: 'Avg Monthly (kg)', align: 'right' },
  { key: 'months_to_clear', label: 'Months to Clear', align: 'right' },
  { key: 'sales_90d_kg', label: 'Last 90d (kg)', align: 'right' },
  { key: 'last_sale_date', label: 'Last Sale', align: 'right' },
];

const StatusBadge = ({ r }) => {
  if (r.status === 'never_sold') return <Badge variant="destructive" className="text-[10px]">Never sold</Badge>;
  if (r.status === 'no_positive_net_sales') return <Badge variant="destructive" className="text-[10px] bg-orange-600">No positive net sales</Badge>;
  return <span className="font-bold tabular-nums">{r.months_to_clear?.toFixed(3)}</span>;
};

export default function DeadItems() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [threshold, setThreshold] = useState(3);
  const [asOf, setAsOf] = useState('');
  const [sort, setSort] = useState(null); // null = spec default ranking
  const [showRemoved, setShowRemoved] = useState(false);

  const fetchData = useCallback(async (asOfParam) => {
    setLoading(true);
    setError(null);
    try {
      const q = asOfParam ? `?as_of=${asOfParam}` : '';
      const r = await axios.get(`${API}/analytics/dead-items${q}`);
      setData(r.data);
      if (!asOfParam) setAsOf(r.data.as_of);
    } catch (e) {
      const msg = e.response?.status === 503
        ? 'Server is busy — please retry in a few seconds.'
        : (e.response?.data?.detail || 'Failed to load dead items');
      setError(msg);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const th = (() => { const v = parseFloat(threshold); return isNaN(v) ? 3 : v; })();

  const rank = (rows) => {
    const noSales = rows.filter((r) => r.status !== 'ok');
    const scored = rows.filter((r) => r.status === 'ok');
    const tie = (a, b) =>
      String(a.last_sale_date || '0000').localeCompare(String(b.last_sale_date || '0000')) ||
      (b.stock_net_kg - a.stock_net_kg);
    noSales.sort(tie);
    scored.sort((a, b) => (b.months_to_clear - a.months_to_clear) || tie(a, b));
    return [...noSales, ...scored];
  };

  const { deadRows, provisionalRows } = useMemo(() => {
    if (!data) return { deadRows: [], provisionalRows: [] };
    const eligible = data.items.filter((r) =>
      r.status !== 'ok' || (r.months_to_clear !== null && r.months_to_clear >= th));
    let dead = rank(eligible.filter((r) => !r.provisional));
    const prov = rank(eligible.filter((r) => r.provisional));
    if (sort) {
      const dir = sort.dir === 'asc' ? 1 : -1;
      const val = (r) => {
        const v = r[sort.key];
        if (sort.key === 'months_to_clear') return v === null ? INF : v;
        return v === null || v === undefined ? '' : v;
      };
      dead = [...dead].sort((a, b) => {
        const va = val(a); const vb = val(b);
        if (typeof va === 'string' || typeof vb === 'string') return String(va).localeCompare(String(vb)) * dir;
        return (va - vb) * dir;
      });
    }
    return { deadRows: dead, provisionalRows: prov };
  }, [data, th, sort]);

  const toggleSort = (key) => {
    setSort((p) => (p?.key === key ? (p.dir === 'desc' ? { key, dir: 'asc' } : null) : { key, dir: 'desc' }));
  };

  const removeItem = async (name) => {
    try {
      await axios.post(`${API}/dead-items/remove`, { item_name: name });
      fetchData(asOf);
      toast.success(`"${name}" removed from dead items list`);
    } catch (e) { toast.error('Failed to remove item'); }
  };

  const restoreItem = async (name) => {
    try {
      await axios.post(`${API}/dead-items/restore`, { item_name: name });
      fetchData(asOf);
      toast.success(`"${name}" restored`);
    } catch (e) { toast.error('Failed to restore item'); }
  };

  const renderRow = (r, extra) => (
    <tr key={r.item_name} className="border-b border-border/20 hover:bg-muted/30" data-testid={`dead-row-${r.item_name}`}>
      <td className="px-3 py-2">
        <div className="font-medium flex items-center gap-2">
          {r.item_name}
          {r.provisional && <Badge variant="outline" className="text-[10px] border-sky-500 text-sky-600">New/provisional</Badge>}
        </div>
        {r.merged_names?.length > 0 && (
          <div className="text-[11px] text-muted-foreground truncate max-w-[240px]">incl. {r.merged_names.join(', ')}</div>
        )}
        {extra}
      </td>
      <td className="px-3 py-2 text-right font-semibold tabular-nums">{r.stock_net_kg.toFixed(3)}</td>
      <td className="px-3 py-2 text-right text-xs whitespace-nowrap">{fmtDate(r.first_purchase)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{r.observed_days ?? '—'}</td>
      <td className="px-3 py-2 text-right tabular-nums">{r.total_net_sales_kg.toFixed(3)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{r.avg_monthly_sale_kg === null ? '—' : r.avg_monthly_sale_kg.toFixed(3)}</td>
      <td className="px-3 py-2 text-right"><StatusBadge r={r} /></td>
      <td className="px-3 py-2 text-right tabular-nums">{r.sales_90d_kg.toFixed(3)}</td>
      <td className="px-3 py-2 text-right text-xs whitespace-nowrap">{fmtDate(r.last_sale_date)}</td>
      <td className="px-3 py-2 text-right">
        <Button variant="ghost" size="sm" className="h-7 text-destructive" onClick={() => removeItem(r.item_name)}
          data-testid={`remove-dead-${r.item_name}`} title="Remove from this list (restorable)">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </td>
    </tr>
  );

  const tableHead = (
    <thead>
      <tr className="border-b border-border/40 bg-muted/40">
        {COLS.map((c) => (
          <th key={c.key} onClick={() => toggleSort(c.key)}
            className={`px-3 py-2.5 text-xs font-semibold cursor-pointer select-none whitespace-nowrap ${c.align === 'right' ? 'text-right' : 'text-left'}`}
            data-testid={`sort-${c.key}`}>
            {c.label}
            {sort?.key === c.key && (sort.dir === 'desc' ? <ArrowDown className="inline h-3 w-3 ml-0.5" /> : <ArrowUp className="inline h-3 w-3 ml-0.5" />)}
          </th>
        ))}
        <th className="px-3 py-2.5" />
      </tr>
    </thead>
  );

  return (
    <div className="space-y-5" data-testid="dead-items-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <PackageX className="h-7 w-7 text-destructive" /> Dead Items
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.method || 'First recorded purchase / zero-opening estimate'} — analytical stock, not operational stock.
            Months to Clear: lower = faster-moving, higher = slower-moving.
          </p>
          {data && data.last_txn_date && data.as_of > data.last_txn_date && (
            <p className="text-xs text-amber-600 mt-1" data-testid="coverage-note">
              Coverage unverified after {fmtDate(data.last_txn_date)} (last transaction on record).
            </p>
          )}
        </div>
        <button onClick={() => setShowRemoved(true)}
          className="text-xs text-primary underline underline-offset-4 hover:opacity-80 mt-1"
          data-testid="removed-items-link">
          Removed items ({data?.removed?.length ?? 0})
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">As-of</span>
          <Input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)}
            onBlur={() => asOf && fetchData(asOf)} className="h-8 w-40" data-testid="as-of-input" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Dead if ≥</span>
          <Input type="number" min="0.5" step="0.5" value={threshold}
            onChange={(e) => setThreshold(e.target.value)} className="h-8 w-20" data-testid="threshold-input" />
          <span className="text-xs text-muted-foreground">months to clear</span>
        </div>
        {data && (
          <>
            <Badge variant="secondary" data-testid="dead-count-badge">{deadRows.length} dead items</Badge>
            {provisionalRows.length > 0 && (
              <Badge variant="outline" className="border-sky-500 text-sky-600" data-testid="provisional-count-badge">
                {provisionalRows.length} new/provisional
              </Badge>
            )}
            {(data.review?.length ?? 0) > 0 && (
              <Badge variant="outline" className="border-amber-500 text-amber-600" data-testid="review-count-badge">
                {data.review.length} need history review
              </Badge>
            )}
          </>
        )}
        <Button variant="outline" size="sm" className="h-8" onClick={() => fetchData(asOf)} disabled={loading} data-testid="refresh-dead-items">
          <RotateCcw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/40">
          <CardContent className="p-6 text-center space-y-3" data-testid="dead-items-error">
            <p className="text-sm text-destructive font-medium">{error}</p>
            <Button variant="outline" size="sm" onClick={() => fetchData(asOf)} data-testid="retry-dead-items">
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" /> Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {!error && (
        <Card className="border-border/30 shadow-sm">
          <CardContent className="p-0 overflow-x-auto">
            {loading ? (
              <div className="p-8 text-center text-sm text-muted-foreground">Reconstructing analytical stock from each item's first recorded purchase…</div>
            ) : (
              <table className="w-full text-sm" data-testid="dead-items-table">
                {tableHead}
                <tbody>
                  {deadRows.map((r) => renderRow(r))}
                  {deadRows.length === 0 && (
                    <tr><td colSpan={10} className="p-8 text-center text-sm text-muted-foreground">No confirmed dead items at this threshold</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {!error && !loading && provisionalRows.length > 0 && (
        <div className="space-y-2" data-testid="provisional-section">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-sky-500" /> New / Provisional (under 30 observed days)
          </h2>
          <Card className="border-sky-500/30 shadow-sm">
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-sm" data-testid="provisional-table">
                {tableHead}
                <tbody>{provisionalRows.map((r) => renderRow(r))}</tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {!error && !loading && (data?.review?.length ?? 0) > 0 && (
        <div className="space-y-2" data-testid="review-section">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" /> Needs History Review
          </h2>
          <p className="text-xs text-muted-foreground">
            These items have incomplete or ambiguous history (no purchase anchor, movements before first purchase,
            negative reconstructed stock, or overlapping sources). Their numbers are shown but excluded from the dead ranking.
          </p>
          <Card className="border-amber-500/30 shadow-sm">
            <CardContent className="p-0 overflow-x-auto">
              <table className="w-full text-sm" data-testid="review-table">
                {tableHead}
                <tbody>
                  {data.review.map((r) => renderRow(r, (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {r.review_reasons.map((reason) => (
                        <Badge key={reason} variant="outline" className="text-[10px] border-amber-500 text-amber-600">
                          {reason.replaceAll('_', ' ')}
                        </Badge>
                      ))}
                    </div>
                  )))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      <Dialog open={showRemoved} onOpenChange={setShowRemoved}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="removed-items-dialog">
          <DialogHeader>
            <DialogTitle>Removed Items</DialogTitle>
            <DialogDescription>Items you removed from the dead list. Restore any time.</DialogDescription>
          </DialogHeader>
          {(data?.removed?.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground py-4">Nothing removed yet.</p>
          ) : (
            <div className="space-y-2">
              {data.removed.map((r) => (
                <div key={r.item_name} className="flex items-center justify-between gap-3 border border-border/30 rounded-md px-3 py-2" data-testid={`removed-row-${r.item_name}`}>
                  <div>
                    <p className="text-sm font-medium">{r.item_name}</p>
                    <p className="text-[11px] text-muted-foreground">
                      analytical stock {r.stock_net_kg?.toFixed(3)} kg · removed by {r.removed_by || '—'}
                    </p>
                  </div>
                  <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => restoreItem(r.item_name)} data-testid={`restore-dead-${r.item_name}`}>
                    <ArchiveRestore className="h-3.5 w-3.5 mr-1.5" /> Restore
                  </Button>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
