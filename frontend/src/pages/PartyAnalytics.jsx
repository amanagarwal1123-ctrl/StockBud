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
import { useSortableData } from '@/hooks/useSortableData';
import { SortableHeader } from '@/components/SortableHeader';

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
  const [custProfitPage, setCustProfitPage] = useState(1);
  const [suppProfitPage, setSuppProfitPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Sortable data for each tab
  const custSort = useSortableData(analytics?.customers, 'total_net_wt', 'desc');
  const suppSort = useSortableData(analytics?.suppliers, 'total_net_wt', 'desc');
  const custProfSort = useSortableData(customerProfit?.customers, 'silver_profit_kg', 'desc');
  const suppProfSort = useSortableData(supplierProfit?.suppliers, 'silver_profit_kg', 'desc');

  useEffect(() => { fetchAnalytics(); fetchCustomerProfit(); fetchSupplierProfit(); }, []);

  const fetchAnalytics = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/party-analysis`;
      if (start && end) url += `?start_date=${start}&end_date=${end}`;
      const response = await axios.get(url);
      setAnalytics(response.data);
    } catch (error) { console.error('Error:', error); }
    finally { setLoading(false); }
  };

  const fetchCustomerProfit = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/customer-profit`;
      if (start && end) url += `?start_date=${start}&end_date=${end}`;
      const response = await axios.get(url);
      setCustomerProfit(response.data);
    } catch (error) { console.error('Error:', error); }
  };

  const fetchSupplierProfit = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/supplier-profit`;
      if (start && end) url += `?start_date=${start}&end_date=${end}`;
      const response = await axios.get(url);
      setSupplierProfit(response.data);
    } catch (error) { console.error('Error:', error); }
  };

  const handleApply = () => {
    if (startDate && endDate) { fetchAnalytics(startDate, endDate); fetchCustomerProfit(startDate, endDate); fetchSupplierProfit(startDate, endDate); }
  };
  const handleClear = () => { setStartDate(''); setEndDate(''); fetchAnalytics(); fetchCustomerProfit(); fetchSupplierProfit(); };
  const setQuickRange = (days) => {
    const end = new Date(), start = new Date();
    start.setDate(start.getDate() - days);
    const s = start.toISOString().split('T')[0], e = end.toISOString().split('T')[0];
    setStartDate(s); setEndDate(e); fetchAnalytics(s, e); fetchCustomerProfit(s, e); fetchSupplierProfit(s, e);
  };

  const handleExportCustomers = () => {
    exportToCSV((analytics?.customers || []).map((c, i) => ({
      'Rank': i + 1, 'Customer': c.party_name, 'Net Wt (kg)': (c.total_net_wt / 1000).toFixed(3),
      'Fine Wt (kg)': (c.total_fine_wt / 1000).toFixed(3), 'Sales Value': c.total_sales_value, 'Txns': c.transaction_count
    })), `customers${startDate && endDate ? `_${startDate}_to_${endDate}` : ''}`);
  };
  const handleExportSuppliers = () => {
    exportToCSV((analytics?.suppliers || []).map((s, i) => ({
      'Rank': i + 1, 'Supplier': s.party_name, 'Net Wt (kg)': (s.total_net_wt / 1000).toFixed(3),
      'Fine Wt (kg)': (s.total_fine_wt / 1000).toFixed(3), 'Purchase Value': s.total_purchases_value, 'Txns': s.transaction_count
    })), `suppliers${startDate && endDate ? `_${startDate}_to_${endDate}` : ''}`);
  };

  if (loading) return <div className="flex items-center justify-center h-screen"><div className="text-muted-foreground">Loading...</div></div>;

  // Pagination helper
  const paginate = (data, page) => {
    const start = (page - 1) * itemsPerPage;
    return { items: (data || []).slice(start, start + itemsPerPage), totalPages: Math.ceil((data || []).length / itemsPerPage), startIdx: start };
  };

  const custPag = paginate(custSort.sortedData, customerPage);
  const suppPag = paginate(suppSort.sortedData, supplierPage);
  const custProfPag = paginate(custProfSort.sortedData, custProfitPage);
  const suppProfPag = paginate(suppProfSort.sortedData, suppProfitPage);

  const Pager = ({ page, setPage, totalPages, total }) => totalPages > 1 ? (
    <div className="flex flex-col sm:flex-row items-center justify-between mt-3 pt-3 border-t gap-2">
      <span className="text-xs text-muted-foreground">{total} items</span>
      <div className="flex items-center gap-1.5">
        <Button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} variant="outline" size="sm" className="h-7 text-xs">Prev</Button>
        <span className="text-xs text-muted-foreground">{page}/{totalPages}</span>
        <Button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} variant="outline" size="sm" className="h-7 text-xs">Next</Button>
      </div>
    </div>
  ) : null;

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="party-analytics-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight" data-testid="party-analytics-title">Party Analytics</h1>
        <p className="text-xs sm:text-base text-muted-foreground mt-1">Customer & supplier insights with profitability</p>
      </div>

      {/* Date Range - compact */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader className="p-3 sm:p-6 pb-2">
          <CardTitle className="flex items-center gap-2 text-sm sm:text-lg"><Calendar className="h-4 w-4 text-primary" />Date Range</CardTitle>
        </CardHeader>
        <CardContent className="p-3 sm:p-6 pt-0">
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 sm:items-end">
            <div className="flex gap-2 flex-1">
              <div className="flex-1">
                <Label className="text-xs">From</Label>
                <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="font-mono text-xs h-8 sm:h-9" />
              </div>
              <div className="flex-1">
                <Label className="text-xs">To</Label>
                <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="font-mono text-xs h-8 sm:h-9" />
              </div>
            </div>
            <div className="flex gap-1.5">
              <Button onClick={handleApply} disabled={!startDate || !endDate} size="sm" className="h-8 text-xs">Apply</Button>
              <Button onClick={handleClear} variant="outline" size="sm" className="h-8 text-xs">Clear</Button>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {[7, 30, 90, 365].map(d => (
              <Button key={d} onClick={() => setQuickRange(d)} variant="secondary" size="sm" className="h-6 text-[10px] sm:text-xs sm:h-7">
                {d < 365 ? `${d}d` : '1yr'}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Top Cards - compact mobile */}
      {(analytics?.top_customer || analytics?.top_supplier) && (
        <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
          {analytics?.top_customer && (
            <Card className="border-2 border-primary/20 shadow-sm bg-gradient-to-br from-primary/5 to-transparent">
              <CardHeader className="p-3 sm:p-4 pb-1">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-1.5 text-sm sm:text-base"><Award className="h-4 w-4 text-primary" />Top Customer</CardTitle>
                  <Badge className="bg-primary text-[10px]">#1</Badge>
                </div>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-1">
                <p className="text-base sm:text-xl font-bold truncate">{analytics.top_customer.party_name}</p>
                <div className="mt-2 space-y-1 text-xs sm:text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">Net Wt:</span><span className="font-mono font-semibold text-primary">{(analytics.top_customer.total_net_wt / 1000).toFixed(3)} kg</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Fine Wt:</span><span className="font-mono font-semibold text-green-600">{(analytics.top_customer.total_fine_wt / 1000).toFixed(3)} kg</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Sales:</span><span className="font-mono">{formatIndianCurrency(analytics.top_customer.total_sales_value)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Txns:</span><span className="font-mono">{analytics.top_customer.transaction_count}</span></div>
                </div>
              </CardContent>
            </Card>
          )}
          {analytics?.top_supplier && (
            <Card className="border-2 border-green-500/20 shadow-sm bg-gradient-to-br from-green-500/5 to-transparent">
              <CardHeader className="p-3 sm:p-4 pb-1">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-1.5 text-sm sm:text-base"><Package className="h-4 w-4 text-green-600" />Top Supplier</CardTitle>
                  <Badge className="bg-green-600 text-[10px]">#1</Badge>
                </div>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 pt-1">
                <p className="text-base sm:text-xl font-bold truncate">{analytics.top_supplier.party_name}</p>
                <div className="mt-2 space-y-1 text-xs sm:text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">Net Wt:</span><span className="font-mono font-semibold text-primary">{(analytics.top_supplier.total_net_wt / 1000).toFixed(3)} kg</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Fine Wt:</span><span className="font-mono font-semibold text-green-600">{(analytics.top_supplier.total_fine_wt / 1000).toFixed(3)} kg</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Purchases:</span><span className="font-mono">{formatIndianCurrency(analytics.top_supplier.total_purchases_value)}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Txns:</span><span className="font-mono">{analytics.top_supplier.transaction_count}</span></div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="customers" className="space-y-3">
        <div className="overflow-x-auto -mx-3 px-3">
          <TabsList className="w-max">
            <TabsTrigger value="customers" data-testid="tab-customers" className="text-xs sm:text-sm px-2 sm:px-3">
              <Users className="h-3.5 w-3.5 mr-1 sm:mr-2" />Customers
            </TabsTrigger>
            <TabsTrigger value="suppliers" data-testid="tab-suppliers" className="text-xs sm:text-sm px-2 sm:px-3">
              <Package className="h-3.5 w-3.5 mr-1 sm:mr-2" />Suppliers
            </TabsTrigger>
            <TabsTrigger value="customer-profit" className="text-xs sm:text-sm px-2 sm:px-3">
              <TrendingUp className="h-3.5 w-3.5 mr-1 sm:mr-2" />Cust Profit
            </TabsTrigger>
            <TabsTrigger value="supplier-profit" className="text-xs sm:text-sm px-2 sm:px-3">
              <TrendingUp className="h-3.5 w-3.5 mr-1 sm:mr-2" />Supp Profit
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Customers Tab */}
        <TabsContent value="customers">
          <Card className="border-border/40 shadow-sm">
            <CardHeader className="p-3 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-sm sm:text-base">Top Customers by Sales</CardTitle>
                  <CardDescription className="text-xs">Ranked by net silver weight sold</CardDescription>
                </div>
                <Button onClick={handleExportCustomers} variant="outline" size="sm" className="h-7 text-xs self-start">
                  <Download className="h-3 w-3 mr-1" />Export
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-2 sm:p-6 pt-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs w-8">#</TableHead>
                      <SortableHeader label="Customer" sortKey="party_name" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs" />
                      <SortableHeader label="Net Wt (kg)" sortKey="total_net_wt" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right" />
                      <SortableHeader label="Fine Wt (kg)" sortKey="total_fine_wt" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right hidden sm:table-cell" />
                      <SortableHeader label="Sales Value" sortKey="total_sales_value" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right hidden sm:table-cell" />
                      <SortableHeader label="Txns" sortKey="transaction_count" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right hidden md:table-cell" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {custPag.items.length === 0 ? (
                      <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-xs">No data</TableCell></TableRow>
                    ) : custPag.items.map((c, idx) => (
                      <TableRow key={idx} data-testid={`customer-row-${idx}`}>
                        <TableCell className="text-xs py-1.5 text-muted-foreground">{custPag.startIdx + idx + 1}</TableCell>
                        <TableCell className="text-xs py-1.5 font-medium max-w-[120px] sm:max-w-none truncate">{c.party_name}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-primary font-semibold">{(c.total_net_wt / 1000).toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-green-600 hidden sm:table-cell">{(c.total_fine_wt / 1000).toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 hidden sm:table-cell">{formatIndianCurrency(c.total_sales_value)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 hidden md:table-cell">{c.transaction_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <Pager page={customerPage} setPage={setCustomerPage} totalPages={custPag.totalPages} total={custSort.sortedData?.length || 0} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Suppliers Tab */}
        <TabsContent value="suppliers">
          <Card className="border-border/40 shadow-sm">
            <CardHeader className="p-3 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-sm sm:text-base">Top Suppliers by Purchases</CardTitle>
                  <CardDescription className="text-xs">Ranked by net silver weight purchased</CardDescription>
                </div>
                <Button onClick={handleExportSuppliers} variant="outline" size="sm" className="h-7 text-xs self-start">
                  <Download className="h-3 w-3 mr-1" />Export
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-2 sm:p-6 pt-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs w-8">#</TableHead>
                      <SortableHeader label="Supplier" sortKey="party_name" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs" />
                      <SortableHeader label="Net Wt (kg)" sortKey="total_net_wt" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right" />
                      <SortableHeader label="Fine Wt (kg)" sortKey="total_fine_wt" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right hidden sm:table-cell" />
                      <SortableHeader label="Purch. Value" sortKey="total_purchases_value" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right hidden sm:table-cell" />
                      <SortableHeader label="Txns" sortKey="transaction_count" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right hidden md:table-cell" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {suppPag.items.length === 0 ? (
                      <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-xs">No data</TableCell></TableRow>
                    ) : suppPag.items.map((s, idx) => (
                      <TableRow key={idx} data-testid={`supplier-row-${idx}`}>
                        <TableCell className="text-xs py-1.5 text-muted-foreground">{suppPag.startIdx + idx + 1}</TableCell>
                        <TableCell className="text-xs py-1.5 font-medium max-w-[120px] sm:max-w-none truncate">{s.party_name}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-primary font-semibold">{(s.total_net_wt / 1000).toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-green-600 hidden sm:table-cell">{(s.total_fine_wt / 1000).toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 hidden sm:table-cell">{formatIndianCurrency(s.total_purchases_value)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 hidden md:table-cell">{s.transaction_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <Pager page={supplierPage} setPage={setSupplierPage} totalPages={suppPag.totalPages} total={suppSort.sortedData?.length || 0} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Customer Profit Tab */}
        <TabsContent value="customer-profit">
          <Card className="border-border/40 shadow-sm">
            <CardHeader className="p-3 sm:p-6">
              <CardTitle className="text-sm sm:text-base">Customer-Wise Profit</CardTitle>
              <CardDescription className="text-xs">Profit from each customer (silver & labour)</CardDescription>
            </CardHeader>
            <CardContent className="p-2 sm:p-6 pt-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs w-8">#</TableHead>
                      <SortableHeader label="Customer" sortKey="customer_name" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs" />
                      <SortableHeader label="Silver (kg)" sortKey="silver_profit_kg" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right" />
                      <SortableHeader label="Labour" sortKey="labour_profit_inr" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right" />
                      <SortableHeader label="Sold (kg)" sortKey="total_sold_kg" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right hidden sm:table-cell" />
                      <SortableHeader label="Txns" sortKey="transaction_count" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right hidden md:table-cell" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {custProfPag.items.length === 0 ? (
                      <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-xs">No data</TableCell></TableRow>
                    ) : custProfPag.items.map((c, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="text-xs py-1.5 text-muted-foreground">{custProfPag.startIdx + idx + 1}</TableCell>
                        <TableCell className="text-xs py-1.5 font-medium max-w-[120px] sm:max-w-none truncate">{c.customer_name}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-green-600 font-semibold">{c.silver_profit_kg?.toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-blue-600 font-semibold">{formatIndianCurrency(c.labour_profit_inr)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 hidden sm:table-cell">{c.total_sold_kg?.toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 hidden md:table-cell">{c.transaction_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <Pager page={custProfitPage} setPage={setCustProfitPage} totalPages={custProfPag.totalPages} total={custProfSort.sortedData?.length || 0} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Supplier Profit Tab */}
        <TabsContent value="supplier-profit">
          <Card className="border-border/40 shadow-sm">
            <CardHeader className="p-3 sm:p-6">
              <CardTitle className="text-sm sm:text-base">Supplier-Wise Profit</CardTitle>
              <CardDescription className="text-xs">Profit from items supplied by each supplier</CardDescription>
            </CardHeader>
            <CardContent className="p-2 sm:p-6 pt-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs w-8">#</TableHead>
                      <SortableHeader label="Supplier" sortKey="supplier_name" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs" />
                      <SortableHeader label="Purchased (kg)" sortKey="total_purchased_kg" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right hidden sm:table-cell" />
                      <SortableHeader label="Silver (kg)" sortKey="silver_profit_kg" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right" />
                      <SortableHeader label="Labour" sortKey="labor_profit_inr" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right" />
                      <SortableHeader label="Items" sortKey="items_count" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right hidden md:table-cell" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {suppProfPag.items.length === 0 ? (
                      <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-xs">No data</TableCell></TableRow>
                    ) : suppProfPag.items.map((s, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="text-xs py-1.5 text-muted-foreground">{suppProfPag.startIdx + idx + 1}</TableCell>
                        <TableCell className="text-xs py-1.5 font-medium max-w-[120px] sm:max-w-none truncate">{s.supplier_name}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-blue-600 hidden sm:table-cell">{s.total_purchased_kg?.toFixed(3)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-green-600 font-semibold">{s.silver_profit_kg?.toFixed(3)} kg</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-primary font-semibold">{formatIndianCurrency(s.labor_profit_inr || 0)}</TableCell>
                        <TableCell className="text-right font-mono text-xs py-1.5 text-muted-foreground hidden md:table-cell">{s.items_count || 0}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <Pager page={suppProfitPage} setPage={setSuppProfitPage} totalPages={suppProfPag.totalPages} total={suppProfSort.sortedData?.length || 0} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
