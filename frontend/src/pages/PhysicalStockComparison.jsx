import { useEffect, useState } from 'react';
import axios from 'axios';
import { Scale, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function PhysicalStockComparison() {
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchComparison();
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading comparison...</div>
      </div>
    );
  }

  if (!comparison || !comparison.summary) {
    return (
      <div className="p-6 md:p-8">
        <Alert>
          <AlertTriangle className="h-5 w-5" />
          <AlertDescription>
            No physical stock data found. Please upload your physical stock file first.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const summary = comparison.summary;

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

      {/* Summary Cards */}
      <div className="grid gap-6 md:grid-cols-4">
        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-blue-500/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Book Stock</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-blue-600">
              {summary.total_book_kg.toLocaleString()} kg
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-green-500/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Physical Stock</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold font-mono text-green-600">
              {summary.total_physical_kg.toLocaleString()} kg
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-orange-500/10 to-transparent">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Difference</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-bold font-mono ${summary.total_difference_kg >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {summary.total_difference_kg >= 0 ? '+' : ''}{summary.total_difference_kg.toLocaleString()} kg
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
              <CardTitle>Items with Discrepancies</CardTitle>
              <CardDescription>Items where physical count differs from book stock</CardDescription>
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
              <CardTitle>Only in Book Stock</CardTitle>
              <CardDescription>Items present in book but missing from physical count</CardDescription>
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
              <CardTitle>Only in Physical Stock</CardTitle>
              <CardDescription>Items found in physical count but not in book stock</CardDescription>
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
    </div>
  );
}
