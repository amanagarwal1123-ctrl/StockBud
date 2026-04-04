import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Box, Download, Trash2, Search, X, Check, ChevronsUpDown, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { exportToCSV } from '@/utils/exportCSV';
import { toast } from 'sonner';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { cn } from '@/lib/utils';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function ComboFilter({ value, onSelect, options, placeholder, testId }) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal"
          data-testid={testId}
        >
          <span className="truncate">{value || placeholder}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command>
          <CommandInput placeholder={`Search...`} />
          <CommandList>
            <CommandEmpty>No results.</CommandEmpty>
            <CommandGroup>
              <CommandItem
                onSelect={() => { onSelect(''); setOpen(false); }}
                data-testid={`${testId}-all`}
              >
                <Check className={cn("mr-2 h-4 w-4", !value ? "opacity-100" : "opacity-0")} />
                All
              </CommandItem>
              {options.map((opt) => (
                <CommandItem
                  key={opt}
                  value={opt}
                  onSelect={() => { onSelect(opt); setOpen(false); }}
                >
                  <Check className={cn("mr-2 h-4 w-4", value === opt ? "opacity-100" : "opacity-0")} />
                  {opt}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export default function PolytheneManagement() {
  const [entries, setEntries] = useState([]);
  const [users, setUsers] = useState([]);
  const [filterUser, setFilterUser] = useState('all');
  const [filterItem, setFilterItem] = useState('');
  const [filterStamp, setFilterStamp] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [loading, setLoading] = useState(true);

  const { isAdmin, user } = useAuth();
  const canAccess = user?.role === 'admin' || user?.role === 'executive';

  useEffect(() => {
    if (canAccess) {
      fetchAllEntries();
      if (isAdmin) fetchUsers();
    }
  }, [canAccess, isAdmin]);

  const fetchAllEntries = async () => {
    try {
      const response = await axios.get(`${API}/polythene/all`);
      setEntries(response.data);
    } catch (error) {
      console.error('Failed to fetch entries:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/users/list`);
      const polyUsers = response.data.filter(u => u.role === 'polythene_executive');
      setUsers(polyUsers);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  };

  const deleteEntry = async (entryId) => {
    const confirmed = window.confirm('Delete this polythene entry?');
    if (!confirmed) return;
    try {
      await axios.delete(`${API}/polythene/${entryId}`);
      toast.success('Entry deleted');
      fetchAllEntries();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  // Cross-filtered: item options narrow based on selected stamp (and vice versa)
  const availableItems = useMemo(() => {
    const pool = filterStamp ? entries.filter(e => e.stamp === filterStamp) : entries;
    return [...new Set(pool.map(e => e.item_name).filter(Boolean))].sort();
  }, [entries, filterStamp]);

  const availableStamps = useMemo(() => {
    const pool = filterItem ? entries.filter(e => e.item_name === filterItem) : entries;
    return [...new Set(pool.map(e => e.stamp).filter(Boolean))].sort();
  }, [entries, filterItem]);

  // Auto-clear item if it's no longer valid for the selected stamp
  useEffect(() => {
    if (filterItem && !availableItems.includes(filterItem)) setFilterItem('');
  }, [availableItems, filterItem]);

  // Auto-clear stamp if it's no longer valid for the selected item
  useEffect(() => {
    if (filterStamp && !availableStamps.includes(filterStamp)) setFilterStamp('');
  }, [availableStamps, filterStamp]);

  const filteredEntries = useMemo(() => {
    return entries.filter(entry => {
      const matchesUser = filterUser === 'all' || entry.adjusted_by === filterUser;
      const matchesItem = !filterItem || entry.item_name === filterItem;
      const matchesStamp = !filterStamp || entry.stamp === filterStamp;

      let matchesDate = true;
      if (filterDateFrom || filterDateTo) {
        const entryDate = new Date(entry.created_at);
        const entryDateStr = entryDate.toISOString().split('T')[0];
        if (filterDateFrom && entryDateStr < filterDateFrom) matchesDate = false;
        if (filterDateTo && entryDateStr > filterDateTo) matchesDate = false;
      }

      return matchesUser && matchesItem && matchesStamp && matchesDate;
    });
  }, [entries, filterUser, filterItem, filterStamp, filterDateFrom, filterDateTo]);

  const totals = useMemo(() => {
    const totalAdd = filteredEntries
      .filter(e => e.operation === 'add')
      .reduce((sum, e) => sum + (e.poly_weight || 0), 0);
    const totalSubtract = filteredEntries
      .filter(e => e.operation === 'subtract')
      .reduce((sum, e) => sum + (e.poly_weight || 0), 0);
    return { totalAdd, totalSubtract, net: totalAdd - totalSubtract };
  }, [filteredEntries]);

  // 30-day trend data for admin
  const trendData = useMemo(() => {
    if (!isAdmin || entries.length === 0) return [];
    const now = new Date();
    const thirtyDaysAgo = new Date(now);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const dayMap = {};
    for (let i = 0; i <= 30; i++) {
      const d = new Date(thirtyDaysAgo);
      d.setDate(d.getDate() + i);
      const key = d.toISOString().split('T')[0];
      dayMap[key] = { date: key, label: `${d.getDate()}/${d.getMonth() + 1}`, add: 0, subtract: 0 };
    }

    entries.forEach(e => {
      const d = new Date(e.created_at).toISOString().split('T')[0];
      if (dayMap[d]) {
        if (e.operation === 'add') dayMap[d].add += e.poly_weight || 0;
        else dayMap[d].subtract += e.poly_weight || 0;
      }
    });

    return Object.values(dayMap).map(d => ({
      ...d,
      add: parseFloat(d.add.toFixed(4)),
      subtract: parseFloat(d.subtract.toFixed(4)),
    }));
  }, [entries, isAdmin]);

  const hasActiveFilters = filterItem || filterStamp || filterDateFrom || filterDateTo || filterUser !== 'all';

  const clearFilters = () => {
    setFilterItem('');
    setFilterStamp('');
    setFilterDateFrom('');
    setFilterDateTo('');
    setFilterUser('all');
  };

  const handleExport = () => {
    const exportData = filteredEntries.map(entry => ({
      'Date': new Date(entry.created_at).toLocaleString(),
      'User': entry.adjusted_by,
      'Item Name': entry.item_name,
      'Stamp': entry.stamp || 'N/A',
      'Polythene (kg)': entry.poly_weight,
      'Operation': entry.operation.toUpperCase()
    }));
    exportToCSV(exportData, 'polythene_adjustments');
  };

  if (!canAccess) {
    return (
      <div className="p-3 sm:p-6 md:p-8">
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-center text-destructive" data-testid="access-denied-msg">Access Denied.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight" data-testid="polythene-mgmt-title">
          Polythene Management
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          {isAdmin ? 'View and manage all polythene adjustments' : 'View all polythene adjustments (read-only)'}
        </p>
      </div>

      {/* Summary Totals */}
      <div className="grid grid-cols-3 gap-3" data-testid="polythene-summary">
        <Card className="border-green-200 bg-green-50/50">
          <CardContent className="p-4 text-center">
            <p className="text-xs font-medium text-green-700 mb-1">Total Add</p>
            <p className="text-xl font-bold text-green-700 font-mono" data-testid="poly-total-add">+{totals.totalAdd.toFixed(3)} kg</p>
            <p className="text-[10px] text-green-600 mt-1">{filteredEntries.filter(e => e.operation === 'add').length} entries</p>
          </CardContent>
        </Card>
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="p-4 text-center">
            <p className="text-xs font-medium text-red-700 mb-1">Total Subtract</p>
            <p className="text-xl font-bold text-red-700 font-mono" data-testid="poly-total-subtract">-{totals.totalSubtract.toFixed(3)} kg</p>
            <p className="text-[10px] text-red-600 mt-1">{filteredEntries.filter(e => e.operation === 'subtract').length} entries</p>
          </CardContent>
        </Card>
        <Card className={`${totals.net >= 0 ? 'border-blue-200 bg-blue-50/50' : 'border-orange-200 bg-orange-50/50'}`}>
          <CardContent className="p-4 text-center">
            <p className="text-xs font-medium text-muted-foreground mb-1">Net Polythene</p>
            <p className={`text-xl font-bold font-mono ${totals.net >= 0 ? 'text-blue-700' : 'text-orange-700'}`} data-testid="poly-net-total">
              {totals.net >= 0 ? '+' : ''}{totals.net.toFixed(3)} kg
            </p>
            <p className="text-[10px] text-muted-foreground mt-1">{filteredEntries.length} total entries</p>
          </CardContent>
        </Card>
      </div>

      {/* 30-Day Trend Chart — Admin Only */}
      {isAdmin && trendData.length > 0 && (
        <Card data-testid="polythene-trend-chart">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              30-Day Polythene Trend
            </CardTitle>
            <CardDescription>Daily polythene additions and subtractions over the last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    interval="preserveStartEnd"
                    className="text-muted-foreground"
                  />
                  <YAxis tick={{ fontSize: 11 }} className="text-muted-foreground" unit=" kg" />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }}
                    formatter={(val, name) => [`${val.toFixed(4)} kg`, name === 'add' ? 'Added' : 'Subtracted']}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Legend formatter={(val) => val === 'add' ? 'Added' : 'Subtracted'} />
                  <Bar dataKey="add" fill="#16a34a" radius={[3, 3, 0, 0]} name="add" />
                  <Bar dataKey="subtract" fill="#dc2626" radius={[3, 3, 0, 0]} name="subtract" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <CardTitle className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Search & Filter
            </CardTitle>
            <div className="flex items-center gap-2">
              {hasActiveFilters && (
                <Button onClick={clearFilters} variant="ghost" size="sm" data-testid="clear-filters-btn">
                  <X className="h-4 w-4 mr-1" />
                  Clear
                </Button>
              )}
              <Button onClick={handleExport} variant="outline" size="sm" data-testid="export-csv-btn">
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <Label className="text-sm mb-2 block">Item Name</Label>
              <ComboFilter
                value={filterItem}
                onSelect={setFilterItem}
                options={availableItems}
                placeholder="All Items"
                testId="filter-item-name"
              />
            </div>
            <div>
              <Label className="text-sm mb-2 block">Stamp Name</Label>
              <ComboFilter
                value={filterStamp}
                onSelect={setFilterStamp}
                options={availableStamps}
                placeholder="All Stamps"
                testId="filter-stamp-name"
              />
            </div>
            {isAdmin && (
              <div>
                <Label className="text-sm mb-2 block">User</Label>
                <Select value={filterUser} onValueChange={setFilterUser}>
                  <SelectTrigger data-testid="filter-user-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Users</SelectItem>
                    {users.map(u => (
                      <SelectItem key={u.username} value={u.username}>
                        {u.full_name} ({u.username})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div>
              <Label className="text-sm mb-2 block">Date From</Label>
              <Input
                type="date"
                value={filterDateFrom}
                onChange={(e) => setFilterDateFrom(e.target.value)}
                data-testid="filter-date-from"
              />
            </div>
            <div>
              <Label className="text-sm mb-2 block">Date To</Label>
              <Input
                type="date"
                value={filterDateTo}
                onChange={(e) => setFilterDateTo(e.target.value)}
                data-testid="filter-date-to"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Entries Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Box className="h-5 w-5 text-primary" />
            All Polythene Adjustments ({filteredEntries.length})
          </CardTitle>
          <CardDescription>Complete history of polythene add/subtract operations</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground" data-testid="loading-indicator">Loading...</div>
          ) : (
            <div className="overflow-x-auto">
              <Table className="min-w-[640px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Date & Time</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Item Name</TableHead>
                    <TableHead>Stamp</TableHead>
                    <TableHead className="text-right">Polythene (kg)</TableHead>
                    <TableHead>Operation</TableHead>
                    {isAdmin && <TableHead className="text-right">Actions</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredEntries.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={isAdmin ? 7 : 6} className="text-center py-8 text-muted-foreground" data-testid="no-entries-msg">
                        No polythene adjustments found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredEntries.map((entry, idx) => (
                      <TableRow key={entry.id || idx} data-testid={`poly-entry-row-${idx}`}>
                        <TableCell className="font-mono text-sm">
                          {new Date(entry.created_at).toLocaleString()}
                        </TableCell>
                        <TableCell className="font-medium">{entry.adjusted_by}</TableCell>
                        <TableCell>{entry.item_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{entry.stamp || 'N/A'}</Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {entry.poly_weight?.toFixed(3)}
                        </TableCell>
                        <TableCell>
                          <Badge className={entry.operation === 'add' ? 'bg-green-600' : 'bg-red-600'}>
                            {entry.operation?.toUpperCase()}
                          </Badge>
                        </TableCell>
                        {isAdmin && (
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => deleteEntry(entry.id)}
                              data-testid={`delete-entry-btn-${idx}`}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </TableCell>
                        )}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
