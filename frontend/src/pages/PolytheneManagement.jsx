import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Box, Filter, Download, Edit, Trash2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { exportToCSV } from '@/utils/exportCSV';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PolytheneManagement() {
  const [entries, setEntries] = useState([]);
  const [allItems, setAllItems] = useState([]);
  const [users, setUsers] = useState([]);
  const [filterUser, setFilterUser] = useState('all');
  const [filterItem, setFilterItem] = useState('');
  const [filteredSuggestions, setFilteredSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const { isAdmin } = useAuth();

  useEffect(() => {
    if (isAdmin) {
      fetchAllEntries();
      fetchUsers();
      fetchAllItems();
    }
  }, [isAdmin]);

  useEffect(() => {
    if (filterItem.length > 1) {
      const suggestions = allItems.filter(item =>
        item.item_name.toLowerCase().includes(filterItem.toLowerCase())
      ).slice(0, 10);
      setFilteredSuggestions(suggestions);
    } else {
      setFilteredSuggestions([]);
    }
  }, [filterItem, allItems]);

  const fetchAllItems = async () => {
    try {
      const response = await axios.get(`${API}/inventory/current`);
      setAllItems(response.data.inventory);
    } catch (error) {
      console.error('Failed to fetch items:', error);
    }
  };

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

  const filteredEntries = entries.filter(entry => {
    const matchesUser = filterUser === 'all' || entry.adjusted_by === filterUser;
    const matchesItem = !filterItem || entry.item_name.toLowerCase().includes(filterItem.toLowerCase());
    return matchesUser && matchesItem;
  });

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

  if (!isAdmin) {
    return (
      <div className="p-3 sm:p-6 md:p-8">
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-center text-destructive">Access Denied. Admin privileges required.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          Polythene Management
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          View and manage all polythene adjustments
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Filters</CardTitle>
            <Button onClick={handleExport} variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <Label className="text-sm mb-2">Filter by User</Label>
              <Select value={filterUser} onValueChange={setFilterUser}>
                <SelectTrigger>
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
            <div>
              <Label className="text-sm mb-2">Filter by Item Name</Label>
              <div className="relative">
                <Input
                  placeholder="Search item name..."
                  value={filterItem}
                  onChange={(e) => setFilterItem(e.target.value)}
                />
                {filteredSuggestions.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-background border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                    {filteredSuggestions.map((item, idx) => (
                      <div
                        key={idx}
                        onClick={() => {
                          setFilterItem(item.item_name);
                          setFilteredSuggestions([]);
                        }}
                        className="p-2 hover:bg-muted cursor-pointer text-sm"
                      >
                        {item.item_name} <span className="text-xs text-muted-foreground">({item.stamp})</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

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
            <div className="text-center py-8 text-muted-foreground">Loading...</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date & Time</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Item Name</TableHead>
                    <TableHead>Stamp</TableHead>
                    <TableHead className="text-right">Polythene (kg)</TableHead>
                    <TableHead>Operation</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredEntries.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                        No polythene adjustments found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredEntries.map((entry, idx) => (
                      <TableRow key={idx}>
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
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteEntry(entry.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </TableCell>
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
