import { useEffect, useState } from 'react';
import axios from 'axios';
import { TrendingUp, DollarSign, ShoppingCart, Package, Calendar } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatIndianCurrency } from '@/utils/formatCurrency';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ProfitAnalysis() {
  const [profitData, setProfitData] = useState(null);
  const [salesSummary, setSalesSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  useEffect(() => {
    fetchProfit();
    fetchSalesSummary();
  }, []);

  const fetchProfit = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/profit`;
      if (start && end) {
        url += `?start_date=${start}&end_date=${end}`;
      }
      const response = await axios.get(url);
      setProfitData(response.data);
    } catch (error) {
      console.error('Error fetching profit:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSalesSummary = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/sales-summary`;
      if (start && end) {
        url += `?start_date=${start}&end_date=${end}`;
      }
      const response = await axios.get(url);
      setSalesSummary(response.data);
    } catch (error) {
      console.error('Error fetching sales summary:', error);
    }
  };

  const handleApplyDateRange = () => {
    if (startDate && endDate) {
      fetchProfit(startDate, endDate);
      fetchSalesSummary(startDate, endDate);
    }
  };

  const handleClearDates = () => {
    setStartDate('');
    setEndDate('');
    fetchProfit();
    fetchSalesSummary();
  };

  const setQuickRange = (days) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    
    const startStr = start.toISOString().split('T')[0];
    const endStr = end.toISOString().split('T')[0];
    
    setStartDate(startStr);
    setEndDate(endStr);
    fetchProfit(startStr, endStr);
    fetchSalesSummary(startStr, endStr);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading profit data...</div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="profit-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Profit Analysis
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Silver trading profit based on tunch difference and labour margins
        </p>
      </div>

      {/* Profit Cards */}
      <div className="grid gap-6 md:grid-cols-4">
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-green-500/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Package className="h-4 w-4 text-green-600" />
              Silver Profit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-green-600">
              {profitData?.silver_profit_kg?.toLocaleString() || 0} kg
            </div>
            <p className="text-xs text-muted-foreground mt-1">Difference in tunch/purity</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-blue-500/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-blue-600" />
              Labour Profit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-blue-600">
              {formatIndianCurrency(profitData?.labor_profit_inr || 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Labour margin difference</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-accent/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <ShoppingCart className="h-4 w-4 text-accent" />
              Total Sales
            </CardTitle>
          </CardHeader>
          <CardContent>
            {salesSummary ? (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted-foreground">Net Wt:</span>
                  <span className="text-lg font-bold font-mono text-green-600">
                    {salesSummary.total_net_wt_kg} kg
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted-foreground">Fine:</span>
                  <span className="text-lg font-bold font-mono text-blue-600">
                    {salesSummary.total_fine_wt_kg} kg
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted-foreground">Labour:</span>
                  <span className="text-lg font-bold font-mono text-purple-600">
                    {formatIndianCurrency(salesSummary.total_labor)}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-3xl font-bold font-mono text-accent">
                {formatIndianCurrency(profitData?.total_sales_value || 0)}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Items Analyzed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono">
              {profitData?.total_items_analyzed || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Profitable Items */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle>Most Profitable Items</CardTitle>
          <CardDescription>Items generating the highest profit margin</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item Name</TableHead>
                  <TableHead className="text-right font-mono">Net Wt Sold (kg)</TableHead>
                  <TableHead className="text-right">Avg Purchase Tunch</TableHead>
                  <TableHead className="text-right">Avg Sale Tunch</TableHead>
                  <TableHead className="text-right font-mono">Silver Profit (kg)</TableHead>
                  <TableHead className="text-right font-mono">Labour Profit (₹)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {profitData?.top_profitable_items?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No profit data available
                    </TableCell>
                  </TableRow>
                ) : (
                  profitData?.top_profitable_items?.slice(0, 15).map((item, idx) => (
                    <TableRow key={idx} className="table-row">
                      <TableCell className="font-medium">{item.item_name}</TableCell>
                      <TableCell className="text-right font-mono">{item.net_wt_sold_kg}</TableCell>
                      <TableCell className="text-right font-mono">{item.avg_purchase_tunch}%</TableCell>
                      <TableCell className="text-right font-mono">{item.avg_sale_tunch}%</TableCell>
                      <TableCell className="text-right font-mono text-green-600 font-semibold">
                        {item.silver_profit_kg} kg
                      </TableCell>
                      <TableCell className="text-right font-mono text-blue-600 font-semibold">
                        {formatIndianCurrency(item.labor_profit_inr)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
