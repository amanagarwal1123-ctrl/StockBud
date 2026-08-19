import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Truck, Check, Undo2, Search, X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const fmtDT = (iso) => iso ? new Date(iso).toLocaleString('en-IN', {
  timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
}) : '—';

function QtyCell({ order, onSave }) {
  const [val, setVal] = useState(order.order_qty_kg);
  useEffect(() => { setVal(order.order_qty_kg); }, [order.order_qty_kg]);
  const commit = () => {
    const v = parseFloat(val);
    if (isNaN(v) || v < 0 || v === order.order_qty_kg) { setVal(order.order_qty_kg); return; }
    onSave(order.id, v);
  };
  return (
    <Input type="number" step="0.001" min="0" value={val} data-testid={`gta-qty-input-${order.id}`}
      onChange={e => setVal(e.target.value)} onBlur={commit}
      onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); }}
      className="h-8 w-28 text-right tabular-nums ml-auto" />
  );
}

export default function GoodsToArrive() {
  const [data, setData] = useState({ to_arrive: [], arrived: [] });
  const [tab, setTab] = useState('to_arrive');
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [showSug, setShowSug] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/goods-to-arrive`);
      setData(res.data);
    } catch { toast.error('Failed to load'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { fetchData(); }, [fetchData]);

  const saveQty = async (id, qty) => {
    try {
      const res = await axios.put(`${API}/goods-to-arrive/${id}`, { order_qty_kg: qty });
      setData(prev => ({
        ...prev,
        to_arrive: prev.to_arrive.map(o => o.id === id ? { ...o, ...res.data, success: undefined } : o),
        arrived: prev.arrived.map(o => o.id === id ? { ...o, ...res.data, success: undefined } : o),
      }));
      toast.success('Quantity updated');
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); fetchData(); }
  };

  const act = async (id, action) => {
    try {
      await axios.put(`${API}/goods-to-arrive/${id}`, { action });
      toast.success(action === 'arrive' ? 'Marked arrived' : 'Moved back to Goods to Arrive');
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const allRows = tab === 'to_arrive' ? data.to_arrive : data.arrived;
  const q = query.trim().toLowerCase();
  const rows = q ? allRows.filter(o => o.item_name.toLowerCase().includes(q)) : allRows;

  const suggestions = useMemo(() => {
    if (!q) return [];
    const names = [...new Set([...data.to_arrive, ...data.arrived].map(o => o.item_name))];
    return names.filter(n => n.toLowerCase().includes(q)).slice(0, 8);
  }, [q, data]);

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4" data-testid="goods-to-arrive-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight flex items-center gap-2">
            <Truck className="h-8 w-8 text-indigo-600" />Goods to Arrive
          </h1>
          <p className="text-sm text-muted-foreground mt-1">Green-marked orders from the Purchase List — mark them arrived when goods come in</p>
        </div>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="to_arrive" data-testid="gta-tab-pending">To Arrive ({data.to_arrive.length})</TabsTrigger>
            <TabsTrigger value="arrived" data-testid="gta-tab-arrived">Arrived ({data.arrived.length})</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input value={query} placeholder="Search ordered items…"
          onChange={e => { setQuery(e.target.value); setShowSug(true); }}
          onFocus={() => setShowSug(true)}
          onBlur={() => setTimeout(() => setShowSug(false), 150)}
          className="pl-10 pr-9 h-10" data-testid="gta-search-input" />
        {query && (
          <button className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setQuery('')} data-testid="gta-search-clear"><X className="h-4 w-4" /></button>
        )}
        {showSug && suggestions.length > 0 && (
          <div className="absolute z-30 mt-1 w-full rounded-md border bg-popover shadow-lg max-h-64 overflow-y-auto"
            data-testid="gta-search-suggestions">
            {suggestions.map((s, i) => (
              <button key={s} data-testid={`gta-search-suggestion-${i}`}
                onMouseDown={(e) => { e.preventDefault(); setQuery(s); setShowSug(false); }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-muted truncate">
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="py-14 text-center text-muted-foreground">Loading…</div>
          ) : rows.length === 0 ? (
            <div className="py-14 text-center text-muted-foreground" data-testid="gta-empty">
              {q ? 'No ordered items match your search'
                : tab === 'to_arrive' ? 'Nothing pending — green-mark items in the Purchase List to order them' : 'No arrivals yet'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>List Date</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead>Marked At</TableHead>
                    <TableHead className="text-right">Ordered Qty (kg)</TableHead>
                    <TableHead className="text-right">Fine (kg)</TableHead>
                    <TableHead className="text-right">Labour (₹)</TableHead>
                    {tab === 'arrived' && <TableHead>Arrived At</TableHead>}
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((o, i) => (
                    <TableRow key={o.id} data-testid={`gta-row-${i}`}
                      className={tab === 'arrived' ? 'bg-green-50/60' : ''}>
                      <TableCell className="whitespace-nowrap text-sm">{o.snapshot_date || '—'}</TableCell>
                      <TableCell className="font-medium whitespace-nowrap">{o.item_name}</TableCell>
                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">{fmtDT(o.green_at)}</TableCell>
                      <TableCell className="text-right">
                        {tab === 'to_arrive'
                          ? <QtyCell order={o} onSave={saveQty} />
                          : <span className="tabular-nums">{Number(o.order_qty_kg).toFixed(3)}</span>}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{Number(o.fine_kg).toFixed(3)}</TableCell>
                      <TableCell className="text-right tabular-nums">₹{Math.round(o.labour_inr).toLocaleString('en-IN')}</TableCell>
                      {tab === 'arrived' && <TableCell className="whitespace-nowrap text-sm">{fmtDT(o.arrived_at)}</TableCell>}
                      <TableCell className="text-right">
                        {tab === 'to_arrive' ? (
                          <Button size="sm" className="h-8 bg-green-600 hover:bg-green-700" data-testid={`gta-arrive-btn-${i}`}
                            onClick={() => act(o.id, 'arrive')}>
                            <Check className="h-4 w-4 mr-1" />Arrived
                          </Button>
                        ) : (
                          <Button size="sm" variant="outline" className="h-8" data-testid={`gta-undo-btn-${i}`}
                            onClick={() => act(o.id, 'undo')}>
                            <Undo2 className="h-4 w-4 mr-1" />Undo
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
