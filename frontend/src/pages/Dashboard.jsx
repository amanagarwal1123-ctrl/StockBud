import { useEffect, useState } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertTriangle, CheckCircle2, Clock, Globe } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [stampHistory, setStampHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    fetchStampHistory();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStampHistory = async () => {
    try {
      const response = await axios.get(`${API}/stamp-verification/history`);
      setStampHistory(response.data);
    } catch (error) {
      console.error('Error fetching stamp history:', error);
    }
  };

  const getDaysSinceVerification = (lastDate) => {
    if (!lastDate) return 999;
    const last = new Date(lastDate);
    const now = new Date();
    return Math.floor((now - last) / (1000 * 60 * 60 * 24));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Transactions',
      value: stats?.total_transactions || 0,
      icon: Package,
      color: 'text-primary',
      bgColor: 'bg-primary/10',
    },
    {
      title: 'Total Parties',
      value: stats?.total_parties || 0,
      icon: TrendingUp,
      color: 'text-accent',
      bgColor: 'bg-accent/10',
    },
    {
      title: 'Purchases',
      value: stats?.total_purchases || 0,
      icon: TrendingUp,
      color: 'text-secondary',
      bgColor: 'bg-secondary/10',
    },
    {
      title: 'Sales',
      value: stats?.total_sales || 0,
      icon: TrendingUp,
      color: 'text-accent',
      bgColor: 'bg-accent/10',
    },
  ];

  return (
    <div className="p-6 md:p-8 space-y-6" data-testid="dashboard-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight" data-testid="dashboard-title">
          Dashboard
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          StockBud - Intelligent inventory management for your jewelry business
        </p>
      </div>

      {/* Latest Match Alert */}
      {stats?.latest_match && (
        <Alert
          data-testid="latest-match-alert"
          className={`${
            stats.latest_match.complete_match
              ? 'border-accent/30 bg-accent/10'
              : 'border-secondary/30 bg-secondary/10'
          }`}
        >
          {stats.latest_match.complete_match ? (
            <CheckCircle2 className="h-5 w-5 text-accent" />
          ) : (
            <AlertTriangle className="h-5 w-5 text-secondary" />
          )}
          <AlertDescription className="ml-2">
            {stats.latest_match.complete_match
              ? '🎉 Complete stock match achieved!'
              : `Last match found ${stats.latest_match.differences?.length || 0} differences and ${stats.latest_match.unmatched_items?.length || 0} unmatched items`}
          </AlertDescription>
        </Alert>
      )}

      {/* Stats Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <Card
            key={stat.title}
            className="stat-card relative overflow-hidden border-border/40 shadow-sm hover:shadow-md transition-shadow"
            data-testid={`stat-card-${stat.title.toLowerCase().replace(' ', '-')}`}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <div className={`stat-card-icon p-2 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`h-5 w-5 ${stat.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold font-mono">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Stamp Verification Status */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            Stamp Verification Status
          </CardTitle>
          <CardDescription>Last physical verification for each stamp</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto max-h-96">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Stamp</TableHead>
                  <TableHead>Last Verified</TableHead>
                  <TableHead>Days Ago</TableHead>
                  <TableHead className="text-right">Difference</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stampHistory.map((stamp, idx) => {
                  const daysAgo = getDaysSinceVerification(stamp.last_verified_date);
                  const isOverdue = daysAgo > 15;
                  
                  return (
                    <TableRow key={idx} className={isOverdue ? 'bg-red-50 border-l-4 border-red-500' : ''}>
                      <TableCell className="font-bold">{stamp.stamp}</TableCell>
                      <TableCell className="text-sm">
                        {stamp.last_verified_date ? new Date(stamp.last_verified_date).toLocaleDateString() : 'Never'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={isOverdue ? 'destructive' : 'outline'}>
                          {daysAgo === 999 ? 'Never' : `${daysAgo} days`}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {stamp.difference ? `${stamp.difference >= 0 ? '+' : ''}${stamp.difference.toFixed(3)} kg` : '-'}
                      </TableCell>
                      <TableCell>
                        {isOverdue ? (
                          <Badge className="bg-red-600">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Needs Verification
                          </Badge>
                        ) : stamp.is_match ? (
                          <Badge className="bg-green-600">
                            <CheckCircle2 className="h-3 w-3 mr-1" />
                            Matched
                          </Badge>
                        ) : (
                          <Badge variant="outline">Unknown</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Getting Started</CardTitle>
            <CardDescription>Begin managing your inventory with StockBud</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-start gap-2">
              <div className="h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                1
              </div>
              <p className="text-muted-foreground">Upload opening stock (current inventory)</p>
            </div>
            <div className="flex items-start gap-2">
              <div className="h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                2
              </div>
              <p className="text-muted-foreground">Upload purchase and sale ledgers</p>
            </div>
            <div className="flex items-start gap-2">
              <div className="h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                3
              </div>
              <p className="text-muted-foreground">View party analytics and profit analysis</p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Key Features</CardTitle>
            <CardDescription>What StockBud can do for you</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>• Intelligent stock calculation with negative stock detection</p>
            <p>• Party-wise analytics (customers & suppliers)</p>
            <p>• Comprehensive profit analysis with margins</p>
            <p>• Undo/Redo functionality for safe operations</p>
            <p>• Automatic item name merging with stamp priority</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-primary/5 via-secondary/5 to-accent/5">
          <CardHeader>
            <CardTitle className="text-xl">Pro Tip</CardTitle>
            <CardDescription>Maximize your efficiency</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>
              Upload files regularly to maintain accurate records. StockBud automatically resolves
              naming conflicts and identifies negative stock items that need attention.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}