import { useEffect, useState } from 'react';
import axios from 'axios';
import { Scale, CheckCircle2, AlertTriangle, XCircle, Download, Weight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { exportToCSV } from '@/utils/exportCSV';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PhysicalStockComparison() {
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stampWeights, setStampWeights] = useState({});
  const [selectedStamp, setSelectedStamp] = useState('');
  const [stampGrossWeight, setStampGrossWeight] = useState('');
  const [stampComparison, setStampComparison] = useState(null);
  const [verificationHistory, setVerificationHistory] = useState([]);
  const { isAdmin, isManager } = useAuth();

  useEffect(() => {
    fetchComparison();
    fetchStampWeights();
    fetchVerificationHistory();
  }, []);

  const fetchComparison = async () => {
    try {
      const response = await axios.get(`${API}/physical-stock/compare`);
      setComparison(response.data);
    } catch (error) {
      console.error('Error fetching comparison:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStampWeights = async () => {
    try {
      const response = await axios.get(`${API}/inventory/current`);
      // Calculate stamp-wise totals from book stock
      const byStamp = response.data.by_stamp || {};
      const totals = {};
      
      Object.keys(byStamp).forEach(stamp => {
        const items = byStamp[stamp];
        totals[stamp] = {
          gross: items.reduce((sum, item) => sum + item.gr_wt, 0),
          net: items.reduce((sum, item) => sum + item.net_wt, 0),
          itemCount: items.length
        };
      });
      
      setStampWeights(totals);
    } catch (error) {
      console.error('Error fetching stamp weights:', error);
    }
  };

  const handleStampMatch = async () => {
    if (!selectedStamp || !stampGrossWeight) {
      return;
    }

    try {
      // Fetch detailed breakdown for this stamp
      const breakdownRes = await axios.get(`${API}/inventory/stamp-breakdown/${encodeURIComponent(selectedStamp)}`);
      const breakdown = breakdownRes.data;

      const physicalGross = parseFloat(stampGrossWeight) * 1000; // Convert kg to grams
      const bookGross = breakdown.current_gross;
      const bookNet = breakdown.current_net;
      
      const difference = physicalGross - bookGross;
      const matchPercentage = (Math.min(physicalGross, bookGross) / Math.max(physicalGross, bookGross) * 100);

      setStampComparison({
        stamp: selectedStamp,
        physicalGross: physicalGross,
        bookGross: bookGross,
        bookNet: bookNet,
        itemCount: breakdown.item_count + breakdown.mapped_count,
        difference: difference,
        matchPercentage: matchPercentage,
        isMatch: Math.abs(difference) < 100, // Within 100 grams tolerance
        // Breakdown details
        openingGross: breakdown.opening_gross,
        openingNet: breakdown.opening_net,
        purchaseGross: breakdown.purchase_gross,
        purchaseNet: breakdown.purchase_net,
        saleGross: breakdown.sale_gross,
        saleNet: breakdown.sale_net
      });
    } catch (error) {
      toast.error('Failed to fetch stamp breakdown');
    }
  };

  const saveStampVerification = async () => {
    if (!stampComparison) return;

    try {
      await axios.post(`${API}/stamp-verification/save`, {
        stamp: stampComparison.stamp,
        physical_gross_wt: stampComparison.physicalGross,
        book_gross_wt: stampComparison.bookGross,
        difference: stampComparison.difference,
        is_match: stampComparison.isMatch,
        verification_date: new Date().toISOString().split('T')[0]
      });

      toast.success(`${stampComparison.stamp} verification saved!`);
      clearStampMatch();
      fetchVerificationHistory();
    } catch (error) {
      toast.error('Failed to save verification');
    }
  };

  const fetchVerificationHistory = async () => {
    try {
      const res = await axios.get(`${API}/stamp-verification/all`);
      setVerificationHistory(res.data.verifications || []);
    } catch (e) { console.error(e); }
  };

  const deleteVerification = async (stamp, date) => {
    if (!window.confirm(`Cancel verification for ${stamp} on ${date}?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API}/stamp-verification/${encodeURIComponent(stamp)}/${date}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Verification for ${stamp} cancelled`);
      fetchVerificationHistory();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to cancel');
    }
  };

  const clearStampMatch = () => {
    setSelectedStamp('');
    setStampGrossWeight('');
    setStampComparison(null);
  };

  const summary = comparison?.summary;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading comparison...</div>
      </div>
    );
  }

  const handleExportDiscrepancies = () => {
    const exportData = comparison.discrepancies.map(item => ({
      'Item Name': item.item_name,
      'Stamp': item.stamp || 'Unassigned',
      'Book Stock (kg)': (item.book_net_wt / 1000).toFixed(3),
      'Physical Stock (kg)': (item.physical_net_wt / 1000).toFixed(3),
      'Difference (kg)': item.difference_kg,
      'Match %': item.match_percentage
    }));
    exportToCSV(exportData, 'stock_discrepancies');
  };

  const handleExportOnlyBook = () => {
    const exportData = comparison.only_in_book.map(item => ({
      'Item Name': item.item_name,
      'Stamp': item.stamp || 'Unassigned',
      'Book Weight (kg)': item.book_net_wt_kg
    }));
    exportToCSV(exportData, 'items_only_in_book');
  };

  const handleExportOnlyPhysical = () => {
    const exportData = comparison.only_in_physical.map(item => ({
      'Item Name': item.item_name,
      'Stamp': item.stamp || 'Unassigned',
      'Physical Weight (kg)': item.physical_net_wt_kg
    }));
    exportToCSV(exportData, 'items_only_in_physical');
  };

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Physical vs Book Stock
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Compare your physical count with calculated book inventory
        </p>
      </div>

      {/* Quick Stamp Verification - ALWAYS AVAILABLE */}
      <Card className="border-primary/20 shadow-sm bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Weight className="h-5 w-5 text-primary" />
            Quick Stamp Verification
          </CardTitle>
          <CardDescription>
            For busy times - Enter total gross weight for one stamp to verify
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-4 items-end">
            <div>
              <Label className="text-sm font-medium mb-2">Select Stamp</Label>
              <Select value={selectedStamp} onValueChange={setSelectedStamp}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose stamp..." />
                </SelectTrigger>
                <SelectContent className="max-h-60">
                  {Object.keys(stampWeights).sort((a, b) => {
                    // Extract number from "Stamp X" format
                    const numA = parseInt(a.replace(/\D/g, '')) || 0;
                    const numB = parseInt(b.replace(/\D/g, '')) || 0;
                    return numA - numB;
                  }).map(stamp => (
                    <SelectItem key={stamp} value={stamp}>
                      {stamp} ({stampWeights[stamp]?.itemCount || 0} items)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-sm font-medium mb-2">Physical Gross Weight (kg)</Label>
              <Input
                type="number"
                step="0.001"
                placeholder="Enter gross weight"
                value={stampGrossWeight}
                onChange={(e) => setStampGrossWeight(e.target.value)}
              />
            </div>

            <div className="flex gap-2">
              <Button onClick={handleStampMatch} disabled={!selectedStamp || !stampGrossWeight}>
                Match
              </Button>
              <Button onClick={clearStampMatch} variant="outline">
                Clear
              </Button>
            </div>
          </div>

          {/* Stamp Comparison Result */}
          {stampComparison && (
            <div className="mt-6 p-4 rounded-lg border-2 border-primary/20 bg-muted/30">
              <h3 className="font-semibold text-lg mb-3">{stampComparison.stamp} Verification Result</h3>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Book Stock (Calculated)</p>
                  <div className="space-y-1 text-xs bg-muted/30 p-3 rounded">
                    <p className="font-mono">
                      <span className="text-muted-foreground">Opening:</span>{' '}
                      <span className="font-semibold">Gross: {(stampComparison.openingGross / 1000).toFixed(3)} kg, Net: {(stampComparison.openingNet / 1000).toFixed(3)} kg</span>
                    </p>
                    <p className="font-mono text-green-600">
                      <span className="text-muted-foreground">+ Purchase:</span>{' '}
                      <span className="font-semibold">Gross: {(stampComparison.purchaseGross / 1000).toFixed(3)} kg, Net: {(stampComparison.purchaseNet / 1000).toFixed(3)} kg</span>
                    </p>
                    <p className="font-mono text-red-600">
                      <span className="text-muted-foreground">- Sale:</span>{' '}
                      <span className="font-semibold">Gross: {(stampComparison.saleGross / 1000).toFixed(3)} kg, Net: {(stampComparison.saleNet / 1000).toFixed(3)} kg</span>
                    </p>
                    <div className="border-t pt-1 mt-1">
                      <p className="font-mono">
                        <span className="text-muted-foreground">= Current:</span>{' '}
                        <span className="font-bold text-lg text-blue-600">Gross: {(stampComparison.bookGross / 1000).toFixed(3)} kg</span>
                      </p>
                      <p className="font-mono text-sm">
                        <span className="text-muted-foreground ml-11">Net: {(stampComparison.bookNet / 1000).toFixed(3)} kg</span>
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      {stampComparison.itemCount} items (includes mapped items)
                    </p>
                  </div>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground mb-2">Physical vs Book</p>
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Book Gross Stock</p>
                      <p className="font-mono font-bold text-3xl text-blue-600">
                        {(stampComparison.bookGross / 1000).toFixed(3)} kg
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Physical Gross Stock</p>
                      <p className="font-mono font-bold text-2xl">
                        {(stampComparison.physicalGross / 1000).toFixed(3)} kg
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Difference</p>
                      <p className={`font-mono font-bold text-3xl ${stampComparison.difference >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {stampComparison.difference >= 0 ? '+' : ''}{(stampComparison.difference / 1000).toFixed(3)} kg
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t">
                {stampComparison.isMatch ? (
                  <Alert className="border-green-500/50 bg-green-500/10">
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                    <AlertDescription className="ml-2 flex items-center justify-between">
                      <span>
                        <strong>✓ MATCH!</strong> Physical gross weight matches book stock (within 100g tolerance)
                      </span>
                      <Button onClick={saveStampVerification} size="sm" className="ml-4">
                        Save Verification
                      </Button>
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Alert className="border-orange-500/50 bg-orange-500/10">
                    <AlertTriangle className="h-5 w-5 text-orange-600" />
                    <AlertDescription className="ml-2 flex items-center justify-between">
                      <span>
                        <strong>Discrepancy Found:</strong> Gross weight difference of {Math.abs(stampComparison.difference / 1000).toFixed(3)} kg. 
                        {stampComparison.difference > 0 ? ' Physical count is higher than book stock.' : ' Physical count is lower than book stock.'}
                      </span>
                      <Button onClick={saveStampVerification} size="sm" variant="outline" className="ml-4">
                        Save Verification
                      </Button>
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info message if no physical stock data */}
      {!summary && (
        <Alert className="border-blue-500/50 bg-blue-500/10">
          <AlertTriangle className="h-5 w-5 text-blue-600" />
          <AlertDescription className="ml-2">
            <strong>Item-wise Comparison:</strong> Upload a physical stock file (via Upload Files → Physical Stock) to see detailed item-by-item comparison. Or use Quick Stamp Verification above for fast checks.
          </AlertDescription>
        </Alert>
      )}

      {/* Summary Cards - Only show for Admin */}
      {summary && isAdmin && (
        <>
          <div className="grid gap-6 md:grid-cols-4">
            <Card className="border-border/40 shadow-sm bg-gradient-to-br from-blue-500/10 to-transparent">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">Book Stock</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Gross:</p>
                  <div className="text-2xl font-bold font-mono text-blue-600">
                    {summary.total_book_gross_kg?.toLocaleString() || '0'} kg
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">Net:</p>
                  <div className="text-lg font-semibold font-mono text-blue-500">
                    {summary.total_book_kg?.toLocaleString() || '0'} kg
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/40 shadow-sm bg-gradient-to-br from-green-500/10 to-transparent">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">Physical Stock</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Gross:</p>
                  <div className="text-2xl font-bold font-mono text-green-600">
                    {summary.total_physical_gross_kg?.toLocaleString() || '0'} kg
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">Net:</p>
                  <div className="text-lg font-semibold font-mono text-green-500">
                    {summary.total_physical_kg?.toLocaleString() || '0'} kg
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/40 shadow-sm bg-gradient-to-br from-orange-500/10 to-transparent">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">Difference</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Gross Diff:</p>
                  <div className={`text-2xl font-bold font-mono ${(summary.total_difference_gross_kg || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {(summary.total_difference_gross_kg || 0) >= 0 ? '+' : ''}{(summary.total_difference_gross_kg || 0).toLocaleString()} kg
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">Net Diff:</p>
                  <div className={`text-lg font-semibold font-mono ${(summary.total_difference_kg || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {(summary.total_difference_kg || 0) >= 0 ? '+' : ''}{(summary.total_difference_kg || 0).toLocaleString()} kg
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/40 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">Accuracy</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold font-mono text-primary">
                  {summary.match_count}/{summary.match_count + summary.discrepancy_count}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Items matched</p>
              </CardContent>
            </Card>
          </div>

          {/* Tabs for different categories */}
          <Tabs defaultValue="discrepancies" className="space-y-6">
        <TabsList>
          <TabsTrigger value="discrepancies">
            <AlertTriangle className="h-4 w-4 mr-2" />
            Discrepancies ({summary.discrepancy_count})
          </TabsTrigger>
          <TabsTrigger value="matches">
            <CheckCircle2 className="h-4 w-4 mr-2" />
            Matches ({summary.match_count})
          </TabsTrigger>
          <TabsTrigger value="only-book">
            <XCircle className="h-4 w-4 mr-2" />
            Only in Book ({summary.only_in_book_count})
          </TabsTrigger>
          <TabsTrigger value="only-physical">
            <XCircle className="h-4 w-4 mr-2" />
            Only in Physical ({summary.only_in_physical_count})
          </TabsTrigger>
        </TabsList>

        {/* Discrepancies */}
        <TabsContent value="discrepancies">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Items with Discrepancies</CardTitle>
                  <CardDescription>Items where physical count differs from book stock</CardDescription>
                </div>
                <Button onClick={handleExportDiscrepancies} variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item Name</TableHead>
                    <TableHead>Stamp</TableHead>
                    <TableHead className="text-right font-mono">Book (kg)</TableHead>
                    <TableHead className="text-right font-mono">Physical (kg)</TableHead>
                    <TableHead className="text-right font-mono">Difference (kg)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comparison.discrepancies.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        No discrepancies found! All items match.
                      </TableCell>
                    </TableRow>
                  ) : (
                    comparison.discrepancies.map((item, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{item.item_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.stamp || 'Unassigned'}</Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {(item.book_net_wt / 1000).toFixed(3)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {(item.physical_net_wt / 1000).toFixed(3)}
                        </TableCell>
                        <TableCell className={`text-right font-mono font-semibold ${item.difference >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {item.difference >= 0 ? '+' : ''}{item.difference_kg}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Matches */}
        <TabsContent value="matches">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <CardTitle>Matching Items</CardTitle>
              <CardDescription>Items where physical count matches book stock (within 10g tolerance)</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item Name</TableHead>
                    <TableHead>Stamp</TableHead>
                    <TableHead className="text-right font-mono">Weight (kg)</TableHead>
                    <TableHead className="text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comparison.matches.slice(0, 50).map((item, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-medium">{item.item_name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{item.stamp || 'Unassigned'}</Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {(item.book_net_wt / 1000).toFixed(3)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge className="bg-green-600">
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Match
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Only in Book */}
        <TabsContent value="only-book">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Only in Book Stock</CardTitle>
                  <CardDescription>
                    Items present in calculated book stock but missing from physical count. 
                    This is normal if you&apos;re doing partial physical verification.
                  </CardDescription>
                </div>
                <Button onClick={handleExportOnlyBook} variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item Name</TableHead>
                    <TableHead>Stamp</TableHead>
                    <TableHead className="text-right font-mono">Book Weight (kg)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comparison.only_in_book.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                        All book items are present in physical stock
                      </TableCell>
                    </TableRow>
                  ) : (
                    comparison.only_in_book.map((item, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{item.item_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.stamp || 'Unassigned'}</Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono text-orange-600 font-semibold">
                          {item.book_net_wt_kg}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Only in Physical */}
        <TabsContent value="only-physical">
          <Card className="border-border/40 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Only in Physical Stock</CardTitle>
                  <CardDescription>Items found in physical count but not in book stock</CardDescription>
                </div>
                <Button onClick={handleExportOnlyPhysical} variant="outline" size="sm">
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item Name</TableHead>
                    <TableHead>Stamp</TableHead>
                    <TableHead className="text-right font-mono">Physical Weight (kg)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comparison.only_in_physical.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                        All physical items are accounted for in book stock
                      </TableCell>
                    </TableRow>
                  ) : (
                    comparison.only_in_physical.map((item, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{item.item_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{item.stamp || 'Unassigned'}</Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono text-blue-600 font-semibold">
                          {item.physical_net_wt_kg}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
        </>
      )}

      {/* Info message when no physical stock data */}
      {!summary && (
        <Alert>
          <AlertTriangle className="h-5 w-5" />
          <AlertDescription>
            No physical stock comparison data available yet. Upload a physical stock file to see detailed comparisons, or use Quick Stamp Verification above for quick checks.
          </AlertDescription>
        </Alert>
      )}

      {/* Saved Verifications History */}
      {verificationHistory.length > 0 && (
        <Card className="border-border/40" data-testid="verification-history">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              Saved Verifications
            </CardTitle>
            <CardDescription>Stamp verifications saved from this page. Admin/Manager can cancel if done by mistake.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stamp</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Book Gross</TableHead>
                    <TableHead className="text-right">Physical Gross</TableHead>
                    <TableHead className="text-right">Difference</TableHead>
                    <TableHead>Status</TableHead>
                    {(isAdmin || isManager) && <TableHead className="text-right">Action</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {verificationHistory.map((v, idx) => (
                    <TableRow key={idx} data-testid={`verif-row-${idx}`}>
                      <TableCell className="font-medium">{v.stamp}</TableCell>
                      <TableCell className="text-sm">{v.verification_date}</TableCell>
                      <TableCell className="text-right font-mono text-sm">{(v.book_gross_wt / 1000).toFixed(3)} kg</TableCell>
                      <TableCell className="text-right font-mono text-sm">{(v.physical_gross_wt / 1000).toFixed(3)} kg</TableCell>
                      <TableCell className={`text-right font-mono text-sm font-semibold ${v.is_match ? 'text-green-600' : 'text-red-600'}`}>
                        {v.difference_kg} kg
                      </TableCell>
                      <TableCell>
                        <Badge className={v.is_match ? 'bg-green-600' : 'bg-red-600'}>
                          {v.is_match ? 'Matched' : 'Mismatch'}
                        </Badge>
                      </TableCell>
                      {(isAdmin || isManager) && (
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => deleteVerification(v.stamp, v.verification_date)}
                            data-testid={`verif-cancel-${idx}`} className="text-destructive hover:text-destructive">
                            Cancel
                          </Button>
                        </TableCell>
                      )}
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
