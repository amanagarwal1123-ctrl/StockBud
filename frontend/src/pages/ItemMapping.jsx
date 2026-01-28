import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link2, AlertCircle, Search, Check, X } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ItemMapping() {
  const [unmappedItems, setUnmappedItems] = useState([]);
  const [masterItems, setMasterItems] = useState([]);
  const [allMasterItems, setAllMasterItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedMappings, setSelectedMappings] = useState({});
  const [showAllForItem, setShowAllForItem] = useState({});

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [unmappedRes, masterRes] = await Promise.all([
        axios.get(`${API}/mappings/unmapped`),
        axios.get(`${API}/master-items`)
      ]);
      
      setUnmappedItems(unmappedRes.data.unmapped_items || []);
      setMasterItems(masterRes.data);
      setAllMasterItems(masterRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSuggestions = (transactionName) => {
    if (!allMasterItems || allMasterItems.length === 0) {
      return [];
    }

    // Intelligent matching: find items with similar names
    const searchTerms = transactionName.toLowerCase().split(/[\s-]+/).filter(term => term.length > 2);
    
    const scored = allMasterItems.map(item => {
      const itemLower = item.item_name.toLowerCase();
      let score = 0;
      
      // Exact match
      if (itemLower === transactionName.toLowerCase()) {
        score = 100;
      } else {
        // Partial matches
        searchTerms.forEach(term => {
          if (itemLower.includes(term)) {
            score += 10;
          }
        });
        
        // Check if starts with same chars
        const prefix = transactionName.toLowerCase().substring(0, Math.min(5, transactionName.length));
        if (itemLower.startsWith(prefix)) {
          score += 5;
        }
        
        // For very short names or specific patterns, be more lenient
        if (transactionName.length <= 10) {
          const transWords = transactionName.toLowerCase().split(/[\s-]+/);
          const itemWords = itemLower.split(/[\s-]+/);
          transWords.forEach(tw => {
            itemWords.forEach(iw => {
              if (tw.length > 2 && iw.includes(tw)) {
                score += 3;
              }
            });
          });
        }
      }
      
      return { ...item, score };
    });
    
    // Return top 8 suggestions with score > 0
    return scored
      .filter(item => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8);
  };

  const handleSaveMapping = async (transactionName, masterName) => {
    try {
      await axios.post(`${API}/mappings/create`, null, {
        params: { transaction_name: transactionName, master_name: masterName }
      });
      
      toast.success(`Mapped: ${transactionName} → ${masterName}`);
      
      // Remove from unmapped list
      setUnmappedItems(prev => prev.filter(item => item !== transactionName));
      setSelectedMappings(prev => ({ ...prev, [transactionName]: undefined }));
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create mapping');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Item Name Mapping
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Map transaction item names to master stock items (STOCK 2026) - {allMasterItems.length} master items available
        </p>
      </div>

      {unmappedItems.length === 0 ? (
        <Alert className="border-green-500/50 bg-green-500/10">
          <Check className="h-5 w-5 text-green-600" />
          <AlertDescription className="ml-2">
            All items are mapped! No unmapped items found in transactions.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert className="border-orange-500/50 bg-orange-500/10">
          <AlertCircle className="h-5 w-5 text-orange-600" />
          <AlertDescription className="ml-2">
            <strong>{unmappedItems.length} unmapped items</strong> found in transactions. Please map them to master items.
          </AlertDescription>
        </Alert>
      )}

      {/* Unmapped Items */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle>Unmapped Items</CardTitle>
          <CardDescription>
            Items found in purchase/sale files that don't exist in STOCK 2026
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {unmappedItems.map((item, idx) => {
              const suggestions = getSuggestions(item);
              const showingAll = showAllForItem[item];
              const itemsToShow = showingAll ? allMasterItems : suggestions;
              
              return (
                <div key={idx} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-lg">{item}</p>
                      <p className="text-sm text-muted-foreground">
                        {suggestions.length > 0 
                          ? `${suggestions.length} intelligent suggestions` 
                          : 'No suggestions found'}
                      </p>
                    </div>
                    <Badge variant="outline" className="text-orange-600">Unmapped</Badge>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Map to master item:</label>
                    <Select
                      value={selectedMappings[item] || ''}
                      onValueChange={(value) => setSelectedMappings(prev => ({ ...prev, [item]: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select master item..." />
                      </SelectTrigger>
                      <SelectContent className="max-h-60">
                        {itemsToShow.map((master, midx) => (
                          <SelectItem key={midx} value={master.item_name}>
                            {master.item_name} [{master.stamp}]
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {selectedMappings[item] && (
                      <p className="text-xs text-muted-foreground">
                        Selected: {selectedMappings[item]}
                      </p>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <Button
                      onClick={() => handleSaveMapping(item, selectedMappings[item])}
                      disabled={!selectedMappings[item]}
                      size="sm"
                    >
                      <Check className="h-4 w-4 mr-1" />
                      Save Mapping
                    </Button>
                    
                    {!showingAll && suggestions.length > 0 && (
                      <Button
                        onClick={() => setShowAllForItem(prev => ({ ...prev, [item]: true }))}
                        variant="outline"
                        size="sm"
                      >
                        <Search className="h-4 w-4 mr-1" />
                        Show All Items ({allMasterItems.length})
                      </Button>
                    )}
                    
                    {showingAll && (
                      <Button
                        onClick={() => setShowAllForItem(prev => ({ ...prev, [item]: false }))}
                        variant="outline"
                        size="sm"
                      >
                        Show Suggestions Only
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
