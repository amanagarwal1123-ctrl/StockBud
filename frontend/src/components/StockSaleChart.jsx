import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Badge } from '@/components/ui/badge';

const ratioMeta = (ratio) => {
  if (ratio === null || ratio === undefined) return { label: 'No sales', cls: 'bg-red-100 text-red-700 border-red-300' };
  if (ratio < 0) return { label: 'Neg. stock, selling', cls: 'bg-green-100 text-green-700 border-green-300' };
  if (ratio <= 2) return { label: 'Healthy', cls: 'bg-green-100 text-green-700 border-green-300' };
  if (ratio <= 4) return { label: 'Watch', cls: 'bg-amber-100 text-amber-700 border-amber-300' };
  return { label: 'Overstocked', cls: 'bg-red-100 text-red-700 border-red-300' };
};

export const RatioPill = ({ ratio }) => {
  const rm = ratioMeta(ratio);
  return (
    <span className={`inline-block rounded-full border px-1.5 py-0.5 text-[10px] font-bold font-mono ${rm.cls}`} title={rm.label} data-testid="ratio-pill">
      {ratio !== null && ratio !== undefined ? `${ratio}×` : '—'}
    </span>
  );
};

export const StockSaleChart = ({ drill, loading }) => {
  if (loading) return <div className="py-8 text-center text-sm text-muted-foreground" data-testid="stock-sale-chart-loading">Loading stock vs sale…</div>;
  if (!drill) return <div className="py-8 text-center text-sm text-red-600" data-testid="stock-sale-chart-error">Could not load chart</div>;
  const rows = drill.days || [];
  const rm = ratioMeta(drill.stock_to_sale_ratio);
  return (
    <div className="space-y-2" data-testid="stock-sale-chart">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs font-semibold mr-1 truncate max-w-[40vw] sm:max-w-none">{drill.name}</span>
        <Badge variant="outline" className="text-[10px] bg-indigo-50 text-indigo-700 border-indigo-300" data-testid="avg-stock-badge">
          Avg Stock {(drill.avg_stock_kg ?? 0).toFixed(3)} kg
        </Badge>
        <Badge variant="outline" className="text-[10px] bg-rose-50 text-rose-700 border-rose-300" data-testid="period-sale-badge">
          Sale {(drill.total_sold_kg ?? 0).toFixed(3)} kg
        </Badge>
        {drill.avg_monthly_sale_kg !== undefined && (
          <Badge variant="outline" className="text-[10px] bg-rose-50 text-rose-700 border-rose-300" data-testid="monthly-sale-badge">
            Sale/Mo {(drill.avg_monthly_sale_kg ?? 0).toFixed(3)} kg
          </Badge>
        )}
        <Badge variant="outline" className={`text-[10px] font-bold ${rm.cls}`} data-testid="stock-sale-ratio-badge">
          Stock:Sale {drill.stock_to_sale_ratio !== null && drill.stock_to_sale_ratio !== undefined ? `${drill.stock_to_sale_ratio}×` : '—'} · {rm.label}
        </Badge>
      </div>
      <div className="h-[230px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 5, right: 0, left: -6, bottom: 0 }} barCategoryGap="12%">
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="date" tickFormatter={(v) => v.slice(8, 10)} tick={{ fontSize: 9 }} tickLine={false} interval="preserveStartEnd" minTickGap={6} />
            <YAxis yAxisId="stock" tick={{ fontSize: 9, fill: '#6366f1' }} tickLine={false} axisLine={false} width={42} />
            <YAxis yAxisId="sale" orientation="right" tick={{ fontSize: 9, fill: '#e11d48' }} tickLine={false} axisLine={false} width={38} />
            <Tooltip
              formatter={(v, k) => [`${Number(v).toFixed(3)} kg`, k === 'stock_kg' ? 'Stock (day opening)' : 'Sold that day']}
              labelFormatter={(l) => l}
              contentStyle={{ fontSize: 11, borderRadius: 8 }}
            />
            <Legend formatter={(v) => <span style={{ fontSize: 10 }}>{v === 'stock_kg' ? 'Day-opening net stock (kg)' : 'Day sale (kg)'}</span>} />
            <Bar yAxisId="stock" dataKey="stock_kg" fill="#a5b4fc" stroke="#6366f1" strokeWidth={0.5} radius={[3, 3, 0, 0]} />
            <Line yAxisId="sale" dataKey="sold_kg" stroke="#e11d48" strokeWidth={2.2} dot={{ r: 1.6, fill: '#e11d48' }} activeDot={{ r: 4 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[10px] text-muted-foreground leading-snug">
        Bars = opening net stock each day · Line = that day&apos;s sale ·{' '}
        <span className="font-medium">Stock:Sale</span> = avg stock ÷ avg monthly sale —{' '}
        <span className="text-green-600 font-medium">≤2× healthy</span>,{' '}
        <span className="text-amber-600 font-medium">2–4× watch</span>,{' '}
        <span className="text-red-600 font-medium">&gt;4× stock isn&apos;t converting to sales</span>.
      </p>
    </div>
  );
};
