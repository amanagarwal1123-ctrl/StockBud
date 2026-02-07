import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Bell, AlertTriangle, Info, CheckCircle2, Package, ShoppingCart, Tag, Box, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TAB_CONFIG = [
  { id: 'stock', label: 'Stock', icon: Package },
  { id: 'order', label: 'Orders', icon: ShoppingCart },
  { id: 'stamp', label: 'Stamps', icon: Tag },
  { id: 'polythene', label: 'Polythene', icon: Box },
  { id: 'general', label: 'General', icon: Bell },
];

export default function Notifications() {
  const [categorized, setCategorized] = useState({});
  const [totalUnread, setTotalUnread] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchNotifications = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${API}/notifications/categorized`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCategorized(res.data.notifications || {});
      setTotalUnread(res.data.total_unread || 0);
    } catch (e) {
      // Fallback to old endpoint
      try {
        const res = await axios.get(`${API}/notifications/my`);
        setCategorized({ general: res.data });
      } catch (e2) {
        console.error(e2);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  const markRead = async (notifId) => {
    try {
      await axios.post(`${API}/notifications/${notifId}/read`);
      fetchNotifications();
    } catch (e) { /* ignore */ }
  };

  const getSeverityStyle = (severity) => {
    switch (severity) {
      case 'critical': return 'border-red-400 bg-red-50';
      case 'warning': return 'border-amber-400 bg-amber-50';
      case 'success': return 'border-green-400 bg-green-50';
      case 'info': return 'border-blue-400 bg-blue-50';
      default: return 'border-border/40';
    }
  };

  const getSeverityIcon = (type, severity) => {
    if (severity === 'critical' || type === 'stock_deficit') return <AlertTriangle className="h-4 w-4 text-red-600" />;
    if (severity === 'warning') return <AlertTriangle className="h-4 w-4 text-amber-600" />;
    if (severity === 'success' || type === 'stamp_approval') return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    return <Info className="h-4 w-4 text-blue-600" />;
  };

  const renderNotifList = (notifs) => {
    if (!notifs || notifs.length === 0) {
      return (
        <div className="py-12 text-center text-muted-foreground">
          <Bell className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No notifications in this category</p>
        </div>
      );
    }
    return (
      <div className="space-y-2">
        {notifs.map((notif, idx) => (
          <Alert key={idx} className={`${getSeverityStyle(notif.severity)} cursor-pointer`}
            onClick={() => notif.id && !notif.read && markRead(notif.id)}
            data-testid={`notif-${idx}`}
          >
            {getSeverityIcon(notif.type, notif.severity)}
            <AlertDescription className="ml-2 flex-1">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium text-sm">{notif.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {notif.stamp && <Badge variant="outline" className="text-xs">{notif.stamp}</Badge>}
                    {notif.item_name && <span className="text-xs text-muted-foreground">{notif.item_name}</span>}
                    <span className="text-xs text-muted-foreground">
                      {notif.timestamp ? new Date(notif.timestamp).toLocaleString() : notif.created_at ? new Date(notif.created_at).toLocaleString() : ''}
                    </span>
                  </div>
                </div>
                {!notif.read && <Badge className="bg-red-500 text-white text-xs flex-shrink-0">New</Badge>}
              </div>
            </AlertDescription>
          </Alert>
        ))}
      </div>
    );
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="notifications-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Notifications</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {totalUnread > 0 ? `${totalUnread} unread` : 'All caught up'}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchNotifications}>
          <RefreshCw className="h-4 w-4 mr-2" />Refresh
        </Button>
      </div>

      <Tabs defaultValue="stock" className="space-y-4">
        <TabsList className="flex flex-wrap">
          {TAB_CONFIG.map(tab => {
            const count = (categorized[tab.id] || []).length;
            const unread = (categorized[tab.id] || []).filter(n => !n.read).length;
            return (
              <TabsTrigger key={tab.id} value={tab.id} className="gap-1.5" data-testid={`notif-tab-${tab.id}`}>
                <tab.icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{tab.label}</span>
                {unread > 0 && <Badge className="bg-red-500 text-white text-xs h-5 w-5 p-0 flex items-center justify-center rounded-full">{unread}</Badge>}
                {unread === 0 && count > 0 && <span className="text-xs text-muted-foreground">({count})</span>}
              </TabsTrigger>
            );
          })}
        </TabsList>

        {TAB_CONFIG.map(tab => (
          <TabsContent key={tab.id} value={tab.id}>
            {renderNotifList(categorized[tab.id])}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
