import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Tag, TrendingUp, Package, Calendar } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ItemDetail() {
  const { itemName } = useParams();
  const navigate = useNavigate();
  const [itemData, setItemData] = useState(null);
  const [newStamp, setNewStamp] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchItemDetail();
  }, [itemName]);

  const fetchItemDetail = async () => {
    try {
      const response = await axios.get(`${API}/item/${encodeURIComponent(itemName)}`);
      setItemData(response.data);
      setNewStamp(response.data.current_stamp || '');
    } catch (error) {
      console.error('Error fetching item:', error);
      toast.error('Failed to load item details');
    } finally {
      setLoading(false);
    }
  };

  const handleStampAssignment = async () => {
    if (!newStamp) {
      toast.error('Please enter a stamp');
      return;
    }

    try {
      await axios.post(`${API}/item/${encodeURIComponent(itemName)}/assign-stamp?stamp=${encodeURIComponent(newStamp)}`);
      toast.success(`Stamp "${newStamp}" assigned successfully!`);
      fetchItemDetail();
    } catch (error) {
      toast.error('Failed to assign stamp');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading item details...</div>
      </div>
    );
  }

  if (!itemData) {
    return (
      <div className="p-3 sm:p-6 md:p-8">
        <Button onClick={() => navigate(-1)} variant="outline" className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <p>Item not found</p>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6" data-testid="item-detail-page">
      <div className="flex items-center justify-between">
        <div>
          <Button onClick={() => navigate(-1)} variant="ghost" className="mb-2" data-testid="back-button">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">{itemData.item_name}</h1>
          <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">Complete item history and statistics</p>
        </div>
      </div>

      {/* Key Stats */}
      <div className="grid gap-3 sm:gap-6 grid-cols-2 md:grid-cols-4">
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-primary/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Package className="h-4 w-4 text-primary" />
              Current Stock
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono text-primary">
              {itemData.current_stock_kg} kg
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-accent/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-accent" />
              Tunch Margin
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono text-accent">
              {itemData.tunch_margin}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Sale: {itemData.avg_sale_tunch}% | Purchase: {itemData.avg_purchase_tunch}%
            </p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Purchases</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{itemData.total_purchases}</div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Sales</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg sm:text-2xl md:text-3xl font-bold font-mono">{itemData.total_sales}</div>
          </CardContent>
        </Card>
      </div>

      {/* Stamp Assignment */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tag className="h-5 w-5 text-primary" />
            Stamp Assignment
          </CardTitle>
          <CardDescription>Assign or change the stamp category for this item</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <Label htmlFor="stamp">Current Stamp</Label>
              <div className="flex gap-2 mt-2">
                <Badge variant="outline" className="text-base px-4 py-2">
                  {itemData.current_stamp}
                </Badge>
              </div>
            </div>
            <div className="flex-1">
              <Label htmlFor="new-stamp">New Stamp</Label>
              <div className="flex gap-2 mt-2">
                <Input
                  id="new-stamp"
                  value={newStamp}
                  onChange={(e) => setNewStamp(e.target.value)}
                  placeholder="Enter stamp name"
                  data-testid="stamp-input"
                />
                <Button onClick={handleStampAssignment} data-testid="assign-stamp-button">
                  Assign
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Transactions */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-primary" />
            Recent Transactions
          </CardTitle>
          <CardDescription>Last 20 purchase and sale transactions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Party</TableHead>
                  <TableHead className="text-right font-mono">Weight (kg)</TableHead>
                  <TableHead className="text-right">Tunch %</TableHead>
                  <TableHead className="text-right">Labour</TableHead>
                  <TableHead>Stamp</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {itemData.recent_transactions?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                      No transactions found
                    </TableCell>
                  </TableRow>
                ) : (
                  itemData.recent_transactions?.map((trans, idx) => (
                    <TableRow key={idx} className="table-row">
                      <TableCell>{trans.date || 'N/A'}</TableCell>
                      <TableCell>
                        <Badge className={trans.type === 'purchase' ? 'bg-secondary' : 'bg-accent'}>
                          {trans.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium">{trans.party_name || 'N/A'}</TableCell>
                      <TableCell className="text-right font-mono">{trans.net_wt.toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono">{trans.tunch || 'N/A'}</TableCell>
                      <TableCell className="text-right font-mono">{trans.labor || 'N/A'}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {trans.stamp || 'Unassigned'}
                        </Badge>
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
