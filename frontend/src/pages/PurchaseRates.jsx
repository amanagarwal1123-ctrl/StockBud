import { useEffect, useState } from 'react';
import axios from 'axios';
import { Receipt, Download, Search } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatIndianCurrency } from '@/utils/formatCurrency';
import { exportToCSV } from '@/utils/exportCSV';
import { useSortableData } from '@/hooks/useSortableData';
import { SortableHeader } from '@/components/SortableHeader';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PurchaseRates() {
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchLedger();
  }, []);

  const fetchLedger = async () => {
    try {
      const response = await axios.get(`${API}/purchase-ledger/all`);
      setLedger(response.data);
    } catch (error) {
      console.error('Error fetching ledger:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredLedger = ledger.filter(item =>
    item.item_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const { sortedData: sortedLedger, sortConfig: ledgerSortConfig, requestSort: ledgerRequestSort } = useSortableData(filteredLedger, 'item_name', 'asc');

  const handleExport = () => {
    const exportData = filteredLedger.map(item => ({
      'Item Name': item.item_name,
      'Purchase Tunch (%)': item.purchase_tunch.toFixed(2),
      'Labour per kg': item.labour_per_kg.toFixed(2)
    }));
    exportToCSV(exportData, 'purchase_rate_ledger');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          Purchase Rate Ledger
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          Cumulative purchase rates (tunch & labour) for profit calculation
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-1">
        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono text-primary">{ledger.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search items..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button onClick={handleExport} variant="outline">
          <Download className="h-4 w-4 mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Ledger Table */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="h-5 w-5 text-primary" />
            Purchase Rate Ledger ({filteredLedger.length} items)
          </CardTitle>
          <CardDescription>
            Calculated from PURCHASE_CUMUL.xlsx - Used as cost basis for profit calculation
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHeader label="Item Name" sortKey="item_name" sortConfig={ledgerSortConfig} onSort={ledgerRequestSort} className="text-xs" />
                  <SortableHeader label="Purchase Tunch (%)" sortKey="purchase_tunch" sortConfig={ledgerSortConfig} onSort={ledgerRequestSort} className="text-xs text-right font-mono" />
                  <SortableHeader label="Labour per kg" sortKey="labour_per_kg" sortConfig={ledgerSortConfig} onSort={ledgerRequestSort} className="text-xs text-right font-mono" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedLedger.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                      No items found
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedLedger.map((item, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="text-xs font-medium max-w-[150px] sm:max-w-none truncate">{item.item_name}</TableCell>
                      <TableCell className="text-right font-mono text-primary font-semibold">
                        {item.purchase_tunch.toFixed(2)}%
                      </TableCell>
                      <TableCell className="text-right font-mono text-blue-600">
                        {formatIndianCurrency(item.labour_per_kg)}
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
