import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ClipboardCheck, AlertTriangle, Calendar, Download, Search } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatIndianCurrency } from '@/utils/formatCurrency';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const todayISO = () => new Date().toISOString().slice(0, 10);
const monthStart = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
};

const csvEscape = (v) => {
  const s = v == null ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

function exportCSV(rows, filename) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')];
  for (const r of rows) lines.push(headers.map((h) => csvEscape(r[h])).join(','));
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export default function SalesReconciliation() {
  const [startDate, setStartDate] = useState(monthStart());
  const [endDate, setEndDate] = useState(todayISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all'); // all | included | excluded | unassigned
  const [search, setSearch] = useState('');

  const fetchReport = async () => {
    if (!startDate || !endDate) {
      toast.error('Both dates are required');
      return;
    }
    setLoading(true);
    try {
      const res = await axios.get(
        `${API}/analytics/sales-reconciliation?start_date=${startDate}&end_date=${endDate}`
      );
      setData(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load reconciliation');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleItems = useMemo(() => {
    if (!data?.items) return [];
    const term = search.trim().toLowerCase();
    return data.items.filter((r) => {
      if (filter === 'excluded' && !r.is_excluded) return false;
      if (filter === 'unassigned' && (!r.is_unassigned || r.is_excluded)) return false;
      if (filter === 'included' && (r.is_excluded || r.is_unassigned)) return false;
      if (term) {
        const blob = `${r.raw_item_name} ${r.leader} ${r.stamp}`.toLowerCase();
        if (!blob.includes(term)) return false;
      }
      return true;
    });
  }, [data, filter, search]);

  const handleExport = () => {
    if (!visibleItems.length) return;
    const rows = visibleItems.map((r) => ({
      'Item Name (raw)': r.raw_item_name,
      'Leader (resolved)': r.leader,
      Stamp: r.stamp,
      Excluded: r.is_excluded ? 'YES' : '',
      Unassigned: r.is_unassigned ? 'YES' : '',
      'Reason (if dropped)': r.excluded_reason || '',
      'Sale Gross (kg)': r.sale_gross_kg,
      'Return Gross (kg)': r.ret_gross_kg,
      'Sale Net (kg)': r.sale_net_kg,
      'Return Net (kg)': r.ret_net_kg,
      'Net After Returns (kg)': r.net_after_returns_kg,
      'Sale Fine (kg)': r.sale_fine_kg,
      'Return Fine (kg)': r.ret_fine_kg,
      'Net Fine (kg)': r.net_fine_kg,
      'Sale Amount (Rs)': r.sale_amount,
      'Return Amount (Rs)': r.ret_amount,
      'Net Amount (Rs)': r.net_amount,
      'Sale Rows': r.sale_rows,
      'Return Rows': r.ret_rows,
      Customers: r.customers,
      'First Date': r.first_date,
      'Last Date': r.last_date,
    }));
    exportCSV(rows, `sales_reconciliation_${startDate}_${endDate}.csv`);
  };

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-5" data-testid="sales-reconciliation-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight flex items-center gap-3">
            <ClipboardCheck className="h-7 w-7 text-primary" />
            Sales Reconciliation
          </h1>
          <p className="text-xs sm:text-base text-muted-foreground mt-1">
            Item-by-item comparison vs Tally — every raw item name listed, with
            its resolved leader, stamp, and whether the analytics pipeline
            silently drops it.
          </p>
        </div>
        <Button
          onClick={handleExport}
          disabled={!visibleItems.length}
          className="gap-2"
          data-testid="recon-export-btn"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Date range picker */}
      <Card className="border-border/40">
        <CardContent className="p-3 sm:p-4 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-muted-foreground font-medium">Start Date</label>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-40 h-9 text-sm font-mono"
              data-testid="recon-start-date"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-muted-foreground font-medium">End Date</label>
            <Input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-40 h-9 text-sm font-mono"
              data-testid="recon-end-date"
            />
          </div>
          <Button
            onClick={fetchReport}
            disabled={loading}
            className="h-9 gap-2"
            data-testid="recon-fetch-btn"
          >
            <Calendar className="h-4 w-4" />
            {loading ? 'Loading…' : 'Run Reconciliation'}
          </Button>
        </CardContent>
      </Card>

      {data && (
        <>
          {/* Headline totals */}
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            <Card data-testid="recon-card-grand">
              <CardHeader className="p-3 pb-1">
                <CardTitle className="text-xs text-muted-foreground font-medium">
                  Grand Net (all items) — match Tally Less
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-0">
                <div className="text-xl font-mono font-bold text-primary">
                  {data.grand_totals_all_items.net_after_returns_kg.toFixed(3)} kg
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Sale {data.grand_totals_all_items.sale_net_kg.toFixed(3)} − Return {data.grand_totals_all_items.ret_net_kg.toFixed(3)}
                </p>
              </CardContent>
            </Card>
            <Card data-testid="recon-card-amount">
              <CardHeader className="p-3 pb-1">
                <CardTitle className="text-xs text-muted-foreground font-medium">Grand Labour / Sale Value</CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-0">
                <div className="text-xl font-mono font-bold text-emerald-600">
                  {formatIndianCurrency(data.grand_totals_all_items.net_amount)}
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Match Tally Total column
                </p>
              </CardContent>
            </Card>
            <Card data-testid="recon-card-excluded">
              <CardHeader className="p-3 pb-1">
                <CardTitle className="text-xs text-muted-foreground font-medium flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3 text-amber-500" />
                  Hidden: EXCLUDED_ITEMS
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-0">
                <div className="text-xl font-mono font-bold text-amber-600">
                  {data.excluded_items_totals.net_after_returns_kg.toFixed(3)} kg
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {data.excluded_items_totals.rows} rows · {formatIndianCurrency(data.excluded_items_totals.net_amount)}
                </p>
              </CardContent>
            </Card>
            <Card data-testid="recon-card-unassigned">
              <CardHeader className="p-3 pb-1">
                <CardTitle className="text-xs text-muted-foreground font-medium flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3 text-red-500" />
                  Hidden: Unassigned stamp
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 pt-0">
                <div className="text-xl font-mono font-bold text-red-600">
                  {data.unassigned_stamp_totals.net_after_returns_kg.toFixed(3)} kg
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {data.unassigned_stamp_totals.rows} rows · {formatIndianCurrency(data.unassigned_stamp_totals.net_amount)}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Explanation */}
          <Card className="border-blue-200 bg-blue-50/50">
            <CardContent className="p-3 text-xs text-blue-900 flex gap-2">
              <ClipboardCheck className="h-4 w-4 shrink-0 mt-0.5" />
              <p>
                <span className="font-semibold">What Dashboard / Profit Analysis see:</span>{' '}
                <span className="font-mono">{data.visible_net_after_returns_kg.toFixed(3)} kg</span> ·{' '}
                Items in the <span className="font-semibold">Excluded</span> or{' '}
                <span className="font-semibold">Unassigned</span> tabs are silently dropped from those pages.
                Map each "Unassigned" row to a stamp in <span className="font-mono">Stamp Mgmt</span> to make it count.
              </p>
            </CardContent>
          </Card>

          {/* Filter / Search */}
          <Card className="border-border/40">
            <CardContent className="p-3 flex flex-wrap items-center justify-between gap-3">
              <Tabs value={filter} onValueChange={setFilter}>
                <TabsList>
                  <TabsTrigger value="all" data-testid="filter-all">
                    All ({data.items.length})
                  </TabsTrigger>
                  <TabsTrigger value="included" data-testid="filter-included">
                    Included
                  </TabsTrigger>
                  <TabsTrigger value="unassigned" data-testid="filter-unassigned">
                    Unassigned
                  </TabsTrigger>
                  <TabsTrigger value="excluded" data-testid="filter-excluded">
                    Excluded
                  </TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="relative">
                <Search className="h-3.5 w-3.5 absolute left-2 top-2.5 text-muted-foreground" />
                <Input
                  placeholder="Search item / leader / stamp..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-64 h-8 text-xs pl-7"
                  data-testid="recon-search"
                />
              </div>
            </CardContent>
          </Card>

          {/* Item table */}
          <Card className="border-border/40">
            <CardHeader className="p-3">
              <CardTitle className="text-sm">Items ({visibleItems.length})</CardTitle>
              <CardDescription className="text-xs">
                Sorted by net weight after returns (highest first).
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-auto max-h-[34rem]">
                <Table className="min-w-[1100px] text-xs">
                  <TableHeader>
                    <TableRow className="bg-muted/40">
                      <TableHead className="text-xs">Item (raw)</TableHead>
                      <TableHead className="text-xs">Leader</TableHead>
                      <TableHead className="text-xs">Stamp</TableHead>
                      <TableHead className="text-xs">Status</TableHead>
                      <TableHead className="text-right text-xs">Sale (kg)</TableHead>
                      <TableHead className="text-right text-xs">Return (kg)</TableHead>
                      <TableHead className="text-right text-xs font-bold">Net (kg)</TableHead>
                      <TableHead className="text-right text-xs">Fine (kg)</TableHead>
                      <TableHead className="text-right text-xs">Net Amount</TableHead>
                      <TableHead className="text-right text-xs">Rows</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {visibleItems.map((r) => (
                      <TableRow
                        key={r.raw_item_name}
                        className={
                          r.is_excluded
                            ? 'bg-amber-50/40 hover:bg-amber-50'
                            : r.is_unassigned
                            ? 'bg-red-50/30 hover:bg-red-50'
                            : 'hover:bg-muted/20'
                        }
                        data-testid={`recon-row-${r.raw_item_name.replace(/\s+/g, '-')}`}
                      >
                        <TableCell className="font-mono font-semibold">{r.raw_item_name}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {r.leader !== r.raw_item_name ? r.leader : <span className="italic text-muted-foreground/60">same</span>}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">{r.stamp || '—'}</Badge>
                        </TableCell>
                        <TableCell>
                          {r.is_excluded ? (
                            <Badge className="bg-amber-500 text-[10px]">EXCLUDED</Badge>
                          ) : r.is_unassigned ? (
                            <Badge className="bg-red-500 text-[10px]">UNASSIGNED</Badge>
                          ) : (
                            <Badge className="bg-emerald-600 text-[10px]">visible</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono">{r.sale_net_kg.toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-red-600">{r.ret_net_kg.toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono font-bold">{r.net_after_returns_kg.toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-blue-600">{r.net_fine_kg.toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono">{formatIndianCurrency(r.net_amount)}</TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {r.sale_rows}{r.ret_rows > 0 && <span className="text-red-500">+{r.ret_rows}</span>}
                        </TableCell>
                      </TableRow>
                    ))}
                    {!visibleItems.length && (
                      <TableRow>
                        <TableCell colSpan={10} className="text-center py-8 text-muted-foreground">
                          No items match this filter.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
