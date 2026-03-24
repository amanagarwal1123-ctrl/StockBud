import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { CheckSquare, XSquare, Download, Calendar, Pencil } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { exportToCSV } from '@/utils/exportCSV';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const diffColor = (d) => {
  if (Math.abs(d) < 0.020) return 'text-green-600';
  return d > 0 ? 'text-blue-600' : 'text-red-600';
};
const diffBg = (d) => {
  if (Math.abs(d) < 0.020) return 'bg-green-50';
  return d > 0 ? 'bg-blue-50' : 'bg-red-50';
};
const diffBadgeCls = (d) => {
  if (Math.abs(d) < 0.020) return 'bg-green-600';
  return d > 0 ? 'bg-blue-600' : 'bg-red-600';
};

export default function ManagerApprovals() {
  const [allEntries, setAllEntries] = useState([]);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [approvalDetails, setApprovalDetails] = useState(null);
  const [allDetails, setAllDetails] = useState({});
  const [rejectionMessage, setRejectionMessage] = useState('');
  const [editingDate, setEditingDate] = useState({});
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const { isManager, isAdmin } = useAuth();

  useEffect(() => {
    if (isManager || isAdmin) fetchAllEntries();
  }, [isManager, isAdmin]);

  const fetchAllEntries = async () => {
    try {
      const response = await axios.get(`${API}/manager/all-entries`);
      setAllEntries(response.data);
      const pending = response.data.filter(e => e.status === 'pending');
      for (const entry of pending) fetchDetailsForBadge(entry.stamp, entry.verification_date || entry.entry_day);
    } catch (error) {
      console.error('Error fetching entries:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchDetailsForBadge = async (stamp, verificationDate) => {
    try {
      const params = verificationDate ? `?verification_date=${verificationDate}` : '';
      const response = await axios.get(`${API}/manager/approval-details/${stamp}${params}`);
      const key = verificationDate ? `${stamp}__${verificationDate}` : stamp;
      setAllDetails(prev => ({ ...prev, [key]: response.data }));
    } catch (error) {
      console.error('Failed to load details:', error);
    }
  };

  const fetchApprovalDetails = async (stamp, verificationDate) => {
    try {
      setDetailsLoading(true);
      const params = verificationDate ? `?verification_date=${verificationDate}` : '';
      const response = await axios.get(`${API}/manager/approval-details/${stamp}${params}`);
      setApprovalDetails(response.data);
      setSelectedEntry(`${stamp}__${verificationDate || ''}`);
    } catch (error) {
      toast.error('Failed to load details');
    } finally {
      setDetailsLoading(false);
    }
  };

  const updateVerificationDate = async (stamp, newDate) => {
    try {
      const token = sessionStorage.getItem('token');
      await axios.put(`${API}/manager/update-verification-date/${stamp}`, 
        { verification_date: newDate },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Date updated to ${newDate}`);
      setEditingDate(prev => ({ ...prev, [stamp]: false }));
      fetchAllEntries();
      fetchDetailsForBadge(stamp, newDate);
      if (selectedEntry?.startsWith(stamp)) fetchApprovalDetails(stamp, newDate);
    } catch (error) {
      toast.error('Failed to update date');
    }
  };

  const exportStampDifferences = async (stamp, verificationDate) => {
    try {
      const params = verificationDate ? `?verification_date=${verificationDate}` : '';
      const response = await axios.get(`${API}/manager/approval-details/${stamp}${params}`);
      const exportData = response.data.comparison.map(item => ({
        'Item Name': item.item_name,
        'Book Gross (kg)': (item.book_gross || 0).toFixed(3),
        'Entered Gross (kg)': (item.entered_gross || 0).toFixed(3),
        'Difference (kg)': (item.difference || 0).toFixed(3)
      }));
      exportToCSV(exportData, `${stamp}_comparison`);
    } catch (error) {
      toast.error('Failed to export');
    }
  };

  const handleApproval = async (stamp, approve, verificationDate) => {
    if (!approve && !rejectionMessage.trim()) {
      toast.error('Please enter a rejection message');
      return;
    }
    const detailKey = verificationDate ? `${stamp}__${verificationDate}` : stamp;
    let details = allDetails[detailKey] || approvalDetails;
    if (!details) {
      await fetchDetailsForBadge(stamp, verificationDate);
      details = allDetails[detailKey];
    }
    const totalDiff = details?.total_difference ? details.total_difference * 1000 : 0;

    try {
      await axios.post(`${API}/manager/approve-stamp`, {
        stamp, approve, total_difference: totalDiff,
        rejection_message: approve ? null : rejectionMessage
      });
      toast.success(`${stamp} ${approve ? 'approved' : 'rejected'}!`);
      setSelectedEntry(null);
      setApprovalDetails(null);
      setRejectionMessage('');
      fetchAllEntries();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Action failed');
    }
  };

  if (!isManager && !isAdmin) {
    return (
      <div className="p-4"><Alert variant="destructive"><AlertDescription>Access Denied.</AlertDescription></Alert></div>
    );
  }

  const pendingEntries = allEntries.filter(e => e.status === 'pending');
  const approvedEntries = allEntries.filter(e => e.status === 'approved');
  const rejectedEntries = allEntries.filter(e => e.status === 'rejected');

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="approvals-page">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">Stamp Approvals</h1>
        <p className="text-sm sm:text-lg text-muted-foreground mt-1">Review and approve stock entries</p>
      </div>

      <Tabs defaultValue="pending" className="space-y-4">
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="pending" className="text-xs sm:text-sm">Pending ({pendingEntries.length})</TabsTrigger>
          <TabsTrigger value="approved" className="text-xs sm:text-sm">Approved ({approvedEntries.length})</TabsTrigger>
          <TabsTrigger value="rejected" className="text-xs sm:text-sm">Rejected ({rejectedEntries.length})</TabsTrigger>
        </TabsList>

        {/* ===== PENDING ===== */}
        <TabsContent value="pending" className="space-y-3">
          {pendingEntries.map((entry) => {
            const vd = entry.verification_date || entry.entry_day || '';
            const detailKey = `${entry.stamp}__${vd}`;
            return (
            <EntryCard
              key={`p-${entry.stamp}-${vd}`}
              entry={entry}
              status="pending"
              details={allDetails[detailKey]}
              isExpanded={selectedEntry === detailKey}
              approvalDetails={selectedEntry === detailKey ? approvalDetails : null}
              detailsLoading={selectedEntry === detailKey && detailsLoading}
              editingDate={editingDate}
              setEditingDate={setEditingDate}
              onViewDetails={() => fetchApprovalDetails(entry.stamp, vd)}
              onApprove={() => handleApproval(entry.stamp, true, vd)}
              onReject={() => handleApproval(entry.stamp, false, vd)}
              onDateUpdate={updateVerificationDate}
              onExport={() => exportStampDifferences(entry.stamp, vd)}
              rejectionMessage={rejectionMessage}
              setRejectionMessage={setRejectionMessage}
            />
            );
          })}
          {pendingEntries.length === 0 && <p className="text-muted-foreground text-center py-8">No pending entries</p>}
        </TabsContent>

        {/* ===== APPROVED ===== */}
        <TabsContent value="approved" className="space-y-3">
          {approvedEntries.map((entry) => {
            const vd = entry.verification_date || entry.entry_day || '';
            const detailKey = `${entry.stamp}__${vd}`;
            return (
            <EntryCard
              key={`a-${entry.stamp}-${vd}`}
              entry={entry}
              status="approved"
              details={allDetails[detailKey]}
              isExpanded={selectedEntry === detailKey}
              approvalDetails={selectedEntry === detailKey ? approvalDetails : null}
              detailsLoading={selectedEntry === detailKey && detailsLoading}
              editingDate={editingDate}
              setEditingDate={setEditingDate}
              onViewDetails={() => fetchApprovalDetails(entry.stamp, vd)}
              onReject={() => handleApproval(entry.stamp, false, vd)}
              onDateUpdate={updateVerificationDate}
              onExport={() => exportStampDifferences(entry.stamp, vd)}
              rejectionMessage={rejectionMessage}
              setRejectionMessage={setRejectionMessage}
            />
            );
          })}
          {approvedEntries.length === 0 && <p className="text-muted-foreground text-center py-8">No approved entries</p>}
        </TabsContent>

        {/* ===== REJECTED ===== */}
        <TabsContent value="rejected" className="space-y-3">
          {rejectedEntries.map((entry) => (
            <Card key={`r-${entry.stamp}-${entry.entry_day}`} className="border-red-500/20">
              <CardHeader className="p-3 sm:p-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-base sm:text-lg">{entry.stamp}</CardTitle>
                    <CardDescription className="text-xs sm:text-sm">
                      By {entry.entered_by} — Rejected on {entry.approved_at ? new Date(entry.approved_at).toLocaleDateString() : '—'}
                    </CardDescription>
                    {entry.rejection_message && (
                      <Alert className="mt-2 border-red-500/50 bg-red-50 p-2">
                        <AlertDescription className="text-xs sm:text-sm">
                          <strong>Reason:</strong> {entry.rejection_message}
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                  <Badge className="bg-red-600 self-start">REJECTED</Badge>
                </div>
              </CardHeader>
            </Card>
          ))}
          {rejectedEntries.length === 0 && <p className="text-muted-foreground text-center py-8">No rejected entries</p>}
        </TabsContent>
      </Tabs>
    </div>
  );
}

/** Reusable entry card for pending & approved tabs */
function EntryCard({
  entry, status, details, isExpanded, approvalDetails, detailsLoading,
  editingDate, setEditingDate, onViewDetails, onApprove, onReject,
  onDateUpdate, onExport, rejectionMessage, setRejectionMessage
}) {
  const stamp = entry.stamp;
  const vDate = entry.verification_date || entry.entry_day || '';
  const isEditing = editingDate[stamp];
  const [tempDate, setTempDate] = useState(vDate);
  const isPending = status === 'pending';
  const borderCls = isPending ? 'border-orange-500/20' : 'border-green-500/20';

  return (
    <Card className={borderCls} data-testid={`entry-card-${stamp}`}>
      <CardHeader className="p-3 sm:p-6">
        {/* Row 1: Stamp name + status badge + diff badge */}
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          <span className="font-bold text-base sm:text-lg">{stamp}</span>
          <Badge variant="outline" className={isPending ? 'text-orange-600 text-[10px] sm:text-xs' : 'text-green-600 text-[10px] sm:text-xs'}>
            {status.toUpperCase()}
          </Badge>
          {details && (
            <Badge className={`${diffBadgeCls(details.total_difference)} text-[10px] sm:text-xs px-1.5`}>
              {details.total_difference >= 0 ? '+' : ''}{details.total_difference?.toFixed(3)} kg
            </Badge>
          )}
        </div>

        {/* Row 2: Date info + edit */}
        <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
          {isEditing ? (
            <div className="flex items-center gap-1.5">
              <Input
                type="date"
                value={tempDate}
                onChange={(e) => setTempDate(e.target.value)}
                className="h-7 text-xs w-36"
                data-testid={`date-input-${stamp}`}
              />
              <Button size="sm" className="h-7 text-xs px-2" onClick={() => onDateUpdate(stamp, tempDate)} data-testid={`save-date-${stamp}`}>Save</Button>
              <Button size="sm" variant="ghost" className="h-7 text-xs px-2" onClick={() => setEditingDate(p => ({ ...p, [stamp]: false }))}>Cancel</Button>
            </div>
          ) : (
            <>
              {vDate && (
                <Badge variant="outline" className="text-[10px] sm:text-xs text-blue-700 border-blue-300 bg-blue-50">
                  <Calendar className="h-3 w-3 mr-0.5" />Stock for: {vDate}
                </Badge>
              )}
              <button
                onClick={() => { setTempDate(vDate || new Date().toISOString().slice(0, 10)); setEditingDate(p => ({ ...p, [stamp]: true })); }}
                className="text-muted-foreground hover:text-primary p-0.5"
                title="Edit verification date"
                data-testid={`edit-date-${stamp}`}
              >
                <Pencil className="h-3 w-3" />
              </button>
            </>
          )}
        </div>

        {/* Row 3: Metadata */}
        <p className="text-[11px] sm:text-xs text-muted-foreground mt-0.5">
          By {entry.entered_by} on {new Date(entry.entry_date).toLocaleDateString()}
          {entry.iteration > 1 && <span className="ml-1 text-orange-600">• Iter {entry.iteration}</span>}
          {!isPending && entry.approved_by && <span> • {status === 'approved' ? 'Approved' : 'Reviewed'} by {entry.approved_by}</span>}
        </p>

        {/* Row 4: Actions */}
        <div className="flex flex-wrap gap-1.5 mt-2">
          <Button onClick={onViewDetails} variant="outline" size="sm" className="h-7 text-xs" data-testid={`view-details-${stamp}`}>Details</Button>
          {isPending && onApprove && (
            <Button onClick={onApprove} size="sm" className="h-7 text-xs" data-testid={`approve-${stamp}`}>
              <CheckSquare className="h-3 w-3 mr-1" />Approve
            </Button>
          )}
          {onReject && (
            <Button onClick={onReject} variant="destructive" size="sm" className="h-7 text-xs" data-testid={`reject-${stamp}`}>
              <XSquare className="h-3 w-3 mr-1" />Reject
            </Button>
          )}
          <Button onClick={onExport} variant="outline" size="sm" className="h-7 text-xs">
            <Download className="h-3 w-3 mr-1" />Export
          </Button>
        </div>
      </CardHeader>

      {/* Expanded comparison */}
      {isExpanded && detailsLoading && (
        <CardContent className="p-2 sm:p-6 pt-0">
          <div className="flex items-center justify-center py-8 gap-2">
            <div className="h-2 w-2 bg-primary rounded-full animate-bounce [animation-delay:-0.3s]" />
            <div className="h-2 w-2 bg-primary rounded-full animate-bounce [animation-delay:-0.15s]" />
            <div className="h-2 w-2 bg-primary rounded-full animate-bounce" />
            <span className="ml-2 text-sm text-muted-foreground">Loading comparison data...</span>
          </div>
        </CardContent>
      )}
      {isExpanded && !detailsLoading && approvalDetails && (
        <CardContent className="p-2 sm:p-6 pt-0">
          <ComparisonTable details={approvalDetails} />
          {/* Rejection message */}
          <div className="mt-3 p-3 bg-orange-50 rounded-lg border border-orange-200">
            <Label className="text-xs font-semibold">Rejection Message (required to reject)</Label>
            <Textarea
              placeholder="What needs correction..."
              value={rejectionMessage}
              onChange={(e) => setRejectionMessage(e.target.value)}
              rows={2}
              className="mt-1 text-sm"
              data-testid={`rejection-msg-${stamp}`}
            />
          </div>
        </CardContent>
      )}
    </Card>
  );
}

/** Comparison table with color-coded diffs */
function ComparisonTable({ details }) {
  return (
    <div className="bg-muted/30 p-2 sm:p-4 rounded-lg">
      <p className="font-semibold text-sm mb-2">
        Book vs Entered{details.verification_date ? ` (as of ${details.verification_date})` : ''}
      </p>
      <div className="max-h-64 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs">Item</TableHead>
              <TableHead className="text-right text-xs">Book</TableHead>
              <TableHead className="text-right text-xs">Entered</TableHead>
              <TableHead className="text-right text-xs">Diff</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {details.comparison?.map((item, i) => {
              const d = item.difference || 0;
              return (
                <TableRow key={i} className={`${item.was_entered ? '' : 'opacity-40'} ${item.was_entered ? diffBg(d) : ''}`}>
                  <TableCell className="text-xs py-1.5 max-w-[120px] sm:max-w-none truncate">{item.item_name}</TableCell>
                  <TableCell className="text-right font-mono text-xs py-1.5">{(item.book_gross || 0).toFixed(3)}</TableCell>
                  <TableCell className="text-right font-mono text-xs py-1.5">{(item.entered_gross || 0).toFixed(3)}</TableCell>
                  <TableCell className={`text-right font-mono text-xs py-1.5 font-semibold ${diffColor(d)}`}>
                    {d >= 0 ? '+' : ''}{d.toFixed(3)}
                  </TableCell>
                </TableRow>
              );
            })}
            <TableRow className="bg-primary/10 border-t-2">
              <TableCell className="font-bold text-xs">TOTAL</TableCell>
              <TableCell className="text-right font-mono text-xs font-bold">{(details.total_book || 0).toFixed(3)}</TableCell>
              <TableCell className="text-right font-mono text-xs font-bold">{(details.total_entered || 0).toFixed(3)}</TableCell>
              <TableCell className={`text-right font-mono text-xs font-bold ${diffColor(details.total_difference || 0)}`}>
                {(details.total_difference || 0) >= 0 ? '+' : ''}{(details.total_difference || 0).toFixed(3)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
