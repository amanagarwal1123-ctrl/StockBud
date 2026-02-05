import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Package, Save, CheckCircle2, Trash2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ExecutiveStockEntry() {
  const [selectedStamp, setSelectedStamp] = useState('');
  const [stampItems, setStampItems] = useState([]);
  const [stockData, setStockData] = useState({});
  const [loading, setLoading] = useState(false);
  const [stamps, setStamps] = useState([]);
  const [myEntries, setMyEntries] = useState([]);
  const [editingEntry, setEditingEntry] = useState(null);

  const { user } = useAuth();

  useEffect(() => {
    fetchStamps();
    fetchMyEntries();
  }, []);

  const fetchStamps = async () => {
    try {
      const response = await axios.get(`${API}/master-items`);
      const uniqueStamps = [...new Set(response.data.map(item => item.stamp))].sort((a, b) => {
        const numA = parseInt(a.replace(/\D/g, '')) || 0;
        const numB = parseInt(b.replace(/\D/g, '')) || 0;
        return numA - numB;
      });
      setStamps(uniqueStamps);
    } catch (error) {
      toast.error('Failed to load stamps');
    }
  };

  const fetchMyEntries = async () => {
    try {
      const response = await axios.get(`${API}/executive/my-entries/${user.username}`);
      setMyEntries(response.data);
    } catch (error) {
      console.error('Failed to fetch entries:', error);
    }
  };

  const loadStampItems = async (stamp) => {
    setLoading(true);
    try {
      // Add timestamp to bust any proxy/CDN caches
      const cacheBuster = `?_t=${Date.now()}`;
      const response = await axios.get(`${API}/master-items${cacheBuster}`);
      const items = response.data.filter(item => item.stamp === stamp);
      setStampItems(items);
      
      const initialData = {};
      items.forEach(item => {
        initialData[item.item_name] = { gross: '' };
      });
      setStockData(initialData);
    } catch (error) {
      toast.error('Failed to load items');
    } finally {
      setLoading(false);
    }
  };

  const handleStampChange = (stamp) => {
    if (!editingEntry) {
      setSelectedStamp(stamp);
      loadStampItems(stamp);
    }
  };

  const handleSave = async () => {
    const entries = Object.entries(stockData)
      .filter(([_, data]) => data.gross)
      .map(([itemName, data]) => ({
        item_name: itemName,
        gross_wt: parseFloat(data.gross) || 0
      }));

    if (entries.length === 0) {
      toast.error('Please enter at least one weight');
      return;
    }

    try {
      if (editingEntry) {
        await axios.put(`${API}/executive/update-entry/${selectedStamp}`, {
          entries,
          entered_by: user.username
        });
        toast.success('Entry updated and resubmitted!');
      } else {
        await axios.post(`${API}/executive/stock-entry`, {
          stamp: selectedStamp,
          entries,
          entered_by: user.username
        });
        toast.success('Sent for approval!');
      }
      
      setStockData({});
      setEditingEntry(null);
      setSelectedStamp('');
      setStampItems([]);
      fetchMyEntries();
    } catch (error) {
      toast.error('Failed to save stock entry');
    }
  };

  const editEntry = (entry) => {
    setEditingEntry(entry);
    setSelectedStamp(entry.stamp);
    
    axios.get(`${API}/master-items`).then(response => {
      const items = response.data.filter(item => item.stamp === entry.stamp);
      setStampItems(items);
      
      const data = {};
      items.forEach(item => {
        const existingEntry = entry.entries?.find(e => e.item_name === item.item_name);
        data[item.item_name] = { gross: existingEntry?.gross_wt || '' };
      });
      setStockData(data);
    });
  };

  const deleteEntry = async (stamp) => {
    const confirmed = window.confirm(`Delete stock entry for ${stamp}?`);
    if (!confirmed) return;

    try {
      await axios.delete(`${API}/executive/delete-entry/${stamp}/${user.username}`);
      toast.success('Entry deleted');
      
      // Close edit form if currently editing this entry
      if (editingEntry && editingEntry.stamp === stamp) {
        setEditingEntry(null);
        setSelectedStamp('');
        setStampItems([]);
        setStockData({});
      }
      
      fetchMyEntries();
    } catch (error) {
      toast.error('Failed to delete entry');
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Stock Entry
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Enter physical stock for stamps
        </p>
      </div>

      {/* My Entries */}
      {myEntries.length > 0 && (
        <Card className="border-primary/20">
          <CardHeader>
            <CardTitle>My Stock Entries</CardTitle>
            <CardDescription>Previous submissions - Edit rejected entries</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {myEntries.map((entry, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex-1">
                    <p className="font-semibold">{entry.stamp}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(entry.entry_date).toLocaleString()} - {entry.entries?.length || 0} items
                    </p>
                    {entry.rejection_message && (
                      <Alert className="mt-2 border-red-500/50 bg-red-50">
                        <AlertDescription className="text-sm">
                          <strong>Manager says:</strong> {entry.rejection_message}
                        </AlertDescription>
                      </Alert>
                    )}
                    <Badge className={
                      entry.status === 'approved' ? 'bg-green-600 mt-2' : 
                      entry.status === 'rejected' ? 'bg-red-600 mt-2' : 'bg-orange-600 mt-2'
                    }>
                      {entry.status.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="flex gap-2">
                    {entry.status === 'rejected' && (
                      <>
                        <Button onClick={() => editEntry(entry)} size="sm">Edit</Button>
                        <Button onClick={() => deleteEntry(entry.stamp)} size="sm" variant="destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stamp Selector */}
      <Card className="border-primary/20">
        <CardHeader>
          <CardTitle>Select Stamp</CardTitle>
          <CardDescription>Choose warehouse location to count</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={selectedStamp} onValueChange={handleStampChange} disabled={editingEntry !== null}>
            <SelectTrigger className="w-full md:w-64">
              <SelectValue placeholder="Choose stamp..." />
            </SelectTrigger>
            <SelectContent>
              {stamps.map(stamp => (
                <SelectItem key={stamp} value={stamp}>{stamp}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {editingEntry && (
            <p className="text-xs text-orange-600 mt-2">✏️ Editing {selectedStamp} - Stamp locked</p>
          )}
        </CardContent>
      </Card>

      {/* Stock Entry Form */}
      {selectedStamp && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{selectedStamp} - Stock Entry</CardTitle>
                <CardDescription>{stampItems.length} items</CardDescription>
              </div>
              <Button onClick={handleSave}>
                <Save className="h-4 w-4 mr-2" />
                {editingEntry ? 'Update Entry' : 'Save Entry'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-8 text-muted-foreground">Loading items...</div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {stampItems.map((item, idx) => (
                  <div key={idx} className="grid grid-cols-2 gap-3 items-center p-3 border rounded-lg">
                    <div>
                      <p className="font-medium text-sm">{item.item_name}</p>
                    </div>
                    <div>
                      <Label className="text-xs">Gross Weight (kg) *</Label>
                      <Input
                        type="number"
                        step="0.001"
                        placeholder="0.000"
                        value={stockData[item.item_name]?.gross || ''}
                        onChange={(e) => setStockData({...stockData, [item.item_name]: { gross: e.target.value }})}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Alert className="border-blue-500/50 bg-blue-500/10">
        <CheckCircle2 className="h-5 w-5 text-blue-600" />
        <AlertDescription>
          <strong>Instructions:</strong> Select stamp, enter gross weights. Manager will review and approve.
        </AlertDescription>
      </Alert>
    </div>
  );
}
