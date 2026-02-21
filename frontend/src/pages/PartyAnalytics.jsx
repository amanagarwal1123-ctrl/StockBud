import { useEffect, useState } from 'react';
import axios from 'axios';
import { Users, TrendingUp, Award, Package, Calendar, Download } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatIndianCurrency } from '@/utils/formatCurrency';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { exportToCSV } from '@/utils/exportCSV';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PartyAnalytics() {
  const [analytics, setAnalytics] = useState(null);
  const [customerProfit, setCustomerProfit] = useState(null);
  const [supplierProfit, setSupplierProfit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [customerPage, setCustomerPage] = useState(1);
  const [supplierPage, setSupplierPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  useEffect(() => {
    fetchAnalytics();
    fetchCustomerProfit();
    fetchSupplierProfit();
  }, []);

  const fetchAnalytics = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/party-analysis`;
      if (start && end) {
        url += `?start_date=${start}&end_date=${end}`;
      }
      const response = await axios.get(url);
      setAnalytics(response.data);
    } catch (error) {
      console.error('Error fetching party analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomerProfit = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/customer-profit`;
      if (start && end) {
        url += `?start_date=${start}&end_date=${end}`;
      }
      const response = await axios.get(url);
      setCustomerProfit(response.data);
    } catch (error) {
      console.error('Error fetching customer profit:', error);
    }
  };

  const fetchSupplierProfit = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/supplier-profit`;
      if (start && end) {
        url += `?start_date=${start}&end_date=${end}`;
      }
      const response = await axios.get(url);
      setSupplierProfit(response.data);
    } catch (error) {
      console.error('Error fetching supplier profit:', error);
    }
  };

  const handleApplyDateRange = () => {
    if (startDate && endDate) {
      fetchAnalytics(startDate, endDate);
      fetchCustomerProfit(startDate, endDate);
      fetchSupplierProfit(startDate, endDate);
    }
  };

  const handleClearDates = () => {
    setStartDate('');
    setEndDate('');
    fetchAnalytics();
    fetchCustomerProfit();
    fetchSupplierProfit();
  };

  const setQuickRange = (days) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    
    setStartDate(start.toISOString().split('T')[0]);
    setEndDate(end.toISOString().split('T')[0]);
    fetchAnalytics(start.toISOString().split('T')[0], end.toISOString().split('T')[0]);
    fetchCustomerProfit(start.toISOString().split('T')[0], end.toISOString().split('T')[0]);
    fetchSupplierProfit(start.toISOString().split('T')[0], end.toISOString().split('T')[0]);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading analytics...</div>
      </div>
    );
  }

  const topCustomers = analytics?.customers || [];
  const topSuppliers = analytics?.suppliers || [];

  // Pagination for customers
  const customerStartIdx = (customerPage - 1) * itemsPerPage;
  const customerEndIdx = customerStartIdx + itemsPerPage;
  const paginatedCustomers = topCustomers.slice(customerStartIdx, customerEndIdx);
  const totalCustomerPages = Math.ceil(topCustomers.length / itemsPerPage);

  // Pagination for suppliers
  const supplierStartIdx = (supplierPage - 1) * itemsPerPage;
  const supplierEndIdx = supplierStartIdx + itemsPerPage;
  const paginatedSuppliers = topSuppliers.slice(supplierStartIdx, supplierEndIdx);
  const totalSupplierPages = Math.ceil(topSuppliers.length / itemsPerPage);

  const handleExportCustomers = () => {
    const exportData = (analytics?.customers || []).map((customer, idx) => ({
      'Rank': idx + 1,
      'Customer Name': customer.party_name,
      'Net Weight (kg)': (customer.total_net_wt / 1000).toFixed(3),
      'Fine Weight (kg)': (customer.total_fine_wt / 1000).toFixed(3),
      'Sales Value': customer.total_sales_value,
      'Transactions': customer.transaction_count
    }));
    
    const dateStr = startDate && endDate ? `_${startDate}_to_${endDate}` : '';
    exportToCSV(exportData, `customers${dateStr}`);
  };

  const handleExportSuppliers = () => {
    const exportData = (analytics?.suppliers || []).map((supplier, idx) => ({
      'Rank': idx + 1,
      'Supplier Name': supplier.party_name,
      'Net Weight (kg)': (supplier.total_net_wt / 1000).toFixed(3),
      'Fine Weight (kg)': (supplier.total_fine_wt / 1000).toFixed(3),
      'Purchase Value': supplier.total_purchases_value,
      'Transactions': supplier.transaction_count
    }));
    
    const dateStr = startDate && endDate ? `_${startDate}_to_${endDate}` : '';
    exportToCSV(exportData, `suppliers${dateStr}`);
  };

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="party-analytics-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight" data-testid="party-analytics-title">
          Party Analytics
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          Customer and supplier insights with profitability analysis
        </p>
      </div>

      {/* Date Range Selector */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Calendar className="h-5 w-5 text-primary" />
            Date Range Filter
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1">
              <Label htmlFor="start-date" className="text-sm font-medium mb-2">From Date</Label>
              <Input
                id="start-date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="font-mono"
              />
            </div>
            <div className="flex-1">
              <Label htmlFor="end-date" className="text-sm font-medium mb-2">To Date</Label>
              <Input
                id="end-date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="font-mono"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleApplyDateRange} disabled={!startDate || !endDate}>
                Apply
              </Button>
              <Button onClick={handleClearDates} variant="outline">
                Clear
              </Button>
            </div>
          </div>
          
          {/* Quick Range Buttons */}
          <div className="flex flex-wrap gap-2 mt-4">
            <Button onClick={() => setQuickRange(7)} variant="secondary" size="sm">
              Last 7 Days
            </Button>
            <Button onClick={() => setQuickRange(30)} variant="secondary" size="sm">
              Last 30 Days
            </Button>
            <Button onClick={() => setQuickRange(90)} variant="secondary" size="sm">
              Last 3 Months
            </Button>
            <Button onClick={() => setQuickRange(365)} variant="secondary" size="sm">
              Last Year
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Top Party Cards */}
      {(analytics?.top_customer || analytics?.top_supplier) && (
        <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-2">
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
                    <span className="text-muted-foreground">Net Silver Weight:</span>
                    <span className="font-mono font-semibold text-primary">
                      {(analytics.top_customer.total_net_wt / 1000).toFixed(3)} kg
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Fine Silver Weight:</span>
                    <span className="font-mono font-semibold text-accent">
                      {(analytics.top_customer.total_fine_wt / 1000).toFixed(3)} kg
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Sales Value:</span>
                    <span className="font-mono">
                      {formatIndianCurrency(analytics.top_customer.total_sales_value)}
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
                    <span className="text-muted-foreground">Net Silver Weight:</span>
                    <span className="font-mono font-semibold text-primary">
                      {(analytics.top_supplier.total_net_wt / 1000).toFixed(3)} kg
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Fine Silver Weight:</span>
                    <span className="font-mono font-semibold text-accent">
                      {(analytics.top_supplier.total_fine_wt / 1000).toFixed(3)} kg
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Purchase Value:</span>
                    <span className="font-mono">
                      {formatIndianCurrency(analytics.top_supplier.total_purchases_value)}
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
      <Tabs defaultValue="customers" className="space-y-4 sm:space-y-6">
        <TabsList>
          <TabsTrigger value="customers" data-testid="tab-customers">
            <Users className="h-4 w-4 mr-2" />
            Customers
          </TabsTrigger>
          <TabsTrigger value="suppliers" data-testid="tab-suppliers">
            <Package className="h-4 w-4 mr-2" />
            Suppliers
          </TabsTrigger>
          <TabsTrigger value="customer-profit">
            <TrendingUp className="h-4 w-4 mr-2" />
            Customer Profit
          </TabsTrigger>
          <TabsTrigger value="supplier-profit">
            <TrendingUp className="h-4 w-4 mr-2" />
            Supplier Profit
          </TabsTrigger>
        </TabsList>

        <TabsContent value="customers">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Top Customers by Sales</CardTitle>
                  <CardDescription>Ranked by net silver weight sold</CardDescription>
                </div>
                <Button onClick={handleExportCustomers} variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rank</TableHead>
                      <TableHead>Customer Name</TableHead>
                      <TableHead className="text-right font-mono">Net Wt (kg)</TableHead>
                      <TableHead className="text-right font-mono hidden sm:table-cell">Fine Wt (kg)</TableHead>
                      <TableHead className="text-right font-mono hidden sm:table-cell">Sales Value</TableHead>
                      <TableHead className="text-right hidden md:table-cell">Count</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedCustomers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                          No customer data available
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedCustomers.map((customer, idx) => {
                        const actualRank = customerStartIdx + idx + 1;
                        return (
                          <TableRow key={idx} className="table-row" data-testid={`customer-row-${idx}`}>
                            <TableCell>
                              <Badge variant="outline" className="font-mono">
                                #{actualRank}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-medium">{customer.party_name}</TableCell>
                            <TableCell className="text-right font-mono text-primary font-semibold">
                              {(customer.total_net_wt / 1000).toFixed(3)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-accent font-semibold">
                              {(customer.total_fine_wt / 1000).toFixed(3)}
                            </TableCell>
                            <TableCell className="text-right font-mono">
                              {formatIndianCurrency(customer.total_sales_value)}
                            </TableCell>
                            <TableCell className="text-right font-mono">
                              {customer.transaction_count}
                            </TableCell>
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination Controls */}
              {topCustomers.length > 10 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Items per page:</span>
                    <Select value={String(itemsPerPage)} onValueChange={(val) => { setItemsPerPage(Number(val)); setCustomerPage(1); }}>
                      <SelectTrigger className="w-20">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="10">10</SelectItem>
                        <SelectItem value="20">20</SelectItem>
                        <SelectItem value="30">30</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => setCustomerPage(p => Math.max(1, p - 1))}
                      disabled={customerPage === 1}
                      variant="outline"
                      size="sm"
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {customerPage} of {totalCustomerPages} ({topCustomers.length} total)
                    </span>
                    <Button
                      onClick={() => setCustomerPage(p => Math.min(totalCustomerPages, p + 1))}
                      disabled={customerPage === totalCustomerPages}
                      variant="outline"
                      size="sm"
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="suppliers">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Top Suppliers by Purchases</CardTitle>
                  <CardDescription>Ranked by net silver weight purchased</CardDescription>
                </div>
                <Button onClick={handleExportSuppliers} variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rank</TableHead>
                      <TableHead>Supplier Name</TableHead>
                      <TableHead className="text-right font-mono">Net Wt (kg)</TableHead>
                      <TableHead className="text-right font-mono hidden sm:table-cell">Fine Wt (kg)</TableHead>
                      <TableHead className="text-right font-mono hidden sm:table-cell">Purchase Value</TableHead>
                      <TableHead className="text-right hidden md:table-cell">Count</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedSuppliers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                          No supplier data available
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedSuppliers.map((supplier, idx) => {
                        const actualRank = supplierStartIdx + idx + 1;
                        return (
                          <TableRow key={idx} className="table-row" data-testid={`supplier-row-${idx}`}>
                            <TableCell>
                              <Badge variant="outline" className="font-mono">
                                #{actualRank}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-medium">{supplier.party_name}</TableCell>
                            <TableCell className="text-right font-mono text-primary font-semibold">
                              {(supplier.total_net_wt / 1000).toFixed(3)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-accent font-semibold">
                              {(supplier.total_fine_wt / 1000).toFixed(3)}
                            </TableCell>
                            <TableCell className="text-right font-mono">
                              {formatIndianCurrency(supplier.total_purchases_value)}
                            </TableCell>
                            <TableCell className="text-right font-mono">
                              {supplier.transaction_count}
                            </TableCell>
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination Controls */}
              {topSuppliers.length > 10 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Items per page:</span>
                    <Select value={String(itemsPerPage)} onValueChange={(val) => { setItemsPerPage(Number(val)); setSupplierPage(1); }}>
                      <SelectTrigger className="w-20">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="10">10</SelectItem>
                        <SelectItem value="20">20</SelectItem>
                        <SelectItem value="30">30</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => setSupplierPage(p => Math.max(1, p - 1))}
                      disabled={supplierPage === 1}
                      variant="outline"
                      size="sm"
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {supplierPage} of {totalSupplierPages} ({topSuppliers.length} total)
                    </span>
                    <Button
                      onClick={() => setSupplierPage(p => Math.min(totalSupplierPages, p + 1))}
                      disabled={supplierPage === totalSupplierPages}
                      variant="outline"
                      size="sm"
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>


        {/* Customer Profit Tab */}
        <TabsContent value="customer-profit">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <CardTitle>Customer-Wise Profit</CardTitle>
              <CardDescription>Profit made from each customer (silver & labour)</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rank</TableHead>
                    <TableHead>Customer Name</TableHead>
                    <TableHead className="text-right font-mono">Silver Profit (kg)</TableHead>
                    <TableHead className="text-right font-mono">Labour Profit</TableHead>
                    <TableHead className="text-right font-mono">Total Sold (kg)</TableHead>
                    <TableHead className="text-right">Transactions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {customerProfit?.customers?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        No customer profit data available
                      </TableCell>
                    </TableRow>
                  ) : (
                    customerProfit?.customers?.map((customer, idx) => (
                      <TableRow key={idx}>
                        <TableCell>
                          <Badge variant="outline" className="font-mono">#{idx + 1}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{customer.customer_name}</TableCell>
                        <TableCell className="text-right font-mono text-green-600 font-semibold">
                          {customer.silver_profit_kg?.toFixed(3)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-blue-600 font-semibold">
                          {formatIndianCurrency(customer.labour_profit_inr)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {customer.total_sold_kg?.toFixed(3)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {customer.transaction_count}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Supplier Profit Tab */}
        <TabsContent value="supplier-profit">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <CardTitle>Supplier-Wise Profit</CardTitle>
              <CardDescription>Profit earned from items supplied by each supplier</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rank</TableHead>
                    <TableHead>Supplier Name</TableHead>
                    <TableHead className="text-right font-mono">Total Purchased (kg)</TableHead>
                    <TableHead className="text-right font-mono">Silver Profit (kg)</TableHead>
                    <TableHead className="text-right font-mono">Labour Profit (₹)</TableHead>
                    <TableHead className="text-right">Items Count</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {supplierProfit?.suppliers?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        No supplier data available
                      </TableCell>
                    </TableRow>
                  ) : (
                    supplierProfit?.suppliers?.map((supplier, idx) => (
                      <TableRow key={idx}>
                        <TableCell>
                          <Badge variant="outline" className="font-mono">#{idx + 1}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{supplier.supplier_name}</TableCell>
                        <TableCell className="text-right font-mono text-blue-600">
                          {supplier.total_purchased_kg?.toFixed(3)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-green-600 font-semibold">
                          {supplier.silver_profit_kg?.toFixed(3)} kg
                        </TableCell>
                        <TableCell className="text-right font-mono text-primary font-semibold">
                          {formatIndianCurrency(supplier.labor_profit_inr || 0)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-muted-foreground">
                          {supplier.items_count || 0}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

      </Tabs>
    </div>
  );
}
