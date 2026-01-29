import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Package, Save, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ExecutiveStockEntry() {
  const [selectedStamp, setSelectedStamp] = useState('');
  const [stampItems, setStampItems] = useState([]);
  const [stockData, setStockData] = useState({});
  const [loading, setLoading] = useState(false);
  const [stamps, setStamps] = useState([]);

  const { user } = useAuth();

  useEffect(() => {
    fetchStamps();
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

  const loadStampItems = async (stamp) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/master-items?search=`);
      const items = response.data.filter(item => item.stamp === stamp);
      setStampItems(items);
      
      // Initialize stock data (only gross weight)
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
    setSelectedStamp(stamp);
    loadStampItems(stamp);
  };

  const handleWeightChange = (itemName, field, value) => {
    setStockData(prev => ({
      ...prev,
      [itemName]: {
        ...prev[itemName],
        [field]: value
      }
    }));
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
      await axios.post(`${API}/executive/stock-entry`, {
        stamp: selectedStamp,
        entries,
        entered_by: user.username
      });
      
      toast.success(`Stock entry saved for ${selectedStamp}!`);
      setStockData({});
    } catch (error) {
      toast.error('Failed to save stock entry');
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Stock Entry
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Enter physical stock for one stamp at a time
        </p>
      </div>

      {/* Stamp Selector */}
      <Card className="border-primary/20">
        <CardHeader>
          <CardTitle>Select Stamp</CardTitle>
          <CardDescription>Choose which warehouse location to count</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={selectedStamp} onValueChange={handleStampChange}>
            <SelectTrigger className="w-full md:w-64">
              <SelectValue placeholder="Choose stamp..." />
            </SelectTrigger>
            <SelectContent>
              {stamps.map(stamp => (
                <SelectItem key={stamp} value={stamp}>{stamp}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* Stock Entry Form */}
      {selectedStamp && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{selectedStamp} - Stock Entry</CardTitle>
                <CardDescription>{stampItems.length} items in this stamp</CardDescription>
              </div>
              <Button onClick={handleSave}>
                <Save className="h-4 w-4 mr-2" />
                Save Entry
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
                        onChange={(e) => handleWeightChange(item.item_name, 'gross', e.target.value)}
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
          <strong>Stock Entry Instructions:</strong> Select a stamp, enter gross and net weights for items you've counted. 
          The manager will verify and approve your entry.
        </AlertDescription>
      </Alert>
    </div>
  );
}
