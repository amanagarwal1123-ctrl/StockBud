import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TrendingUp, RefreshCw } from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const RANGES = [30, 60, 90, 180, 365];
const fmtDate = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : '—');

export const DailyClosingStock = () => {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async (d) => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API}/stock-audit/daily-closing?days=${d}`);
      setData(r.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load daily closing stock');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(days); }, [fetchData, days]);

  const chartData = (data?.days || []).map((d) => ({ ...d, short: d.date.slice(5) }));

  return (
    <div className="space-y-4" data-testid="daily-closing-section">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
          {RANGES.map((r) => (
            <Button key={r} variant={days === r ? 'default' : 'outline'} size="sm" className="h-8"
              onClick={() => setDays(r)} data-testid={`closing-range-${r}`}>
              {r}d
            </Button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {data && (
            <p className="text-sm text-muted-foreground">
              Current total: <span className="font-bold text-foreground tabular-nums" data-testid="closing-current-total">
                {data.current_total_kg.toFixed(3)} kg</span>
            </p>
          )}
          <Button variant="outline" size="sm" className="h-8" onClick={() => fetchData(days)} disabled={loading}
            data-testid="closing-refresh-btn">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {data?.anchor_clamped && (
        <p className="text-xs text-amber-600" data-testid="closing-anchor-note">
          Range clamped to the opening-stock anchor ({fmtDate(data.anchor_date)}) — closing stock before it is undefined.
        </p>
      )}

      {error && <p className="text-sm text-destructive" data-testid="closing-error">{error}</p>}

      {!error && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-lg">
              <TrendingUp className="h-5 w-5" /> Total Closing Stock (net kg)
            </CardTitle>
            <CardDescription>
              Datewise total net-weight closing stock across all items — back-rolled from the live Current Stock total.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground py-10 text-center">Loading…</p>
            ) : (
              <div className="h-72 w-full" data-testid="closing-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="closingFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3} />
                    <XAxis dataKey="short" tick={{ fontSize: 11 }} minTickGap={24} />
                    <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']}
                      tickFormatter={(v) => v.toLocaleString()} width={70} />
                    <Tooltip
                      formatter={(v) => [`${Number(v).toFixed(3)} kg`, 'Closing stock']}
                      labelFormatter={(l, p) => (p?.[0]?.payload?.date ? fmtDate(p[0].payload.date) : l)}
                    />
                    <Area type="monotone" dataKey="closing_kg" stroke="hsl(var(--primary))"
                      strokeWidth={2} fill="url(#closingFill)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!error && !loading && (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <Table data-testid="closing-table">
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Date</TableHead>
                  <TableHead className="text-xs text-right">Closing Stock (net kg)</TableHead>
                  <TableHead className="text-xs text-right">Day Change (kg)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...(data?.days || [])].reverse().map((d, i, arr) => {
                  const prev = arr[i + 1];
                  const change = prev ? d.closing_kg - prev.closing_kg : null;
                  return (
                    <TableRow key={d.date} data-testid={`closing-row-${d.date}`}>
                      <TableCell className="text-xs font-mono whitespace-nowrap">{fmtDate(d.date)}</TableCell>
                      <TableCell className="text-right font-semibold tabular-nums">{d.closing_kg.toFixed(3)}</TableCell>
                      <TableCell className={`text-right tabular-nums text-xs ${change === null ? 'text-muted-foreground' : change >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {change === null ? '—' : `${change >= 0 ? '+' : ''}${change.toFixed(3)}`}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
