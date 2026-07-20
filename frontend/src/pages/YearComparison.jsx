import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown, BarChart3, Users, Package, Truck, Search } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { formatIndianCurrency } from '@/utils/formatCurrency';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const YEAR_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#0ea5e9', '#ec4899', '#84cc16'];

const yearColor = (years, y) => YEAR_COLORS[years.indexOf(Number(y)) % YEAR_COLORS.length];

/** 3D-styled bar: front face + lighter top + darker side */
const Bar3D = (props) => {
  const { x, y, width, height, fill } = props;
  if (!height || height <= 0 || width <= 0) return null;
  const d = Math.max(2, Math.min(6, width * 0.4));
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} />
      <polygon points={`${x},${y} ${x + d},${y - d} ${x + width + d},${y - d} ${x + width},${y}`} fill={fill} />
      <polygon points={`${x},${y} ${x + d},${y - d} ${x + width + d},${y - d} ${x + width},${y}`} fill="#ffffff" opacity={0.4} />
      <polygon points={`${x + width},${y} ${x + width + d},${y - d} ${x + width + d},${y + height - d} ${x + width},${y + height}`} fill={fill} />
      <polygon points={`${x + width},${y} ${x + width + d},${y - d} ${x + width + d},${y + height - d} ${x + width},${y + height}`} fill="#000000" opacity={0.28} />
    </g>
  );
};

/** Multi-year monthly chart: months on X, one colored series per year, bar/line toggle */
const YearlyMonthChart = ({ years, seriesByYear, mode, unit, height = 260 }) => {
  const data = MONTHS.map((mn, i) => {
    const row = { name: mn };
    years.forEach((y) => { row[String(y)] = seriesByYear?.[String(y)]?.[i] ?? 0; });
    return row;
  });
  const fmt = (v) => (unit === '₹' ? formatIndianCurrency(v) : `${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })}${unit ? ' ' + unit : ''}`);
  const common = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
      <YAxis tick={{ fontSize: 10 }} width={62} tickFormatter={(v) => Math.abs(v) >= 100000 ? `${(v / 100000).toFixed(1)}L` : Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : v} />
      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(value, name) => [fmt(value), name]} />
      <Legend wrapperStyle={{ fontSize: 12 }} />
    </>
  );
  return (
    <div style={{ height }} className="w-full" data-testid="yearly-month-chart">
      <ResponsiveContainer width="100%" height="100%">
        {mode === 'line' ? (
          <LineChart data={data} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
            {common}
            {years.map((y) => (
              <Line key={y} type="monotone" dataKey={String(y)} name={String(y)} stroke={yearColor(years, y)} strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
            ))}
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 12, right: 16, left: 0, bottom: 4 }} barGap={3}>
            {common}
            {years.map((y) => (
              <Bar key={y} dataKey={String(y)} name={String(y)} fill={yearColor(years, y)} shape={<Bar3D />} maxBarSize={26} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
};

const ModeToggle = ({ mode, setMode }) => (
  <div className="flex gap-1">
    {['bar', 'line'].map((m) => (
      <Button key={m} variant={mode === m ? 'default' : 'outline'} size="sm" className="h-6 text-[10px] px-2 capitalize"
        onClick={() => setMode(m)} data-testid={`chart-mode-${m}`}>{m === 'bar' ? '3D Bars' : 'Lines'}</Button>
    ))}
  </div>
);

const OVERVIEW_METRICS = [
  { key: 'sales_kg', label: 'Sales (kg)', unit: 'kg' },
  { key: 'sales_value', label: 'Sales Value (₹)', unit: '₹' },
  { key: 'purchases_kg', label: 'Purchases (kg)', unit: 'kg' },
  { key: 'silver_profit_kg', label: 'Silver Profit (kg)', unit: 'kg' },
  { key: 'labor_profit_inr', label: 'Labour Profit (₹)', unit: '₹' },
  { key: 'transactions', label: 'Transactions', unit: '' },
];

const PARTY_METRICS = [
  { key: 'kg', label: 'Weight (kg)', unit: 'kg' },
  { key: 'value', label: 'Value (₹)', unit: '₹' },
  { key: 'silver_profit_kg', label: 'Silver Profit (kg)', unit: 'kg' },
  { key: 'labor_profit_inr', label: 'Labour Profit (₹)', unit: '₹' },
];

const ENTITY_TABS = [
  { key: 'items', label: 'Top Items', icon: Package },
  { key: 'customers', label: 'Top Customers', icon: Users },
  { key: 'suppliers', label: 'Top Suppliers', icon: Truck },
];

export default function YearComparison() {
  const { isAdmin } = useAuth();
  const [overview, setOverview] = useState(null);
  const [overviewMetric, setOverviewMetric] = useState('sales_kg');
  const [overviewMode, setOverviewMode] = useState('bar');

  const [entityTab, setEntityTab] = useState('items');
  const [topData, setTopData] = useState(null);
  const [topLoading, setTopLoading] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [topMode, setTopMode] = useState('bar');

  const [partyType, setPartyType] = useState('customer');
  const [partyList, setPartyList] = useState([]);
  const [partyInput, setPartyInput] = useState('');
  const [partyDetail, setPartyDetail] = useState(null);
  const [partyMetric, setPartyMetric] = useState('kg');
  const [partyMode, setPartyMode] = useState('bar');
  const [partyLoading, setPartyLoading] = useState(false);

  useEffect(() => {
    if (!isAdmin) return;
    axios.get(`${API}/analytics/year-comparison/overview`).then((r) => setOverview(r.data)).catch(console.error);
  }, [isAdmin]);

  const fetchTop = useCallback((tab) => {
    setTopLoading(true);
    setSelectedEntity(null);
    axios.get(`${API}/analytics/year-comparison/top?entity=${tab}&limit=8`)
      .then((r) => { setTopData(r.data); if (r.data.top?.length) setSelectedEntity(r.data.top[0]); })
      .catch(console.error).finally(() => setTopLoading(false));
  }, []);

  useEffect(() => { if (isAdmin) fetchTop(entityTab); }, [isAdmin, entityTab, fetchTop]);

  useEffect(() => {
    if (!isAdmin) return;
    axios.get(`${API}/analytics/year-comparison/parties?party_type=${partyType}`)
      .then((r) => setPartyList(r.data.parties || [])).catch(console.error);
    setPartyDetail(null); setPartyInput('');
  }, [isAdmin, partyType]);

  const loadPartyDetail = (name) => {
    if (!name) return;
    setPartyLoading(true);
    axios.get(`${API}/analytics/year-comparison/party-detail?party=${encodeURIComponent(name)}&party_type=${partyType}`)
      .then((r) => setPartyDetail(r.data)).catch(console.error).finally(() => setPartyLoading(false));
  };

  if (!isAdmin) return null;

  const years = overview?.years || [];
  const activeOM = OVERVIEW_METRICS.find((m) => m.key === overviewMetric);
  const activePM = PARTY_METRICS.find((m) => m.key === partyMetric);

  // grouped bar data for top entities (entity on X, one bar per year — same scale)
  const topGrouped = (topData?.top || []).map((e) => {
    const row = { name: e.name.length > 14 ? e.name.slice(0, 13) + '…' : e.name, full: e.name };
    (topData.years || []).forEach((y) => { row[String(y)] = e.yearly?.[String(y)] ?? 0; });
    return row;
  });

  return (
    <div className="space-y-6" data-testid="year-comparison-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-7 w-7" /> Year Comparison
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">All years on the same scale — one color per year, months side by side</p>
        </div>
        <div className="flex gap-2 items-center flex-wrap" data-testid="year-legend">
          {years.map((y) => (
            <span key={y} className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border"
              style={{ borderColor: yearColor(years, y), color: yearColor(years, y) }}>
              <span className="h-2.5 w-2.5 rounded-sm inline-block" style={{ background: yearColor(years, y) }} />{y}
            </span>
          ))}
        </div>
      </div>

      {/* Yearly totals */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="yearly-totals-cards">
        {(overview?.yearly_totals || []).map((t) => (
          <Card key={t.year} className="border-l-4" style={{ borderLeftColor: yearColor(years, t.year) }}>
            <CardHeader className="pb-2 flex-row items-center justify-between space-y-0">
              <CardTitle className="text-lg font-bold" style={{ color: yearColor(years, t.year) }}>{t.year}</CardTitle>
              {t.sales_growth_pct !== null && t.sales_growth_pct !== undefined && (
                <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${t.sales_growth_pct >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}
                  data-testid={`growth-badge-${t.year}`}>
                  {t.sales_growth_pct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                  {t.sales_growth_pct >= 0 ? '+' : ''}{t.sales_growth_pct}% sales
                </span>
              )}
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <div><span className="text-muted-foreground">Sales</span><p className="font-mono font-bold text-sm">{t.sales_kg.toLocaleString('en-IN')} kg</p></div>
              <div><span className="text-muted-foreground">Sales Value</span><p className="font-mono font-bold text-sm">{formatIndianCurrency(t.sales_value)}</p></div>
              <div><span className="text-muted-foreground">Silver Profit</span><p className="font-mono font-bold text-sm text-emerald-600">{t.silver_profit_kg.toLocaleString('en-IN')} kg</p></div>
              <div><span className="text-muted-foreground">Labour Profit</span><p className="font-mono font-bold text-sm text-blue-600">{formatIndianCurrency(t.labor_profit_inr)}</p></div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Monthly overview comparison */}
      <Card data-testid="overview-comparison-card">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="text-lg">Monthly Comparison — {activeOM.label}</CardTitle>
              <CardDescription>Same months across years, identical scale</CardDescription>
            </div>
            <ModeToggle mode={overviewMode} setMode={setOverviewMode} />
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {OVERVIEW_METRICS.map((mt) => (
              <Button key={mt.key} variant={overviewMetric === mt.key ? 'default' : 'outline'} size="sm"
                className="h-6 text-[10px] px-2" onClick={() => setOverviewMetric(mt.key)}
                data-testid={`overview-metric-${mt.key}`}>{mt.label}</Button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {overview ? (
            <YearlyMonthChart years={years} seriesByYear={overview.monthly[overviewMetric]} mode={overviewMode} unit={activeOM.unit} height={280} />
          ) : <p className="text-sm text-muted-foreground py-10 text-center">Loading...</p>}
        </CardContent>
      </Card>

      {/* Top entities */}
      <Card data-testid="top-entities-card">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex gap-1.5">
              {ENTITY_TABS.map((t) => (
                <Button key={t.key} variant={entityTab === t.key ? 'default' : 'outline'} size="sm"
                  className="h-7 text-xs px-3" onClick={() => setEntityTab(t.key)} data-testid={`entity-tab-${t.key}`}>
                  <t.icon className="h-3.5 w-3.5 mr-1" />{t.label}
                </Button>
              ))}
            </div>
            <ModeToggle mode={topMode} setMode={setTopMode} />
          </div>
          <CardDescription>
            {entityTab === 'items' ? 'Total sold (kg) per year — tap a name for its month-by-month comparison'
              : entityTab === 'customers' ? 'Total bought (kg) per year — tap a name for month-by-month'
                : 'Total supplied (kg) per year — tap a name for month-by-month'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {topLoading ? <p className="text-sm text-muted-foreground py-8 text-center">Loading...</p> : (
            <>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topGrouped} margin={{ top: 12, right: 16, left: 0, bottom: 30 }} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-18} textAnchor="end" interval={0} />
                    <YAxis tick={{ fontSize: 10 }} width={55} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }}
                      formatter={(v, n) => [`${Number(v).toLocaleString('en-IN')} kg`, n]}
                      labelFormatter={(l, payload) => payload?.[0]?.payload?.full || l} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {(topData?.years || []).map((y) => (
                      <Bar key={y} dataKey={String(y)} name={String(y)} fill={yearColor(topData.years, y)} shape={<Bar3D />} maxBarSize={22} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap gap-1.5" data-testid="entity-chips">
                {(topData?.top || []).map((e) => (
                  <button key={e.name}
                    className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${selectedEntity?.name === e.name ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}
                    onClick={() => setSelectedEntity(e)} data-testid={`entity-chip-${e.name}`}>
                    {e.name} · {e.total_kg.toLocaleString('en-IN')} kg
                  </button>
                ))}
              </div>
              {selectedEntity && (
                <div className="pt-2 border-t" data-testid="entity-detail-section">
                  <p className="text-sm font-semibold mb-2">{selectedEntity.name} — month by month (kg)</p>
                  <YearlyMonthChart years={topData.years} seriesByYear={selectedEntity.monthly} mode={topMode} unit="kg" height={220} />
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Party drill-down */}
      <Card data-testid="party-drilldown-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Customer / Supplier Drill-Down</CardTitle>
          <CardDescription>Pick anyone and see how much they {partyType === 'customer' ? 'bought' : 'supplied'} each year, month by month</CardDescription>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <div className="flex gap-1">
              {['customer', 'supplier'].map((pt) => (
                <Button key={pt} variant={partyType === pt ? 'default' : 'outline'} size="sm"
                  className="h-7 text-xs px-3 capitalize" onClick={() => setPartyType(pt)}
                  data-testid={`party-type-${pt}`}>{pt}s</Button>
              ))}
            </div>
            <div className="relative flex-1 min-w-[220px] max-w-md">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
              <input list="yc-party-options" value={partyInput}
                onChange={(e) => { setPartyInput(e.target.value); if (partyList.includes(e.target.value)) loadPartyDetail(e.target.value); }}
                placeholder={`Type a ${partyType} name...`}
                className="w-full h-8 pl-8 pr-2 rounded-md border bg-background text-xs"
                data-testid="party-search-input" />
              <datalist id="yc-party-options">
                {partyList.map((n) => <option key={n} value={n} />)}
              </datalist>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {partyLoading ? <p className="text-sm text-muted-foreground py-8 text-center">Loading...</p>
            : partyDetail ? (
              <div className="space-y-3" data-testid="party-detail-section">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap gap-1.5">
                    {PARTY_METRICS.map((mt) => (
                      <Button key={mt.key} variant={partyMetric === mt.key ? 'default' : 'outline'} size="sm"
                        className="h-6 text-[10px] px-2" onClick={() => setPartyMetric(mt.key)}
                        data-testid={`party-metric-${mt.key}`}>{mt.label}</Button>
                    ))}
                  </div>
                  <ModeToggle mode={partyMode} setMode={setPartyMode} />
                </div>
                <div className="flex flex-wrap gap-2">
                  {(partyDetail.years || []).map((y) => (
                    <span key={y} className="text-[11px] px-2 py-0.5 rounded bg-muted font-mono">
                      {y}: <b>{(partyDetail.yearly_kg?.[String(y)] ?? 0).toLocaleString('en-IN')} kg</b>
                    </span>
                  ))}
                </div>
                <YearlyMonthChart years={partyDetail.years} seriesByYear={partyDetail.monthly[partyMetric]} mode={partyMode} unit={activePM.unit} height={240} />
              </div>
            ) : <p className="text-sm text-muted-foreground py-8 text-center">Search a {partyType} above to compare their years</p>}
        </CardContent>
      </Card>
    </div>
  );
}
