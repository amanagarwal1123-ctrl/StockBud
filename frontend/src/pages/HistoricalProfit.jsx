import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { TrendingUp, Users, Package, Calendar, IndianRupee, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const VIEWS = [
  { value: 'yearly', label: 'Yearly Summary', icon: TrendingUp },
  { value: 'customer', label: 'Customer-wise', icon: Users },
  { value: 'supplier', label: 'Supplier-wise', icon: Package },
  { value: 'item', label: 'Item-wise', icon: Package },
  { value: 'month', label: 'Month-wise', icon: Calendar },
];

const fmt = (v) => v?.toLocaleString('en-IN', { maximumFractionDigits: 2 }) ?? '0';
const fmtKg = (v) => `${fmt(v)} kg`;
const fmtInr = (v) => `₹${fmt(v)}`;

export default function HistoricalProfit({ years = [] }) {
  const [view, setView] = useState('yearly');
  const [year, setYear] = useState(years[0] || '2025');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('silver_profit_kg');
  const [sortAsc, setSortAsc] = useState(false);

  const fetchProfit = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/analytics/historical-profit?year=${year}&view=${view}`);
      setData(res.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [year, view]);

  useEffect(() => { fetchProfit(); }, [fetchProfit]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const SortIcon = ({ col }) => sortKey === col
    ? (sortAsc ? <ChevronUp className="h-3 w-3 inline ml-0.5" /> : <ChevronDown className="h-3 w-3 inline ml-0.5" />)
    : null;

  const filtered = (data?.data || [])
    .filter(r => !search || (r.name || r.month || '').toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const av = a[sortKey] ?? 0, bv = b[sortKey] ?? 0;
      return sortAsc ? av - bv : bv - av;
    });

  return (
    <div className="space-y-4" data-testid="historical-profit">
      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <span className="text-xs font-medium text-muted-foreground block mb-1">Year</span>
          <Select value={year} onValueChange={setYear}>
            <SelectTrigger className="w-24" data-testid="hp-year"><SelectValue /></SelectTrigger>
            <SelectContent>{years.map(y => <SelectItem key={y} value={y}>{y}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <span className="text-xs font-medium text-muted-foreground block mb-1">View</span>
          <Select value={view} onValueChange={v => { setView(v); setSearch(''); }}>
            <SelectTrigger className="w-44" data-testid="hp-view"><SelectValue /></SelectTrigger>
            <SelectContent>{VIEWS.map(v => <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        {view !== 'yearly' && view !== 'month' && (
          <div className="flex-1 min-w-[180px]">
            <span className="text-xs font-medium text-muted-foreground block mb-1">Search</span>
            <Input placeholder="Filter by name..." value={search} onChange={e => setSearch(e.target.value)}
              className="h-9" data-testid="hp-search" />
          </div>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
      ) : !data ? (
        <div className="text-center text-muted-foreground py-16">No historical data for this year</div>
      ) : view === 'yearly' ? (
        <YearlySummary data={data} />
      ) : view === 'month' ? (
        <MonthView rows={data.data || []} />
      ) : (
        <TableView view={view} rows={filtered} sortKey={sortKey} sortAsc={sortAsc}
          toggleSort={toggleSort} SortIcon={SortIcon} total={data.total} />
      )}
    </div>
  );
}

function YearlySummary({ data }) {
  const cards = [
    { label: 'Silver Profit', value: fmtKg(data.silver_profit_kg), color: 'bg-emerald-50 border-emerald-200 text-emerald-700' },
    { label: 'Labour Profit', value: fmtInr(data.labor_profit_inr), color: 'bg-blue-50 border-blue-200 text-blue-700' },
    { label: 'Total Sold', value: fmtKg(data.total_sold_kg), color: 'bg-amber-50 border-amber-200 text-amber-700' },
    { label: 'Transactions Matched', value: fmt(data.total_transactions), color: 'bg-purple-50 border-purple-200 text-purple-700' },
    { label: 'Sale Records', value: fmt(data.total_sale_records), color: 'bg-rose-50 border-rose-200 text-rose-700' },
    { label: 'Purchase Records', value: fmt(data.total_purchase_records), color: 'bg-sky-50 border-sky-200 text-sky-700' },
  ];
  return (
    <div data-testid="hp-yearly">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {cards.map(c => (
          <div key={c.label} className={`rounded-lg border p-4 ${c.color}`}>
            <p className="text-xs opacity-80">{c.label}</p>
            <p className="text-lg font-bold mt-1">{c.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function MonthView({ rows }) {
  const chartData = rows.map(r => ({
    month: r.month?.slice(5) || r.month,
    silver: r.silver_profit_kg,
    labor: Math.round(r.labor_profit_inr / 1000),
  }));
  return (
    <div className="space-y-4" data-testid="hp-month">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Monthly Silver Profit (kg)</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v, name) => [name === 'silver' ? `${v} kg` : `₹${v}K`, name === 'silver' ? 'Silver Profit' : 'Labour Profit']} />
              <Bar dataKey="silver" fill="#10b981" radius={[4, 4, 0, 0]} name="silver" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Monthly Labour Profit Trend (₹ thousands)</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`₹${v}K`, 'Labour Profit']} />
              <Line type="monotone" dataKey="labor" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Month</TableHead>
                <TableHead className="text-xs text-right">Silver Profit (kg)</TableHead>
                <TableHead className="text-xs text-right">Labour Profit (₹)</TableHead>
                <TableHead className="text-xs text-right">Sold (kg)</TableHead>
                <TableHead className="text-xs text-right">Transactions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(r => (
                <TableRow key={r.month}>
                  <TableCell className="font-medium text-sm">{r.month}</TableCell>
                  <TableCell className={`text-right text-sm ${r.silver_profit_kg >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{fmtKg(r.silver_profit_kg)}</TableCell>
                  <TableCell className={`text-right text-sm ${r.labor_profit_inr >= 0 ? 'text-blue-600' : 'text-red-600'}`}>{fmtInr(r.labor_profit_inr)}</TableCell>
                  <TableCell className="text-right text-sm">{fmtKg(r.total_sold_kg)}</TableCell>
                  <TableCell className="text-right text-sm">{fmt(r.transactions)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function TableView({ view, rows, sortKey, toggleSort, SortIcon, total }) {
  const isSupplier = view === 'supplier';
  const isItem = view === 'item';
  const [page, setPage] = useState(1);
  const perPage = 25;
  const paged = rows.slice((page - 1) * perPage, page * perPage);
  const totalPages = Math.ceil(rows.length / perPage);

  // Chart: top 15 by silver profit
  const chartRows = [...rows].sort((a, b) => b.silver_profit_kg - a.silver_profit_kg).slice(0, 15);
  const chartData = chartRows.map(r => ({
    name: (r.name || '').length > 22 ? r.name.slice(0, 22) + '..' : r.name,
    silver: r.silver_profit_kg,
  }));

  return (
    <div className="space-y-4" data-testid={`hp-${view}`}>
      {chartData.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Top 15 by Silver Profit (kg)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 28)}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={160} tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v) => [`${v} kg`, 'Silver Profit']} />
                <Bar dataKey="silver" fill="#10b981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">{view === 'customer' ? 'Customer' : view === 'supplier' ? 'Supplier' : 'Item'} Profit Breakdown</CardTitle>
            <Badge variant="outline">{total} total</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Name</TableHead>
                  <TableHead className="text-xs text-right cursor-pointer select-none" onClick={() => toggleSort('silver_profit_kg')}>
                    Silver Profit (kg)<SortIcon col="silver_profit_kg" />
                  </TableHead>
                  <TableHead className="text-xs text-right cursor-pointer select-none" onClick={() => toggleSort('labor_profit_inr')}>
                    Labour Profit (₹)<SortIcon col="labor_profit_inr" />
                  </TableHead>
                  <TableHead className="text-xs text-right">
                    {isSupplier ? 'Purchased (kg)' : 'Sold (kg)'}
                  </TableHead>
                  {isItem && <TableHead className="text-xs text-right">Buy Tunch</TableHead>}
                  {isItem && <TableHead className="text-xs text-right">Sell Tunch</TableHead>}
                  <TableHead className="text-xs text-right">{isSupplier ? 'Items' : 'Txns'}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paged.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium text-sm max-w-[250px] truncate" title={r.name}>{r.name}</TableCell>
                    <TableCell className={`text-right text-sm ${r.silver_profit_kg >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {fmtKg(r.silver_profit_kg)}
                    </TableCell>
                    <TableCell className={`text-right text-sm ${r.labor_profit_inr >= 0 ? 'text-blue-600' : 'text-red-600'}`}>
                      {fmtInr(r.labor_profit_inr)}
                    </TableCell>
                    <TableCell className="text-right text-sm">{fmtKg(isSupplier ? r.total_purchased_kg : r.total_sold_kg)}</TableCell>
                    {isItem && <TableCell className="text-right text-sm">{r.avg_purchase_tunch}</TableCell>}
                    {isItem && <TableCell className="text-right text-sm">{r.avg_sale_tunch}</TableCell>}
                    <TableCell className="text-right text-sm">{isSupplier ? r.items_count : r.transactions}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-3 pt-3 border-t">
              <span className="text-xs text-muted-foreground">Showing {(page-1)*perPage+1}-{Math.min(page*perPage, rows.length)} of {rows.length}</span>
              <div className="flex gap-1">
                <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page === 1}
                  className="px-2 py-1 text-xs rounded border disabled:opacity-40">Prev</button>
                <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page === totalPages}
                  className="px-2 py-1 text-xs rounded border disabled:opacity-40">Next</button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
