import { useEffect, useState } from 'react';
import { Plus, EyeOff, Trash2 } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const PurchaseItemSheet = ({ item, orderers, onClose, onUpdate, onAddOrderer, onTempDelete, onPermDelete }) => {
  const [fixedVal, setFixedVal] = useState('');
  const [newOrderer, setNewOrderer] = useState('');
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => {
    setFixedVal(item?.fixed_baseline_kg ?? '');
    setShowAdd(false);
    setNewOrderer('');
  }, [item?.item_name]);

  if (!item) return null;
  const seasons = item.season_months || [];

  const toggleMonth = (m) => {
    const next = seasons.includes(m) ? seasons.filter(x => x !== m) : [...seasons, m];
    onUpdate(item.item_name, { season_months: next.length ? next : null });
  };

  const setMode = (mode) => {
    if (mode === item.baseline_mode) return;
    const updates = { baseline_mode: mode };
    if (mode === 'fixed' && fixedVal !== '') updates.fixed_baseline_kg = parseFloat(fixedVal);
    onUpdate(item.item_name, updates, { refetch: true });
  };

  const saveFixed = () => {
    const v = parseFloat(fixedVal);
    if (isNaN(v) || v < 0) return;
    onUpdate(item.item_name, { baseline_mode: 'fixed', fixed_baseline_kg: v }, { refetch: true });
  };

  const addNew = async () => {
    const name = newOrderer.trim();
    if (!name) return;
    const ok = await onAddOrderer(name);
    if (ok) {
      onUpdate(item.item_name, { purview: name });
      setNewOrderer('');
      setShowAdd(false);
    }
  };

  return (
    <Dialog open={!!item} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto" data-testid="pl-item-sheet">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {item.item_name}
            {item.green && <Badge className="bg-green-600">Ordered</Badge>}
          </DialogTitle>
          <DialogDescription className="sr-only">Edit baseline, selling season and purview for this item</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-muted p-2">
              <p className="text-[11px] text-muted-foreground">Current Stock</p>
              <p className="font-semibold tabular-nums">{item.current_stock_kg != null ? `${item.current_stock_kg.toFixed(3)} kg` : '—'}</p>
            </div>
            <div className="rounded-lg bg-muted p-2">
              <p className="text-[11px] text-muted-foreground">Baseline</p>
              <p className="font-semibold tabular-nums">{item.baseline_kg != null ? `${item.baseline_kg.toFixed(3)} kg` : '—'}</p>
            </div>
            <div className="rounded-lg bg-muted p-2">
              <p className="text-[11px] text-muted-foreground">Order Qty</p>
              <p className="font-semibold tabular-nums">{item.order_qty_kg != null ? `${item.order_qty_kg.toFixed(3)} kg` : '—'}</p>
            </div>
          </div>

          {/* Group members */}
          {item.members?.length > 1 && (
            <div data-testid="pl-members-section">
              <p className="text-sm font-medium mb-1.5">Group members (combined into this row)</p>
              <div className="rounded-lg border divide-y">
                {item.members.map((m, i) => (
                  <div key={m.name} data-testid={`pl-member-${i}`}
                    className="flex items-center justify-between gap-2 px-3 py-1.5 text-xs">
                    <span className="font-medium truncate">{m.name}</span>
                    <span className="tabular-nums text-muted-foreground shrink-0">
                      stock {m.current_stock_kg.toFixed(3)} kg · sold {m.sold_60d_kg.toFixed(3)} kg
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Baseline */}
          <div>
            <p className="text-sm font-medium mb-1.5">Baseline</p>
            <div className="flex gap-2 mb-2">
              <Button size="sm" variant={item.baseline_mode !== 'fixed' ? 'default' : 'outline'}
                onClick={() => setMode('variable')} data-testid="pl-baseline-variable">
                Variable (peak {item.variable_baseline_kg?.toFixed(3)} kg)
              </Button>
              <Button size="sm" variant={item.baseline_mode === 'fixed' ? 'default' : 'outline'}
                onClick={() => setMode('fixed')} data-testid="pl-baseline-fixed">Fixed</Button>
            </div>
            {item.baseline_mode === 'fixed' && (
              <div className="flex gap-2">
                <Input type="number" step="0.001" min="0" value={fixedVal} placeholder="Fixed baseline (kg)"
                  onChange={e => setFixedVal(e.target.value)} className="h-9" data-testid="pl-fixed-baseline-input" />
                <Button size="sm" className="h-9" onClick={saveFixed} data-testid="pl-fixed-baseline-save">Save</Button>
              </div>
            )}
          </div>

          {/* Season */}
          <div>
            <div className="flex items-center justify-between mb-0.5">
              <p className="text-sm font-medium">Seasonal selling</p>
              <Switch checked={!!item.seasonal_enabled} data-testid="pl-seasonal-toggle"
                onCheckedChange={(v) => onUpdate(item.item_name, { seasonal_enabled: v, season_months: null })} />
            </div>
            {item.seasonal_enabled ? (
              <>
                <p className="text-xs text-muted-foreground mb-1.5">Tap the months it sells in — it will only appear in those months. No months selected yet = shows all year.</p>
                <div className="grid grid-cols-6 gap-1.5">
                  {MONTHS.map((m, i) => (
                    <button key={m} onClick={() => toggleMonth(i + 1)} data-testid={`pl-season-${i + 1}`}
                      className={`text-xs rounded-md py-1.5 border transition-colors ${seasons.includes(i + 1)
                        ? 'bg-sky-600 text-white border-sky-600' : 'bg-background hover:bg-muted border-input'}`}>
                      {m}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">Off — item shows all year. Switch on to pick its selling months.</p>
            )}
          </div>

          {/* Purview */}
          <div>
            <p className="text-sm font-medium mb-1.5">Purview (who orders this)</p>
            <div className="flex flex-wrap gap-1.5">
              {orderers.map(o => (
                <button key={o} onClick={() => onUpdate(item.item_name, { purview: o })} data-testid={`pl-purview-${o}`}
                  className={`text-xs rounded-full px-3 py-1.5 border transition-colors ${item.purview === o
                    ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-background hover:bg-muted border-input'}`}>
                  {o}
                </button>
              ))}
              <button onClick={() => setShowAdd(s => !s)} data-testid="pl-purview-add-toggle"
                className="text-xs rounded-full px-2.5 py-1.5 border border-dashed border-input hover:bg-muted inline-flex items-center gap-1">
                <Plus className="h-3 w-3" />New
              </button>
            </div>
            {showAdd && (
              <div className="flex gap-2 mt-2">
                <Input value={newOrderer} onChange={e => setNewOrderer(e.target.value)} placeholder="Salesman name"
                  className="h-9" data-testid="pl-new-orderer-input"
                  onKeyDown={e => { if (e.key === 'Enter') addNew(); }} />
                <Button size="sm" className="h-9" onClick={addNew} data-testid="pl-new-orderer-save"><Plus className="h-4 w-4" /></Button>
              </div>
            )}
          </div>

          {/* Removal */}
          <div className="pt-3 border-t space-y-2">
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => onTempDelete(item.item_name)} data-testid="pl-temp-delete-btn">
                <EyeOff className="h-4 w-4 mr-1.5" />Remove temporarily
              </Button>
              <Button variant="destructive" className="flex-1" onClick={() => onPermDelete(item.item_name)} data-testid="pl-perm-delete-btn">
                <Trash2 className="h-4 w-4 mr-1.5" />Delete permanently
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">Temporary removals come back with the Refresh button. Permanent deletions can be restored from "Permanently Deleted Items" on the list page.</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
