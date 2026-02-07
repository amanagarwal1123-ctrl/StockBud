import { useEffect, useState } from 'react';
import axios from 'axios';
import { Search, Package, Filter } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function BookInventory() {
  const [inventory, setInventory] = useState([]);
  const [byStamp, setByStamp] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStamp, setSelectedStamp] = useState('all');

  useEffect(() => {
    fetchInventory();
  }, []);

  const fetchInventory = async () => {
    try {
      const response = await axios.get(`${API}/inventory/book`);
      setInventory(response.data.inventory);
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
        <div className="text-muted-foreground">Loading inventory...</div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="book-inventory-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight" data-testid="book-inventory-title">
          Book Inventory
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Calculated inventory based on purchases and sales
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-6 md:grid-cols-3">
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono" data-testid="total-items-count">{inventory.length}</div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Stamps</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono">{Object.keys(byStamp).length}</div>
          </CardContent>
        </Card>
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Gross Weight</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono">
              {inventory.reduce((sum, item) => sum + item.gr_wt, 0).toFixed(3)}g
            </div>
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
            data-testid="search-input"
          />
        </div>
        <Select value={selectedStamp} onValueChange={setSelectedStamp}>
          <SelectTrigger className="w-full md:w-64" data-testid="stamp-filter">
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
            Inventory Items
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
                  <TableHead className="text-right font-mono">Gross Wt (g)</TableHead>
                  <TableHead className="text-right font-mono">Net Wt (g)</TableHead>
                  <TableHead className="text-right font-mono">Fine Silver</TableHead>
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
                    <TableRow key={idx} className="table-row" data-testid={`inventory-row-${idx}`}>
                      <TableCell className="font-medium">{item.item_name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {item.stamp || 'Unassigned'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono">{item.gr_wt.toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono">{item.net_wt.toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono">{item.fine_sil.toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono">{item.total_pc}</TableCell>
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