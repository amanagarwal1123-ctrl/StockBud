import { useEffect, useState } from 'react';
import axios from 'axios';
import { Plus, Check, Clock, Package, AlertTriangle, Trash2, ShoppingCart } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function OrderManagement() {
  const { user, isAdmin, isManager } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stockAlerts, setStockAlerts] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [form, setForm] = useState({ item_name: '', quantity_kg: '', supplier: '', notes: '' });

  useEffect(() => {
    fetchOrders();
    fetchStockAlerts();
    checkOverdue();
  }, []);

  const fetchOrders = async () => {
    try {
      const res = await axios.get(`${API}/orders`);
      setOrders(res.data.orders || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const fetchStockAlerts = async () => {
    try {
      const token = sessionStorage.getItem('token');
      const res = await axios.get(`${API}/notifications/categorized`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStockAlerts(res.data.notifications?.stock?.filter(n => n.type === 'stock_deficit' && !n.read) || []);
    } catch (e) { console.error(e); }
  };

  const checkOverdue = async () => {
    try {
      const token = sessionStorage.getItem('token');
      await axios.get(`${API}/orders/overdue`, { headers: { Authorization: `Bearer ${token}` } });
    } catch (e) { /* ignore */ }
  };

  const handleCreate = async () => {
    if (!form.item_name || !form.quantity_kg) {
      toast.error('Item name and quantity required');
      return;
    }
    try {
      const token = sessionStorage.getItem('token');
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

  const handleQuickOrder = (alert) => {
    setForm({
      item_name: alert.item_name,
      quantity_kg: String(alert.order_range_max || alert.deficit || ''),
      supplier: '',
      notes: `Stock deficit: ${alert.deficit} kg (current: ${alert.current_stock} kg, min: ${alert.minimum_stock} kg)`
    });
    setShowCreate(true);
  };

  const handleMarkReceived = async (orderId) => {
    try {
      const token = sessionStorage.getItem('token');
      await axios.put(`${API}/orders/${orderId}/received`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Order marked as received');
      fetchOrders();
    } catch (e) { toast.error('Failed to update order'); }
  };

  const handleCancel = async (orderId) => {
    if (!window.confirm('Cancel this order?')) return;
    try {
      const token = sessionStorage.getItem('token');
      await axios.delete(`${API}/orders/${orderId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Order cancelled');
      fetchOrders();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to cancel'); }
  };

  const getDaysAgo = (dateStr) => {
    if (!dateStr) return 0;
    return Math.floor((new Date() - new Date(dateStr)) / (1000 * 60 * 60 * 24));
  };

  const filteredOrders = filterStatus === 'all' ? orders : orders.filter(o => o.status === filterStatus);
  const pendingCount = orders.filter(o => o.status === 'ordered').length;
  const overdueCount = orders.filter(o => o.status === 'ordered' && getDaysAgo(o.ordered_at) > 7).length;

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-4 sm:space-y-6" data-testid="order-management-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Order Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {pendingCount > 0 ? `${pendingCount} pending` : 'No pending'} orders
            {overdueCount > 0 && <span className="text-red-600 font-semibold"> ({overdueCount} overdue!)</span>}
          </p>
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
                <Textarea value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="Optional notes" rows={2} />
              </div>
              <Button onClick={handleCreate} className="w-full" data-testid="submit-order-btn">
                <ShoppingCart className="h-4 w-4 mr-2" />Place Order
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stock Deficit Alerts with Quick Order */}
      {stockAlerts.length > 0 && (
        <Card className="border-red-200 bg-red-50/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2 text-red-700">
              <AlertTriangle className="h-5 w-5" />Stock Deficit Alerts ({stockAlerts.length})
            </CardTitle>
            <CardDescription>Click "Order" to quickly create a restock order from an alert</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {stockAlerts.map((alert, idx) => (
                <div key={idx} className="flex items-center justify-between p-2.5 bg-white rounded border border-red-100" data-testid={`stock-alert-${idx}`}>
                  <div className="min-w-0 flex-1">
                    <span className="font-medium text-sm">{alert.item_name}</span>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Stock: {alert.current_stock} kg | Min: {alert.minimum_stock} kg | Deficit: <span className="text-red-600 font-semibold">{alert.deficit} kg</span>
                    </div>
                    {alert.order_range_min && (
                      <span className="text-xs text-blue-600">Suggested: {alert.order_range_min} - {alert.order_range_max} kg</span>
                    )}
                  </div>
                  <Button size="sm" variant="outline" className="ml-3 border-red-300 text-red-700 hover:bg-red-50"
                    onClick={() => handleQuickOrder(alert)} data-testid={`quick-order-${idx}`}>
                    <ShoppingCart className="h-3.5 w-3.5 mr-1" />Order
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filter + Stats */}
      <div className="flex gap-3 items-center flex-wrap">
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Filter" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Orders ({orders.length})</SelectItem>
            <SelectItem value="ordered">Pending ({pendingCount})</SelectItem>
            <SelectItem value="received">Received ({orders.filter(o => o.status === 'received').length})</SelectItem>
          </SelectContent>
        </Select>
        {overdueCount > 0 && (
          <Badge className="bg-red-500 text-white">{overdueCount} Overdue (7+ days)</Badge>
        )}
      </div>

      {/* Orders Table */}
      <Card>
        <CardContent className="pt-4">
          {filteredOrders.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <Package className="h-10 w-10 mx-auto mb-3 opacity-40" />
              <p>No orders yet. Create one or click "Order" from stock alerts above.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table className="min-w-[640px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead className="text-right">Qty (kg)</TableHead>
                    <TableHead>Supplier</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead>Ordered</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOrders.map((order, idx) => {
                    const days = getDaysAgo(order.ordered_at);
                    const isOverdue = order.status === 'ordered' && days > 7;
                    return (
                      <TableRow key={idx} className={isOverdue ? 'bg-red-50 border-l-4 border-red-500' : ''} data-testid={`order-row-${idx}`}>
                        <TableCell>
                          {isOverdue ? (
                            <Badge className="bg-red-600 text-white">
                              <AlertTriangle className="h-3 w-3 mr-1" />Overdue
                            </Badge>
                          ) : (
                            <Badge variant={order.status === 'received' ? 'default' : 'secondary'} className={order.status === 'received' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}>
                              {order.status === 'received' ? <Check className="h-3 w-3 mr-1" /> : <Clock className="h-3 w-3 mr-1" />}
                              {order.status}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="font-medium max-w-[150px] truncate">{order.item_name}</TableCell>
                        <TableCell className="text-right font-mono">{order.quantity_kg}</TableCell>
                        <TableCell className="text-sm">{order.supplier || '-'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground max-w-[150px] truncate">{order.notes || '-'}</TableCell>
                        <TableCell className="text-sm">
                          <div>{order.ordered_at?.slice(0, 10)}</div>
                          <div className="text-xs text-muted-foreground">by {order.ordered_by} ({days}d ago)</div>
                          {order.status === 'received' && (
                            <div className="text-xs text-green-600">Rcvd: {order.received_at?.slice(0, 10)}</div>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {order.status === 'ordered' && (
                              <Button size="sm" variant="outline" onClick={() => handleMarkReceived(order.id)} data-testid={`receive-btn-${idx}`}>
                                <Check className="h-3 w-3 mr-1" />Received
                              </Button>
                            )}
                            {(isAdmin || isManager) && order.status === 'ordered' && (
                              <Button size="sm" variant="ghost" onClick={() => handleCancel(order.id)} data-testid={`cancel-btn-${idx}`}>
                                <Trash2 className="h-3 w-3 text-destructive" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
