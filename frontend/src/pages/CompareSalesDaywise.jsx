import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CalendarRange, Plus, Trash2, Printer, X, Minus, Eraser, Table2 } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LS_KEY = 'compareSalesDaywise_v1';

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
  const [entries, setEntries] = useState([defaultEntry()]);
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(false);
  const [fontPt, setFontPt] = useState(10);
  const [cellPad, setCellPad] = useState(4);
  const [orientation, setOrientation] = useState('portrait');
  const loadedRef = useRef(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (saved?.entries?.length) {
        setEntries(saved.entries);
        if (saved.print) {
          setFontPt(saved.print.fontPt ?? 10);
          setCellPad(saved.print.cellPad ?? 4);
          setOrientation(saved.print.orientation ?? 'portrait');
        }
        if (saved.generated) buildTable(saved.entries, true);
      }
    } catch (e) { /* corrupt storage — start fresh */ }
    loadedRef.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loadedRef.current) return;
    const saved = JSON.parse(localStorage.getItem(LS_KEY) || '{}');
    localStorage.setItem(LS_KEY, JSON.stringify({
      ...saved,
      print: { fontPt, cellPad, orientation },
    }));
  }, [fontPt, cellPad, orientation]);

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

  const buildTable = async (list, silent = false) => {
    const clean = [];
    for (const e of list) {
      const days = parseInt(e.daysBack, 10);
      if (!e.anchor || isNaN(days) || days < 0 || days > 365) {
        if (!silent) toast.error('Each year needs a valid date and days back (0–365)');
        return;
      }
      clean.push({ anchor: e.anchor, daysBack: days });
    }
    setLoading(true);
    try {
      const results = await Promise.all(clean.map((e) =>
        axios.get(`${API}/analytics/daily-sales?start_date=${addDays(e.anchor, -e.daysBack)}&end_date=${e.anchor}`)
      ));
      setColumns(clean.map((e, i) => ({
        ...e,
        year: e.anchor.slice(0, 4),
        daily: results[i].data.daily_net_kg || {},
      })));
      const prev = JSON.parse(localStorage.getItem(LS_KEY) || '{}');
      localStorage.setItem(LS_KEY, JSON.stringify({ ...prev, entries: clean, generated: true }));
      if (!silent) toast.success('Comparison table ready');
    } catch (e) {
      if (e.response?.status === 503) toast.error('Server is busy — please try again in a few seconds.');
      else toast.error(e.response?.data?.detail || 'Failed to load daily sales');
    } finally {
      setLoading(false);
    }
  };

  const clearTable = () => {
    localStorage.removeItem(LS_KEY);
    setColumns([]);
    setEntries([defaultEntry()]);
  };

  const rows = useMemo(() => {
    if (!columns.length) return [];
    const maxDays = Math.max(...columns.map((c) => c.daysBack));
    const out = [];
    for (let off = maxDays; off >= 0; off--) {
      out.push({
        off,
        cells: columns.map((c) => {
          if (off > c.daysBack) return null;
          const date = addDays(c.anchor, -off);
          return { date, weekday: weekdayOf(date), kg: c.daily[date] };
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
            <th key={i} colSpan={3} className="csd-year-head csd-group-start">
              {c.year} <span className="csd-anchor-note">(till {ddmmyyyy(c.anchor)})</span>
            </th>
          ))}
        </tr>
        <tr>
          {columns.map((_, i) => (
            <WeekHead key={i} />
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.off} className={r.off === 0 ? 'csd-day0' : ''}>
            <td className="csd-count">{r.off}</td>
            {r.cells.map((cell, i) =>
              cell ? (
                <CellGroup key={i} cell={cell} />
              ) : (
                <EmptyGroup key={i} />
              )
            )}
          </tr>
        ))}
        <tr className="csd-total-row">
          <td className="csd-count">Total</td>
          {columns.map((c, i) => (
            <td key={i} colSpan={3} className="csd-group-start csd-sales">
              {totals[i].toFixed(3)} kg
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );

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
        <div className="ml-auto flex items-center gap-2">
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
        <h1 className="csd-doc-title">Daywise Sales Comparison</h1>
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
          Day-by-day net sales (kg) counting down to a chosen date (e.g., Diwali) of each year
        </p>
      </div>

      <Card className="border-border/30 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Years to Compare</CardTitle>
          <CardDescription className="text-xs">
            For each year pick the anchor date (day 0, e.g., Diwali) and how many days back to include
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
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
            <Button size="sm" onClick={() => buildTable(entries)} disabled={loading} data-testid="make-table-btn">
              <Table2 className="h-4 w-4 mr-1.5" /> {loading ? 'Loading…' : 'Make Table'}
            </Button>
            {columns.length > 0 && (
              <>
                <Button variant="outline" size="sm" onClick={() => setPreview(true)} data-testid="print-preview-btn">
                  <Printer className="h-4 w-4 mr-1.5" /> Print Preview
                </Button>
                <Button variant="outline" size="sm" className="text-destructive" onClick={clearTable} data-testid="clear-table-btn">
                  <Eraser className="h-4 w-4 mr-1.5" /> Clear
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {columns.length > 0 && (
        <Card className="border-border/30 shadow-sm">
          <CardContent className="p-3 sm:p-5 csd-screen-wrap overflow-x-auto">
            <div className="csd-doc" style={{ '--csd-font': '13px', '--csd-pad': '4px 8px' }}>
              {renderGrid()}
            </div>
          </CardContent>
        </Card>
      )}

      {printOverlay}
    </div>
  );
}

const WeekHead = () => (
  <>
    <th className="csd-group-start">Day</th>
    <th>Date</th>
    <th>Sales (kg)</th>
  </>
);

const CellGroup = ({ cell }) => (
  <>
    <td className="csd-wd csd-group-start">{cell.weekday}</td>
    <td>{ddmm(cell.date)}</td>
    <td className={`csd-sales ${cell.kg < 0 ? 'csd-neg' : ''}`}>
      {cell.kg === undefined ? '—' : cell.kg.toFixed(3)}
    </td>
  </>
);

const EmptyGroup = () => (
  <>
    <td className="csd-group-start" />
    <td />
    <td />
  </>
);
