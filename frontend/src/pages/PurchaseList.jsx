import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { ShoppingCart, RotateCcw, ArrowUpDown, ArrowUp, ArrowDown, Settings2, Users } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { PurchaseItemSheet } from '../components/PurchaseItemSheet';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

function SortHead({ label, field, sort, onSort, align = 'right' }) {
  const active = sort.field === field;
  const Icon = !active ? ArrowUpDown : (sort.dir === 'asc' ? ArrowUp : ArrowDown);
  return (
    <TableHead className={`whitespace-nowrap ${align === 'right' ? 'text-right' : ''}`}>
      <button onClick={() => onSort(field)} data-testid={`pl-sort-${field}`}
        className={`inline-flex items-center gap-1 hover:text-foreground ${active ? 'text-foreground font-semibold' : ''}`}>
        {label}<Icon className="h-3.5 w-3.5" />
      </button>
    </TableHead>
  );
}

function SwipeRow({ row, idx, onSwipeLeft, onOpen, onGreenToggle, date }) {
  const [dx, setDx] = useState(0);
  const drag = useRef(null);

  const onPointerDown = (e) => {
    if (e.target.closest('[data-noswipe]')) return;
    drag.current = { x: e.clientX, moved: false };
  };
  const onPointerMove = (e) => {
    if (!drag.current) return;
    const d = e.clientX - drag.current.x;
    if (Math.abs(d) > 8) drag.current.moved = true;
    if (d < 0) setDx(Math.max(d, -160));
  };
  const endDrag = () => {
    if (!drag.current) return;
    const moved = drag.current.moved;
    drag.current = null;
    if (dx < -90) {
      setDx(0);
      onSwipeLeft(row.item_name);
    } else {
      setDx(0);
      if (!moved) onOpen(row);
    }
  };

  return (
    <TableRow
      data-testid={`pl-row-${idx}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={() => { drag.current = null; setDx(0); }}
      onPointerLeave={() => { if (drag.current) { drag.current = null; setDx(0); } }}
      style={{ transform: `translateX(${dx}px)`, transition: dx === 0 ? 'transform 0.2s' : 'none', touchAction: 'pan-y' }}
      className={`cursor-pointer select-none ${row.green
        ? 'bg-green-100 outline outline-2 -outline-offset-2 outline-green-500 hover:bg-green-100'
        : 'hover:bg-muted/40'}`}
    >
      <TableCell data-noswipe className="w-10" onClick={(e) => e.stopPropagation()}>
        <Checkbox checked={row.green} data-testid={`pl-green-check-${idx}`}
          className="data-[state=checked]:bg-green-600 data-[state=checked]:border-green-600"
          onCheckedChange={(v) => onGreenToggle(row.item_name, !!v, date)} />
      </TableCell>
      <TableCell className="text-muted-foreground text-xs w-10">{idx + 1}</TableCell>
      <TableCell className="font-medium whitespace-nowrap">
        {row.item_name}
        {row.baseline_mode === 'fixed' && <span className="ml-1.5 text-[10px] uppercase text-amber-600 font-semibold">fixed</span>}
        {row.season_months?.length > 0 && <span className="ml-1.5 text-[10px] uppercase text-sky-600 font-semibold">seasonal</span>}
      </TableCell>
      <TableCell className="text-right tabular-nums font-semibold">{row.order_qty_kg.toFixed(3)}</TableCell>
      <TableCell className="text-right tabular-nums">{row.current_stock_kg.toFixed(3)}</TableCell>
      <TableCell className="text-right tabular-nums">{row.fine_kg.toFixed(3)}</TableCell>
      <TableCell className="text-right tabular-nums">₹{Math.round(row.labour_inr).toLocaleString('en-IN')}</TableCell>
      <TableCell className={`text-right tabular-nums ${row.profit_silver_per_kg < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
        {row.profit_silver_per_kg == null ? '—' : `${row.profit_silver_per_kg.toFixed(1)} g`}
      </TableCell>
      <TableCell className={`text-right tabular-nums ${row.profit_labour_per_kg < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
        {row.profit_labour_per_kg == null ? '—' : `₹${Math.round(row.profit_labour_per_kg).toLocaleString('en-IN')}`}
      </TableCell>
    </TableRow>
  );
}

export default function PurchaseList() {
  const [date, setDate] = useState(todayStr());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState({ field: 'profit_silver_per_kg', dir: 'desc' });
  const [sel, setSel] = useState(['Admin']);
  const [openItem, setOpenItem] = useState(null);
  const [baselineInput, setBaselineInput] = useState('');

  const fetchList = useCallback(async (d) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/purchase-list`, { params: { date: d } });
      setData(res.data);
      setBaselineInput(res.data.baseline_start);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load purchase list');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchList(date); }, [date, fetchList]);

  const patchRow = (itemName, patch) => {
    setData(prev => prev ? { ...prev, rows: prev.rows.map(r => r.item_name === itemName ? { ...r, ...patch } : r) } : prev);
  };

  const updateState = async (itemName, updates, { refetch = false } = {}) => {
    try {
      await axios.post(`${API}/purchase-list/item-state`, { item_name: itemName, date, ...updates });
      if (refetch) fetchList(date); else patchRow(itemName, updates);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Update failed');
      fetchList(date);
    }
  };

  const onSwipeLeft = (itemName) => {
    patchRow(itemName, { temp_removed: true });
    updateState(itemName, { temp_removed: true });
    toast(`${itemName} removed temporarily`, { description: 'Press Refresh to bring it back' });
  };

  const onGreenToggle = (itemName, green) => {
    patchRow(itemName, { green, green_at: green ? new Date().toISOString() : null });
    updateState(itemName, { green });
  };

  const onRefresh = async () => {
    try {
      const res = await axios.post(`${API}/purchase-list/refresh`);
      toast.success(`Restored ${res.data.restored} removed item(s)`);
      fetchList(date);
    } catch { toast.error('Refresh failed'); }
  };

  const addOrderer = async (name) => {
    try {
      await axios.post(`${API}/purchase-list/orderers`, { name });
      setData(prev => prev ? { ...prev, orderers: [...new Set([...prev.orderers, name])] } : prev);
      return true;
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to add'); return false; }
  };

  const saveBaselineStart = async () => {
    try {
      await axios.put(`${API}/purchase-list/config`, { baseline_start: baselineInput });
      toast.success('Baseline start date updated');
      fetchList(date);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const toggleSel = (name) => {
    setSel(prev => {
      if (name === 'ALL') return prev.includes('ALL') ? ['Admin'] : ['ALL'];
      const withoutAll = prev.filter(x => x !== 'ALL');
      const next = withoutAll.includes(name) ? withoutAll.filter(x => x !== name) : [...withoutAll, name];
      return next.length ? next : ['Admin'];
    });
  };

  const month = useMemo(() => parseInt(date.slice(5, 7), 10), [date]);
  const rows = useMemo(() => {
    if (!data) return [];
    let r = data.rows.filter(x => !x.temp_removed);
    r = r.filter(x => !x.season_months?.length || x.season_months.includes(month));
    if (!sel.includes('ALL')) r = r.filter(x => sel.includes(x.purview));
    const dirMul = sort.dir === 'asc' ? 1 : -1;
    r.sort((a, b) => {
      if (sort.field === 'item_name') return dirMul * a.item_name.localeCompare(b.item_name);
      const av = a[sort.field]; const bv = b[sort.field];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return dirMul * (av - bv);
    });
    return r;
  }, [data, sel, sort, month]);

  const onSort = (field) => setSort(prev => prev.field === field
    ? { field, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    : { field, dir: field === 'item_name' ? 'asc' : 'desc' });

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4" data-testid="purchase-list-page">
      <div className="flex flex-wrap items-end gap-3 justify-between">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight flex items-center gap-2">
            <ShoppingCart className="h-8 w-8 text-indigo-600" />Purchase List
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Order qty = baseline (peak stock since {data?.baseline_start || '…'}) − current stock · swipe a row left to remove it temporarily · tap a row for seasons, baseline &amp; purview
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">List date</label>
            <Input type="date" value={date} max={todayStr()} onChange={e => setDate(e.target.value)}
              className="h-9 w-40" data-testid="pl-date-picker" />
          </div>
          <Button variant="outline" size="sm" className="h-9" onClick={onRefresh} data-testid="pl-refresh-btn">
            <RotateCcw className="h-4 w-4 mr-1" />Refresh
          </Button>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="h-9" data-testid="pl-settings-btn"><Settings2 className="h-4 w-4" /></Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64 space-y-2">
              <p className="text-sm font-medium">Baseline start date</p>
              <p className="text-xs text-muted-foreground">Peak stock is tracked from this date (default 1st Jan)</p>
              <Input type="date" value={baselineInput} onChange={e => setBaselineInput(e.target.value)} data-testid="pl-baseline-start-input" />
              <Button size="sm" className="w-full" onClick={saveBaselineStart} data-testid="pl-baseline-start-save">Save</Button>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {/* Orderer filter */}
      <Card>
        <CardContent className="py-3 flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className="text-sm text-muted-foreground flex items-center gap-1"><Users className="h-4 w-4" />Orderers:</span>
          <label className="flex items-center gap-1.5 text-sm cursor-pointer" data-testid="pl-orderer-all">
            <Checkbox checked={sel.includes('ALL')} onCheckedChange={() => toggleSel('ALL')} />All
          </label>
          {(data?.orderers || ['Admin']).map(o => (
            <label key={o} className="flex items-center gap-1.5 text-sm cursor-pointer" data-testid={`pl-orderer-${o}`}>
              <Checkbox checked={sel.includes('ALL') || sel.includes(o)} disabled={sel.includes('ALL')}
                onCheckedChange={() => toggleSel(o)} />{o}
            </label>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="py-14 text-center text-muted-foreground">Computing purchase list…</div>
          ) : rows.length === 0 ? (
            <div className="py-14 text-center text-muted-foreground" data-testid="pl-empty">No items to order for this view</div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10"></TableHead>
                    <TableHead className="w-10">#</TableHead>
                    <SortHead label="Item" field="item_name" sort={sort} onSort={onSort} align="left" />
                    <SortHead label="Order Qty (kg)" field="order_qty_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Current Stock (kg)" field="current_stock_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Fine (kg)" field="fine_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Labour (₹)" field="labour_inr" sort={sort} onSort={onSort} />
                    <SortHead label="Profit Ag (g/kg)" field="profit_silver_per_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Profit Labour (₹/kg)" field="profit_labour_per_kg" sort={sort} onSort={onSort} />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r, idx) => (
                    <SwipeRow key={r.item_name} row={r} idx={idx} date={date}
                      onSwipeLeft={onSwipeLeft} onOpen={setOpenItem} onGreenToggle={onGreenToggle} />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <PurchaseItemSheet
        item={openItem ? (data?.rows.find(r => r.item_name === openItem.item_name) || openItem) : null}
        orderers={data?.orderers || ['Admin']}
        onClose={() => setOpenItem(null)}
        onUpdate={updateState}
        onAddOrderer={addOrderer}
      />
    </div>
  );
}
