import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog';
import { PackageX, ArrowUp, ArrowDown, RotateCcw, Trash2, ArchiveRestore } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const fmtDate = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : '—');
const INF = Number.POSITIVE_INFINITY;

const COLS = [
  { key: 'item_name', label: 'Item', align: 'left' },
  { key: 'stamp', label: 'Stamp', align: 'left' },
  { key: 'stock_net_kg', label: 'Stock (kg)', align: 'right' },
  { key: 'sold_net_kg', label: 'Sold (kg)', align: 'right' },
  { key: 'avg_monthly_sale_kg', label: 'Avg Monthly (kg)', align: 'right' },
  { key: 'stock_sale_ratio', label: 'Stock:Sale (months)', align: 'right' },
  { key: 'last_sale_date', label: 'Last Sale', align: 'right' },
];

export default function DeadItems() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [threshold, setThreshold] = useState(3);
  const [sort, setSort] = useState({ key: 'stock_sale_ratio', dir: 'desc' });
  const [showRemoved, setShowRemoved] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/analytics/dead-items`);
      setData(r.data);
    } catch (e) {
      if (e.response?.status === 503) toast.error('Server is busy — please try again in a few seconds.');
      else toast.error('Failed to load dead items');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const sortVal = (r, key) => {
    const v = r[key];
    if (key === 'stock_sale_ratio') return v === null || v === undefined ? INF : v;
    if (v === null || v === undefined) return typeof r.stock_net_kg === 'number' ? '' : 0;
    return v;
  };

  const deadRows = useMemo(() => {
    if (!data) return [];
    const th = parseFloat(threshold);
    const lim = isNaN(th) ? 3 : th;
    const rows = data.items.filter((r) => r.stock_sale_ratio === null || r.stock_sale_ratio >= lim);
    const dirMul = sort.dir === 'asc' ? 1 : -1;
    rows.sort((a, b) => {
      const va = sortVal(a, sort.key); const vb = sortVal(b, sort.key);
      if (typeof va === 'string' || typeof vb === 'string') return String(va).localeCompare(String(vb)) * dirMul;
      return (va - vb) * dirMul;
    });
    return rows;
  }, [data, threshold, sort]);

  const totalDeadStock = useMemo(() => deadRows.reduce((s, r) => s + r.stock_net_kg, 0), [deadRows]);

  const toggleSort = (key) => {
    setSort((p) => (p.key === key ? { key, dir: p.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' }));
  };

  const removeItem = async (name) => {
    try {
      await axios.post(`${API}/dead-items/remove`, { item_name: name });
      setData((p) => {
        const row = p.items.find((r) => r.item_name === name);
        return { ...p, items: p.items.filter((r) => r.item_name !== name), removed: [...p.removed, row] };
      });
      toast.success(`"${name}" removed from dead items list`);
    } catch (e) {
      toast.error('Failed to remove item');
    }
  };

  const restoreItem = async (name) => {
    try {
      await axios.post(`${API}/dead-items/restore`, { item_name: name });
      setData((p) => {
        const row = p.removed.find((r) => r.item_name === name);
        return { ...p, removed: p.removed.filter((r) => r.item_name !== name), items: [...p.items, row] };
      });
      toast.success(`"${name}" restored to the list`);
    } catch (e) {
      toast.error('Failed to restore item');
    }
  };

  return (
    <div className="space-y-5" data-testid="dead-items-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <PackageX className="h-7 w-7 text-destructive" /> Dead Items
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Current stock (mapped items &amp; groups merged) vs avg monthly sales since {fmtDate(data?.baseline_date)} baseline.
            Ratio = months to clear stock at that pace — below {threshold || 3} is healthy.
          </p>
        </div>
        <button
          onClick={() => setShowRemoved(true)}
          className="text-xs text-primary underline underline-offset-4 hover:opacity-80 mt-1"
          data-testid="removed-items-link"
        >
          Removed items ({data?.removed?.length ?? 0})
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Dead if ratio ≥</span>
          <Input
            type="number" min="0.5" step="0.5" value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className="h-8 w-20" data-testid="threshold-input"
          />
          <span className="text-xs text-muted-foreground">months</span>
        </div>
        <Badge variant="secondary" data-testid="dead-count-badge">{deadRows.length} dead items</Badge>
        <Badge variant="outline" data-testid="dead-stock-badge">{totalDeadStock.toFixed(3)} kg stuck</Badge>
        <Button variant="outline" size="sm" className="h-8" onClick={fetchData} disabled={loading} data-testid="refresh-dead-items">
          <RotateCcw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      <Card className="border-border/30 shadow-sm">
        <CardContent className="p-0 overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-sm text-muted-foreground">Analysing stock vs sales across all years…</div>
          ) : (
            <table className="w-full text-sm" data-testid="dead-items-table">
              <thead>
                <tr className="border-b border-border/40 bg-muted/40">
                  {COLS.map((c) => (
                    <th
                      key={c.key}
                      onClick={() => toggleSort(c.key)}
                      className={`px-3 py-2.5 text-xs font-semibold cursor-pointer select-none whitespace-nowrap ${c.align === 'right' ? 'text-right' : 'text-left'}`}
                      data-testid={`sort-${c.key}`}
                    >
                      {c.label}
                      {sort.key === c.key && (sort.dir === 'desc'
                        ? <ArrowDown className="inline h-3 w-3 ml-0.5" />
                        : <ArrowUp className="inline h-3 w-3 ml-0.5" />)}
                    </th>
                  ))}
                  <th className="px-3 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {deadRows.map((r) => (
                  <tr key={r.item_name} className="border-b border-border/20 hover:bg-muted/30" data-testid={`dead-row-${r.item_name}`}>
                    <td className="px-3 py-2">
                      <div className="font-medium">{r.item_name}</div>
                      {r.merged_names?.length > 0 && (
                        <div className="text-[11px] text-muted-foreground truncate max-w-[260px]">
                          incl. {r.merged_names.join(', ')}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{r.stamp}</td>
                    <td className="px-3 py-2 text-right font-semibold tabular-nums">{r.stock_net_kg.toFixed(3)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.sold_net_kg.toFixed(3)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.avg_monthly_sale_kg.toFixed(3)}</td>
                    <td className="px-3 py-2 text-right">
                      {r.stock_sale_ratio === null
                        ? <Badge variant="destructive" className="text-[10px]">Never sold</Badge>
                        : <span className="font-bold tabular-nums">{r.stock_sale_ratio.toFixed(2)}</span>}
                    </td>
                    <td className="px-3 py-2 text-right text-xs whitespace-nowrap">{fmtDate(r.last_sale_date)}</td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        variant="ghost" size="sm" className="h-7 text-destructive"
                        onClick={() => removeItem(r.item_name)}
                        data-testid={`remove-dead-${r.item_name}`}
                        title="Remove from this list (restorable)"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
                {deadRows.length === 0 && (
                  <tr><td colSpan={8} className="p-8 text-center text-sm text-muted-foreground">No dead items above this threshold 🎉</td></tr>
                )}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Dialog open={showRemoved} onOpenChange={setShowRemoved}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="removed-items-dialog">
          <DialogHeader>
            <DialogTitle>Removed Items</DialogTitle>
            <DialogDescription>Items you removed from the dead list (e.g., stock remains only due to data errors). Restore any time.</DialogDescription>
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
                      stock {r.stock_net_kg?.toFixed(3)} kg · removed by {r.removed_by || '—'}
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
