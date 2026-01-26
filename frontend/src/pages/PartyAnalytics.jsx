import { useEffect, useState } from 'react';
import axios from 'axios';
import { Users, TrendingUp, Award, Package } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PartyAnalytics() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API}/analytics/party-analysis`);
      setAnalytics(response.data);
    } catch (error) {
      console.error('Error fetching party analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading analytics...</div>
      </div>
    );
  }

  const topCustomers = analytics?.customers?.slice(0, 10) || [];
  const topSuppliers = analytics?.suppliers?.slice(0, 10) || [];

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="party-analytics-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight" data-testid="party-analytics-title">
          Party Analytics
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Customer and supplier insights with profitability analysis
        </p>
      </div>

      {/* Top Party Cards */}
      {(analytics?.top_customer || analytics?.top_supplier) && (
        <div className="grid gap-6 md:grid-cols-2">
          {analytics?.top_customer && (
            <Card className="border-2 border-primary/20 shadow-md bg-gradient-to-br from-primary/5 to-transparent">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Award className="h-5 w-5 text-primary" />
                    Top Customer
                  </CardTitle>
                  <Badge className="bg-primary">
                    #{1}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{analytics.top_customer.party_name}</p>
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Total Sales:</span>
                    <span className="font-mono font-semibold text-primary">
                      ₹{analytics.top_customer.total_sales.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Transactions:</span>
                    <span className="font-mono">{analytics.top_customer.transaction_count}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {analytics?.top_supplier && (
            <Card className="border-2 border-accent/20 shadow-md bg-gradient-to-br from-accent/5 to-transparent">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Package className="h-5 w-5 text-accent" />
                    Top Supplier
                  </CardTitle>
                  <Badge className="bg-accent">
                    #{1}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{analytics.top_supplier.party_name}</p>
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Total Purchases:</span>
                    <span className="font-mono font-semibold text-accent">
                      ₹{analytics.top_supplier.total_purchases.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Transactions:</span>
                    <span className="font-mono">{analytics.top_supplier.transaction_count}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Tabs for Customers and Suppliers */}
      <Tabs defaultValue="customers" className="space-y-6">
        <TabsList>
          <TabsTrigger value="customers" data-testid="tab-customers">
            <Users className="h-4 w-4 mr-2" />
            Customers
          </TabsTrigger>
          <TabsTrigger value="suppliers" data-testid="tab-suppliers">
            <Package className="h-4 w-4 mr-2" />
            Suppliers
          </TabsTrigger>
        </TabsList>

        <TabsContent value="customers">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <CardTitle>Top Customers by Sales</CardTitle>
              <CardDescription>Ranked by total sales value</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rank</TableHead>
                      <TableHead>Customer Name</TableHead>
                      <TableHead className="text-right font-mono">Total Sales</TableHead>
                      <TableHead className="text-right">Transactions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topCustomers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                          No customer data available
                        </TableCell>
                      </TableRow>
                    ) : (
                      topCustomers.map((customer, idx) => (
                        <TableRow key={idx} className="table-row" data-testid={`customer-row-${idx}`}>
                          <TableCell>
                            <Badge variant="outline" className="font-mono">
                              #{idx + 1}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-medium">{customer.party_name}</TableCell>
                          <TableCell className="text-right font-mono text-primary font-semibold">
                            ₹{customer.total_sales.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {customer.transaction_count}
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

        <TabsContent value="suppliers">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <CardTitle>Top Suppliers by Purchases</CardTitle>
              <CardDescription>Ranked by total purchase value</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rank</TableHead>
                      <TableHead>Supplier Name</TableHead>
                      <TableHead className="text-right font-mono">Total Purchases</TableHead>
                      <TableHead className="text-right">Transactions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topSuppliers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                          No supplier data available
                        </TableCell>
                      </TableRow>
                    ) : (
                      topSuppliers.map((supplier, idx) => (
                        <TableRow key={idx} className="table-row" data-testid={`supplier-row-${idx}`}>
                          <TableCell>
                            <Badge variant="outline" className="font-mono">
                              #{idx + 1}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-medium">{supplier.party_name}</TableCell>
                          <TableCell className="text-right font-mono text-accent font-semibold">
                            ₹{supplier.total_purchases.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {supplier.transaction_count}
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
