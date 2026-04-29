import { useEffect, useState } from 'react';
import axios from 'axios';
import { TrendingUp, DollarSign, Package, Calendar, Download, ChevronDown, ChevronUp, Users } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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

export default function ProfitAnalysis() {
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const [profitData, setProfitData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [selectedMonth, setSelectedMonth] = useState(currentMonth);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  const [expandedItem, setExpandedItem] = useState(null);
  const [monthlyBreakdown, setMonthlyBreakdown] = useState(null);
  const [breakdownLoading, setBreakdownLoading] = useState(false);
  const [chartMetric, setChartMetric] = useState('silver_profit_kg');
  const [dailyProfits, setDailyProfits] = useState(null);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);
  const [dailyDetail, setDailyDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchMonthlyProfit(selectedYear, selectedMonth);
  }, []);

  const fetchMonthlyProfit = async (year, month) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/analytics/monthly-profit?year=${year}&month=${month}`);
      setProfitData(response.data);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
    // Fetch daily profits if a specific month is selected
    if (month > 0) {
      fetchDailyProfits(year, month);
    } else {
      setDailyProfits(null);
      setSelectedDate(null);
      setDailyDetail(null);
    }
  };

  const fetchDailyProfits = async (year, month) => {
    setDailyLoading(true);
    setSelectedDate(null);
    setDailyDetail(null);
    try {
      const response = await axios.get(`${API}/analytics/daily-profit?year=${year}&month=${month}`);
      setDailyProfits(response.data.daily);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setDailyLoading(false);
    }
  };

  const handleDateClick = async (date) => {
    if (selectedDate === date) {
      setSelectedDate(null);
      setDailyDetail(null);
      return;
    }
    setSelectedDate(date);
    setDetailLoading(true);
    try {
      const response = await axios.get(`${API}/analytics/daily-profit-detail?date=${date}`);
      setDailyDetail(response.data);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleMonthClick = (month) => {
    setSelectedMonth(month);
    setCurrentPage(1);
    setExpandedItem(null);
    setMonthlyBreakdown(null);
    fetchMonthlyProfit(selectedYear, month);
  };

  const handleYearChange = (year) => {
    const yr = Number(year);
    setSelectedYear(yr);
    setCurrentPage(1);
    setExpandedItem(null);
    setMonthlyBreakdown(null);
    fetchMonthlyProfit(yr, selectedMonth);
  };

  const handleExpandItem = async (itemName) => {
    if (expandedItem === itemName) {
      setExpandedItem(null);
      setMonthlyBreakdown(null);
      return;
    }
    setExpandedItem(itemName);
    setBreakdownLoading(true);
    try {
      const response = await axios.get(`${API}/analytics/item-monthly-breakdown/${encodeURIComponent(itemName)}?year=${selectedYear}`);
      setMonthlyBreakdown(response.data);
    } catch (error) {
      console.error('Error fetching breakdown:', error);
    } finally {
      setBreakdownLoading(false);
    }
  };

  const handleExportProfit = () => {
    const exportData = (profitData?.all_items || []).map((item, idx) => ({
      'Rank': idx + 1, 'Item Name': item.item_name, 'Net Weight Sold (kg)': item.net_wt_sold_kg,
      'Avg Purchase Tunch (%)': item.avg_purchase_tunch, 'Avg Sale Tunch (%)': item.avg_sale_tunch,
      'Silver Profit (kg)': item.silver_profit_kg, 'Labour Profit (INR)': item.labor_profit_inr
    }));
    exportToCSV(exportData, `profit_${selectedYear}_${selectedMonth === 0 ? 'ALL' : MONTHS[selectedMonth - 1]}`);
  };

  const allItems = profitData?.all_items || [];
  const { sortedData: sortedItems, sortConfig, requestSort } = useSortableData(allItems, 'silver_profit_kg', 'desc');

  const startIdx = (currentPage - 1) * itemsPerPage;
  const paginatedItems = sortedItems.slice(startIdx, startIdx + itemsPerPage);
  const totalPages = Math.ceil(sortedItems.length / itemsPerPage);

  // Year options (current year and 2 years back)
  const yearOptions = [];
  for (let y = currentYear; y >= currentYear - 2; y--) yearOptions.push(y);

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="profit-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">Profit Analysis</h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-1">Silver trading profit based on tunch &amp; labour</p>
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
                size="sm"
                className="h-7 text-xs px-3 font-semibold"
                data-testid="month-all"
              >
                ALL
              </Button>
              {MONTHS.map((m, idx) => (
                <Button
                  key={idx}
                  onClick={() => handleMonthClick(idx + 1)}
                  variant={selectedMonth === idx + 1 ? "default" : "outline"}
                  size="sm"
                  className="h-7 text-xs px-2.5"
                  data-testid={`month-${idx + 1}`}
                >
                  {m}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-20"><div className="text-muted-foreground">Loading...</div></div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-4">
            <Card className="border-border/40 shadow-sm bg-gradient-to-br from-green-500/10 to-transparent">
              <CardHeader className="p-2 sm:p-4 pb-1">
                <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <Package className="h-3 w-3 sm:h-4 sm:w-4 text-green-600" />Silver Profit
                </CardTitle>
              </CardHeader>
              <CardContent className="p-2 sm:p-4 pt-0">
                <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono text-green-600" data-testid="silver-profit-total">
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
                <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono text-blue-600" data-testid="labor-profit-total">
                  {formatIndianCurrency(profitData?.labor_profit_inr || 0)}
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/40 shadow-sm bg-gradient-to-br from-accent/10 to-transparent">
              <CardHeader className="p-2 sm:p-4 pb-1">
                <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <TrendingUp className="h-3 w-3 sm:h-4 sm:w-4 text-accent" />Total Sales
                </CardTitle>
              </CardHeader>
              <CardContent className="p-2 sm:p-4 pt-0">
                <div className="space-y-0.5">
                  <div className="flex justify-between"><span className="text-[10px] text-muted-foreground">Net:</span><span className="text-xs sm:text-sm font-bold font-mono text-green-600">{((profitData?.total_net_wt_sold || 0) / 1000).toFixed(3)} kg</span></div>
                  <div className="flex justify-between"><span className="text-[10px] text-muted-foreground">Fine:</span><span className="text-xs sm:text-sm font-bold font-mono text-blue-600">{((profitData?.total_fine_wt_sold || 0) / 1000).toFixed(3)} kg</span></div>
                  <div className="flex justify-between"><span className="text-[10px] text-muted-foreground">Labour:</span><span className="text-xs sm:text-sm font-bold font-mono text-purple-600">{formatIndianCurrency(profitData?.total_labour_sold || 0)}</span></div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/40 shadow-sm">
              <CardHeader className="p-2 sm:p-4 pb-1">
                <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground flex items-center gap-1">
                  <Users className="h-3 w-3 sm:h-4 sm:w-4" />Customers
                </CardTitle>
              </CardHeader>
              <CardContent className="p-2 sm:p-4 pt-0">
                <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{profitData?.unique_customers || 0}</div>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {selectedMonth === 0 ? `Year ${selectedYear}` : `${MONTHS[selectedMonth - 1]} ${selectedYear}`}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Daily Profit Breakdown */}
          {selectedMonth > 0 && (
            <Card className="border-border/40 shadow-sm">
              <CardHeader className="p-3 sm:p-6 pb-2">
                <CardTitle className="text-sm sm:text-base">
                  Daily Profit — {MONTHS[selectedMonth - 1]} {selectedYear}
                </CardTitle>
                <CardDescription className="text-xs">Click a date to see top 20 customers & items</CardDescription>
              </CardHeader>
              <CardContent className="p-2 sm:p-6 pt-0">
                {dailyLoading ? (
                  <div className="text-center py-4 text-xs text-muted-foreground">Loading daily data...</div>
                ) : dailyProfits ? (
                  <div className="space-y-1">
                    {dailyProfits.filter(d => d.sale_count > 0 || d.silver_profit_kg !== 0).length === 0 ? (
                      <p className="text-center py-4 text-xs text-muted-foreground">No sales activity this month</p>
                    ) : dailyProfits.map(day => {
                      if (day.sale_count === 0 && day.silver_profit_kg === 0) return null;
                      const isSelected = selectedDate === day.date;
                      const dd = day.date.split('-')[2];
                      return (
                        <div key={day.date}>
                          <div
                            className={`flex items-center justify-between p-2 rounded-md cursor-pointer transition-colors ${isSelected ? 'bg-primary/10 border border-primary/30' : 'hover:bg-muted/50 border border-transparent'}`}
                            onClick={() => handleDateClick(day.date)}
                            data-testid={`daily-row-${day.date}`}
                          >
                            <div className="flex items-center gap-2">
                              {isSelected ? <ChevronUp className="h-3.5 w-3.5 text-primary" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                              <span className="text-xs font-mono font-semibold w-6">{dd}</span>
                              <Badge variant="outline" className="text-[10px] px-1.5">{day.sale_count} sales</Badge>
                            </div>
                            <div className="flex items-center gap-4">
                              <span className="text-xs font-mono text-green-600 font-semibold">{day.silver_profit_kg} kg</span>
                              <span className="text-xs font-mono text-blue-600 font-semibold w-20 text-right">{formatIndianCurrency(day.labor_profit_inr)}</span>
                            </div>
                          </div>
                          {isSelected && (
                            <div className="ml-6 mt-1 mb-2 p-3 rounded-md bg-muted/30 border border-border/30">
                              {detailLoading ? (
                                <p className="text-xs text-muted-foreground text-center py-2">Loading...</p>
                              ) : dailyDetail ? (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  {/* Top Items */}
                                  <div>
                                    <h4 className="text-xs font-semibold mb-1.5 text-green-700">Top 20 Items</h4>
                                    <div className="space-y-0.5 max-h-60 overflow-y-auto">
                                      {dailyDetail.top_items.length === 0 ? (
                                        <p className="text-[10px] text-muted-foreground">No item data</p>
                                      ) : dailyDetail.top_items.map((item, i) => (
                                        <div key={i} className="flex justify-between text-[11px] py-0.5 border-b border-border/20">
                                          <span className="truncate mr-2">{i+1}. {item.item_name}</span>
                                          <span className="font-mono text-green-600 shrink-0">{item.silver_profit_kg}kg / {formatIndianCurrency(item.labor_profit_inr)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                  {/* Top Customers */}
                                  <div>
                                    <h4 className="text-xs font-semibold mb-1.5 text-blue-700">Top 20 Customers</h4>
                                    <div className="space-y-0.5 max-h-60 overflow-y-auto">
                                      {dailyDetail.top_customers.length === 0 ? (
                                        <p className="text-[10px] text-muted-foreground">No customer data</p>
                                      ) : dailyDetail.top_customers.map((c, i) => (
                                        <div key={i} className="flex justify-between text-[11px] py-0.5 border-b border-border/20">
                                          <span className="truncate mr-2">{i+1}. {c.party_name}</span>
                                          <span className="font-mono text-blue-600 shrink-0">{c.total_net_wt_kg} kg ({c.sale_count} txns)</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )}

          {/* Item Profit Table */}
          <Card className="border-border/40 shadow-sm">
            <CardHeader className="p-3 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-sm sm:text-base">
                    {selectedMonth === 0 ? `All of ${selectedYear}` : `${MONTHS[selectedMonth - 1]} ${selectedYear}`} — Item Profits
                  </CardTitle>
                  <CardDescription className="text-xs">Click arrow to see monthly breakdown</CardDescription>
                </div>
                <Button onClick={handleExportProfit} variant="outline" size="sm" className="h-7 text-xs self-start" data-testid="export-profit">
                  <Download className="h-3 w-3 mr-1" />Export
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-2 sm:p-6 pt-0">
              {allItems.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No profit data for this period. Try selecting "ALL" or a different month.</p>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <Table className="min-w-[750px] table-fixed">
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs w-[30px]"></TableHead>
                          <TableHead className="text-xs w-[35px]">#</TableHead>
                          <SortableHeader label="Item" sortKey="item_name" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-xs w-[170px]" />
                          <SortableHeader label="Sold (kg)" sortKey="net_wt_sold_kg" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs w-[90px]" />
                          <SortableHeader label="Buy T%" sortKey="avg_purchase_tunch" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs w-[80px]" />
                          <SortableHeader label="Sell T%" sortKey="avg_sale_tunch" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs w-[80px]" />
                          <SortableHeader label="Silver (kg)" sortKey="silver_profit_kg" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs w-[100px]" />
                          <SortableHeader label="Labour" sortKey="labor_profit_inr" sortConfig={sortConfig} onSort={(k) => { requestSort(k); setCurrentPage(1); }} className="text-right text-xs w-[100px]" />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {paginatedItems.map((item, idx) => (
                          <>
                            <TableRow
                              key={item.item_name}
                              className="cursor-pointer hover:bg-muted/50"
                              onClick={() => handleExpandItem(item.item_name)}
                              data-testid={`profit-row-${startIdx + idx}`}
                            >
                              <TableCell className="text-xs py-2 w-[30px] text-muted-foreground">
                                {expandedItem === item.item_name ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                              </TableCell>
                              <TableCell className="text-xs py-2 text-muted-foreground w-[35px]">{startIdx + idx + 1}</TableCell>
                              <TableCell className="text-xs py-2 font-medium truncate w-[170px]">{item.item_name}</TableCell>
                              <TableCell className="text-right font-mono text-xs py-2 w-[90px]">{item.net_wt_sold_kg}</TableCell>
                              <TableCell className="text-right font-mono text-xs py-2 w-[80px]">{item.avg_purchase_tunch}%</TableCell>
                              <TableCell className="text-right font-mono text-xs py-2 w-[80px]">{item.avg_sale_tunch}%</TableCell>
                              <TableCell className="text-right font-mono text-xs py-2 text-green-600 font-semibold w-[100px]">{item.silver_profit_kg} kg</TableCell>
                              <TableCell className="text-right font-mono text-xs py-2 text-blue-600 font-semibold w-[100px]">{formatIndianCurrency(item.labor_profit_inr)}</TableCell>
                            </TableRow>
                            {expandedItem === item.item_name && (
                              <TableRow key={`${item.item_name}-chart`}>
                                <TableCell colSpan={8} className="p-3 bg-muted/30">
                                  <MonthlyBreakdownChart
                                    data={monthlyBreakdown}
                                    loading={breakdownLoading}
                                    metric={chartMetric}
                                    onMetricChange={setChartMetric}
                                    type="item"
                                  />
                                </TableCell>
                              </TableRow>
                            )}
                          </>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Pagination */}
                  {allItems.length > itemsPerPage && (
                    <div className="flex flex-col sm:flex-row items-center justify-between mt-3 pt-3 border-t gap-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">Per page:</span>
                        <Select value={String(itemsPerPage)} onValueChange={(v) => { setItemsPerPage(Number(v)); setCurrentPage(1); }}>
                          <SelectTrigger className="w-16 h-7 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {[10, 20, 50].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
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
                </>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

/** Expandable bar chart showing monthly breakdown */
function MonthlyBreakdownChart({ data, loading, metric, onMetricChange, type }) {
  if (loading) return <div className="text-center py-4 text-xs text-muted-foreground">Loading chart...</div>;
  if (!data || !data.months) return <div className="text-center py-4 text-xs text-muted-foreground">No data</div>;

  const chartData = data.months.map(m => ({
    name: MONTHS[m.month - 1],
    silver_profit_kg: m.silver_profit_kg || 0,
    labor_profit_inr: m.labor_profit_inr || 0,
    net_wt_sold_kg: m.net_wt_sold_kg || 0,
    total_net_wt: m.total_net_wt || 0,
    total_sales_value: m.total_sales_value || 0,
  }));

  const metricOptions = type === 'item'
    ? [
        { key: 'silver_profit_kg', label: 'Silver Profit (kg)', color: '#16a34a' },
        { key: 'labor_profit_inr', label: 'Labour Profit (INR)', color: '#2563eb' },
        { key: 'net_wt_sold_kg', label: 'Net Wt Sold (kg)', color: '#d97706' },
      ]
    : [
        { key: 'total_net_wt', label: 'Net Weight (g)', color: '#16a34a' },
        { key: 'total_sales_value', label: 'Sales Value', color: '#2563eb' },
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
            size="sm"
            className="h-6 text-[10px] px-2"
          >
            {opt.label}
          </Button>
        ))}
      </div>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} width={50} />
            <Tooltip
              contentStyle={{ fontSize: 11, borderRadius: 8 }}
              formatter={(value) => [typeof value === 'number' ? value.toFixed(2) : value, activeMetric.label]}
            />
            <Bar dataKey={activeMetric.key} fill={activeMetric.color} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
