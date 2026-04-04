import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { TrendingUp, Loader2, RefreshCw, Package, Users, AlertTriangle, BarChart3, Calendar, ShoppingCart, Layers } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const REASON_LABELS = {
  high_pms_balanced_margin: { label: 'Balanced Margin', color: 'bg-green-600' },
  high_labour_but_silver_weak: { label: 'Labour Strong / Silver Weak', color: 'bg-amber-500' },
  high_silver_but_labour_weak: { label: 'Silver Strong / Labour Weak', color: 'bg-blue-500' },
  seasonal_peak_prebuild: { label: 'Seasonal Pre-build', color: 'bg-purple-500' },
  slow_mover_low_pms: { label: 'Slow Mover', color: 'bg-gray-500' },
  hold_procurement: { label: 'Hold', color: 'bg-red-500' },
  moderate_demand: { label: 'Moderate', color: 'bg-cyan-600' },
};

const SEGMENT_COLORS = {
  dense_daily: 'bg-green-100 text-green-800',
  medium_daily: 'bg-blue-100 text-blue-800',
  weekly_sparse: 'bg-amber-100 text-amber-800',
  cold_start: 'bg-gray-100 text-gray-600',
};

const CONF_COLORS = {
  high: 'bg-green-600', medium: 'bg-amber-500', low: 'bg-orange-500', very_low: 'bg-red-500',
};

function SearchInput({ value, onChange, placeholder, testId }) {
  return (
    <Input
      placeholder={placeholder} value={value}
      onChange={e => onChange(e.target.value)}
      className="max-w-xs" data-testid={testId}
    />
  );
}

function PMSTable({ items, showBalanced, searchTerm }) {
  const filtered = useMemo(() => {
    if (!searchTerm) return items;
    const q = searchTerm.toLowerCase();
    return items.filter(i =>
      i.item_name.toLowerCase().includes(q) || i.stamp?.toLowerCase().includes(q)
    );
  }, [items, searchTerm]);

  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[800px]">
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs w-8">#</TableHead>
            <TableHead className="text-xs">Item</TableHead>
            <TableHead className="text-xs">Stamp</TableHead>
            <TableHead className="text-xs">Segment</TableHead>
            <TableHead className="text-xs text-right">PMS</TableHead>
            <TableHead className="text-xs text-right">Silver Score</TableHead>
            <TableHead className="text-xs text-right">Labour Score</TableHead>
            {showBalanced && <TableHead className="text-xs text-right">Balanced</TableHead>}
            <TableHead className="text-xs text-right">Forecast 30d (g)</TableHead>
            <TableHead className="text-xs">Confidence</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow><TableCell colSpan={showBalanced ? 10 : 9} className="text-center py-6 text-muted-foreground">No items found</TableCell></TableRow>
          ) : filtered.slice(0, 100).map((item, i) => (
            <TableRow key={`${item.item_name}-${item.stamp}-${i}`}>
              <TableCell className="text-xs text-muted-foreground">{i + 1}</TableCell>
              <TableCell className="text-xs font-medium max-w-[180px] truncate">{item.item_name}</TableCell>
              <TableCell className="text-xs"><Badge variant="outline" className="text-[10px]">{item.stamp}</Badge></TableCell>
              <TableCell><Badge className={`text-[10px] ${SEGMENT_COLORS[item.segment] || ''}`}>{item.segment}</Badge></TableCell>
              <TableCell className="text-xs text-right font-mono font-bold">{item.pms?.toLocaleString()}</TableCell>
              <TableCell className={`text-xs text-right font-mono ${item.silver_score > 0 ? 'text-green-700' : 'text-red-600'}`}>{item.silver_score}</TableCell>
              <TableCell className={`text-xs text-right font-mono ${item.labour_score > 0 ? 'text-green-700' : 'text-red-600'}`}>{item.labour_score}</TableCell>
              {showBalanced && <TableCell className="text-xs text-right font-mono">{item.balanced_score}</TableCell>}
              <TableCell className="text-xs text-right font-mono">{item.forecast_30d?.toLocaleString()}</TableCell>
              <TableCell><Badge className={`text-[10px] ${CONF_COLORS[item.confidence] || 'bg-gray-400'}`}>{item.confidence}</Badge></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {filtered.length > 100 && <p className="text-xs text-muted-foreground text-center py-2">Showing top 100 of {filtered.length}</p>}
    </div>
  );
}

export default function SeasonalAnalysis() {
  const [loading, setLoading] = useState(false);
  const [computed, setComputed] = useState(false);
  const [summary, setSummary] = useState(null);
  const [pmsData, setPmsData] = useState({ final: [], silver: [], labour: [] });
  const [forecasts, setForecasts] = useState([]);
  const [seasonality, setSeasonality] = useState([]);
  const [procurement, setProcurement] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [deadStock, setDeadStock] = useState([]);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('pms-final');

  const runComputation = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/seasonal/compute?force=true`);
      setSummary(res.data);
      setComputed(true);
      toast.success(`Analysis complete — ${res.data.total_items} items processed`);
      fetchTabData(activeTab);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Computation failed');
    } finally {
      setLoading(false);
    }
  };

  const fetchTabData = async (tab) => {
    try {
      const endpoints = {
        'pms-final': '/seasonal/pms-final',
        'pms-silver': '/seasonal/pms-silver',
        'pms-labour': '/seasonal/pms-labour',
        'demand': '/seasonal/demand-forecast',
        'seasonality': '/seasonal/seasonality',
        'procurement': '/seasonal/procurement',
        'supplier': '/seasonal/supplier-view',
        'dead-stock': '/seasonal/dead-stock',
      };
      const ep = endpoints[tab];
      if (!ep) return;
      const res = await axios.get(`${API}${ep}`);
      const items = res.data.items || [];
      switch (tab) {
        case 'pms-final': setPmsData(d => ({ ...d, final: items })); break;
        case 'pms-silver': setPmsData(d => ({ ...d, silver: items })); break;
        case 'pms-labour': setPmsData(d => ({ ...d, labour: items })); break;
        case 'demand': setForecasts(items); break;
        case 'seasonality': setSeasonality(items); break;
        case 'procurement': setProcurement(items); break;
        case 'supplier': setSuppliers(items); break;
        case 'dead-stock': setDeadStock(items); break;
      }
      if (!computed) setComputed(true);
    } catch (e) {
      if (e.response?.status !== 403) toast.error('Failed to load data');
    }
  };

  useEffect(() => {
    fetchTabData(activeTab);
  }, [activeTab]);

  const handleTabChange = (val) => {
    setActiveTab(val);
    setSearch('');
  };

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-5" data-testid="seasonal-analysis-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-4xl font-bold tracking-tight" data-testid="seasonal-title">
            Seasonal Analysis
          </h1>
          <p className="text-xs sm:text-base text-muted-foreground mt-1">
            ML-driven demand forecasting, PMS rankings & procurement planning
          </p>
        </div>
        <Button onClick={runComputation} disabled={loading} data-testid="compute-btn" size="sm">
          {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
          {loading ? 'Computing...' : 'Run Analysis'}
        </Button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="summary-cards">
          <Card><CardContent className="p-3 text-center">
            <p className="text-[10px] text-muted-foreground">Total Items</p>
            <p className="text-lg font-bold">{summary.total_items}</p>
          </CardContent></Card>
          {Object.entries(summary.segments_summary || {}).map(([seg, count]) => (
            <Card key={seg}><CardContent className="p-3 text-center">
              <p className="text-[10px] text-muted-foreground">{seg}</p>
              <p className="text-lg font-bold">{count}</p>
            </CardContent></Card>
          ))}
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-4">
        <div className="overflow-x-auto">
          <TabsList className="inline-flex w-auto min-w-full sm:min-w-0">
            <TabsTrigger value="pms-final" data-testid="tab-pms-final">PMS Final</TabsTrigger>
            <TabsTrigger value="pms-silver" data-testid="tab-pms-silver">PMS Silver</TabsTrigger>
            <TabsTrigger value="pms-labour" data-testid="tab-pms-labour">PMS Labour</TabsTrigger>
            <TabsTrigger value="demand" data-testid="tab-demand">Demand</TabsTrigger>
            <TabsTrigger value="seasonality" data-testid="tab-seasonality">Seasonality</TabsTrigger>
            <TabsTrigger value="procurement" data-testid="tab-procurement">Procurement</TabsTrigger>
            <TabsTrigger value="supplier" data-testid="tab-supplier">Supplier</TabsTrigger>
            <TabsTrigger value="dead-stock" data-testid="tab-dead-stock">Dead Stock</TabsTrigger>
          </TabsList>
        </div>

        {/* Search bar */}
        <SearchInput value={search} onChange={setSearch} placeholder="Search item or stamp..." testId="seasonal-search" />

        {/* PMS Final */}
        <TabsContent value="pms-final">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><TrendingUp className="h-4 w-4" />PMS Final Rankings</CardTitle>
              <CardDescription className="text-xs">Balanced profit-margin score: penalises one-sided distortion</CardDescription>
            </CardHeader>
            <CardContent><PMSTable items={pmsData.final} showBalanced searchTerm={search} /></CardContent>
          </Card>
        </TabsContent>

        {/* PMS Silver */}
        <TabsContent value="pms-silver">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">PMS Silver Rankings</CardTitle>
              <CardDescription className="text-xs">Ranked by silver-margin weighted demand</CardDescription>
            </CardHeader>
            <CardContent><PMSTable items={pmsData.silver} showBalanced={false} searchTerm={search} /></CardContent>
          </Card>
        </TabsContent>

        {/* PMS Labour */}
        <TabsContent value="pms-labour">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">PMS Labour Rankings</CardTitle>
              <CardDescription className="text-xs">Ranked by labour-margin weighted demand</CardDescription>
            </CardHeader>
            <CardContent><PMSTable items={pmsData.labour} showBalanced={false} searchTerm={search} /></CardContent>
          </Card>
        </TabsContent>

        {/* Demand Forecast */}
        <TabsContent value="demand">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><BarChart3 className="h-4 w-4" />Demand Forecast</CardTitle>
              <CardDescription className="text-xs">14-day and 30-day gross weight demand predictions</CardDescription>
            </CardHeader>
            <CardContent>
              <DemandTable items={forecasts} searchTerm={search} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Seasonality */}
        <TabsContent value="seasonality">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><Calendar className="h-4 w-4" />Seasonality Patterns</CardTitle>
              <CardDescription className="text-xs">Real month-over-month demand patterns from historical data</CardDescription>
            </CardHeader>
            <CardContent>
              <SeasonalityTable items={seasonality} searchTerm={search} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Procurement Planner */}
        <TabsContent value="procurement">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><ShoppingCart className="h-4 w-4" />Procurement Planner</CardTitle>
              <CardDescription className="text-xs">PMS-driven buy/hold recommendations with reason codes</CardDescription>
            </CardHeader>
            <CardContent>
              <ProcurementTable items={procurement} searchTerm={search} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Supplier View */}
        <TabsContent value="supplier">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><Users className="h-4 w-4" />Supplier View</CardTitle>
              <CardDescription className="text-xs">Supplier-wise recommendations by item PMS and recency</CardDescription>
            </CardHeader>
            <CardContent>
              <SupplierTable items={suppliers} searchTerm={search} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Dead Stock */}
        <TabsContent value="dead-stock">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-red-500" />Dead Stock & Slow Movers</CardTitle>
              <CardDescription className="text-xs">Low-velocity and low-PMS items — candidates for do-not-restock</CardDescription>
            </CardHeader>
            <CardContent>
              <DeadStockTable items={deadStock} searchTerm={search} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ---- Sub-tables ---- */

function DemandTable({ items, searchTerm }) {
  const filtered = useMemo(() => {
    if (!searchTerm) return items;
    const q = searchTerm.toLowerCase();
    return items.filter(i => i.item_name.toLowerCase().includes(q) || i.stamp?.toLowerCase().includes(q));
  }, [items, searchTerm]);
  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[700px]">
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">#</TableHead>
            <TableHead className="text-xs">Item</TableHead>
            <TableHead className="text-xs">Stamp</TableHead>
            <TableHead className="text-xs">Family</TableHead>
            <TableHead className="text-xs">Segment</TableHead>
            <TableHead className="text-xs text-right">14d (g)</TableHead>
            <TableHead className="text-xs text-right">30d (g)</TableHead>
            <TableHead className="text-xs">Confidence</TableHead>
            <TableHead className="text-xs text-right">Active Days</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow><TableCell colSpan={9} className="text-center py-6 text-muted-foreground">No forecast data</TableCell></TableRow>
          ) : filtered.slice(0, 100).map((item, i) => (
            <TableRow key={`${item.item_name}-${item.stamp}-${i}`}>
              <TableCell className="text-xs text-muted-foreground">{i + 1}</TableCell>
              <TableCell className="text-xs font-medium max-w-[160px] truncate">{item.item_name}</TableCell>
              <TableCell className="text-xs"><Badge variant="outline" className="text-[10px]">{item.stamp}</Badge></TableCell>
              <TableCell className="text-xs">{item.item_family}</TableCell>
              <TableCell><Badge className={`text-[10px] ${SEGMENT_COLORS[item.segment] || ''}`}>{item.segment}</Badge></TableCell>
              <TableCell className="text-xs text-right font-mono">{item.forecast_14d?.toLocaleString()}</TableCell>
              <TableCell className="text-xs text-right font-mono font-bold">{item.forecast_30d?.toLocaleString()}</TableCell>
              <TableCell><Badge className={`text-[10px] ${CONF_COLORS[item.confidence] || 'bg-gray-400'}`}>{item.confidence}</Badge></TableCell>
              <TableCell className="text-xs text-right">{item.active_days}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function SeasonalityTable({ items, searchTerm }) {
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const filtered = useMemo(() => {
    if (!searchTerm) return items;
    const q = searchTerm.toLowerCase();
    return items.filter(i => i.item_name.toLowerCase().includes(q) || i.stamp?.toLowerCase().includes(q));
  }, [items, searchTerm]);
  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[900px]">
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Item</TableHead>
            <TableHead className="text-xs">Stamp</TableHead>
            {MONTHS.map(m => <TableHead key={m} className="text-[10px] text-center px-1">{m}</TableHead>)}
            <TableHead className="text-xs">Peaks</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow><TableCell colSpan={15} className="text-center py-6 text-muted-foreground">No seasonality data</TableCell></TableRow>
          ) : filtered.slice(0, 60).map((item, i) => (
            <TableRow key={`${item.item_name}-${item.stamp}-${i}`}>
              <TableCell className="text-xs font-medium max-w-[140px] truncate">{item.item_name}</TableCell>
              <TableCell className="text-xs"><Badge variant="outline" className="text-[10px]">{item.stamp}</Badge></TableCell>
              {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => {
                const prof = item.monthly_profile?.[m];
                const idx = prof?.index || 0;
                const bg = idx > 1.2 ? 'bg-green-100 text-green-800 font-bold' : idx < 0.8 ? 'bg-red-50 text-red-600' : '';
                return <TableCell key={m} className={`text-[10px] text-center font-mono px-1 ${bg}`}>{idx.toFixed(1)}</TableCell>;
              })}
              <TableCell className="text-xs">
                {item.peak_months?.map(m => <Badge key={m} className="bg-green-600 text-[9px] mr-0.5">{MONTHS[m-1]}</Badge>)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ProcurementTable({ items, searchTerm }) {
  const filtered = useMemo(() => {
    if (!searchTerm) return items;
    const q = searchTerm.toLowerCase();
    return items.filter(i => i.item_name.toLowerCase().includes(q) || i.stamp?.toLowerCase().includes(q));
  }, [items, searchTerm]);
  const buyItems = filtered.filter(i => i.action === 'buy');
  const holdItems = filtered.filter(i => i.action === 'hold');
  return (
    <div className="space-y-4">
      <div className="flex gap-3 text-sm">
        <Badge className="bg-green-600">{buyItems.length} Buy</Badge>
        <Badge className="bg-red-500">{holdItems.length} Hold</Badge>
      </div>
      <div className="overflow-x-auto">
        <Table className="min-w-[900px]">
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Item</TableHead>
              <TableHead className="text-xs">Stamp</TableHead>
              <TableHead className="text-xs">Action</TableHead>
              <TableHead className="text-xs">Reason</TableHead>
              <TableHead className="text-xs text-right">PMS</TableHead>
              <TableHead className="text-xs text-right">Forecast 30d (g)</TableHead>
              <TableHead className="text-xs text-right">Stock (g)</TableHead>
              <TableHead className="text-xs text-right">Coverage (d)</TableHead>
              <TableHead className="text-xs text-right">Suggested Qty (g)</TableHead>
              <TableHead className="text-xs">Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow><TableCell colSpan={10} className="text-center py-6 text-muted-foreground">No procurement data</TableCell></TableRow>
            ) : filtered.slice(0, 100).map((item, i) => {
              const reason = REASON_LABELS[item.reason_code] || { label: item.reason_code, color: 'bg-gray-400' };
              return (
                <TableRow key={`${item.item_name}-${item.stamp}-${i}`}>
                  <TableCell className="text-xs font-medium max-w-[150px] truncate">{item.item_name}</TableCell>
                  <TableCell className="text-xs"><Badge variant="outline" className="text-[10px]">{item.stamp}</Badge></TableCell>
                  <TableCell>
                    <Badge className={item.action === 'buy' ? 'bg-green-600 text-[10px]' : 'bg-red-500 text-[10px]'}>
                      {item.action.toUpperCase()}
                    </Badge>
                  </TableCell>
                  <TableCell><Badge className={`${reason.color} text-[10px]`}>{reason.label}</Badge></TableCell>
                  <TableCell className="text-xs text-right font-mono">{item.pms_final?.toLocaleString()}</TableCell>
                  <TableCell className="text-xs text-right font-mono">{item.forecast_30d?.toLocaleString()}</TableCell>
                  <TableCell className="text-xs text-right font-mono">{item.current_stock_g?.toLocaleString()}</TableCell>
                  <TableCell className="text-xs text-right font-mono">{item.coverage_days > 900 ? '999+' : item.coverage_days}</TableCell>
                  <TableCell className="text-xs text-right font-mono font-bold">{item.suggested_qty_g?.toLocaleString()}</TableCell>
                  <TableCell><Badge className={`text-[10px] ${CONF_COLORS[item.confidence] || 'bg-gray-400'}`}>{item.confidence}</Badge></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function SupplierTable({ items, searchTerm }) {
  const filtered = useMemo(() => {
    if (!searchTerm) return items;
    const q = searchTerm.toLowerCase();
    return items.filter(i => i.supplier.toLowerCase().includes(q) || i.items?.some(it => it.toLowerCase().includes(q)));
  }, [items, searchTerm]);
  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[700px]">
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Supplier</TableHead>
            <TableHead className="text-xs text-right">Items</TableHead>
            <TableHead className="text-xs text-right">Purchases</TableHead>
            <TableHead className="text-xs text-right">Volume (kg)</TableHead>
            <TableHead className="text-xs text-right">Days Since</TableHead>
            <TableHead className="text-xs text-right">Avg PMS</TableHead>
            <TableHead className="text-xs">Top Items</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow><TableCell colSpan={7} className="text-center py-6 text-muted-foreground">No supplier data</TableCell></TableRow>
          ) : filtered.slice(0, 50).map((s, i) => (
            <TableRow key={`${s.supplier}-${i}`}>
              <TableCell className="text-xs font-medium">{s.supplier}</TableCell>
              <TableCell className="text-xs text-right">{s.n_items}</TableCell>
              <TableCell className="text-xs text-right">{s.n_purchases}</TableCell>
              <TableCell className="text-xs text-right font-mono">{s.total_volume_kg}</TableCell>
              <TableCell className="text-xs text-right">{s.days_since_last_purchase}</TableCell>
              <TableCell className={`text-xs text-right font-mono ${s.avg_item_pms > 0 ? 'text-green-700' : 'text-red-600'}`}>{s.avg_item_pms}</TableCell>
              <TableCell className="text-xs max-w-[200px] truncate">{s.items?.slice(0, 3).join(', ')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function DeadStockTable({ items, searchTerm }) {
  const filtered = useMemo(() => {
    if (!searchTerm) return items;
    const q = searchTerm.toLowerCase();
    return items.filter(i => i.item_name.toLowerCase().includes(q));
  }, [items, searchTerm]);
  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[700px]">
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Item</TableHead>
            <TableHead className="text-xs">Stamp</TableHead>
            <TableHead className="text-xs">Family</TableHead>
            <TableHead className="text-xs">Classification</TableHead>
            <TableHead className="text-xs text-right">Days Since Sale</TableHead>
            <TableHead className="text-xs text-right">Daily Velocity (g)</TableHead>
            <TableHead className="text-xs text-right">PMS</TableHead>
            <TableHead className="text-xs text-right">Stock (g)</TableHead>
            <TableHead className="text-xs">Recommendation</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow><TableCell colSpan={9} className="text-center py-6 text-muted-foreground">No dead stock detected</TableCell></TableRow>
          ) : filtered.map((item, i) => (
            <TableRow key={`${item.item_name}-${item.stamp}-${i}`}>
              <TableCell className="text-xs font-medium max-w-[160px] truncate">{item.item_name}</TableCell>
              <TableCell className="text-xs"><Badge variant="outline" className="text-[10px]">{item.stamp}</Badge></TableCell>
              <TableCell className="text-xs">{item.item_family}</TableCell>
              <TableCell>
                <Badge className={item.classification === 'dead_stock' ? 'bg-red-600 text-[10px]' : 'bg-amber-500 text-[10px]'}>
                  {item.classification === 'dead_stock' ? 'Dead Stock' : 'Slow Mover'}
                </Badge>
              </TableCell>
              <TableCell className="text-xs text-right font-mono">{item.days_since_last_sale}</TableCell>
              <TableCell className="text-xs text-right font-mono">{item.daily_velocity_g}</TableCell>
              <TableCell className="text-xs text-right font-mono">{item.pms_final}</TableCell>
              <TableCell className="text-xs text-right font-mono">{item.current_stock_g?.toLocaleString()}</TableCell>
              <TableCell>
                <Badge className={item.recommendation === 'do_not_restock' ? 'bg-red-600 text-[10px]' : 'bg-amber-500 text-[10px]'}>
                  {item.recommendation === 'do_not_restock' ? 'Do Not Restock' : 'Reduce'}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
