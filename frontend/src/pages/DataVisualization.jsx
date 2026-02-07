import { useEffect, useState } from 'react';
import axios from 'axios';
import { BarChart3, TrendingUp, Calendar, Sparkles, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, Legend } from 'recharts';
import { toast } from 'sonner';

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

  useEffect(() => { fetchData(); }, []);

  const fetchData = async (sd, ed) => {
    setLoading(true);
    try {
      let url = `${API}/analytics/visualization`;
      const params = new URLSearchParams();
      if (sd || startDate) params.append('start_date', sd || startDate);
      if (ed || endDate) params.append('end_date', ed || endDate);
      if (params.toString()) url += `?${params.toString()}`;
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
      });
      setInsights(res.data.insights);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'AI insights failed');
    } finally {
      setInsightsLoading(false);
    }
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
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="viz-page">
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
        <TabsList className="grid grid-cols-4 w-full max-w-lg">
          <TabsTrigger value="sales" data-testid="tab-sales">Sales</TabsTrigger>
          <TabsTrigger value="purchases" data-testid="tab-purchases">Purchases</TabsTrigger>
          <TabsTrigger value="health" data-testid="tab-health">Stock Health</TabsTrigger>
          <TabsTrigger value="ai" data-testid="tab-ai">Smart AI</TabsTrigger>
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

          {/* Monthly Sales Trend */}
          {salesTrend.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Monthly Sales Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={salesTrend}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis />
                    <Tooltip formatter={(v) => [`${v} kg`, 'Sales']} />
                    <Line type="monotone" dataKey="net_wt_kg" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
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
      </Tabs>
    </div>
  );
}
