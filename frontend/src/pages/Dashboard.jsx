import { useEffect, useState } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
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
        >\n          {stats.latest_match.complete_match ? (
            <CheckCircle2 className=\"h-5 w-5 text-accent\" />\n          ) : (\n            <AlertTriangle className=\"h-5 w-5 text-secondary\" />\n          )}\n          <AlertDescription className=\"ml-2\">\n            {stats.latest_match.complete_match\n              ? '🎉 Complete stock match achieved!'\n              : `Last match found ${stats.latest_match.differences?.length || 0} differences and ${stats.latest_match.unmatched_items?.length || 0} unmatched items`}\n          </AlertDescription>\n        </Alert>\n      )}

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

      {/* Quick Actions */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Getting Started</CardTitle>
            <CardDescription>Begin managing your inventory</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-start gap-2">
              <div className="h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                1
              </div>
              <p className="text-muted-foreground">Upload purchase and sale Excel files</p>
            </div>
            <div className="flex items-start gap-2">
              <div className="h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                2
              </div>
              <p className="text-muted-foreground">Check your book inventory calculation</p>
            </div>
            <div className="flex items-start gap-2">
              <div className="h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                3
              </div>
              <p className="text-muted-foreground">Upload physical inventory and match</p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Key Features</CardTitle>
            <CardDescription>What you can do</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>• Track purchases and sales automatically</p>
            <p>• Match physical vs book inventory</p>
            <p>• Analyze fast/slow/dead stock</p>
            <p>• Detect poly weight exceptions</p>
            <p>• View historical snapshots</p>
          </CardContent>
        </Card>

        <Card className="border-border/40 shadow-sm bg-gradient-to-br from-primary/5 to-secondary/5">
          <CardHeader>
            <CardTitle className="text-xl">Pro Tip</CardTitle>
            <CardDescription>Maximize efficiency</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>
              Upload your files regularly to maintain accurate inventory records. The system
              preserves all historical data for rollback and analysis.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}