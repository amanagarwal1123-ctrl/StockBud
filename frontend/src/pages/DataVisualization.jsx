import { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart3, TrendingUp, Calendar, Sparkles, Loader2, Upload, Trash2, IndianRupee } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { toast } from 'sonner';
import HistoricalProfit from './HistoricalProfit';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TIER_CHART_COLORS = { fastest: '#ef4444', fast: '#f97316', medium: '#3b82f6', slow: '#6b7280', dead: '#d1d5db' };
const HEALTH_COLORS = { red: '#ef4444', green: '#10b981', yellow: '#f59e0b' };
const CHART_COLORS = ['#3b82f6', '#10b981', '#f97316', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f43f5e', '#a855f7', '#14b8a6'];

export default function DataVisualization() {
  const [vizData, setVizData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [insights, setInsights] = useState('');
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightQuestion, setInsightQuestion] = useState('');
  const [historicalSummary, setHistoricalSummary] = useState(null);
  const [histYear, setHistYear] = useState('2025');
  const [histType, setHistType] = useState('sale');
  const [histUploading, setHistUploading] = useState(false);
  const [trendGranularity, setTrendGranularity] = useState('auto');

  useEffect(() => { fetchData(); fetchHistorical(); }, []);

  const fetchData = async (sd, ed, gran) => {
    setLoading(true);
    try {
      let url = `${API}/analytics/visualization`;
      const params = new URLSearchParams();
      if (sd || startDate) params.append('start_date', sd || startDate);
      if (ed || endDate) params.append('end_date', ed || endDate);
      params.append('trend_granularity', gran || trendGranularity);
      url += `?${params.toString()}`;
      const res = await axios.get(url);
      setVizData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDateFilter = () => {
    if (startDate && endDate) fetchData(startDate, endDate);
    else { fetchData(); }
  };

  const handleSmartInsights = async () => {
    setInsightsLoading(true);
    try {
      const res = await axios.post(`${API}/analytics/smart-insights`, {
        start_date: startDate || null,
        end_date: endDate || null,
        question: insightQuestion || null
      }, { timeout: 0 });
      setInsights(res.data.insights);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'AI insights failed');
    } finally {
      setInsightsLoading(false);
    }
  };

  const fetchHistorical = async () => {
    try {
      const res = await axios.get(`${API}/historical/summary`);
      setHistoricalSummary(res.data);
    } catch (e) { console.error(e); }
  };

  const handleHistoricalUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setHistUploading(true);
    try {
      const token = sessionStorage.getItem('token');
      const fd = new FormData();
      fd.append('file', file);
      const res = await axios.post(
        `${API}/historical/upload?file_type=${histType}&year=${histYear}`,
        fd,
        { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' } }
      );
      toast.success(res.data.message);
      fetchHistorical();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setHistUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteHistorical = async (year) => {
    if (!window.confirm(`Delete all historical data for ${year}?`)) return;
    try {
      const token = sessionStorage.getItem('token');
      await axios.delete(`${API}/historical/${year}`, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Historical data for ${year} deleted`);
      fetchHistorical();
    } catch (e) { toast.error('Delete failed'); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  const salesByItem = vizData?.sales_by_item?.slice(0, 15).map(i => ({
    name: i.item_name.length > 18 ? i.item_name.slice(0, 18) + '..' : i.item_name,
    kg: i.net_wt_kg,
    tier: i.tier,
    fill: TIER_CHART_COLORS[i.tier] || '#6b7280'
  })) || [];

  const salesByParty = vizData?.sales_by_party?.slice(0, 12).map(i => ({
    name: i.party_name.length > 20 ? i.party_name.slice(0, 20) + '..' : i.party_name,
    kg: i.net_wt_kg
  })) || [];

  const purchasesBySupplier = vizData?.purchases_by_supplier?.slice(0, 12).map(i => ({
    name: i.party_name.length > 20 ? i.party_name.slice(0, 20) + '..' : i.party_name,
    kg: i.net_wt_kg
  })) || [];

  const tierDist = vizData?.tier_distribution?.map(t => ({
    name: t.tier.charAt(0).toUpperCase() + t.tier.slice(1),
    value: t.count,
    fill: TIER_CHART_COLORS[t.tier] || '#6b7280'
  })) || [];

  const salesTrend = vizData?.sales_trend || [];
  const health = vizData?.stock_health || {};

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-4 sm:space-y-6" data-testid="viz-page">
      <div>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Data Visualization</h1>
        <p className="text-sm text-muted-foreground mt-1">Visual analytics for sales, purchases, and inventory health</p>
      </div>

      {/* Date Filter */}
      <Card className="border-border/40">
        <CardContent className="pt-4 pb-3">
          <div className="flex flex-col sm:flex-row gap-3 items-end">
            <div className="flex-1">
              <Label className="text-xs">Start Date</Label>
              <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} data-testid="viz-start-date" />
            </div>
            <div className="flex-1">
              <Label className="text-xs">End Date</Label>
              <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} data-testid="viz-end-date" />
            </div>
            <Button onClick={handleDateFilter} data-testid="viz-filter-btn">
              <Calendar className="h-4 w-4 mr-2" />Apply
            </Button>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="sales" className="space-y-4">
        <TabsList className="grid grid-cols-4 sm:grid-cols-6 w-full">
          <TabsTrigger value="sales" data-testid="tab-sales">Sales</TabsTrigger>
          <TabsTrigger value="purchases" data-testid="tab-purchases">Purchases</TabsTrigger>
          <TabsTrigger value="health" data-testid="tab-health">Health</TabsTrigger>
          <TabsTrigger value="profit" data-testid="tab-profit">
            <IndianRupee className="h-3.5 w-3.5 mr-1" />Profit
          </TabsTrigger>
          <TabsTrigger value="historical" data-testid="tab-historical">
            <Upload className="h-3.5 w-3.5 mr-1" />History
          </TabsTrigger>
          <TabsTrigger value="ai" data-testid="tab-ai">AI</TabsTrigger>
        </TabsList>

        {/* Sales Tab */}
        <TabsContent value="sales" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Top Items by Sales (kg)</CardTitle>
                <CardDescription>Color-coded by movement tier</CardDescription>
              </CardHeader>
              <CardContent>
                {salesByItem.length > 0 ? (
                  <ResponsiveContainer width="100%" height={400}>
                    <BarChart data={salesByItem} layout="vertical" margin={{ left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                      <XAxis type="number" />
                      <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(v) => [`${v} kg`, 'Sales']} />
                      <Bar dataKey="kg" radius={[0, 4, 4, 0]}>
                        {salesByItem.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : <p className="text-center text-muted-foreground py-12">No sales data</p>}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Sales by Customer (kg)</CardTitle>
              </CardHeader>
              <CardContent>
                {salesByParty.length > 0 ? (
                  <ResponsiveContainer width="100%" height={400}>
                    <BarChart data={salesByParty} layout="vertical" margin={{ left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                      <XAxis type="number" />
                      <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(v) => [`${v} kg`, 'Sold']} />
                      <Bar dataKey="kg" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <p className="text-center text-muted-foreground py-12">No customer data</p>}
              </CardContent>
            </Card>
          </div>

          {/* Sales Trend */}
          {salesTrend.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Sales Trend ({vizData?.trend_granularity === 'daily' ? 'Daily' : 'Monthly'})</CardTitle>
                  <div className="flex gap-1">
                    {['daily', 'monthly', 'auto'].map(g => (
                      <Button key={g} size="sm" variant={trendGranularity === g ? 'default' : 'outline'} className="text-xs h-7 px-2.5" data-testid={`trend-${g}`}
                        onClick={() => { setTrendGranularity(g); fetchData(startDate, endDate, g); }}>
                        {g === 'auto' ? 'Auto' : g === 'daily' ? 'Daily' : 'Monthly'}
                      </Button>
                    ))}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={salesTrend}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} angle={vizData?.trend_granularity === 'daily' ? -45 : 0} textAnchor={vizData?.trend_granularity === 'daily' ? 'end' : 'middle'} height={vizData?.trend_granularity === 'daily' ? 60 : 30} />
                    <YAxis />
                    <Tooltip formatter={(v) => [`${v} kg`, 'Sales']} />
                    <Line type="monotone" dataKey="net_wt_kg" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Purchases Tab */}
        <TabsContent value="purchases" className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Purchases by Supplier (kg)</CardTitle>
            </CardHeader>
            <CardContent>
              {purchasesBySupplier.length > 0 ? (
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={purchasesBySupplier} layout="vertical" margin={{ left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => [`${v} kg`, 'Purchased']} />
                    <Bar dataKey="kg" fill="#10b981" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <p className="text-center text-muted-foreground py-12">No purchase data</p>}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Stock Health Tab */}
        <TabsContent value="health" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Movement Tier Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                {tierDist.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={tierDist} cx="50%" cy="50%" outerRadius={100} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                        {tierDist.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <p className="text-center text-muted-foreground py-12">Run categorization first</p>}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Stock Health</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4 pt-4">
                  {[
                    { label: 'Below Minimum (Red)', count: health.red || 0, color: 'bg-red-500' },
                    { label: 'Healthy (Green)', count: health.green || 0, color: 'bg-emerald-500' },
                    { label: 'Overstocked (Yellow)', count: health.yellow || 0, color: 'bg-amber-400' },
                  ].map((item, idx) => (
                    <div key={idx} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span>{item.label}</span>
                        <span className="font-mono font-bold">{item.count}</span>
                      </div>
                      <div className="h-3 bg-muted rounded-full overflow-hidden">
                        <div className={`h-full ${item.color} rounded-full transition-all`}
                          style={{ width: `${Math.max(((item.count / (Object.values(health).reduce((a, b) => a + b, 0) || 1)) * 100), 2)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* AI Insights Tab */}
        <TabsContent value="ai" className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-purple-500" />Smart Analytics (AI)
              </CardTitle>
              <CardDescription>Powered by Claude - ask questions about your data</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-3">
                <Input
                  value={insightQuestion}
                  onChange={e => setInsightQuestion(e.target.value)}
                  placeholder="Ask a question or leave blank for general insights..."
                  className="flex-1"
                  data-testid="ai-question-input"
                />
                <Button onClick={handleSmartInsights} disabled={insightsLoading} data-testid="ai-insights-btn">
                  {insightsLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Sparkles className="h-4 w-4 mr-2" />}
                  {insightsLoading ? 'Analyzing...' : 'Get Insights'}
                </Button>
              </div>
              {insights && (
                <div className="bg-gradient-to-br from-purple-50 to-blue-50 border border-purple-100 rounded-lg p-4 prose prose-sm max-w-none" data-testid="ai-insights-result">
                  <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">{insights}</pre>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Historical Profit Analysis Tab */}
        <TabsContent value="profit" className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-emerald-500" />Historical Profit Analysis
              </CardTitle>
              <CardDescription>
                Profit breakdown from uploaded historical data — does not affect current operations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <HistoricalProfit years={historicalSummary?.years || ['2025']} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Historical Data Upload Tab */}
        <TabsContent value="historical" className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <Upload className="h-5 w-5 text-blue-500" />Historical Data Upload
              </CardTitle>
              <CardDescription>
                Upload previous years' sales/purchase files here for AI training. This data does NOT affect current stock calculations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-3 items-end">
                <div>
                  <Label className="text-xs">Year</Label>
                  <Select value={histYear} onValueChange={setHistYear}>
                    <SelectTrigger className="w-28" data-testid="hist-year-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {['2020','2021','2022','2023','2024','2025'].map(y => (
                        <SelectItem key={y} value={y}>{y}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs">Type</Label>
                  <Select value={histType} onValueChange={setHistType}>
                    <SelectTrigger className="w-32" data-testid="hist-type-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="sale">Sales</SelectItem>
                      <SelectItem value="purchase">Purchases</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs">Excel File</Label>
                  <Input
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={handleHistoricalUpload}
                    disabled={histUploading}
                    data-testid="hist-file-input"
                  />
                </div>
                {histUploading && <Loader2 className="h-5 w-5 animate-spin text-blue-500" />}
              </div>

              {/* Uploaded Historical Data Summary */}
              {historicalSummary?.years?.length > 0 ? (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Uploaded Historical Data</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Table className="min-w-[640px]">
                      <TableHeader>
                        <TableRow>
                          <TableHead>Year</TableHead>
                          <TableHead>Sales</TableHead>
                          <TableHead>Purchases</TableHead>
                          <TableHead className="text-right">Action</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {historicalSummary.years.map(year => {
                          const yearData = historicalSummary.summary[year] || {};
                          return (
                            <TableRow key={year}>
                              <TableCell className="font-medium">{year}</TableCell>
                              <TableCell>
                                {yearData.sale ? (
                                  <span className="text-sm">{yearData.sale.count} txns ({yearData.sale.total_kg} kg)</span>
                                ) : <span className="text-muted-foreground text-xs">-</span>}
                              </TableCell>
                              <TableCell>
                                {yearData.purchase ? (
                                  <span className="text-sm">{yearData.purchase.count} txns ({yearData.purchase.total_kg} kg)</span>
                                ) : <span className="text-muted-foreground text-xs">-</span>}
                              </TableCell>
                              <TableCell className="text-right">
                                <Button variant="ghost" size="sm" onClick={() => handleDeleteHistorical(year)}>
                                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              ) : (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  No historical data uploaded yet. Upload previous years' sales/purchase Excel files to enable seasonal AI analysis.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
