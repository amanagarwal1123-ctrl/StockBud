import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Search, Package, Filter, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function CurrentStock() {
  const navigate = useNavigate();
  const [inventory, setInventory] = useState([]);
  const [negativeItems, setNegativeItems] = useState([]);
  const [byStamp, setByStamp] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStamp, setSelectedStamp] = useState('all');

  useEffect(() => {
    fetchInventory();
  }, []);

  const fetchInventory = async () => {
    try {
      const response = await axios.get(`${API}/inventory/current`);
      setInventory(response.data.inventory);
      setNegativeItems(response.data.negative_items || []);
      setByStamp(response.data.by_stamp);
    } catch (error) {
      console.error('Error fetching inventory:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredInventory = inventory.filter((item) => {
    const matchesSearch = item.item_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStamp = selectedStamp === 'all' || item.stamp === selectedStamp;
    return matchesSearch && matchesStamp;
  });

  const stamps = ['all', ...Object.keys(byStamp).sort()];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading stock...</div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="current-stock-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Current Stock
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Real-time inventory calculated from opening stock and transactions
        </p>
      </div>

      {/* Negative Stock Alert */}
      {negativeItems.length > 0 && (
        <Alert className="border-destructive/50 bg-destructive/10">
          <AlertTriangle className="h-5 w-5 text-destructive" />
          <AlertDescription className="ml-2">
            <strong>{negativeItems.length} items</strong> have negative stock. Please review and resolve naming inconsistencies.
          </AlertDescription>
        </Alert>
      )}

      {/* Stats */}
      <div className="grid gap-6 md:grid-cols-3">
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-primary/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-primary">{inventory.length}</div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-accent/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Stamps</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-accent">{Object.keys(byStamp).length}</div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-secondary/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Net Weight</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-secondary">
              {(inventory.reduce((sum, item) => sum + item.net_wt, 0) / 1000).toFixed(3)} kg
            </div>
            <p className="text-xs text-muted-foreground mt-1">Pure silver weight</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search items..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <Select value={selectedStamp} onValueChange={setSelectedStamp}>
          <SelectTrigger className="w-full md:w-64">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Filter by stamp" />
          </SelectTrigger>
          <SelectContent>
            {stamps.map((stamp) => (
              <SelectItem key={stamp} value={stamp}>
                {stamp === 'all' ? 'All Stamps' : stamp}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Inventory Table */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5 text-primary" />
            Stock Items
          </CardTitle>
          <CardDescription>
            Showing {filteredInventory.length} of {inventory.length} items
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item Name</TableHead>
                  <TableHead>Stamp</TableHead>
                  <TableHead className="text-right font-mono">Net Wt (kg)</TableHead>
                  <TableHead className="text-right font-mono text-muted-foreground">Gross Wt (kg)</TableHead>
                  <TableHead className="text-right font-mono">Fine</TableHead>
                  <TableHead className="text-right font-mono">Pieces</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredInventory.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No items found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredInventory.map((item, idx) => (
                    <TableRow 
                      key={idx} 
                      className="table-row cursor-pointer hover:bg-primary/5" 
                      onClick={() => navigate(`/item/${encodeURIComponent(item.item_name)}`)}
                      data-testid={`item-row-${idx}`}
                    >
                      <TableCell className="font-medium text-primary hover:underline">
                        {item.item_name}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {item.stamp || 'Unassigned'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono font-semibold text-primary">{(item.net_wt / 1000).toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground">{(item.gr_wt / 1000).toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono">{(item.fine / 1000).toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono">{item.total_pc}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Negative Stock Items */}
      {negativeItems.length > 0 && (
        <Card className="border-destructive/50 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Negative Stock Items
            </CardTitle>
            <CardDescription>
              These items need to be merged or corrected due to naming inconsistencies
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item Name</TableHead>
                    <TableHead>Stamp</TableHead>
                    <TableHead className="text-right font-mono">Net Wt (kg)</TableHead>
                    <TableHead className="text-right font-mono text-muted-foreground">Gross Wt (kg)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {negativeItems.map((item, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-medium">{item.item_name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {item.stamp || 'Unassigned'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-destructive">
                        {item.gr_wt.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-destructive">
                        {item.net_wt.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
