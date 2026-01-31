import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { CheckSquare, XSquare, Clock, Download } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { exportToCSV } from '@/utils/exportCSV';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ManagerApprovals() {
  const [allEntries, setAllEntries] = useState([]);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [approvalDetails, setApprovalDetails] = useState(null);
  const [allDetails, setAllDetails] = useState({}); // Store details for all entries
  const [loading, setLoading] = useState(true);
  const { isManager, isAdmin } = useAuth();

  useEffect(() => {
    if (isManager || isAdmin) {
      fetchAllEntries();
    }
  }, [isManager, isAdmin]);

  const fetchAllEntries = async () => {
    try {
      const response = await axios.get(`${API}/manager/all-entries`);
      setAllEntries(response.data);
      
      // Fetch details for all pending entries to show diff badges
      const pending = response.data.filter(e => e.status === 'pending');
      for (const entry of pending) {
        fetchDetailsForBadge(entry.stamp);
      }
    } catch (error) {
      console.error('Error fetching entries:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchDetailsForBadge = async (stamp) => {
    try {
      const response = await axios.get(`${API}/manager/approval-details/${stamp}`);
      setAllDetails(prev => ({...prev, [stamp]: response.data}));
    } catch (error) {
      console.error('Failed to load details:', error);
    }
  };

  const fetchApprovalDetails = async (stamp) => {
    try {
      const response = await axios.get(`${API}/manager/approval-details/${stamp}`);
      setApprovalDetails(response.data);
      setSelectedEntry(stamp);
    } catch (error) {
      toast.error('Failed to load details');
    }
  };

  const exportStampDifferences = async (stamp) => {
    try {
      const response = await axios.get(`${API}/manager/approval-details/${stamp}`);
      
      // Export ALL items, not just differences
      const exportData = response.data.comparison.map(item => ({
        'Item Name': item.item_name,
        'Book Gross (kg)': (item.book_gross || 0).toFixed(3),
        'Entered Gross (kg)': (item.entered_gross || 0).toFixed(3),
        'Difference (kg)': (item.difference || 0).toFixed(3)
      }));
      
      exportToCSV(exportData, `${stamp}_complete_comparison`);
      toast.success('Stamp comparison exported!');
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export - ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleApproval = async (stamp, approve) => {
    // Ensure we have details loaded
    if (!allDetails[stamp]) {
      await fetchDetailsForBadge(stamp);
    }


  const exportStampDifferences = async (stamp) => {
    try {
      const response = await axios.get(`${API}/manager/approval-details/${stamp}`);
      const differences = response.data.comparison.filter(item => Math.abs(item.difference || 0) > 0.001);
      
      const exportData = differences.map(item => ({
        'Item Name': item.item_name,
        'Book Gross (kg)': (item.book_gross || 0).toFixed(3),
        'Entered Gross (kg)': (item.entered_gross || 0).toFixed(3),
        'Difference (kg)': (item.difference || 0).toFixed(3)
      }));
      
      exportToCSV(exportData, `${stamp}_differences`);
      toast.success('Differences exported!');
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export');
    }
  };

    
    const details = allDetails[stamp];
    const totalDiff = details?.total_difference ? details.total_difference * 1000 : 0; // Convert kg to grams
    
    try {
      await axios.post(`${API}/manager/approve-stamp`, {
        stamp: stamp,
        approve: approve,
        total_difference: totalDiff
      });
      
      toast.success(`${stamp} ${approve ? 'approved' : 'rejected'}!`);
      setSelectedEntry(null);
      setApprovalDetails(null);
      fetchAllEntries();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Action failed');
    }
  };

  if (!isManager && !isAdmin) {
    return (
      <div className="p-6 md:p-8">
        <Alert variant="destructive">
          <AlertDescription>Access Denied. Manager privileges required.</AlertDescription>
        </Alert>
      </div>
    );
  }

  const pendingEntries = allEntries.filter(e => e.status === 'pending');
  const approvedEntries = allEntries.filter(e => e.status === 'approved');
  const rejectedEntries = allEntries.filter(e => e.status === 'rejected');

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Stamp Approvals
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Review and approve stock entries from executives
        </p>
      </div>

      <Tabs defaultValue="pending" className="space-y-6">
        <TabsList>
          <TabsTrigger value="pending">Pending ({pendingEntries.length})</TabsTrigger>
          <TabsTrigger value="approved">Approved ({approvedEntries.length})</TabsTrigger>
          <TabsTrigger value="rejected">Rejected ({rejectedEntries.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="pending">
          {pendingEntries.length === 0 ? (
            <Card>
              <CardContent className="py-16 text-center">
                <Clock className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No pending approvals</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {pendingEntries.map((entry, idx) => (
                <Card key={idx} className="border-orange-500/20">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {entry.stamp}
                          <Badge variant="outline" className="text-orange-600">Pending</Badge>
                          {allDetails[entry.stamp] && (
                            <Badge className={Math.abs(allDetails[entry.stamp].total_difference) < 0.05 ? 'bg-green-600' : 'bg-red-600'}>
                              Diff: {allDetails[entry.stamp].total_difference >= 0 ? '+' : ''}{allDetails[entry.stamp].total_difference?.toFixed(3)} kg
                            </Badge>
                          )}
                        </CardTitle>
                        <CardDescription>
                          By {entry.entered_by} on {new Date(entry.entry_date).toLocaleString()}
                          {entry.iteration > 1 && <span className="ml-2 text-orange-600">• Iteration {entry.iteration}</span>}
                        </CardDescription>
                      </div>
                      <div className="flex gap-2">
                        <Button onClick={() => fetchApprovalDetails(entry.stamp)} variant="outline" size="sm">
                          View Details
                        </Button>
                        <Button onClick={() => handleApproval(entry.stamp, true)} size="sm">
                          <CheckSquare className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <Button onClick={() => handleApproval(entry.stamp, false)} variant="destructive" size="sm">
                          <XSquare className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  
                  {selectedEntry === entry.stamp && approvalDetails && (
                    <CardContent>
                      <div className="bg-muted/30 p-4 rounded-lg">
                        <p className="font-semibold mb-3">Book vs Entered Comparison</p>
                        <div className="max-h-64 overflow-y-auto">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Item Name</TableHead>
                                <TableHead className="text-right">Book Gross (kg)</TableHead>
                                <TableHead className="text-right">Entered Gross (kg)</TableHead>
                                <TableHead className="text-right">Difference</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {approvalDetails.comparison?.map((item, i) => (
                                <TableRow key={i}>
                                  <TableCell className="font-medium text-sm">{item.item_name}</TableCell>
                                  <TableCell className="text-right font-mono">{item.book_gross?.toFixed(3)}</TableCell>
                                  <TableCell className="text-right font-mono">{item.entered_gross?.toFixed(3)}</TableCell>
                                  <TableCell className={`text-right font-mono font-semibold ${
                                    Math.abs(item.difference) < 0.05 ? 'text-green-600' : 'text-orange-600'
                                  }`}>
                                    {item.difference >= 0 ? '+' : ''}{item.difference?.toFixed(3)}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                          
                          {/* Totals Summary */}
                          <div className="mt-4 p-4 bg-primary/5 rounded-lg border-2 border-primary/20">
                            <div className="grid grid-cols-3 gap-4 text-center">
                              <div>
                                <p className="text-xs text-muted-foreground">Total Book</p>
                                <p className="font-mono font-bold text-lg">{approvalDetails?.total_book?.toFixed(3)} kg</p>
                              </div>
                              <div>
                                <p className="text-xs text-muted-foreground">Total Entered</p>
                                <p className="font-mono font-bold text-lg">{approvalDetails?.total_entered?.toFixed(3)} kg</p>
                              </div>
                              <div>
                                <p className="text-xs text-muted-foreground">Total Difference</p>
                                <p className={`font-mono font-bold text-xl ${
                                  Math.abs(approvalDetails?.total_difference || 0) < 0.05 ? 'text-green-600' : 'text-red-600'
                                }`}>
                                  {(approvalDetails?.total_difference || 0) >= 0 ? '+' : ''}{(approvalDetails?.total_difference || 0).toFixed(3)} kg
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  )}
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="approved">
          <div className="space-y-3">
            {approvedEntries.map((entry, idx) => (
              <Card key={idx} className="border-green-500/20">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <CardTitle>{entry.stamp}</CardTitle>
                      <CardDescription>
                        By {entry.entered_by} • Approved by {entry.approved_by} on {new Date(entry.approved_at).toLocaleString()}
                        {entry.iteration > 1 && <span className="ml-2">• {entry.iteration} iterations</span>}
                      </CardDescription>
                      <div className="mt-3 flex gap-2">
                        <Badge className="bg-green-600">APPROVED</Badge>
                        <Button onClick={() => fetchApprovalDetails(entry.stamp)} variant="outline" size="sm">
                          View Details
                        </Button>
                        <Button onClick={() => exportStampDifferences(entry.stamp)} variant="outline" size="sm">
                          <Download className="h-4 w-4 mr-1" />
                          Export All
                        </Button>
                        <Button onClick={() => handleApproval(entry.stamp, false)} variant="destructive" size="sm">
                          <XSquare className="h-4 w-4 mr-1" />
                          Reject Again
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                
                {selectedEntry === entry.stamp && approvalDetails && (
                  <CardContent>
                    <div className="bg-muted/30 p-4 rounded-lg">
                      <p className="font-semibold mb-3">Book vs Entered Comparison (Approved)</p>
                      <div className="max-h-64 overflow-y-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Item Name</TableHead>
                              <TableHead className="text-right">Book Gross (kg)</TableHead>
                              <TableHead className="text-right">Entered Gross (kg)</TableHead>
                              <TableHead className="text-right">Difference</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {approvalDetails.comparison?.map((item, i) => (
                              <TableRow key={i} className={item.was_entered ? '' : 'opacity-40'}>
                                <TableCell className="font-medium text-sm">{item.item_name}</TableCell>
                                <TableCell className="text-right font-mono">{(item.book_gross || 0).toFixed(3)}</TableCell>
                                <TableCell className="text-right font-mono">{(item.entered_gross || 0).toFixed(3)}</TableCell>
                                <TableCell className={`text-right font-mono font-semibold ${
                                  Math.abs(item.difference || 0) < 0.05 ? 'text-green-600' : 'text-orange-600'
                                }`}>
                                  {(item.difference || 0) >= 0 ? '+' : ''}{(item.difference || 0).toFixed(3)}
                                </TableCell>
                              </TableRow>
                            ))}
                            
                            {/* Totals */}
                            <TableRow className="bg-primary/10 border-t-2">
                              <TableCell className="font-bold">TOTAL</TableCell>
                              <TableCell className="text-right font-mono font-bold">
                                {(approvalDetails?.total_book || 0).toFixed(3)} kg
                              </TableCell>
                              <TableCell className="text-right font-mono font-bold">
                                {(approvalDetails?.total_entered || 0).toFixed(3)} kg
                              </TableCell>
                              <TableCell className={`text-right font-mono font-bold text-lg ${
                                Math.abs(approvalDetails?.total_difference || 0) < 0.05 ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {((approvalDetails?.total_difference || 0) >= 0 ? '+' : '') + (approvalDetails?.total_difference || 0).toFixed(3)} kg
                              </TableCell>
                            </TableRow>
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="rejected">
          <div className="space-y-3">
            {rejectedEntries.map((entry, idx) => (
              <Card key={idx} className="border-red-500/20">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>{entry.stamp}</CardTitle>
                      <CardDescription>
                        By {entry.entered_by} • Rejected by {entry.approved_by || 'Manager'}
                      </CardDescription>
                    </div>
                    <Badge className="bg-red-600">REJECTED</Badge>
                  </div>
                </CardHeader>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
