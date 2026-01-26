import { useEffect, useState } from 'react';
import axios from 'axios';
import { TrendingUp, DollarSign, ShoppingCart, Package } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ProfitAnalysis() {
  const [profitData, setProfitData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProfit();
  }, []);

  const fetchProfit = async () => {
    try {
      const response = await axios.get(`${API}/analytics/profit`);
      setProfitData(response.data);
    } catch (error) {
      console.error('Error fetching profit:', error);
    } finally {
      setLoading(false);
    }
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
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-primary/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              Total Profit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-primary">
              ₹{profitData?.total_profit?.toLocaleString() || 0}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-accent/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Package className="h-4 w-4 text-accent" />
              Tunch Profit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-accent">
              ₹{profitData?.tunch_profit?.toLocaleString() || 0}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-secondary/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-secondary" />
              Labour Profit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-secondary">
              ₹{profitData?.labor_profit?.toLocaleString() || 0}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <ShoppingCart className="h-4 w-4" />
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
                  <TableHead className="text-right font-mono">Sales</TableHead>
                  <TableHead className="text-right font-mono">Purchases</TableHead>
                  <TableHead className="text-right font-mono">Profit</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {profitData?.top_profitable_items?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                      No profit data available
                    </TableCell>
                  </TableRow>
                ) : (
                  profitData?.top_profitable_items?.slice(0, 15).map((item, idx) => (
                    <TableRow key={idx} className="table-row">
                      <TableCell className="font-medium">{item.item_name}</TableCell>
                      <TableCell className="text-right font-mono text-primary">
                        ₹{item.sales.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono text-secondary">
                        ₹{item.purchases.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        <Badge className={item.profit > 0 ? 'bg-accent' : 'bg-destructive'}>
                          ₹{item.profit.toLocaleString()}
                        </Badge>
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
