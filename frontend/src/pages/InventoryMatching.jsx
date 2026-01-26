import { useEffect, useState } from 'react';
import axios from 'axios';
import { GitCompare, AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function InventoryMatching() {
  const [matchResult, setMatchResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [assigningStamp, setAssigningStamp] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [newStamp, setNewStamp] = useState('');

  const performMatch = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/inventory/match`);
      setMatchResult(response.data);
      toast.success(response.data.message);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Matching failed');
    } finally {
      setLoading(false);
    }
  };

  const assignStamp = async () => {
    if (!selectedItem || !newStamp) return;

    setAssigningStamp(true);
    try {
      await axios.post(`${API}/inventory/assign-stamp`, {
        item_name: selectedItem.item_name,
        stamp: newStamp,
      });
      toast.success(`Stamp assigned successfully`);
      setSelectedItem(null);
      setNewStamp('');
      performMatch(); // Refresh match results
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Assignment failed');
    } finally {
      setAssigningStamp(false);
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="matching-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight" data-testid="matching-title">
            Inventory Matching
          </h1>
          <p className="text-lg text-muted-foreground mt-2">
            Compare book inventory with physical stock
          </p>
        </div>
        <Button
          onClick={performMatch}
          disabled={loading}
          size="lg"
          className="shadow-md"
          data-testid="match-button"
        >
          <GitCompare className="mr-2 h-5 w-5" />
          {loading ? 'Matching...' : 'Run Match'}
        </Button>
      </div>

      {matchResult && (
        <>
          {/* Match Status */}
          <Card
            className={`border-2 ${
              matchResult.complete_match
                ? 'border-emerald-200 bg-emerald-50'
                : 'border-amber-200 bg-amber-50'
            }`}
            data-testid="match-status-card"
          >
            <CardContent className="flex items-center gap-4 p-6">
              {matchResult.complete_match ? (
                <CheckCircle2 className="h-12 w-12 text-emerald-600" />
              ) : (
                <AlertTriangle className="h-12 w-12 text-amber-600" />
              )}
              <div>
                <h3 className="text-xl font-bold">
                  {matchResult.complete_match ? 'Complete Match!' : 'Discrepancies Found'}
                </h3>
                <p className="text-sm mt-1">
                  {matchResult.complete_match
                    ? 'All items match perfectly between book and physical inventory.'
                    : `${matchResult.differences.length} differences and ${matchResult.unmatched_items.length} unmatched items detected.`}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Differences Table */}
          {matchResult.differences.length > 0 && (
            <Card className="border-border/40 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  Weight Differences
                </CardTitle>
                <CardDescription>
                  Items with mismatched weights between book and physical inventory
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Item Name</TableHead>
                        <TableHead>Stamp</TableHead>
                        <TableHead className="text-right font-mono">Book Gr.Wt</TableHead>
                        <TableHead className="text-center"></TableHead>
                        <TableHead className="text-right font-mono">Physical Gr.Wt</TableHead>
                        <TableHead className="text-right font-mono">Difference</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {matchResult.differences.map((diff, idx) => (
                        <TableRow key={idx} className="table-row" data-testid={`difference-row-${idx}`}>
                          <TableCell className="font-medium">{diff.item_name}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="font-mono text-xs">
                              {diff.stamp}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono">{diff.book_gr_wt.toFixed(2)}g</TableCell>
                          <TableCell className="text-center">
                            <ArrowRight className="h-4 w-4 text-muted-foreground mx-auto" />
                          </TableCell>
                          <TableCell className="text-right font-mono">{diff.physical_gr_wt.toFixed(2)}g</TableCell>
                          <TableCell className="text-right font-mono">
                            <span className={diff.gr_wt_diff > 0 ? 'text-emerald-600' : 'text-red-600'}>
                              {diff.gr_wt_diff > 0 ? '+' : ''}{diff.gr_wt_diff.toFixed(2)}g
                            </span>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Unmatched Items */}
          {matchResult.unmatched_items.length > 0 && (
            <Card className="border-border/40 shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  Unmatched Items
                </CardTitle>
                <CardDescription>
                  Items in physical inventory without a stamp or not found in book inventory
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Item Name</TableHead>
                        <TableHead>Current Stamp</TableHead>
                        <TableHead className="text-right font-mono">Gross Wt (g)</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {matchResult.unmatched_items.map((item, idx) => (
                        <TableRow key={idx} className="table-row" data-testid={`unmatched-row-${idx}`}>
                          <TableCell className="font-medium">{item.item_name}</TableCell>
                          <TableCell>
                            <Badge variant="secondary" className="font-mono text-xs">
                              {item.stamp || 'None'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono">{item.gr_wt.toFixed(2)}</TableCell>
                          <TableCell className="text-right">
                            <Dialog>
                              <DialogTrigger asChild>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setSelectedItem(item)}
                                  data-testid={`assign-stamp-button-${idx}`}
                                >
                                  Assign Stamp
                                </Button>
                              </DialogTrigger>
                              <DialogContent>
                                <DialogHeader>
                                  <DialogTitle>Assign Stamp</DialogTitle>
                                  <DialogDescription>
                                    Assign a stamp category to {selectedItem?.item_name}
                                  </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 mt-4">
                                  <div>
                                    <Label htmlFor="stamp">Stamp Name</Label>
                                    <Input
                                      id="stamp"
                                      placeholder="Enter stamp name"
                                      value={newStamp}
                                      onChange={(e) => setNewStamp(e.target.value)}
                                      data-testid="stamp-input"
                                    />
                                  </div>
                                  <Button
                                    onClick={assignStamp}
                                    disabled={assigningStamp || !newStamp}
                                    className="w-full"
                                    data-testid="confirm-assign-button"
                                  >
                                    {assigningStamp ? 'Assigning...' : 'Confirm Assignment'}
                                  </Button>
                                </div>
                              </DialogContent>
                            </Dialog>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {!matchResult && (
        <Card className="border-border/40 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <GitCompare className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">Ready to Match</h3>
            <p className="text-muted-foreground mb-6">
              Click "Run Match" to compare your book inventory with physical stock
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}