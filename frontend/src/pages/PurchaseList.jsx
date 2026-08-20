import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { ShoppingCart, RotateCcw, ArrowUpDown, ArrowUp, ArrowDown, Settings2, Users, CalendarRange, Trash2, Undo2, ZoomIn, ZoomOut, Search, X, FileDown, Share2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { PurchaseItemSheet } from '../components/PurchaseItemSheet';
import { buildPdf, sharePdf } from '../lib/pdfExport';

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
    <TableHead className={`whitespace-nowrap px-1 sm:px-3 ${align === 'right' ? 'text-right' : ''}`}>
      <button onClick={() => onSort(field)} data-testid={`pl-sort-${field}`}
        className={`inline-flex items-center gap-0.5 hover:text-foreground ${active ? 'text-foreground font-semibold' : ''}`}>
        {label}<Icon className="h-3 w-3 shrink-0" />
      </button>
    </TableHead>
  );
}

function ItemRow({ row, idx, onOpen, onGreenToggle, date }) {
  return (
    <TableRow
      data-testid={`pl-row-${idx}`}
      onClick={() => onOpen(row)}
      className={`cursor-pointer ${row.green
        ? 'bg-green-100 outline outline-2 -outline-offset-2 outline-green-500 hover:bg-green-100'
        : 'hover:bg-muted/40'}`}
    >
      <TableCell className="w-7 px-1 sm:px-3" onClick={(e) => e.stopPropagation()}>
        <Checkbox checked={row.green} data-testid={`pl-green-check-${idx}`}
          className="data-[state=checked]:bg-green-600 data-[state=checked]:border-green-600"
          onCheckedChange={(v) => onGreenToggle(row.item_name, !!v, date)} />
      </TableCell>
      <TableCell className="text-muted-foreground text-[10px] sm:text-xs w-6 px-0.5 sm:px-2">{idx + 1}</TableCell>
      <TableCell className="px-1 py-2 sm:px-3">
        <div className="font-medium truncate max-w-[80px] sm:max-w-[220px] md:max-w-none">
          {row.item_name}
          {row.members?.length > 1 && <span className="ml-1 text-[10px] text-indigo-500 font-semibold">×{row.members.length}</span>}
          {row.baseline_mode === 'fixed' && <span className="ml-1 text-[10px] uppercase text-amber-600 font-semibold">fixed</span>}
          {row.seasonal_enabled && <span className="ml-1 text-[10px] uppercase text-sky-600 font-semibold">seasonal</span>}
        </div>
      </TableCell>
      <TableCell className="text-right tabular-nums font-semibold px-1 py-2 sm:px-3">{row.order_qty_kg.toFixed(3)}</TableCell>
      <TableCell className={`text-right tabular-nums px-1 py-2 sm:px-3 ${row.profit_silver_tunch < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
        {row.profit_silver_tunch == null ? '—' : row.profit_silver_tunch.toFixed(1)}
      </TableCell>
      <TableCell className={`text-right tabular-nums px-1 py-2 sm:px-3 ${row.profit_labour_per_kg < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
        {row.profit_labour_per_kg == null ? '—' : `₹${Math.round(row.profit_labour_per_kg).toLocaleString('en-IN')}`}
      </TableCell>
      <TableCell className={`text-right tabular-nums px-1 py-2 sm:px-3 ${row.current_stock_kg < 0 ? 'text-red-600' : ''}`}>{row.current_stock_kg.toFixed(3)}</TableCell>
      <TableCell className="text-right tabular-nums px-1 py-2 sm:px-3">{row.fine_kg.toFixed(3)}</TableCell>
      <TableCell className="text-right tabular-nums px-1 py-2 sm:px-3">₹{Math.round(row.labour_inr).toLocaleString('en-IN')}</TableCell>
    </TableRow>
  );
}

export default function PurchaseList() {
  const [date, setDate] = useState(todayStr());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState({ field: 'profit_silver_tunch', dir: 'desc' });
  const [sel, setSel] = useState(['Admin']);
  const [openItem, setOpenItem] = useState(null);
  const [baselineInput, setBaselineInput] = useState('');
  const [seasonalOpen, setSeasonalOpen] = useState(false);
  const [seasonalItems, setSeasonalItems] = useState([]);
  const [deletedOpen, setDeletedOpen] = useState(false);
  const [deletedItems, setDeletedItems] = useState([]);
  const [zoom, setZoom] = useState(1);
  const pinchRef = useRef(null);
  const [query, setQuery] = useState('');
  const [showSug, setShowSug] = useState(false);

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
    setOpenItem(prev => prev && prev.item_name === itemName ? { ...prev, ...patch } : prev);
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

  const onTempDelete = (itemName) => {
    patchRow(itemName, { temp_removed: true });
    updateState(itemName, { temp_removed: true });
    setOpenItem(null);
    toast(`${itemName} removed temporarily`, { description: 'Press Refresh to bring it back' });
  };

  const onPermDelete = (itemName) => {
    patchRow(itemName, { perm_removed: true });
    updateState(itemName, { perm_removed: true });
    setOpenItem(null);
    toast(`${itemName} permanently deleted`, { description: 'Restore it from "Permanently Deleted Items"' });
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

  const makePdf = () => {
    if (!rows.length) { toast.error('Nothing to export'); return null; }
    return buildPdf({
      title: 'Purchase List',
      subtitle: `Date: ${date} · ${rows.length} items · Baseline since ${data?.baseline_start || ''}`,
      rows: rows.map((r, i) => [i + 1, r.item_name, r.order_qty_kg.toFixed(3), r.current_stock_kg.toFixed(3)]),
    });
  };

  const exportPdf = () => {
    const doc = makePdf();
    if (doc) { doc.save(`purchase-list-${date}.pdf`); toast.success('PDF downloaded'); }
  };

  const shareWhatsApp = async () => {
    const doc = makePdf();
    if (!doc) return;
    const res = await sharePdf(doc, `purchase-list-${date}.pdf`, `Purchase List ${date}`);
    if (res === 'shared') toast.success('Shared');
    else if (res === 'downloaded') toast('PDF downloaded', { description: 'Sharing not supported on this browser — attach the file in WhatsApp manually' });
  };

  const openSeasonalList = async () => {
    try {
      const res = await axios.get(`${API}/purchase-list/seasonal-items`);
      setSeasonalItems(res.data.items || []);
      setSeasonalOpen(true);
    } catch { toast.error('Failed to load seasonal items'); }
  };

  const openDeletedList = async () => {
    try {
      const res = await axios.get(`${API}/purchase-list/deleted-items`);
      setDeletedItems(res.data.items || []);
      setDeletedOpen(true);
    } catch { toast.error('Failed to load deleted items'); }
  };

  const undeleteItem = async (itemName) => {
    try {
      await axios.post(`${API}/purchase-list/item-state`, { item_name: itemName, perm_removed: false });
      setDeletedItems(prev => prev.filter(x => x.item_name !== itemName));
      patchRow(itemName, { perm_removed: false });
      toast.success(`${itemName} restored to the list`);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to restore'); }
  };

  const toggleSel = (name) => {
    setSel(prev => {
      if (name === 'ALL') return prev.includes('ALL') ? ['Admin'] : ['ALL'];
      const withoutAll = prev.filter(x => x !== 'ALL');
      const next = withoutAll.includes(name) ? withoutAll.filter(x => x !== name) : [...withoutAll, name];
      return next.length ? next : ['Admin'];
    });
  };

  const suggestions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !data) return [];
    const out = [];
    for (const r of data.rows) {
      if (r.perm_removed) continue;
      const names = [r.item_name, ...(r.members || []).map(m => m.name)];
      const hit = names.find(n => n.toLowerCase().includes(q));
      if (hit) out.push({ label: hit, leader: r.item_name });
      if (out.length >= 8) break;
    }
    return out;
  }, [query, data]);

  const month = useMemo(() => parseInt(date.slice(5, 7), 10), [date]);
  const rows = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    let r;
    if (q) {
      r = data.rows.filter(x => !x.perm_removed &&
        (x.item_name.toLowerCase().includes(q) || x.members?.some(m => m.name.toLowerCase().includes(q))));
    } else {
      r = data.rows.filter(x => !x.temp_removed && !x.perm_removed);
      r = r.filter(x => !(x.seasonal_enabled && x.season_months?.length) || x.season_months.includes(month));
      if (!sel.includes('ALL')) r = r.filter(x => sel.includes(x.purview));
    }
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
  }, [data, sel, sort, month, query]);

  const pinchDist = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
  const onPinchStart = (e) => {
    if (e.touches.length === 2) pinchRef.current = { d: pinchDist(e.touches), z: zoom };
  };
  const onPinchMove = (e) => {
    if (pinchRef.current && e.touches.length === 2) {
      const r = pinchDist(e.touches) / pinchRef.current.d;
      setZoom(Math.min(1.4, Math.max(0.5, +(pinchRef.current.z * r).toFixed(2))));
    }
  };
  const onPinchEnd = () => { pinchRef.current = null; };

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
            Order qty = baseline (peak stock since {data?.baseline_start || '…'}) − current stock · tap a row to manage seasons, baseline, purview &amp; removal
          </p>
          <button onClick={openDeletedList} data-testid="pl-deleted-list-btn"
            className="text-sm text-red-600 hover:text-red-700 underline underline-offset-2 mt-1 inline-flex items-center gap-1">
            <Trash2 className="h-3.5 w-3.5" />Permanently Deleted Items
          </button>
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
          <Button variant="outline" size="sm" className="h-9" onClick={openSeasonalList} data-testid="pl-seasonal-list-btn">
            <CalendarRange className="h-4 w-4 mr-1" />Seasonal
          </Button>
          <Button variant="outline" size="sm" className="h-9" onClick={exportPdf} data-testid="pl-export-pdf-btn">
            <FileDown className="h-4 w-4 mr-1" />PDF
          </Button>
          <Button variant="outline" size="sm" className="h-9 text-green-700 border-green-300 hover:bg-green-50" onClick={shareWhatsApp} data-testid="pl-share-whatsapp-btn">
            <Share2 className="h-4 w-4 mr-1" />WhatsApp
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

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input value={query} placeholder="Search items (leaders & group members)…"
          onChange={e => { setQuery(e.target.value); setShowSug(true); }}
          onFocus={() => setShowSug(true)}
          onBlur={() => setTimeout(() => setShowSug(false), 150)}
          className="pl-10 pr-9 h-10" data-testid="pl-search-input" />
        {query && (
          <button className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setQuery('')} data-testid="pl-search-clear"><X className="h-4 w-4" /></button>
        )}
        {showSug && suggestions.length > 0 && (
          <div className="absolute z-30 mt-1 w-full rounded-md border bg-popover shadow-lg max-h-64 overflow-y-auto"
            data-testid="pl-search-suggestions">
            {suggestions.map((s, i) => (
              <button key={`${s.label}-${i}`} data-testid={`pl-search-suggestion-${i}`}
                onMouseDown={(e) => { e.preventDefault(); setQuery(s.leader); setShowSug(false); }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-muted flex items-center justify-between gap-2">
                <span className="truncate">{s.label}</span>
                {s.label !== s.leader && <span className="text-xs text-muted-foreground shrink-0">→ {s.leader}</span>}
              </button>
            ))}
          </div>
        )}
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

      {/* Zoom controls */}
      <div className="flex items-center justify-end gap-0.5 -mt-1 -mb-2">
        <span className="text-[11px] text-muted-foreground mr-1">Pinch table or use</span>
        <Button variant="ghost" size="sm" className="h-7 px-2" data-testid="pl-zoom-out"
          onClick={() => setZoom(z => Math.max(0.5, +(z - 0.1).toFixed(2)))}><ZoomOut className="h-4 w-4" /></Button>
        <button className="text-xs text-muted-foreground w-10 text-center tabular-nums" data-testid="pl-zoom-reset"
          onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</button>
        <Button variant="ghost" size="sm" className="h-7 px-2" data-testid="pl-zoom-in"
          onClick={() => setZoom(z => Math.min(1.4, +(z + 0.1).toFixed(2)))}><ZoomIn className="h-4 w-4" /></Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="py-14 text-center text-muted-foreground">Computing purchase list…</div>
          ) : rows.length === 0 ? (
            <div className="py-14 text-center space-y-3 px-4" data-testid="pl-empty">
              {(data?.rows?.length || 0) > 0 ? (
                <>
                  <p className="text-muted-foreground" data-testid="pl-empty-filtered">
                    All <span className="font-semibold text-foreground">{data.rows.length}</span> item(s) are hidden by current filters
                    — {data.rows.filter(x => x.temp_removed).length} removed temporarily, {data.rows.filter(x => x.perm_removed).length} permanently deleted, {data.rows.filter(x => x.seasonal_enabled && x.season_months?.length && !x.season_months.includes(month)).length} out of season, rest under other orderers.
                  </p>
                  <div className="flex justify-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => setSel(['ALL'])} data-testid="pl-show-all-btn">Show all orderers</Button>
                    <Button size="sm" variant="outline" onClick={onRefresh} data-testid="pl-restore-swiped-btn">Restore temporary removals</Button>
                  </div>
                </>
              ) : data?.window_txn_count === 0 ? (
                <p className="text-muted-foreground" data-testid="pl-empty-nodata">
                  No transactions found between {data.baseline_start} and {data.date} — upload data for this period first.
                </p>
              ) : (
                <p className="text-muted-foreground">No items to order for this date — every item is at its peak stock.</p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto" onTouchStart={onPinchStart} onTouchMove={onPinchMove}
              onTouchEnd={onPinchEnd} style={{ touchAction: 'pan-x pan-y' }} data-testid="pl-table-wrapper">
              <div style={{ zoom }}>
                <Table className="text-xs sm:text-sm">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-7 px-1 sm:px-3"></TableHead>
                    <TableHead className="w-6 px-0.5 sm:px-2">#</TableHead>
                    <SortHead label="Item" field="item_name" sort={sort} onSort={onSort} align="left" />
                    <SortHead label="Order kg" field="order_qty_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Ag tunch" field="profit_silver_tunch" sort={sort} onSort={onSort} />
                    <SortHead label="Lbr ₹/kg" field="profit_labour_per_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Stock kg" field="current_stock_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Fine kg" field="fine_kg" sort={sort} onSort={onSort} />
                    <SortHead label="Labour ₹" field="labour_inr" sort={sort} onSort={onSort} />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r, idx) => (
                    <ItemRow key={r.item_name} row={r} idx={idx} date={date}
                      onOpen={setOpenItem} onGreenToggle={onGreenToggle} />
                  ))}
                </TableBody>
              </Table>
              </div>
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
        onTempDelete={onTempDelete}
        onPermDelete={onPermDelete}
      />

      {/* Permanently deleted items dialog */}
      <Dialog open={deletedOpen} onOpenChange={setDeletedOpen}>
        <DialogContent className="max-w-md" data-testid="pl-deleted-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Trash2 className="h-5 w-5 text-red-600" />Permanently Deleted Items</DialogTitle>
            <DialogDescription className="sr-only">Restore items permanently deleted from the purchase list</DialogDescription>
          </DialogHeader>
          {deletedItems.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center" data-testid="pl-deleted-empty">
              No permanently deleted items.
            </p>
          ) : (
            <div className="max-h-[60vh] overflow-y-auto space-y-1.5">
              {deletedItems.map((s, i) => (
                <div key={s.item_name} data-testid={`pl-deleted-item-${i}`}
                  className="rounded-lg border border-input px-3 py-2 flex items-center justify-between gap-2">
                  <span className="font-medium text-sm truncate">{s.item_name}</span>
                  <Button size="sm" variant="outline" className="h-8 shrink-0" data-testid={`pl-undelete-btn-${i}`}
                    onClick={() => undeleteItem(s.item_name)}>
                    <Undo2 className="h-4 w-4 mr-1" />Undelete
                  </Button>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Seasonal items dialog */}
      <Dialog open={seasonalOpen} onOpenChange={setSeasonalOpen}>
        <DialogContent className="max-w-md" data-testid="pl-seasonal-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><CalendarRange className="h-5 w-5 text-sky-600" />Seasonal items</DialogTitle>
            <DialogDescription className="sr-only">All items with seasonal selling enabled</DialogDescription>
          </DialogHeader>
          {seasonalItems.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center" data-testid="pl-seasonal-empty">
              No seasonal items yet — open an item and switch on "Seasonal selling".
            </p>
          ) : (
            <div className="max-h-[60vh] overflow-y-auto space-y-1.5">
              {seasonalItems.map((s, i) => (
                <button key={s.item_name} data-testid={`pl-seasonal-item-${i}`}
                  onClick={() => {
                    setSeasonalOpen(false);
                    setOpenItem(data?.rows.find(r => r.item_name === s.item_name) || s);
                  }}
                  className="w-full text-left rounded-lg border border-input hover:bg-muted px-3 py-2 flex items-center justify-between gap-2">
                  <span className="font-medium text-sm truncate">{s.item_name}</span>
                  <span className="flex flex-wrap gap-1 justify-end">
                    {(s.season_months || []).map(m => (
                      <Badge key={m} variant="outline" className="text-[10px] px-1.5 bg-sky-50 text-sky-700 border-sky-200">
                        {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m - 1]}
                      </Badge>
                    ))}
                  </span>
                </button>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
