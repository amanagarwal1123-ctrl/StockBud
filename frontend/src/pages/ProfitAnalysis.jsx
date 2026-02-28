import { useEffect, useState } from 'react';
import axios from 'axios';
import { TrendingUp, DollarSign, ShoppingCart, Package, Calendar, Download } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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

export default function ProfitAnalysis() {
  const [profitData, setProfitData] = useState(null);
  const [salesSummary, setSalesSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  useEffect(() => { fetchProfit(); fetchSalesSummary(); }, []);

  const fetchProfit = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/profit`;
      if (start && end) url += `?start_date=${start}&end_date=${end}`;
      const response = await axios.get(url);
      setProfitData(response.data);
    } catch (error) { console.error('Error:', error); }
    finally { setLoading(false); }
  };

  const fetchSalesSummary = async (start = '', end = '') => {
    try {
      let url = `${API}/analytics/sales-summary`;
      if (start && end) url += `?start_date=${start}&end_date=${end}`;
      const response = await axios.get(url);
      setSalesSummary(response.data);
    } catch (error) { console.error('Error:', error); }
  };

  const handleApplyDateRange = () => {
    if (startDate && endDate) { fetchProfit(startDate, endDate); fetchSalesSummary(startDate, endDate); }
  };
  const handleClearDates = () => { setStartDate(''); setEndDate(''); fetchProfit(); fetchSalesSummary(); };
  const setQuickRange = (days) => {
    const end = new Date(); const start = new Date();
    start.setDate(start.getDate() - days);
    const s = start.toISOString().split('T')[0], e = end.toISOString().split('T')[0];
    setStartDate(s); setEndDate(e); fetchProfit(s, e); fetchSalesSummary(s, e);
  };

  const handleExportProfit = () => {
    const exportData = (profitData?.all_items || []).map((item, idx) => ({
      'Rank': idx + 1, 'Item Name': item.item_name, 'Net Weight Sold (kg)': item.net_wt_sold_kg,
      'Avg Purchase Tunch (%)': item.avg_purchase_tunch, 'Avg Sale Tunch (%)': item.avg_sale_tunch,
      'Silver Profit (kg)': item.silver_profit_kg, 'Labour Profit (₹)': item.labor_profit_inr
    }));
    exportToCSV(exportData, `profit_analysis${startDate && endDate ? `_${startDate}_to_${endDate}` : ''}`);
  };

  const allItems = profitData?.all_items || [];
  const { sortedData: sortedItems, sortConfig, requestSort } = useSortableData(allItems, 'silver_profit_kg', 'desc');

  if (loading) return <div className="flex items-center justify-center h-screen"><div className="text-muted-foreground">Loading...</div></div>;

  const startIdx = (currentPage - 1) * itemsPerPage;
  const paginatedItems = sortedItems.slice(startIdx, startIdx + itemsPerPage);
  const totalPages = Math.ceil(sortedItems.length / itemsPerPage);

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="profit-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">Profit Analysis</h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-1">Silver trading profit based on tunch &amp; labour</p>
      </div>

      {/* Date Range */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader className="p-3 sm:p-6 pb-2">
          <CardTitle className="flex items-center gap-2 text-sm sm:text-lg">
            <Calendar className="h-4 w-4 text-primary" />Date Range
          </CardTitle>
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
              <Button onClick={handleApplyDateRange} disabled={!startDate || !endDate} size="sm" className="h-8 text-xs">Apply</Button>
              <Button onClick={handleClearDates} variant="outline" size="sm" className="h-8 text-xs">Clear</Button>
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

      {/* Summary Cards */}
      <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-4">
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-green-500/10 to-transparent">
          <CardHeader className="p-2 sm:p-4 pb-1">
            <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
              <Package className="h-3 w-3 sm:h-4 sm:w-4 text-green-600" />Silver Profit
            </CardTitle>
          </CardHeader>
          <CardContent className="p-2 sm:p-4 pt-0">
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono text-green-600">
              {profitData?.silver_profit_kg?.toLocaleString() || 0} kg
            </div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-blue-500/10 to-transparent">
          <CardHeader className="p-2 sm:p-4 pb-1">
            <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
              <DollarSign className="h-3 w-3 sm:h-4 sm:w-4 text-blue-600" />Labour Profit
            </CardTitle>
          </CardHeader>
          <CardContent className="p-2 sm:p-4 pt-0">
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono text-blue-600">
              {formatIndianCurrency(profitData?.labor_profit_inr || 0)}
            </div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-accent/10 to-transparent">
          <CardHeader className="p-2 sm:p-4 pb-1">
            <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
              <ShoppingCart className="h-3 w-3 sm:h-4 sm:w-4 text-accent" />Total Sales
            </CardTitle>
          </CardHeader>
          <CardContent className="p-2 sm:p-4 pt-0">
            {salesSummary ? (
              <div className="space-y-0.5">
                <div className="flex justify-between"><span className="text-[10px] text-muted-foreground">Net:</span><span className="text-xs sm:text-sm font-bold font-mono text-green-600">{salesSummary.total_net_wt_kg} kg</span></div>
                <div className="flex justify-between"><span className="text-[10px] text-muted-foreground">Fine:</span><span className="text-xs sm:text-sm font-bold font-mono text-blue-600">{salesSummary.total_fine_wt_kg} kg</span></div>
                <div className="flex justify-between"><span className="text-[10px] text-muted-foreground">Labour:</span><span className="text-xs sm:text-sm font-bold font-mono text-purple-600">{formatIndianCurrency(salesSummary.total_labor)}</span></div>
              </div>
            ) : (
              <div className="text-lg sm:text-3xl font-bold font-mono text-accent">{formatIndianCurrency(profitData?.total_sales_value || 0)}</div>
            )}
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="p-2 sm:p-4 pb-1">
            <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
              <TrendingUp className="h-3 w-3 sm:h-4 sm:w-4" />Items
            </CardTitle>
          </CardHeader>
          <CardContent className="p-2 sm:p-4 pt-0">
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{profitData?.total_items_analyzed || 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Item Profit Table */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader className="p-3 sm:p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <CardTitle className="text-sm sm:text-base">Most Profitable Items</CardTitle>
              <CardDescription className="text-xs">Items generating the highest profit margin</CardDescription>
            </div>
            <Button onClick={handleExportProfit} variant="outline" size="sm" className="h-7 text-xs self-start">
              <Download className="h-3 w-3 mr-1" />Export
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-2 sm:p-6 pt-0">
          <div className="overflow-x-auto">
            <Table className="table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs w-10">#</TableHead>
                  <SortableHeader label="Item" sortKey="item_name" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-xs w-[180px]" />
                  <SortableHeader label="Sold (kg)" sortKey="net_wt_sold_kg" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs" />
                  <SortableHeader label="Buy Tunch" sortKey="avg_purchase_tunch" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs" />
                  <SortableHeader label="Sell Tunch" sortKey="avg_sale_tunch" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs" />
                  <SortableHeader label="Silver" sortKey="silver_profit_kg" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs" />
                  <SortableHeader label="Labour" sortKey="labor_profit_inr" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedItems.map((item, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="text-xs py-2 text-muted-foreground">{startIdx + idx + 1}</TableCell>
                    <TableCell className="text-xs py-2 font-medium truncate">{item.item_name}</TableCell>
                    <TableCell className="text-right font-mono text-xs py-2">{item.net_wt_sold_kg}</TableCell>
                    <TableCell className="text-right font-mono text-xs py-2">{item.avg_purchase_tunch}%</TableCell>
                    <TableCell className="text-right font-mono text-xs py-2">{item.avg_sale_tunch}%</TableCell>
                    <TableCell className="text-right font-mono text-xs py-2 text-green-600 font-semibold">{item.silver_profit_kg} kg</TableCell>
                    <TableCell className="text-right font-mono text-xs py-2 text-blue-600 font-semibold">{formatIndianCurrency(item.labor_profit_inr)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {allItems.length > 10 && (
            <div className="flex flex-col sm:flex-row items-center justify-between mt-3 pt-3 border-t gap-2">
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Per page:</span>
                <Select value={String(itemsPerPage)} onValueChange={(v) => { setItemsPerPage(Number(v)); setCurrentPage(1); }}>
                  <SelectTrigger className="w-16 h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {[10, 20, 30].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-1.5">
                <Button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} variant="outline" size="sm" className="h-7 text-xs">Prev</Button>
                <span className="text-xs text-muted-foreground">{currentPage}/{totalPages}</span>
                <Button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} variant="outline" size="sm" className="h-7 text-xs">Next</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
