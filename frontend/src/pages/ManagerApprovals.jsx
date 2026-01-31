import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { CheckSquare, XSquare, Clock } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ManagerApprovals() {
  const [allEntries, setAllEntries] = useState([]);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [approvalDetails, setApprovalDetails] = useState(null);
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
    } catch (error) {
      console.error('Error fetching entries:', error);
    } finally {
      setLoading(false);
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

  const handleApproval = async (stamp, approve) => {
    const totalDiff = approvalDetails?.comparison?.reduce((sum, item) => sum + Math.abs(item.difference * 1000), 0) || 0;
    
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
                    <div>
                      <CardTitle>{entry.stamp}</CardTitle>
                      <CardDescription>
                        By {entry.entered_by} • Approved by {entry.approved_by} on {new Date(entry.approved_at).toLocaleString()}
                      </CardDescription>
                    </div>
                    <Badge className="bg-green-600">APPROVED</Badge>
                  </div>
                </CardHeader>
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
