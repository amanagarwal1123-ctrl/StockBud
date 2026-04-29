import { useEffect, useState } from 'react';
import axios from 'axios';
import { Users, TrendingUp, Award, Package, Calendar, Download, ChevronDown, ChevronUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatIndianCurrency } from '@/utils/formatCurrency';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { exportToCSV } from '@/utils/exportCSV';
import { useSortableData } from '@/hooks/useSortableData';
import { SortableHeader } from '@/components/SortableHeader';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export default function PartyAnalytics() {
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const [partyData, setPartyData] = useState(null);
  const [customerProfit, setCustomerProfit] = useState(null);
  const [supplierProfit, setSupplierProfit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [selectedMonth, setSelectedMonth] = useState(currentMonth);

  const [customerPage, setCustomerPage] = useState(1);
  const [supplierPage, setSupplierPage] = useState(1);
  const [custProfitPage, setCustProfitPage] = useState(1);
  const [suppProfitPage, setSuppProfitPage] = useState(1);
  const [itemsPerPage] = useState(20);

  const [expandedParty, setExpandedParty] = useState(null);
  const [partyBreakdown, setPartyBreakdown] = useState(null);
  const [breakdownLoading, setBreakdownLoading] = useState(false);
  const [chartMetric, setChartMetric] = useState('total_net_wt');

  const custSort = useSortableData(partyData?.customers, 'total_net_wt', 'desc');
  const suppSort = useSortableData(partyData?.suppliers, 'total_net_wt', 'desc');
  const custProfSort = useSortableData(customerProfit?.customers, 'silver_profit_kg', 'desc');
  const suppProfSort = useSortableData(supplierProfit?.suppliers, 'silver_profit_kg', 'desc');

  useEffect(() => {
    fetchAll(selectedYear, selectedMonth);
  }, []);

  const fetchAll = async (year, month) => {
    setLoading(true);
    try {
      const [partyRes, custProfRes, suppProfRes] = await Promise.all([
        axios.get(`${API}/analytics/monthly-party?year=${year}&month=${month}`),
        fetchCustProfitForMonth(year, month),
        fetchSuppProfitForMonth(year, month),
      ]);
      setPartyData(partyRes.data);
      setCustomerProfit(custProfRes);
      setSupplierProfit(suppProfRes);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCustProfitForMonth = async (year, month) => {
    const { start, end } = getMonthDates(year, month);
    try {
      let url = `${API}/analytics/customer-profit`;
      if (start && end) url += `?start_date=${start}&end_date=${end}`;
      const res = await axios.get(url);
      return res.data;
    } catch { return null; }
  };

  const fetchSuppProfitForMonth = async (year, month) => {
    const { start, end } = getMonthDates(year, month);
    try {
      let url = `${API}/analytics/supplier-profit`;
      if (start && end) url += `?start_date=${start}&end_date=${end}`;
      const res = await axios.get(url);
      return res.data;
    } catch { return null; }
  };

  const getMonthDates = (year, month) => {
    if (month === 0) return { start: `${year}-01-01`, end: `${year}-12-31` };
    const start = `${year}-${String(month).padStart(2, '0')}-01`;
    const lastDay = new Date(year, month, 0).getDate();
    const end = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
    return { start, end };
  };

  const handleMonthClick = (month) => {
    setSelectedMonth(month);
    setCustomerPage(1); setSupplierPage(1);
    setCustProfitPage(1); setSuppProfitPage(1);
    setExpandedParty(null); setPartyBreakdown(null);
    fetchAll(selectedYear, month);
  };

  const handleYearChange = (year) => {
    const yr = Number(year);
    setSelectedYear(yr);
    setExpandedParty(null); setPartyBreakdown(null);
    fetchAll(yr, selectedMonth);
  };

  const handleExpandParty = async (partyName, partyType) => {
    const key = `${partyType}__${partyName}`;
    if (expandedParty === key) {
      setExpandedParty(null);
      setPartyBreakdown(null);
      return;
    }
    setExpandedParty(key);
    setBreakdownLoading(true);
    try {
      const res = await axios.get(`${API}/analytics/party-monthly-breakdown/${encodeURIComponent(partyName)}?year=${selectedYear}&party_type=${partyType}`);
      setPartyBreakdown(res.data);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setBreakdownLoading(false);
    }
  };

  const handleExportCustomers = () => {
    exportToCSV((partyData?.customers || []).map((c, i) => ({
      'Rank': i + 1, 'Customer': c.party_name, 'Net Wt (kg)': (c.total_net_wt / 1000).toFixed(3),
      'Fine Wt (kg)': (c.total_fine_wt / 1000).toFixed(3), 'Sales Value': c.total_sales_value, 'Txns': c.transaction_count
    })), `customers_${selectedYear}_${selectedMonth === 0 ? 'ALL' : MONTHS[selectedMonth - 1]}`);
  };
  const handleExportSuppliers = () => {
    exportToCSV((partyData?.suppliers || []).map((s, i) => ({
      'Rank': i + 1, 'Supplier': s.party_name, 'Net Wt (kg)': (s.total_net_wt / 1000).toFixed(3),
      'Fine Wt (kg)': (s.total_fine_wt / 1000).toFixed(3), 'Purchase Value': s.total_purchases_value, 'Txns': s.transaction_count
    })), `suppliers_${selectedYear}_${selectedMonth === 0 ? 'ALL' : MONTHS[selectedMonth - 1]}`);
  };

  const paginate = (data, page) => {
    const start = (page - 1) * itemsPerPage;
    return { items: (data || []).slice(start, start + itemsPerPage), totalPages: Math.ceil((data || []).length / itemsPerPage), startIdx: start };
  };

  const custPag = paginate(custSort.sortedData, customerPage);
  const suppPag = paginate(suppSort.sortedData, supplierPage);
  const custProfPag = paginate(custProfSort.sortedData, custProfitPage);
  const suppProfPag = paginate(suppProfSort.sortedData, suppProfitPage);

  const yearOptions = [];
  for (let y = currentYear; y >= currentYear - 2; y--) yearOptions.push(y);

  const Pager = ({ page, setPage, totalPages, total }) => totalPages > 1 ? (
    <div className="flex flex-col sm:flex-row items-center justify-between mt-3 pt-3 border-t gap-2">
      <span className="text-xs text-muted-foreground">{total} entries</span>
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

      {/* Year + Month Selector */}
      <Card className="border-border/40 shadow-sm">
        <CardContent className="p-3 sm:p-4">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <Calendar className="h-4 w-4 text-primary shrink-0" />
              <Select value={String(selectedYear)} onValueChange={handleYearChange}>
                <SelectTrigger className="w-24 h-8 text-xs font-mono" data-testid="year-selector">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {yearOptions.map(y => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Button
                onClick={() => handleMonthClick(0)}
                variant={selectedMonth === 0 ? "default" : "outline"}
                size="sm" className="h-7 text-xs px-3 font-semibold"
                data-testid="month-all"
              >ALL</Button>
              {MONTHS.map((m, idx) => (
                <Button
                  key={idx}
                  onClick={() => handleMonthClick(idx + 1)}
                  variant={selectedMonth === idx + 1 ? "default" : "outline"}
                  size="sm" className="h-7 text-xs px-2.5"
                  data-testid={`month-${idx + 1}`}
                >{m}</Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-20"><div className="text-muted-foreground">Loading...</div></div>
      ) : (
        <>
          {/* Top Cards */}
          {(partyData?.top_customer || partyData?.top_supplier) && (
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
              {partyData?.top_customer && (
                <Card className="border-2 border-primary/20 shadow-sm bg-gradient-to-br from-primary/5 to-transparent">
                  <CardHeader className="p-3 sm:p-4 pb-1">
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-1.5 text-sm sm:text-base"><Award className="h-4 w-4 text-primary" />Top Customer</CardTitle>
                      <Badge className="bg-primary text-[10px]">#1</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="p-3 sm:p-4 pt-1">
                    <p className="text-base sm:text-xl font-bold truncate">{partyData.top_customer.party_name}</p>
                    <div className="mt-2 space-y-1 text-xs sm:text-sm">
                      <div className="flex justify-between"><span className="text-muted-foreground">Net Wt:</span><span className="font-mono font-semibold text-primary">{(partyData.top_customer.total_net_wt / 1000).toFixed(3)} kg</span></div>
                      <div className="flex justify-between"><span className="text-muted-foreground">Fine Wt:</span><span className="font-mono font-semibold text-green-600">{(partyData.top_customer.total_fine_wt / 1000).toFixed(3)} kg</span></div>
                      <div className="flex justify-between"><span className="text-muted-foreground">Sales:</span><span className="font-mono">{formatIndianCurrency(partyData.top_customer.total_sales_value)}</span></div>
                    </div>
                  </CardContent>
                </Card>
              )}
              {partyData?.top_supplier && (
                <Card className="border-2 border-green-500/20 shadow-sm bg-gradient-to-br from-green-500/5 to-transparent">
                  <CardHeader className="p-3 sm:p-4 pb-1">
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-1.5 text-sm sm:text-base"><Package className="h-4 w-4 text-green-600" />Top Supplier</CardTitle>
                      <Badge className="bg-green-600 text-[10px]">#1</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="p-3 sm:p-4 pt-1">
                    <p className="text-base sm:text-xl font-bold truncate">{partyData.top_supplier.party_name}</p>
                    <div className="mt-2 space-y-1 text-xs sm:text-sm">
                      <div className="flex justify-between"><span className="text-muted-foreground">Net Wt:</span><span className="font-mono font-semibold text-primary">{(partyData.top_supplier.total_net_wt / 1000).toFixed(3)} kg</span></div>
                      <div className="flex justify-between"><span className="text-muted-foreground">Fine Wt:</span><span className="font-mono font-semibold text-green-600">{(partyData.top_supplier.total_fine_wt / 1000).toFixed(3)} kg</span></div>
                      <div className="flex justify-between"><span className="text-muted-foreground">Purchases:</span><span className="font-mono">{formatIndianCurrency(partyData.top_supplier.total_purchases_value)}</span></div>
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
                      <CardTitle className="text-sm sm:text-base">
                        {selectedMonth === 0 ? `All of ${selectedYear}` : `${MONTHS[selectedMonth - 1]} ${selectedYear}`} — Customers
                      </CardTitle>
                      <CardDescription className="text-xs">Click row for monthly comparison</CardDescription>
                    </div>
                    <Button onClick={handleExportCustomers} variant="outline" size="sm" className="h-7 text-xs self-start">
                      <Download className="h-3 w-3 mr-1" />Export
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-2 sm:p-6 pt-0">
                  <div className="overflow-x-auto">
                    <Table className="min-w-[680px]">
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs w-[30px]"></TableHead>
                          <TableHead className="text-xs w-8">#</TableHead>
                          <SortableHeader label="Customer" sortKey="party_name" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs" />
                          <SortableHeader label="Net Wt (kg)" sortKey="total_net_wt" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Fine Wt (kg)" sortKey="total_fine_wt" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Sales Value" sortKey="total_sales_value" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Txns" sortKey="transaction_count" sortConfig={custSort.sortConfig} onSort={(k) => { custSort.requestSort(k); setCustomerPage(1); }} className="text-xs text-right" />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {custPag.items.length === 0 ? (
                          <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground text-xs">No data for this period</TableCell></TableRow>
                        ) : custPag.items.map((c, idx) => {
                          const key = `customer__${c.party_name}`;
                          return (
                            <>
                              <TableRow
                                key={c.party_name}
                                className="cursor-pointer hover:bg-muted/50"
                                onClick={() => handleExpandParty(c.party_name, 'customer')}
                                data-testid={`customer-row-${idx}`}
                              >
                                <TableCell className="text-xs py-1.5 w-[30px] text-muted-foreground">
                                  {expandedParty === key ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                                </TableCell>
                                <TableCell className="text-xs py-1.5 text-muted-foreground">{custPag.startIdx + idx + 1}</TableCell>
                                <TableCell className="text-xs py-1.5 font-medium truncate max-w-[150px]">{c.party_name}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5 text-primary font-semibold">{(c.total_net_wt / 1000).toFixed(3)}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5 text-green-600">{(c.total_fine_wt / 1000).toFixed(3)}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5">{formatIndianCurrency(c.total_sales_value)}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5">{c.transaction_count}</TableCell>
                              </TableRow>
                              {expandedParty === key && (
                                <TableRow key={`${c.party_name}-chart`}>
                                  <TableCell colSpan={7} className="p-3 bg-muted/30">
                                    <PartyBreakdownChart data={partyBreakdown} loading={breakdownLoading} metric={chartMetric} onMetricChange={setChartMetric} partyType="customer" />
                                  </TableCell>
                                </TableRow>
                              )}
                            </>
                          );
                        })}
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
                      <CardTitle className="text-sm sm:text-base">
                        {selectedMonth === 0 ? `All of ${selectedYear}` : `${MONTHS[selectedMonth - 1]} ${selectedYear}`} — Suppliers
                      </CardTitle>
                      <CardDescription className="text-xs">Click row for monthly comparison</CardDescription>
                    </div>
                    <Button onClick={handleExportSuppliers} variant="outline" size="sm" className="h-7 text-xs self-start">
                      <Download className="h-3 w-3 mr-1" />Export
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-2 sm:p-6 pt-0">
                  <div className="overflow-x-auto">
                    <Table className="min-w-[680px]">
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs w-[30px]"></TableHead>
                          <TableHead className="text-xs w-8">#</TableHead>
                          <SortableHeader label="Supplier" sortKey="party_name" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs" />
                          <SortableHeader label="Net Wt (kg)" sortKey="total_net_wt" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Fine Wt (kg)" sortKey="total_fine_wt" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Purch. Value" sortKey="total_purchases_value" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Txns" sortKey="transaction_count" sortConfig={suppSort.sortConfig} onSort={(k) => { suppSort.requestSort(k); setSupplierPage(1); }} className="text-xs text-right" />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {suppPag.items.length === 0 ? (
                          <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground text-xs">No data for this period</TableCell></TableRow>
                        ) : suppPag.items.map((s, idx) => {
                          const key = `supplier__${s.party_name}`;
                          return (
                            <>
                              <TableRow
                                key={s.party_name}
                                className="cursor-pointer hover:bg-muted/50"
                                onClick={() => handleExpandParty(s.party_name, 'supplier')}
                                data-testid={`supplier-row-${idx}`}
                              >
                                <TableCell className="text-xs py-1.5 w-[30px] text-muted-foreground">
                                  {expandedParty === key ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                                </TableCell>
                                <TableCell className="text-xs py-1.5 text-muted-foreground">{suppPag.startIdx + idx + 1}</TableCell>
                                <TableCell className="text-xs py-1.5 font-medium truncate max-w-[150px]">{s.party_name}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5 text-primary font-semibold">{(s.total_net_wt / 1000).toFixed(3)}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5 text-green-600">{(s.total_fine_wt / 1000).toFixed(3)}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5">{formatIndianCurrency(s.total_purchases_value)}</TableCell>
                                <TableCell className="text-right font-mono text-xs py-1.5">{s.transaction_count}</TableCell>
                              </TableRow>
                              {expandedParty === key && (
                                <TableRow key={`${s.party_name}-chart`}>
                                  <TableCell colSpan={7} className="p-3 bg-muted/30">
                                    <PartyBreakdownChart data={partyBreakdown} loading={breakdownLoading} metric={chartMetric} onMetricChange={setChartMetric} partyType="supplier" />
                                  </TableCell>
                                </TableRow>
                              )}
                            </>
                          );
                        })}
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
                  <CardTitle className="text-sm sm:text-base">Customer-Wise Profit — {selectedMonth === 0 ? `All ${selectedYear}` : `${MONTHS[selectedMonth - 1]} ${selectedYear}`}</CardTitle>
                  <CardDescription className="text-xs">Profit from each customer (silver & labour)</CardDescription>
                </CardHeader>
                <CardContent className="p-2 sm:p-6 pt-0">
                  <div className="overflow-x-auto">
                    <Table className="min-w-[640px]">
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs w-8">#</TableHead>
                          <SortableHeader label="Customer" sortKey="customer_name" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs" />
                          <SortableHeader label="Silver (kg)" sortKey="silver_profit_kg" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Labour" sortKey="labour_profit_inr" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Sold (kg)" sortKey="total_sold_kg" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Txns" sortKey="transaction_count" sortConfig={custProfSort.sortConfig} onSort={(k) => { custProfSort.requestSort(k); setCustProfitPage(1); }} className="text-xs text-right" />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {custProfPag.items.length === 0 ? (
                          <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-xs">No data</TableCell></TableRow>
                        ) : custProfPag.items.map((c, idx) => (
                          <TableRow key={idx}>
                            <TableCell className="text-xs py-1.5 text-muted-foreground">{custProfPag.startIdx + idx + 1}</TableCell>
                            <TableCell className="text-xs py-1.5 font-medium truncate max-w-[150px]">{c.customer_name}</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5 text-green-600 font-semibold">{c.silver_profit_kg?.toFixed(3)}</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5 text-blue-600 font-semibold">{formatIndianCurrency(c.labour_profit_inr)}</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5">{c.total_sold_kg?.toFixed(3)}</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5">{c.transaction_count}</TableCell>
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
                  <CardTitle className="text-sm sm:text-base">Supplier-Wise Profit — {selectedMonth === 0 ? `All ${selectedYear}` : `${MONTHS[selectedMonth - 1]} ${selectedYear}`}</CardTitle>
                  <CardDescription className="text-xs">Profit from items supplied by each supplier</CardDescription>
                </CardHeader>
                <CardContent className="p-2 sm:p-6 pt-0">
                  <div className="overflow-x-auto">
                    <Table className="min-w-[640px]">
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs w-8">#</TableHead>
                          <SortableHeader label="Supplier" sortKey="supplier_name" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs" />
                          <SortableHeader label="Purchased (kg)" sortKey="total_purchased_kg" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Silver (kg)" sortKey="silver_profit_kg" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Labour" sortKey="labor_profit_inr" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right" />
                          <SortableHeader label="Items" sortKey="items_count" sortConfig={suppProfSort.sortConfig} onSort={(k) => { suppProfSort.requestSort(k); setSuppProfitPage(1); }} className="text-xs text-right" />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {suppProfPag.items.length === 0 ? (
                          <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-xs">No data</TableCell></TableRow>
                        ) : suppProfPag.items.map((s, idx) => (
                          <TableRow key={idx}>
                            <TableCell className="text-xs py-1.5 text-muted-foreground">{suppProfPag.startIdx + idx + 1}</TableCell>
                            <TableCell className="text-xs py-1.5 font-medium truncate max-w-[150px]">{s.supplier_name}</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5 text-blue-600">{s.total_purchased_kg?.toFixed(3)}</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5 text-green-600 font-semibold">{s.silver_profit_kg?.toFixed(3)} kg</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5 text-primary font-semibold">{formatIndianCurrency(s.labor_profit_inr || 0)}</TableCell>
                            <TableCell className="text-right font-mono text-xs py-1.5 text-muted-foreground">{s.items_count || 0}</TableCell>
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
        </>
      )}
    </div>
  );
}

/** Bar chart for party monthly breakdown */
function PartyBreakdownChart({ data, loading, metric, onMetricChange, partyType }) {
  if (loading) return <div className="text-center py-4 text-xs text-muted-foreground">Loading chart...</div>;
  if (!data || !data.months) return <div className="text-center py-4 text-xs text-muted-foreground">No data</div>;

  const chartData = data.months.map(m => ({
    name: MONTHS[m.month - 1],
    total_net_wt: (m.total_net_wt || 0) / 1000,
    total_sales_value: m.total_sales_value || 0,
    total_purchases_value: m.total_purchases_value || 0,
    transaction_count: m.transaction_count || 0,
  }));

  const metricOptions = partyType === 'customer'
    ? [
        { key: 'total_net_wt', label: 'Net Wt (kg)', color: '#7c3aed' },
        { key: 'total_sales_value', label: 'Sales Value', color: '#2563eb' },
        { key: 'transaction_count', label: 'Transactions', color: '#d97706' },
      ]
    : [
        { key: 'total_net_wt', label: 'Net Wt (kg)', color: '#7c3aed' },
        { key: 'total_purchases_value', label: 'Purch. Value', color: '#16a34a' },
        { key: 'transaction_count', label: 'Transactions', color: '#d97706' },
      ];

  const activeMetric = metricOptions.find(m => m.key === metric) || metricOptions[0];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-muted-foreground">Show:</span>
        {metricOptions.map(opt => (
          <Button
            key={opt.key}
            onClick={(e) => { e.stopPropagation(); onMetricChange(opt.key); }}
            variant={metric === opt.key ? "default" : "outline"}
            size="sm" className="h-6 text-[10px] px-2"
          >{opt.label}</Button>
        ))}
      </div>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} width={50} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} formatter={(value) => [typeof value === 'number' ? value.toFixed(2) : value, activeMetric.label]} />
            <Bar dataKey={activeMetric.key} fill={activeMetric.color} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
