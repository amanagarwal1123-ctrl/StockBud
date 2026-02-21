import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { Search, Download, RefreshCw, Package, ArrowUpDown, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { exportToCSV } from '@/utils/exportCSV';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TIER_COLORS = {
  fastest: 'bg-red-100 text-red-800 border-red-300',
  fast: 'bg-orange-100 text-orange-800 border-orange-300',
  medium: 'bg-blue-100 text-blue-800 border-blue-300',
  slow: 'bg-gray-100 text-gray-700 border-gray-300',
  dead: 'bg-gray-50 text-gray-400 border-gray-200',
};

const STATUS_COLORS = {
  red: 'bg-red-500',
  green: 'bg-emerald-500',
  yellow: 'bg-amber-400',
};

export default function ItemBufferManagement() {
  const { isAdmin } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categorizing, setCategorizing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterTier, setFilterTier] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterStamp, setFilterStamp] = useState('all');
  const [sortField, setSortField] = useState('tier_num');
  const [sortDir, setSortDir] = useState('asc');
  const [editingItem, setEditingItem] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [seasonInfo, setSeasonInfo] = useState(null);

  useEffect(() => { fetchItems(); }, []);

  const fetchItems = async () => {
    try {
      const res = await axios.get(`${API}/item-buffers`);
      setItems(res.data.items || []);
      if (res.data.items?.length > 0) {
        const first = res.data.items[0];
        setSeasonInfo({
          season: first.current_season,
          label: first.season_label,
          lead_time: first.lead_time_days,
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCategorize = async () => {
    setCategorizing(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(`${API}/item-buffers/categorize`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const d = res.data;
      toast.success(`${d.total_items} items | ${d.season_label} | Lead: ${d.lead_time_days}d | Stock: ${d.total_current_stock_kg} kg | ${d.years_analyzed}yr data`);
      setSeasonInfo({ season: d.current_season, label: d.season_label, lead_time: d.lead_time_days });
      fetchItems();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Categorization failed');
    } finally {
      setCategorizing(false);
    }
  };

  const handleSaveMinStock = async (itemName) => {
    try {
      await axios.put(`${API}/item-buffers/${encodeURIComponent(itemName)}?minimum_stock_kg=${editValue}`);
      toast.success(`Minimum stock updated for ${itemName}`);
      setEditingItem(null);
      fetchItems();
    } catch (e) {
      toast.error('Update failed');
    }
  };

  const stamps = useMemo(() => {
    const s = new Set(items.map(i => i.stamp));
    return ['all', ...Array.from(s).sort()];
  }, [items]);

  const filtered = useMemo(() => {
    let result = items.filter(i => {
      if (searchTerm && !i.item_name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      if (filterTier !== 'all' && i.tier !== filterTier) return false;
      if (filterStatus !== 'all' && i.status !== filterStatus) return false;
      if (filterStamp !== 'all' && i.stamp !== filterStamp) return false;
      return true;
    });
    result.sort((a, b) => {
      const aVal = a[sortField] || 0;
      const bVal = b[sortField] || 0;
      return sortDir === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
    });
    return result;
  }, [items, searchTerm, filterTier, filterStatus, filterStamp, sortField, sortDir]);

  const statusCounts = useMemo(() => {
    const c = { red: 0, green: 0, yellow: 0 };
    items.forEach(i => { if (c[i.status] !== undefined) c[i.status]++; });
    return c;
  }, [items]);

  const totalStock = useMemo(() => {
    return items.reduce((sum, i) => sum + (i.current_stock_kg || 0), 0).toFixed(2);
  }, [items]);

  const toggleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  };

  const handleExport = () => {
    exportToCSV(filtered.map(i => ({
      'Item': i.item_name, 'Stamp': i.stamp, 'Tier': i.tier,
      'Sales/mo (kg)': i.monthly_velocity_kg, 'Current Stock (kg)': i.current_stock_kg,
      'Min Stock (2.73mo)': i.minimum_stock_kg, 'Reorder Buffer': i.reorder_buffer_kg,
      'Upper Target': i.upper_target_kg, 'Lead Time (days)': i.lead_time_days, 'Status': i.status
    })), 'item_buffers');
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-4 sm:space-y-6" data-testid="item-buffer-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Stock Rotation & Buffers</h1>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">
            2.73-month rotation cycle with seasonal lead-time buffers
          </p>
        </div>
        {isAdmin && (
          <Button onClick={handleCategorize} disabled={categorizing} data-testid="categorize-btn">
            <RefreshCw className={`h-4 w-4 mr-2 ${categorizing ? 'animate-spin' : ''}`} />
            {categorizing ? 'Calculating...' : 'Recalculate'}
          </Button>
        )}
      </div>

      {/* Season + Stock Overview */}
      <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-lg font-bold text-blue-700" data-testid="season-label">
              {seasonInfo?.label || 'Not calculated'}
            </div>
            <p className="text-xs text-blue-600/70">Current Season</p>
          </CardContent>
        </Card>
        <Card className="border-slate-200 bg-slate-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold font-mono text-slate-700" data-testid="total-stock">
              {totalStock}
            </div>
            <p className="text-xs text-slate-600/70">Total Stock (kg)</p>
          </CardContent>
        </Card>
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold font-mono text-red-600" data-testid="count-red">{statusCounts.red}</div>
            <p className="text-xs text-red-600/70">Critical (Order Now)</p>
          </CardContent>
        </Card>
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold font-mono text-amber-600" data-testid="count-yellow">{statusCounts.yellow}</div>
            <p className="text-xs text-amber-600/70">Below Min Stock</p>
          </CardContent>
        </Card>
      </div>

      {/* Legend */}
      <Card className="bg-muted/30">
        <CardContent className="py-3 px-4">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
            <span><span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500 mr-1.5" />Red: Below reorder buffer — order immediately</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-full bg-amber-400 mr-1.5" />Yellow: Below min stock (2.73mo) — restock soon</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 mr-1.5" />Green: Healthy stock level</span>
            <span className="ml-auto">Lead time: <strong>{seasonInfo?.lead_time || 7}d</strong></span>
          </div>
        </CardContent>
      </Card>

      {items.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <Package className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-semibold">No Buffer Data</h3>
            <p className="text-sm text-muted-foreground mt-2">Upload sales data and click "Recalculate" to generate rotation-based stock buffers.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Search items..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} className="pl-10" data-testid="buffer-search" />
            </div>
            <Select value={filterTier} onValueChange={setFilterTier}>
              <SelectTrigger className="w-full sm:w-40" data-testid="filter-tier"><SelectValue placeholder="Tier" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Tiers</SelectItem>
                <SelectItem value="fastest">Fastest</SelectItem>
                <SelectItem value="fast">Fast</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="slow">Slow</SelectItem>
                <SelectItem value="dead">Dead</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-full sm:w-40" data-testid="filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="red">Red (Critical)</SelectItem>
                <SelectItem value="yellow">Yellow (Low)</SelectItem>
                <SelectItem value="green">Green (OK)</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStamp} onValueChange={setFilterStamp}>
              <SelectTrigger className="w-full sm:w-44"><SelectValue placeholder="Stamp" /></SelectTrigger>
              <SelectContent>
                {stamps.map(s => <SelectItem key={s} value={s}>{s === 'all' ? 'All Stamps' : s}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" onClick={handleExport} data-testid="export-btn"><Download className="h-4 w-4" /></Button>
          </div>

          {/* Table */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Items ({filtered.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <TooltipProvider>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-8">St</TableHead>
                        <TableHead className="cursor-pointer" onClick={() => toggleSort('item_name')}>Item <ArrowUpDown className="inline h-3 w-3" /></TableHead>
                        <TableHead>Stamp</TableHead>
                        <TableHead className="cursor-pointer" onClick={() => toggleSort('tier_num')}>Tier <ArrowUpDown className="inline h-3 w-3" /></TableHead>
                        <TableHead className="text-right cursor-pointer" onClick={() => toggleSort('monthly_velocity_kg')}>
                          Sales/mo
                          <ArrowUpDown className="inline h-3 w-3 ml-1" />
                        </TableHead>
                        <TableHead className="text-right cursor-pointer" onClick={() => toggleSort('current_stock_kg')}>
                          Current
                          <ArrowUpDown className="inline h-3 w-3 ml-1" />
                        </TableHead>
                        <TableHead className="text-right">
                          <Tooltip>
                            <TooltipTrigger className="flex items-center gap-1 justify-end">
                              Min Stock <Info className="h-3 w-3" />
                            </TooltipTrigger>
                            <TooltipContent>2.73 months of sales — full rotation cycle</TooltipContent>
                          </Tooltip>
                        </TableHead>
                        <TableHead className="text-right">
                          <Tooltip>
                            <TooltipTrigger className="flex items-center gap-1 justify-end">
                              Reorder Buf <Info className="h-3 w-3" />
                            </TooltipTrigger>
                            <TooltipContent>Stock consumed during order lead time ({seasonInfo?.lead_time || 7} days)</TooltipContent>
                          </Tooltip>
                        </TableHead>
                        <TableHead className="text-right">
                          <Tooltip>
                            <TooltipTrigger className="flex items-center gap-1 justify-end">
                              Target <Info className="h-3 w-3" />
                            </TooltipTrigger>
                            <TooltipContent>Upper stock target to maximize sales potential</TooltipContent>
                          </Tooltip>
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filtered.map((item, idx) => (
                        <TableRow key={idx} className={item.status === 'red' ? 'bg-red-50/50' : item.status === 'yellow' ? 'bg-amber-50/30' : ''} data-testid={`buffer-row-${idx}`}>
                          <TableCell>
                            <div className={`w-3 h-3 rounded-full ${STATUS_COLORS[item.status]}`} title={item.status} />
                          </TableCell>
                          <TableCell className="font-medium text-sm">
                            {item.item_name}
                            {item.is_group && <Badge className="ml-1.5 text-[10px] bg-purple-100 text-purple-700">Group</Badge>}
                          </TableCell>
                          <TableCell><Badge variant="outline" className="text-xs font-mono">{item.stamp}</Badge></TableCell>
                          <TableCell><Badge className={`text-xs ${TIER_COLORS[item.tier]}`}>{item.tier}</Badge></TableCell>
                          <TableCell className="text-right font-mono text-sm">{item.monthly_velocity_kg}</TableCell>
                          <TableCell className="text-right font-mono text-sm font-semibold">{item.current_stock_kg}</TableCell>
                          <TableCell className="text-right">
                            {editingItem === item.item_name ? (
                              <div className="flex items-center gap-1">
                                <Input type="number" step="0.001" value={editValue} onChange={e => setEditValue(e.target.value)} className="w-20 h-7 text-xs" />
                                <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => handleSaveMinStock(item.item_name)}>Save</Button>
                              </div>
                            ) : (
                              <span className="font-mono text-sm cursor-pointer hover:underline" onClick={() => { setEditingItem(item.item_name); setEditValue(item.minimum_stock_kg); }}>
                                {item.minimum_stock_kg}
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm text-muted-foreground">{item.reorder_buffer_kg}</TableCell>
                          <TableCell className="text-right font-mono text-sm text-muted-foreground">{item.upper_target_kg}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TooltipProvider>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
