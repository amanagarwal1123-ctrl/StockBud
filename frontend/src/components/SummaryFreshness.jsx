import { useState } from 'react';
import axios from 'axios';
import { RefreshCw, Clock, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function timeAgo(iso) {
  if (!iso) return 'Never computed';
  const then = new Date(iso);
  const now = new Date();
  const diffSec = Math.floor((now - then) / 1000);
  if (Number.isNaN(diffSec) || diffSec < 0) return 'just now';
  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} hr ago`;
  return `${Math.floor(diffSec / 86400)} days ago`;
}

/**
 * Inline freshness indicator + manual refresh for pre-computed analytics.
 *
 * Props
 *   year                — int. Year to recompute when the button is clicked.
 *   lastComputedAt      — ISO timestamp string from the backend response.
 *   wasRecomputed       — true if the last read forced a recompute (info badge).
 *   onRefreshed         — async callback fired after a successful manual refresh.
 *   testId              — root data-testid (defaults to "summary-freshness").
 */
export default function SummaryFreshness({
  year,
  lastComputedAt,
  wasRecomputed = false,
  onRefreshed,
  testId = 'summary-freshness',
}) {
  const [busy, setBusy] = useState(false);

  const handleRefresh = async () => {
    setBusy(true);
    const tid = toast.loading('Recomputing summaries...');
    try {
      const res = await axios.post(`${API}/analytics/recompute-summaries`, { year });
      toast.success(
        `Refreshed ${res.data?.txn_count?.toLocaleString?.() || ''} transactions`,
        { id: tid }
      );
      if (onRefreshed) await onRefreshed(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Refresh failed', { id: tid });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-border/40 bg-muted/30"
      data-testid={testId}
    >
      <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      <span className="text-[11px] text-muted-foreground font-mono whitespace-nowrap">
        Updated <span className="font-semibold text-foreground" data-testid={`${testId}-label`}>{timeAgo(lastComputedAt)}</span>
      </span>
      {wasRecomputed && (
        <span
          className="text-[10px] gap-1 inline-flex items-center text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-1.5 py-0.5"
          title="Server detected stale data and recomputed automatically"
          data-testid={`${testId}-auto-recomputed`}
        >
          <CheckCircle2 className="h-3 w-3" />Auto-refreshed
        </span>
      )}
      {!lastComputedAt && (
        <span
          className="text-[10px] gap-1 inline-flex items-center text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"
          data-testid={`${testId}-never-computed`}
        >
          <AlertCircle className="h-3 w-3" />Stale
        </span>
      )}
      <Button
        size="sm"
        variant="outline"
        className="h-6 px-2 text-[11px] gap-1"
        onClick={handleRefresh}
        disabled={busy}
        data-testid={`${testId}-refresh-btn`}
      >
        <RefreshCw className={`h-3 w-3 ${busy ? 'animate-spin' : ''}`} />
        Refresh
      </Button>
    </div>
  );
}
