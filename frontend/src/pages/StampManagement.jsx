import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Tag, Search, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function StampManagement() {
  const navigate = useNavigate();
  const [inventory, setInventory] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [stampChanges, setStampChanges] = useState({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('name');

  useEffect(() => {
    fetchInventory();
  }, []);

  const fetchInventory = async () => {
    try {
      const response = await axios.get(`${API}/inventory/current`);
      // Inventory already resolves mappings + groups — single source of truth
      const allItems = response.data.inventory || [];
      const negItems = response.data.negative_items || [];
      
      const uniqueItems = new Map();
      [...allItems, ...negItems].forEach(item => {
        uniqueItems.set(item.item_name, {
          item_name: item.item_name,
          stamp: item.stamp || 'Unassigned'
        });
      });
      
      setInventory(Array.from(uniqueItems.values()));
    } catch (error) {
      console.error('Error fetching inventory:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStampChange = (itemName, newStamp) => {
    setStampChanges({
      ...stampChanges,
      [itemName]: newStamp
    });
  };

  const saveStampChanges = async () => {
    if (Object.keys(stampChanges).length === 0) {
      toast.error('No changes to save');
      return;
    }

    setSaving(true);
    let successCount = 0;
    let errorCount = 0;

    for (const [itemName, stamp] of Object.entries(stampChanges)) {
      try {
        await axios.post(`${API}/item/${encodeURIComponent(itemName)}/assign-stamp?stamp=${encodeURIComponent(stamp)}`);
        successCount++;
      } catch (error) {
        errorCount++;
      }
    }

    setSaving(false);
    
    if (successCount > 0) {
      toast.success(`${successCount} stamp(s) assigned successfully!`);
      setStampChanges({});
      fetchInventory();
    }
    
    if (errorCount > 0) {
      toast.error(`${errorCount} stamp(s) failed to assign`);
    }
  };

  const handleNormalizeStamps = async () => {
    const confirmed = window.confirm(
      '🔧 Normalize All Stamps to CAPS Format?\n\n' +
      'This will convert all stamps to consistent "STAMP X" format:\n' +
      '• "Stamp 1" → "STAMP 1"\n' +
      '• "stamp 1" → "STAMP 1"\n' +
      '• "STamp 1" → "STAMP 1"\n\n' +
      'This will consolidate duplicate stamps and fix inconsistencies.\n\n' +
      'Continue?'
    );
    
    if (!confirmed) return;
    
    try {
      setSaving(true);
      toast.info('Normalizing all stamps... Please wait.');
      
      const response = await axios.post(`${API}/admin/normalize-stamps`);
      
      toast.success(response.data.message);
      
      if (response.data.total_documents > 0) {
        toast.info(`✓ Updated ${response.data.total_documents} documents across ${response.data.stamps_updated} stamp variations`);
      }
      
      // Refresh after 2 seconds
      setTimeout(() => {
        window.location.reload();
      }, 2000);
      
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Normalization failed');
    } finally {
      setSaving(false);
    }
  };

  const filteredInventory = inventory.filter(item =>
    item.item_name.toLowerCase().includes(searchTerm.toLowerCase())
  );
  
  // Sort items
  const sortedInventory = [...filteredInventory].sort((a, b) => {
    if (sortBy === 'stamp') {
      const stampA = parseInt(a.stamp.replace(/\D/g, '')) || 999;
      const stampB = parseInt(b.stamp.replace(/\D/g, '')) || 999;
      return stampA - stampB;
    }
    // Default: sort by name
    return a.item_name.localeCompare(b.item_name);
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading items...</div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="stamp-management-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
            Stamp Management
          </h1>
          <p className="text-lg text-muted-foreground mt-2">
            Assign or change stamps for items in bulk
          </p>
        </div>
        <div className="flex gap-2">
          <Button 
            onClick={handleNormalizeStamps}
            variant="secondary"
            size="lg"
            className="shadow-md"
          >
            <Tag className="mr-2 h-5 w-5" />
            Normalize All Stamps
          </Button>
          <Button 
            onClick={saveStampChanges} 
            disabled={saving || Object.keys(stampChanges).length === 0}
            size="lg"
            className="shadow-md"
            data-testid="save-stamps-button"
          >
            <Save className="mr-2 h-5 w-5" />
            Save {Object.keys(stampChanges).length > 0 && `(${Object.keys(stampChanges).length})`}
          </Button>
        </div>
      </div>

      {Object.keys(stampChanges).length > 0 && (
        <Card className="border-accent/50 bg-accent/10">
          <CardContent className="py-3">
            <p className="text-sm font-medium">
              {Object.keys(stampChanges).length} unsaved changes - Click Save to apply
            </p>
          </CardContent>
        </Card>
      )}

      {/* Search and Sort */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search items..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
            data-testid="search-input"
          />
        </div>
        <Select value={sortBy} onValueChange={setSortBy}>
          <SelectTrigger className="w-full md:w-48">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="name">Sort by Name</SelectItem>
            <SelectItem value="stamp">Sort by Stamp</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Items Table */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tag className="h-5 w-5 text-primary" />
            Items ({sortedInventory.length})
          </CardTitle>
          <CardDescription>
            Click on any item to view details, or modify stamps here
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item Name</TableHead>
                  <TableHead>Current Stamp</TableHead>
                  <TableHead>New Stamp</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredInventory.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                      No items found
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedInventory.map((item, idx) => (
                    <TableRow key={idx} className="table-row">
                      <TableCell 
                        className="font-medium text-primary hover:underline cursor-pointer"
                        onClick={() => navigate(`/item/${encodeURIComponent(item.item_name)}`)}
                      >
                        {item.item_name}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {item.stamp}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Input
                          placeholder="Enter new stamp"
                          value={stampChanges[item.item_name] || ''}
                          onChange={(e) => handleStampChange(item.item_name, e.target.value)}
                          className="max-w-xs"
                          data-testid={`stamp-input-${idx}`}
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/item/${encodeURIComponent(item.item_name)}`)}
                        >
                          View Details
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
