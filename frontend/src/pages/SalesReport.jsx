import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { FileText, Calendar, Download, Search, ChevronDown, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { formatIndianCurrency } from '@/utils/formatCurrency';
import { exportToCSV } from '@/utils/exportCSV';
import { useSortableData } from '@/hooks/useSortableData';
import { SortableHeader } from '@/components/SortableHeader';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export default function SalesReport() {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1;

  const [mode, setMode] = useState('month'); // 'month' | 'custom'
  const [year, setYear] = useState(currentYear);
  const [month, setMonth] = useState(currentMonth);
  const [startDate, setStartDate] = useState(`${currentYear}-${String(currentMonth).padStart(2, '0')}-01`);
  const [endDate, setEndDate] = useState(() => {
    const d = new Date(currentYear, currentMonth, 0);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  });

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState('by_stamp'); // 'by_stamp' | 'by_item'
  const [search, setSearch] = useState('');
  const [excludedStamps, setExcludedStamps] = useState(new Set()); // stamps unchecked

  useEffect(() => {
    fetchReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchReport = async (overrides = {}) => {
    setLoading(true);
    setExcludedStamps(new Set());
    const m = overrides.mode ?? mode;
    const y = overrides.year ?? year;
    const mo = overrides.month ?? month;
    const sd = overrides.startDate ?? startDate;
    const ed = overrides.endDate ?? endDate;
    try {
      let url;
      if (m === 'month') {
        url = `${API}/analytics/sales-report?year=${y}&month=${mo}`;
      } else {
        url = `${API}/analytics/sales-report?start_date=${sd}&end_date=${ed}`;
      }
      const r = await axios.get(url);
      setData(r.data);
    } catch (e) {
      console.error('Sales report error:', e);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleMonthClick = (m) => {
    setMonth(m);
    setMode('month');
    fetchReport({ mode: 'month', month: m });
  };

  const handleYearChange = (y) => {
    const yi = parseInt(y, 10);
    setYear(yi);
    fetchReport({ year: yi });
  };

  const toggleStamp = (stampName, checked) => {
    setExcludedStamps((prev) => {
      const next = new Set(prev);
      if (checked) next.delete(stampName);
      else next.add(stampName);
      return next;
    });
  };

  // Items inherit inclusion from their stamp
  const includedItems = useMemo(() => {
    if (!data) return [];
    return (data.by_item || []).filter((it) => !excludedStamps.has(it.stamp));
  }, [data, excludedStamps]);

  const includedStamps = useMemo(() => {
    if (!data) return [];
    return (data.by_stamp || []).filter((s) => !excludedStamps.has(s.stamp));
  }, [data, excludedStamps]);

  // Live totals based on selection
  const totals = useMemo(() => {
    const src = includedStamps;
    return {
      gross_wt_kg: src.reduce((a, r) => a + (r.gross_wt_kg || 0), 0),
      net_wt_kg: src.reduce((a, r) => a + (r.net_wt_kg || 0), 0),
      total_fine_kg: src.reduce((a, r) => a + (r.total_fine_kg || 0), 0),
      total_labour_inr: src.reduce((a, r) => a + (r.total_labour_inr || 0), 0),
      transactions: src.reduce((a, r) => a + (r.transactions || 0), 0),
      // weighted averages
      avg_tunch:
        src.reduce((a, r) => a + (r.avg_tunch || 0) * Math.abs(r.net_wt_kg || 0), 0) /
          (src.reduce((a, r) => a + Math.abs(r.net_wt_kg || 0), 0) || 1),
      avg_labour_per_kg:
        src.reduce((a, r) => a + (r.total_labour_inr || 0), 0) /
          (src.reduce((a, r) => a + Math.abs(r.net_wt_kg || 0), 0) || 1),
    };
  }, [includedStamps]);

  // Natural-sort comparator (Stamp 1, Stamp 2, Stamp 10 ... not Stamp 1, Stamp 10, Stamp 2)
  const naturalCompare = (a, b) =>
    (a || '').localeCompare(b || '', undefined, { numeric: true, sensitivity: 'base' });

  // Search filter (stamps in natural order by default)
  const filteredStamps = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    const base = q ? (data.by_stamp || []).filter((s) => s.stamp.toLowerCase().includes(q)) : (data.by_stamp || []);
    return [...base].sort((a, b) => naturalCompare(a.stamp, b.stamp));
  }, [data, search]);

  const filteredItems = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    if (!q) return data.by_item || [];
    return (data.by_item || []).filter(
      (i) => i.item_name.toLowerCase().includes(q) || (i.stamp || '').toLowerCase().includes(q)
    );
  }, [data, search]);

  const { sortedData: sortedStamps, requestSort: sortStamps, sortConfig: stampSort } =
    useSortableData(filteredStamps, null, 'asc'); // default: preserve natural order
  const { sortedData: sortedItems, requestSort: sortItems, sortConfig: itemSort } =
    useSortableData(filteredItems, 'net_wt_kg', 'desc');

  // Group items by stamp for expandable rows
  const itemsByStamp = useMemo(() => {
    const map = {};
    (data?.by_item || []).forEach((it) => {
      if (!map[it.stamp]) map[it.stamp] = [];
      map[it.stamp].push(it);
    });
    // sort items within each stamp by net_wt_kg desc
    Object.keys(map).forEach((k) => {
      map[k].sort((a, b) => (b.net_wt_kg || 0) - (a.net_wt_kg || 0));
    });
    return map;
  }, [data]);

  const [expandedStamps, setExpandedStamps] = useState(new Set());
  const toggleExpand = (stampName) => {
    setExpandedStamps((prev) => {
      const next = new Set(prev);
      if (next.has(stampName)) next.delete(stampName);
      else next.add(stampName);
      return next;
    });
  };

  const handleExport = () => {
    if (!data) return;
    if (view === 'by_stamp') {
      exportToCSV(
        sortedStamps.map((r) => ({
          ...r,
          included: excludedStamps.has(r.stamp) ? 'No' : 'Yes',
        })),
        `sales_report_by_stamp_${data.period.start_date}_to_${data.period.end_date}.csv`,
        [
          { key: 'included', header: 'Included' },
          { key: 'stamp', header: 'Stamp' },
          { key: 'gross_wt_kg', header: 'Gross Wt (kg)' },
          { key: 'net_wt_kg', header: 'Net Wt (kg)' },
          { key: 'avg_tunch', header: 'Avg Tunch (%)' },
          { key: 'avg_labour_per_kg', header: 'Avg Labour (₹/kg)' },
          { key: 'total_fine_kg', header: 'Total Fine (kg)' },
          { key: 'total_labour_inr', header: 'Total Labour (₹)' },
          { key: 'sale_kg', header: 'Sale (kg)' },
          { key: 'return_kg', header: 'Return (kg)' },
          { key: 'transactions', header: 'Txns' },
          { key: 'items_count', header: 'Items' },
          { key: 'customers_count', header: 'Customers' },
        ]
      );
    } else {
      exportToCSV(
        sortedItems,
        `sales_report_by_item_${data.period.start_date}_to_${data.period.end_date}.csv`,
        [
          { key: 'item_name', header: 'Item' },
          { key: 'stamp', header: 'Stamp' },
          { key: 'gross_wt_kg', header: 'Gross Wt (kg)' },
          { key: 'net_wt_kg', header: 'Net Wt (kg)' },
          { key: 'avg_tunch', header: 'Avg Tunch (%)' },
          { key: 'avg_labour_per_kg', header: 'Avg Labour (₹/kg)' },
          { key: 'total_fine_kg', header: 'Total Fine (kg)' },
          { key: 'total_labour_inr', header: 'Total Labour (₹)' },
          { key: 'sale_kg', header: 'Sale (kg)' },
          { key: 'return_kg', header: 'Return (kg)' },
          { key: 'transactions', header: 'Txns' },
        ]
      );
    }
  };

  const yearOptions = useMemo(() => {
    const arr = [];
    for (let y = currentYear; y >= currentYear - 5; y--) arr.push(y);
    return arr;
  }, [currentYear]);

  return (
    <div className="space-y-6" data-testid="sales-report-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight">Sales Report</h1>
          <p className="text-base text-muted-foreground mt-1">
            Stamp-wise and item-wise sales for any period
          </p>
        </div>
        <Button onClick={handleExport} disabled={!data} data-testid="sales-report-export-btn">
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Period selector */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Period
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Tabs value={mode} onValueChange={setMode} data-testid="sales-report-mode-tabs">
            <TabsList>
              <TabsTrigger value="month" data-testid="mode-month">
                Year + Month
              </TabsTrigger>
              <TabsTrigger value="custom" data-testid="mode-custom">
                Custom Range
              </TabsTrigger>
            </TabsList>

            <TabsContent value="month" className="pt-3 space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <label className="text-sm text-muted-foreground">Year:</label>
                <Select value={String(year)} onValueChange={handleYearChange}>
                  <SelectTrigger className="w-[100px]" data-testid="year-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {yearOptions.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant={month === 0 ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleMonthClick(0)}
                  data-testid="month-all"
                >
                  ALL
                </Button>
                {MONTHS.map((label, idx) => (
                  <Button
                    key={label}
                    variant={month === idx + 1 ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleMonthClick(idx + 1)}
                    data-testid={`month-${idx + 1}`}
                  >
                    {label}
                  </Button>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="custom" className="pt-3">
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="text-sm text-muted-foreground block mb-1">From</label>
                  <Input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-[170px]"
                    data-testid="start-date-input"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground block mb-1">To</label>
                  <Input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-[170px]"
                    data-testid="end-date-input"
                  />
                </div>
                <Button onClick={fetchReport} data-testid="apply-custom-range">
                  Apply
                </Button>
              </div>
            </TabsContent>
          </Tabs>

          {data && (
            <div className="text-xs text-muted-foreground">
              Showing data from <span className="font-mono">{data.period.start_date}</span> to{' '}
              <span className="font-mono">{data.period.end_date}</span>
              {data.excluded_rows > 0 && (
                <Badge variant="outline" className="ml-2">
                  Profit filter applied: {data.excluded_rows} rows excluded ({data.excluded_items_kg.toFixed(3)} kg)
                </Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Totals */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <TotalCard label="Gross Wt" value={`${totals.gross_wt_kg.toFixed(3)} kg`} data-testid="total-gross" />
        <TotalCard label="Net Wt" value={`${totals.net_wt_kg.toFixed(3)} kg`} data-testid="total-net" />
        <TotalCard label="Total Fine" value={`${totals.total_fine_kg.toFixed(3)} kg`} />
        <TotalCard label="Total Labour" value={formatIndianCurrency(totals.total_labour_inr)} />
        <TotalCard label="Avg Tunch" value={`${(totals.avg_tunch || 0).toFixed(2)} %`} />
        <TotalCard
          label="Avg Labour"
          value={`₹${(totals.avg_labour_per_kg || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}/kg`}
        />
      </div>

      {/* Search + view tabs */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs value={view} onValueChange={setView}>
              <TabsList>
                <TabsTrigger value="by_stamp" data-testid="view-by-stamp">
                  By Stamp ({(data?.by_stamp || []).length})
                </TabsTrigger>
                <TabsTrigger value="by_item" data-testid="view-by-item">
                  By Item ({(data?.by_item || []).length})
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 w-[220px]"
                data-testid="sales-report-search"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-10 text-muted-foreground">Loading...</div>
          ) : !data ? (
            <div className="text-center py-10 text-muted-foreground">No data</div>
          ) : view === 'by_stamp' ? (
            <StampTable
              rows={sortedStamps}
              excludedStamps={excludedStamps}
              onToggleStamp={toggleStamp}
              sortConfig={stampSort}
              onSort={sortStamps}
              itemsByStamp={itemsByStamp}
              expandedStamps={expandedStamps}
              onToggleExpand={toggleExpand}
            />
          ) : (
            <ItemTable
              rows={sortedItems}
              excludedStamps={excludedStamps}
              sortConfig={itemSort}
              onSort={sortItems}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TotalCard({ label, value }) {
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-[10px] uppercase text-muted-foreground tracking-wide">{label}</div>
        <div className="text-base sm:text-lg font-bold font-mono mt-1" data-testid={`total-${label.toLowerCase().replace(/\s+/g, '-')}`}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function StampTable({ rows, excludedStamps, onToggleStamp, sortConfig, onSort, itemsByStamp, expandedStamps, onToggleExpand }) {
  if (!rows || rows.length === 0) return <div className="text-muted-foreground text-sm">No data</div>;
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40px]"></TableHead>
            <TableHead className="w-[40px]"></TableHead>
            <SortableHeader label="Stamp" sortKey="stamp" sortConfig={sortConfig} onSort={onSort} />
            <SortableHeader label="Gross Wt (kg)" sortKey="gross_wt_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Net Wt (kg)" sortKey="net_wt_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Avg Tunch %" sortKey="avg_tunch" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Avg Labour ₹/kg" sortKey="avg_labour_per_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Total Fine (kg)" sortKey="total_fine_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Total Labour" sortKey="total_labour_inr" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Sale" sortKey="sale_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Return" sortKey="return_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Txns" sortKey="transactions" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Items" sortKey="items_count" sortConfig={sortConfig} onSort={onSort} className="text-right" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const included = !excludedStamps.has(r.stamp);
            const isExpanded = expandedStamps.has(r.stamp);
            const items = itemsByStamp[r.stamp] || [];
            return (
              <FragmentRow key={r.stamp}>
                <TableRow
                  className={!included ? 'opacity-50' : ''}
                  data-testid={`stamp-row-${r.stamp}`}
                >
                  <TableCell className="w-[40px]">
                    <button
                      onClick={() => onToggleExpand(r.stamp)}
                      className="p-1 hover:bg-muted rounded transition-colors"
                      aria-label={isExpanded ? 'Collapse' : 'Expand'}
                      data-testid={`stamp-expand-${r.stamp}`}
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </button>
                  </TableCell>
                  <TableCell className="w-[40px]">
                    <Checkbox
                      checked={included}
                      onCheckedChange={(v) => onToggleStamp(r.stamp, !!v)}
                      data-testid={`stamp-toggle-${r.stamp}`}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    {r.stamp}
                    {r.stamp === 'Unassigned' && (
                      <Badge variant="outline" className="ml-2 text-[10px]">
                        no stamp assigned
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono">{r.gross_wt_kg.toFixed(3)}</TableCell>
                  <TableCell className="text-right font-mono font-bold">{r.net_wt_kg.toFixed(3)}</TableCell>
                  <TableCell className="text-right font-mono">{r.avg_tunch.toFixed(2)}</TableCell>
                  <TableCell className="text-right font-mono">
                    {r.avg_labour_per_kg.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </TableCell>
                  <TableCell className="text-right font-mono">{r.total_fine_kg.toFixed(3)}</TableCell>
                  <TableCell className="text-right font-mono">{formatIndianCurrency(r.total_labour_inr)}</TableCell>
                  <TableCell className="text-right font-mono text-green-600">{r.sale_kg.toFixed(3)}</TableCell>
                  <TableCell className="text-right font-mono text-red-600">{r.return_kg.toFixed(3)}</TableCell>
                  <TableCell className="text-right font-mono">{r.transactions}</TableCell>
                  <TableCell className="text-right font-mono">{r.items_count}</TableCell>
                </TableRow>
                {isExpanded && items.map((it) => (
                  <TableRow
                    key={`${r.stamp}__${it.item_name}`}
                    className={`bg-muted/30 ${!included ? 'opacity-50' : ''}`}
                    data-testid={`item-sub-row-${it.item_name}`}
                  >
                    <TableCell className="w-[40px]"></TableCell>
                    <TableCell className="w-[40px]"></TableCell>
                    <TableCell className="pl-8 text-sm text-muted-foreground">↳ {it.item_name}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{it.gross_wt_kg.toFixed(3)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{it.net_wt_kg.toFixed(3)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{it.avg_tunch.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {it.avg_labour_per_kg.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">{it.total_fine_kg.toFixed(3)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{formatIndianCurrency(it.total_labour_inr)}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-green-600">{it.sale_kg.toFixed(3)}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-red-600">{it.return_kg.toFixed(3)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{it.transactions}</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                ))}
              </FragmentRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

// Helper: render multiple TableRow children inline (we cannot use a Fragment
// directly inside <TableBody> in shadcn's Table for the key prop case, so we
// just inline render via a function that returns a fragment).
function FragmentRow({ children }) {
  return <>{children}</>;
}

function ItemTable({ rows, excludedStamps, sortConfig, onSort }) {
  if (!rows || rows.length === 0) return <div className="text-muted-foreground text-sm">No data</div>;
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHeader label="Item" sortKey="item_name" sortConfig={sortConfig} onSort={onSort} />
            <SortableHeader label="Stamp" sortKey="stamp" sortConfig={sortConfig} onSort={onSort} />
            <SortableHeader label="Gross Wt (kg)" sortKey="gross_wt_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Net Wt (kg)" sortKey="net_wt_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Avg Tunch %" sortKey="avg_tunch" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Avg Labour ₹/kg" sortKey="avg_labour_per_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Total Fine (kg)" sortKey="total_fine_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Total Labour" sortKey="total_labour_inr" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Sale" sortKey="sale_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Return" sortKey="return_kg" sortConfig={sortConfig} onSort={onSort} className="text-right" />
            <SortableHeader label="Txns" sortKey="transactions" sortConfig={sortConfig} onSort={onSort} className="text-right" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const stampExcluded = excludedStamps.has(r.stamp);
            return (
              <TableRow
                key={r.item_name}
                className={stampExcluded ? 'opacity-50' : ''}
                data-testid={`item-row-${r.item_name}`}
              >
                <TableCell className="font-medium">{r.item_name}</TableCell>
                <TableCell>
                  <Badge variant={r.stamp === 'Unassigned' ? 'outline' : 'secondary'}>{r.stamp}</Badge>
                </TableCell>
                <TableCell className="text-right font-mono">{r.gross_wt_kg.toFixed(3)}</TableCell>
                <TableCell className="text-right font-mono font-bold">{r.net_wt_kg.toFixed(3)}</TableCell>
                <TableCell className="text-right font-mono">{r.avg_tunch.toFixed(2)}</TableCell>
                <TableCell className="text-right font-mono">
                  {r.avg_labour_per_kg.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </TableCell>
                <TableCell className="text-right font-mono">{r.total_fine_kg.toFixed(3)}</TableCell>
                <TableCell className="text-right font-mono">{formatIndianCurrency(r.total_labour_inr)}</TableCell>
                <TableCell className="text-right font-mono text-green-600">{r.sale_kg.toFixed(3)}</TableCell>
                <TableCell className="text-right font-mono text-red-600">{r.return_kg.toFixed(3)}</TableCell>
                <TableCell className="text-right font-mono">{r.transactions}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
