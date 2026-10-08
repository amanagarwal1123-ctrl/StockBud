import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { CalendarRange, Plus, Trash2, Printer, X, Minus, Table2, FileText, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const PRINT_LS_KEY = 'compareSalesDaywise_print_v2';

const pad2 = (n) => String(n).padStart(2, '0');
const fmtYMD = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const todayStr = () => fmtYMD(new Date());
const addDays = (dateStr, delta) => {
  const [y, m, dd] = dateStr.split('-').map(Number);
  return fmtYMD(new Date(y, m - 1, dd + delta));
};
const weekdayOf = (dateStr) => {
  const [y, m, dd] = dateStr.split('-').map(Number);
  return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][new Date(y, m - 1, dd).getDay()];
};
const ddmm = (dateStr) => `${dateStr.slice(8, 10)}/${dateStr.slice(5, 7)}`;
const ddmmyyyy = (dateStr) => `${dateStr.slice(8, 10)}/${dateStr.slice(5, 7)}/${dateStr.slice(0, 4)}`;

const defaultEntry = () => ({ anchor: todayStr(), daysBack: 15 });

export default function CompareSalesDaywise() {
  const [tables, setTables] = useState([]);
  const [activeId, setActiveId] = useState(null); // comparison id or 'new'
  const [columns, setColumns] = useState([]);
  const [entries, setEntries] = useState([defaultEntry()]);
  const [tableName, setTableName] = useState('');
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [preview, setPreview] = useState(false);
  const [fontPt, setFontPt] = useState(10);
  const [cellPad, setCellPad] = useState(4);
  const [orientation, setOrientation] = useState('portrait');
  const [showCum, setShowCum] = useState(true);
  const [loadedPrefs, setLoadedPrefs] = useState(false);

  useEffect(() => {
    try {
      const p = JSON.parse(localStorage.getItem(PRINT_LS_KEY) || 'null');
      if (p) {
        setFontPt(p.fontPt ?? 10);
        setCellPad(p.cellPad ?? 4);
        setOrientation(p.orientation ?? 'portrait');
        setShowCum(p.showCum ?? true);
      }
    } catch (e) { /* start fresh */ }
    setLoadedPrefs(true);
    loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loadedPrefs) return;
    localStorage.setItem(PRINT_LS_KEY, JSON.stringify({ fontPt, cellPad, orientation, showCum }));
  }, [fontPt, cellPad, orientation, showCum, loadedPrefs]);

  const loadList = async () => {
    setListLoading(true);
    try {
      const r = await axios.get(`${API}/daywise-comparisons`);
      const list = r.data.comparisons || [];
      setTables(list);
      if (list.length) {
        openTable(list[0]);
      } else {
        setActiveId('new');
      }
    } catch (e) {
      toast.error('Failed to load saved tables');
      setActiveId('new');
    } finally {
      setListLoading(false);
    }
  };

  const fetchColumns = async (entryList) => {
    const results = await Promise.all(entryList.map((e) =>
      axios.get(`${API}/analytics/daily-sales?start_date=${addDays(e.anchor, -e.daysBack)}&end_date=${e.anchor}`)
    ));
    return entryList.map((e, i) => ({
      ...e,
      year: e.anchor.slice(0, 4),
      daily: results[i].data.daily_net_kg || {},
    }));
  };

  const openTable = async (table) => {
    setActiveId(table.id);
    setColumns([]);
    setLoading(true);
    try {
      setColumns(await fetchColumns(table.entries));
    } catch (e) {
      if (e.response?.status === 503) toast.error('Server is busy — please try again in a few seconds.');
      else toast.error('Failed to load sales data');
    } finally {
      setLoading(false);
    }
  };

  const activeTable = tables.find((t) => t.id === activeId);

  const updateEntry = (i, field, value) => {
    setEntries((prev) => prev.map((e, idx) => (idx === i ? { ...e, [field]: value } : e)));
  };

  const addYear = () => {
    setEntries((prev) => {
      const last = prev[prev.length - 1];
      const [y, m, d] = last.anchor.split('-').map(Number);
      return [...prev, { anchor: fmtYMD(new Date(y - 1, m - 1, d)), daysBack: last.daysBack }];
    });
  };

  const removeEntry = (i) => setEntries((prev) => prev.filter((_, idx) => idx !== i));

  const makeTable = async () => {
    const clean = [];
    for (const e of entries) {
      const days = parseInt(e.daysBack, 10);
      if (!e.anchor || isNaN(days) || days < 0 || days > 365) {
        toast.error('Each year needs a valid date and days back (0–365)');
        return;
      }
      clean.push({ anchor: e.anchor, daysBack: days });
    }
    setLoading(true);
    try {
      const r = await axios.post(`${API}/daywise-comparisons`, { name: tableName.trim() || null, entries: clean });
      const doc = r.data;
      setTables((prev) => [...prev, doc]);
      setEntries([defaultEntry()]);
      setTableName('');
      setActiveId(doc.id);
      setColumns(await fetchColumns(doc.entries));
      toast.success(`Table "${doc.name}" saved — visible to all admins`);
    } catch (e) {
      if (e.response?.status === 503) toast.error('Server is busy — please try again in a few seconds.');
      else toast.error(e.response?.data?.detail || 'Failed to create table');
    } finally {
      setLoading(false);
    }
  };

  const deleteTable = async (table) => {
    if (!window.confirm(`Delete table "${table.name}" for all admins?`)) return;
    try {
      await axios.delete(`${API}/daywise-comparisons/${table.id}`);
      const remaining = tables.filter((t) => t.id !== table.id);
      setTables(remaining);
      toast.success('Table deleted');
      if (activeId === table.id) {
        if (remaining.length) openTable(remaining[0]);
        else { setActiveId('new'); setColumns([]); }
      }
    } catch (e) {
      toast.error('Failed to delete table');
    }
  };

  const rows = useMemo(() => {
    if (!columns.length) return [];
    const maxDays = Math.max(...columns.map((c) => c.daysBack));
    const cums = columns.map(() => 0);
    const out = [];
    for (let off = maxDays; off >= 0; off--) {
      out.push({
        off,
        cells: columns.map((c, i) => {
          if (off > c.daysBack) return null;
          const date = addDays(c.anchor, -off);
          const kg = c.daily[date];
          cums[i] += kg || 0;
          return { date, weekday: weekdayOf(date), kg, cum: cums[i] };
        }),
      });
    }
    return out;
  }, [columns]);

  const totals = useMemo(
    () => columns.map((c) => Object.values(c.daily).reduce((s, v) => s + v, 0)),
    [columns]
  );

  useEffect(() => {
    document.body.classList.toggle('csd-printing', preview);
    return () => document.body.classList.remove('csd-printing');
  }, [preview]);

  const renderGrid = () => (
    <table className="csd-table" data-testid="comparison-table">
      <thead>
        <tr>
          <th rowSpan={2} className="csd-count-col">Days<br />Before</th>
          {columns.map((c, i) => (
            <th key={i} colSpan={showCum ? 4 : 3} className="csd-year-head csd-group-start">
              {c.year} <span className="csd-anchor-note">(till {ddmmyyyy(c.anchor)})</span>
            </th>
          ))}
        </tr>
        <tr>
          {columns.map((_, i) => (
            <WeekHead key={i} showCum={showCum} />
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.off} className={r.off === 0 ? 'csd-day0' : ''}>
            <td className="csd-count">{r.off}</td>
            {r.cells.map((cell, i) =>
              cell ? (
                <CellGroup key={i} cell={cell} showCum={showCum} />
              ) : (
                <EmptyGroup key={i} showCum={showCum} />
              )
            )}
          </tr>
        ))}
        <tr className="csd-total-row">
          <td className="csd-count">Total</td>
          {columns.map((c, i) => (
            <td key={i} colSpan={showCum ? 4 : 3} className="csd-group-start csd-sales">
              {totals[i].toFixed(3)} kg
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );

  const viewPdf = () => {
    const doc = new jsPDF({ orientation, unit: 'pt', format: 'a4' });
    const sub = showCum ? ['Day', 'Date', 'Sales', 'Cum.'] : ['Day', 'Date', 'Sales'];
    const head = [
      [{ content: 'Days\nBefore', rowSpan: 2, styles: { valign: 'middle' } },
       ...columns.map((c) => ({ content: `${c.year} (till ${ddmmyyyy(c.anchor)})`, colSpan: sub.length }))],
      columns.flatMap(() => sub),
    ];
    const fmtKg = (v) => (v === undefined ? '\u2014' : v.toFixed(3));
    const body = rows.map((r) => [
      String(r.off),
      ...r.cells.flatMap((cell) => cell
        ? (showCum
            ? [cell.weekday, ddmm(cell.date), fmtKg(cell.kg), cell.cum.toFixed(3)]
            : [cell.weekday, ddmm(cell.date), fmtKg(cell.kg)])
        : Array(sub.length).fill('')),
    ]);
    body.push(['Total', ...columns.flatMap((c, i) => {
      const t = `${totals[i].toFixed(3)} kg`;
      return showCum ? ['', '', t, ''] : ['', '', t];
    })]);
    const pageW = doc.internal.pageSize.getWidth();
    doc.setFont('times', 'bold');
    doc.setFontSize(15);
    doc.setTextColor(0);
    doc.text(activeTable?.name || 'Daywise Sales Comparison', pageW / 2, 38, { align: 'center' });
    doc.setFont('times', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(70);
    doc.text(`Net sales (kg) \u00b7 countdown to ${columns.map((c) => ddmmyyyy(c.anchor)).join(' / ')}`, pageW / 2, 52, { align: 'center' });
    autoTable(doc, {
      startY: 64,
      head,
      body,
      theme: 'grid',
      styles: { font: 'times', fontSize: fontPt, cellPadding: cellPad, halign: 'center', textColor: 0, lineColor: 0, lineWidth: 0.4 },
      headStyles: { fillColor: 255, textColor: 0, fontStyle: 'bold', lineWidth: 0.6 },
      didParseCell: (data) => {
        if (data.section !== 'body') return;
        const col = data.column.index;
        if (col === 0) {
          data.cell.styles.fontStyle = 'bold';
        } else {
          const within = (col - 1) % sub.length;
          if (within === 0 || within === 2) data.cell.styles.fontStyle = 'bold';
        }
        if (data.row.index === rows.length - 1) data.cell.styles.fillColor = [244, 238, 222];
        if (data.row.index === rows.length) data.cell.styles.fontStyle = 'bold';
      },
    });
    window.open(doc.output('bloburl'), '_blank');
  };

  const printOverlay = preview ? createPortal(
    <div className="csd-print-overlay fixed inset-0 z-[100] bg-white overflow-auto" data-testid="print-overlay">
      <div className="csd-toolbar sticky top-0 z-10 bg-zinc-900 text-white px-4 py-2.5 flex flex-wrap items-center gap-3 shadow-md">
        <span className="text-sm font-semibold mr-2">Print Preview</span>
        <div className="flex items-center gap-1 bg-zinc-800 rounded-md p-0.5">
          <button
            onClick={() => setOrientation('portrait')}
            className={`px-2.5 py-1 text-xs rounded ${orientation === 'portrait' ? 'bg-white text-zinc-900 font-semibold' : 'text-zinc-300'}`}
            data-testid="orientation-portrait"
          >Vertical</button>
          <button
            onClick={() => setOrientation('landscape')}
            className={`px-2.5 py-1 text-xs rounded ${orientation === 'landscape' ? 'bg-white text-zinc-900 font-semibold' : 'text-zinc-300'}`}
            data-testid="orientation-landscape"
          >Horizontal</button>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-zinc-400">Font</span>
          <button onClick={() => setFontPt((v) => Math.max(7, v - 1))} className="w-6 h-6 rounded bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center" data-testid="font-dec"><Minus className="h-3 w-3" /></button>
          <span className="w-9 text-center font-mono" data-testid="font-size-value">{fontPt}pt</span>
          <button onClick={() => setFontPt((v) => Math.min(16, v + 1))} className="w-6 h-6 rounded bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center" data-testid="font-inc"><Plus className="h-3 w-3" /></button>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-zinc-400">Spacing</span>
          <button onClick={() => setCellPad((v) => Math.max(1, v - 1))} className="w-6 h-6 rounded bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center" data-testid="spacing-dec"><Minus className="h-3 w-3" /></button>
          <span className="w-7 text-center font-mono" data-testid="spacing-value">{cellPad}</span>
          <button onClick={() => setCellPad((v) => Math.min(14, v + 1))} className="w-6 h-6 rounded bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center" data-testid="spacing-inc"><Plus className="h-3 w-3" /></button>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-zinc-400">Cumulative</span>
          <Switch checked={showCum} onCheckedChange={setShowCum} data-testid="toolbar-cum-toggle" className="scale-75" />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" variant="secondary" className="h-7 text-xs" onClick={viewPdf} data-testid="view-pdf-btn">
            <FileText className="h-3.5 w-3.5 mr-1.5" /> View PDF
          </Button>
          <Button size="sm" className="h-7 text-xs" onClick={() => window.print()} data-testid="do-print-btn">
            <Printer className="h-3.5 w-3.5 mr-1.5" /> Print
          </Button>
          <button onClick={() => setPreview(false)} className="w-7 h-7 rounded bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center" data-testid="close-preview-btn">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div
        className="csd-print-area csd-doc mx-auto my-6 px-6"
        style={{ '--csd-font': `${fontPt}pt`, '--csd-pad': `${cellPad}px ${cellPad + 3}px`, maxWidth: orientation === 'landscape' ? '1100px' : '780px' }}
      >
        <h1 className="csd-doc-title">{activeTable?.name || 'Daywise Sales Comparison'}</h1>
        <p className="csd-doc-sub">Net sales (kg) · countdown of days before {columns.map((c) => `${ddmmyyyy(c.anchor)}`).join(' / ')}</p>
        {renderGrid()}
      </div>
    </div>,
    document.body
  ) : null;

  return (
    <div className="space-y-6" data-testid="compare-sales-daywise-page">
      <style>{`
        .csd-doc { font-family: 'Literata', 'Bookerly', Georgia, 'Times New Roman', serif; color: #000; }
        .csd-doc-title { font-size: 1.35em; font-weight: 700; text-align: center; margin-bottom: 2px; }
        .csd-doc-sub { text-align: center; font-size: 0.8em; color: #333; margin-bottom: 14px; }
        .csd-table { border-collapse: collapse; width: 100%; font-size: var(--csd-font, 13px); }
        .csd-table th, .csd-table td {
          padding: var(--csd-pad, 4px 7px);
          text-align: center; white-space: nowrap;
          border-top: 1px solid #000; border-bottom: 1px solid #000;
          border-left: 1px solid #cfcfcf; border-right: 1px solid #cfcfcf;
        }
        .csd-table .csd-group-start { border-left: 1.5px solid #000; }
        .csd-table .csd-count-col, .csd-table .csd-count { border-left: 1.5px solid #000; font-weight: 600; }
        .csd-table tr th:last-child, .csd-table tr td:last-child { border-right: 1.5px solid #000; }
        .csd-table thead th { font-weight: 600; }
        .csd-year-head { font-weight: 700 !important; font-size: 1.05em; }
        .csd-anchor-note { font-weight: 400; font-size: 0.78em; color: #444; }
        .csd-wd { font-weight: 700; }
        .csd-sales { font-weight: 700; font-variant-numeric: tabular-nums; }
        .csd-cum { font-weight: 500; font-variant-numeric: tabular-nums; color: #222; }
        .csd-screen-wrap .csd-cum { color: inherit; opacity: 0.85; }
        .csd-neg { color: #b00000; }
        .csd-day0 td { border-top: 2px solid #000; background: #f7f3e8; }
        .csd-total-row td { border-top: 2px solid #000; font-weight: 700; }
        .csd-table tr { page-break-inside: avoid; }
        .csd-screen-wrap .csd-doc { color: inherit; }
        .csd-screen-wrap .csd-table th, .csd-screen-wrap .csd-table td {
          border-top-color: hsl(var(--border)); border-bottom-color: hsl(var(--border));
        }
        @media print {
          @page { size: A4 ${orientation}; margin: 10mm; }
          body.csd-printing #root { display: none !important; }
          body.csd-printing [data-sonner-toaster] { display: none !important; }
          .csd-toolbar { display: none !important; }
          .csd-print-overlay { position: static !important; overflow: visible !important; }
          .csd-print-area { max-width: none !important; margin: 0 !important; padding: 0 !important; }
          .csd-day0 td { background: #f1ead7 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>

      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
          <CalendarRange className="h-7 w-7 text-primary" /> Compare Sales Daywise
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Day-by-day net sales (kg) counting down to a chosen date (e.g., Diwali) — tables are saved and shared across all admins
        </p>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-2" data-testid="comparison-tabs">
        {tables.map((t) => (
          <button
            key={t.id}
            onClick={() => openTable(t)}
            className={`px-3.5 py-1.5 rounded-md text-sm border transition-colors ${activeId === t.id ? 'bg-primary text-primary-foreground border-primary font-semibold' : 'bg-card border-border/50 hover:border-primary/50'}`}
            data-testid={`comparison-tab-${t.id}`}
          >
            {t.name}
          </button>
        ))}
        <button
          onClick={() => { setActiveId('new'); setColumns([]); }}
          className={`px-3.5 py-1.5 rounded-md text-sm border transition-colors flex items-center gap-1.5 ${activeId === 'new' ? 'bg-primary text-primary-foreground border-primary font-semibold' : 'bg-card border-dashed border-border/60 hover:border-primary/50'}`}
          data-testid="new-table-tab"
        >
          <Plus className="h-3.5 w-3.5" /> New Table
        </button>
        {listLoading && <span className="text-xs text-muted-foreground">Loading…</span>}
      </div>

      {activeId === 'new' && (
        <Card className="border-border/30 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">New Comparison Table</CardTitle>
            <CardDescription className="text-xs">
              For each year pick the anchor date (day 0, e.g., Diwali) and how many days back to include. Saved tables appear for every admin on every device.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Table name (optional)</label>
              <Input
                value={tableName}
                onChange={(e) => setTableName(e.target.value)}
                placeholder="e.g., Diwali 2026 vs 2025"
                className="h-9 w-72"
                maxLength={60}
                data-testid="table-name-input"
              />
            </div>
            {entries.map((e, i) => (
              <div key={i} className="flex flex-wrap items-end gap-3" data-testid={`compare-entry-${i}`}>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Anchor date (day 0)</label>
                  <Input
                    type="date"
                    value={e.anchor}
                    onChange={(ev) => updateEntry(i, 'anchor', ev.target.value)}
                    className="h-9 w-44"
                    data-testid={`compare-entry-date-${i}`}
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Days back</label>
                  <Input
                    type="number"
                    min="0"
                    max="365"
                    value={e.daysBack}
                    onChange={(ev) => updateEntry(i, 'daysBack', ev.target.value)}
                    className="h-9 w-28"
                    data-testid={`compare-entry-days-${i}`}
                  />
                </div>
                <div className="text-xs text-muted-foreground pb-2.5 font-mono">
                  {e.anchor ? `${e.anchor.slice(0, 4)} · ${ddmm(addDays(e.anchor, -(parseInt(e.daysBack, 10) || 0)))} → ${ddmm(e.anchor)}` : ''}
                </div>
                {entries.length > 1 && (
                  <Button variant="ghost" size="sm" className="h-9 text-destructive" onClick={() => removeEntry(i)} data-testid={`remove-entry-${i}`}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
            <div className="flex flex-wrap gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={addYear} disabled={loading || entries.length >= 6} data-testid="add-year-btn">
                <Plus className="h-4 w-4 mr-1.5" /> Add Year
              </Button>
              <Button size="sm" onClick={makeTable} disabled={loading} data-testid="make-table-btn">
                <Table2 className="h-4 w-4 mr-1.5" /> {loading ? 'Saving…' : 'Make & Save Table'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {activeId !== 'new' && activeTable && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => openTable(activeTable)} disabled={loading} data-testid="refresh-table-btn">
              <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPreview(true)} disabled={!columns.length} data-testid="print-preview-btn">
              <Printer className="h-4 w-4 mr-1.5" /> Print Preview
            </Button>
            <Button variant="outline" size="sm" className="text-destructive" onClick={() => deleteTable(activeTable)} data-testid="delete-table-btn">
              <Trash2 className="h-4 w-4 mr-1.5" /> Delete Table
            </Button>
            <div className="flex items-center gap-2 pl-2 self-center">
              <Switch checked={showCum} onCheckedChange={setShowCum} data-testid="cum-toggle" />
              <span className="text-xs text-muted-foreground">Cumulative column</span>
            </div>
            <span className="text-xs text-muted-foreground ml-auto">
              Created by {activeTable.created_by} · live data, auto-refreshed
            </span>
          </div>

          {loading && !columns.length ? (
            <Card className="border-border/30 shadow-sm">
              <CardContent className="p-8 text-center text-sm text-muted-foreground">Loading sales data…</CardContent>
            </Card>
          ) : columns.length > 0 ? (
            <Card className="border-border/30 shadow-sm">
              <CardContent className="p-3 sm:p-5 csd-screen-wrap overflow-x-auto">
                <div className="csd-doc" style={{ '--csd-font': '13px', '--csd-pad': '4px 8px' }}>
                  {renderGrid()}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </>
      )}

      {printOverlay}
    </div>
  );
}

const WeekHead = ({ showCum }) => (
  <>
    <th className="csd-group-start">Day</th>
    <th>Date</th>
    <th>Sales (kg)</th>
    {showCum && <th>Cum. (kg)</th>}
  </>
);

const CellGroup = ({ cell, showCum }) => (
  <>
    <td className="csd-wd csd-group-start">{cell.weekday}</td>
    <td>{ddmm(cell.date)}</td>
    <td className={`csd-sales ${cell.kg < 0 ? 'csd-neg' : ''}`}>
      {cell.kg === undefined ? '—' : cell.kg.toFixed(3)}
    </td>
    {showCum && (
      <td className={`csd-cum ${cell.cum < 0 ? 'csd-neg' : ''}`}>{cell.cum.toFixed(3)}</td>
    )}
  </>
);

const EmptyGroup = ({ showCum }) => (
  <>
    <td className="csd-group-start" />
    <td />
    <td />
    {showCum && <td />}
  </>
);
