import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, User, Package, Save } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (v) => v?.toLocaleString('en-IN', { maximumFractionDigits: 3 }) ?? '0';

export default function StampDetail() {
  const { stampName } = useParams();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState('');

  useEffect(() => { fetchData(); }, [stampName]);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('token');
      const [dRes, uRes] = await Promise.all([
        axios.get(`${API}/stamps/${encodeURIComponent(stampName)}/detail`),
        axios.get(`${API}/users/list`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setData(dRes.data);
      setUsers(uRes.data || []);
      setSelectedUser(dRes.data.assigned_user || '');
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleAssign = async () => {
    if (!selectedUser) { toast.error('Select an executive'); return; }
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/stamp-assignments`, {
        stamp: stampName, assigned_user: selectedUser
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`${selectedUser} assigned to ${stampName}`);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-muted-foreground">Loading...</div>;
  if (!data) return <div className="p-8 text-center text-muted-foreground">Stamp not found</div>;

  const executives = users.filter(u => u.role === 'executive' || u.role === 'admin');

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4" data-testid="stamp-detail-page">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/stamp-assignments')} data-testid="back-btn">
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">{stampName}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data.total_items} items | {fmt(data.total_net_wt_kg)} kg total stock
          </p>
        </div>
      </div>

      {/* Summary + Assignment */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <Package className="h-5 w-5 mx-auto mb-1 text-blue-600" />
            <div className="text-2xl font-bold font-mono text-blue-700" data-testid="total-items">{data.total_items}</div>
            <p className="text-xs text-blue-600/70">Items</p>
          </CardContent>
        </Card>
        <Card className="border-emerald-200 bg-emerald-50/50">
          <CardContent className="pt-4 pb-3 text-center">
            <div className="text-2xl font-bold font-mono text-emerald-700" data-testid="total-stock">{fmt(data.total_net_wt_kg)}</div>
            <p className="text-xs text-emerald-600/70">Total Stock (kg)</p>
          </CardContent>
        </Card>
        <Card className={`${data.assigned_user ? 'border-purple-200 bg-purple-50/50' : 'border-amber-200 bg-amber-50/50'}`}>
          <CardContent className="pt-4 pb-3 text-center">
            <User className={`h-5 w-5 mx-auto mb-1 ${data.assigned_user ? 'text-purple-600' : 'text-amber-600'}`} />
            <div className={`text-lg font-bold ${data.assigned_user ? 'text-purple-700' : 'text-amber-700'}`}
              data-testid="assigned-user">
              {data.assigned_user || 'Unassigned'}
            </div>
            <p className="text-xs opacity-70">Executive</p>
          </CardContent>
        </Card>
      </div>

      {/* Assign Executive */}
      {isAdmin && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Assign Sales Executive</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <Select value={selectedUser} onValueChange={setSelectedUser}>
                  <SelectTrigger data-testid="assign-exec-select"><SelectValue placeholder="Select Executive" /></SelectTrigger>
                  <SelectContent>
                    {executives.map(u => (
                      <SelectItem key={u.username} value={u.username}>{u.username} ({u.role})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleAssign} data-testid="assign-exec-btn">
                <Save className="h-4 w-4 mr-2" />Assign
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Items Table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Items in {stampName}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">#</TableHead>
                  <TableHead className="text-xs">Item Name</TableHead>
                  <TableHead className="text-xs text-right">Net Wt (kg)</TableHead>
                  <TableHead className="text-xs text-right">Gross Wt (kg)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((item, idx) => (
                  <TableRow key={item.item_name} data-testid={`stamp-item-${idx}`}>
                    <TableCell className="text-xs text-muted-foreground">{idx + 1}</TableCell>
                    <TableCell className="font-medium text-sm">{item.item_name}</TableCell>
                    <TableCell className={`text-right font-mono text-sm ${item.net_wt_kg < 0 ? 'text-red-600' : ''}`}>
                      {fmt(item.net_wt_kg)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">{fmt(item.gr_wt_kg)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
