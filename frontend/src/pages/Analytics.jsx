import { useEffect, useState } from 'react';
import axios from 'axios';
import { TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLORS = {
  fast: 'hsl(158, 64%, 24%)',
  good: 'hsl(217, 91%, 60%)',
  slow: 'hsl(32, 95%, 44%)',
  dead: 'hsl(0, 72%, 35%)',
};

export default function Analytics() {
  const [movementData, setMovementData] = useState([]);
  const [polyExceptions, setPolyExceptions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const [movementRes, polyRes] = await Promise.all([
        axios.get(`${API}/analytics/movement`),
        axios.get(`${API}/analytics/poly-exceptions`),
      ]);
      setMovementData(movementRes.data);
      setPolyExceptions(polyRes.data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const getCategoryIcon = (category) => {
    switch (category) {
      case 'fast':
        return <TrendingUp className="h-4 w-4" />;
      case 'slow':
        return <TrendingDown className="h-4 w-4" />;
      case 'dead':
        return <AlertTriangle className="h-4 w-4" />;
      default:
        return <Minus className="h-4 w-4" />;
    }
  };

  const getCategoryBadge = (category) => {
    const configs = {
      fast: 'text-emerald-700 bg-emerald-50 border-emerald-200',
      good: 'text-blue-700 bg-blue-50 border-blue-200',
      slow: 'text-amber-700 bg-amber-50 border-amber-200',
      dead: 'text-red-700 bg-red-50 border-red-200',
    };
    return configs[category] || '';
  };

  // Prepare chart data
  const categoryCounts = movementData.reduce(
    (acc, item) => {
      acc[item.movement_category] = (acc[item.movement_category] || 0) + 1;
      return acc;
    },
    { fast: 0, good: 0, slow: 0, dead: 0 }
  );

  const pieData = [
    { name: 'Fast Moving', value: categoryCounts.fast, color: COLORS.fast },
    { name: 'Good', value: categoryCounts.good, color: COLORS.good },
    { name: 'Slow Moving', value: categoryCounts.slow, color: COLORS.slow },
    { name: 'Dead Stock', value: categoryCounts.dead, color: COLORS.dead },
  ].filter((item) => item.value > 0);

  const topMovers = [...movementData]
    .sort((a, b) => b.monthly_sale_kg - a.monthly_sale_kg)
    .slice(0, 10);

  const barData = topMovers.map((item) => ({
    name: item.item_name.substring(0, 20) + '...',
    sales: parseFloat(item.monthly_sale_kg.toFixed(3)),
  }));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading analytics...</div>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6" data-testid="analytics-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight" data-testid="analytics-title">
          Analytics & Insights
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          Item movement analysis and exceptions
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-4">
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-600" />
              Fast Moving
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{categoryCounts.fast}</div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Minus className="h-4 w-4 text-blue-600" />
              Good
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{categoryCounts.good}</div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-amber-600" />
              Slow Moving
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{categoryCounts.slow}</div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              Dead Stock
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{categoryCounts.dead}</div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle>Movement Distribution</CardTitle>
            <CardDescription>Breakdown by category</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle>Top 10 Sellers</CardTitle>
            <CardDescription>Monthly sales in kg</CardDescription>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-45} textAnchor="end" height={100} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="sales" fill={COLORS.fast} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Tabs for detailed data */}
      <Tabs defaultValue="movement" className="space-y-6">
        <TabsList>
          <TabsTrigger value="movement" data-testid="tab-movement">
            Movement Analysis
          </TabsTrigger>
          <TabsTrigger value="exceptions" data-testid="tab-exceptions">
            Poly Weight Exceptions
          </TabsTrigger>
        </TabsList>

        <TabsContent value="movement">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <CardTitle>Item Movement Details</CardTitle>
              <CardDescription>
                Based on 2000kg/month baseline: Fast (150-300kg), Good (50kg), Slow (15kg), Dead (≤2kg)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Item Name</TableHead>
                      <TableHead>Stamp</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead className="text-right font-mono">Monthly Sales (kg)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {movementData.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                          No movement data available
                        </TableCell>
                      </TableRow>
                    ) : (
                      movementData.map((item, idx) => (
                        <TableRow key={idx} className="table-row" data-testid={`movement-row-${idx}`}>
                          <TableCell className="font-medium">{item.item_name}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="font-mono text-xs">
                              {item.stamp || 'Unassigned'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge className={`${getCategoryBadge(item.movement_category)} border`}>
                              {getCategoryIcon(item.movement_category)}
                              <span className="ml-1 capitalize">{item.movement_category}</span>
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {item.monthly_sale_kg.toFixed(3)}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="exceptions">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                Poly Weight Exceptions
              </CardTitle>
              <CardDescription>
                Items with poly weight ratios deviating significantly from the average
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Item Name</TableHead>
                      <TableHead>Stamp</TableHead>
                      <TableHead className="text-right font-mono">Gross Wt (g)</TableHead>
                      <TableHead className="text-right font-mono">Poly Wt (g)</TableHead>
                      <TableHead className="text-right font-mono">Ratio (%)</TableHead>
                      <TableHead>Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {polyExceptions.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                          No exceptions found
                        </TableCell>
                      </TableRow>
                    ) : (
                      polyExceptions.map((item, idx) => (
                        <TableRow key={idx} className="table-row" data-testid={`exception-row-${idx}`}>
                          <TableCell className="font-medium">{item.item_name}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="font-mono text-xs">
                              {item.stamp || 'Unassigned'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono">{item.gr_wt.toFixed(3)}</TableCell>
                          <TableCell className="text-right font-mono">{item.poly_wt.toFixed(3)}</TableCell>
                          <TableCell className="text-right font-mono">
                            <span className="text-amber-600 font-semibold">
                              {item.poly_ratio.toFixed(2)}%
                            </span>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {item.exception_reason}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}