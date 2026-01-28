import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { CheckSquare, XSquare, Clock, Users } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ManagerApprovals() {
  const [pendingEntries, setPendingEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const { isManager, isAdmin } = useAuth();

  useEffect(() => {
    if (isManager || isAdmin) {
      fetchPendingApprovals();
    }
  }, [isManager, isAdmin]);

  const fetchPendingApprovals = async () => {
    try {
      const response = await axios.get(`${API}/manager/pending-approvals`);
      setPendingEntries(response.data);
    } catch (error) {
      console.error('Error fetching approvals:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleApproval = async (stamp, approve) => {
    try {
      await axios.post(`${API}/manager/approve-stamp`, null, {
        params: { stamp, approve }
      });
      
      toast.success(`${stamp} ${approve ? 'approved' : 'rejected'}!`);
      fetchPendingApprovals();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Action failed');
    }
  };

  if (!isManager && !isAdmin) {
    return (
      <div className="p-6 md:p-8">
        <Alert variant="destructive">
          <AlertDescription>Access Denied. Manager or Admin privileges required.</AlertDescription>
        </Alert>
      </div>
    );
  }

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

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading...</div>
        </div>
      ) : pendingEntries.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Clock className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">No Pending Approvals</h3>
            <p className="text-muted-foreground">All stock entries have been processed</p>
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
                      Submitted by {entry.entered_by} on {new Date(entry.entry_date).toLocaleString()}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => handleApproval(entry.stamp, true)}
                      variant="default"
                      size="sm"
                    >
                      <CheckSquare className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      onClick={() => handleApproval(entry.stamp, false)}
                      variant="destructive"
                      size="sm"
                    >
                      <XSquare className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-3">
                  {entry.entries?.length || 0} items entered
                </p>
                <div className="max-h-48 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Item Name</TableHead>
                        <TableHead className="text-right">Gross (kg)</TableHead>
                        <TableHead className="text-right">Net (kg)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {entry.entries?.slice(0, 10).map((item, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-medium text-sm">{item.item_name}</TableCell>
                          <TableCell className="text-right font-mono">{item.gross_wt?.toFixed(3) || '0.000'}</TableCell>
                          <TableCell className="text-right font-mono">{item.net_wt?.toFixed(3) || '0.000'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
