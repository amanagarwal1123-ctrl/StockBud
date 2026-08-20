import { useState } from 'react';
import axios from 'axios';
import { Pencil, Trash2, Check, X, UserCog } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const OrdererManageDialog = ({ open, onClose, orderers, counts, onChanged }) => {
  const [renaming, setRenaming] = useState(null);
  const [newName, setNewName] = useState('');
  const [deleting, setDeleting] = useState(null);
  const [reassignTo, setReassignTo] = useState('Admin');

  const salesmen = orderers.filter(o => o !== 'Admin');

  const doRename = async (name) => {
    const nn = newName.trim();
    if (!nn) { toast.error('Enter a name'); return; }
    try {
      const res = await axios.put(`${API}/purchase-list/orderers/${encodeURIComponent(name)}`, { new_name: nn });
      toast.success(`Renamed to ${nn} — ${res.data.items_moved} item(s) moved`);
      setRenaming(null);
      onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || 'Rename failed'); }
  };

  const doDelete = async (name) => {
    try {
      const res = await axios.delete(`${API}/purchase-list/orderers/${encodeURIComponent(name)}`,
        { params: { reassign_to: reassignTo } });
      toast.success(`${name} deleted — ${res.data.items_reassigned} item(s) moved to ${res.data.reassigned_to}`);
      setDeleting(null);
      onChanged();
    } catch (e) { toast.error(e.response?.data?.detail || 'Delete failed'); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md" data-testid="om-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><UserCog className="h-5 w-5 text-indigo-600" />Manage Orderers</DialogTitle>
          <DialogDescription className="sr-only">Rename or delete salesmen and reassign their items</DialogDescription>
        </DialogHeader>
        {salesmen.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center" data-testid="om-empty">
            No salesmen yet — add one from any item's purview section.
          </p>
        ) : (
          <div className="space-y-2 max-h-[60vh] overflow-y-auto">
            {salesmen.map(name => (
              <div key={name} className="rounded-lg border border-input px-3 py-2" data-testid={`om-row-${name}`}>
                {renaming === name ? (
                  <div className="flex items-center gap-2">
                    <Input value={newName} onChange={e => setNewName(e.target.value)} className="h-8"
                      data-testid="om-rename-input" onKeyDown={e => { if (e.key === 'Enter') doRename(name); }} autoFocus />
                    <Button size="sm" className="h-8 px-2" onClick={() => doRename(name)} data-testid="om-rename-save"><Check className="h-4 w-4" /></Button>
                    <Button size="sm" variant="ghost" className="h-8 px-2" onClick={() => setRenaming(null)}><X className="h-4 w-4" /></Button>
                  </div>
                ) : deleting === name ? (
                  <div className="space-y-2">
                    <p className="text-sm">Delete <span className="font-semibold">{name}</span> and move his {counts[name] || 0} item(s) to:</p>
                    <div className="flex items-center gap-2">
                      <Select value={reassignTo} onValueChange={setReassignTo}>
                        <SelectTrigger className="h-8 flex-1" data-testid="om-reassign-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {orderers.filter(o => o !== name).map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <Button size="sm" variant="destructive" className="h-8" onClick={() => doDelete(name)} data-testid="om-delete-confirm">Delete</Button>
                      <Button size="sm" variant="ghost" className="h-8 px-2" onClick={() => setDeleting(null)}><X className="h-4 w-4" /></Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm truncate">{name}</span>
                    <span className="flex items-center gap-1.5 shrink-0">
                      <Badge variant="outline" className="text-[10px]">{counts[name] || 0} item{(counts[name] || 0) === 1 ? '' : 's'}</Badge>
                      <Button size="sm" variant="ghost" className="h-8 px-2" data-testid={`om-rename-btn-${name}`}
                        onClick={() => { setRenaming(name); setNewName(name); setDeleting(null); }}><Pencil className="h-4 w-4" /></Button>
                      <Button size="sm" variant="ghost" className="h-8 px-2 text-red-600 hover:text-red-700" data-testid={`om-delete-btn-${name}`}
                        onClick={() => { setDeleting(name); setReassignTo('Admin'); setRenaming(null); }}><Trash2 className="h-4 w-4" /></Button>
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
