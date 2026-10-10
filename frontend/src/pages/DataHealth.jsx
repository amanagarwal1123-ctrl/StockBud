import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { HeartPulse, RotateCcw, Trash2, ArchiveRestore, Anchor, AlertTriangle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const kg = (g) => ((g || 0) / 1000).toFixed(3);
const fmtDate = (d) => (d ? String(d).slice(0, 10) : '—');

const TxnTable = ({ rows, action, actionLabel, actionIcon: Icon, testPrefix, extraCols }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-xs uppercase text-muted-foreground">
          <th className="px-3 py-2">Item</th>
          <th className="px-3 py-2">Type</th>
          <th className="px-3 py-2">Date</th>
          <th className="px-3 py-2">Party</th>
          <th className="px-3 py-2 text-right">Net (kg)</th>
          <th className="px-3 py-2">Source</th>
          {extraCols && <th className="px-3 py-2">Held By</th>}
          <th className="px-3 py-2" />
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="border-b hover:bg-muted/40" data-testid={`${testPrefix}-row-${r.id}`}>
            <td className="px-3 py-2 font-medium">{r.item_name}
              {r.quarantine_reason === 'upload_guard_overweight' && (
                <Badge variant="destructive" className="ml-2 text-[10px]">held by upload guard</Badge>
              )}
            </td>
            <td className="px-3 py-2">{r.type}</td>
            <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.date)}</td>
            <td className="px-3 py-2">{r.party_name || '—'}</td>
            <td className="px-3 py-2 text-right font-bold tabular-nums text-red-600">{kg(r.net_wt)}</td>
            <td className="px-3 py-2 text-xs">{r.source_collection}</td>
            {extraCols && <td className="px-3 py-2 text-xs">{r.quarantined_by || '—'}</td>}
            <td className="px-3 py-2">
              <Button size="sm" variant="outline" onClick={() => action(r)} data-testid={`${testPrefix}-action-${r.id}`}>
                <Icon className="h-3.5 w-3.5 mr-1" /> {actionLabel}
              </Button>
            </td>
          </tr>
        ))}
        {rows.length === 0 && (
          <tr><td colSpan={8} className="px-3 py-4 text-center text-muted-foreground text-sm">None found</td></tr>
        )}
      </tbody>
    </table>
  </div>
);

export default function DataHealth() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [threshold, setThreshold] = useState('500');

  const fetchData = useCallback(async (th) => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API}/admin/data-health?threshold_kg=${th || 500}`);
      setData(r.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load data health report');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(500); }, [fetchData]);

  const quarantine = async (r) => {
    if (!window.confirm(`Remove "${r.item_name}" (${kg(r.net_wt)} kg, ${r.type}) from live data? It goes to quarantine and can be restored anytime.`)) return;
    try {
      const res = await axios.post(`${API}/admin/data-health/quarantine/${r.id}`);
      toast.success(res.data.message);
      fetchData(threshold);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Remove failed');
    }
  };

  const restore = async (r) => {
    try {
      const res = await axios.post(`${API}/admin/data-health/restore/${r.id}`);
      toast.success(res.data.message);
      fetchData(threshold);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Restore failed');
    }
  };

  const anchor = data?.anchor;

  return (
    <div className="space-y-6" data-testid="data-health-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <HeartPulse className="h-7 w-7 text-rose-500" /> Data Health
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Catch corrupted rows before they distort stock. Removals are reversible (quarantine).
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="text-xs text-muted-foreground">Weight alert threshold (kg)</label>
            <Input type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)}
              className="h-8 w-32" data-testid="threshold-input" />
          </div>
          <Button variant="outline" size="sm" className="h-8" onClick={() => fetchData(threshold)} disabled={loading} data-testid="rescan-btn">
            <RotateCcw className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Rescan
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-300 bg-red-50"><CardContent className="py-4 text-sm text-red-700" data-testid="data-health-error">{error}</CardContent></Card>
      )}

      {anchor && (
        <Card data-testid="anchor-card">
          <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Anchor className="h-4 w-4" /> Opening Stock Anchor</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div><p className="text-xs text-muted-foreground">Anchor date</p><p className="font-bold">{anchor.opening_stock_effective_date || 'Not set'}</p></div>
            <div><p className="text-xs text-muted-foreground">Opening items</p><p className="font-bold tabular-nums">{anchor.opening_items}</p></div>
            <div><p className="text-xs text-muted-foreground">Opening total</p><p className="font-bold tabular-nums">{anchor.opening_total_kg?.toFixed(3)} kg</p></div>
            <div><p className="text-xs text-muted-foreground">Txns counted (after anchor)</p><p className="font-bold tabular-nums">{anchor.transactions_counted_after_anchor ?? '—'}</p></div>
            <div><p className="text-xs text-muted-foreground">Txns excluded (≤ anchor)</p><p className="font-bold tabular-nums">{anchor.transactions_excluded_by_anchor ?? '—'}</p></div>
          </CardContent>
          <CardContent className="pt-0 text-xs text-muted-foreground">
            Current Stock = opening stock on the anchor date + only transactions dated after it. Rows before the anchor never count.
          </CardContent>
        </Card>
      )}

      <Card data-testid="overweight-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-500" />
            Suspicious weights (≥ {data?.overweight?.threshold_kg ?? threshold} kg in one row)
            <Badge variant={data?.overweight?.count ? 'destructive' : 'secondary'} data-testid="overweight-count">{data?.overweight?.count ?? 0}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TxnTable rows={data?.overweight?.rows || []} action={quarantine} actionLabel="Remove" actionIcon={Trash2} testPrefix="ow" />
        </CardContent>
      </Card>

      <Card data-testid="numeric-names-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            Numeric item names (malformed rows)
            <Badge variant={data?.numeric_names?.count ? 'destructive' : 'secondary'} data-testid="numeric-count">{data?.numeric_names?.count ?? 0}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TxnTable rows={data?.numeric_names?.rows || []} action={quarantine} actionLabel="Remove" actionIcon={Trash2} testPrefix="num" />
        </CardContent>
      </Card>

      <Card data-testid="quarantine-section">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            Quarantine (removed / held rows — restorable)
            <Badge variant="secondary" data-testid="quarantine-count">{data?.quarantined?.length ?? 0}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TxnTable rows={data?.quarantined || []} action={restore} actionLabel="Restore" actionIcon={ArchiveRestore} testPrefix="q" extraCols />
        </CardContent>
      </Card>
    </div>
  );
}
