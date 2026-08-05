import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { FileText, ArrowUpDown, ArrowUp, ArrowDown, Tag, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

function getWindow() {
  const today = new Date();
  const sixtyBack = new Date(today); sixtyBack.setDate(today.getDate() - 60);
  const firstPrev = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  const earliest = sixtyBack < firstPrev ? sixtyBack : firstPrev;
  return { earliest: fmt(earliest), latest: fmt(today) };
}

function SortHeader({ label, field, sort, onSort, align = 'right', testid }) {
  const active = sort.field === field;
  const Icon = !active ? ArrowUpDown : (sort.dir === 'asc' ? ArrowUp : ArrowDown);
  return (
    <TableHead className={align === 'right' ? 'text-right' : ''}>
      <button onClick={() => onSort(field)} data-testid={testid}
        className={`inline-flex items-center gap-1 hover:text-foreground ${active ? 'text-foreground font-semibold' : ''}`}>
        {label}<Icon className="h-3.5 w-3.5" />
      </button>
    </TableHead>
  );
}

export default function ManagerSalesView() {
  const win = useMemo(getWindow, []);
  const today = new Date();
  const [view, setView] = useState('by_item');
  const [period, setPeriod] = useState('this_month');
  const [startDate, setStartDate] = useState(fmt(new Date(today.getFullYear(), today.getMonth(), 1)));
  const [endDate, setEndDate] = useState(win.latest);
  const [customStart, setCustomStart] = useState(win.earliest);
  const [customEnd, setCustomEnd] = useState(win.latest);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState({ field: 'net_wt_kg', dir: 'desc' });

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${API}/analytics/sales-manager-report`, {
          params: { start_date: startDate, end_date: endDate }
        });
        setData(res.data);
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to load sales data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [startDate, endDate]);

  const selectThisMonth = () => {
    setPeriod('this_month');
    const d = new Date();
    setStartDate(fmt(new Date(d.getFullYear(), d.getMonth(), 1)));
    setEndDate(fmt(d));
  };
  const selectLastMonth = () => {
    setPeriod('last_month');
    const d = new Date();
    const first = new Date(d.getFullYear(), d.getMonth() - 1, 1);
    const last = new Date(d.getFullYear(), d.getMonth(), 0);
    const sd = fmt(first) < win.earliest ? win.earliest : fmt(first);
    setStartDate(sd);
    setEndDate(fmt(last));
  };
  const applyCustom = () => {
    if (!customStart || !customEnd) { toast.error('Pick both dates'); return; }
    if (customStart > customEnd) { toast.error('Start date must be before end date'); return; }
    if (customStart < win.earliest || customEnd > win.latest) {
      toast.error(`Only the last 2 months are viewable (${win.earliest} to ${win.latest})`);
      return;
    }
    setPeriod('custom');
    setStartDate(customStart);
    setEndDate(customEnd);
  };

  const onSort = (field) => {
    setSort(prev => prev.field === field
      ? { field, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: field === 'name' ? 'asc' : 'desc' });
  };

  const rows = useMemo(() => {
    if (!data) return [];
    const src = view === 'by_item' ? (data.by_item || []) : (data.by_stamp || []);
    const nameKey = view === 'by_item' ? 'item_name' : 'stamp';
    const sorted = [...src].sort((a, b) => {
      let cmp;
      if (sort.field === 'name') cmp = (a[nameKey] || '').localeCompare(b[nameKey] || '');
      else cmp = (a[sort.field] || 0) - (b[sort.field] || 0);
      return sort.dir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [data, view, sort]);

  const nameKey = view === 'by_item' ? 'item_name' : 'stamp';

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="manager-sales-page">
      <div>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight flex items-center gap-2">
          <FileText className="h-8 w-8 text-indigo-600" />Sales View
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Gross &amp; net sold weight for your assigned stamps — last 2 months only ({win.earliest} → {win.latest})
        </p>
      </div>

      {data?.assigned_stamps?.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <Tag className="h-4 w-4 text-muted-foreground" />
          {data.assigned_stamps.map(s => (
            <Badge key={s} variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200" data-testid={`assigned-stamp-chip-${s}`}>{s}</Badge>
          ))}
        </div>
      )}

      {data?.no_stamps_assigned && !loading && (
        <Card className="border-amber-300 bg-amber-50" data-testid="no-stamps-alert">
          <CardContent className="pt-6 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
            <div>
              <p className="font-medium text-amber-800">No stamps assigned to you yet</p>
              <p className="text-sm text-amber-700">Ask the admin to assign stamps to your account from Stamp Assign.</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Period controls */}
      <Card>
        <CardContent className="pt-4 pb-4 flex flex-col sm:flex-row flex-wrap gap-3 items-start sm:items-end">
          <div className="flex gap-2">
            <Button size="sm" variant={period === 'this_month' ? 'default' : 'outline'} onClick={selectThisMonth} data-testid="period-this-month">This Month</Button>
            <Button size="sm" variant={period === 'last_month' ? 'default' : 'outline'} onClick={selectLastMonth} data-testid="period-last-month">Last Month</Button>
          </div>
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">From</label>
              <Input type="date" value={customStart} min={win.earliest} max={win.latest}
                onChange={e => setCustomStart(e.target.value)} className="h-9 w-40" data-testid="custom-start-date" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">To</label>
              <Input type="date" value={customEnd} min={win.earliest} max={win.latest}
                onChange={e => setCustomEnd(e.target.value)} className="h-9 w-40" data-testid="custom-end-date" />
            </div>
            <Button size="sm" variant={period === 'custom' ? 'default' : 'secondary'} onClick={applyCustom} data-testid="custom-apply-btn">Apply</Button>
          </div>
          <div className="text-xs text-muted-foreground sm:ml-auto" data-testid="active-period-label">
            Showing: {startDate} → {endDate}
          </div>
        </CardContent>
      </Card>

      {/* Totals */}
      <div className="grid grid-cols-2 gap-3 sm:max-w-md">
        <Card>
          <CardContent className="pt-4 pb-4">
            <p className="text-xs text-muted-foreground">Total Gross Wt</p>
            <p className="text-2xl font-bold" data-testid="total-gross">{loading ? '…' : `${(data?.totals?.gross_wt_kg ?? 0).toFixed(3)} kg`}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <p className="text-xs text-muted-foreground">Total Net Wt</p>
            <p className="text-2xl font-bold" data-testid="total-net">{loading ? '…' : `${(data?.totals?.net_wt_kg ?? 0).toFixed(3)} kg`}</p>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-base">Sales {view === 'by_item' ? 'by Item' : 'by Stamp'}</CardTitle>
          <Tabs value={view} onValueChange={setView}>
            <TabsList>
              <TabsTrigger value="by_item" data-testid="sales-view-tab-item">By Item</TabsTrigger>
              <TabsTrigger value="by_stamp" data-testid="sales-view-tab-stamp">By Stamp</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-10 text-center text-muted-foreground">Loading...</div>
          ) : rows.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground" data-testid="no-sales-rows">No sales in this period</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortHeader label={view === 'by_item' ? 'Item' : 'Stamp'} field="name" sort={sort} onSort={onSort} align="left" testid="sort-name" />
                    {view === 'by_item' && <TableHead>Stamp</TableHead>}
                    <SortHeader label="Gross Wt (kg)" field="gross_wt_kg" sort={sort} onSort={onSort} testid="sort-gross" />
                    <SortHeader label="Net Wt (kg)" field="net_wt_kg" sort={sort} onSort={onSort} testid="sort-net" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r, idx) => (
                    <TableRow key={r[nameKey]} data-testid={`sales-row-${idx}`}>
                      <TableCell className="font-medium">{r[nameKey]}</TableCell>
                      {view === 'by_item' && (
                        <TableCell><Badge variant="outline" className="text-xs">{r.stamp}</Badge></TableCell>
                      )}
                      <TableCell className="text-right tabular-nums">{r.gross_wt_kg.toFixed(3)}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.net_wt_kg.toFixed(3)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
