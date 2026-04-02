import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Tag, TrendingUp, Package, Calendar, DollarSign, AlertTriangle, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { formatIndianCurrency } from '@/utils/formatCurrency';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ItemDetail() {
  const { itemName } = useParams();
  const navigate = useNavigate();
  const [itemData, setItemData] = useState(null);
  const [newStamp, setNewStamp] = useState('');
  const [loading, setLoading] = useState(true);
  const [purchaseTunch, setPurchaseTunch] = useState('');
  const [labourPerKg, setLabourPerKg] = useState('');
  const [savingRate, setSavingRate] = useState(false);

  useEffect(() => {
    fetchItemDetail();
  }, [itemName]);

  const fetchItemDetail = async () => {
    try {
      const response = await axios.get(`${API}/item/${encodeURIComponent(itemName)}`);
      setItemData(response.data);
      setNewStamp(response.data.current_stamp || '');
      setPurchaseTunch(response.data.purchase_tunch_ledger ? Math.round(response.data.purchase_tunch_ledger * 100) / 100 : '');
      setLabourPerKg(response.data.labour_per_kg_ledger ? Math.round(response.data.labour_per_kg_ledger * 100) / 100 : '');
    } catch (error) {
      console.error('Error fetching item:', error);
      toast.error('Failed to load item details');
    } finally {
      setLoading(false);
    }
  };

  const handleStampAssignment = async () => {
    if (!newStamp) { toast.error('Please enter a stamp'); return; }
    try {
      await axios.post(`${API}/item/${encodeURIComponent(itemName)}/assign-stamp?stamp=${encodeURIComponent(newStamp)}`);
      toast.success(`Stamp "${newStamp}" assigned!`);
      fetchItemDetail();
    } catch (error) { toast.error('Failed to assign stamp'); }
  };

  const handleSavePurchaseRate = async () => {
    if (!purchaseTunch && !labourPerKg) { toast.error('Enter tunch or labour rate'); return; }
    setSavingRate(true);
    try {
      await axios.post(`${API}/item/${encodeURIComponent(itemName)}/set-purchase-rate`, {
        purchase_tunch: purchaseTunch ? parseFloat(purchaseTunch) : undefined,
        labour_per_kg: labourPerKg ? parseFloat(labourPerKg) : undefined,
      });
      toast.success('Purchase rate saved!');
      fetchItemDetail();
    } catch (error) { toast.error('Failed to save purchase rate'); }
    finally { setSavingRate(false); }
  };

  if (loading) return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <h1 className="text-2xl sm:text-4xl font-bold tracking-tight">{decodeURIComponent(itemName)}</h1>
      <p className="text-muted-foreground">Loading...</p>
    </div>
  );

  if (!itemData) return (
    <div className="p-3 sm:p-6 md:p-8">
      <Button onClick={() => navigate(-1)} variant="outline" className="mb-4"><ArrowLeft className="h-4 w-4 mr-2" />Back</Button>
      <p>Item not found</p>
    </div>
  );

  const noRate = !itemData.has_purchase_rate;

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6" data-testid="item-detail-page">
      <div>
        <Button onClick={() => navigate(-1)} variant="ghost" className="mb-2" data-testid="back-button">
          <ArrowLeft className="h-4 w-4 mr-2" />Back
        </Button>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">{itemData.item_name}</h1>
        <p className="text-xs sm:text-base text-muted-foreground mt-1">Complete item history and statistics</p>
      </div>

      {noRate && (
        <Alert className="border-orange-500/50 bg-orange-50">
          <AlertTriangle className="h-4 w-4 text-orange-600" />
          <AlertDescription className="text-sm">
            <strong>No purchase rate found.</strong> Fine and labour values will be zero. Set the purchase rate below.
          </AlertDescription>
        </Alert>
      )}

      {/* Key Stats */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 md:grid-cols-4">
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-primary/10 to-transparent">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-[10px] sm:text-xs font-medium text-muted-foreground flex items-center gap-1">
              <Package className="h-3 w-3 text-primary" />Current Stock
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="text-lg sm:text-2xl font-bold font-mono text-primary">{itemData.current_stock_kg} kg</div>
            <p className="text-[10px] text-muted-foreground">Gross: {itemData.current_gr_wt_kg} kg</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-green-500/10 to-transparent">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-[10px] sm:text-xs font-medium text-muted-foreground flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-green-600" />Tunch Margin
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className={`text-lg sm:text-2xl font-bold font-mono ${itemData.tunch_margin > 0 ? 'text-green-600' : 'text-red-600'}`}>
              {itemData.tunch_margin}%
            </div>
            <p className="text-[10px] text-muted-foreground">S: {itemData.avg_sale_tunch}% | P: {itemData.avg_purchase_tunch}%</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-blue-500/10 to-transparent">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-[10px] sm:text-xs font-medium text-muted-foreground flex items-center gap-1">
              <DollarSign className="h-3 w-3 text-blue-600" />Labour Margin
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className={`text-lg sm:text-2xl font-bold font-mono ${itemData.labour_margin >= 0 ? 'text-blue-600' : 'text-red-600'}`}>
              {formatIndianCurrency(itemData.labour_margin)}/kg
            </div>
            <p className="text-[10px] text-muted-foreground">S: {formatIndianCurrency(itemData.avg_sale_labour)} | P: {formatIndianCurrency(itemData.avg_purchase_labour)}</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader className="p-3 pb-1">
            <CardTitle className="text-[10px] sm:text-xs font-medium text-muted-foreground">Transactions</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="text-lg sm:text-2xl font-bold font-mono">{itemData.total_purchases + itemData.total_sales}</div>
            <p className="text-[10px] text-muted-foreground">Buy: {itemData.total_purchases} | Sell: {itemData.total_sales}</p>
          </CardContent>
        </Card>
      </div>

      {/* Purchase Rate Input (for items without purchase rates) */}
      <Card className={`border-border/40 shadow-sm ${noRate ? 'border-orange-500/30 bg-orange-50/30' : ''}`}>
        <CardHeader className="p-3 sm:p-6 pb-2">
          <CardTitle className="text-sm sm:text-base flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-primary" />
            Purchase Rate {noRate && <Badge variant="outline" className="text-orange-600 border-orange-400 text-[10px]">NOT SET</Badge>}
          </CardTitle>
          <CardDescription className="text-xs">Purchase tunch % and labour rate used for fine/labour calculations</CardDescription>
        </CardHeader>
        <CardContent className="p-3 sm:p-6 pt-0">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Purchase Tunch (%)</Label>
              <Input type="number" step="0.01" value={purchaseTunch} onChange={(e) => setPurchaseTunch(e.target.value)}
                placeholder="e.g. 65" className="mt-1 h-8 text-sm" data-testid="purchase-tunch-input" />
            </div>
            <div>
              <Label className="text-xs">Labour per kg (Rs)</Label>
              <Input type="number" step="0.01" value={labourPerKg} onChange={(e) => setLabourPerKg(e.target.value)}
                placeholder="e.g. 1200" className="mt-1 h-8 text-sm" data-testid="labour-per-kg-input" />
            </div>
          </div>
          <Button onClick={handleSavePurchaseRate} disabled={savingRate} size="sm" className="mt-3 h-8 text-xs" data-testid="save-purchase-rate">
            <Save className="h-3 w-3 mr-1" />{savingRate ? 'Saving...' : 'Save Purchase Rate'}
          </Button>
        </CardContent>
      </Card>

      {/* Stamp Assignment */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader className="p-3 sm:p-6 pb-2">
          <CardTitle className="text-sm sm:text-base flex items-center gap-2">
            <Tag className="h-4 w-4 text-primary" />Stamp Assignment
          </CardTitle>
        </CardHeader>
        <CardContent className="p-3 sm:p-6 pt-0">
          <div className="flex items-end gap-3">
            <Badge variant="outline" className="text-sm px-3 py-1.5">{itemData.current_stamp}</Badge>
            <div className="flex-1 flex gap-2">
              <Input value={newStamp} onChange={(e) => setNewStamp(e.target.value)} placeholder="New stamp" className="h-8 text-sm" data-testid="stamp-input" />
              <Button onClick={handleStampAssignment} size="sm" className="h-8 text-xs" data-testid="assign-stamp-button">Assign</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent Transactions */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader className="p-3 sm:p-6 pb-2">
          <CardTitle className="text-sm sm:text-base flex items-center gap-2">
            <Calendar className="h-4 w-4 text-primary" />Recent Transactions
          </CardTitle>
          <CardDescription className="text-xs">Last 20 transactions</CardDescription>
        </CardHeader>
        <CardContent className="p-2 sm:p-6 pt-0">
          <div className="overflow-x-auto">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Date</TableHead>
                  <TableHead className="text-xs">Type</TableHead>
                  <TableHead className="text-xs">Party</TableHead>
                  <TableHead className="text-xs text-right font-mono">Weight</TableHead>
                  <TableHead className="text-xs text-right">Tunch %</TableHead>
                  <TableHead className="text-xs text-right">Labour</TableHead>
                  <TableHead className="text-xs">Stamp</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {itemData.recent_transactions?.length === 0 ? (
                  <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">No transactions found</TableCell></TableRow>
                ) : (
                  itemData.recent_transactions?.map((trans, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="text-xs py-1.5">{trans.date || 'N/A'}</TableCell>
                      <TableCell className="py-1.5">
                        <Badge className={`text-[10px] ${trans.type === 'purchase' ? 'bg-secondary' : 'bg-accent'}`}>{trans.type}</Badge>
                      </TableCell>
                      <TableCell className="text-xs py-1.5 max-w-[100px] truncate">{trans.party_name || 'N/A'}</TableCell>
                      <TableCell className="text-right font-mono text-xs py-1.5">{(trans.net_wt || 0).toFixed(3)}</TableCell>
                      <TableCell className="text-right font-mono text-xs py-1.5">{trans.tunch || 'N/A'}</TableCell>
                      <TableCell className="text-right font-mono text-xs py-1.5">{trans.labor || 'N/A'}</TableCell>
                      <TableCell className="py-1.5"><Badge variant="outline" className="text-[10px]">{trans.stamp || '—'}</Badge></TableCell>
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
