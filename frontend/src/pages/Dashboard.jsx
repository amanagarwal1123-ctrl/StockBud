import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertTriangle, CheckCircle2, Clock, FileText, Download, Calendar, Users, BarChart3, ArrowUpRight, RotateCcw, Filter, Scale, ChevronDown, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function formatDateDDMMYYYY(dateStr) {
  if (!dateStr) return '—';
  const parts = dateStr.split('-');
  if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
  return dateStr;
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [stampHistory, setStampHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reconSessions, setReconSessions] = useState([]);
  const [reconFilter, setReconFilter] = useState('all');
  const [expandedSession, setExpandedSession] = useState(null);
  const [sessionDetail, setSessionDetail] = useState(null);

  useEffect(() => {
    fetchStats();
    fetchStampHistory();
    fetchReconSessions();

    const onFocus = () => {
      fetchStats();
      fetchStampHistory();
      fetchReconSessions();
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
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

  const fetchReconSessions = async () => {
    try {
      const res = await axios.get(`${API}/physical-stock/update-history`);
      setReconSessions(res.data.sessions || []);
    } catch (error) {
      console.error('Error fetching reconciliation sessions:', error);
    }
  };

  const toggleSessionDetail = async (sessionId) => {
    if (expandedSession === sessionId) {
      setExpandedSession(null);
      setSessionDetail(null);
      return;
    }
    try {
      const res = await axios.get(`${API}/physical-stock/update-history/${sessionId}`);
      setSessionDetail(res.data);
      setExpandedSession(sessionId);
    } catch {
      toast.error('Failed to load session details');
    }
  };

  const handleReverseSession = async (sessionId) => {
    if (!window.confirm('Reverse this physical stock update? This will restore all items to their previous weights.')) return;
    try {
      await axios.post(`${API}/physical-stock/update-history/${sessionId}/reverse`);
      toast.success('Session reversed successfully');
      setExpandedSession(null);
      setSessionDetail(null);
      fetchReconSessions();
      fetchStats();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Reverse failed');
    }
  };

  const filteredReconSessions = reconSessions.filter(s => {
    if (reconFilter === 'active') return !s.is_reversed && s.session_state !== 'reversed';
    if (reconFilter === 'reversed') return s.is_reversed || s.session_state === 'reversed';
    return true;
  });

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

  const fromDate = stats?.date_range?.from_date;
  const toDate = stats?.date_range?.to_date;

  const statCards = [
    {
      title: 'Total Transactions',
      value: stats?.total_transactions || 0,
      icon: BarChart3,
      gradient: 'from-blue-500/15 to-blue-600/5',
      iconBg: 'bg-blue-500/10',
      iconColor: 'text-blue-600',
      borderAccent: 'border-l-blue-500',
    },
    {
      title: 'Total Parties',
      value: stats?.total_parties || 0,
      icon: Users,
      gradient: 'from-violet-500/15 to-violet-600/5',
      iconBg: 'bg-violet-500/10',
      iconColor: 'text-violet-600',
      borderAccent: 'border-l-violet-500',
    },
    {
      title: 'Purchases',
      value: stats?.total_purchases || 0,
      icon: ArrowUpRight,
      gradient: 'from-emerald-500/15 to-emerald-600/5',
      iconBg: 'bg-emerald-500/10',
      iconColor: 'text-emerald-600',
      borderAccent: 'border-l-emerald-500',
    },
    {
      title: 'Sales',
      value: stats?.total_sales || 0,
      icon: TrendingUp,
      gradient: 'from-amber-500/15 to-amber-600/5',
      iconBg: 'bg-amber-500/10',
      iconColor: 'text-amber-600',
      borderAccent: 'border-l-amber-500',
    },
  ];

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-5 sm:space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight" data-testid="dashboard-title">
            Dashboard
          </h1>
          <p className="text-xs sm:text-base text-muted-foreground mt-1">
            StockBud — Intelligent inventory management
          </p>
        </div>
        {/* Download Manual Buttons */}
        <div className="flex gap-2 flex-shrink-0" data-testid="manual-download-section">
          <a href="/manuals/StockBud_Manual_EN.pdf" download>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" data-testid="download-manual-en">
              <Download className="h-3.5 w-3.5" />
              Manual (EN)
            </Button>
          </a>
          <a href="/manuals/StockBud_Manual_HI.pdf" download>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" data-testid="download-manual-hi">
              <Download className="h-3.5 w-3.5" />
              Manual (HI)
            </Button>
          </a>
        </div>
      </div>

      {/* Date Range Banner */}
      {fromDate && toDate && (
        <div
          className="relative overflow-hidden rounded-xl border border-border/40 bg-gradient-to-r from-primary/5 via-card to-accent/5 p-4 sm:p-5"
          data-testid="date-range-banner"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="relative flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-primary/10">
                <Calendar className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Transaction Period</p>
                <p className="text-base sm:text-lg font-bold font-mono mt-0.5" data-testid="date-range-value">
                  {formatDateDDMMYYYY(fromDate)}
                  <span className="mx-2 text-muted-foreground font-normal">to</span>
                  {formatDateDDMMYYYY(toDate)}
                </p>
              </div>
            </div>
            <div className="sm:ml-auto flex items-center gap-4 text-sm">
              <div className="px-3 py-1.5 rounded-lg bg-card border border-border/40">
                <span className="text-muted-foreground text-xs">Items</span>
                <p className="font-bold font-mono text-sm">{stats?.total_items || 0}</p>
              </div>
              <div className="px-3 py-1.5 rounded-lg bg-card border border-border/40">
                <span className="text-muted-foreground text-xs">Opening Stock</span>
                <p className="font-bold font-mono text-sm">{stats?.total_opening_stock || 0}</p>
              </div>
            </div>
          </div>
        </div>
      )}

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
              ? 'Complete stock match achieved!'
              : `Last match found ${stats.latest_match.differences?.length || 0} differences and ${stats.latest_match.unmatched_items?.length || 0} unmatched items`}
          </AlertDescription>
        </Alert>
      )}

      {/* Stats Grid */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <Card
            key={stat.title}
            className={`relative overflow-hidden border-l-4 ${stat.borderAccent} border-border/30 shadow-sm hover:shadow-md transition-all duration-200 hover:-translate-y-0.5`}
            data-testid={`stat-card-${stat.title.toLowerCase().replace(/\s+/g, '-')}`}
          >
            <div className={`absolute inset-0 bg-gradient-to-br ${stat.gradient} pointer-events-none`} />
            <CardHeader className="relative flex flex-row items-center justify-between pb-1 pt-4 px-4">
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {stat.title}
              </CardTitle>
              <div className={`p-1.5 rounded-md ${stat.iconBg}`}>
                <stat.icon className={`h-4 w-4 ${stat.iconColor}`} />
              </div>
            </CardHeader>
            <CardContent className="relative px-4 pb-4 pt-0">
              <div className="text-xl sm:text-2xl md:text-3xl font-bold font-mono tracking-tight">{stat.value.toLocaleString()}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Reconciliation Sessions */}
      <Card className="border-border/30 shadow-sm overflow-hidden" data-testid="recon-sessions-card">
        <CardHeader className="bg-gradient-to-r from-card to-muted/20 border-b border-border/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-md bg-indigo-500/10">
                <Scale className="h-4 w-4 text-indigo-600" />
              </div>
              <div>
                <CardTitle className="text-base">Stock Reconciliation History</CardTitle>
                <CardDescription className="text-xs">All physical stock update sessions across dates</CardDescription>
              </div>
            </div>
            <Select value={reconFilter} onValueChange={setReconFilter}>
              <SelectTrigger className="w-[140px] h-8 text-xs" data-testid="recon-filter">
                <Filter className="h-3 w-3 mr-1" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sessions</SelectItem>
                <SelectItem value="active">Active Only</SelectItem>
                <SelectItem value="reversed">Reversed Only</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto max-h-[40rem]">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow className="bg-muted/30">
                  <TableHead className="font-semibold text-xs w-6"></TableHead>
                  <TableHead className="font-semibold text-xs">Date</TableHead>
                  <TableHead className="font-semibold text-xs">Status</TableHead>
                  <TableHead className="font-semibold text-xs">Items</TableHead>
                  <TableHead className="text-right font-semibold text-xs">Gross Change</TableHead>
                  <TableHead className="text-right font-semibold text-xs">Net Change</TableHead>
                  <TableHead className="font-semibold text-xs">By</TableHead>
                  <TableHead className="font-semibold text-xs">When</TableHead>
                  <TableHead className="font-semibold text-xs text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredReconSessions.map((s) => {
                  const grDelta = s.gr_delta_total || 0;
                  const netDelta = s.net_delta_total || 0;
                  const isReversed = s.is_reversed || s.session_state === 'reversed';
                  const appliedCount = s.applied_count || 0;
                  const rejectedCount = s.rejected_count || 0;
                  const createdAt = s.applied_at || s.created_at || '';
                  const dateStr = createdAt ? new Date(createdAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
                  const isExpanded = expandedSession === s.session_id;

                  return (
                    <React.Fragment key={s.session_id}>
                      <TableRow
                        className={`cursor-pointer transition-colors ${isReversed ? 'opacity-60 hover:opacity-80' : 'hover:bg-muted/20'} ${isExpanded ? 'bg-muted/20' : ''}`}
                        onClick={() => toggleSessionDetail(s.session_id)}
                        data-testid={`recon-row-${s.session_id.slice(0,8)}`}
                      >
                        <TableCell className="px-2 w-6">
                          {isExpanded
                            ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            : <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          }
                        </TableCell>
                        <TableCell className="font-mono text-sm font-semibold">{formatDateDDMMYYYY(s.verification_date)}</TableCell>
                        <TableCell>
                          {isReversed ? (
                            <Badge className="bg-red-500/80 text-xs gap-1"><RotateCcw className="h-3 w-3" />Reversed</Badge>
                          ) : s.reversible ? (
                            <Badge className="bg-emerald-600 text-xs gap-1"><CheckCircle2 className="h-3 w-3" />Active</Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs">Finalized</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-xs">
                          <span className="text-emerald-600 font-semibold">{appliedCount}</span>
                          {rejectedCount > 0 && <span className="text-muted-foreground ml-1">({rejectedCount} rej)</span>}
                        </TableCell>
                        <TableCell className={`text-right font-mono text-xs font-semibold ${grDelta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {grDelta >= 0 ? '+' : ''}{(grDelta / 1000).toFixed(3)} kg
                        </TableCell>
                        <TableCell className={`text-right font-mono text-xs font-semibold ${netDelta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                          {netDelta >= 0 ? '+' : ''}{(netDelta / 1000).toFixed(3)} kg
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{s.applied_by || '—'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{dateStr}</TableCell>
                        <TableCell className="text-right">
                          {s.reversible && !isReversed && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-xs text-destructive border-destructive/30 h-7 px-2"
                              onClick={(e) => { e.stopPropagation(); handleReverseSession(s.session_id); }}
                              data-testid={`reverse-btn-${s.session_id.slice(0,8)}`}
                            >
                              <RotateCcw className="h-3 w-3 mr-1" />
                              Reverse
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                      {isExpanded && sessionDetail && (
                        <TableRow className="hover:bg-transparent">
                          <TableCell colSpan={9} className="p-0 border-b-2 border-primary/20">
                            <div className="bg-muted/10 px-4 py-3">
                              <p className="text-xs font-semibold text-muted-foreground mb-2">Item-wise Changes</p>
                              <div className="rounded border overflow-hidden">
                                <Table className="min-w-[640px]">
                                  <TableHeader>
                                    <TableRow className="text-xs bg-muted/40">
                                      <TableHead className="text-xs py-1.5">Status</TableHead>
                                      <TableHead className="text-xs py-1.5">Stamp</TableHead>
                                      <TableHead className="text-xs py-1.5">Item Name</TableHead>
                                      <TableHead className="text-right text-xs py-1.5">Old Gross</TableHead>
                                      <TableHead className="text-right text-xs py-1.5">New Gross</TableHead>
                                      <TableHead className="text-right text-xs py-1.5">Gross Delta</TableHead>
                                      <TableHead className="text-right text-xs py-1.5">Old Net</TableHead>
                                      <TableHead className="text-right text-xs py-1.5">New Net</TableHead>
                                      <TableHead className="text-right text-xs py-1.5">Net Delta</TableHead>
                                    </TableRow>
                                  </TableHeader>
                                  <TableBody>
                                    {(sessionDetail.items || []).map((item, idx) => (
                                      <TableRow key={idx} className={
                                        item.status === 'applied' ? 'bg-white' :
                                        item.status === 'rejected' ? 'bg-amber-50/50' :
                                        item.status === 'unmatched' ? 'bg-red-50/50' :
                                        item.status === 'skipped' ? 'bg-gray-50/50' : ''
                                      }>
                                        <TableCell className="py-1.5">
                                          <Badge className={`text-[10px] px-1.5 py-0 ${
                                            item.status === 'applied' ? 'bg-emerald-600' :
                                            item.status === 'rejected' ? 'bg-amber-500' :
                                            item.status === 'unmatched' ? 'bg-red-500' :
                                            item.status === 'skipped' ? 'bg-gray-500' : 'bg-blue-500'
                                          }`}>{item.status}</Badge>
                                        </TableCell>
                                        <TableCell className="text-xs py-1.5"><Badge variant="outline" className="text-[10px] px-1.5 py-0">{item.stamp || '—'}</Badge></TableCell>
                                        <TableCell className="text-xs font-medium py-1.5">{item.item_name}</TableCell>
                                        <TableCell className="text-right font-mono text-xs py-1.5">{((item.old_gr_wt || 0) / 1000).toFixed(3)}</TableCell>
                                        <TableCell className="text-right font-mono text-xs py-1.5">{((item.final_gr_wt || item.proposed_gr_wt || 0) / 1000).toFixed(3)}</TableCell>
                                        <TableCell className={`text-right font-mono text-xs font-semibold py-1.5 ${(item.gr_delta || 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                          {(item.gr_delta || 0) >= 0 ? '+' : ''}{((item.gr_delta || 0) / 1000).toFixed(3)}
                                        </TableCell>
                                        <TableCell className="text-right font-mono text-xs py-1.5">{((item.old_net_wt || 0) / 1000).toFixed(3)}</TableCell>
                                        <TableCell className="text-right font-mono text-xs py-1.5">{((item.final_net_wt || item.proposed_net_wt || 0) / 1000).toFixed(3)}</TableCell>
                                        <TableCell className={`text-right font-mono text-xs font-semibold py-1.5 ${(item.net_delta || 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                          {(item.net_delta || 0) >= 0 ? '+' : ''}{((item.net_delta || 0) / 1000).toFixed(3)}
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  );
                })}
                {filteredReconSessions.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center py-8 text-muted-foreground text-sm">
                      {reconFilter !== 'all' ? 'No sessions match the current filter' : 'No reconciliation sessions yet'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Stamp Verification Status */}
      <Card className="border-border/30 shadow-sm overflow-hidden">
        <CardHeader className="bg-gradient-to-r from-card to-muted/20 border-b border-border/30">
          <CardTitle className="flex items-center gap-2 text-base">
            <div className="p-1.5 rounded-md bg-primary/10">
              <Clock className="h-4 w-4 text-primary" />
            </div>
            Stamp Verification Status
          </CardTitle>
          <CardDescription>Last physical verification for each stamp</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto max-h-96">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow className="bg-muted/30">
                  <TableHead className="font-semibold">Stamp</TableHead>
                  <TableHead className="font-semibold">Last Verified</TableHead>
                  <TableHead className="font-semibold">Days Ago</TableHead>
                  <TableHead className="text-right font-semibold">Difference</TableHead>
                  <TableHead className="font-semibold">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stampHistory.map((stamp, idx) => {
                  const daysAgo = getDaysSinceVerification(stamp.last_verified_date);
                  const isOverdue = daysAgo > 15;
                  
                  return (
                    <TableRow key={idx} className={isOverdue ? 'bg-red-50/50 border-l-4 border-l-red-500' : 'hover:bg-muted/20'}>
                      <TableCell className="font-bold font-mono text-sm">{stamp.stamp}</TableCell>
                      <TableCell className="text-sm">
                        {stamp.last_verified_date ? formatDateDDMMYYYY(stamp.last_verified_date) : 'Never'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={isOverdue ? 'destructive' : 'outline'} className="font-mono text-xs">
                          {daysAgo === 999 ? 'Never' : `${daysAgo}d`}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {stamp.difference ? `${stamp.difference >= 0 ? '+' : ''}${stamp.difference.toFixed(3)} kg` : '-'}
                      </TableCell>
                      <TableCell>
                        {stamp.last_verified_date === null ? (
                          <Badge variant="outline" className="text-xs gap-1 text-muted-foreground">
                            <Clock className="h-3 w-3" />
                            Not Verified
                          </Badge>
                        ) : isOverdue ? (
                          <Badge className="bg-red-600 text-xs gap-1">
                            <AlertTriangle className="h-3 w-3" />
                            Overdue
                          </Badge>
                        ) : stamp.is_match ? (
                          <Badge className="bg-green-600 text-xs gap-1">
                            <CheckCircle2 className="h-3 w-3" />
                            Matched
                          </Badge>
                        ) : stamp.is_match === false ? (
                          <Badge className="bg-orange-500 text-xs gap-1">
                            <AlertTriangle className="h-3 w-3" />
                            Mismatch
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-xs">Unknown</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {stampHistory.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground text-sm">
                      No stamp verification data yet
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
