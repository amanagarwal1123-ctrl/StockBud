import { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { Search, Plus, Trash2, Users, Link2, ChevronDown, ChevronRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ItemGroupManagement() {
  const [groups, setGroups] = useState([]);
  const [allItems, setAllItems] = useState([]);
  const [alreadyGrouped, setAlreadyGrouped] = useState([]);
  const [autoSuggestions, setAutoSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedItems, setSelectedItems] = useState([]);
  const [leaderItem, setLeaderItem] = useState('');
  const [createSearch, setCreateSearch] = useState('');
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [editingGroup, setEditingGroup] = useState(null); // null = create mode, string = editing group name

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      const [gRes, sRes] = await Promise.all([
        axios.get(`${API}/item-groups`),
        axios.get(`${API}/item-groups/suggestions`)
      ]);
      setGroups(gRes.data.groups || []);
      setAllItems(sRes.data.items || []);
      setAlreadyGrouped(sRes.data.already_grouped || []);
      setAutoSuggestions(sRes.data.auto_suggestions || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleSave = async () => {
    if (!leaderItem || selectedItems.length < 2) {
      toast.error('Select a leader and at least 2 items');
      return;
    }
    try {
      const token = localStorage.getItem('token');
      // If editing and leader changed, delete old group first
      if (editingGroup && editingGroup !== leaderItem) {
        await axios.delete(`${API}/item-groups/${encodeURIComponent(editingGroup)}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
      await axios.post(`${API}/item-groups`, {
        group_name: leaderItem,
        members: selectedItems
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(editingGroup ? `Group updated` : `Group "${leaderItem}" created`);
      setShowCreate(false);
      setSelectedItems([]);
      setLeaderItem('');
      setCreateSearch('');
      setEditingGroup(null);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const openEdit = (group) => {
    setEditingGroup(group.group_name);
    setSelectedItems([...group.members]);
    setLeaderItem(group.group_name);
    setCreateSearch('');
    setShowCreate(true);
  };

  const handleDelete = async (name) => {
    if (!window.confirm(`Delete group "${name}"?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API}/item-groups/${encodeURIComponent(name)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Group deleted');
      fetchAll();
    } catch (e) { toast.error('Failed'); }
  };

  const toggleItem = (itemName) => {
    setSelectedItems(prev =>
      prev.includes(itemName) ? prev.filter(i => i !== itemName) : [...prev, itemName]
    );
  };

  const filteredGroups = groups.filter(g =>
    !search || g.group_name.toLowerCase().includes(search.toLowerCase()) ||
    g.members.some(m => m.toLowerCase().includes(search.toLowerCase()))
  );

  const availableItems = useMemo(() => {
    return allItems.filter(i =>
      !alreadyGrouped.includes(i.item_name) || selectedItems.includes(i.item_name)
    ).filter(i =>
      !createSearch || i.item_name.toLowerCase().includes(createSearch.toLowerCase())
    );
  }, [allItems, alreadyGrouped, selectedItems, createSearch]);

  if (loading) return <div className="flex items-center justify-center h-64 text-muted-foreground">Loading...</div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4" data-testid="item-group-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Item Groups</h1>
          <p className="text-sm text-muted-foreground mt-1">Merge similar items for combined buffer & order calculations</p>
        </div>
        <Button onClick={() => setShowCreate(true)} data-testid="create-group-btn">
          <Plus className="h-4 w-4 mr-2" />New Group
        </Button>
      </div>

      {groups.length > 0 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search groups..." value={search} onChange={e => setSearch(e.target.value)}
            className="pl-10 max-w-sm" data-testid="group-search" />
        </div>
      )}

      {/* Auto-suggested groups from mappings */}
      {autoSuggestions.filter(s => !alreadyGrouped.includes(s.leader)).length > 0 && (
        <Card className="border-amber-200 bg-amber-50/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Link2 className="h-4 w-4 text-amber-600" />
              Auto-detected from Mappings
            </CardTitle>
            <p className="text-xs text-muted-foreground">These items share mappings and can be quickly grouped</p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {autoSuggestions.filter(s => !alreadyGrouped.includes(s.leader)).map(s => (
                <div key={s.leader} className="flex items-center justify-between p-2.5 bg-white rounded border border-amber-100"
                  data-testid={`auto-suggest-${s.leader}`}>
                  <div>
                    <span className="font-medium text-sm">{s.leader}</span>
                    <span className="text-xs text-muted-foreground ml-2">+ {s.members.filter(m => m !== s.leader).join(', ')}</span>
                  </div>
                  <Button size="sm" variant="outline" className="border-amber-300 text-amber-700"
                    onClick={async () => {
                      try {
                        const token = localStorage.getItem('token');
                        await axios.post(`${API}/item-groups`, { group_name: s.leader, members: s.members },
                          { headers: { Authorization: `Bearer ${token}` } });
                        toast.success(`Group "${s.leader}" created from mappings`);
                        fetchAll();
                      } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
                    }} data-testid={`auto-group-${s.leader}`}>
                    <Plus className="h-3.5 w-3.5 mr-1" />Group
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {filteredGroups.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <Users className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-semibold">No Item Groups</h3>
            <p className="text-sm text-muted-foreground mt-2">Create groups to merge similar items (e.g., "SNT 40 Premium" + "SNT 40")</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredGroups.map(g => (
            <Card key={g.group_name} data-testid={`group-card-${g.group_name}`}>
              <CardHeader className="pb-2 cursor-pointer" onClick={() => setExpandedGroup(expandedGroup === g.group_name ? null : g.group_name)}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {expandedGroup === g.group_name ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    <CardTitle className="text-base">{g.group_name}</CardTitle>
                    <Badge variant="secondary" className="text-xs">{g.members.length} items</Badge>
                  </div>
                  <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); handleDelete(g.group_name); }}>
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </Button>
                </div>
              </CardHeader>
              {expandedGroup === g.group_name && (
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Member Item</TableHead>
                        <TableHead className="text-xs">Role</TableHead>
                        <TableHead className="text-xs">Mapped Transaction Names</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {g.members.map(m => (
                        <TableRow key={m}>
                          <TableCell className="font-medium text-sm">{m}</TableCell>
                          <TableCell>
                            {m === g.group_name
                              ? <Badge className="bg-blue-100 text-blue-700 text-xs">Leader</Badge>
                              : <Badge variant="outline" className="text-xs">Member</Badge>}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {(g.mapped_items?.[m] || []).length > 0
                              ? <div className="flex flex-wrap gap-1">{g.mapped_items[m].map(t => <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>)}</div>
                              : <span className="italic">No mappings</span>}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Create Group Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Create Item Group</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input placeholder="Search items..." value={createSearch} onChange={e => setCreateSearch(e.target.value)}
                className="pl-10" data-testid="create-group-search" />
            </div>
            {selectedItems.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">Selected ({selectedItems.length}) — click one as Leader:</p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedItems.map(item => (
                    <Badge key={item}
                      className={`cursor-pointer text-xs ${item === leaderItem ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-blue-50'}`}
                      onClick={() => setLeaderItem(item)}
                      data-testid={`selected-${item}`}>
                      {item === leaderItem && <Link2 className="h-3 w-3 mr-1" />}{item}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            <div className="max-h-60 overflow-y-auto border rounded-md">
              {availableItems.map(i => (
                <label key={i.item_name} className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/50 cursor-pointer text-sm">
                  <Checkbox checked={selectedItems.includes(i.item_name)} onCheckedChange={() => toggleItem(i.item_name)} />
                  <span>{i.item_name}</span>
                  <Badge variant="outline" className="text-[10px] ml-auto">{i.stamp}</Badge>
                </label>
              ))}
              {availableItems.length === 0 && <p className="text-sm text-muted-foreground p-4 text-center">No items match</p>}
            </div>
            <Button onClick={handleCreate} className="w-full" disabled={!leaderItem || selectedItems.length < 2}
              data-testid="save-group-btn">
              Create Group ({selectedItems.length} items)
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
