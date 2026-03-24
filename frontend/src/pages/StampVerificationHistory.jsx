import { useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function StampVerificationHistory() {
  const [stamps, setStamps] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStampHistory();
  }, []);

  const fetchStampHistory = async () => {
    try {
      const response = await axios.get(`${API}/stamp-verification/history`);
      setStamps(response.data);
    } catch (error) {
      console.error('Failed to fetch:', error);
    } finally {
      setLoading(false);
    }
  };

  const getDaysSinceVerification = (lastDate) => {
    if (!lastDate) return 999;
    const last = new Date(lastDate);
    const now = new Date();
    return Math.floor((now - last) / (1000 * 60 * 60 * 24));
  };

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          Stamp Verification History
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          Track when each stamp was last verified with physical stock
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Stamps Verification Status</CardTitle>
          <CardDescription>Red stamps need verification (>15 days)</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead>Stamp</TableHead>
                <TableHead>Last Verified</TableHead>
                <TableHead>Days Ago</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Verified By</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stamps.map((stamp, idx) => {
                const daysAgo = getDaysSinceVerification(stamp.last_verified_date);
                const isOverdue = daysAgo > 15;
                
                return (
                  <TableRow key={idx} className={isOverdue ? 'bg-red-50' : ''}>
                    <TableCell className="font-bold">{stamp.stamp}</TableCell>
                    <TableCell className="text-sm">
                      {stamp.last_verified_date ? new Date(stamp.last_verified_date).toLocaleDateString() : 'Never'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={isOverdue ? 'destructive' : 'outline'}>
                        {daysAgo === 999 ? 'Never' : `${daysAgo} days`}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {isOverdue ? (
                        <Badge className="bg-red-600">
                          <AlertTriangle className="h-3 w-3 mr-1" />
                          Overdue
                        </Badge>
                      ) : (
                        <Badge className="bg-green-600">
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          OK
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {stamp.verified_by || '-'}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
