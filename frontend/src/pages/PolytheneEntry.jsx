import { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Plus, Minus, Save, Eye } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PolytheneEntry() {
  const [searchTerm, setSearchTerm] = useState('');
  const [allItems, setAllItems] = useState([]);
  const [filteredItems, setFilteredItems] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [polyWeight, setPolyWeight] = useState('');
  const [operation, setOperation] = useState('add'); // 'add' or 'subtract'
  const [todayEntries, setTodayEntries] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  
  const { user } = useAuth();

  useEffect(() => {
    fetchAllItems();
    fetchTodayEntries();
  }, []);

  useEffect(() => {
    if (searchTerm.length > 1) {
      const filtered = allItems.filter(item =>
        item.item_name.toLowerCase().includes(searchTerm.toLowerCase())
      ).slice(0, 10);
      setFilteredItems(filtered);
    } else {
      setFilteredItems([]);
    }
  }, [searchTerm, allItems]);

  const fetchAllItems = async () => {
    try {
      const response = await axios.get(`${API}/inventory/current`);
      setAllItems(response.data.inventory);
    } catch (error) {
      toast.error('Failed to load items');
    }
  };

  const fetchTodayEntries = async () => {
    try {
      const response = await axios.get(`${API}/polythene/today/${user.username}`);
      setTodayEntries(response.data);
    } catch (error) {
      console.error('Error fetching entries:', error);
    }
  };

  const selectItem = (item) => {
    setSelectedItem(item);
    setSearchTerm(item.item_name);
    setFilteredItems([]);
  };

  const handleSave = async () => {
    if (!selectedItem || !polyWeight) {
      toast.error('Please select item and enter weight');
      return;
    }

    try {
      await axios.post(`${API}/polythene/adjust`, {
        item_name: selectedItem.item_name,
        poly_weight: parseFloat(polyWeight),
        operation: operation,
        adjusted_by: user.username
      });

      toast.success(`Polythene ${operation === 'add' ? 'added' : 'removed'} successfully!`);
      setSelectedItem(null);
      setSearchTerm('');
      setPolyWeight('');
      fetchTodayEntries();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save');
    }
  };

  const deleteEntry = async (entryId) => {
    try {
      await axios.delete(`${API}/polythene/${entryId}`);
      toast.success('Entry deleted');
      fetchTodayEntries();
    } catch (error) {
      toast.error('Failed to delete entry');
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Polythene Adjustment
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Adjust gross weights due to polythene changes
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Search & Select Item</CardTitle>
          <CardDescription>Search for item to adjust polythene weight</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search item name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
            {filteredItems.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-background border rounded-lg shadow-lg max-h-60 overflow-y-auto">
                {filteredItems.map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => selectItem(item)}
                    className="p-3 hover:bg-muted cursor-pointer border-b last:border-0"
                  >
                    <p className="font-medium">{item.item_name}</p>
                    <p className="text-xs text-muted-foreground">{item.stamp} - Gross: {(item.gr_wt/1000).toFixed(3)} kg</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedItem && (
            <div className="border-2 border-primary/20 rounded-lg p-4 space-y-4">
              <div>
                <p className="font-semibold text-lg">{selectedItem.item_name}</p>
                <p className="text-sm text-muted-foreground">
                  Current Gross: {(selectedItem.gr_wt/1000).toFixed(3)} kg | Net: {(selectedItem.net_wt/1000).toFixed(3)} kg
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label>Polythene Weight (kg)</Label>
                  <Input
                    type="number"
                    step="0.001"
                    placeholder="0.000"
                    value={polyWeight}
                    onChange={(e) => setPolyWeight(e.target.value)}
                  />
                </div>
                <div>
                  <Label>Operation</Label>
                  <div className="flex gap-2">
                    <Button
                      variant={operation === 'add' ? 'default' : 'outline'}
                      onClick={() => setOperation('add')}
                      className="flex-1"
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Add
                    </Button>
                    <Button
                      variant={operation === 'subtract' ? 'default' : 'outline'}
                      onClick={() => setOperation('subtract')}
                      className="flex-1"
                    >
                      <Minus className="h-4 w-4 mr-1" />
                      Subtract
                    </Button>
                  </div>
                </div>
              </div>

              <Button onClick={handleSave} className="w-full">
                <Save className="h-4 w-4 mr-2" />
                Save Polythene Adjustment
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Today's Entries */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Today's Polythene Adjustments</CardTitle>
            <Button variant="outline" size="sm" onClick={fetchTodayEntries}>
              <Eye className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {todayEntries.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No adjustments made today</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item Name</TableHead>
                  <TableHead className="text-right">Polythene (kg)</TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {todayEntries.map((entry, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">{entry.item_name}</TableCell>
                    <TableCell className="text-right font-mono">{entry.poly_weight?.toFixed(3)}</TableCell>
                    <TableCell>
                      <Badge className={entry.operation === 'add' ? 'bg-green-600' : 'bg-red-600'}>
                        {entry.operation === 'add' ? 'ADD' : 'SUBTRACT'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{new Date(entry.created_at).toLocaleTimeString()}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => deleteEntry(entry.id)}>
                        Delete
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
