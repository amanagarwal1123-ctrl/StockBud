import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Search, Plus, Minus, Save, Trash2, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PolytheneEntry() {
  const [searchTerm, setSearchTerm] = useState('');
  const [allItems, setAllItems] = useState([]);
  const [filteredItems, setFilteredItems] = useState([]);
  const [pendingEntries, setPendingEntries] = useState([]);
  const [savedEntries, setSavedEntries] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [currentEntry, setCurrentEntry] = useState({
    item: null,
    polyWeight: '',
    operation: 'add'
  });
  
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
      // Add timestamp to bust any proxy/CDN caches and fetch ALL items including negative stock
      const cacheBuster = `?_t=${Date.now()}`;
      const response = await axios.get(`${API}/inventory/current${cacheBuster}`);
      
      // Use stamp_items (ungrouped, per-item) so group members appear separately
      // This is critical for stamp-wise stock tallying — each item has its own stock
      const allInventoryItems = response.data.stamp_items || [...response.data.inventory, ...response.data.negative_items];
      setAllItems(allInventoryItems);
    } catch (error) {
      toast.error('Failed to load items');
    }
  };

  const fetchTodayEntries = async () => {
    try {
      const response = await axios.get(`${API}/polythene/today/${user.username}`);
      setSavedEntries(response.data);
    } catch (error) {
      console.error('Error fetching entries:', error);
    }
  };

  const selectItem = (item) => {
    setCurrentEntry({ ...currentEntry, item });
    setSearchTerm(item.item_name);
    setFilteredItems([]);
  };

  const addToPending = () => {
    if (!currentEntry.item || !currentEntry.polyWeight) {
      toast.error('Please select item and enter weight');
      return;
    }

    const newEntry = {
      item_name: currentEntry.item.item_name,
      stamp: currentEntry.item.stamp,
      poly_weight: parseFloat(currentEntry.polyWeight),
      operation: currentEntry.operation
    };

    // Duplicate check: warn if same item+stamp+operation+weight already in pending
    const isDuplicate = pendingEntries.some(
      e => e.item_name === newEntry.item_name &&
           e.stamp === newEntry.stamp &&
           e.operation === newEntry.operation &&
           e.poly_weight === newEntry.poly_weight
    );
    if (isDuplicate) {
      toast.error('Duplicate entry — same item, weight & operation already in the list');
      return;
    }

    setPendingEntries([...pendingEntries, newEntry]);

    // Reset for next entry
    setCurrentEntry({ item: null, polyWeight: '', operation: 'add' });
    setSearchTerm('');
    toast.success('Entry added to list');
  };

  const removePending = (index) => {
    setPendingEntries(pendingEntries.filter((_, i) => i !== index));
  };

  const saveAllEntries = async () => {
    if (pendingEntries.length === 0) {
      toast.error('No entries to save');
      return;
    }
    if (isSaving) return; // Guard against double-clicks
    setIsSaving(true);

    try {
      const response = await axios.post(`${API}/polythene/adjust-batch`, {
        entries: pendingEntries,
        adjusted_by: user.username
      });

      const saved = response.data?.saved ?? pendingEntries.length;
      const skipped = response.data?.skipped ?? 0;
      if (skipped > 0) {
        toast.warning(`Saved ${saved} entries. ${skipped} duplicate(s) skipped.`);
      } else {
        toast.success(`${saved} polythene adjustment(s) saved!`);
      }
      setPendingEntries([]);
      fetchTodayEntries();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save entries');
    } finally {
      setIsSaving(false);
    }
  };

  const deleteSavedEntry = async (entryId) => {
    try {
      await axios.delete(`${API}/polythene/${entryId}`);
      toast.success('Entry deleted');
      fetchTodayEntries();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          Polythene Adjustment
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          Adjust gross weights due to polythene changes (net weight unchanged)
        </p>
      </div>

      {/* Entry Form */}
      <Card className="border-primary/20">
        <CardHeader>
          <CardTitle>Add Polythene Adjustment</CardTitle>
          <CardDescription>Search item, enter weight, choose add/subtract</CardDescription>
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
                    <p className="text-xs text-muted-foreground">
                      {item.stamp} - Current Gross: {(item.gr_wt/1000).toFixed(3)} kg
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {currentEntry.item && (
            <div className="border-2 border-primary/20 rounded-lg p-4 space-y-4">
              <div>
                <p className="font-semibold text-lg">{currentEntry.item.item_name}</p>
                <p className="text-sm text-muted-foreground">
                  {currentEntry.item.stamp} | Gross: {(currentEntry.item.gr_wt/1000).toFixed(3)} kg | Net: {(currentEntry.item.net_wt/1000).toFixed(3)} kg
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label>Polythene Weight (kg) *</Label>
                  <Input
                    type="number"
                    step="0.001"
                    placeholder="0.000"
                    value={currentEntry.polyWeight}
                    onChange={(e) => setCurrentEntry({...currentEntry, polyWeight: e.target.value})}
                  />
                </div>
                <div>
                  <Label>Operation *</Label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant={currentEntry.operation === 'add' ? 'default' : 'outline'}
                      onClick={() => setCurrentEntry({...currentEntry, operation: 'add'})}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Add
                    </Button>
                    <Button
                      type="button"
                      variant={currentEntry.operation === 'subtract' ? 'default' : 'outline'}
                      onClick={() => setCurrentEntry({...currentEntry, operation: 'subtract'})}
                      className="flex-1 bg-red-600 hover:bg-red-700"
                    >
                      <Minus className="h-4 w-4 mr-1" />
                      Subtract
                    </Button>
                  </div>
                </div>
              </div>

              <Button onClick={addToPending} className="w-full" variant="outline">
                <Plus className="h-4 w-4 mr-2" />
                Add to List (Add More Entries)
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending Entries */}
      {pendingEntries.length > 0 && (
        <Card className="border-orange-500/20">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Pending Entries ({pendingEntries.length})</CardTitle>
              <Button onClick={saveAllEntries} className="bg-primary" disabled={isSaving}
                data-testid="save-all-polythene-btn">
                {isSaving ? (
                  <>
                    <span className="animate-spin mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full inline-block" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4 mr-2" />
                    Save All Entries
                  </>
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item Name</TableHead>
                  <TableHead>Stamp</TableHead>
                  <TableHead className="text-right">Polythene (kg)</TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingEntries.map((entry, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">{entry.item_name}</TableCell>
                    <TableCell>{entry.stamp}</TableCell>
                    <TableCell className="text-right font-mono">{entry.poly_weight.toFixed(3)}</TableCell>
                    <TableCell>
                      <Badge className={entry.operation === 'add' ? 'bg-green-600' : 'bg-red-600'}>
                        {entry.operation === 'add' ? 'ADD' : 'SUBTRACT'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => removePending(idx)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Today's Saved Entries */}
      <Card>
        <CardHeader>
          <CardTitle>Today's Saved Adjustments</CardTitle>
          <CardDescription>All polythene adjustments made today</CardDescription>
        </CardHeader>
        <CardContent>
          {savedEntries.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">No adjustments saved today</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item Name</TableHead>
                  <TableHead>Stamp</TableHead>
                  <TableHead className="text-right">Polythene (kg)</TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {savedEntries.map((entry, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">{entry.item_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{entry.stamp || 'N/A'}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">{entry.poly_weight?.toFixed(3)}</TableCell>
                    <TableCell>
                      <Badge className={entry.operation === 'add' ? 'bg-green-600' : 'bg-red-600'}>
                        {entry.operation === 'add' ? 'ADD' : 'SUBTRACT'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(entry.created_at).toLocaleTimeString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => deleteSavedEntry(entry.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
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
