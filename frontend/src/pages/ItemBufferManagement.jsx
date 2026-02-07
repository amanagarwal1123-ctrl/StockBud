import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { Search, Filter, Download, RefreshCw, Package, AlertTriangle, CheckCircle2, ArrowUpDown } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
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

  useEffect(() => { fetchItems(); }, []);

  const fetchItems = async () => {
    try {
      const res = await axios.get(`${API}/item-buffers`);
      setItems(res.data.items || []);
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
      toast.success(`Categorized ${res.data.total_items} items into ${Object.keys(res.data.tiers).length} tiers`);
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

  const toggleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  };

  const handleExport = () => {
    exportToCSV(filtered.map(i => ({
      'Item': i.item_name, 'Stamp': i.stamp, 'Tier': i.tier,
      'Velocity (kg/mo)': i.monthly_velocity_kg, 'Current Stock (kg)': i.current_stock_kg,
      'Min Stock (kg)': i.minimum_stock_kg, 'Lower Buffer': i.lower_buffer_kg,
      'Upper Buffer': i.upper_buffer_kg, 'Status': i.status
    })), 'item_buffers');
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="item-buffer-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Item Buffer Management</h1>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">Auto-categorized movement tiers with stock buffers</p>
        </div>
        {isAdmin && (
          <Button onClick={handleCategorize} disabled={categorizing} data-testid="categorize-btn">
            <RefreshCw className={`h-4 w-4 mr-2 ${categorizing ? 'animate-spin' : ''}`} />
            {categorizing ? 'Analyzing...' : 'Re-Categorize'}
          </Button>
        )}
      </div>

      {/* Status Summary */}
      <div className="grid gap-4 grid-cols-3">
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold font-mono text-red-600" data-testid="count-red">{statusCounts.red}</div>
            <p className="text-xs text-red-600/70">Below Minimum</p>
          </CardContent>
        </Card>
        <Card className="border-emerald-200 bg-emerald-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold font-mono text-emerald-600" data-testid="count-green">{statusCounts.green}</div>
            <p className="text-xs text-emerald-600/70">Healthy</p>
          </CardContent>
        </Card>
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold font-mono text-amber-600" data-testid="count-yellow">{statusCounts.yellow}</div>
            <p className="text-xs text-amber-600/70">Overstocked</p>
          </CardContent>
        </Card>
      </div>

      {items.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <Package className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-semibold">No Buffer Data</h3>
            <p className="text-sm text-muted-foreground mt-2">Upload sales data and click "Re-Categorize" to auto-generate movement tiers and buffers.</p>
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
                <SelectItem value="red">Red (Low)</SelectItem>
                <SelectItem value="green">Green (OK)</SelectItem>
                <SelectItem value="yellow">Yellow (Over)</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStamp} onValueChange={setFilterStamp}>
              <SelectTrigger className="w-full sm:w-44"><SelectValue placeholder="Stamp" /></SelectTrigger>
              <SelectContent>
                {stamps.map(s => <SelectItem key={s} value={s}>{s === 'all' ? 'All Stamps' : s}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" onClick={handleExport}><Download className="h-4 w-4" /></Button>
          </div>

          {/* Table */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Items ({filtered.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8">Status</TableHead>
                      <TableHead className="cursor-pointer" onClick={() => toggleSort('item_name')}>Item Name <ArrowUpDown className="inline h-3 w-3" /></TableHead>
                      <TableHead>Stamp</TableHead>
                      <TableHead className="cursor-pointer" onClick={() => toggleSort('tier_num')}>Tier <ArrowUpDown className="inline h-3 w-3" /></TableHead>
                      <TableHead className="text-right cursor-pointer" onClick={() => toggleSort('monthly_velocity_kg')}>Velocity/mo <ArrowUpDown className="inline h-3 w-3" /></TableHead>
                      <TableHead className="text-right cursor-pointer" onClick={() => toggleSort('current_stock_kg')}>Current (kg) <ArrowUpDown className="inline h-3 w-3" /></TableHead>
                      <TableHead className="text-right">Min Stock (kg)</TableHead>
                      <TableHead className="text-right">Lower Buffer</TableHead>
                      <TableHead className="text-right">Upper Buffer</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((item, idx) => (
                      <TableRow key={idx} className={item.status === 'red' ? 'bg-red-50/50' : item.status === 'yellow' ? 'bg-amber-50/30' : ''} data-testid={`buffer-row-${idx}`}>
                        <TableCell>
                          <div className={`w-3 h-3 rounded-full ${STATUS_COLORS[item.status]}`} title={item.status} />
                        </TableCell>
                        <TableCell className="font-medium text-sm">{item.item_name}</TableCell>
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
                        <TableCell className="text-right font-mono text-sm text-muted-foreground">{item.lower_buffer_kg}</TableCell>
                        <TableCell className="text-right font-mono text-sm text-muted-foreground">{item.upper_buffer_kg}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
