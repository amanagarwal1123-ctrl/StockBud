import { useEffect, useState } from 'react';
import axios from 'axios';
import { Plus, Check, Clock, Package, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function OrderManagement() {
  const { user, isAdmin } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stockAlerts, setStockAlerts] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [form, setForm] = useState({ item_name: '', quantity_kg: '', supplier: '', notes: '' });

  useEffect(() => {
    fetchOrders();
    fetchStockAlerts();
  }, []);

  const fetchOrders = async () => {
    try {
      const res = await axios.get(`${API}/orders`);
      setOrders(res.data.orders || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchStockAlerts = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${API}/notifications/categorized`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStockAlerts(res.data.notifications?.stock?.filter(n => n.type === 'stock_deficit' && !n.read) || []);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreate = async () => {
    if (!form.item_name || !form.quantity_kg) {
      toast.error('Item name and quantity required');
      return;
    }
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/orders/create`, {
        item_name: form.item_name,
        quantity_kg: parseFloat(form.quantity_kg),
        supplier: form.supplier,
        notes: form.notes
      }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success('Order created');
      setShowCreate(false);
      setForm({ item_name: '', quantity_kg: '', supplier: '', notes: '' });
      fetchOrders();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create order');
    }
  };

  const handleMarkReceived = async (orderId) => {
    try {
      const token = localStorage.getItem('token');
      await axios.put(`${API}/orders/${orderId}/received`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Order marked as received');
      fetchOrders();
    } catch (e) {
      toast.error('Failed to update order');
    }
  };

  const filteredOrders = filterStatus === 'all' ? orders : orders.filter(o => o.status === filterStatus);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="order-management-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Order Management</h1>
          <p className="text-sm text-muted-foreground mt-1">Track restock orders and stock deficit alerts</p>
        </div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild>
            <Button data-testid="create-order-btn"><Plus className="h-4 w-4 mr-2" />New Order</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create Restock Order</DialogTitle></DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label>Item Name</Label>
                <Input value={form.item_name} onChange={e => setForm({...form, item_name: e.target.value})} placeholder="Item name" data-testid="order-item-input" />
              </div>
              <div>
                <Label>Quantity (kg)</Label>
                <Input type="number" step="0.001" value={form.quantity_kg} onChange={e => setForm({...form, quantity_kg: e.target.value})} placeholder="Quantity in kg" data-testid="order-qty-input" />
              </div>
              <div>
                <Label>Supplier</Label>
                <Input value={form.supplier} onChange={e => setForm({...form, supplier: e.target.value})} placeholder="Supplier name" />
              </div>
              <div>
                <Label>Notes</Label>
                <Input value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="Optional notes" />
              </div>
              <Button onClick={handleCreate} className="w-full" data-testid="submit-order-btn">Place Order</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stock Deficit Alerts */}
      {stockAlerts.length > 0 && (
        <Card className="border-red-200 bg-red-50/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2 text-red-700">
              <AlertTriangle className="h-5 w-5" />Stock Deficit Alerts ({stockAlerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {stockAlerts.map((alert, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 bg-white rounded border border-red-100" data-testid={`stock-alert-${idx}`}>
                  <div>
                    <span className="font-medium text-sm">{alert.item_name}</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      Stock: {alert.current_stock}kg | Min: {alert.minimum_stock}kg | Deficit: {alert.deficit}kg
                    </span>
                  </div>
                  {alert.order_range_min && (
                    <Badge variant="outline" className="text-xs">
                      Order: {alert.order_range_min}-{alert.order_range_max} kg
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Orders Table */}
      <div className="flex gap-3 items-center">
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Filter" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Orders</SelectItem>
            <SelectItem value="ordered">Pending</SelectItem>
            <SelectItem value="received">Received</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">{filteredOrders.length} orders</span>
      </div>

      <Card>
        <CardContent className="pt-4">
          {filteredOrders.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <Package className="h-10 w-10 mx-auto mb-3 opacity-40" />
              <p>No orders yet</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead className="text-right">Qty (kg)</TableHead>
                    <TableHead>Supplier</TableHead>
                    <TableHead>Ordered By</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOrders.map((order, idx) => (
                    <TableRow key={idx} data-testid={`order-row-${idx}`}>
                      <TableCell>
                        <Badge variant={order.status === 'received' ? 'default' : 'secondary'} className={order.status === 'received' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                          {order.status === 'received' ? <Check className="h-3 w-3 mr-1" /> : <Clock className="h-3 w-3 mr-1" />}
                          {order.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium">{order.item_name}</TableCell>
                      <TableCell className="text-right font-mono">{order.quantity_kg}</TableCell>
                      <TableCell>{order.supplier || '-'}</TableCell>
                      <TableCell className="text-sm">{order.ordered_by}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{order.ordered_at?.slice(0, 10)}</TableCell>
                      <TableCell>
                        {order.status === 'ordered' && (
                          <Button size="sm" variant="outline" onClick={() => handleMarkReceived(order.id)} data-testid={`receive-btn-${idx}`}>
                            <Check className="h-3 w-3 mr-1" />Received
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
